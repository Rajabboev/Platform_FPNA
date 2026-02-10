-- =============================================
-- SQL Server DDL for FP&A Platform (Banking Sector)
-- Version: v1.0 (based on Metadata v3)
-- Generated: FP&A Full DDL (Dimensions, Facts, App, Planning, Allocation, CRM, HR)
-- Target: Microsoft SQL Server
-- Notes:
--  * Create dimensions in order to satisfy FK dependencies (dim_currency, dim_region, dim_branch, dim_department, dim_position, dim_employee, etc.)
--  * For self-referencing FKs (dim_entity.parent_entity_key, dim_businessunit.parent_bu_key, dim_employee.supervisor_key), create table then add FK constraints if needed.
--  * Use deferred or two-step load for circular references (employee -> department -> employee manager). In DDL below we add some FKs after creating referenced tables.
-- =============================================

SET NOCOUNT ON;

-- =====================================================
-- SCHEMA: default dbo (you may adjust schema names)
-- =====================================================

-- =====================================================
-- DIMENSION TABLES
-- =====================================================

CREATE TABLE dbo.dim_currency (
    currency_key INT PRIMARY KEY,
    currency_code VARCHAR(10) NOT NULL,
    currency_name VARCHAR(50) NULL,
    is_base BIT NOT NULL DEFAULT 0,
    fx_rate_to_base DECIMAL(18,6) NULL
);

CREATE TABLE dbo.dim_date (
    date_key INT PRIMARY KEY,
    date_value DATE NOT NULL,
    year_num INT NULL,
    month_num INT NULL,
    quarter_num INT NULL,
    month_name VARCHAR(20) NULL,
    fiscal_year INT NULL,
    fiscal_period INT NULL,
    is_month_end BIT NULL
);

CREATE TABLE dbo.dim_scenario (
    scenario_key INT PRIMARY KEY,
    scenario_name VARCHAR(50) NOT NULL,
    category VARCHAR(50) NULL,
    description VARCHAR(200) NULL
);

CREATE TABLE dbo.dim_region (
    region_key INT PRIMARY KEY,
    region_code VARCHAR(20) NULL,
    region_name VARCHAR(100) NULL
);

CREATE TABLE dbo.dim_branch (
    branch_key INT PRIMARY KEY,
    branch_code VARCHAR(20) NULL,
    branch_name VARCHAR(200) NULL,
    region_key INT NULL
);
ALTER TABLE dbo.dim_branch
    ADD CONSTRAINT fk_dim_branch_region FOREIGN KEY (region_key) REFERENCES dbo.dim_region(region_key);

CREATE TABLE dbo.dim_businessunit (
    bu_key INT PRIMARY KEY,
    bu_code VARCHAR(20) NULL,
    bu_name VARCHAR(200) NULL,
    parent_bu_key INT NULL
);
ALTER TABLE dbo.dim_businessunit
    ADD CONSTRAINT fk_dim_bu_parent FOREIGN KEY (parent_bu_key) REFERENCES dbo.dim_businessunit(bu_key);

CREATE TABLE dbo.dim_product (
    product_key INT PRIMARY KEY,
    product_code VARCHAR(50) NULL,
    product_name VARCHAR(200) NULL,
    product_type VARCHAR(50) NULL,
    bu_key INT NULL
);
ALTER TABLE dbo.dim_product
    ADD CONSTRAINT fk_dim_product_bu FOREIGN KEY (bu_key) REFERENCES dbo.dim_businessunit(bu_key);

CREATE TABLE dbo.dim_account (
    account_key INT PRIMARY KEY,
    account_code VARCHAR(50) NULL,
    account_name VARCHAR(200) NULL,
    account_type VARCHAR(50) NULL,
    gl_group VARCHAR(50) NULL
);

CREATE TABLE dbo.dim_driver (
    driver_key INT PRIMARY KEY,
    driver_name VARCHAR(100) NULL,
    driver_type VARCHAR(50) NULL,
    description VARCHAR(200) NULL
);

