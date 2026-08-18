import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import Settings, get_settings, settings
from .datasets import router as datasets_router
from .database import get_session
from .reference import ReferenceDataError, load_administrative_reference

app = FastAPI(title="Intelligent Data Quality Assessment")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(datasets_router)


@app.middleware("http")
async def request_identifier(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    detail = {**detail, "request_id": request.state.request_id}
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)


@app.get("/api/health")
def health(
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    try:
        load_administrative_reference(config.master_reference_path)
    except ReferenceDataError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    return {"status": "ok"}


@app.get("/api/config")
def public_config(config: Settings = Depends(get_settings)) -> dict[str, int]:
    return {"max_upload_mb": config.max_upload_mb}
