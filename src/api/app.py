from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.schemas import ErrorResponse, IncidentCreateRequest, IncidentResponse
from src.config import settings
from src.errors.app_error import AppError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agente de Triagem de Incidentes Técnicos",
    version="0.1.0",
    description="API que recebe incidentes textuais e executa fluxo LangGraph de triagem.",
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    cid = getattr(request.state, "correlation_id", None)
    body = exc.to_dict(correlation_id=cid)
    if settings.log_level == "DEBUG":
        logger.exception("AppError: %s", exc.message)
    else:
        logger.error("AppError %s: %s", exc.code, exc.message, extra={"context": exc.context})
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    cid = getattr(request.state, "correlation_id", None)
    tb = traceback.format_exc()
    logger.error("Unhandled exception: %r\n%s", exc, tb)
    body = ErrorResponse(code="UNEXPECTED_ERROR", message="erro interno", correlation_id=cid)
    return JSONResponse(status_code=500, content=body.model_dump())


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    import uuid
    cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    request.state.correlation_id = cid
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = cid
    return response


@app.post("/incidents", response_model=IncidentResponse, summary="Submete incidente para triagem")
async def create_incident(payload: IncidentCreateRequest, request: Request):
    from src.graph.service import run_triage
    raw = payload.model_dump()
    result = await run_triage(raw)
    return IncidentResponse.model_validate(result)


@app.get("/incidents/{execution_id}", response_model=IncidentResponse, summary="Recupera triagem por execution_id")
def get_incident(execution_id: str):
    from src.memory.store import execution_store
    data = execution_store.load(execution_id)
    if not data or "output_dto" not in data:
        return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "message": "execution_id não encontrado"})
    return IncidentResponse.model_validate(data["output_dto"])


@app.get("/incidents/{execution_id}/trace", summary="Timeline de observabilidade da execução")
def get_trace(execution_id: str):
    from src.observability.trace import build_timeline
    events = build_timeline(execution_id)
    return {"execution_id": execution_id, "events": events}


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "storage": str(settings.storage_path), "max_steps": settings.max_steps}