CREATE TABLE dbo.dim_entity (
    entity_key INT PRIMARY KEY,
    entity_code VARCHAR(20) NULL,
    entity_name VARCHAR(200) NULL,
    parent_entity_key INT NULL,
    country VARCHAR(50) NULL,
    currency_key INT NULL
);
ALTER TABLE dbo.dim_entity
    ADD CONSTRAINT fk_dim_entity_currency FOREIGN KEY (currency_key) REFERENCES dbo.dim_currency(currency_key);
-- add self-FK later to avoid ordering issues
ALTER TABLE dbo.dim_entity
    ADD CONSTRAINT fk_dim_entity_parent FOREIGN KEY (parent_entity_key) REFERENCES dbo.dim_entity(entity_key);

CREATE TABLE dbo.dim_position (
    position_key INT PRIMARY KEY,
    position_name VARCHAR(100) NULL,
    level VARCHAR(50) NULL
);

CREATE TABLE dbo.dim_department (
    department_key INT PRIMARY KEY,
    dept_code VARCHAR(50) NULL,
    dept_name VARCHAR(200) NULL,
    branch_key INT NULL,
    manager_emp_key INT NULL
);
ALTER TABLE dbo.dim_department
    ADD CONSTRAINT fk_dim_department_branch FOREIGN KEY (branch_key) REFERENCES dbo.dim_branch(branch_key);
-- manager_emp_key will reference dim_employee; add later after dim_employee created

CREATE TABLE dbo.dim_employee (
    employee_key INT PRIMARY KEY,
    employee_id VARCHAR(50) NULL,
    employee_name VARCHAR(200) NULL,
    position_key INT NULL,
    department_key INT NULL,
    supervisor_key INT NULL,
    hire_date DATE NULL,
    termination_date DATE NULL,
    status VARCHAR(20) NULL
);
ALTER TABLE dbo.dim_employee
    ADD CONSTRAINT fk_dim_employee_position FOREIGN KEY (position_key) REFERENCES dbo.dim_position(position_key);
ALTER TABLE dbo.dim_employee
    ADD CONSTRAINT fk_dim_employee_department FOREIGN KEY (department_key) REFERENCES dbo.dim_department(department_key);
-- supervisor self-FK
ALTER TABLE dbo.dim_employee
    ADD CONSTRAINT fk_dim_employee_supervisor FOREIGN KEY (supervisor_key) REFERENCES dbo.dim_employee(employee_key);

-- now add department.manager_emp_key fk to dim_employee
ALTER TABLE dbo.dim_department
    ADD CONSTRAINT fk_dim_department_manager FOREIGN KEY (manager_emp_key) REFERENCES dbo.dim_employee(employee_key);

CREATE TABLE dbo.dim_customer_segment (
    segment_key INT PRIMARY KEY,
    segment_name VARCHAR(100) NULL,
    criteria_definition TEXT NULL,
    owner_department_key INT NULL
);
ALTER TABLE dbo.dim_customer_segment
    ADD CONSTRAINT fk_dim_custseg_dept FOREIGN KEY (owner_department_key) REFERENCES dbo.dim_department(department_key);

CREATE TABLE dbo.dim_customer (
    customer_key INT PRIMARY KEY,
    customer_id VARCHAR(50) NULL,
    customer_name VARCHAR(200) NULL,
    customer_type VARCHAR(50) NULL,
    segment_key INT NULL,
    assigned_dept_key INT NULL,
    assigned_emp_key INT NULL,
    risk_score DECIMAL(5,2) NULL,
    lifetime_value DECIMAL(18,2) NULL,
    onboarding_date DATE NULL,
    status VARCHAR(20) NULL
);
ALTER TABLE dbo.dim_customer
    ADD CONSTRAINT fk_dim_customer_segment FOREIGN KEY (segment_key) REFERENCES dbo.dim_customer_segment(segment_key);
ALTER TABLE dbo.dim_customer
    ADD CONSTRAINT fk_dim_customer_dept FOREIGN KEY (assigned_dept_key) REFERENCES dbo.dim_department(department_key);
ALTER TABLE dbo.dim_customer
    ADD CONSTRAINT fk_dim_customer_emp FOREIGN KEY (assigned_emp_key) REFERENCES dbo.dim_employee(employee_key);

