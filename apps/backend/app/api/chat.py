import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.core.security import SessionData, require_operator_session
from app.services.conversation_store import (
    ConversationRecord,
    MessageRecord,
    append_message,
    get_or_create_conversation,
)
from app.services.person_store import get_person


router = APIRouter()


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str


class ConversationResponse(BaseModel):
    conversation_id: str
    person_id: str
    status: str
    last_message_at: str
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class SendMessageResponse(BaseModel):
    conversation: ConversationResponse
    assistant_message: MessageResponse


def _to_conversation_response(record: ConversationRecord) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=record["conversation_id"],
        person_id=record["person_id"],
        status=record["status"],
        last_message_at=record["last_message_at"],
        messages=[MessageResponse(**item) for item in record["messages"]],
    )


def _to_message_response(message: MessageRecord) -> MessageResponse:
    return MessageResponse(**message)


def _build_assistant_reply(person_id: str, raw_message: str) -> str:
    person = get_person(person_id)
    if not person:
        return (
            "Recibi tu mensaje. No pude cargar el perfil, pero el mensaje "
            "quedo registrado en la conversacion."
        )

    top_role = person["target_roles"][0] if person["target_roles"] else "rol objetivo"
    return (
        f"Contexto activo para {person['full_name']} ({top_role}). "
        f"Mensaje recibido: {raw_message}. "
        "Siguiente paso sugerido: convertir esta solicitud en accion sobre "
        "vacantes, analisis o preparacion de postulacion."
    )


def _serialize_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _require_person(person_id: str) -> None:
    if not get_person(person_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )


@router.get("/conversation")
def get_conversation(
    person_id: str,
    _: SessionData = Depends(require_operator_session),
) -> ConversationResponse:
    _require_person(person_id)
    conversation = get_or_create_conversation(person_id)
    return _to_conversation_response(conversation)


@router.post("")
def send_message(
    person_id: str,
    payload: SendMessageRequest,
    _: SessionData = Depends(require_operator_session),
) -> SendMessageResponse:
    _require_person(person_id)
    append_message(person_id, "user", payload.message.strip())
    assistant_text = _build_assistant_reply(person_id, payload.message.strip())
    updated = append_message(person_id, "assistant", assistant_text)
    assistant_message = updated["messages"][-1]
    return SendMessageResponse(
        conversation=_to_conversation_response(updated),
        assistant_message=_to_message_response(assistant_message),
    )


@router.post("/stream")
async def stream_message(
    person_id: str,
    payload: SendMessageRequest,
    _: SessionData = Depends(require_operator_session),
) -> StreamingResponse:
    _require_person(person_id)
    append_message(person_id, "user", payload.message.strip())
    assistant_text = _build_assistant_reply(person_id, payload.message.strip())
    updated = append_message(person_id, "assistant", assistant_text)

    async def event_generator():
        yield _serialize_sse("message_start", {"person_id": person_id})
        for token in assistant_text.split(" "):
            yield _serialize_sse("message_delta", {"delta": f"{token} "})
            await asyncio.sleep(0.015)
        yield _serialize_sse(
            "message_complete",
            {
                "conversation_id": updated["conversation_id"],
                "person_id": person_id,
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
