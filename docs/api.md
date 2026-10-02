# API

FastAPI exposes OpenAPI at `/docs`. Authentication returns an eight-hour HS256 bearer token. List endpoints accept server-side search and governance filters; exceptions are paginated. Workflow commands are explicit subresources (`assign`, `remediation`, `evidence`, `status`, `close`) rather than unconstrained updates. Validation failures return 422 with unmet prerequisites; authorization failures return 403; missing records return 404; invalid transitions return 409. `/reports/monthly.csv` streams a management extract and `/search` searches references and names across five domains.
