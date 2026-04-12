from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.settings import get_settings
from app.services.ai_runtime_config_store import seed_ai_runtime_config
from app.services.operator_store import seed_operator
from app.services.person_store import seed_persons
from app.services.prompt_config_store import seed_prompt_configs
from app.services.search_provider_store import seed_search_provider_configs


app = FastAPI(
    title="Opportunity Workspace API",
    version="0.0.1",
    description="Backend scaffold aligned with the current SDD artifacts.",
)

def _parse_cors_origins(value: str) -> list[str]:
    items = [item.strip() for item in (value or "").split(",")]
    return [item for item in items if item]


settings = get_settings()
cors_origins = _parse_cors_origins(settings.cors_allow_origins)
if not cors_origins:
    cors_origins = ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    seed_operator()
    seed_persons()
    seed_ai_runtime_config()
    seed_prompt_configs()
    seed_search_provider_configs()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
