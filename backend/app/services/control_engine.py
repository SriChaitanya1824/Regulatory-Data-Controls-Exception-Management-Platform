import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ControlExecution,
    DataAsset,
    DataField,
    GovernanceControl,
    GovernanceException,
)
from app.services.audit import audit


def evaluate(control: GovernanceControl, asset: DataAsset, db: Session) -> tuple[str, str, str, str]:
    code = control.control_code
    if code == "DG-OWN-001":
        failed = asset.criticality == "Critical" and asset.owner_id is None
        return result(failed, "Owner missing", "owner assigned", str(asset.owner_id))
    if code == "DG-OWN-002":
        failed = asset.criticality == "Critical" and asset.steward_id is None
        return result(failed, "Steward missing", "steward assigned", str(asset.steward_id))
    if code == "DG-CDE-001":
        fields = db.scalars(select(DataField).where(DataField.data_asset_id == asset.id, DataField.is_cde)).all()
        failed = any(not f.description for f in fields)
        return result(failed, "CDE business definition missing", "all CDEs defined", f"{len(fields)} CDEs")
    if code == "DG-LIN-001":
        failed = asset.regulatory_relevance and asset.lineage_count == 0
        return result(failed, "Regulatory asset has no documented lineage", ">= 1 lineage", str(asset.lineage_count))
    if code == "DG-DQ-001":
        threshold = 95 if asset.criticality == "Critical" else 90
        return result(asset.quality_score < threshold, "Quality score below threshold", f">= {threshold}", str(asset.quality_score))
    if code == "DG-CLS-001":
        return result(asset.status == "Governed" and not asset.classification, "Classification missing", "classification present", str(asset.classification))
    if code == "DG-REV-001":
        cutoff = date.today() - timedelta(days=365)
        return result(not asset.last_reviewed_at or asset.last_reviewed_at < cutoff, "Governance review is stale", f">= {cutoff}", str(asset.last_reviewed_at))
    if code == "DG-MET-001":
        return result(not asset.description or not asset.source_system, "Mandatory metadata incomplete", "description and source", "metadata inspected")
    if code == "DG-REG-001":
        return result(asset.regulatory_relevance and not asset.classification, "Regulatory mapping incomplete", "mapped and classified", str(asset.classification))
    if code == "DG-DOC-001":
        return result(len(asset.description.strip()) < 20, "Documentation insufficient", ">= 20 characters", str(len(asset.description.strip())))
    return "WARNING", "No executable rule is registered", "registered rule", "none"


def result(failed: bool, failure: str, expected: str, measured: str) -> tuple[str, str, str, str]:
    return ("FAIL" if failed else "PASS", failure if failed else "Control satisfied", measured, expected)


def run_controls(db: Session, actor_id: int, control_id: int | None = None,
                 asset_id: int | None = None, division_id: int | None = None) -> list[ControlExecution]:
    cq = select(GovernanceControl).where(GovernanceControl.active)
    aq = select(DataAsset).where(DataAsset.status == "Governed")
    if control_id: cq = cq.where(GovernanceControl.id == control_id)
    if asset_id: aq = aq.where(DataAsset.id == asset_id)
    if division_id: aq = aq.where(DataAsset.business_division_id == division_id)
    controls, assets, batch = db.scalars(cq).all(), db.scalars(aq).all(), str(uuid.uuid4())
    executions = []
    for control in controls:
        for asset in assets:
            outcome, details, measured, expected = evaluate(control, asset, db)
            execution = ControlExecution(control_id=control.id, asset_id=asset.id, result=outcome,
                severity=control.severity, details=details, measured_value=measured,
                expected_value=expected, execution_id=batch)
            db.add(execution); db.flush(); executions.append(execution)
            if outcome == "FAIL":
                existing = db.scalar(select(GovernanceException).join(ControlExecution).where(
                    ControlExecution.control_id == control.id,
                    GovernanceException.data_asset_id == asset.id,
                    GovernanceException.status.notin_(["Closed", "Rejected"])))
                if not existing:
                    count = db.query(GovernanceException).count() + 1
                    exc = GovernanceException(exception_reference=f"DG-EXC-{date.today().year}-{count:03d}",
                        source_type="Control Failure", control_execution_id=execution.id, data_asset_id=asset.id,
                        business_division_id=asset.business_division_id, title=f"{control.control_code}: {control.name}",
                        description=details, severity=control.severity, status="Open",
                        target_date=date.today() + timedelta(days=30 if control.severity == "Critical" else 60))
                    db.add(exc); db.flush(); audit(db, actor_id, "Exception Created", "GovernanceException", exc.id, after={"status": "Open"})
    db.commit()
    return executions

