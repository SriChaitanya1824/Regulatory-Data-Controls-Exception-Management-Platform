# Exception workflow

Server-side transitions form a finite state machine. Open cases need an owner before assignment. Assigned cases need a plan before remediation. Pending Review requires evidence and a completed/submitted plan. Closure is a separate guarded operation restricted to Reviewer, Compliance Officer, or Admin and additionally requires accepted evidence, a reviewer, and closure rationale. Every transition appends status history and an audit event. Rejected work returns to remediation; deferred work can be reassigned; a closed case may be explicitly reopened with history.
