import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from .models import DatasetStatus


class ColumnProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_name: str
    display_name: str
    position: int
    inferred_type: str
    candidate_role: str
    null_count: int
    empty_count: int
    unique_count: int
    sample_values: list[object]
    distribution: list[dict[str, object]] | None


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row: int
    column: str | None
    issue_type: str
    severity: str
    original_value: Any
    expected_value: Any | None
    evidence: str
    recommendation: str
    confidence: float
    detector: str


class FindingSummaryResponse(BaseModel):
    by_issue_type: dict[str, int]
    by_severity: dict[str, int]


class DatasetSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    source_type: str
    file_type: str
    worksheet_name: str | None
    status: DatasetStatus
    row_count: int
    column_count: int
    duplicate_row_count: int
    finding_count: int
    failure_message: str | None
    assessment_status: str | None
    parent_dataset_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None


class DatasetDetailResponse(DatasetSummaryResponse):
    preview: list[dict[str, object]]
    source_metadata: dict[str, object]
    column_profiles: list[ColumnProfileResponse]
    finding_summary: FindingSummaryResponse
    findings: list[FindingResponse]


class DatasetPreviewResponse(BaseModel):
    filename: str
    worksheet_name: str | None
    row_count: int
    column_count: int
    duplicate_row_count: int
    rows: list[dict[str, object]]
    columns: list[ColumnProfileResponse]
    checks: list[str]


class FindingRowGroupResponse(BaseModel):
    row: int
    source_record: dict[str, Any] | None = None
    findings: list[FindingResponse]
    action_summary: str
    action_summary_source: str
    action_summary_confidence: float | None


class FindingPageResponse(BaseModel):
    items: list[FindingResponse]
    total: int
    total_rows: int
    page: int
    page_size: int
    by_issue_type: dict[str, int]
    row_groups: list[FindingRowGroupResponse]


class GlobalFindingResponse(FindingResponse):
    dataset_id: uuid.UUID
    dataset_name: str
    dataset_completed_at: datetime | None


class GlobalFindingPageResponse(BaseModel):
    items: list[GlobalFindingResponse]
    total: int
    page: int
    page_size: int


class LatestAssessmentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    source_type: str
    completed_at: datetime
    finding_count: int
    issue_counts: dict[str, int]


class DashboardResponse(BaseModel):
    total_assessments: int
    passed_assessments: int
    needs_correction_assessments: int
    latest_findings: int
    latest_assessment: LatestAssessmentResponse | None