-- =====================================================
-- APPLICATION / SECURITY / WORKFLOW DIMENSIONS
-- =====================================================

CREATE TABLE dbo.app_user (
    user_id INT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NULL,
    employee_key INT NULL,
    email VARCHAR(150) NULL,
    is_active BIT NOT NULL DEFAULT 1
);
ALTER TABLE dbo.app_user
    ADD CONSTRAINT fk_appuser_employee FOREIGN KEY (employee_key) REFERENCES dbo.dim_employee(employee_key);

CREATE TABLE dbo.app_role (
    role_id INT PRIMARY KEY,
    role_name VARCHAR(100) NOT NULL,
    role_scope VARCHAR(50) NULL,
    description VARCHAR(200) NULL
);

CREATE TABLE dbo.user_role_mapping (
    user_role_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    active_from DATE NULL,
    active_to DATE NULL
);
ALTER TABLE dbo.user_role_mapping
    ADD CONSTRAINT fk_userrole_user FOREIGN KEY (user_id) REFERENCES dbo.app_user(user_id);
ALTER TABLE dbo.user_role_mapping
    ADD CONSTRAINT fk_userrole_role FOREIGN KEY (role_id) REFERENCES dbo.app_role(role_id);

CREATE TABLE dbo.workflow_status (
    status_id INT PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL,
    description VARCHAR(200) NULL
);

-- =====================================================
-- PLANNING / APPROVAL METADATA
-- =====================================================

CREATE TABLE dbo.planning_cycle (
    planning_cycle_id INT PRIMARY KEY,
    cycle_name VARCHAR(100) NULL,
    start_period_key INT NULL,
    end_period_key INT NULL,
    created_by_user INT NULL,
    cycle_status VARCHAR(50) NULL,
    approval_deadline DATE NULL
);
ALTER TABLE dbo.planning_cycle
    ADD CONSTRAINT fk_plancyc_startdate FOREIGN KEY (start_period_key) REFERENCES dbo.dim_date(date_key);
ALTER TABLE dbo.planning_cycle
    ADD CONSTRAINT fk_plancyc_enddate FOREIGN KEY (end_period_key) REFERENCES dbo.dim_date(date_key);
ALTER TABLE dbo.planning_cycle
    ADD CONSTRAINT fk_plancyc_createdby FOREIGN KEY (created_by_user) REFERENCES dbo.app_user(user_id);

CREATE TABLE dbo.plan_metadata (
    plan_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    scenario_key INT NULL,
    planning_cycle_id INT NULL,
    department_key INT NULL,
    created_by_user INT NULL,
    current_status_id INT NULL,
    version_no INT NULL,
    created_at DATETIME DEFAULT GETDATE(),
    approved_at DATETIME NULL,
    is_active BIT DEFAULT 1
);
ALTER TABLE dbo.plan_metadata
    ADD CONSTRAINT fk_planmeta_scenario FOREIGN KEY (scenario_key) REFERENCES dbo.dim_scenario(scenario_key);
ALTER TABLE dbo.plan_metadata
    ADD CONSTRAINT fk_planmeta_cycle FOREIGN KEY (planning_cycle_id) REFERENCES dbo.planning_cycle(planning_cycle_id);
ALTER TABLE dbo.plan_metadata
    ADD CONSTRAINT fk_planmeta_dept FOREIGN KEY (department_key) REFERENCES dbo.dim_department(department_key);
ALTER TABLE dbo.plan_metadata
    ADD CONSTRAINT fk_planmeta_createdby FOREIGN KEY (created_by_user) REFERENCES dbo.app_user(user_id);
ALTER TABLE dbo.plan_metadata
    ADD CONSTRAINT fk_planmeta_status FOREIGN KEY (current_status_id) REFERENCES dbo.workflow_status(status_id);

