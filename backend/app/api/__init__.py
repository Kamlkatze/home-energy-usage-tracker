from fastapi import APIRouter

from .costs import router as costs_router
from .meters import router as meters_router
from .readings import router as readings_router
from .tariff_periods import router as tariff_periods_router

api_router = APIRouter()

api_router.include_router(costs_router, prefix="/costs", tags=["costs"])
api_router.include_router(meters_router, prefix="/meters", tags=["meters"])
api_router.include_router(readings_router, prefix="/readings", tags=["readings"])
api_router.include_router(tariff_periods_router, prefix="/tariffs", tags=["tariffs"])