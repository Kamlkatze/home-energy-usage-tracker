import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .api import api_router
from .config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger = logging.getLogger(__name__)
    logger.exception("Database integrity error")
    
    # Try to extract constraint name from psycopg2 error details
    constraint_name = None
    if hasattr(exc, 'orig') and exc.orig:
        # PostgreSQL psycopg2 errors have diag attribute
        if hasattr(exc.orig, 'diag') and exc.orig.diag:
            if hasattr(exc.orig.diag, 'constraint_name'):
                constraint_name = exc.orig.diag.constraint_name
        # Fallback: try to parse from error message
        elif hasattr(exc.orig, 'pgerror') and exc.orig.pgerror:
            import re
            match = re.search(r'constraint "([^"]+)"', exc.orig.pgerror)
            if match:
                constraint_name = match.group(1)
    
    # Map constraint names to German messages
    if constraint_name == "uq_meter_reading_date":
        message = "Für diesen Zähler existiert bereits ein Zählerstand an diesem Datum."
    elif constraint_name == "uq_meter_valid_from":
        message = "Für diesen Zähler existiert bereits ein Tarifzeitraum mit diesem Startdatum."
    else:
        message = "Der Vorgang verletzt eine Datenbank-Beschränkung."
    
    # SQLAlchemy automatically marks session as invalid after IntegrityError
    # and will roll back on next access, so we don't need to manually roll back
    
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": message}
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)