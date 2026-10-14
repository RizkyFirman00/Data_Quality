import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Uuid
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
    __table_args__ = (
        CheckConstraint(
            "assessment_status IS NULL OR assessment_status IN ('PASSED', 'NEEDS_CORRECTION')",
            name="ck_datasets_assessment_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("local_users.id", ondelete="SET NULL"), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    owner: Mapped["LocalUser | None"] = relationship(foreign_keys=[owner_id])
    original_filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(32), default="file_upload")
    source_metadata: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
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
    assessment_status: Mapped[str | None] = mapped_column(String(32))
    parent_dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"), index=True
    )
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
    parent_dataset: Mapped["Dataset | None"] = relationship(remote_side="Dataset.id")

    @property
    def pending_column_count(self) -> int | None:
        coverage = (self.source_metadata or {}).get("column_assessment")
        return coverage.get("pending_count") if isinstance(coverage, dict) else None

    @property
    def owner_display_name(self) -> str | None:
        return self.owner.display_name if self.owner else None

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
    action_summary: Mapped[str | None] = mapped_column(Text)
    action_summary_source: Mapped[str | None] = mapped_column(String(16))
    action_summary_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    dataset: Mapped[Dataset] = relationship(back_populates="findings")


class LocalUser(Base):
    __tablename__ = "local_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sessions: Mapped[list["LocalSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class LocalSession(Base):
    __tablename__ = "local_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("local_users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user: Mapped[LocalUser] = relationship(back_populates="sessions")
