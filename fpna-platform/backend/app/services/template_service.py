"""
Template Manager Service
Handles template creation, assignment, and pre-filling with baseline data
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Tuple
import logging

from app.models.template import (
    BudgetTemplate, TemplateSection, TemplateAssignment, 
    TemplateLineItem, TemplateType, TemplateStatus
)
from app.models.snapshot import BaselineBudget
from app.models.coa import Account, AccountCategory, AccountGroup
from app.models.business_unit import BusinessUnit, AccountResponsibility
from app.services.driver_engine import DriverEngine

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing budget templates"""

    def __init__(self, db: Session):
        self.db = db

    def create_template(
        self,
        code: str,
        name_en: str,
        name_uz: str,
        template_type: TemplateType = TemplateType.STANDARD,
        fiscal_year: Optional[int] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        created_by_user_id: Optional[int] = None
    ) -> BudgetTemplate:
        """Create a new budget template"""
        template = BudgetTemplate(
            code=code,
            name_en=name_en,
            name_uz=name_uz,
            template_type=template_type,
            fiscal_year=fiscal_year,
            description=description,
            instructions=instructions,
            status=TemplateStatus.DRAFT,
            created_by_user_id=created_by_user_id
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def add_section(
        self,
        template_id: int,
        code: str,
        name_en: str,
        name_uz: str,
        account_pattern: Optional[str] = None,
        account_codes: Optional[List[str]] = None,
        is_editable: bool = True,
        display_order: int = 0
    ) -> TemplateSection:
        """Add section to template"""
        section = TemplateSection(
            template_id=template_id,
            code=code,
            name_en=name_en,
            name_uz=name_uz,
            account_pattern=account_pattern,
            account_codes=",".join(account_codes) if account_codes else None,
            is_editable=is_editable,
            display_order=display_order
        )
        self.db.add(section)
        self.db.commit()
        self.db.refresh(section)
        return section

    def assign_to_business_unit(
        self,
        template_id: int,
        business_unit_id: int,
        fiscal_year: int,
        deadline: Optional[date] = None,
        assigned_by_user_id: Optional[int] = None
    ) -> TemplateAssignment:
        """Assign template to business unit"""
        existing = self.db.query(TemplateAssignment).filter(
            TemplateAssignment.template_id == template_id,
            TemplateAssignment.business_unit_id == business_unit_id,
            TemplateAssignment.fiscal_year == fiscal_year
        ).first()

        if existing:
            return existing

        assignment = TemplateAssignment(
            template_id=template_id,
            business_unit_id=business_unit_id,
            fiscal_year=fiscal_year,
            deadline=deadline,
            status="pending",
            assigned_by_user_id=assigned_by_user_id
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def bulk_assign(
        self,
        template_id: int,
        business_unit_ids: List[int],
        fiscal_year: int,
        deadline: Optional[date] = None,
        assigned_by_user_id: Optional[int] = None
    ) -> List[TemplateAssignment]:
        """Assign template to multiple business units"""
        assignments = []
        for bu_id in business_unit_ids:
            assignment = self.assign_to_business_unit(
                template_id, bu_id, fiscal_year, deadline, assigned_by_user_id
            )
            assignments.append(assignment)
        return assignments

    def generate_prefilled_template(
        self,
        assignment_id: int,
        baseline_version: Optional[int] = None,
        apply_drivers: bool = True
    ) -> Dict:
        """
        Generate template pre-filled with baseline data
        Returns template structure with line items
        """
        assignment = self.db.query(TemplateAssignment).filter(
            TemplateAssignment.id == assignment_id
        ).first()

        if not assignment:
            raise ValueError("Assignment not found")

        template = self.db.query(BudgetTemplate).filter(
            BudgetTemplate.id == assignment.template_id
        ).first()

        business_unit = self.db.query(BusinessUnit).filter(
            BusinessUnit.id == assignment.business_unit_id
        ).first()

        sections = self.db.query(TemplateSection).filter(
            TemplateSection.template_id == template.id
        ).order_by(TemplateSection.display_order).all()

        result = {
            "assignment_id": assignment_id,
            "template_code": template.code,
            "template_name": template.name_en,
            "business_unit_code": business_unit.code if business_unit else None,
            "business_unit_name": business_unit.name_en if business_unit else None,
            "fiscal_year": assignment.fiscal_year,
            "sections": [],
            "total_baseline": Decimal("0"),
            "total_adjusted": Decimal("0"),
            "line_items_count": 0
        }

        for section in sections:
            section_data = {
                "section_id": section.id,
                "code": section.code,
                "name_en": section.name_en,
                "name_uz": section.name_uz,
                "is_editable": section.is_editable,
                "line_items": []
            }

            accounts = self._get_section_accounts(section, business_unit.id if business_unit else None)

            for account in accounts:
                line_item = self._create_or_get_line_item(
                    assignment_id, section.id, account.code,
                    assignment.fiscal_year, baseline_version
                )

                line_item_data = {
                    "line_item_id": line_item.id,
                    "account_code": account.code,
                    "account_name": account.name_en,
                    "baseline": {
                        "jan": line_item.baseline_jan,
                        "feb": line_item.baseline_feb,
                        "mar": line_item.baseline_mar,
                        "apr": line_item.baseline_apr,
                        "may": line_item.baseline_may,
                        "jun": line_item.baseline_jun,
                        "jul": line_item.baseline_jul,
                        "aug": line_item.baseline_aug,
                        "sep": line_item.baseline_sep,
                        "oct": line_item.baseline_oct,
                        "nov": line_item.baseline_nov,
                        "dec": line_item.baseline_dec,
                        "total": line_item.baseline_total
                    },
                    "adjusted": {
                        "jan": line_item.adjusted_jan,
                        "feb": line_item.adjusted_feb,
                        "mar": line_item.adjusted_mar,
                        "apr": line_item.adjusted_apr,
                        "may": line_item.adjusted_may,
                        "jun": line_item.adjusted_jun,
                        "jul": line_item.adjusted_jul,
                        "aug": line_item.adjusted_aug,
                        "sep": line_item.adjusted_sep,
                        "oct": line_item.adjusted_oct,
                        "nov": line_item.adjusted_nov,
                        "dec": line_item.adjusted_dec,
                        "total": line_item.adjusted_total
                    },
                    "is_locked": line_item.is_locked
                }

                section_data["line_items"].append(line_item_data)
                result["total_baseline"] += line_item.baseline_total
                result["total_adjusted"] += line_item.adjusted_total
                result["line_items_count"] += 1

            result["sections"].append(section_data)

        return result

    def _get_section_accounts(
        self,
        section: TemplateSection,
        business_unit_id: Optional[int]
    ) -> List[Account]:
        """Get accounts for a template section"""
        query = self.db.query(Account).filter(Account.is_active == True)

        if section.account_codes:
            codes = section.account_codes_list
            query = query.filter(Account.code.in_(codes))
        elif section.account_pattern:
            query = query.filter(Account.code.startswith(section.account_pattern))

        if business_unit_id:
            responsible_accounts = self.db.query(AccountResponsibility.account_id).filter(
                AccountResponsibility.business_unit_id == business_unit_id,
                AccountResponsibility.can_budget == True
            )
            query = query.filter(Account.id.in_(responsible_accounts))

        return query.order_by(Account.code).all()

    def _create_or_get_line_item(
        self,
        assignment_id: int,
        section_id: int,
        account_code: str,
        fiscal_year: int,
        baseline_version: Optional[int]
    ) -> TemplateLineItem:
        """Create or retrieve line item with baseline data"""
        existing = self.db.query(TemplateLineItem).filter(
            TemplateLineItem.assignment_id == assignment_id,
            TemplateLineItem.section_id == section_id,
            TemplateLineItem.account_code == account_code
        ).first()

        if existing:
            return existing

        baseline_query = self.db.query(BaselineBudget).filter(
            BaselineBudget.fiscal_year == fiscal_year,
            BaselineBudget.account_code == account_code,
            BaselineBudget.is_active == True
        )
        if baseline_version:
            baseline_query = baseline_query.filter(
                BaselineBudget.baseline_version == baseline_version
            )
        baseline = baseline_query.order_by(BaselineBudget.baseline_version.desc()).first()

        line_item = TemplateLineItem(
            assignment_id=assignment_id,
            section_id=section_id,
            account_code=account_code,
            baseline_jan=baseline.jan if baseline else Decimal("0"),
            baseline_feb=baseline.feb if baseline else Decimal("0"),
            baseline_mar=baseline.mar if baseline else Decimal("0"),
            baseline_apr=baseline.apr if baseline else Decimal("0"),
            baseline_may=baseline.may if baseline else Decimal("0"),
            baseline_jun=baseline.jun if baseline else Decimal("0"),
            baseline_jul=baseline.jul if baseline else Decimal("0"),
            baseline_aug=baseline.aug if baseline else Decimal("0"),
            baseline_sep=baseline.sep if baseline else Decimal("0"),
            baseline_oct=baseline.oct if baseline else Decimal("0"),
            baseline_nov=baseline.nov if baseline else Decimal("0"),
            baseline_dec=baseline.dec if baseline else Decimal("0"),
        )
        self.db.add(line_item)
        self.db.commit()
        self.db.refresh(line_item)
        return line_item

    def update_line_item(
        self,
        line_item_id: int,
        adjusted_values: Dict[str, Decimal],
        notes: Optional[str] = None
    ) -> TemplateLineItem:
        """Update adjusted values for a line item"""
        line_item = self.db.query(TemplateLineItem).filter(
            TemplateLineItem.id == line_item_id
        ).first()

        if not line_item:
            raise ValueError("Line item not found")

        if line_item.is_locked:
            raise ValueError("Line item is locked")

        month_fields = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                        'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

        for month in month_fields:
            if month in adjusted_values:
                setattr(line_item, f"adjusted_{month}", adjusted_values[month])

        if notes:
            line_item.adjustment_notes = notes

        self.db.commit()
        self.db.refresh(line_item)
        return line_item

    def submit_template(
        self,
        assignment_id: int,
        submitted_by_user_id: int,
        notes: Optional[str] = None
    ) -> Tuple[TemplateAssignment, bool, List[str]]:
        """
        Submit filled template for approval
        Returns: (assignment, validation_passed, errors)
        """
        assignment = self.db.query(TemplateAssignment).filter(
            TemplateAssignment.id == assignment_id
        ).first()

        if not assignment:
            raise ValueError("Assignment not found")

        validation_passed, errors = self._validate_template(assignment_id)

        if validation_passed:
            assignment.status = "submitted"
            assignment.submitted_at = datetime.utcnow()
            assignment.submitted_by_user_id = submitted_by_user_id
            if notes:
                assignment.notes = notes
            self.db.commit()

        return assignment, validation_passed, errors

    def _validate_template(self, assignment_id: int) -> Tuple[bool, List[str]]:
        """Validate template before submission"""
        errors = []

        line_items = self.db.query(TemplateLineItem).filter(
            TemplateLineItem.assignment_id == assignment_id
        ).all()

        if not line_items:
            errors.append("No line items found in template")
            return False, errors

        for item in line_items:
            section = self.db.query(TemplateSection).filter(
                TemplateSection.id == item.section_id
            ).first()

            if section and section.is_required:
                if item.adjusted_total == 0 and item.baseline_total == 0:
                    pass

        return len(errors) == 0, errors

    def get_templates_for_user(
        self,
        user_id: int,
        fiscal_year: Optional[int] = None,
        business_unit_id: Optional[int] = None
    ) -> List[Dict]:
        """Get templates assigned to user's business unit(s)"""
        query = self.db.query(TemplateAssignment).join(
            BudgetTemplate
        ).filter(
            BudgetTemplate.is_active == True
        )

        if fiscal_year:
            query = query.filter(TemplateAssignment.fiscal_year == fiscal_year)

        if business_unit_id:
            query = query.filter(TemplateAssignment.business_unit_id == business_unit_id)

        assignments = query.all()

        results = []
        for assignment in assignments:
            template = self.db.query(BudgetTemplate).filter(
                BudgetTemplate.id == assignment.template_id
            ).first()
            business_unit = self.db.query(BusinessUnit).filter(
                BusinessUnit.id == assignment.business_unit_id
            ).first()

            results.append({
                "assignment_id": assignment.id,
                "template_id": template.id,
                "template_code": template.code,
                "template_name": template.name_en,
                "business_unit_id": business_unit.id if business_unit else None,
                "business_unit_code": business_unit.code if business_unit else None,
                "business_unit_name": business_unit.name_en if business_unit else None,
                "fiscal_year": assignment.fiscal_year,
                "deadline": assignment.deadline,
                "status": assignment.status
            })

        return results

    def activate_template(self, template_id: int) -> BudgetTemplate:
        """Activate a template (change status from draft to active)"""
        template = self.db.query(BudgetTemplate).filter(
            BudgetTemplate.id == template_id
        ).first()

        if not template:
            raise ValueError("Template not found")

        sections = self.db.query(TemplateSection).filter(
            TemplateSection.template_id == template_id
        ).count()

        if sections == 0:
            raise ValueError("Template must have at least one section")

        template.status = TemplateStatus.ACTIVE
        self.db.commit()
        self.db.refresh(template)
        return template

    def clone_template(
        self,
        source_template_id: int,
        new_code: str,
        new_fiscal_year: Optional[int] = None,
        created_by_user_id: Optional[int] = None
    ) -> BudgetTemplate:
        """Clone an existing template"""
        source = self.db.query(BudgetTemplate).filter(
            BudgetTemplate.id == source_template_id
        ).first()

        if not source:
            raise ValueError("Source template not found")

        new_template = BudgetTemplate(
            code=new_code,
            name_en=f"{source.name_en} (Copy)",
            name_uz=f"{source.name_uz} (Nusxa)",
            description=source.description,
            template_type=source.template_type,
            fiscal_year=new_fiscal_year or source.fiscal_year,
            include_baseline=source.include_baseline,
            include_prior_year=source.include_prior_year,
            include_variance=source.include_variance,
            instructions=source.instructions,
            status=TemplateStatus.DRAFT,
            created_by_user_id=created_by_user_id
        )
        self.db.add(new_template)
        self.db.flush()

        source_sections = self.db.query(TemplateSection).filter(
            TemplateSection.template_id == source_template_id
        ).all()

        for section in source_sections:
            new_section = TemplateSection(
                template_id=new_template.id,
                code=section.code,
                name_en=section.name_en,
                name_uz=section.name_uz,
                description=section.description,
                section_type=section.section_type,
                account_pattern=section.account_pattern,
                account_codes=section.account_codes,
                is_editable=section.is_editable,
                is_required=section.is_required,
                is_collapsed=section.is_collapsed,
                show_subtotals=section.show_subtotals,
                show_monthly=section.show_monthly,
                show_quarterly=section.show_quarterly,
                show_annual=section.show_annual,
                validation_rules=section.validation_rules,
                display_order=section.display_order
            )
            self.db.add(new_section)

        self.db.commit()
        self.db.refresh(new_template)
        return new_template

    def seed_default_templates(self) -> int:
        """Seed default budget templates"""
        templates = [
            {
                "code": "REVENUE_BUDGET",
                "name_en": "Revenue Budget Template",
                "name_uz": "Daromad byudjeti shabloni",
                "template_type": TemplateType.REVENUE,
                "description": "Standard template for revenue planning",
                "sections": [
                    {"code": "INT_INCOME_LOANS", "name_en": "Interest Income - Loans", "name_uz": "Foiz daromadi - Kreditlar", "account_pattern": "40", "display_order": 1},
                    {"code": "INT_INCOME_SEC", "name_en": "Interest Income - Securities", "name_uz": "Foiz daromadi - Qimmatli qog'ozlar", "account_pattern": "41", "display_order": 2},
                    {"code": "FEE_INCOME", "name_en": "Fee and Commission Income", "name_uz": "Komissiya daromadi", "account_pattern": "43", "display_order": 3},
                    {"code": "FX_INCOME", "name_en": "FX Trading Income", "name_uz": "Valyuta savdosi daromadi", "account_pattern": "44", "display_order": 4},
                ]
            },
            {
                "code": "EXPENSE_BUDGET",
                "name_en": "Expense Budget Template",
                "name_uz": "Xarajat byudjeti shabloni",
                "template_type": TemplateType.EXPENSE,
                "description": "Standard template for expense planning",
                "sections": [
                    {"code": "INT_EXPENSE", "name_en": "Interest Expense", "name_uz": "Foiz xarajati", "account_pattern": "50", "display_order": 1},
                    {"code": "PERSONNEL", "name_en": "Personnel Expenses", "name_uz": "Xodimlar xarajati", "account_pattern": "53", "display_order": 2},
                    {"code": "ADMIN", "name_en": "Administrative Expenses", "name_uz": "Ma'muriy xarajatlar", "account_pattern": "54", "display_order": 3},
                    {"code": "DEPRECIATION", "name_en": "Depreciation", "name_uz": "Amortizatsiya", "account_pattern": "55", "display_order": 4},
                    {"code": "PROVISIONS", "name_en": "Provisions", "name_uz": "Zaxiralar", "account_pattern": "56", "display_order": 5},
                ]
            },
            {
                "code": "BALANCE_SHEET",
                "name_en": "Balance Sheet Budget Template",
                "name_uz": "Balans byudjeti shabloni",
                "template_type": TemplateType.BALANCE_SHEET,
                "description": "Template for balance sheet planning",
                "sections": [
                    {"code": "CASH", "name_en": "Cash and Equivalents", "name_uz": "Naqd pul va ekvivalentlar", "account_pattern": "10", "display_order": 1},
                    {"code": "LOANS", "name_en": "Loans to Customers", "name_uz": "Mijozlarga kreditlar", "account_pattern": "12", "display_order": 2},
                    {"code": "DEPOSITS", "name_en": "Customer Deposits", "name_uz": "Mijozlar depozitlari", "account_pattern": "20", "is_editable": False, "display_order": 3},
                    {"code": "EQUITY", "name_en": "Equity", "name_uz": "Kapital", "account_pattern": "3", "is_editable": False, "display_order": 4},
                ]
            },
        ]

        created = 0
        for tmpl_data in templates:
            existing = self.db.query(BudgetTemplate).filter(
                BudgetTemplate.code == tmpl_data["code"]
            ).first()

            if existing:
                continue

            sections = tmpl_data.pop("sections", [])
            template = BudgetTemplate(**tmpl_data, status=TemplateStatus.ACTIVE)
            self.db.add(template)
            self.db.flush()

            for section_data in sections:
                section = TemplateSection(template_id=template.id, **section_data)
                self.db.add(section)

            created += 1

        self.db.commit()
        return created
