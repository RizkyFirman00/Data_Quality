import uuid
from datetime import datetime

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
    failure_message: str | None
    created_at: datetime
    completed_at: datetime | None


class DatasetDetailResponse(DatasetSummaryResponse):
    preview: list[dict[str, object]]
    column_profiles: list[ColumnProfileResponse]
