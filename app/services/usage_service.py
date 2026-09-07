from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from sqlmodel import Session, select
from app.config import get_utc_now
from app.models.vehicle import (
    Vehicle,
    OdometerEntry,
    VehicleUsageStats,
    MonthMileagePoint,
)

class UsageService:
    @staticmethod
    def _normalize_dt(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _interpolate_mileage(sorted_entries: List[OdometerEntry], target_dt: datetime) -> float:
        """
        Linearly interpolates mileage at a given target_dt using adjacent sorted OdometerEntry records.
        Clamps to earliest or latest reading if outside the recorded bounds.
        """
        if not sorted_entries:
            return 0.0
        
        target_dt = UsageService._normalize_dt(target_dt)
        first_dt = UsageService._normalize_dt(sorted_entries[0].recorded_at)
        last_dt = UsageService._normalize_dt(sorted_entries[-1].recorded_at)

        if target_dt <= first_dt:
            return float(sorted_entries[0].mileage)
        if target_dt >= last_dt:
            return float(sorted_entries[-1].mileage)

        for i in range(len(sorted_entries) - 1):
            e1 = sorted_entries[i]
            e2 = sorted_entries[i + 1]
            dt1 = UsageService._normalize_dt(e1.recorded_at)
            dt2 = UsageService._normalize_dt(e2.recorded_at)
            if dt1 <= target_dt <= dt2:
                span_sec = (dt2 - dt1).total_seconds()
                if span_sec <= 0:
                    return float(e1.mileage)
                ratio = (target_dt - dt1).total_seconds() / span_sec
                return float(e1.mileage + ratio * (e2.mileage - e1.mileage))

        return float(sorted_entries[-1].mileage)

    @classmethod
    def calculate_usage_stats(
        cls,
        session: Session,
        vehicle_id: int,
        as_of: Optional[datetime] = None,
        min_span_days: float = 14.0
    ) -> VehicleUsageStats:
        """
        Computes observed usage metrics, trailing window deltas, and monthly bucketed series
        from OdometerEntry history. Returns insufficient_data=True if < 2 readings or span < 14 days.
        """
        stmt = (
            select(OdometerEntry)
            .where(OdometerEntry.vehicle_id == vehicle_id)
            .order_by(OdometerEntry.recorded_at.asc(), OdometerEntry.id.asc())
        )
        entries = session.exec(stmt).all()

        if len(entries) < 2:
            return VehicleUsageStats(vehicle_id=vehicle_id, insufficient_data=True)

        ref_dt = cls._normalize_dt(as_of or get_utc_now())
        first_dt = cls._normalize_dt(entries[0].recorded_at)
        last_dt = cls._normalize_dt(entries[-1].recorded_at)

        total_span_sec = (last_dt - first_dt).total_seconds()
        span_days = max(0.0, total_span_sec / 86400.0)

        if span_days < min_span_days:
            return VehicleUsageStats(
                vehicle_id=vehicle_id,
                insufficient_data=True,
                observation_span_days=round(span_days, 1),
                total_miles=max(0, entries[-1].mileage - entries[0].mileage)
            )

        total_miles = max(0, entries[-1].mileage - entries[0].mileage)
        avg_mpd = total_miles / span_days if span_days > 0 else 0.0

        # Trailing window deltas (interpolated at ref_dt - window_days)
        m_now = float(entries[-1].mileage)
        m_30 = cls._interpolate_mileage(entries, ref_dt - timedelta(days=30))
        m_90 = cls._interpolate_mileage(entries, ref_dt - timedelta(days=90))
        m_365 = cls._interpolate_mileage(entries, ref_dt - timedelta(days=365))

        last_30_miles = max(0.0, round(m_now - m_30, 1))
        last_90_miles = max(0.0, round(m_now - m_90, 1))
        last_365_miles = max(0.0, round(m_now - m_365, 1))

        # Monthly calendar series: from first_dt's month to last_dt's month
        monthly_series: List[MonthMileagePoint] = []
        cur_year = first_dt.year
        cur_month = first_dt.month
        end_year = last_dt.year
        end_month = last_dt.month

        while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
            m_start_dt = datetime(cur_year, cur_month, 1, 0, 0, 0, tzinfo=timezone.utc)
            if cur_month == 12:
                m_end_dt = datetime(cur_year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            else:
                m_end_dt = datetime(cur_year, cur_month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

            interp_start = cls._interpolate_mileage(entries, m_start_dt)
            interp_end = cls._interpolate_mileage(entries, m_end_dt)
            month_miles = max(0.0, round(interp_end - interp_start, 1))

            month_label = f"{cur_year:04d}-{cur_month:02d}"
            monthly_series.append(MonthMileagePoint(month=month_label, miles=month_miles))

            if cur_month == 12:
                cur_year += 1
                cur_month = 1
            else:
                cur_month += 1

        return VehicleUsageStats(
            vehicle_id=vehicle_id,
            insufficient_data=False,
            total_miles=total_miles,
            observation_span_days=round(span_days, 1),
            average_miles_per_day=round(avg_mpd, 2),
            miles_per_week=round(avg_mpd * 7.0, 1),
            miles_per_month=round(avg_mpd * 30.4375, 1),
            miles_per_year=round(avg_mpd * 365.25, 1),
            last_30_days_miles=last_30_miles,
            last_90_days_miles=last_90_miles,
            last_365_days_miles=last_365_miles,
            monthly_series=monthly_series,
        )

    @classmethod
    def get_observed_daily_rate(
        cls,
        session: Session,
        vehicle_id: int,
        window_days: int = 90,
        min_span_days: float = 14.0,
        as_of: Optional[datetime] = None
    ) -> Optional[float]:
        """
        Span-delta estimator over the trailing window [ref_dt - window_days, ref_dt].
        Returns observed miles/day if data span >= min_span_days, otherwise None.
        """
        stmt = (
            select(OdometerEntry)
            .where(OdometerEntry.vehicle_id == vehicle_id)
            .order_by(OdometerEntry.recorded_at.asc(), OdometerEntry.id.asc())
        )
        entries = session.exec(stmt).all()

        if len(entries) < 2:
            return None

        ref_dt = cls._normalize_dt(as_of or get_utc_now())
        first_dt = cls._normalize_dt(entries[0].recorded_at)
        last_dt = cls._normalize_dt(entries[-1].recorded_at)

        total_span_sec = (last_dt - first_dt).total_seconds()
        total_span_days = total_span_sec / 86400.0

        if total_span_days < min_span_days:
            return None

        # Trailing window start
        window_start_dt = ref_dt - timedelta(days=window_days)
        actual_start_dt = max(first_dt, window_start_dt)
        actual_span_days = (last_dt - actual_start_dt).total_seconds() / 86400.0

        if actual_span_days < min_span_days:
            return None

        m_start = cls._interpolate_mileage(entries, actual_start_dt)
        m_end = float(entries[-1].mileage)
        delta_miles = m_end - m_start

        if actual_span_days <= 0 or delta_miles < 0:
            return None

        return round(delta_miles / actual_span_days, 3)
