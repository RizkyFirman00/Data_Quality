import json
import uuid
from decimal import Decimal, InvalidOperation
from typing import Literal
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .backoffice import fetch_backoffice_dataset
from .config import Settings, get_settings
from .database import get_session
from .datasets import _load_dataset
from .models import ColumnProfile, Dataset, DatasetStatus, Finding
from .normalization import write_snapshot, read_snapshot
from .profiling import profile_dataset
from .quality import check_execution_metadata, ordered_findings, quality_findings
from .reports import csv_bytes, pdf_bytes, xlsx_bytes
from .reference import load_administrative_reference
from .schemas import (
    DashboardResponse,
    DatasetDetailResponse,
    FindingPageResponse,
    GlobalFindingPageResponse,
)
from .semantic import (
    action_summary_key,
    apply_action_summaries,
    apply_semantic_roles,
    fallback_action_summary,
    semantic_analysis,
    summarize_finding_actions,
)

router = APIRouter(prefix="/api", tags=["workflow"])


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
                    "expected_value", "evidence", "recommendation", "confidence", "detector",
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
        "latest_findings": latest.finding_count if latest else 0,
        "latest_assessment": latest_assessment,
    }


@router.get("/datasets/{dataset_id}/findings", response_model=FindingPageResponse)
def list_findings(
    dataset_id: uuid.UUID,
    severity: str | None = None,
    issue_type: str | None = None,
    column: str | None = None,
    search: str | None = None,
    group_by_row: bool = False,
    assessment_kind: str | None = Query(None, pattern="^(required|review)$"),
    sort_by: str | None = None,
    sort_direction: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, object]:
    dataset = _load_dataset(session, dataset_id)
    records = []
    if group_by_row and dataset.snapshot_key:
        records, _ = read_snapshot(config.storage_root, dataset.snapshot_key, 1, max(dataset.row_count, 1))
    matching_rows = None
    if group_by_row and search:
        needle = search.strip().lower()
        matching_rows = {record["_source_row"] for record in records if needle in " ".join(str(item) for item in record.values()).lower()}
    findings = _filtered_findings(
        list(session.scalars(select(Finding).where(Finding.dataset_id == dataset_id))),
        severity,
        issue_type,
        column,
        None if matching_rows is not None else search,
    )
    review_types = {"STATISTICAL_ANOMALY", "POTENTIAL_TYPO", "SEMANTIC_MISMATCH"}
    if assessment_kind:
        findings = [finding for finding in findings if (finding.issue_type in review_types) == (assessment_kind == "review")]
    if matching_rows is not None:
        needle = search.strip().lower()
        findings = [finding for finding in findings if finding.row in matching_rows or needle in " ".join(str(item) for item in (finding.row, finding.column, finding.original_value, finding.issue_type, finding.evidence)).lower()]
    total = len(findings)
    findings_by_row: dict[int, list[Finding]] = {}
    for finding in findings:
        findings_by_row.setdefault(finding.row, []).append(finding)
    total_rows = len(findings_by_row)
    start = (page - 1) * page_size
    if group_by_row:
        groups = sorted(findings_by_row.items())
        if sort_by:
            profile = next((item for item in dataset.column_profiles if item.display_name == sort_by), None)
            if sort_by != "_source_row" and profile is None:
                raise HTTPException(status_code=422, detail={"message": "Kolom pengurutan tidak ditemukan."})
            if sort_by == "_source_row":
                groups.sort(key=lambda item: item[0], reverse=sort_direction == "desc")
            else:
                source_by_row = {record["_source_row"]: record for record in records}
                numeric = profile.inferred_type in {"integer", "decimal", "numeric", "percentage"} or profile.candidate_role in {"numeric", "percentage"}
                def raw_value(item):
                    row, group = item
                    record = source_by_row.get(row, {})
                    if sort_by in record:
                        return record[sort_by]
                    return next((finding.original_value for finding in group if finding.column == sort_by), None)
                def sort_value(item):
                    raw = raw_value(item)
                    if numeric:
                        try:
                            number = Decimal(str(raw).strip().replace(",", "."))
                            if number.is_finite():
                                return (0, number)
                        except InvalidOperation:
                            pass
                    return (1, str(raw).casefold())
                present = [item for item in groups if raw_value(item) is not None and str(raw_value(item)).strip()]
                missing = [item for item in groups if raw_value(item) is None or not str(raw_value(item)).strip()]
                groups = sorted(present, key=sort_value, reverse=sort_direction == "desc") + missing
        selected_groups = groups[start : start + page_size]
        source_records = {}
        if records and selected_groups:
            selected_rows = {row for row, _ in selected_groups}
            source_records = {record["_source_row"]: record for record in records if record["_source_row"] in selected_rows}
        selected_findings = [finding for _, group in selected_groups for finding in group]
        row_groups = []
        for row, group in selected_groups:
            keys = {
                action_summary_key(row, finding.severity, finding.issue_type)
                for finding in group
            }
            first = group[0]
            stored = (
                {
                    "text": first.action_summary,
                    "source": first.action_summary_source,
                    "confidence": first.action_summary_confidence,
                }
                if len(keys) == 1 and first.action_summary
                else None
            )
            if not isinstance(stored, dict) or not isinstance(stored.get("text"), str):
                stored = {
                    "text": fallback_action_summary(group),
                    "source": "fallback",
                    "confidence": None,
                }
            row_groups.append({
                "row": row,
                "source_record": source_records.get(row),
                "findings": group,
                "action_summary": stored["text"],
                "action_summary_source": stored.get("source", "fallback"),
                "action_summary_confidence": stored.get("confidence"),
            })
    else:
        selected_findings = findings[start : start + page_size]
        row_groups = []
    return {
        "items": selected_findings,
        "total": total,
        "total_rows": total_rows,
        "page": page,
        "page_size": page_size,
        "by_issue_type": dict(Counter(item.issue_type for item in findings)),
        "row_groups": row_groups,
    }


