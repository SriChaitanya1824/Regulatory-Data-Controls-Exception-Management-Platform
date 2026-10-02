import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.seed import seed

structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
app = FastAPI(title="Regulatory Data Controls & Exception Management Platform", version="1.0.0",
              description="Portfolio implementation using synthetic governance data.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db: seed(db)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    response = await call_next(request)
    structlog.get_logger().info("request", method=request.method, path=request.url.path, status=response.status_code)
    return response


@app.get("/health")
def health(): return {"status": "healthy"}
