import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonType = JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DatasetStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(32), default="file_upload")
    file_type: Mapped[str] = mapped_column(String(8))
    worksheet_name: Mapped[str | None] = mapped_column(String(255))
    original_file_key: Mapped[str | None] = mapped_column(String(500))
    snapshot_key: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[DatasetStatus] = mapped_column(Enum(DatasetStatus))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_row_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    preview: Mapped[list[dict[str, object]]] = mapped_column(JsonType, default=list)
    failure_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    column_profiles: Mapped[list["ColumnProfile"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="ColumnProfile.position",
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by=lambda: Finding.position,
    )

    @property
    def finding_summary(self) -> dict[str, dict[str, int]]:
        by_issue_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for finding in self.findings:
            by_issue_type[finding.issue_type] = by_issue_type.get(finding.issue_type, 0) + 1
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
        return {"by_issue_type": by_issue_type, "by_severity": by_severity}


class ColumnProfile(Base):
    __tablename__ = "column_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    original_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    inferred_type: Mapped[str] = mapped_column(String(32))
    candidate_role: Mapped[str] = mapped_column(String(32))
    null_count: Mapped[int] = mapped_column(Integer)
    empty_count: Mapped[int] = mapped_column(Integer)
    unique_count: Mapped[int] = mapped_column(Integer)
    sample_values: Mapped[list[object]] = mapped_column(JsonType, default=list)
    distribution: Mapped[list[dict[str, object]] | None] = mapped_column(JsonType)
    dataset: Mapped[Dataset] = relationship(back_populates="column_profiles")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    row: Mapped[int] = mapped_column(Integer)
    column: Mapped[str | None] = mapped_column(String(255))
    issue_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    original_value: Mapped[object] = mapped_column(JsonType)
    expected_value: Mapped[object | None] = mapped_column(JsonType)
    evidence: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    detector: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    dataset: Mapped[Dataset] = relationship(back_populates="findings")
