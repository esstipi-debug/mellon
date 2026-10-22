-- ==============================================================================================
-- audit_assertions_sap.sql
-- ==============================================================================================
-- Production-Ready ANSI SQL Audit Assertion Suite for SAP S/4HANA Core Ledgers.
-- Target Tables: s4_mseg, s4_mkpf, s4_ekpo, s4_eket, s4_acdoca
-- Primary Key Composite Join: MBLNR (Material Document) + MJAHR (Fiscal Year) + ZEILE (Line Item)
-- Standard: Zero-Trust Telemetry Parity, Cryptographic Negative Controls.
-- Parameter: :deployment_go_live_date (ISO-8601 Date String, e.g. '2026-11-01')
-- ==============================================================================================

-- ----------------------------------------------------------------------------------------------
-- ASSERTION 1: Negative Control - Bypassed Inventory Write-Offs & Unregistered Scrap
-- Movement Types:
--   701 / 702 : Physical inventory difference in warehouse (Gain / Loss)
--   551 / 552 : Scrap / Destruction of material (Scrapping from unrestricted stock)
-- Rule: Every manual write-off after go-live MUST have a corresponding 1:1 sensor-verified
--       telemetry event (scale weight parity <= 3% + SHA-256 photo hash) in fde_telemetry_scrap_events.
-- Falsification: ANY row returned demonstrates an unverified inventory manipulation.
-- ----------------------------------------------------------------------------------------------
WITH sap_inventory_adjustments AS (
    SELECT 
        mseg.mandt,
        mseg.mblnr,
        mseg.mjahr,
        mseg.zeile,
        mseg.bwart AS movement_type,
        mseg.matnr AS material_number,
        mseg.werks AS plant,
        mseg.lgort AS storage_location,
        mseg.menge AS quantity,
        mseg.meins AS base_uom,
        mseg.dmbtr AS amount_in_local_currency,
        mseg.waers AS currency,
        mseg.erfnam AS created_by_user,
        mkpf.cpudt AS posting_date,
        mkpf.cputm AS posting_time
    FROM s4_mseg mseg
    INNER JOIN s4_mkpf mkpf 
        ON mseg.mandt = mkpf.mandt
       AND mseg.mblnr = mkpf.mblnr 
       AND mseg.mjahr = mkpf.mjahr
    WHERE mseg.bwart IN ('701', '702', '551', '552')
      AND mkpf.cpudt >= :deployment_go_live_date
)
SELECT 
    adj.mandt,
    adj.mblnr AS sap_material_document,
    adj.mjahr AS sap_fiscal_year,
    adj.zeile AS sap_document_line,
    adj.movement_type,
    adj.material_number,
    adj.plant,
    adj.quantity,
    adj.base_uom,
    adj.amount_in_local_currency,
    adj.created_by_user,
    adj.posting_date,
    'SECURITY_ALERT: Manual write-off executed without valid Gemba sensor proof' AS audit_violation_reason
FROM sap_inventory_adjustments adj
LEFT JOIN fde_telemetry_scrap_events tel 
    ON adj.mandt = tel.sap_mandt_reference
   AND adj.mblnr = tel.sap_mblnr_reference
   AND adj.mjahr = tel.sap_mjahr_reference
   AND adj.zeile = tel.sap_zeile_reference
WHERE tel.transaction_id IS NULL
   OR tel.is_cryptographically_verified = FALSE
   OR tel.scale_weight_divergence_pct > 0.0300;
-- EXPECTED RESULT: 0 rows.


-- ----------------------------------------------------------------------------------------------
-- ASSERTION 2: Negative Control - Phantom Inventory & Unblinded Recount Closures
-- Rule: No inventory adjustment (701/702) can be approved if:
--       (a) The counting user is identical to the posting user (Segregation of Duties breach).
--       (b) The count confirmation lacks a valid blind_token_hash generated before counting.
-- ----------------------------------------------------------------------------------------------
WITH cycle_count_postings AS (
    SELECT 
        mseg.mandt,
        mseg.mblnr,
        mseg.mjahr,
        mseg.zeile,
        mseg.matnr,
        mseg.werks,
        mseg.lgort,
        mseg.menge,
        mseg.erfnam AS posting_user,
        mkpf.cpudt AS posting_date,
        count_log.counter_user_badge,
        count_log.blind_token_hash,
        count_log.is_system_stock_revealed_on_rf
    FROM s4_mseg mseg
    INNER JOIN s4_mkpf mkpf 
        ON mseg.mandt = mkpf.mandt AND mseg.mblnr = mkpf.mblnr AND mseg.mjahr = mkpf.mjahr
    LEFT JOIN fde_blind_cycle_counts count_log
        ON mseg.mandt = count_log.sap_mandt_ref
       AND mseg.mblnr = count_log.sap_mblnr_ref
       AND mseg.mjahr = count_log.sap_mjahr_ref
       AND mseg.zeile = count_log.sap_zeile_ref
    WHERE mseg.bwart IN ('701', '702')
      AND mkpf.cpudt >= :deployment_go_live_date
)
SELECT 
    mandt,
    mblnr,
    mjahr,
    zeile,
    matnr,
    werks,
    menge,
    posting_user,
    counter_user_badge,
    posting_date,
    CASE 
        WHEN posting_user = counter_user_badge THEN 'SEGREGATION_OF_DUTIES_VIOLATION: Poster equals Counter'
        WHEN blind_token_hash IS NULL THEN 'INTEGRITY_BREACH: Missing blind verification token'
        WHEN is_system_stock_revealed_on_rf = TRUE THEN 'GOODHART_VIOLATION: System stock was displayed to picker'
        ELSE 'UNKNOWN_ANOMALY'
    END AS audit_violation_reason
