import csv
import io
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import create_token, current_user, require_roles, verify_password
from app.database import get_db
from app.models import (
    AuditLog,
    BusinessDivision,
    ControlExecution,
    DataAsset,
    Evidence,
    ExceptionComment,
    ExceptionStatusHistory,
    GovernanceControl,
    GovernanceException,
    RegulatoryFinding,
    RemediationPlan,
    User,
)
from app.schemas import (
    AIRequest,
    AssignRequest,
    CloseRequest,
    CommentRequest,
    ControlRunRequest,
    EvidenceReviewRequest,
    LoginRequest,
    LoginResponse,
    RemediationRequest,
    StatusRequest,
)
from app.services.ai import generate
from app.services.audit import audit
from app.services.control_engine import run_controls
from app.services.notifications import notifications
from app.services.storage import storage
from app.services.workflow import close_exception, transition

router = APIRouter(prefix="/api")


def exc_dict(x: GovernanceException) -> dict:
    today = date.today()
    return {"id": x.id, "exception_reference": x.exception_reference, "title": x.title,
        "description": x.description, "source_type": x.source_type, "severity": x.severity,
        "status": x.status, "asset": x.asset.name if x.asset else None, "asset_id": x.data_asset_id,
        "division": x.division.name, "business_division_id": x.business_division_id,
        "owner": x.owner.full_name if x.owner else None, "owner_id": x.owner_id,
        "reviewer_id": x.reviewer_id, "target_date": x.target_date, "created_at": x.created_at,
        "closed_at": x.closed_at, "closure_rationale": x.closure_rationale,
        "age_days": (today - x.created_at.date()).days, "overdue": today > x.target_date and x.status != "Closed"}


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(user), "user": user}


@router.get("/auth/me")
def me(user: User = Depends(current_user)): return user


@router.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role} for u in db.scalars(select(User).order_by(User.full_name))]


