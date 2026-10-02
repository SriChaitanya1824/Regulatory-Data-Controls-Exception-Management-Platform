# Testing

Backend tests use an isolated SQLite database and exercise login, negative authorization, seeded dashboard calculations, real lineage failure, duplicate suppression, closure rejection, labeled AI fallback, filtering, and CSV reporting. Ruff checks imports and correctness. The frontend pipeline runs ESLint, Vitest, strict TypeScript, and a production Vite build. CI uses Python 3.12 and Node 22 with locked dependencies. Docker Compose validation additionally covers PostgreSQL connectivity and service health checks.
