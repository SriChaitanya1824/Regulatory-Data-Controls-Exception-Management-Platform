from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class BusinessDivision(Base, TimestampMixin):
    __tablename__ = "business_divisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DataAsset(Base, TimestampMixin):
    __tablename__ = "data_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    asset_type: Mapped[str] = mapped_column(String(60), default="Dataset")
    business_division_id: Mapped[int] = mapped_column(ForeignKey("business_divisions.id"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    steward_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), default="Medium")
    classification: Mapped[str | None] = mapped_column(String(40), nullable=True)
    regulatory_relevance: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="Governed")
    source_system: Mapped[str] = mapped_column(String(100), default="Enterprise Data Platform")
    quality_score: Mapped[float] = mapped_column(Float, default=100)
    lineage_count: Mapped[int] = mapped_column(Integer, default=1)
    last_reviewed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    division: Mapped[BusinessDivision] = relationship()
    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id])


class DataField(Base):
    __tablename__ = "data_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    data_asset_id: Mapped[int] = mapped_column(ForeignKey("data_assets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    data_type: Mapped[str] = mapped_column(String(50))
    is_cde: Mapped[bool] = mapped_column(Boolean, default=False)
    classification: Mapped[str | None] = mapped_column(String(40))
    regulatory_tag: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)


class GovernanceControl(Base, TimestampMixin):
    __tablename__ = "governance_controls"
    id: Mapped[int] = mapped_column(primary_key=True)
    control_code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    frequency: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    regulatory_relevance: Mapped[bool] = mapped_column(Boolean, default=False)


class ControlExecution(Base):
    __tablename__ = "control_executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("governance_controls.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("data_assets.id"), index=True)
    execution_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    result: Mapped[str] = mapped_column(String(15), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    details: Mapped[str] = mapped_column(Text)
    measured_value: Mapped[str | None] = mapped_column(String(100))
    expected_value: Mapped[str | None] = mapped_column(String(100))
    execution_id: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    control: Mapped[GovernanceControl] = relationship()
    asset: Mapped[DataAsset] = relationship()


class RegulatoryFinding(Base, TimestampMixin):
    __tablename__ = "regulatory_findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    finding_reference: Mapped[str] = mapped_column(String(40), unique=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    business_division_id: Mapped[int] = mapped_column(ForeignKey("business_divisions.id"), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    finding_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    regulatory_reference: Mapped[str | None] = mapped_column(String(120))
    root_cause: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    division: Mapped[BusinessDivision] = relationship()


class GovernanceException(Base, TimestampMixin):
    __tablename__ = "governance_exceptions"
    __table_args__ = (Index("ix_exception_state", "status", "severity", "target_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    exception_reference: Mapped[str] = mapped_column(String(40), unique=True)
    source_type: Mapped[str] = mapped_column(String(40))
    control_execution_id: Mapped[int | None] = mapped_column(ForeignKey("control_executions.id"), nullable=True)
    regulatory_finding_id: Mapped[int | None] = mapped_column(ForeignKey("regulatory_findings.id"), nullable=True)
    data_asset_id: Mapped[int | None] = mapped_column(ForeignKey("data_assets.id"), nullable=True, index=True)
    business_division_id: Mapped[int] = mapped_column(ForeignKey("business_divisions.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(40), default="Open", index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset: Mapped[DataAsset | None] = relationship()
    division: Mapped[BusinessDivision] = relationship()
    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id])
    execution: Mapped[ControlExecution | None] = relationship()
    finding: Mapped[RegulatoryFinding | None] = relationship()


class RemediationPlan(Base, TimestampMixin):
    __tablename__ = "remediation_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("governance_exceptions.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    root_cause: Mapped[str] = mapped_column(Text)
    corrective_action: Mapped[str] = mapped_column(Text)
    preventive_action: Mapped[str] = mapped_column(Text)
    milestone: Mapped[str] = mapped_column(String(200))
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="Draft")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("governance_exceptions.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str] = mapped_column(String(200))
    file_path: Mapped[str] = mapped_column(String(300))
    checksum: Mapped[str] = mapped_column(String(64))
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(30), default="Pending Review")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)


class ExceptionComment(Base):
    __tablename__ = "exception_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("governance_exceptions.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExceptionStatusHistory(Base):
    __tablename__ = "exception_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("governance_exceptions.id"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    request_id: Mapped[str] = mapped_column(String(80), index=True)


class AIAuditRecord(Base):
    __tablename__ = "ai_audit_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    feature: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(80))
    input_reference: Mapped[str] = mapped_column(String(120))
    generated_output: Mapped[dict[str, Any]] = mapped_column(JSON)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    accepted_status: Mapped[str] = mapped_column(String(30), default="Not reviewed")


class ReportingMetric(Base):
    __tablename__ = "reporting_metrics"
    __table_args__ = (UniqueConstraint("metric_date", "metric_name", "dimension", name="uq_metric_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    metric_name: Mapped[str] = mapped_column(String(100))
    dimension: Mapped[str] = mapped_column(String(100), default="all")
    value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