@router.get("/divisions")
def divisions(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.scalars(select(BusinessDivision).order_by(BusinessDivision.name)).all()


@router.get("/assets")
def assets(q: str | None = None, division_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(DataAsset)
    if q: stmt = stmt.where(DataAsset.name.ilike(f"%{q}%"))
    if division_id: stmt = stmt.where(DataAsset.business_division_id == division_id)
    return db.scalars(stmt.order_by(DataAsset.name)).all()


@router.get("/controls")
def controls(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = []
    for c in db.scalars(select(GovernanceControl).order_by(GovernanceControl.control_code)):
        total = db.scalar(select(func.count()).where(ControlExecution.control_id == c.id)) or 0
        failures = db.scalar(select(func.count()).where(ControlExecution.control_id == c.id, ControlExecution.result == "FAIL")) or 0
        last = db.scalar(select(func.max(ControlExecution.execution_timestamp)).where(ControlExecution.control_id == c.id))
        rows.append({"id": c.id, "control_code": c.control_code, "name": c.name, "description": c.description,
          "category": c.category, "severity": c.severity, "frequency": c.frequency, "active": c.active,
          "last_execution": last, "pass_rate": round((total-failures)*100/total, 1) if total else None, "failure_count": failures})
    return rows


@router.get("/controls/{control_id}")
def control_detail(control_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    control = db.get(GovernanceControl, control_id)
    if not control: raise HTTPException(404, "Control not found")
    executions = db.scalars(select(ControlExecution).where(ControlExecution.control_id == control_id).order_by(ControlExecution.execution_timestamp.desc()).limit(100)).all()
    return {"control": control, "executions": [{"id": e.id, "asset": e.asset.name, "asset_id": e.asset_id,
      "result": e.result, "details": e.details, "measured_value": e.measured_value, "expected_value": e.expected_value,
      "execution_timestamp": e.execution_timestamp} for e in executions]}


@router.post("/controls/run")
def run(body: ControlRunRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "GOVERNANCE_ANALYST"))):
    rows = run_controls(db, user.id, body.control_id, body.asset_id, body.division_id)
    return {"execution_count": len(rows), "passed": sum(x.result == "PASS" for x in rows),
            "failed": sum(x.result == "FAIL" for x in rows), "batch_id": rows[0].execution_id if rows else None}


@router.get("/control-executions")
def executions(result: str | None = None, control_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(ControlExecution)
    if result: stmt = stmt.where(ControlExecution.result == result)
    if control_id: stmt = stmt.where(ControlExecution.control_id == control_id)
    return db.scalars(stmt.order_by(ControlExecution.execution_timestamp.desc()).limit(500)).all()


@router.get("/findings")
def findings(source: str | None = None, severity: str | None = None, status: str | None = None,
             division_id: int | None = None, overdue: bool = False, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(RegulatoryFinding)
    for column, value in [(RegulatoryFinding.source_type, source), (RegulatoryFinding.severity, severity), (RegulatoryFinding.status, status)]:
        if value: stmt = stmt.where(column == value)
    if division_id: stmt = stmt.where(RegulatoryFinding.business_division_id == division_id)
    if overdue: stmt = stmt.where(RegulatoryFinding.due_date < date.today(), RegulatoryFinding.status != "Closed")
    return [{**f.__dict__, "division": f.division.name,
      "linked_exceptions": db.scalar(select(func.count()).where(GovernanceException.regulatory_finding_id == f.id))} for f in db.scalars(stmt.order_by(RegulatoryFinding.due_date))]


@router.get("/exceptions")
def exceptions(q: str | None = None, status: str | None = None, severity: str | None = None,
               division_id: int | None = None, overdue: bool = False, page: int = 1, page_size: int = Query(25, le=100),
               db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(GovernanceException)
    if q: stmt = stmt.where(or_(GovernanceException.title.ilike(f"%{q}%"), GovernanceException.exception_reference.ilike(f"%{q}%")))
    if status: stmt = stmt.where(GovernanceException.status == status)
    if severity: stmt = stmt.where(GovernanceException.severity == severity)
    if division_id: stmt = stmt.where(GovernanceException.business_division_id == division_id)
    if overdue: stmt = stmt.where(GovernanceException.target_date < date.today(), GovernanceException.status != "Closed")
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(GovernanceException.target_date).offset((page-1)*page_size).limit(page_size)).all()
    return {"items": [exc_dict(x) for x in items], "total": total, "page": page, "page_size": page_size}


@router.get("/exceptions/{exception_id}")
def exception_detail(exception_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    exc = db.get(GovernanceException, exception_id)
    if not exc: raise HTTPException(404, "Exception not found")
    plans = db.scalars(select(RemediationPlan).where(RemediationPlan.exception_id == exception_id)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.exception_id == exception_id)).all()
    comments = db.scalars(select(ExceptionComment).where(ExceptionComment.exception_id == exception_id).order_by(ExceptionComment.created_at)).all()
    history = db.scalars(select(ExceptionStatusHistory).where(ExceptionStatusHistory.exception_id == exception_id).order_by(ExceptionStatusHistory.changed_at)).all()
    source = None
    if exc.execution: source = {"type": "control", "control_code": exc.execution.control.control_code, "result": exc.execution.result, "details": exc.execution.details}
    elif exc.finding: source = {"type": "finding", "reference": exc.finding.finding_reference, "title": exc.finding.title}
    return {**exc_dict(exc), "source": source, "remediation": plans, "evidence": evidence, "comments": comments, "history": history}


@router.post("/exceptions/{exception_id}/assign")
def assign(exception_id: int, body: AssignRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "GOVERNANCE_ANALYST"))):
    exc = db.get(GovernanceException, exception_id)
    if not exc: raise HTTPException(404, "Exception not found")
    exc.owner_id = body.owner_id
    if body.target_date: exc.target_date = body.target_date
    transition(db, exc, "Assigned", user, body.reason); db.commit()
    notifications.send("exception_assigned", exc.owner.email, {"reference": exc.exception_reference})
    return exc_dict(exc)


@router.post("/exceptions/{exception_id}/remediation")
def remediate(exception_id: int, body: RemediationRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "GOVERNANCE_ANALYST", "DATA_OWNER"))):
    exc = db.get(GovernanceException, exception_id)
    if not exc: raise HTTPException(404, "Exception not found")
    plan = RemediationPlan(exception_id=exception_id, owner_id=exc.owner_id or user.id, **body.model_dump())
    db.add(plan); db.flush(); audit(db, user.id, "Remediation Created", "RemediationPlan", plan.id, after={"status": plan.status})
    if exc.status == "Assigned": transition(db, exc, "Remediation In Progress", user, "Remediation plan established")
    db.commit(); return plan


