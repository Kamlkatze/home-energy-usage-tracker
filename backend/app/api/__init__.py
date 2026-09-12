from fastapi import APIRouter

from .advance_payments import router as advance_payments_router
from .costs import router as costs_router
from .electricity import router as electricity_router
from .meters import router as meters_router
from .projections import router as projections_router
from .readings import router as readings_router
from .tariff_periods import router as tariff_periods_router

api_router = APIRouter()

api_router.include_router(advance_payments_router, prefix="/advance-payments", tags=["advance-payments"])
api_router.include_router(costs_router, prefix="/costs", tags=["costs"])
api_router.include_router(electricity_router, prefix="/electricity", tags=["electricity"])
api_router.include_router(meters_router, prefix="/meters", tags=["meters"])
api_router.include_router(readings_router, prefix="/readings", tags=["readings"])
api_router.include_router(tariff_periods_router, prefix="/tariffs", tags=["tariffs"])
api_router.include_router(projections_router, tags=["projections"])