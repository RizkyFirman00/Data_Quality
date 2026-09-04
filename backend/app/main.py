import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import Settings, get_settings, settings
from .auth import AuthContext, require_user, router as auth_router
from .datasets import router as datasets_router
from .database import get_session
from .reference import ReferenceDataError, load_administrative_reference
from .workflow import router as workflow_router

app = FastAPI(
    title="Intelligent Data Quality Assessment",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(datasets_router, dependencies=[Depends(require_user)])
app.include_router(workflow_router, dependencies=[Depends(require_user)])


@app.get("/openapi.json", include_in_schema=False)
def protected_openapi(_auth: AuthContext = Depends(require_user)) -> JSONResponse:
    return JSONResponse(app.openapi())


@app.get("/docs", include_in_schema=False)
def protected_docs(_auth: AuthContext = Depends(require_user)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Intelligent Data Quality Assessment - API",
    )


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
def public_config(
    config: Settings = Depends(get_settings),
    _auth: AuthContext = Depends(require_user),
) -> dict[str, int | bool]:
    return {
        "max_upload_mb": config.max_upload_mb,
        "backoffice_enabled": bool(config.backoffice_api_base_url),
        "llm_max_candidates": config.llm_max_candidates,
    }


@app.get("/api/reference-data")
def reference_data(
    search: str | None = None,
    city_code: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    config: Settings = Depends(get_settings),
    _auth: AuthContext = Depends(require_user),
) -> dict[str, object]:
    reference = load_administrative_reference(config.master_reference_path)
    rows = []
    for village in reference.villages_by_code.values():
        district = reference.districts_by_code[village.parent_code or ""]
        city = reference.cities_by_code[village.city_code or ""]
        rows.append({
            "city_code": city.code,
            "city_name": city.name,
            "district_code": district.code,
            "district_name": district.name,
            "village_code": village.code,
            "village_name": village.name,
        })
    if city_code:
        rows = [row for row in rows if row["city_code"] == city_code]
    if search:
        needle = search.strip().casefold()
        rows = [row for row in rows if needle in " ".join(str(value) for value in row.values()).casefold()]
    rows.sort(key=lambda row: (row["city_code"], row["district_code"], row["village_code"]))
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "items": rows[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": {
            "cities": len(reference.cities_by_code),
            "districts": len(reference.districts_by_code),
            "villages": len(reference.villages_by_code),
            "sha256": reference.sha256,
        },
    }


@app.get("/api/settings")
def safe_settings(
    config: Settings = Depends(get_settings),
    _auth: AuthContext = Depends(require_user),
) -> dict[str, object]:
    reference = load_administrative_reference(config.master_reference_path)
    return {
        "limits": {
            "upload_mb": config.max_upload_mb,
            "rows": config.max_dataset_rows,
            "columns": config.max_dataset_columns,
            "cells": config.max_dataset_cells,
            "findings": config.max_findings,
        },
        "formats": {"upload": ["CSV", "XLSX", "XLS"], "report": ["CSV", "XLSX", "PDF"]},
        "semantic": {
            "enabled": bool(config.llm_base_url and config.llm_api_key and config.llm_model),
            "max_columns": config.llm_max_columns,
            "max_candidates": config.llm_max_candidates,
        },
        "backoffice_enabled": bool(config.backoffice_api_base_url),
        "authentication": {"type": "local_account", "session_hours": config.auth_session_hours},
        "reference": {
            "sha256": reference.sha256,
            "cities": len(reference.cities_by_code),
            "districts": len(reference.districts_by_code),
            "villages": len(reference.villages_by_code),
        },
    }
