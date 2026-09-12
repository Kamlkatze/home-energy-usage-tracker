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
    def _find_chain_start_reading(
        cls, db: Session, chain: list[Meter], year: int
    ) -> Reading | None:
        """Find start reading across the meter chain for a given year.

        Tries each meter in the chain (oldest first) looking for:
        1. An exact reading on year-1-12-31
        2. The first reading in the year
        Returns the earliest valid start found across the whole chain.
        """
        year_start = date(year, 1, 1)
        prev_year_end = date(year - 1, 12, 31)

        for meter in chain:
            # Check for exact previous year-end reading
            prev_reading = (
                db.query(Reading)
                .filter(
                    Reading.meter_id == meter.id,
                    Reading.reading_date == prev_year_end,
                )
                .first()
            )
            if prev_reading:
                return prev_reading

        # No exact prev-year-end reading found; return first reading in year
        # across the whole chain (oldest meter first).
        for meter in chain:
            first_in_year = (
                db.query(Reading)
                .filter(
                    Reading.meter_id == meter.id,
                    Reading.reading_date >= year_start,
                    Reading.reading_date <= date(year, 12, 31),
                )
                .order_by(Reading.reading_date.asc())
                .first()
            )
            if first_in_year:
                return first_in_year

        return None

    @classmethod
    def _find_chain_end_reading(
        cls, db: Session, chain: list[Meter], year: int, as_of_date: date
    ) -> Reading | None:
        """Find end reading across the meter chain for a given year.

        Searches the chain from newest to oldest, returning the latest
        reading within the valid range.
        """
        if year < as_of_date.year:
            year_end = date(year, 12, 31)
            for meter in reversed(chain):
                end = (
                    db.query(Reading)
                    .filter(
                        Reading.meter_id == meter.id,
                        Reading.reading_date <= year_end,
                    )
                    .order_by(Reading.reading_date.desc())
                    .first()
                )
                if end:
                    return end
        else:
            year_start = date(year, 1, 1)
            for meter in reversed(chain):
                end = (
                    db.query(Reading)
                    .filter(
                        Reading.meter_id == meter.id,
                        Reading.reading_date <= as_of_date,
                        Reading.reading_date >= year_start,
                    )
                    .order_by(Reading.reading_date.desc())
                    .first()
                )
                if end:
                    return end
        return None

    @classmethod
    def _compute_chain_consumption(
        cls, db: Session, chain: list[Meter], start_reading: Reading, end_reading: Reading
    ) -> Decimal:
        """Compute total consumption across a meter chain between two boundary readings.

        When start and end are on the same meter, this is a simple subtraction.
        When they span meters in the chain, we sum each meter's contribution:
          - For each meter, find its last reading up to the transition point and
            its first reading from the transition point, then sum the segments.
        """
        if start_reading.meter_id == end_reading.meter_id:
            return end_reading.value - start_reading.value

        # Multi-meter: accumulate consumption segment by segment.
        # Find the transition dates by looking at the first reading of each
        # successor meter (same logic as _get_chain_consumption in costs.py).
        from datetime import timedelta

        total = Decimal(0)
        # Build list of (meter, first_reading_date) for transition detection
        transition_dates: list[date] = []
        for i in range(1, len(chain)):
            first = (
                db.query(Reading)
                .filter(Reading.meter_id == chain[i].id)
                .order_by(Reading.reading_date.asc())
                .first()
            )
            transition_dates.append(first.reading_date if first else date.max)

        for idx, meter in enumerate(chain):
            seg_from_date = start_reading.reading_date if idx == 0 else transition_dates[idx - 1]
            if idx < len(transition_dates):
                seg_to_date = transition_dates[idx] - timedelta(days=1)
            else:
                seg_to_date = end_reading.reading_date

            if seg_from_date > seg_to_date:
                continue

            # start of this segment
            if meter.id == start_reading.meter_id:
                seg_start = start_reading
            else:
                seg_start = (
                    db.query(Reading)
                    .filter(
                        Reading.meter_id == meter.id,
                        Reading.reading_date >= seg_from_date,
                        Reading.reading_date <= seg_to_date,
                    )
                    .order_by(Reading.reading_date.asc())
                    .first()
                )

            # end of this segment
            if meter.id == end_reading.meter_id:
                seg_end = end_reading
            else:
                seg_end = (
                    db.query(Reading)
                    .filter(
                        Reading.meter_id == meter.id,
                        Reading.reading_date <= seg_to_date,
                    )
                    .order_by(Reading.reading_date.desc())
                    .first()
                )

            if seg_start is None or seg_end is None:
                continue
            if seg_end.reading_date <= seg_start.reading_date:
                continue

            total += seg_end.value - seg_start.value

        return total

    @classmethod
    def calculate_projection(
        cls,
        db: Session,
        meter_id: int,
        year: int,
        as_of_date: date | None = None,
        chain: list[Meter] | None = None,
    ) -> dict:
        """Calculate annual consumption projection for a meter.

        When `chain` is provided (list of Meter objects, oldest first,
        ending with the meter identified by meter_id), the projection
        follows the replacement chain so that a meter swap within the
        year does not break the calculation.
        """
        if as_of_date is None:
            as_of_date = datetime.now(UTC).date()

        cls.validate_year(year)

        # Check if meter exists and get unit
        unit = cls.get_meter_unit(db, meter_id)

        # Determine if year is completed
        year_completed = year < as_of_date.year

        # Find start and end readings — chain-aware if chain provided
        if chain and len(chain) > 1:
            start_reading = cls._find_chain_start_reading(db, chain, year)
            end_reading = cls._find_chain_end_reading(db, chain, year, as_of_date)
        else:
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

        # Calculate actual consumption (chain-aware)
        if chain and len(chain) > 1:
            actual_consumption = cls._compute_chain_consumption(
                db, chain, start_reading, end_reading
            )
        else:
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
