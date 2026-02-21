"""
FX (Foreign Exchange) Service
Handles currency conversion and rate management
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Tuple
import logging

from app.models.currency import Currency, CurrencyRate, BudgetFXRate

logger = logging.getLogger(__name__)


class FXService:
    """Service for currency conversion and FX rate management"""

    BASE_CURRENCY = "UZS"

    def __init__(self, db: Session):
        self.db = db

    def get_rate(
        self,
        from_currency: str,
        to_currency: str = "UZS",
        rate_date: Optional[date] = None
    ) -> Optional[Decimal]:
        """
        Get exchange rate for a specific date
        Falls back to most recent rate if exact date not found
        """
        if from_currency == to_currency:
            return Decimal("1.0")

        if rate_date is None:
            rate_date = date.today()

        rate = self.db.query(CurrencyRate).filter(
            CurrencyRate.from_currency == from_currency,
            CurrencyRate.to_currency == to_currency,
            CurrencyRate.rate_date == rate_date
        ).first()

        if rate:
            return rate.rate

        rate = self.db.query(CurrencyRate).filter(
            CurrencyRate.from_currency == from_currency,
            CurrencyRate.to_currency == to_currency,
            CurrencyRate.rate_date <= rate_date
        ).order_by(CurrencyRate.rate_date.desc()).first()

        if rate:
            return rate.rate

        if to_currency != self.BASE_CURRENCY:
            from_to_base = self.get_rate(from_currency, self.BASE_CURRENCY, rate_date)
            to_to_base = self.get_rate(to_currency, self.BASE_CURRENCY, rate_date)
            if from_to_base and to_to_base and to_to_base != 0:
                return from_to_base / to_to_base

        return None

    def get_budget_rate(
        self,
        from_currency: str,
        to_currency: str,
        fiscal_year: int,
        month: int
    ) -> Optional[Decimal]:
        """Get planned FX rate for budget calculations"""
        if from_currency == to_currency:
            return Decimal("1.0")

        rate = self.db.query(BudgetFXRate).filter(
            BudgetFXRate.from_currency == from_currency,
            BudgetFXRate.to_currency == to_currency,
            BudgetFXRate.fiscal_year == fiscal_year,
            BudgetFXRate.month == month
        ).first()

        if rate:
            return rate.planned_rate

        return None

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str = "UZS",
        rate_date: Optional[date] = None,
        use_budget_rate: bool = False,
        fiscal_year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Tuple[Decimal, Decimal, str]:
        """
        Convert amount between currencies
        Returns: (converted_amount, rate_used, rate_source)
        """
        if from_currency == to_currency:
            return amount, Decimal("1.0"), "same_currency"

        rate = None
        source = "actual"

        if use_budget_rate and fiscal_year and month:
            rate = self.get_budget_rate(from_currency, to_currency, fiscal_year, month)
            source = "budget_plan"

        if rate is None:
            rate = self.get_rate(from_currency, to_currency, rate_date)
            source = "actual"

        if rate is None:
            raise ValueError(f"No exchange rate found for {from_currency}/{to_currency}")

        converted = amount * rate
        return Decimal(str(round(converted, 2))), rate, source

    def convert_to_uzs(
        self,
        amount: Decimal,
        currency: str,
        rate_date: Optional[date] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Convert any amount to UZS
        Returns: (uzs_amount, rate_used)
        """
        if currency == "UZS":
            return amount, Decimal("1.0")

        converted, rate, _ = self.convert(amount, currency, "UZS", rate_date)
        return converted, rate

    def save_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        rate_date: date,
        rate_source: str = "CBU",
        is_official: bool = True
    ) -> CurrencyRate:
        """Save or update exchange rate"""
        existing = self.db.query(CurrencyRate).filter(
            CurrencyRate.from_currency == from_currency,
            CurrencyRate.to_currency == to_currency,
            CurrencyRate.rate_date == rate_date
        ).first()

        if existing:
            existing.rate = rate
            existing.rate_source = rate_source
            existing.is_official = is_official
            if rate != 0:
                existing.inverse_rate = Decimal("1.0") / rate
        else:
            inverse = Decimal("1.0") / rate if rate != 0 else None
            existing = CurrencyRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                inverse_rate=inverse,
                rate_date=rate_date,
                rate_source=rate_source,
                is_official=is_official
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def save_budget_rate(
        self,
        from_currency: str,
        to_currency: str,
        fiscal_year: int,
        month: int,
        planned_rate: Decimal,
        assumption_type: str = "flat",
        notes: Optional[str] = None
    ) -> BudgetFXRate:
        """Save or update budget FX rate"""
        existing = self.db.query(BudgetFXRate).filter(
            BudgetFXRate.from_currency == from_currency,
            BudgetFXRate.to_currency == to_currency,
            BudgetFXRate.fiscal_year == fiscal_year,
            BudgetFXRate.month == month
        ).first()

        if existing:
            existing.planned_rate = planned_rate
            existing.assumption_type = assumption_type
            existing.notes = notes
        else:
            existing = BudgetFXRate(
                from_currency=from_currency,
                to_currency=to_currency,
                fiscal_year=fiscal_year,
                month=month,
                planned_rate=planned_rate,
                assumption_type=assumption_type,
                notes=notes
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def generate_budget_rates_from_assumption(
        self,
        from_currency: str,
        to_currency: str,
        fiscal_year: int,
        assumption_type: str,
        base_rate: Decimal,
        growth_rate: Optional[Decimal] = None,
        notes: Optional[str] = None
    ) -> List[BudgetFXRate]:
        """
        Generate 12 monthly budget rates based on assumption type
        assumption_type: flat, linear_growth, seasonal
        """
        rates = []

        for month in range(1, 13):
            if assumption_type == "flat":
                rate = base_rate
            elif assumption_type == "linear_growth" and growth_rate:
                rate = base_rate * (1 + growth_rate * (month - 1) / 12)
            elif assumption_type == "seasonal":
                seasonal_factors = [1.0, 1.0, 1.02, 1.02, 1.03, 1.05, 
                                   1.05, 1.03, 1.02, 1.02, 1.01, 1.0]
                rate = base_rate * Decimal(str(seasonal_factors[month - 1]))
            else:
                rate = base_rate

            budget_rate = self.save_budget_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                fiscal_year=fiscal_year,
                month=month,
                planned_rate=Decimal(str(round(rate, 2))),
                assumption_type=assumption_type,
                notes=notes
            )
            rates.append(budget_rate)

        return rates

    def get_rate_history(
        self,
        from_currency: str,
        to_currency: str = "UZS",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[CurrencyRate]:
        """Get historical exchange rates"""
        query = self.db.query(CurrencyRate).filter(
            CurrencyRate.from_currency == from_currency,
            CurrencyRate.to_currency == to_currency
        )

        if start_date:
            query = query.filter(CurrencyRate.rate_date >= start_date)
        if end_date:
            query = query.filter(CurrencyRate.rate_date <= end_date)

        return query.order_by(CurrencyRate.rate_date).all()

    def get_budget_rates_for_year(
        self,
        fiscal_year: int,
        from_currency: Optional[str] = None
    ) -> List[BudgetFXRate]:
        """Get all budget FX rates for a fiscal year"""
        query = self.db.query(BudgetFXRate).filter(
            BudgetFXRate.fiscal_year == fiscal_year
        )

        if from_currency:
            query = query.filter(BudgetFXRate.from_currency == from_currency)

        return query.order_by(BudgetFXRate.from_currency, BudgetFXRate.month).all()

    def approve_budget_rates(
        self,
        fiscal_year: int,
        from_currency: str,
        to_currency: str,
        approved_by_user_id: int
    ) -> int:
        """Approve all budget rates for a currency pair and year"""
        from datetime import datetime
        
        count = self.db.query(BudgetFXRate).filter(
            BudgetFXRate.fiscal_year == fiscal_year,
            BudgetFXRate.from_currency == from_currency,
            BudgetFXRate.to_currency == to_currency,
            BudgetFXRate.is_approved == False
        ).update({
            "is_approved": True,
            "approved_by_user_id": approved_by_user_id,
            "approved_at": datetime.utcnow()
        })

        self.db.commit()
        return count

    def seed_default_currencies(self) -> int:
        """Seed default currencies if not exist"""
        currencies = [
            {"code": "UZS", "name_en": "Uzbek Som", "name_uz": "O'zbek so'mi", "symbol": "so'm", "is_base_currency": True, "display_order": 1},
            {"code": "USD", "name_en": "US Dollar", "name_uz": "AQSH dollari", "symbol": "$", "display_order": 2},
            {"code": "EUR", "name_en": "Euro", "name_uz": "Yevro", "symbol": "€", "display_order": 3},
            {"code": "RUB", "name_en": "Russian Ruble", "name_uz": "Rossiya rubli", "symbol": "₽", "display_order": 4},
            {"code": "GBP", "name_en": "British Pound", "name_uz": "Britaniya funti", "symbol": "£", "display_order": 5},
            {"code": "CNY", "name_en": "Chinese Yuan", "name_uz": "Xitoy yuani", "symbol": "¥", "display_order": 6},
            {"code": "JPY", "name_en": "Japanese Yen", "name_uz": "Yapon iyenasi", "symbol": "¥", "decimal_places": 0, "display_order": 7},
            {"code": "KZT", "name_en": "Kazakh Tenge", "name_uz": "Qozog'iston tengesi", "symbol": "₸", "display_order": 8},
        ]

        created = 0
        for curr_data in currencies:
            existing = self.db.query(Currency).filter(Currency.code == curr_data["code"]).first()
            if not existing:
                self.db.add(Currency(**curr_data))
                created += 1

        self.db.commit()
        return created

    def seed_sample_rates(self) -> int:
        """Seed sample exchange rates for testing"""
        from datetime import timedelta
        
        sample_rates = {
            "USD": Decimal("12750.00"),
            "EUR": Decimal("13850.00"),
            "RUB": Decimal("140.50"),
            "GBP": Decimal("16100.00"),
            "CNY": Decimal("1750.00"),
            "JPY": Decimal("85.00"),
            "KZT": Decimal("27.50"),
        }

        created = 0
        today = date.today()
        
        for days_ago in range(30):
            rate_date = today - timedelta(days=days_ago)
            for currency, base_rate in sample_rates.items():
                variation = Decimal(str(1 + (days_ago % 5 - 2) * 0.001))
                rate = base_rate * variation
                
                existing = self.db.query(CurrencyRate).filter(
                    CurrencyRate.from_currency == currency,
                    CurrencyRate.to_currency == "UZS",
                    CurrencyRate.rate_date == rate_date
                ).first()
                
                if not existing:
                    self.save_rate(currency, "UZS", rate, rate_date)
                    created += 1

        return created
