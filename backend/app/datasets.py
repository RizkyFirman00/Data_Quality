import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .column_roles import MANUAL_ROLES, prepare_column_roles
from .auth import AuthContext, require_user
from .dataset_access import dataset_scope
from .database import get_session
from .ingestion import DatasetParseError, ParsedColumn, ParsedDataset, parse_dataset
from .models import ColumnProfile, Dataset, DatasetStatus, Finding
from .normalization import json_key, read_snapshot, write_snapshot
from .profiling import profile_dataset
from .quality import (
    QualityAssessmentError,
    check_execution_metadata,
    ordered_findings,
    planned_quality_checks,
    quality_findings,
)
from .reference import ReferenceDataError, load_administrative_reference
from .schemas import DatasetDetailResponse, DatasetPageResponse, DatasetPreviewResponse, DatasetSummaryResponse
from .semantic import (
    apply_action_summaries,
    apply_semantic_roles,
    semantic_analysis,
    summarize_finding_actions,
)
from .storage import delete_storage_key, persist_original, resolve_storage_key

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
logger = logging.getLogger(__name__)


class ColumnRolesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roles: dict[str, Literal["auto", "identifier", "numeric", "percentage", "categorical", "free_text", "date", "latitude", "longitude"]] = Field(max_length=1000)
    expected_revision: int = Field(ge=0)


@router.post("/{dataset_id}/column-roles", response_model=DatasetDetailResponse)
def update_column_roles(
    dataset_id: uuid.UUID, payload: ColumnRolesRequest,
    session: Session = Depends(get_session), config: Settings = Depends(get_settings),
    context: AuthContext = Depends(require_user),
) -> Dataset:
    locked = session.scalar(select(Dataset).where(Dataset.id == dataset_id, *dataset_scope(context)).with_for_update())
    if locked is None:
        raise HTTPException(status_code=404, detail={"message": "Dataset tidak ditemukan."})
    dataset = _load_dataset(session, dataset_id, context)
    metadata = dict(dataset.source_metadata or {})
    if dataset.status != DatasetStatus.COMPLETED:
        raise HTTPException(status_code=409, detail={"message": "Hanya assessment selesai yang dapat diperiksa ulang."})
    if payload.expected_revision != metadata.get("role_revision", 0):
        raise HTTPException(status_code=409, detail={"message": "Pengaturan sudah berubah. Muat ulang halaman sebelum menyimpan."})
    try:
        if dataset.original_file_key:
            parsed = parse_dataset(
                resolve_storage_key(config.storage_root, dataset.original_file_key),
                dataset.original_filename, config.max_upload_mb * 10 * 1024 * 1024,
                config.max_dataset_rows, config.max_dataset_columns, config.max_dataset_cells,
            )
        elif dataset.snapshot_key:
            rows, total = read_snapshot(config.storage_root, dataset.snapshot_key, page_size=config.max_dataset_rows)
            if not rows or len(rows) != total:
                raise DatasetParseError("Snapshot lengkap tidak tersedia.")
            parsed = ParsedDataset(
                [ParsedColumn(c.original_name, c.display_name, c.display_name) for c in dataset.column_profiles],
                [{k: v for k, v in row.items() if k != "_source_row"} for row in rows],
                [row["_source_row"] for row in rows], dataset.worksheet_name,
            )
        else:
            raise DatasetParseError("Sumber assessment tidak tersedia.")
        profile = profile_dataset(parsed, config.preview_rows)
        semantic_roles = metadata.get("semantic_roles", {})
        semantic_roles = semantic_roles if isinstance(semantic_roles, dict) else {}
        profile = apply_semantic_roles(profile, semantic_roles)
        overrides = dict(metadata.get("column_roles", {}))
        _, automatic = prepare_column_roles(profile, trusted_columns=semantic_roles)
        editable = {c["column"] for c in automatic["columns"] if c["status"] == "needs_role"} | set(overrides)
        for name, role in payload.roles.items():
            if name not in editable:
                raise HTTPException(status_code=422, detail={"message": "Kolom tidak tersedia untuk konfirmasi role. Header kosong harus diperbaiki di sumber."})
            if role == "auto":
                overrides.pop(name, None)
            elif role in MANUAL_ROLES:
                overrides[name] = role
        profile, coverage = prepare_column_roles(profile, overrides, trusted_columns=semantic_roles)
        changed = {
            c.display_name for c in profile.columns
            if next((old.candidate_role for old in dataset.column_profiles if old.display_name == c.display_name), None) != c.candidate_role
        }
        reference = load_administrative_reference(config.master_reference_path)
        executed: list[str] = []
        results = quality_findings(parsed, profile, reference, config.max_findings, executed_checks=executed)
        retained_semantic = [f for f in dataset.findings if f.issue_type in {"POTENTIAL_TYPO", "SEMANTIC_MISMATCH"} and f.column not in changed]
        if len(results) + len(retained_semantic) > config.max_findings:
            raise QualityAssessmentError("Hasil pemeriksaan melebihi batas temuan.")
    except HTTPException:
        raise
    except (DatasetParseError, QualityAssessmentError, ReferenceDataError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"message": "Pemeriksaan ulang tidak dapat diselesaikan; hasil sebelumnya tetap tersimpan."}) from exc

    previous = {
        json_key([f.row, f.column, f.issue_type, f.original_value]): f
        for f in dataset.findings
    }
    findings = []
    for result in results:
        key = json_key([result.row, result.column, result.issue_type, result.original_value])
        finding = previous.get(key) or Finding()
        for name, value in result.__dict__.items():
            setattr(finding, name, value)
        findings.append(finding)
    findings.extend(retained_semantic)
    positions = {c.display_name: index for index, c in enumerate(profile.columns)}
    findings.sort(key=lambda f: (f.row, positions.get(f.column, -1), f.issue_type))
    for position, finding in enumerate(findings):
        finding.position = position
    dataset.findings = findings
    stored_columns = {c.display_name: c for c in dataset.column_profiles}
    updated_columns = []
    for result in profile.columns:
        stored = stored_columns.get(result.display_name) or ColumnProfile()
        for name, value in result.__dict__.items():
            setattr(stored, name, value)
        updated_columns.append(stored)
    dataset.column_profiles = updated_columns
    dataset.preview = profile.preview
    dataset.row_count, dataset.column_count = profile.row_count, profile.column_count
    dataset.finding_count = len(findings)
    dataset.assessment_status = "NEEDS_CORRECTION" if any(f.severity == "HIGH" for f in findings) else "PASSED"
    dataset.source_metadata = {
        **metadata, "column_roles": overrides, "column_assessment": coverage,
        "role_revision": payload.expected_revision + 1,
        "quality_checks": check_execution_metadata(profile, executed),
        "role_checks_updated_at": datetime.now(timezone.utc).isoformat(),
        "semantic_recheck": "not_run", "action_summary_available": False,
        "action_summary_ai_count": 0, "action_summary_fallback_count": 0,
    }
    session.commit()
    return _load_dataset(session, dataset_id, context)


