import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AIAuditRecord, GovernanceException

LABEL = "AI-generated recommendation — Requires human review"


def generate(feature: str, text: str, reference: str, user_id: int, db: Session,
             asset_id: int | None = None, control_id: int | None = None) -> dict:
    clean = re.sub(r"\s+", " ", text).strip()
    if feature == "summarize-finding":
        output = {"executive_summary": clean[:280], "potential_impact": "May impair demonstrable governance and regulatory reporting confidence.",
                  "likely_root_cause": "Governance ownership, metadata, or process controls may be incomplete.",
                  "remediation_areas": ["Confirm ownership", "Document the control gap", "Validate sustainable correction"],
                  "evidence_needed": ["Approved procedure", "Validation result", "Owner attestation"]}
    elif feature == "suggest-remediation":
        output = {"steps": ["Confirm scope and accountable owner", "Document current and target state", "Implement the corrective control", "Independently validate effectiveness", "Submit dated evidence"]}
    elif feature == "generate-evidence-checklist":
        output = {"checklist": ["Approved remediation plan", "Before/after control result", "Dated validation report", "Owner approval", "Independent reviewer conclusion"]}
    else:
        candidates = db.scalars(select(GovernanceException).where(GovernanceException.status != "Closed")).all()
        scored = []
        words = set(clean.lower().split())
        for exc in candidates:
            score = len(words & set((exc.title + " " + exc.description).lower().split())) / max(1, len(words))
            if asset_id and exc.data_asset_id == asset_id: score += .35
            if control_id and exc.execution and exc.execution.control_id == control_id: score += .35
            if score >= .35: scored.append({"reference": exc.exception_reference, "similarity": min(round(score, 2), .99), "reason": "Related asset, control, or issue language"})
        output = {"potential_duplicates": sorted(scored, key=lambda x: x["similarity"], reverse=True)[:5], "automatic_merge": False}
    response = {"label": LABEL, "mode": "development/demo deterministic fallback", "provider": settings.ai_provider, **output}
    db.add(AIAuditRecord(feature=feature, provider=settings.ai_provider, input_reference=reference,
                         generated_output=response, user_id=user_id)); db.commit()
    return response
