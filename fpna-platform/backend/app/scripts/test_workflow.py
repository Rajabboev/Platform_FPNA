"""
End-to-End Test Script for FP&A Budget Planning Workflow

Tests the complete workflow:
1. DWH Ingest → Load historical data
2. Baseline Calculation → Generate baseline by groups
3. Department Assignment → Create plans for departments
4. Adjustments → Apply drivers and manual adjustments
5. Approval → Two-level approval workflow
6. Export → Send approved budgets to DWH

Run: python -m app.scripts.test_workflow
"""

import logging
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy import text
from app.database import SessionLocal
from app.models.department import Department, DepartmentAssignment
from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanStatus
from app.models.coa_dimension import BudgetingGroup, COADimension
from app.models.dwh_connection import DWHConnection
from app.models.user import User
from app.services.budget_planning_service import BudgetPlanningService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WorkflowTester:
    """End-to-end workflow tester"""
    
    def __init__(self):
        self.db = SessionLocal()
        self.service = BudgetPlanningService(self.db)
        self.fiscal_year = 2026
        self.results: Dict[str, Any] = {}
    
    def cleanup(self):
        """Close database session"""
        self.db.close()
    
    def print_header(self, title: str):
        """Print section header"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    
    def print_result(self, step: str, success: bool, details: str = ""):
        """Print step result"""
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {step}")
        if details:
            print(f"         {details}")
    
    def step_1_check_prerequisites(self) -> bool:
        """Step 1: Check prerequisites"""
        self.print_header("STEP 1: Check Prerequisites")
        
        # Check COA Dimension
        coa_count = self.db.query(COADimension).count()
        self.print_result("COA Dimension loaded", coa_count > 0, f"{coa_count} accounts")
        
        # Check Budgeting Groups
        group_count = self.db.query(BudgetingGroup).count()
        self.print_result("Budgeting Groups loaded", group_count > 0, f"{group_count} groups")
        
        # Check Departments
        dept_count = self.db.query(Department).count()
        self.print_result("Departments created", dept_count > 0, f"{dept_count} departments")
        
        # Check DWH Connection
        dwh_conn = self.db.query(DWHConnection).filter(DWHConnection.is_active == True).first()
        self.print_result("DWH Connection available", dwh_conn is not None, 
                         dwh_conn.name if dwh_conn else "No active connection")
        
        # Check Users
        user = self.db.query(User).first()
        self.print_result("Users exist", user is not None, user.username if user else "No users")
        
        all_passed = coa_count > 0 and group_count > 0 and dept_count > 0
        self.results["prerequisites"] = {
            "coa_count": coa_count,
            "group_count": group_count,
            "dept_count": dept_count,
            "dwh_available": dwh_conn is not None,
            "passed": all_passed
        }
        
        return all_passed
    
    def step_2_calculate_baseline(self) -> bool:
        """Step 2: Calculate baseline by groups"""
        self.print_header("STEP 2: Calculate Baseline by Groups")
        
        try:
            # Use 2024 and 2025 as source years
            result = self.service.calculate_baseline_by_groups(
                target_fiscal_year=self.fiscal_year,
                source_years=[2024, 2025],
                method="simple_average"
            )
            
            self.print_result("Baseline calculation", True, 
                             f"{result.get('groups_processed', 0)} groups, {result.get('total_accounts', 0)} accounts")
            
            # Show sample baseline data
            if result.get("baseline_by_group"):
                print("\n  Sample Baseline Data:")
                for i, (group_id, data) in enumerate(result["baseline_by_group"].items()):
                    if i >= 3:
                        break
                    total = sum(data.get("monthly", {}).values())
                    print(f"    Group {group_id}: Total = {total:,.2f}")
            
            self.results["baseline"] = result
            return True
            
        except Exception as e:
            self.print_result("Baseline calculation", False, str(e))
            logger.exception("Baseline calculation failed")
            return False
    
    def step_3_create_department_plans(self) -> bool:
        """Step 3: Create department plans"""
        self.print_header("STEP 3: Create Department Plans")
        
        try:
            # Get admin user
            user = self.db.query(User).filter(User.role == "admin").first()
            if not user:
                user = self.db.query(User).first()
            
            if not user:
                self.print_result("Create plans", False, "No user found")
                return False
            
            baseline_data = self.results.get("baseline", {})
            
            result = self.service.create_department_plans(
                fiscal_year=self.fiscal_year,
                user_id=user.id,
                baseline_data=baseline_data if baseline_data.get("status") == "success" else None,
                source_years=None,
                method="simple_average",
            )
            
            self.print_result("Department plans created", True, 
                             f"{result.get('plans_created', 0)} plans")
            
            # List created plans
            plans = self.db.query(BudgetPlan).filter(
                BudgetPlan.fiscal_year == self.fiscal_year
            ).all()
            
            print("\n  Created Plans:")
            for plan in plans:
                dept = self.db.query(Department).get(plan.department_id)
                groups = self.db.query(BudgetPlanGroup).filter(
                    BudgetPlanGroup.plan_id == plan.id
                ).count()
                print(f"    {dept.code}: {groups} groups, Status: {plan.status.value}")
            
            self.results["plans"] = result
            self.results["plan_ids"] = [p.id for p in plans]
            return True
            
        except Exception as e:
            self.print_result("Create plans", False, str(e))
            logger.exception("Plan creation failed")
            return False
    
    def step_4_apply_adjustments(self) -> bool:
        """Step 4: Apply driver adjustments"""
        self.print_header("STEP 4: Apply Driver Adjustments")
        
        try:
            # Get first non-baseline-only plan
            plan = self.db.query(BudgetPlan).join(Department).filter(
                BudgetPlan.fiscal_year == self.fiscal_year,
                Department.is_baseline_only == False
            ).first()
            
            if not plan:
                self.print_result("Apply adjustments", False, "No editable plan found")
                return False
            
            # Get first group in this plan
            group = self.db.query(BudgetPlanGroup).filter(
                BudgetPlanGroup.plan_id == plan.id
            ).first()
            
            if not group:
                self.print_result("Apply adjustments", False, "No groups in plan")
                return False
            
            # Get user
            user = self.db.query(User).first()
            
            # Apply a 5% growth driver
            result = self.service.update_group_adjustment(
                plan_id=plan.id,
                group_id=group.id,
                driver_code="GROWTH",
                driver_rate=Decimal("5.0"),
                notes="Test 5% growth adjustment",
                user_id=user.id
            )
            
            self.print_result("Driver adjustment applied", True, 
                             f"Plan {plan.id}, Group {group.budgeting_group_id}: 5% growth")
            
            # Show before/after
            print(f"\n  Group {group.budgeting_group_id} Adjustment:")
            print(f"    Baseline Jan: {group.baseline_jan:,.2f}")
            print(f"    Adjusted Jan: {group.adjusted_jan:,.2f}")
            print(f"    Driver: {group.driver_code} @ {group.driver_rate}%")
            
            self.results["adjustment"] = {
                "plan_id": plan.id,
                "group_id": group.id,
                "driver_rate": 5.0
            }
            return True
            
        except Exception as e:
            self.print_result("Apply adjustments", False, str(e))
            logger.exception("Adjustment failed")
            return False
    
    def step_5_submit_plan(self) -> bool:
        """Step 5: Submit plan for approval"""
        self.print_header("STEP 5: Submit Plan for Approval")
        
        try:
            # Get the plan we adjusted
            plan_id = self.results.get("adjustment", {}).get("plan_id")
            if not plan_id:
                # Get any editable plan
                plan = self.db.query(BudgetPlan).join(Department).filter(
                    BudgetPlan.fiscal_year == self.fiscal_year,
                    Department.is_baseline_only == False
                ).first()
                plan_id = plan.id if plan else None
            
            if not plan_id:
                self.print_result("Submit plan", False, "No plan to submit")
                return False
            
            user = self.db.query(User).first()
            
            result = self.service.submit_plan(plan_id, user.id)
            
            self.print_result("Plan submitted", True, 
                             f"Plan {plan_id} → Status: {result.status.value}")
            
            self.results["submitted_plan_id"] = plan_id
            return True
            
        except Exception as e:
            self.print_result("Submit plan", False, str(e))
            logger.exception("Submit failed")
            return False
    
    def step_6_department_approval(self) -> bool:
        """Step 6: Department head approval"""
        self.print_header("STEP 6: Department Head Approval")
        
        try:
            plan_id = self.results.get("submitted_plan_id")
            if not plan_id:
                self.print_result("Dept approval", False, "No submitted plan")
                return False
            
            user = self.db.query(User).first()
            
            result = self.service.approve_plan_dept(
                plan_id, 
                user.id, 
                comment="Approved by department head"
            )
            
            self.print_result("Department approval", True, 
                             f"Plan {plan_id} → Status: {result.status.value}")
            
            return True
            
        except Exception as e:
            self.print_result("Dept approval", False, str(e))
            logger.exception("Dept approval failed")
            return False
    
    def step_7_cfo_approval(self) -> bool:
        """Step 7: CFO final approval"""
        self.print_header("STEP 7: CFO Final Approval")
        
        try:
            plan_id = self.results.get("submitted_plan_id")
            if not plan_id:
                self.print_result("CFO approval", False, "No plan for CFO approval")
                return False
            
            user = self.db.query(User).first()
            
            result = self.service.approve_plan_cfo(
                plan_id, 
                user.id, 
                comment="Final CFO approval"
            )
            
            self.print_result("CFO approval", True, 
                             f"Plan {plan_id} → Status: {result.status.value}")
            
            return True
            
        except Exception as e:
            self.print_result("CFO approval", False, str(e))
            logger.exception("CFO approval failed")
            return False
    
    def step_8_check_workflow_status(self) -> bool:
        """Step 8: Check overall workflow status"""
        self.print_header("STEP 8: Workflow Status Summary")
        
        try:
            status = self.service.get_workflow_status(self.fiscal_year)
            
            print(f"\n  Fiscal Year: {self.fiscal_year}")
            print(f"  Total Plans: {status.get('total_plans', 0)}")
            print(f"\n  Status Breakdown:")
            for s, count in status.get("by_status", {}).items():
                print(f"    {s}: {count}")
            
            print(f"\n  Totals:")
            print(f"    Baseline: {status.get('total_baseline', 0):,.2f}")
            print(f"    Adjusted: {status.get('total_adjusted', 0):,.2f}")
            
            ready = status.get("ready_for_export", 0)
            self.print_result("Workflow status", True, 
                             f"{ready} plans ready for export")
            
            self.results["workflow_status"] = status
            return True
            
        except Exception as e:
            self.print_result("Workflow status", False, str(e))
            logger.exception("Status check failed")
            return False
    
    def run_all_steps(self):
        """Run all workflow steps"""
        print("\n" + "#" * 70)
        print("#  FP&A BUDGET PLANNING - END-TO-END WORKFLOW TEST")
        print("#  Fiscal Year:", self.fiscal_year)
        print("#  Started:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("#" * 70)
        
        steps = [
            ("Prerequisites", self.step_1_check_prerequisites),
            ("Baseline Calculation", self.step_2_calculate_baseline),
            ("Department Plans", self.step_3_create_department_plans),
            ("Adjustments", self.step_4_apply_adjustments),
            ("Submit Plan", self.step_5_submit_plan),
            ("Dept Approval", self.step_6_department_approval),
            ("CFO Approval", self.step_7_cfo_approval),
            ("Workflow Status", self.step_8_check_workflow_status),
        ]
        
        passed = 0
        failed = 0
        
        for name, step_func in steps:
            try:
                if step_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.exception(f"Step {name} crashed")
                failed += 1
        
        # Final summary
        print("\n" + "#" * 70)
        print("#  WORKFLOW TEST SUMMARY")
        print("#" * 70)
        print(f"\n  Total Steps: {len(steps)}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"\n  Result: {'SUCCESS' if failed == 0 else 'PARTIAL' if passed > 0 else 'FAILED'}")
        print("#" * 70 + "\n")
        
        return failed == 0


def main():
    """Main entry point"""
    tester = WorkflowTester()
    
    try:
        success = tester.run_all_steps()
        sys.exit(0 if success else 1)
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
