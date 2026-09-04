import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .backoffice import fetch_backoffice_dataset
from .config import Settings, get_settings
from .database import get_session
from .datasets import _load_dataset
from .models import ColumnProfile, Dataset, DatasetStatus, Finding, FindingAudit
from .normalization import write_snapshot, read_snapshot
from .profiling import profile_dataset
from .quality import ordered_findings, quality_findings
from .reports import csv_bytes, pdf_bytes, xlsx_bytes
from .reference import load_administrative_reference
from .schemas import (
    DashboardResponse,
    DatasetDetailResponse,
    FindingPageResponse,
    FindingResponse,
    FindingStatusUpdate,
    GlobalFindingPageResponse,
)
from .semantic import apply_semantic_roles, semantic_analysis

router = APIRouter(prefix="/api", tags=["workflow"])
VALID_STATUSES = {"OPEN", "REVIEWED", "ACCEPTED", "DISMISSED"}


@router.get("/findings", response_model=GlobalFindingPageResponse)
def global_findings(
    dataset_id: uuid.UUID | None = None,
    severity: str | None = None,
    issue_type: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    conditions = []
    if dataset_id:
        conditions.append(Finding.dataset_id == dataset_id)
    if severity:
        conditions.append(Finding.severity == severity)
    if issue_type:
        conditions.append(Finding.issue_type == issue_type)
    if search:
        needle = f"%{search.strip()}%"
        conditions.append(or_(
            Dataset.original_filename.ilike(needle),
            Finding.column.ilike(needle),
            Finding.issue_type.ilike(needle),
            Finding.evidence.ilike(needle),
            cast(Finding.original_value, String).ilike(needle),
        ))
    base = select(Finding, Dataset).join(Dataset, Dataset.id == Finding.dataset_id)
    count_query = select(func.count(Finding.id)).join(Dataset, Dataset.id == Finding.dataset_id)
    if conditions:
        base = base.where(*conditions)
        count_query = count_query.where(*conditions)
    total = session.scalar(count_query) or 0
    rows = session.execute(
        base.order_by(Dataset.completed_at.desc(), Finding.row, Finding.position)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                **{field: getattr(finding, field) for field in (
                    "id", "row", "column", "issue_type", "severity", "original_value",
                    "expected_value", "evidence", "recommendation", "confidence", "detector", "status",
                )},
                "dataset_id": dataset.id,
                "dataset_name": dataset.original_filename,
                "dataset_completed_at": dataset.completed_at,
            }
            for finding, dataset in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(session: Session = Depends(get_session)) -> dict[str, object]:
    datasets = list(session.scalars(select(Dataset)))
    findings = list(session.scalars(select(Finding).where(Finding.status == "OPEN")))
    latest = session.scalar(
        select(Dataset)
        .where(
            Dataset.status == DatasetStatus.COMPLETED,
            Dataset.completed_at.is_not(None),
        )
        .options(selectinload(Dataset.findings))
        .order_by(Dataset.completed_at.desc(), Dataset.created_at.desc())
        .limit(1)
    )
    latest_assessment = None
    if latest:
        issue_counts: dict[str, int] = {}
        for finding in latest.findings:
            issue_counts[finding.issue_type] = issue_counts.get(finding.issue_type, 0) + 1
        latest_assessment = {
            "id": latest.id,
            "original_filename": latest.original_filename,
            "source_type": latest.source_type,
            "completed_at": (
                latest.completed_at.replace(tzinfo=timezone.utc)
                if latest.completed_at and latest.completed_at.tzinfo is None
                else latest.completed_at
            ),
            "finding_count": latest.finding_count,
            "issue_counts": issue_counts,
        }
    return {
        "total_assessments": len(datasets),
        "passed_assessments": sum(item.assessment_status == "PASSED" for item in datasets),
        "needs_correction_assessments": sum(item.assessment_status == "NEEDS_CORRECTION" for item in datasets),
        "open_findings": len(findings),
        "latest_assessment": latest_assessment,
    }


@router.get("/datasets/{dataset_id}/findings", response_model=FindingPageResponse)
def list_findings(
    dataset_id: uuid.UUID,
    severity: str | None = None,
    issue_type: str | None = None,
    column: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _load_dataset(session, dataset_id)
    findings = _filtered_findings(
        list(session.scalars(select(Finding).where(Finding.dataset_id == dataset_id))),
        severity,
        issue_type,
        column,
        status,
        search,
    )
    total = len(findings)
    start = (page - 1) * page_size
    return {
        "items": findings[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: uuid.UUID,
    update: FindingStatusUpdate,
    session: Session = Depends(get_session),
) -> Finding:
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail={"message": "Status temuan tidak valid."})
    finding = session.get(Finding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail={"message": "Temuan tidak ditemukan."})
    if finding.status != update.status:
        session.add(FindingAudit(previous_status=finding.status, status=update.status, reviewer=update.reviewer[:128], finding=finding))
        finding.status = update.status
        dataset = session.get(Dataset, finding.dataset_id)
        if dataset:
            dataset.assessment_status = "NEEDS_CORRECTION" if any(item.severity == "HIGH" and item.status == "OPEN" for item in dataset.findings) else "PASSED"
        session.commit()
        session.refresh(finding)
    return finding


def _filtered_findings(
    findings: list[Finding],
    severity: str | None = None,
    issue_type: str | None = None,
    column: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[Finding]:
    if severity:
        findings = [item for item in findings if item.severity == severity]
    if issue_type:
        findings = [item for item in findings if item.issue_type == issue_type]
    if column:
        findings = [item for item in findings if item.column == column]
    if status:
        findings = [item for item in findings if item.status == status]
    if search:
        needle = search.lower()
        findings = [
            item
            for item in findings
            if needle
            in " ".join(
                (
                    str(item.row),
                    str(item.column),
                    item.issue_type,
                    str(item.original_value),
                    item.evidence,
                )
            ).lower()
        ]
    return sorted(findings, key=lambda item: item.position)


@router.get("/datasets/{dataset_id}/report")
def report(
    dataset_id: uuid.UUID,
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    severity: str | None = None,
    issue_type: str | None = None,
    column: str | None = None,
    status: str | None = None,
    search: str | None = None,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    dataset = _load_dataset(session, dataset_id)
    findings = _filtered_findings(dataset.findings, severity, issue_type, column, status, search)
    filename = f"assessment-{dataset.id}.{format}"
    if format == "csv":
        content, media_type = csv_bytes(dataset, findings), "text/csv"
    elif format == "xlsx":
        content, media_type = xlsx_bytes(dataset, findings), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content, media_type = pdf_bytes(dataset, findings), "application/pdf"
    return StreamingResponse(iter([content]), media_type=media_type, headers={"content-disposition": f'attachment; filename="{filename}"'})


@router.get("/datasets/{dataset_id}/comparison")
def comparison(dataset_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    dataset = _load_dataset(session, dataset_id)
    if not dataset.parent_dataset_id:
        return {"available": False, "resolved": [], "remaining": [], "new": []}
    parent = _load_dataset(session, dataset.parent_dataset_id)
    def fingerprint(item: Finding) -> str:
        return json.dumps([item.row, item.column, item.issue_type, item.original_value], sort_keys=True, default=str)
    parent_by_key = {fingerprint(item): item for item in parent.findings}
    child_by_key = {fingerprint(item): item for item in dataset.findings}
    return {
        "available": True,
        "resolved": [str(item.id) for key, item in parent_by_key.items() if key not in child_by_key],
        "remaining": [str(item.id) for key, item in child_by_key.items() if key in parent_by_key],
        "new": [str(item.id) for key, item in child_by_key.items() if key not in parent_by_key],
    }


@router.get("/datasets/{dataset_id}/preview")
def preview(
    dataset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, object]:
    dataset = _load_dataset(session, dataset_id)
    if not dataset.snapshot_key:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    items, total = read_snapshot(config.storage_root, dataset.snapshot_key, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/backoffice-assessments", response_model=DatasetDetailResponse)
def assess_backoffice(
    parent_dataset_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> Dataset:
    dataset = Dataset(original_filename="BACKOFFICE API", source_type="backoffice_api", file_type="api", status=DatasetStatus.PROCESSING, parent_dataset_id=parent_dataset_id)
    session.add(dataset)
    session.commit()
    try:
        parsed = fetch_backoffice_dataset(config)
        profile = profile_dataset(parsed, config.preview_rows)
        reference = load_administrative_reference(config.master_reference_path)
        semantic = semantic_analysis(parsed, profile, config)
        profile = apply_semantic_roles(profile, semantic.roles)
        deterministic = quality_findings(parsed, profile, reference, config.max_findings)
        results = ordered_findings(parsed, deterministic + semantic.findings)
        dataset.snapshot_key = write_snapshot(parsed, config.storage_root, dataset.id)
        dataset.row_count, dataset.column_count = profile.row_count, profile.column_count
        dataset.duplicate_row_count, dataset.preview = profile.duplicate_row_count, profile.preview
        dataset.column_profiles = [ColumnProfile(**item.__dict__) for item in profile.columns]
        dataset.findings = [Finding(position=index, **item.__dict__) for index, item in enumerate(results)]
        dataset.finding_count = len(results)
        dataset.source_metadata = {
            "semantic_available": semantic.available,
            "semantic_roles": semantic.roles,
        }
        dataset.status, dataset.completed_at = DatasetStatus.COMPLETED, datetime.now(timezone.utc)
        dataset.assessment_status = "NEEDS_CORRECTION" if any(item.severity == "HIGH" for item in results) else "PASSED"
        session.commit()
        return _load_dataset(session, dataset.id)
    except Exception as exc:
        dataset.status = DatasetStatus.FAILED
        dataset.failure_message = "Backoffice assessment gagal."
        session.commit()
        raise HTTPException(status_code=422, detail={"message": "Backoffice assessment gagal.", "dataset_id": str(dataset.id)}) from exc