@router.post("/exceptions/{exception_id}/evidence")
def add_evidence(exception_id: int, evidence_type: str = Form(...), title: str = Form(...), description: str = Form(""),
                 file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "GOVERNANCE_ANALYST", "DATA_OWNER", "DATA_STEWARD"))):
    if not db.get(GovernanceException, exception_id): raise HTTPException(404, "Exception not found")
    try: key, checksum = storage.save(file)
    except ValueError as err: raise HTTPException(422, str(err)) from err
    item = Evidence(exception_id=exception_id, evidence_type=evidence_type, title=title, description=description,
                    file_name=file.filename or "evidence", file_path=key, checksum=checksum, submitted_by=user.id)
    db.add(item); db.flush(); audit(db, user.id, "Evidence Submitted", "Evidence", item.id, after={"status": item.status}); db.commit()
    notifications.send("evidence_submitted", "reviewers", {"exception_id": exception_id})
    return item


@router.post("/evidence/{evidence_id}/review")
def review_evidence(evidence_id: int, body: EvidenceReviewRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "REVIEWER", "COMPLIANCE_OFFICER"))):
    item = db.get(Evidence, evidence_id)
    if not item: raise HTTPException(404, "Evidence not found")
    if body.action not in {"Accepted", "Rejected", "Request Clarification"}: raise HTTPException(422, "Invalid review action")
    if body.action != "Accepted" and len(body.notes.strip()) < 5: raise HTTPException(422, "Reviewer reason is required")
    old = item.status; item.status = body.action; item.reviewer_id = user.id; item.reviewed_at = datetime.now(timezone.utc); item.review_notes = body.notes
    exc = db.get(GovernanceException, item.exception_id); exc.reviewer_id = user.id
    audit(db, user.id, f"Evidence {body.action}", "Evidence", item.id, before={"status": old}, after={"status": item.status}); db.commit()
    return item


