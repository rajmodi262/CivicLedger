-- name: control_totals
-- R1. Every source file must reconcile to the warehouse to the cent:
--     source total = loaded total + rejected total, and row counts likewise.
WITH src AS (
    SELECT source_file, measure, count(*) AS source_rows, round(sum(coalesce(amount, 0)), 2) AS source_amount
    FROM source_all GROUP BY source_file, measure
), loaded AS (
    SELECT source_file, measure, count(*) AS loaded_rows, round(sum(amount), 2) AS loaded_amount
    FROM fact_appropriation GROUP BY source_file, measure
), rejected AS (
    SELECT source_file, measure, count(*) AS rejected_rows, round(sum(coalesce(amount, 0)), 2) AS rejected_amount
    FROM rejected_rows GROUP BY source_file, measure
), unvalued AS (
    SELECT source_file, measure, count(*) AS unvalued_rows
    FROM canonical WHERE amount IS NULL GROUP BY source_file, measure
)
SELECT s.source_file, s.measure, s.source_rows,
       coalesce(l.loaded_rows, 0) AS loaded_rows, coalesce(r.rejected_rows, 0) AS rejected_rows,
       coalesce(u.unvalued_rows, 0) AS unvalued_rows,
       s.source_amount, coalesce(l.loaded_amount, 0) AS loaded_amount, coalesce(r.rejected_amount, 0) AS rejected_amount,
       round(s.source_amount - coalesce(l.loaded_amount, 0) - coalesce(r.rejected_amount, 0), 2) AS variance,
       CASE WHEN s.source_rows = coalesce(l.loaded_rows, 0) + coalesce(r.rejected_rows, 0) + coalesce(u.unvalued_rows, 0)
             AND abs(s.source_amount - coalesce(l.loaded_amount, 0) - coalesce(r.rejected_amount, 0)) < 0.005
            THEN 'RECONCILED' ELSE 'BREAK' END AS status
FROM src s
LEFT JOIN loaded l USING (source_file, measure)
LEFT JOIN rejected r USING (source_file, measure)
LEFT JOIN unvalued u USING (source_file, measure)
ORDER BY s.source_file, s.measure;

-- name: prior_year_by_type
-- R2. Cross-file check, summary: the "prior appropriation" column of year Y's proposed budget
--     against what the council adopted for year Y-1, by fund type. Local funds are expected to
--     match; grant funds are reissued and carried over, so they are reported, not expected to match.
WITH adopted AS (
    SELECT x.fiscal_year, f.fund_type, sum(x.amount) AS adopted_amount
    FROM fact_appropriation x JOIN dim_fund f USING (fund_code)
    WHERE x.stage = 'adopted' AND x.measure = 'ordinance' GROUP BY ALL
), restated AS (
    SELECT x.fiscal_year - 1 AS fiscal_year, f.fund_type, sum(x.amount) AS restated_amount
    FROM fact_appropriation x JOIN dim_fund f USING (fund_code)
    WHERE x.stage = 'proposed' AND x.measure = 'prior_appropriation' GROUP BY ALL
)
SELECT fiscal_year, fund_type,
       round(adopted_amount, 2) AS adopted_amount, round(restated_amount, 2) AS restated_next_year,
       round(restated_amount - adopted_amount, 2) AS difference,
       CASE WHEN abs(restated_amount - adopted_amount) < 0.5 THEN 'MATCH' ELSE 'DIFFERENT' END AS status
FROM adopted JOIN restated USING (fiscal_year, fund_type)
ORDER BY fiscal_year, fund_type;

-- name: prior_year_check
-- R2 detail: the same check fund by fund, so every difference points at a specific fund.
WITH adopted AS (
    SELECT fiscal_year, fund_code, sum(amount) AS adopted_amount
    FROM fact_appropriation WHERE stage = 'adopted' AND measure = 'ordinance'
    GROUP BY fiscal_year, fund_code
), restated AS (
    SELECT fiscal_year - 1 AS fiscal_year, fund_code, sum(amount) AS restated_amount
    FROM fact_appropriation WHERE stage = 'proposed' AND measure = 'prior_appropriation'
    GROUP BY fiscal_year, fund_code
)
SELECT coalesce(a.fiscal_year, r.fiscal_year) AS fiscal_year,
       coalesce(a.fund_code, r.fund_code) AS fund_code,
       f.fund_description, f.fund_type,
       round(coalesce(a.adopted_amount, 0), 2) AS adopted_amount,
       round(coalesce(r.restated_amount, 0), 2) AS restated_next_year,
       round(coalesce(r.restated_amount, 0) - coalesce(a.adopted_amount, 0), 2) AS difference,
       CASE WHEN abs(coalesce(r.restated_amount, 0) - coalesce(a.adopted_amount, 0)) < 0.5 THEN 'MATCH'
            WHEN a.adopted_amount IS NULL THEN 'ONLY IN RESTATEMENT'
            WHEN r.restated_amount IS NULL THEN 'NOT RESTATED'
            ELSE 'DIFFERENT' END AS status
