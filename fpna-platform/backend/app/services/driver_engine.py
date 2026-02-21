"""
Driver Engine Service
Implements driver calculations and golden rules for FP&A
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Tuple
import uuid
import logging

from app.models.driver import Driver, DriverValue, DriverCalculationLog, GoldenRule, DriverType
from app.models.snapshot import BaselineBudget
from app.models.coa import Account, AccountClass, AccountMapping

logger = logging.getLogger(__name__)


class DriverEngine:
    """
    Engine for applying drivers and golden rules to budget calculations
    """

    def __init__(self, db: Session):
        self.db = db

    def get_driver_value(
        self,
        driver_code: str,
        fiscal_year: int,
        month: int,
        account_code: Optional[str] = None,
        business_unit_code: Optional[str] = None
    ) -> Optional[Decimal]:
        """Get driver value for specific period and scope"""
        driver = self.db.query(Driver).filter(Driver.code == driver_code).first()
        if not driver:
            return None

        query = self.db.query(DriverValue).filter(
            DriverValue.driver_id == driver.id,
            DriverValue.fiscal_year == fiscal_year,
            DriverValue.month == month
        )

        if account_code:
            query = query.filter(DriverValue.account_code == account_code)
        if business_unit_code:
            query = query.filter(DriverValue.business_unit_code == business_unit_code)

        value = query.first()
        if value:
            return value.value

        global_value = self.db.query(DriverValue).filter(
            DriverValue.driver_id == driver.id,
            DriverValue.fiscal_year == fiscal_year,
            DriverValue.month == month,
            DriverValue.account_code.is_(None),
            DriverValue.business_unit_code.is_(None)
        ).first()

        if global_value:
            return global_value.value

        return driver.default_value

    def apply_yield_driver(
        self,
        balance: Decimal,
        yield_rate: Decimal,
        days_in_month: int = 30
    ) -> Decimal:
        """
        Calculate interest income from asset balance and yield rate
        Formula: Balance * (Yield% / 100) / 12
        """
        if balance == 0 or yield_rate == 0:
            return Decimal("0")
        
        annual_interest = balance * (yield_rate / 100)
        monthly_interest = annual_interest / 12
        return Decimal(str(round(monthly_interest, 2)))

    def apply_cost_driver(
        self,
        balance: Decimal,
        cost_rate: Decimal,
        days_in_month: int = 30
    ) -> Decimal:
        """
        Calculate interest expense from liability balance and cost rate
        Formula: Balance * (Cost% / 100) / 12
        """
        if balance == 0 or cost_rate == 0:
            return Decimal("0")
        
        annual_expense = balance * (cost_rate / 100)
        monthly_expense = annual_expense / 12
        return Decimal(str(round(monthly_expense, 2)))

    def apply_growth_driver(
        self,
        current_balance: Decimal,
        growth_rate: Decimal,
        period_months: int = 1
    ) -> Decimal:
        """
        Calculate new balance after applying growth rate
        Formula: Balance * (1 + Growth% / 100)^(months/12)
        """
        if current_balance == 0:
            return Decimal("0")
        
        monthly_growth = (1 + float(growth_rate) / 100) ** (period_months / 12)
        new_balance = float(current_balance) * monthly_growth
        return Decimal(str(round(new_balance, 2)))

    def apply_provision_driver(
        self,
        loan_balance: Decimal,
        provision_rate: Decimal,
        existing_provision: Decimal = Decimal("0")
    ) -> Decimal:
        """
        Calculate provision expense
        Formula: (Loan Balance * Provision%) - Existing Provision
        """
        if loan_balance == 0:
            return Decimal("0")
        
        required_provision = loan_balance * (provision_rate / 100)
        provision_expense = required_provision - existing_provision
        return Decimal(str(round(max(provision_expense, Decimal("0")), 2)))

    def calculate_spread(
        self,
        yield_rate: Decimal,
        cost_rate: Decimal
    ) -> Decimal:
        """
        Calculate net interest margin (spread)
        Formula: Yield% - Cost%
        """
        return yield_rate - cost_rate

    def validate_balance_equation(
        self,
        fiscal_year: int,
        month: int
    ) -> Tuple[bool, Decimal, str]:
        """
        Validate accounting equation: Assets = Liabilities + Equity
        Returns: (is_valid, difference, message)
        """
        baselines = self.db.query(BaselineBudget).filter(
            BaselineBudget.fiscal_year == fiscal_year,
            BaselineBudget.is_active == True
        ).all()

        month_attr = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                      'jul', 'aug', 'sep', 'oct', 'nov', 'dec'][month - 1]

        assets = Decimal("0")
        liabilities = Decimal("0")
        equity = Decimal("0")

        for baseline in baselines:
            value = getattr(baseline, month_attr) or Decimal("0")
            class_code = baseline.account_code[0]
            
            if class_code == "1":
                assets += value
            elif class_code == "2":
                liabilities += value
            elif class_code == "3":
                equity += value

        difference = assets - (liabilities + equity)
        is_valid = abs(difference) < Decimal("0.01")

        message = f"Assets: {assets:,.2f}, Liabilities: {liabilities:,.2f}, Equity: {equity:,.2f}"
        if not is_valid:
            message += f" - Difference: {difference:,.2f}"

        return is_valid, difference, message

    def apply_golden_rules(
        self,
        fiscal_year: int,
        month: int,
        source_account_code: str,
        adjustment_amount: Decimal
    ) -> List[Dict]:
        """
        Apply golden rules to calculate P&L impact from balance sheet changes
        Returns list of calculated impacts
        """
        results = []
        
        rules = self.db.query(GoldenRule).filter(
            GoldenRule.is_active == True
        ).order_by(GoldenRule.priority).all()

        for rule in rules:
            if not source_account_code.startswith(rule.source_account_pattern):
                continue

            driver_value = None
            if rule.driver_code:
                driver_value = self.get_driver_value(
                    rule.driver_code, fiscal_year, month, source_account_code
                )

            calculated_amount = self._execute_formula(
                rule.calculation_formula,
                adjustment_amount,
                driver_value
            )

            if calculated_amount and calculated_amount != 0:
                results.append({
                    "rule_code": rule.code,
                    "rule_type": rule.rule_type,
                    "source_account": source_account_code,
                    "target_account_pattern": rule.target_account_pattern,
                    "driver_value": driver_value,
                    "calculated_amount": calculated_amount
                })

        return results

    def _execute_formula(
        self,
        formula: str,
        balance: Decimal,
        driver_value: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Execute calculation formula safely"""
        try:
            local_vars = {
                "balance": float(balance),
                "driver": float(driver_value) if driver_value else 0,
                "rate": float(driver_value) if driver_value else 0,
            }
            
            if formula == "balance * rate / 100 / 12":
                result = float(balance) * (float(driver_value or 0) / 100) / 12
            elif formula == "balance * rate / 100":
                result = float(balance) * (float(driver_value or 0) / 100)
            else:
                result = eval(formula, {"__builtins__": {}}, local_vars)
            
            return Decimal(str(round(result, 2)))
        except Exception as e:
            logger.error(f"Formula execution error: {e}")
            return None

    def run_driver_calculations(
        self,
        fiscal_year: int,
        months: Optional[List[int]] = None,
        driver_codes: Optional[List[str]] = None,
        account_codes: Optional[List[str]] = None,
        apply_golden_rules: bool = True
    ) -> Tuple[str, int, int, List[Dict], List[str]]:
        """
        Run driver calculations for specified scope
        Returns: (batch_id, successful, failed, results, errors)
        """
        batch_id = f"CALC-{uuid.uuid4().hex[:8].upper()}"
        
        if months is None:
            months = list(range(1, 13))

        drivers_query = self.db.query(Driver).filter(Driver.is_active == True)
        if driver_codes:
            drivers_query = drivers_query.filter(Driver.code.in_(driver_codes))
        drivers = drivers_query.all()

        baselines_query = self.db.query(BaselineBudget).filter(
            BaselineBudget.fiscal_year == fiscal_year,
            BaselineBudget.is_active == True
        )
        if account_codes:
            baselines_query = baselines_query.filter(
                BaselineBudget.account_code.in_(account_codes)
            )
        baselines = baselines_query.all()

        successful = 0
        failed = 0
        results = []
        errors = []

        month_attrs = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                       'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

        for baseline in baselines:
            for month in months:
                balance = getattr(baseline, month_attrs[month - 1]) or Decimal("0")
                
                for driver in drivers:
                    if not self._driver_applies_to_account(driver, baseline.account_code):
                        continue

                    try:
                        driver_value = self.get_driver_value(
                            driver.code, fiscal_year, month, baseline.account_code
                        )
                        
                        if driver_value is None:
                            continue

                        calculated = self._apply_driver_by_type(
                            driver.driver_type, balance, driver_value
                        )

                        if calculated is not None:
                            target_account = self._get_target_account(
                                driver, baseline.account_code
                            )

                            result = {
                                "source_account_code": baseline.account_code,
                                "target_account_code": target_account,
                                "month": month,
                                "source_balance": balance,
                                "driver_value": driver_value,
                                "calculated_amount": calculated,
                                "driver_code": driver.code
                            }
                            results.append(result)

                            log = DriverCalculationLog(
                                calculation_batch_id=batch_id,
                                driver_id=driver.id,
                                fiscal_year=fiscal_year,
                                month=month,
                                source_account_code=baseline.account_code,
                                target_account_code=target_account,
                                source_balance=balance,
                                driver_value=driver_value,
                                calculated_amount=calculated,
                                status="SUCCESS"
                            )
                            self.db.add(log)
                            successful += 1

                    except Exception as e:
                        failed += 1
                        error_msg = f"Driver {driver.code}, Account {baseline.account_code}, Month {month}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)

        self.db.commit()
        return batch_id, successful, failed, results, errors

    def _driver_applies_to_account(self, driver: Driver, account_code: str) -> bool:
        """Check if driver applies to given account"""
        if driver.source_account_pattern:
            return account_code.startswith(driver.source_account_pattern)
        return True

    def _get_target_account(self, driver: Driver, source_account: str) -> Optional[str]:
        """Get target account for driver calculation"""
        if driver.target_account_pattern:
            return driver.target_account_pattern
        
        mapping = self.db.query(AccountMapping).filter(
            AccountMapping.balance_account_code.startswith(source_account[:3]),
            AccountMapping.is_active == True
        ).first()
        
        if mapping:
            return mapping.pnl_account_code
        
        return None

    def _apply_driver_by_type(
        self,
        driver_type: DriverType,
        balance: Decimal,
        driver_value: Decimal
    ) -> Optional[Decimal]:
        """Apply driver calculation based on type"""
        if driver_type == DriverType.YIELD_RATE:
            return self.apply_yield_driver(balance, driver_value)
        elif driver_type == DriverType.COST_RATE:
            return self.apply_cost_driver(balance, driver_value)
        elif driver_type == DriverType.GROWTH_RATE:
            return self.apply_growth_driver(balance, driver_value)
        elif driver_type == DriverType.PROVISION_RATE:
            return self.apply_provision_driver(balance, driver_value)
        else:
            return None

    def seed_default_drivers(self) -> int:
        """Seed default drivers for banking FP&A"""
        drivers = [
            {
                "code": "YIELD_CORP_LOAN",
                "name_en": "Corporate Loan Yield Rate",
                "name_uz": "Korporativ kredit daromad stavkasi",
                "driver_type": DriverType.YIELD_RATE,
                "source_account_pattern": "121",
                "target_account_pattern": "401",
                "default_value": Decimal("18.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "YIELD_SME_LOAN",
                "name_en": "SME Loan Yield Rate",
                "name_uz": "KOB kredit daromad stavkasi",
                "driver_type": DriverType.YIELD_RATE,
                "source_account_pattern": "122",
                "target_account_pattern": "402",
                "default_value": Decimal("22.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "YIELD_CONSUMER_LOAN",
                "name_en": "Consumer Loan Yield Rate",
                "name_uz": "Iste'mol krediti daromad stavkasi",
                "driver_type": DriverType.YIELD_RATE,
                "source_account_pattern": "14",
                "target_account_pattern": "403",
                "default_value": Decimal("28.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "YIELD_MORTGAGE",
                "name_en": "Mortgage Yield Rate",
                "name_uz": "Ipoteka daromad stavkasi",
                "driver_type": DriverType.YIELD_RATE,
                "source_account_pattern": "15",
                "target_account_pattern": "404",
                "default_value": Decimal("16.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "COST_CURRENT_ACC",
                "name_en": "Current Account Cost Rate",
                "name_uz": "Joriy hisob xarajat stavkasi",
                "driver_type": DriverType.COST_RATE,
                "source_account_pattern": "201",
                "target_account_pattern": "501",
                "default_value": Decimal("2.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "COST_SAVINGS",
                "name_en": "Savings Deposit Cost Rate",
                "name_uz": "Jamg'arma depozit xarajat stavkasi",
                "driver_type": DriverType.COST_RATE,
                "source_account_pattern": "203",
                "target_account_pattern": "502",
                "default_value": Decimal("12.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "COST_TERM_DEPOSIT",
                "name_en": "Term Deposit Cost Rate",
                "name_uz": "Muddatli depozit xarajat stavkasi",
                "driver_type": DriverType.COST_RATE,
                "source_account_pattern": "204",
                "target_account_pattern": "503",
                "default_value": Decimal("18.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "PROV_CORP_LOAN",
                "name_en": "Corporate Loan Provision Rate",
                "name_uz": "Korporativ kredit zaxira stavkasi",
                "driver_type": DriverType.PROVISION_RATE,
                "source_account_pattern": "121",
                "target_account_pattern": "561",
                "default_value": Decimal("2.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "PROV_SME_LOAN",
                "name_en": "SME Loan Provision Rate",
                "name_uz": "KOB kredit zaxira stavkasi",
                "driver_type": DriverType.PROVISION_RATE,
                "source_account_pattern": "122",
                "target_account_pattern": "562",
                "default_value": Decimal("3.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "PROV_CONSUMER_LOAN",
                "name_en": "Consumer Loan Provision Rate",
                "name_uz": "Iste'mol krediti zaxira stavkasi",
                "driver_type": DriverType.PROVISION_RATE,
                "source_account_pattern": "14",
                "target_account_pattern": "563",
                "default_value": Decimal("5.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "GROWTH_LOANS",
                "name_en": "Loan Portfolio Growth Rate",
                "name_uz": "Kredit portfeli o'sish stavkasi",
                "driver_type": DriverType.GROWTH_RATE,
                "source_account_pattern": "1",
                "default_value": Decimal("15.0"),
                "unit": "%",
                "is_system": True
            },
            {
                "code": "GROWTH_DEPOSITS",
                "name_en": "Deposit Growth Rate",
                "name_uz": "Depozit o'sish stavkasi",
                "driver_type": DriverType.GROWTH_RATE,
                "source_account_pattern": "20",
                "default_value": Decimal("12.0"),
                "unit": "%",
                "is_system": True
            },
        ]

        created = 0
        for driver_data in drivers:
            existing = self.db.query(Driver).filter(Driver.code == driver_data["code"]).first()
            if not existing:
                self.db.add(Driver(**driver_data))
                created += 1

        self.db.commit()
        return created

    def seed_golden_rules(self) -> int:
        """Seed default golden rules"""
        rules = [
            {
                "code": "LOAN_INTEREST_INCOME",
                "name_en": "Loan Interest Income Rule",
                "name_uz": "Kredit foiz daromadi qoidasi",
                "rule_type": "interest_income",
                "source_account_pattern": "12",
                "target_account_pattern": "40",
                "calculation_formula": "balance * rate / 100 / 12",
                "priority": 10
            },
            {
                "code": "DEPOSIT_INTEREST_EXPENSE",
                "name_en": "Deposit Interest Expense Rule",
                "name_uz": "Depozit foiz xarajati qoidasi",
                "rule_type": "interest_expense",
                "source_account_pattern": "20",
                "target_account_pattern": "50",
                "calculation_formula": "balance * rate / 100 / 12",
                "priority": 20
            },
            {
                "code": "LOAN_PROVISION",
                "name_en": "Loan Provision Rule",
                "name_uz": "Kredit zaxirasi qoidasi",
                "rule_type": "provision",
                "source_account_pattern": "12",
                "target_account_pattern": "56",
                "calculation_formula": "balance * rate / 100",
                "priority": 30
            },
        ]

        created = 0
        for rule_data in rules:
            existing = self.db.query(GoldenRule).filter(GoldenRule.code == rule_data["code"]).first()
            if not existing:
                self.db.add(GoldenRule(**rule_data))
                created += 1

        self.db.commit()
        return created