def _filtered_findings(
    findings: list[Finding],
    severity: str | None = None,
    issue_type: str | None = None,
    column: str | None = None,
    search: str | None = None,
) -> list[Finding]:
    if severity:
        findings = [item for item in findings if item.severity == severity]
    if issue_type:
        findings = [item for item in findings if item.issue_type == issue_type]
    if column:
        findings = [item for item in findings if item.column == column]
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
    search: str | None = None,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    dataset = _load_dataset(session, dataset_id)
    findings = _filtered_findings(dataset.findings, severity, issue_type, column, search)
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
    source_row: int | None = Query(None, ge=1),
    session: Session = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, object]:
    dataset = _load_dataset(session, dataset_id)
    if not dataset.snapshot_key:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    if source_row is not None:
        records, total = read_snapshot(config.storage_root, dataset.snapshot_key, 1, max(dataset.row_count, 1))
        position = next((index for index, record in enumerate(records) if record["_source_row"] == source_row), None)
        if position is None:
            raise HTTPException(status_code=404, detail={"message": "Baris sumber tidak ditemukan pada snapshot dataset."})
        page = position // page_size + 1
        items = records[(page - 1) * page_size : page * page_size]
    else:
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
        executed_checks: list[str] = []
        deterministic = quality_findings(parsed, profile, reference, config.max_findings, executed_checks=executed_checks)
        results = ordered_findings(parsed, deterministic + semantic.findings)
        if len(results) > config.max_findings:
            raise ValueError("Dataset menghasilkan terlalu banyak temuan kualitas.")
        action_summaries = summarize_finding_actions(results, config)
        results = apply_action_summaries(results, action_summaries)
        dataset.snapshot_key = write_snapshot(parsed, config.storage_root, dataset.id)
        dataset.row_count, dataset.column_count = profile.row_count, profile.column_count
        dataset.duplicate_row_count, dataset.preview = profile.duplicate_row_count, profile.preview
        dataset.column_profiles = [ColumnProfile(**item.__dict__) for item in profile.columns]
        dataset.findings = [Finding(position=index, **item.__dict__) for index, item in enumerate(results)]
        dataset.finding_count = len(results)
        dataset.source_metadata = {
            "quality_checks": check_execution_metadata(profile, executed_checks),
            "semantic_available": semantic.available,
            "semantic_roles": semantic.roles,
            "action_summary_available": action_summaries.available,
            "action_summary_ai_count": action_summaries.ai_count,
            "action_summary_fallback_count": len(action_summaries.summaries) - action_summaries.ai_count,
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
