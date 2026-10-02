from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Evidence, ExceptionStatusHistory, GovernanceException, RemediationPlan, User
from app.services.audit import audit
from app.services.notifications import notifications

TRANSITIONS = {
    "Open": {"Assigned", "Deferred"}, "Assigned": {"Remediation In Progress", "Deferred"},
    "Remediation In Progress": {"Pending Review", "Deferred"},
    "Pending Review": {"Closed", "Rejected", "Remediation In Progress"},
    "Rejected": {"Remediation In Progress"}, "Deferred": {"Assigned"}, "Closed": {"Open"},
}


def transition(db: Session, exc: GovernanceException, new_status: str, actor: User, reason: str) -> None:
    if new_status not in TRANSITIONS.get(exc.status, set()):
        raise HTTPException(409, f"Transition {exc.status} → {new_status} is not allowed")
    errors = []
    plans = db.scalars(select(RemediationPlan).where(RemediationPlan.exception_id == exc.id)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.exception_id == exc.id)).all()
    if new_status == "Assigned" and not exc.owner_id: errors.append("owner is required")
    if new_status == "Remediation In Progress" and not plans: errors.append("remediation plan is required")
    if new_status == "Pending Review":
        if not any(p.status in ("Completed", "Submitted", "Approved") for p in plans): errors.append("completed remediation is required")
        if not evidence: errors.append("evidence is required")
    if new_status == "Rejected" and len(reason.strip()) < 5: errors.append("reviewer comment is required")
    if errors: raise HTTPException(422, {"message": "Workflow requirements not met", "requirements": errors})
    old = exc.status; exc.status = new_status
    if new_status == "Closed": exc.closed_at = datetime.now(timezone.utc)
    db.add(ExceptionStatusHistory(exception_id=exc.id, previous_status=old, new_status=new_status,
                                  changed_by=actor.id, reason=reason))
    audit(db, actor.id, f"Exception {new_status}", "GovernanceException", exc.id,
          before={"status": old}, after={"status": new_status})


def close_exception(db: Session, exc: GovernanceException, actor: User, rationale: str) -> None:
    if actor.role not in {"REVIEWER", "COMPLIANCE_OFFICER", "ADMIN"}:
        raise HTTPException(403, "Only a reviewer, compliance officer, or admin can close exceptions")
    plans = db.scalars(select(RemediationPlan).where(RemediationPlan.exception_id == exc.id)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.exception_id == exc.id)).all()
    missing = []
    if exc.status != "Pending Review": missing.append("status must be Pending Review")
    if not any(p.status in ("Completed", "Approved") for p in plans): missing.append("remediation must be complete")
    if not evidence: missing.append("evidence must be present")
    if not any(e.status == "Accepted" for e in evidence): missing.append("accepted evidence is required")
    if not exc.reviewer_id: missing.append("reviewer must be assigned")
    if len(rationale.strip()) < 10: missing.append("closure rationale must contain at least 10 characters")
    if missing: raise HTTPException(422, {"message": "Exception is not eligible for closure", "requirements": missing})
    exc.closure_rationale = rationale
    transition(db, exc, "Closed", actor, rationale)
    notifications.send("exception_closed", exc.owner.email if exc.owner else "unassigned", {"reference": exc.exception_reference})

