-- Target schema: a chart-of-accounts dimension model over every year and stage.
-- Loaded from the validated canonical rows (table "canonical" registered by civicledger/warehouse.py).

CREATE OR REPLACE TABLE dim_fund AS
SELECT fund_code,
       arg_max(fund_description, fiscal_year) AS fund_description,   -- latest name wins; history in VR-08
       arg_max(fund_type, fiscal_year)        AS fund_type,
       min(fiscal_year) AS first_year, max(fiscal_year) AS last_year
FROM canonical GROUP BY fund_code;

CREATE OR REPLACE TABLE dim_department AS
SELECT department_code,
       arg_max(department_description, fiscal_year) AS department_description,
       min(fiscal_year) AS first_year, max(fiscal_year) AS last_year
FROM canonical GROUP BY department_code;

CREATE OR REPLACE TABLE dim_account AS
SELECT account_code,
       arg_max(account_description, fiscal_year) AS account_description,
       min(fiscal_year) AS first_year, max(fiscal_year) AS last_year
FROM canonical GROUP BY account_code;

CREATE OR REPLACE TABLE dim_coa AS
SELECT DISTINCT
       fund_code || '-' || department_code || '-' || coalesce(authority_code, '0000') || '-' || account_code AS coa_key,
       fund_code, department_code, coalesce(authority_code, '0000') AS authority_code, account_code
FROM canonical;

CREATE OR REPLACE TABLE fact_appropriation AS
SELECT fiscal_year, stage, measure,
       fund_code || '-' || department_code || '-' || coalesce(authority_code, '0000') || '-' || account_code AS coa_key,
       fund_code, department_code, account_code,
       amount, source_file, source_row
FROM canonical
WHERE amount IS NOT NULL;
