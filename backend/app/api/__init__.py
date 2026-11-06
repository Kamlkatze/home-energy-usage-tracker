from fastapi import APIRouter, Depends

from .admin import router as admin_router
from .advance_payments import router as advance_payments_router
from .auth import public_router as auth_public_router
from .auth import router as auth_router
from .backup import router as backup_router
from .costs import router as costs_router
from .deps import get_current_user
from .electricity import router as electricity_router
from .meta import router as meta_router
from .meters import router as meters_router
from .projections import router as projections_router
from .readings import router as readings_router
from .tariff_periods import router as tariff_periods_router

# All business endpoints require an authenticated user. The public auth
# endpoints (login/logout) live in public_router and are included without
# the session guard in main.py.
api_router = APIRouter(dependencies=[Depends(get_current_user)])

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(advance_payments_router, prefix="/advance-payments", tags=["advance-payments"])
api_router.include_router(backup_router, prefix="/backup", tags=["backup"])
api_router.include_router(costs_router, prefix="/costs", tags=["costs"])
api_router.include_router(electricity_router, prefix="/electricity", tags=["electricity"])
api_router.include_router(meters_router, prefix="/meters", tags=["meters"])
api_router.include_router(meta_router, prefix="/meta", tags=["meta"])
api_router.include_router(readings_router, prefix="/readings", tags=["readings"])
api_router.include_router(tariff_periods_router, prefix="/tariffs", tags=["tariffs"])
api_router.include_router(projections_router, tags=["projections"])

public_router = APIRouter()
public_router.include_router(auth_public_router, prefix="/auth", tags=["auth"])