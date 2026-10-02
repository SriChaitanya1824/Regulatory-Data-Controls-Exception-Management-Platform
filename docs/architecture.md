# Architecture

The system separates HTTP routes, domain services, SQLAlchemy models, and integration abstractions. Routes validate and authorize input; `control_engine.py` evaluates current database records; `workflow.py` owns lifecycle invariants; `audit.py`, `storage.py`, `notifications.py`, and `ai.py` isolate cross-cutting concerns. PostgreSQL is authoritative in Docker, while SQLite enables a zero-service test path. React fetches only filtered API results through TanStack Query. Airflow calls authenticated APIs so scheduled and interactive execution share the same business rules.

Control runs are immutable batches. A failure lookup uses control plus asset plus non-terminal exception state to prevent duplicate active cases. Workflow writes and audit events share a SQLAlchemy transaction.
