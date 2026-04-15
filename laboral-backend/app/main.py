"""PGK Laboral Desk v3.0 — FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from app.database import init_db
from app.services.exceptions import (
    ConvenioNotFoundError,
    LaboralBaseError,
)
from app.services.exceptions import (
    ValidationError as LaboralValidationError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Software laboral profesional con inteligencia normativa",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LaboralValidationError)
async def validation_error_handler(request: Request, exc: LaboralValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "code": exc.code, "field": exc.field},
    )


@app.exception_handler(ConvenioNotFoundError)
async def convenio_not_found_handler(request: Request, exc: ConvenioNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "code": exc.code},
    )


@app.exception_handler(LaboralBaseError)
async def laboral_error_handler(request: Request, exc: LaboralBaseError):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "code": exc.code},
    )


from app.routes import (
    alerts,
    auth,
    chat,
    consultations,
    convenios,
    dismissal,
    employee_dismissal,
    employees,
    health,
    payroll,
    reference,
    sepe,
    simulation,
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(payroll.router, prefix="/api")
app.include_router(dismissal.router, prefix="/api")
app.include_router(convenios.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(consultations.router, prefix="/api")
app.include_router(reference.router, prefix="/api")
app.include_router(employee_dismissal.router)
app.include_router(sepe.router, prefix="/api")
