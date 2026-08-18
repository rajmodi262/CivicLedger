-- =====================================================================
-- CivicLedger: Municipal Budget & General Ledger SQL Reconciliation
-- Target Engines: DuckDB & PostgreSQL
-- Core Patterns: Common Table Expressions (CTEs), Window Functions, Self-Joins
-- =====================================================================

-- 1. Fund Balance Zero-Sum Integrity & Trial Balance Reconciliation
WITH Legacy_Fund_Totals AS (
    SELECT 
        fund_code,
        fund_name,
        fiscal_year,
        SUM(adopted_budget) AS legacy_adopted_total,
        SUM(revised_budget) AS legacy_revised_total,
        SUM(actual_expenditure) AS legacy_actual_total,
        COUNT(*) AS legacy_line_item_count
    FROM legacy_budget_extracts
    GROUP BY fund_code, fund_name, fiscal_year
),
Migrated_Fund_Totals AS (
    SELECT 
        f.fund_code,
        f.fund_name,
        gl.fiscal_year,
        SUM(gl.budget_amount) AS migrated_adopted_total,
        SUM(gl.revised_amount) AS migrated_revised_total,
        SUM(gl.actual_amount) AS migrated_actual_total,
        COUNT(*) AS migrated_line_item_count
    FROM gl_entry_staging gl
    JOIN dim_chart_of_accounts coa ON gl.coa_id = coa.id
    JOIN dim_fund f ON coa.fund_id = f.id
    GROUP BY f.fund_code, f.fund_name, gl.fiscal_year
)
SELECT 
    l.fund_code,
    l.fund_name,
    l.fiscal_year,
    l.legacy_line_item_count,
    m.migrated_line_item_count,
    l.legacy_adopted_total,
    m.migrated_adopted_total,
    ROUND(ABS(l.legacy_adopted_total - m.migrated_adopted_total), 2) AS adopted_variance,
    l.legacy_actual_total,
    m.migrated_actual_total,
    ROUND(ABS(l.legacy_actual_total - m.migrated_actual_total), 2) AS actual_variance,
    CASE 
        WHEN l.legacy_line_item_count = m.migrated_line_item_count 
         AND ABS(l.legacy_adopted_total - m.migrated_adopted_total) < 0.01
         AND ABS(l.legacy_actual_total - m.migrated_actual_total) < 0.01
        THEN 'RECONCILED'
        ELSE 'VARIANCE_FLAGGED'
    END AS reconciliation_status
FROM Legacy_Fund_Totals l
FULL OUTER JOIN Migrated_Fund_Totals m 
    ON l.fund_code = m.fund_code 
   AND l.fiscal_year = m.fiscal_year
ORDER BY adopted_variance DESC, l.fund_code;

-- 2. Multi-Year Departmental Budget Variance & Expenditure Run-Rate Analysis
WITH Department_Fiscal_Series AS (
    SELECT 
        d.department_code,
        d.department_name,
        gl.fiscal_year,
        SUM(gl.budget_amount) AS total_budget,
        SUM(gl.actual_amount) AS total_actual,
        -- Window function: Year-over-Year (YoY) Budget Growth
        LAG(SUM(gl.budget_amount), 1) OVER (
            PARTITION BY d.department_code 
            ORDER BY gl.fiscal_year
        ) AS prior_year_budget,
        -- Window function: Department Share of Total Municipal General Fund
        SUM(SUM(gl.budget_amount)) OVER (
            PARTITION BY gl.fiscal_year
        ) AS municipal_total_budget
    FROM gl_entry_staging gl
    JOIN dim_chart_of_accounts coa ON gl.coa_id = coa.id
    JOIN dim_department d ON coa.department_id = d.id
    GROUP BY d.department_code, d.department_name, gl.fiscal_year
)
SELECT 
    department_code,
    department_name,
    fiscal_year,
    total_budget,
    total_actual,
    ROUND(((total_budget - prior_year_budget) / NULLIF(prior_year_budget, 0)) * 100, 2) AS yoy_budget_growth_pct,
    ROUND((total_budget / NULLIF(municipal_total_budget, 0)) * 100, 2) AS pct_of_municipal_budget,
    ROUND((total_actual / NULLIF(total_budget, 0)) * 100, 2) AS budget_utilization_pct
FROM Department_Fiscal_Series
ORDER BY fiscal_year DESC, total_budget DESC;

-- 3. Unbalanced Fund Entry Detection (GASB Compliance Check)
SELECT 
    gl.batch_id,
    f.fund_code,
    f.fund_name,
    SUM(CASE WHEN coa.account_type IN ('REVENUE', 'LIABILITY', 'FUND_BALANCE') THEN gl.actual_amount ELSE 0 END) AS total_credits,
    SUM(CASE WHEN coa.account_type IN ('EXPENDITURE', 'ASSET') THEN gl.actual_amount ELSE 0 END) AS total_debits,
    ROUND(SUM(CASE WHEN coa.account_type IN ('REVENUE', 'LIABILITY', 'FUND_BALANCE') THEN gl.actual_amount ELSE 0 END) -
          SUM(CASE WHEN coa.account_type IN ('EXPENDITURE', 'ASSET') THEN gl.actual_amount ELSE 0 END), 2) AS fund_imbalance
FROM gl_entry_staging gl
JOIN dim_chart_of_accounts coa ON gl.coa_id = coa.id
JOIN dim_fund f ON coa.fund_id = f.id
GROUP BY gl.batch_id, f.fund_code, f.fund_name
HAVING ABS(SUM(CASE WHEN coa.account_type IN ('REVENUE', 'LIABILITY', 'FUND_BALANCE') THEN gl.actual_amount ELSE 0 END) -
           SUM(CASE WHEN coa.account_type IN ('EXPENDITURE', 'ASSET') THEN gl.actual_amount ELSE 0 END)) > 0.001;
