from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.reading import Reading


class ProjectionService:
    """Service for calculating yearly consumption projections."""
    
    MIN_YEAR = 2000
    MAX_YEAR = 2100
    
    @classmethod
    def validate_year(cls, year: int) -> None:
        """Validate year is within reasonable bounds."""
        if year < cls.MIN_YEAR or year > cls.MAX_YEAR:
            raise ValueError(f"Jahr {year} ist außerhalb des gültigen Bereichs ({cls.MIN_YEAR}-{cls.MAX_YEAR}).")
    
    @classmethod
    def get_meter_unit(cls, db: Session, meter_id: int) -> str:
        """Get unit for a meter."""
        meter = db.query(Meter).filter(Meter.id == meter_id).first()
        if not meter:
            raise ValueError(f"Meter mit ID {meter_id} nicht gefunden.")
        return meter.unit
    
    @classmethod
    def find_start_reading(
        cls, db: Session, meter_id: int, year: int
    ) -> Reading | None:
        """Find start reading for projection calculation.
        
        Logic: 
        1. Exact reading from previous year's end (year-1-12-31)
        2. First reading in the target year
        """
        # Try to get reading from previous year's end exactly
        prev_year_end = date(year - 1, 12, 31)
        prev_year_reading = (
            db.query(Reading)
            .filter(
                Reading.meter_id == meter_id,
                Reading.reading_date == prev_year_end
            )
            .first()
        )
        
        if prev_year_reading:
            return prev_year_reading
        
        # Fallback to first reading in the target year
        year_start = date(year, 1, 1)
        first_reading_in_year = (
            db.query(Reading)
            .filter(
                Reading.meter_id == meter_id,
                Reading.reading_date >= year_start,
                Reading.reading_date <= date(year, 12, 31)
            )
            .order_by(Reading.reading_date.asc())
            .first()
        )
        
        return first_reading_in_year
    
    @classmethod
    def find_end_reading(
        cls, 
        db: Session, 
        meter_id: int, 
        year: int, 
        as_of_date: date
    ) -> Reading | None:
        """Find end reading for projection calculation.
        
        For completed years: last reading <= year-12-31
        For ongoing years: last reading <= as_of_date AND reading_date >= year-01-01
        """
        if year < as_of_date.year:
            # Completed year: last reading in the year
            year_end = date(year, 12, 31)
            return (
                db.query(Reading)
                .filter(
                    Reading.meter_id == meter_id,
                    Reading.reading_date <= year_end
                )
                .order_by(Reading.reading_date.desc())
                .first()
            )
        else:
            # Ongoing year: last reading <= as_of_date and within year
            year_start = date(year, 1, 1)
            return (
                db.query(Reading)
                .filter(
                    Reading.meter_id == meter_id,
                    Reading.reading_date <= as_of_date,
                    Reading.reading_date >= year_start
                )
                .order_by(Reading.reading_date.desc())
                .first()
            )
    
    @classmethod
    def calculate_projection(
        cls,
        db: Session,
        meter_id: int,
        year: int,
        as_of_date: date | None = None
    ) -> dict:
        """Calculate annual consumption projection for a meter."""
        if as_of_date is None:
            as_of_date = datetime.now(UTC).date()
        
        cls.validate_year(year)
        
        # Check if meter exists and get unit
        unit = cls.get_meter_unit(db, meter_id)
        
        # Determine if year is completed
        year_completed = year < as_of_date.year
        
        # Find start and end readings
        start_reading = cls.find_start_reading(db, meter_id, year)
        end_reading = cls.find_end_reading(db, meter_id, year, as_of_date)
        
        # Handle insufficient data
        if not start_reading or not end_reading:
            return {
                "meter_id": meter_id,
                "year": year,
                "unit": unit,
                "actual_consumption_to_date": None,
                "days_elapsed": None,
                "projected_annual_consumption": None,
                "basis": "insufficient_data",
                "message": f"Nicht genügend Zählerstände im Jahr {year} vorhanden, um eine Hochrechnung zu erstellen."
            }
        
        # Check if start and end are valid (end > start)
        # SQLAlchemy Date objects are compatible with Python date objects
        if end_reading.reading_date <= start_reading.reading_date:  # type: ignore[operator]
            return {
                "meter_id": meter_id,
                "year": year,
                "unit": unit,
                "actual_consumption_to_date": None,
                "days_elapsed": None,
                "projected_annual_consumption": None,
                "basis": "insufficient_data",
                "message": f"Nicht genügend Zählerstände im Jahr {year} vorhanden, um eine Hochrechnung zu erstellen."
            }
        
        # Calculate actual consumption
        actual_consumption = end_reading.value - start_reading.value
        days_elapsed = (end_reading.reading_date - start_reading.reading_date).days  # type: ignore[operator]
        
        # Determine basis
        if start_reading.reading_date == date(year - 1, 12, 31):  # type: ignore[operator]
            basis = "linear_from_prev_year_end"
        else:
            basis = "linear_from_first_reading_of_year"
        
        # Handle different cases
        if year_completed:
            # Year is completed - actual consumption is final
            projected_annual = actual_consumption
            basis = "actual_full_year"
            message = None
        else:
            # Year is ongoing - project to full year
            if days_elapsed == 0:
                # Should not happen due to validation above, but handle defensively
                return {
                    "meter_id": meter_id,
                    "year": year,
                    "unit": unit,
                    "actual_consumption_to_date": None,
                    "days_elapsed": None,
                    "projected_annual_consumption": None,
                    "basis": "insufficient_data",
                    "message": f"Nicht genügend Zählerstände im Jahr {year} vorhanden, um eine Hochrechnung zu erstellen."
                }
            
            projected_annual = (actual_consumption / Decimal(days_elapsed)) * Decimal(365)
            message = None
        
        return {
            "meter_id": meter_id,
            "year": year,
            "unit": unit,
            "actual_consumption_to_date": actual_consumption,
            "days_elapsed": days_elapsed,
            "projected_annual_consumption": projected_annual,
            "basis": basis,
            "message": message
        }

    @classmethod
    def analyze_year_status(cls, year: int, as_of_date: date) -> str:
        """Analyze if year is completed, ongoing, or future."""
        if year < as_of_date.year:
            return "completed"
        elif year == as_of_date.year:
            return "ongoing"
        else:
            return "future"