@router.post("/exceptions/{exception_id}/comments")
def comment(exception_id: int, body: CommentRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = ExceptionComment(exception_id=exception_id, author_id=user.id, comment=body.comment)
    db.add(item); db.flush(); audit(db, user.id, "Comment Added", "GovernanceException", exception_id); db.commit(); return item


@router.post("/exceptions/{exception_id}/status")
def status(exception_id: int, body: StatusRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    exc = db.get(GovernanceException, exception_id)
    if not exc: raise HTTPException(404, "Exception not found")
    transition(db, exc, body.status, user, body.reason); db.commit(); return exc_dict(exc)


@router.post("/exceptions/{exception_id}/close")
def close(exception_id: int, body: CloseRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    exc = db.get(GovernanceException, exception_id)
    if not exc: raise HTTPException(404, "Exception not found")
    close_exception(db, exc, user, body.closure_rationale); db.commit(); return exc_dict(exc)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(current_user)):
    today, month = date.today(), date.today().replace(day=1)
    open_filter = GovernanceException.status != "Closed"
    def metric(*filters):
        return db.scalar(select(func.count()).where(*filters)) or 0
    metrics = {"open_exceptions": metric(open_filter), "critical_exceptions": metric(open_filter, GovernanceException.severity == "Critical"),
      "high_severity_exceptions": metric(open_filter, GovernanceException.severity == "High"), "overdue_exceptions": metric(open_filter, GovernanceException.target_date < today),
      "new_this_month": metric(GovernanceException.created_at >= month), "closed_this_month": metric(GovernanceException.closed_at >= month),
      "pending_review": metric(GovernanceException.status == "Pending Review"),
      "open_regulatory_findings": metric(RegulatoryFinding.status != "Closed", RegulatoryFinding.source_type == "Regulatory Review"),
      "open_audit_findings": metric(RegulatoryFinding.status != "Closed", RegulatoryFinding.source_type == "Internal Audit")}
    def grouped(column, *filters):
        return [{"name": str(n), "value": v} for n, v in db.execute(select(column, func.count()).where(*filters).group_by(column)).all()]
    div = [{"name": n, "value": v} for n, v in db.execute(select(BusinessDivision.name, func.count(GovernanceException.id)).join(GovernanceException).where(open_filter).group_by(BusinessDivision.name)).all()]
    overdue_div = [{"name": n, "value": v} for n,v in db.execute(select(BusinessDivision.name, func.count(GovernanceException.id)).join(GovernanceException).where(open_filter, GovernanceException.target_date < today).group_by(BusinessDivision.name)).all()]
    ages = [("0–30", 0), ("31–60", 0), ("61–90", 0), ("91–180", 0), ("180+", 0)]
    for exc in db.scalars(select(GovernanceException).where(open_filter)):
        age=(today-exc.created_at.date()).days; idx=0 if age<=30 else 1 if age<=60 else 2 if age<=90 else 3 if age<=180 else 4
        ages[idx]=(ages[idx][0], ages[idx][1]+1)
    controls = grouped(ControlExecution.result)
    sources = grouped(RegulatoryFinding.source_type, RegulatoryFinding.status != "Closed")
    top = [{"name": c, "value": v} for c,v in db.execute(select(GovernanceControl.control_code, func.count()).join(ControlExecution).where(ControlExecution.result=="FAIL").group_by(GovernanceControl.control_code).order_by(func.count().desc()).limit(5)).all()]
    return {"metrics": metrics, "by_status": grouped(GovernanceException.status), "by_severity": grouped(GovernanceException.severity, open_filter),
      "by_division": div, "overdue_by_division": overdue_div, "control_results": controls, "findings_by_source": sources,
      "aging": [{"name": n,"value":v} for n,v in ages], "monthly_trend": [], "top_failing_controls": top}


@router.get("/audit")
def audit_logs(entity_type: str | None = None, entity_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(AuditLog)
    if entity_type: stmt=stmt.where(AuditLog.entity_type==entity_type)
    if entity_id: stmt=stmt.where(AuditLog.entity_id==entity_id)
    return db.scalars(stmt.order_by(AuditLog.timestamp.desc()).limit(500)).all()


@router.post("/ai/{feature}")
def ai(feature: str, body: AIRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if feature not in {"summarize-finding", "suggest-remediation", "check-duplicate", "generate-evidence-checklist"}: raise HTTPException(404, "AI feature not found")
    return generate(feature, body.text, body.input_reference, user.id, db, body.asset_id, body.control_id)


@router.get("/reports/monthly.csv")
def report_csv(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(GovernanceException).order_by(GovernanceException.exception_reference)).all()
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(["Exception","Title","Division","Severity","Status","Owner","Target Date","Overdue"])
    for x in rows: writer.writerow([x.exception_reference,x.title,x.division.name,x.severity,x.status,x.owner.full_name if x.owner else "",x.target_date,date.today()>x.target_date and x.status!="Closed"])
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=monthly-governance-exceptions.csv"})


@router.get("/search")
def search(q: str = Query(min_length=2), db: Session = Depends(get_db), _: User = Depends(current_user)):
    like=f"%{q}%"
    return {"exceptions":[{"id":x.id,"reference":x.exception_reference,"name":x.title} for x in db.scalars(select(GovernanceException).where(or_(GovernanceException.title.ilike(like),GovernanceException.exception_reference.ilike(like))).limit(10))],
      "findings":[{"id":x.id,"reference":x.finding_reference,"name":x.title} for x in db.scalars(select(RegulatoryFinding).where(or_(RegulatoryFinding.title.ilike(like),RegulatoryFinding.finding_reference.ilike(like))).limit(10))],
      "controls":[{"id":x.id,"reference":x.control_code,"name":x.name} for x in db.scalars(select(GovernanceControl).where(or_(GovernanceControl.name.ilike(like),GovernanceControl.control_code.ilike(like))).limit(10))],
      "assets":[{"id":x.id,"name":x.name} for x in db.scalars(select(DataAsset).where(DataAsset.name.ilike(like)).limit(10))],
      "users":[{"id":x.id,"name":x.full_name} for x in db.scalars(select(User).where(or_(User.full_name.ilike(like),User.email.ilike(like))).limit(10))]}
