from fastapi import FastAPI

from app.api.routes import router as api_router


app = FastAPI(
    title="Opportunity Workspace API",
    version="0.0.1",
    description="Backend scaffold aligned with the current SDD artifacts.",
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