FROM adopted a
FULL OUTER JOIN restated r ON a.fiscal_year = r.fiscal_year AND a.fund_code = r.fund_code
LEFT JOIN dim_fund f ON f.fund_code = coalesce(a.fund_code, r.fund_code)
WHERE coalesce(a.fiscal_year, r.fiscal_year) BETWEEN
      (SELECT min(fiscal_year) FROM fact_appropriation WHERE stage = 'adopted')
  AND (SELECT max(fiscal_year) - 1 FROM fact_appropriation WHERE stage = 'proposed')
ORDER BY fiscal_year, fund_code;

-- name: embedded_totals
-- R4. Some files carry the publisher's own subtotal rows ("LOCAL Total", "Grand Total").
--     They are kept out of the warehouse (VR-09) and used as an independent control:
--     each must equal the sum of the detail lines we loaded.
WITH published AS (
    SELECT source_file, measure, source_row,
           CASE WHEN fund_type = 'GRAND TOTAL' THEN 'ALL' ELSE trim(replace(fund_type, 'TOTAL', '')) END AS scope,
           amount AS published_total
    FROM rejected_rows WHERE fund_type LIKE '%TOTAL' AND fund_code IS NULL
), detail AS (
    SELECT source_file, measure, fund_type AS scope, sum(amount) AS loaded_total
    FROM canonical WHERE amount IS NOT NULL GROUP BY ALL
    UNION ALL
    SELECT source_file, measure, 'ALL', sum(amount)
    FROM canonical WHERE amount IS NOT NULL GROUP BY ALL
)
SELECT p.source_file, p.source_row, p.measure, p.scope,
       round(p.published_total, 2) AS published_total, round(d.loaded_total, 2) AS loaded_total,
       round(d.loaded_total - p.published_total, 2) AS difference,
       CASE WHEN abs(d.loaded_total - p.published_total) < 0.5 THEN 'MATCH' ELSE 'DIFFERENT' END AS status
FROM published p
LEFT JOIN detail d USING (source_file, measure, scope)
ORDER BY p.source_file, p.source_row, p.measure;

-- name: council_changes
-- R3. Budget process variance: the Mayor's recommendation vs the ordinance the council adopted,
--     per year and department.
WITH rec AS (
    SELECT fiscal_year, department_code, sum(amount) AS recommended
    FROM fact_appropriation WHERE stage = 'proposed' AND measure = 'recommendation'
    GROUP BY fiscal_year, department_code
), ord AS (
    SELECT fiscal_year, department_code, sum(amount) AS adopted
    FROM fact_appropriation WHERE stage = 'adopted' AND measure = 'ordinance'
    GROUP BY fiscal_year, department_code
)
SELECT coalesce(r.fiscal_year, o.fiscal_year) AS fiscal_year,
       coalesce(r.department_code, o.department_code) AS department_code,
       d.department_description,
       round(coalesce(r.recommended, 0), 2) AS recommended,
       round(coalesce(o.adopted, 0), 2) AS adopted,
       round(coalesce(o.adopted, 0) - coalesce(r.recommended, 0), 2) AS change
FROM rec r
FULL OUTER JOIN ord o ON r.fiscal_year = o.fiscal_year AND r.department_code = o.department_code
LEFT JOIN dim_department d ON d.department_code = coalesce(r.department_code, o.department_code)
WHERE coalesce(r.fiscal_year, o.fiscal_year) IN (SELECT fiscal_year FROM rec)
  AND coalesce(r.fiscal_year, o.fiscal_year) IN (SELECT fiscal_year FROM ord)
ORDER BY fiscal_year, abs(change) DESC;
