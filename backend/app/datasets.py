import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .database import get_session
from .ingestion import DatasetParseError, parse_dataset
from .models import ColumnProfile, Dataset, DatasetStatus, Finding
from .normalization import write_snapshot
from .profiling import profile_dataset
from .quality import QualityAssessmentError, quality_findings
from .reference import ReferenceDataError, load_administrative_reference
from .schemas import DatasetDetailResponse, DatasetSummaryResponse
from .storage import delete_storage_key, persist_original

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
logger = logging.getLogger(__name__)


def _load_dataset(session: Session, dataset_id: uuid.UUID) -> Dataset:
    dataset = session.scalar(
        select(Dataset)
        .options(selectinload(Dataset.column_profiles), selectinload(Dataset.findings))
        .where(Dataset.id == dataset_id)
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


@router.post("", response_model=DatasetDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> Dataset:
    filename = Path(file.filename or "").name
    if len(filename) > 255:
        raise HTTPException(status_code=422, detail={"message": "Nama file terlalu panjang."})
    if "\x00" in filename:
        raise HTTPException(status_code=422, detail={"message": "Nama file tidak valid."})
    suffix = Path(filename).suffix.lower()
    dataset = Dataset(
        original_filename=filename or "tanpa-nama",
        source_type="file_upload",
        file_type=suffix.removeprefix(".") or "unknown",
        status=DatasetStatus.PROCESSING,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    staged = config.storage_root / "staging" / f"{dataset.id}{suffix or '.upload'}"
    original_key: str | None = None
    snapshot_key: str | None = None
    try:
        if suffix not in {".csv", ".xlsx"}:
            raise DatasetParseError("Format file tidak didukung. Gunakan CSV atau XLSX.")
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
        finding_results = await run_in_threadpool(
            quality_findings, parsed, reference, config.max_findings
        )
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
        dataset.findings = [
            Finding(position=position, **result.__dict__)
            for position, result in enumerate(finding_results)
        ]
        dataset.status = DatasetStatus.COMPLETED
        dataset.completed_at = datetime.now(timezone.utc)
        session.commit()
        return _load_dataset(session, dataset.id)
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
def list_datasets(session: Session = Depends(get_session)) -> list[Dataset]:
    return list(session.scalars(select(Dataset).order_by(Dataset.created_at.desc())))


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(dataset_id: uuid.UUID, session: Session = Depends(get_session)) -> Dataset:
    return _load_dataset(session, dataset_id)