CREATE TABLE dbo.plan_approval_history (
    approval_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    plan_id BIGINT NOT NULL,
    action_by_user INT NULL,
    previous_status INT NULL,
    new_status INT NULL,
    action_date DATETIME DEFAULT GETDATE(),
    remarks VARCHAR(MAX) NULL
);
ALTER TABLE dbo.plan_approval_history
    ADD CONSTRAINT fk_planhist_plan FOREIGN KEY (plan_id) REFERENCES dbo.plan_metadata(plan_id);
ALTER TABLE dbo.plan_approval_history
    ADD CONSTRAINT fk_planhist_actionby FOREIGN KEY (action_by_user) REFERENCES dbo.app_user(user_id);
ALTER TABLE dbo.plan_approval_history
    ADD CONSTRAINT fk_planhist_prevstatus FOREIGN KEY (previous_status) REFERENCES dbo.workflow_status(status_id);
ALTER TABLE dbo.plan_approval_history
    ADD CONSTRAINT fk_planhist_newstatus FOREIGN KEY (new_status) REFERENCES dbo.workflow_status(status_id);

-- =====================================================
-- ALLOCATION / DRIVER / FX METADATA
-- =====================================================

CREATE TABLE dbo.allocation_rule (
    rule_id INT PRIMARY KEY,
    rule_name VARCHAR(200) NULL,
    from_account_key INT NULL,
    driver_key INT NULL,
    target_level VARCHAR(50) NULL,
    formula_text VARCHAR(MAX) NULL
);
ALTER TABLE dbo.allocation_rule
    ADD CONSTRAINT fk_allocrule_account FOREIGN KEY (from_account_key) REFERENCES dbo.dim_account(account_key);
ALTER TABLE dbo.allocation_rule
    ADD CONSTRAINT fk_allocrule_driver FOREIGN KEY (driver_key) REFERENCES dbo.dim_driver(driver_key);

CREATE TABLE dbo.driver_values (
    driver_value_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    date_key INT NOT NULL,
    driver_key INT NOT NULL,
    target_key INT NOT NULL,
    driver_amount DECIMAL(18,6) NULL
);
ALTER TABLE dbo.driver_values
    ADD CONSTRAINT fk_driverval_date FOREIGN KEY (date_key) REFERENCES dbo.dim_date(date_key);
ALTER TABLE dbo.driver_values
    ADD CONSTRAINT fk_driverval_driver FOREIGN KEY (driver_key) REFERENCES dbo.dim_driver(driver_key);

CREATE TABLE dbo.fx_rate (
    rate_date DATE NOT NULL,
    currency_key INT NOT NULL,
    fx_to_base DECIMAL(18,6) NULL,
    PRIMARY KEY (rate_date, currency_key)
);
ALTER TABLE dbo.fx_rate
    ADD CONSTRAINT fk_fx_currency FOREIGN KEY (currency_key) REFERENCES dbo.dim_currency(currency_key);

-- =====================================================
-- FACT TABLES (continued)
-- =====================================================

