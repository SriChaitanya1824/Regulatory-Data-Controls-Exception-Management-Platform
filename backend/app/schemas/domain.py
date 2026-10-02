from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ControlRunRequest(BaseModel):
    control_id: int | None = None
    asset_id: int | None = None
    division_id: int | None = None


class AssignRequest(BaseModel):
    owner_id: int
    target_date: date | None = None
    reason: str = "Assigned for remediation"


class RemediationRequest(BaseModel):
    root_cause: str = Field(min_length=5)
    corrective_action: str = Field(min_length=5)
    preventive_action: str = Field(min_length=5)
    milestone: str
    target_date: date
    status: str = "In Progress"


class StatusRequest(BaseModel):
    status: str
    reason: str = Field(min_length=3)


class CloseRequest(BaseModel):
    closure_rationale: str = Field(min_length=10)


class CommentRequest(BaseModel):
    comment: str = Field(min_length=1)


class EvidenceReviewRequest(BaseModel):
    action: str
    notes: str = ""


class AIRequest(BaseModel):
    input_reference: str
    text: str
    asset_id: int | None = None
    control_id: int | None = None


class DashboardOut(BaseModel):
    metrics: dict[str, int]
    by_status: list[dict[str, Any]]
    by_severity: list[dict[str, Any]]
    by_division: list[dict[str, Any]]
    overdue_by_division: list[dict[str, Any]]
    control_results: list[dict[str, Any]]
    findings_by_source: list[dict[str, Any]]
    aging: list[dict[str, Any]]
    monthly_trend: list[dict[str, Any]]
    top_failing_controls: list[dict[str, Any]]