FROM cycle_count_postings
WHERE posting_user = counter_user_badge
   OR blind_token_hash IS NULL
   OR is_system_stock_revealed_on_rf = TRUE;
-- EXPECTED RESULT: 0 rows.


-- ----------------------------------------------------------------------------------------------
-- ASSERTION 3: Negative Control - Unapproved MOQ Forward-Buying Violating Working Capital
-- Table: s4_ekpo (Purchase Order Item), s4_eket (Schedule Lines), s4_mara (Material Master)
-- Rule: If PO coverage > 90 days and net carrying cost > volume discount, the order MUST have
--       a CFO cryptographic signature in fde_governance_approvals.
-- ----------------------------------------------------------------------------------------------
WITH moq_order_eval AS (
    SELECT 
        po_item.ebeln AS purchase_order,
        po_item.ebelp AS po_item_num,
        po_item.matnr AS material_number,
        po_item.werks AS plant,
        po_item.netpr AS unit_price,
        po_item.menge AS ordered_quantity,
        sched.eindt AS delivery_date,
        COALESCE(mara.plifz, 30) AS vendor_lead_time_days,
        COALESCE(forecast.daily_consumption_rate, 1.0) AS daily_demand_rate,
        (po_item.menge / NULLIF(forecast.daily_consumption_rate, 0)) AS calculated_coverage_days,
        -- Net economic balance: (Carrying Cost - Price Discount)
        (
            po_item.netpr * (po_item.menge / 2.0) * ( (po_item.menge / NULLIF(forecast.daily_consumption_rate, 0)) / 365.0 ) * 0.2450
            - (po_item.netpr * 0.03 * po_item.menge)
        ) AS net_working_capital_destruction_usd
    FROM s4_ekpo po_item
    INNER JOIN s4_eket sched
        ON po_item.mandt = sched.mandt
       AND po_item.ebeln = sched.ebeln
       AND po_item.ebelp = sched.ebelp
    LEFT JOIN s4_mara mara
        ON po_item.mandt = mara.mandt AND po_item.matnr = mara.matnr
    LEFT JOIN fde_demand_forecast_baselines forecast
        ON po_item.matnr = forecast.matnr AND po_item.werks = forecast.werks
    WHERE po_item.aedat >= :deployment_go_live_date
)
SELECT 
    ord.purchase_order,
    ord.po_item_num,
    ord.material_number,
    ord.plant,
    ord.ordered_quantity,
    ord.calculated_coverage_days,
    ord.net_working_capital_destruction_usd,
    'GOVERNANCE_BYPASS: Unapproved PO with coverage > 90 days and positive cash destruction' AS audit_violation_reason
FROM moq_order_eval ord
LEFT JOIN fde_governance_approvals gov 
    ON ord.purchase_order = gov.ebeln_ref
   AND ord.po_item_num = gov.ebelp_ref
   AND gov.approval_level = 'CFO_EXECUTIVE_RED_LANE'
   AND gov.digital_signature_verified = TRUE
WHERE ord.calculated_coverage_days > 90.0
  AND ord.net_working_capital_destruction_usd > 50000.00
  AND gov.approval_id IS NULL;
-- EXPECTED RESULT: 0 rows.


-- ----------------------------------------------------------------------------------------------
-- ASSERTION 4: Subledger Reconciliation - Parity between MM (MSEG) and FI (ACDOCA)
-- Table: s4_acdoca (Universal Journal Entry)
-- Rule: Every dollar of inventory loss posted in logistics (MSEG) must match the exact 
--       reconciliation credit/debit on the inventory write-down account (e.g. RACCT '00501000').
-- ----------------------------------------------------------------------------------------------
WITH logistics_scrap_totals AS (
    SELECT 
        mseg.mandt,
        mseg.mblnr,
        mseg.mjahr,
        SUM(mseg.dmbtr) AS total_logistics_loss_local
    FROM s4_mseg mseg
    INNER JOIN s4_mkpf mkpf 
        ON mseg.mandt = mkpf.mandt AND mseg.mblnr = mkpf.mblnr AND mseg.mjahr = mkpf.mjahr
    WHERE mseg.bwart IN ('551', '702')
      AND mkpf.cpudt >= :deployment_go_live_date
    GROUP BY mseg.mandt, mseg.mblnr, mseg.mjahr
),
financial_gl_totals AS (
    SELECT 
        acdoca.mandt,
        acdoca.awref AS mblnr,
        acdoca.gjahr AS mjahr,
        SUM(acdoca.hsl) AS total_financial_loss_local
    FROM s4_acdoca acdoca
    WHERE acdoca.racct IN ('00501000', '00502000') -- Inventory write-down accounts
      AND acdoca.budat >= :deployment_go_live_date
    GROUP BY acdoca.mandt, acdoca.awref, acdoca.gjahr
)
SELECT 
    log.mandt,
    log.mblnr AS material_doc_reference,
    log.mjahr AS fiscal_year,
    log.total_logistics_loss_local,
    COALESCE(gl.total_financial_loss_local, 0.0) AS total_financial_loss_local,
    ABS(log.total_logistics_loss_local - COALESCE(gl.total_financial_loss_local, 0.0)) AS reconciliation_drift_usd,
    'LEDGER_DESYNCHRONIZATION: Logistics write-off diverges from FI Universal Journal' AS audit_violation_reason
FROM logistics_scrap_totals log
LEFT JOIN financial_gl_totals gl
    ON log.mandt = gl.mandt
   AND log.mblnr = gl.mblnr
   AND log.mjahr = gl.mjahr
WHERE ABS(log.total_logistics_loss_local - COALESCE(gl.total_financial_loss_local, 0.0)) > 0.01;
-- EXPECTED RESULT: 0 rows.
