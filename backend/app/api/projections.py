from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_database_session
from app.schemas.projection import ProjectionResponse
from app.services.projection import ProjectionService

router = APIRouter()


@router.get("/meters/{meter_id}/projection", response_model=ProjectionResponse)
def get_meter_projection(
    meter_id: int,
    year: int = Query(..., description="Jahr für das die Hochrechnung erstellt wird"),
    as_of_date: date | None = Query(
        None, 
        description="Referenzdatum 'heute'. Falls nicht angegeben: Server-Datum (date.today())."
    ),
    db: Session = Depends(get_database_session),
) -> ProjectionResponse:
    """Calculate annual consumption projection for a meter.

    Calculates a linear annual projection based on existing meter readings.

    **Calculation logic:**

    1. **Year closed** (year < as_of_date.year):
       - Actual consumption = End value - Start value (actual annual consumption)
       - Basis: “actual_full_year”

    2. **Year in progress** (year >= as_of_date.year):
       - Linear projection: (current consumption / days elapsed) * 365
       - Basis: “linear_from_prev_year_end” if starting value is from December 31 of the previous year,
         otherwise “linear_from_first_reading_of_year”

    3. **Missing data**:
       - Basis: “insufficient_data”, projection = null
       - HTTP Status: 200 OK (the meter exists; only data is missing)

    **Starting Point Determination:**
    - 1. Preference: Reading exactly on December 31 of the previous year
    - 2. Fallback: First reading in the target year
    """

    try:
        # Call service to calculate projection
        projection_data = ProjectionService.calculate_projection(
            db=db,
            meter_id=meter_id,
            year=year,
            as_of_date=as_of_date
        )
        
        # Convert to Pydantic model
        return ProjectionResponse(**projection_data)
        
    except ValueError as e:
        # Handle validation errors (year out of range, meter not found)
        error_msg = str(e)
        
        if "Meter mit ID" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        elif "Jahr" in error_msg:
            raise HTTPException(status_code=422, detail=error_msg)
        else:
            # Unexpected validation error
            raise HTTPException(status_code=422, detail=error_msg)
            
    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors (database errors, etc.)
        raise HTTPException(
            status_code=500, 
            detail=f"Interner Serverfehler: {e!s}"
        )