def _load_dataset(session: Session, dataset_id: uuid.UUID, context: AuthContext) -> Dataset:
    dataset = session.scalar(
        select(Dataset)
        .options(selectinload(Dataset.column_profiles), selectinload(Dataset.findings), selectinload(Dataset.owner))
        .where(Dataset.id == dataset_id, *dataset_scope(context))
    )
    if not dataset:
        raise HTTPException(status_code=404, detail={"message": "Dataset tidak ditemukan."})
    return dataset


async def _stage_upload(upload: UploadFile, target: Path, limit: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with target.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={"message": "Ukuran file melebihi batas yang diizinkan."},
                )
            handle.write(chunk)
    if size == 0:
        raise DatasetParseError("File yang diunggah kosong.")


def _upload_identity(upload: UploadFile) -> tuple[str, str]:
    filename = Path(upload.filename or "").name
    if len(filename) > 255:
        raise HTTPException(status_code=422, detail={"message": "Nama file terlalu panjang."})
    if "\x00" in filename:
        raise HTTPException(status_code=422, detail={"message": "Nama file tidak valid."})
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise DatasetParseError("Format file tidak didukung. Gunakan CSV, XLSX, atau XLS.")
    return filename or "tanpa-nama", suffix


@router.post("/preview", response_model=DatasetPreviewResponse)
async def preview_upload(
    file: UploadFile = File(...),
    config: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Profile a temporary upload without creating an assessment or calling the LLM."""
    staged: Path | None = None
    try:
        filename, suffix = _upload_identity(file)
        staged = config.storage_root / "staging" / f"preview-{uuid.uuid4()}{suffix}"
        await _stage_upload(file, staged, config.max_upload_mb * 1024 * 1024)
        parsed = await run_in_threadpool(
            parse_dataset,
            staged,
            filename,
            config.max_upload_mb * 10 * 1024 * 1024,
            config.max_dataset_rows,
            config.max_dataset_columns,
            config.max_dataset_cells,
        )
        profile = await run_in_threadpool(profile_dataset, parsed, min(config.preview_rows, 10))
        semantic_enabled = bool(config.llm_base_url and config.llm_api_key and config.llm_model)
        return {
            "filename": filename,
            "worksheet_name": parsed.worksheet_name,
            "row_count": profile.row_count,
            "column_count": profile.column_count,
            "duplicate_row_count": profile.duplicate_row_count,
            "rows": profile.preview,
            "columns": profile.columns,
            "checks": planned_quality_checks(profile, semantic_enabled=semantic_enabled),
        }
    except HTTPException:
        raise
    except DatasetParseError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    except Exception as exc:
        logger.exception("Dataset preview failed")
        raise HTTPException(
            status_code=500,
            detail={"message": "Preview dataset tidak dapat dibuat."},
        ) from exc
    finally:
        if staged:
            staged.unlink(missing_ok=True)
        await file.close()


@router.post("", response_model=DatasetDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    parent_dataset_id: uuid.UUID | None = Form(None),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
    context: AuthContext = Depends(require_user),
) -> Dataset:
    try:
        filename, suffix = _upload_identity(file)
        if parent_dataset_id:
            _load_dataset(session, parent_dataset_id, context)
    except HTTPException:
        await file.close()
        raise
    except DatasetParseError as exc:
        await file.close()
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    dataset = Dataset(
        original_filename=filename or "tanpa-nama",
        source_type="file_upload",
        file_type=suffix.removeprefix(".") or "unknown",
        status=DatasetStatus.PROCESSING,
        parent_dataset_id=parent_dataset_id,
        owner_id=context.user.id,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    staged = config.storage_root / "staging" / f"{dataset.id}{suffix or '.upload'}"
    original_key: str | None = None
    snapshot_key: str | None = None
    try:
        await _stage_upload(file, staged, config.max_upload_mb * 1024 * 1024)
        parsed = await run_in_threadpool(
            parse_dataset,
            staged,
            filename,
            config.max_upload_mb * 10 * 1024 * 1024,
            config.max_dataset_rows,
            config.max_dataset_columns,
            config.max_dataset_cells,
        )
        original_key = await run_in_threadpool(
            persist_original, staged, config.storage_root, dataset.id, suffix
        )
        snapshot_key = await run_in_threadpool(
            write_snapshot, parsed, config.storage_root, dataset.id
        )
        profile = await run_in_threadpool(profile_dataset, parsed, config.preview_rows)
        reference = await run_in_threadpool(
            load_administrative_reference, config.master_reference_path
        )
        semantic = await run_in_threadpool(semantic_analysis, parsed, profile, config)
        profile = apply_semantic_roles(profile, semantic.roles)
        profile, coverage = prepare_column_roles(profile, trusted_columns=semantic.roles)
        executed_checks: list[str] = []
        finding_results = await run_in_threadpool(
            quality_findings, parsed, profile, reference, config.max_findings,
            executed_checks=executed_checks,
        )
        pending_columns = {c.display_name for c in profile.columns if c.candidate_role == "unclassified"}
        finding_results = ordered_findings(parsed, finding_results + [f for f in semantic.findings if f.column not in pending_columns])
        if len(finding_results) > config.max_findings:
            raise QualityAssessmentError("Dataset menghasilkan terlalu banyak temuan kualitas.")
        action_summaries = await run_in_threadpool(
            summarize_finding_actions, finding_results, config
        )
        finding_results = apply_action_summaries(finding_results, action_summaries)
        dataset.original_file_key = original_key
        dataset.snapshot_key = snapshot_key
        dataset.worksheet_name = parsed.worksheet_name
        dataset.row_count = profile.row_count
        dataset.column_count = profile.column_count
        dataset.duplicate_row_count = profile.duplicate_row_count
        dataset.preview = profile.preview
        dataset.column_profiles = [
            ColumnProfile(**result.__dict__) for result in profile.columns
        ]
        dataset.finding_count = len(finding_results)
        dataset.source_metadata = {
            "column_assessment": coverage,
            "column_roles": {},
            "role_revision": 0,
            "quality_checks": check_execution_metadata(profile, executed_checks),
            "semantic_available": semantic.available,
            "semantic_roles": semantic.roles,
            "action_summary_available": action_summaries.available,
            "action_summary_ai_count": action_summaries.ai_count,
            "action_summary_fallback_count": len(action_summaries.summaries) - action_summaries.ai_count,
        }
        dataset.findings = [
            Finding(position=position, **result.__dict__)
            for position, result in enumerate(finding_results)
        ]
        dataset.status = DatasetStatus.COMPLETED
        dataset.assessment_status = (
            "NEEDS_CORRECTION"
            if any(finding.severity == "HIGH" for finding in finding_results)
            else "PASSED"
        )
        dataset.completed_at = datetime.now(timezone.utc)
        session.commit()
        return _load_dataset(session, dataset.id, context)
    except HTTPException as exc:
        dataset.status = DatasetStatus.FAILED
        dataset.failure_message = exc.detail.get("message", "Upload gagal.") if isinstance(exc.detail, dict) else str(exc.detail)
        session.commit()
        delete_storage_key(config.storage_root, original_key)
        delete_storage_key(config.storage_root, snapshot_key)
        raise
    except (DatasetParseError, QualityAssessmentError) as exc:
        dataset.status = DatasetStatus.FAILED
        dataset.failure_message = str(exc)
        session.commit()
        delete_storage_key(config.storage_root, original_key)
        delete_storage_key(config.storage_root, snapshot_key)
        raise HTTPException(status_code=422, detail={"message": str(exc), "dataset_id": str(dataset.id)}) from exc
    except ReferenceDataError as exc:
        dataset.status = DatasetStatus.FAILED
        dataset.failure_message = str(exc)
        session.commit()
        delete_storage_key(config.storage_root, original_key)
        delete_storage_key(config.storage_root, snapshot_key)
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "dataset_id": str(dataset.id)},
        ) from exc
    except Exception as exc:
        logger.exception("Dataset processing failed", extra={"dataset_id": str(dataset.id)})
        session.rollback()
        failed = session.get(Dataset, dataset.id)
        if failed:
            failed.status = DatasetStatus.FAILED
            failed.failure_message = "Dataset tidak dapat diproses."
            session.commit()
        delete_storage_key(config.storage_root, original_key)
        delete_storage_key(config.storage_root, snapshot_key)
        raise HTTPException(
            status_code=500,
            detail={"message": "Dataset tidak dapat diproses.", "dataset_id": str(dataset.id)},
        ) from exc
    finally:
        staged.unlink(missing_ok=True)
        await file.close()


@router.get("", response_model=list[DatasetSummaryResponse])
def list_datasets(session: Session = Depends(get_session), context: AuthContext = Depends(require_user)) -> list[Dataset]:
    return list(session.scalars(select(Dataset).where(*dataset_scope(context)).options(selectinload(Dataset.owner)).order_by(Dataset.created_at.desc(), Dataset.id.desc())))


@router.get("/page", response_model=DatasetPageResponse)
def dataset_page(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=255),
    assessment_status: str | None = Query(None, pattern="^(PASSED|NEEDS_CORRECTION|PROCESSING|FAILED)$"),
    session: Session = Depends(get_session), context: AuthContext = Depends(require_user),
):
    conditions = dataset_scope(context)
    if search.strip():
        conditions.append(Dataset.original_filename.icontains(search.strip(), autoescape=True))
    if assessment_status in {"PASSED", "NEEDS_CORRECTION"}:
        conditions.extend([Dataset.status == DatasetStatus.COMPLETED, Dataset.assessment_status == assessment_status])
    elif assessment_status:
        conditions.append(Dataset.status == DatasetStatus(assessment_status))
    total = session.scalar(select(func.count()).select_from(Dataset).where(*conditions)) or 0
    items = list(session.scalars(select(Dataset).where(*conditions).options(selectinload(Dataset.owner))
        .order_by(Dataset.created_at.desc(), Dataset.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


class DatasetSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


def _change_deletion(payload: DatasetSelection, session: Session, context: AuthContext, *, restore: bool = False):
    ids = set(payload.dataset_ids)
    datasets = list(session.scalars(select(Dataset).where(Dataset.id.in_(ids), *dataset_scope(context, deleted=restore)).with_for_update()))
    if len(datasets) != len(ids):
        raise HTTPException(status_code=404, detail={"message": "Ada dataset yang tidak tersedia atau tidak dapat diakses. Tidak ada perubahan."})
    if any(item.status == DatasetStatus.PROCESSING for item in datasets):
        raise HTTPException(status_code=409, detail={"message": "Dataset yang masih diproses belum dapat dihapus."})
    timestamp = None if restore else datetime.now(timezone.utc)
    for item in datasets:
        item.deleted_at = timestamp
    session.commit()
    return {"dataset_ids": [str(item.id) for item in datasets], "count": len(datasets)}


@router.post("/bulk-delete")
def bulk_delete(payload: DatasetSelection, session: Session = Depends(get_session), context: AuthContext = Depends(require_user)):
    return _change_deletion(payload, session, context)


@router.post("/bulk-restore")
def bulk_restore(payload: DatasetSelection, session: Session = Depends(get_session), context: AuthContext = Depends(require_user)):
    return _change_deletion(payload, session, context, restore=True)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: uuid.UUID, session: Session = Depends(get_session), context: AuthContext = Depends(require_user)):
    return _change_deletion(DatasetSelection(dataset_ids=[dataset_id]), session, context)


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(dataset_id: uuid.UUID, session: Session = Depends(get_session), context: AuthContext = Depends(require_user)) -> Dataset:
    return _load_dataset(session, dataset_id, context)
