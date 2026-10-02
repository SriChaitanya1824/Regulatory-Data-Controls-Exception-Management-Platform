from sqlalchemy import select

from app.database import SessionLocal
from app.models import DataAsset, GovernanceControl, GovernanceException


def test_authentication_and_authorization(client,auth):
    assert client.post("/api/auth/login",json={"username":"bad","password":"bad"}).status_code==401
    auditor=auth("auditor@example.com")
    assert client.post("/api/controls/run",json={},headers=auditor).status_code==403

def test_dashboard_and_seed(client,auth):
    data=client.get("/api/dashboard",headers=auth()).json()
    assert data["metrics"]["open_exceptions"]>=18
    assert any(x["name"]=="Critical" for x in data["by_severity"])

def test_lineage_control_creates_one_exception_only(client,auth):
    headers=auth()
    with SessionLocal() as db:
        asset=db.scalar(select(DataAsset).where(DataAsset.name=="Customer Risk Dataset"))
        control=db.scalar(select(GovernanceControl).where(GovernanceControl.control_code=="DG-LIN-001"))
        payload={"asset_id":asset.id,"control_id":control.id}
    one=client.post("/api/controls/run",json=payload,headers=headers)
    two=client.post("/api/controls/run",json=payload,headers=headers)
    assert one.status_code==200 and one.json()["failed"]==1 and two.status_code==200
    with SessionLocal() as db:
        count=len(db.scalars(select(GovernanceException).join(GovernanceException.execution).where(
            GovernanceException.data_asset_id==asset.id,
            GovernanceException.status.notin_(["Closed", "Rejected"]),
        )).all())
        assert count==1

def test_closure_validation(client,auth):
    headers=auth("reviewer@example.com")
    r=client.post("/api/exceptions/2/close",json={"closure_rationale":"Reviewer confirmed sustained remediation."},headers=headers)
    assert r.status_code==422
    assert "requirements" in r.json()["detail"]

def test_ai_fallback_is_labelled_and_audited(client,auth):
    r=client.post("/api/ai/summarize-finding",json={"input_reference":"FND-TEST","text":"Regulatory dataset has incomplete lineage across source systems."},headers=auth())
    assert r.status_code==200
    assert "Requires human review" in r.json()["label"]
    assert "demo" in r.json()["mode"]

def test_exception_filter_and_report(client,auth):
    h=auth(); assert client.get("/api/exceptions?overdue=true",headers=h).status_code==200
    report=client.get("/api/reports/monthly.csv",headers=h)
    assert report.status_code==200 and "Exception,Title,Division" in report.text
