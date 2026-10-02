from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    BusinessDivision,
    ControlExecution,
    DataAsset,
    DataField,
    Evidence,
    ExceptionComment,
    ExceptionStatusHistory,
    GovernanceControl,
    GovernanceException,
    RegulatoryFinding,
    RemediationPlan,
    User,
)


def seed(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)): return
    divisions = [BusinessDivision(name=n, description=f"Governance reporting scope for {n}") for n in
      ["Retail Banking", "Corporate Banking", "Risk Management", "Finance", "Operations", "Technology"]]
    db.add_all(divisions); db.flush()
    people = [("Admin","admin@example.com","ADMIN"),("Governance Analyst","analyst@example.com","GOVERNANCE_ANALYST"),
      ("Risk Data Owner","risk.owner@example.com","DATA_OWNER"),("Finance Data Owner","finance.owner@example.com","DATA_OWNER"),
      ("Data Steward","steward@example.com","DATA_STEWARD"),("Independent Reviewer","reviewer@example.com","REVIEWER"),
      ("Compliance Officer","compliance@example.com","COMPLIANCE_OFFICER"),("Internal Auditor","auditor@example.com","AUDITOR")]
    users=[User(full_name=n,email=e,role=r,password_hash=hash_password("Governance2026!")) for n,e,r in people]
    db.add_all(users); db.flush()
    controls_data = [
      ("DG-OWN-001","Critical assets must have a Data Owner","Ownership","High"),("DG-OWN-002","Critical assets must have a Data Steward","Ownership","High"),
      ("DG-MET-001","Governed assets must contain mandatory metadata","Metadata","Medium"),("DG-CDE-001","CDEs must have an approved business definition","Documentation","High"),
      ("DG-LIN-001","Regulatory datasets must have documented lineage","Lineage","Critical"),("DG-DQ-001","Critical datasets must satisfy data-quality thresholds","Data Quality","High"),
      ("DG-CLS-001","Governed datasets must have approved classification","Classification","High"),("DG-REV-001","Governed assets must have a current governance review","Review / Certification","Medium"),
      ("DG-DOC-001","Required governance documentation must exist","Documentation","Medium"),("DG-REG-001","Regulatory assets must have regulatory mapping","Regulatory Mapping","Critical")]
    controls=[GovernanceControl(control_code=c,name=n,description=f"Automated preventive/detective governance control: {n}.",category=cat,severity=s,frequency="Monthly",active=True,regulatory_relevance=c in {"DG-LIN-001","DG-REG-001"}) for c,n,cat,s in controls_data]
    db.add_all(controls); db.flush()
    asset_names=["Customer Master","Transaction Dataset","Customer Risk Dataset","Credit Risk Dataset","Regulatory Customer Report","Regulatory Transaction Report","Finance Reporting Dataset","Liquidity Risk Mart","Capital Adequacy Dataset","Payments Ledger","Corporate Client Master","Loan Origination Data","Market Risk Positions","Operational Loss Dataset","Sanctions Screening Dataset","KYC Review Dataset","General Ledger","Treasury Positions","Technology Asset Register","Data Quality Results"]
    assets=[]
    for i,n in enumerate(asset_names):
        critical=i%3==0 or "Regulatory" in n or n == "Customer Risk Dataset"
        a=DataAsset(name=n,description=f"Governed enterprise dataset supporting {n.lower()} processes and controls.",asset_type="Report" if "Report" in n else "Dataset",
          business_division_id=divisions[i%6].id,owner_id=users[2+(i%2)].id if i not in {6,12} else None,steward_id=users[4].id if i!=9 else None,
          criticality="Critical" if critical else "High",classification=None if i in {7,14} else ("Restricted" if critical else "Internal"),
          regulatory_relevance=critical,status="Governed",source_system=["MDM","Risk Lake","Finance Warehouse","Operations Hub"][i%4],
          quality_score=88 if i in {2,8,15} else 97,lineage_count=0 if i in {2,4,13} else 2,last_reviewed_at=date.today()-timedelta(days=500 if i in {3,11} else 120))
        assets.append(a)
    db.add_all(assets); db.flush()
    for i,a in enumerate(assets[:12]):
        db.add(DataField(data_asset_id=a.id,name=["customer_id","risk_rating","transaction_id","transaction_amount"][i%4],data_type="string",is_cde=True,classification=a.classification,regulatory_tag="BCBS239",description=None if i in {3,7} else "Approved enterprise business definition"))
    finding_sources=["Internal Audit","Regulatory Review","Compliance Review","Data Risk Assessment","Data Quality Review","Internal Control Testing"]
    findings=[]
    for i in range(12):
        lineage=i==0
        f=RegulatoryFinding(finding_reference=f"FND-2026-{i+1:03d}",source_type="Regulatory Review" if lineage else finding_sources[i%6],
          title="Customer-risk dataset lacks documented lineage" if lineage else f"Governance control gap in {assets[i].name}",
          description="Source-to-report lineage cannot be demonstrated for the regulatory customer-risk dataset." if lineage else f"Review identified incomplete governance evidence for {assets[i].name}.",
          business_division_id=assets[i].business_division_id,severity="Critical" if lineage else ["High","Medium","Low"][i%3],finding_date=date.today()-timedelta(days=20+i*11),
          due_date=date.today()+timedelta(days=90-i*12),status=["Open","Under Assessment","Remediation in Progress","Pending Validation","Closed"][i%5],
          regulatory_reference="BCBS 239" if lineage else "Enterprise Data Policy",root_cause="Source-to-report lineage capture is incomplete" if lineage else "Control ownership and evidence retention are inconsistent",impact="Regulatory reporting lineage cannot be demonstrated" if lineage else "Reduced confidence in control evidence")
        findings.append(f)
    db.add_all(findings); db.flush()
    statuses=["Open","Assigned","Remediation In Progress","Pending Review","Closed","Deferred","Rejected"]
    exceptions=[]
    for i in range(22):
        exc=GovernanceException(exception_reference=f"DG-EXC-2026-{i+1:03d}",source_type="Regulatory Finding" if i==0 else ("Audit Finding" if i%4==0 else "Governance Gap"),
          regulatory_finding_id=findings[i%12].id,
          data_asset_id=assets[2].id if i == 0 else assets[i%20].id,
          business_division_id=assets[2].business_division_id if i == 0 else assets[i%20].business_division_id,
          title="Regulatory customer-risk dataset lacks documented lineage" if i==0 else f"Governance exception for {assets[i%20].name}",
          description="Implement source-to-report lineage capture." if i==0 else "A governance requirement was not fully satisfied and requires evidenced remediation.",
          severity="Critical" if i in {0,7} else ["High","Medium","Low"][i%3],status="Closed" if i==0 else statuses[i%7],owner_id=users[2+(i%2)].id if i%7!=0 else None,
          reviewer_id=users[5].id if i in {0,3,4,10,11,17,18} else None,target_date=date.today()+timedelta(days=(i-8)*10),
          closed_at=datetime.now(timezone.utc)-timedelta(days=2) if i==0 else None,closure_rationale="Independent reviewer confirmed complete lineage and sustainable control operation." if i==0 else None)
        exceptions.append(exc)
    db.add_all(exceptions); db.flush()
    demo=exceptions[0]
    ex=ControlExecution(control_id=controls[4].id,asset_id=assets[2].id,execution_timestamp=datetime.now(timezone.utc)-timedelta(days=20),result="FAIL",severity="Critical",details="Regulatory asset has no documented lineage",measured_value="0",expected_value=">= 1 lineage",execution_id="DEMO-LINEAGE-2026")
    db.add(ex); db.flush(); demo.control_execution_id=ex.id
    plan=RemediationPlan(exception_id=demo.id,owner_id=users[2].id,root_cause="Source-to-report lineage capture was incomplete",corrective_action="Implement source-to-report lineage capture",preventive_action="Add monthly automated lineage completeness validation",milestone="Lineage mapped, validated, and approved",target_date=date.today()-timedelta(days=2),status="Completed")
    db.add(plan); db.flush()
    db.add(Evidence(exception_id=demo.id,evidence_type="Lineage Report",title="Lineage validation report",description="Reviewer-validated source-to-report lineage evidence",file_name="lineage-validation-report.pdf",file_path="synthetic/demo-lineage-report.pdf",checksum="a"*64,submitted_by=users[2].id,status="Accepted",reviewer_id=users[5].id,reviewed_at=datetime.now(timezone.utc)-timedelta(days=3),review_notes="Lineage coverage and ownership validated."))
    for status,days in [("Open",20),("Assigned",18),("Remediation In Progress",14),("Pending Review",5),("Closed",2)]:
        db.add(ExceptionStatusHistory(exception_id=demo.id,previous_status=None if status=="Open" else "Prior status",new_status=status,changed_by=users[1].id if status!="Closed" else users[5].id,reason=f"Demo lifecycle: {status}",changed_at=datetime.now(timezone.utc)-timedelta(days=days)))
    db.add(ExceptionComment(exception_id=demo.id,author_id=users[5].id,comment="Evidence validated against the lineage completeness criteria; closure approved."))
    db.commit()
