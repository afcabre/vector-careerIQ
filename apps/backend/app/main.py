from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.services.operator_store import seed_operator
from app.services.person_store import seed_persons
from app.services.prompt_config_store import seed_prompt_configs


app = FastAPI(
    title="Opportunity Workspace API",
    version="0.0.1",
    description="Backend scaffold aligned with the current SDD artifacts.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    seed_operator()
    seed_persons()
    seed_prompt_configs()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