CREATE TABLE dbo.fact_allocation (
    alloc_key BIGINT IDENTITY(1,1) PRIMARY KEY,
    date_key INT NULL,
    scenario_key INT NULL,
    from_account_key INT NULL,
    to_department_key INT NULL,
    to_branch_key INT NULL,
    to_product_key INT NULL,
    driver_key INT NULL,
    allocation_rule_id INT NULL,
    amount_allocated DECIMAL(18,2) NULL,
    allocation_text VARCHAR(200) NULL,
    load_date DATETIME DEFAULT GETDATE()
);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_date FOREIGN KEY (date_key) REFERENCES dbo.dim_date(date_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_scenario FOREIGN KEY (scenario_key) REFERENCES dbo.dim_scenario(scenario_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_fromacct FOREIGN KEY (from_account_key) REFERENCES dbo.dim_account(account_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_todept FOREIGN KEY (to_department_key) REFERENCES dbo.dim_department(department_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_tobranch FOREIGN KEY (to_branch_key) REFERENCES dbo.dim_branch(branch_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_toprod FOREIGN KEY (to_product_key) REFERENCES dbo.dim_product(product_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_driver FOREIGN KEY (driver_key) REFERENCES dbo.dim_driver(driver_key);
ALTER TABLE dbo.fact_allocation
    ADD CONSTRAINT fk_factalloc_rule FOREIGN KEY (allocation_rule_id) REFERENCES dbo.allocation_rule(rule_id);

CREATE TABLE dbo.fact_balance (
    balance_key BIGINT IDENTITY(1,1) PRIMARY KEY,
    date_key INT NULL,
    entity_key INT NULL,
    account_key INT NULL,
    branch_key INT NULL,
    product_key INT NULL,
    balance_amount DECIMAL(18,2) NULL,
    load_date DATETIME DEFAULT GETDATE()
);
ALTER TABLE dbo.fact_balance
    ADD CONSTRAINT fk_factbal_date FOREIGN KEY (date_key) REFERENCES dbo.dim_date(date_key);
ALTER TABLE dbo.fact_balance
    ADD CONSTRAINT fk_factbal_entity FOREIGN KEY (entity_key) REFERENCES dbo.dim_entity(entity_key);
ALTER TABLE dbo.fact_balance
    ADD CONSTRAINT fk_factbal_account FOREIGN KEY (account_key) REFERENCES dbo.dim_account(account_key);
ALTER TABLE dbo.fact_balance
    ADD CONSTRAINT fk_factbal_branch FOREIGN KEY (branch_key) REFERENCES dbo.dim_branch(branch_key);
ALTER TABLE dbo.fact_balance
    ADD CONSTRAINT fk_factbal_product FOREIGN KEY (product_key) REFERENCES dbo.dim_product(product_key);

CREATE TABLE dbo.fact_crm_activity (
    crm_activity_key BIGINT IDENTITY(1,1) PRIMARY KEY,
    date_key INT NULL,
    customer_key INT NULL,
    product_key INT NULL,
    transactions INT NULL,
    volume DECIMAL(18,2) NULL,
    revenue_contribution DECIMAL(18,2) NULL,
    load_date DATETIME DEFAULT GETDATE()
);
ALTER TABLE dbo.fact_crm_activity
    ADD CONSTRAINT fk_crm_date FOREIGN KEY (date_key) REFERENCES dbo.dim_date(date_key);
ALTER TABLE dbo.fact_crm_activity
    ADD CONSTRAINT fk_crm_customer FOREIGN KEY (customer_key) REFERENCES dbo.dim_customer(customer_key);
ALTER TABLE dbo.fact_crm_activity
    ADD CONSTRAINT fk_crm_product FOREIGN KEY (product_key) REFERENCES dbo.dim_product(product_key);

-- =====================================================
-- OTHER SUPPORTING TABLES
-- =====================================================

CREATE TABLE dbo.cost_center_map (
    cost_center_code VARCHAR(50) PRIMARY KEY,
    department_key INT NULL,
    account_key INT NULL
);
ALTER TABLE dbo.cost_center_map
    ADD CONSTRAINT fk_costctr_dept FOREIGN KEY (department_key) REFERENCES dbo.dim_department(department_key);
ALTER TABLE dbo.cost_center_map
    ADD CONSTRAINT fk_costctr_account FOREIGN KEY (account_key) REFERENCES dbo.dim_account(account_key);

CREATE TABLE dbo.hr_payroll_integration (
    payroll_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    employee_key INT NULL,
    period_key INT NULL,
    gross_salary DECIMAL(18,2) NULL,
    bonus DECIMAL(18,2) NULL,
    benefits DECIMAL(18,2) NULL
);
ALTER TABLE dbo.hr_payroll_integration
    ADD CONSTRAINT fk_payroll_emp FOREIGN KEY (employee_key) REFERENCES dbo.dim_employee(employee_key);
ALTER TABLE dbo.hr_payroll_integration
    ADD CONSTRAINT fk_payroll_period FOREIGN KEY (period_key) REFERENCES dbo.dim_date(date_key);

CREATE TABLE dbo.customer_profitability (
    profit_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    customer_key INT NULL,
    date_key INT NULL,
    revenue DECIMAL(18,2) NULL,
    expense DECIMAL(18,2) NULL,
    net_income DECIMAL(18,2) NULL
);
ALTER TABLE dbo.customer_profitability
    ADD CONSTRAINT fk_custprof_customer FOREIGN KEY (customer_key) REFERENCES dbo.dim_customer(customer_key);
ALTER TABLE dbo.customer_profitability
    ADD CONSTRAINT fk_custprof_date FOREIGN KEY (date_key) REFERENCES dbo.dim_date(date_key);

CREATE TABLE dbo.customer_scorecard (
    score_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    customer_key INT NULL,
    score_date DATE NULL,
    risk_score DECIMAL(5,2) NULL,
    churn_prob DECIMAL(5,4) NULL,
    segment_key INT NULL
);
ALTER TABLE dbo.customer_scorecard
    ADD CONSTRAINT fk_cscore_customer FOREIGN KEY (customer_key) REFERENCES dbo.dim_customer(customer_key);
ALTER TABLE dbo.customer_scorecard
    ADD CONSTRAINT fk_cscore_segment FOREIGN KEY (segment_key) REFERENCES dbo.dim_customer_segment(segment_key);

CREATE TABLE dbo.audit_log (
    audit_key BIGINT IDENTITY(1,1) PRIMARY KEY,
    table_name VARCHAR(100) NULL,
    record_key VARCHAR(100) NULL,
    action_type VARCHAR(50) NULL,
    user_id INT NULL,
    event_ts DATETIME DEFAULT GETDATE(),
    details VARCHAR(MAX) NULL
);
ALTER TABLE dbo.audit_log
    ADD CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES dbo.app_user(user_id);

-- =====================================================
-- INDEXES & PERFORMANCE (suggested)
-- =====================================================

CREATE INDEX ix_fact_revenue_date_scenario ON dbo.fact_revenue(date_key, scenario_key);
CREATE INDEX ix_fact_expense_date_scenario ON dbo.fact_expense(date_key, scenario_key);
CREATE INDEX ix_fact_pnl_date_dept ON dbo.fact_pnl(date_key, department_key);
CREATE INDEX ix_fact_allocation_date_fromacct ON dbo.fact_allocation(date_key, from_account_key);
CREATE INDEX ix_driver_values_date_driver ON dbo.driver_values(date_key, driver_key);

-- =====================================================
-- SEED: reference data minimal (scenarios, workflow_status, currencies)
-- =====================================================

INSERT INTO dbo.dim_scenario (scenario_key, scenario_name, category) VALUES
(1,'Actual','Actual'),
(2,'Budget','Plan'),
(3,'Forecast','Forecast'),
(4,'Best','Scenario'),
(5,'Worst','Scenario'),
(6,'Balanced','Scenario');

INSERT INTO dbo.workflow_status (status_id, status_name) VALUES
(1,'Draft'),(2,'Submitted'),(3,'UnderReview'),(4,'Approved'),(5,'Rejected'),(6,'Locked');

INSERT INTO dbo.dim_currency (currency_key, currency_code, currency_name, is_base, fx_rate_to_base) VALUES
(1,'USD','US Dollar',1,1.000000),(2,'EUR','Euro',0,1.100000),(3,'UZS','Uzbek Som',0,0.000094);

-- =====================================================
-- NOTES / NEXT STEPS
-- =====================================================
-- 1) Before loading facts, populate dimensions (dim_currency, dim_region, dim_branch, dim_businessunit, dim_product,
--    dim_account, dim_driver, dim_position, dim_department, dim_employee, dim_customer_segment, dim_customer, dim_entity).
-- 2) For circular dependencies (department.manager_emp_key referencing dim_employee), either:
--      - load dim_department with NULL manager_emp_key, load dim_employee, then update dim_department.manager_emp_key; or
--      - use delayed constraint enforcement.
-- 3) Consider adding partitioning to large facts (fact_revenue, fact_expense, fact_balance) by date_key or year for performance.
-- 4) Implement ETL workflows (staging tables -> dim load -> fact load) and data quality checks (row counts, null checks, totals reconciliation).
-- 5) If you want, I will now export a Postgres-compatible .sql file with equivalent DDL (types & syntax adjusted) and provide both files for download.

SET NOCOUNT OFF;
