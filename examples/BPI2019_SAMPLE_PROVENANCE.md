# BPI Challenge 2019 Sample Provenance (`bpi2019_sample.csv`)

## Source Corpus

- **Dataset:** BPI Challenge 2019 (4TU.ResearchData, van Dongen 2019)
- **DOI:** `10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1`
- **License:** CC BY 4.0
- **Full corpus scale:** 251,734 purchase order item cases / 1,595,923 events
- **This file:** A deterministic **200-item sample** extracted from the full corpus for offline mechanism verification (< 200 KB).

## Deterministic Extraction Rule

Extracted from `eventos.csv` (schema: `caso,n,Cumulative net worth (EUR),User,concept:name,org:resource,time:timestamp,extra`) with zero randomness:

1. Filter events to `concept:name` in `{"Create Purchase Order Item", "Record Goods Receipt"}`.
2. Retain cases with exactly 1 `Create Purchase Order Item` event, sorted lexicographically by `caso`:
   - Take the first **150 cases** having `>= 2` `Record Goods Receipt` events (12,678 eligible in full corpus). This naturally includes the 5 documented snapshot-repetition cases whose PO item values are `76210.0`, `1668264.0`, `17414.0`, `457836.0`, and `405009.0`.
   - Take the first **50 cases** having `== 1` `Record Goods Receipt` event (221,801 eligible in full corpus).
3. Merge the 200 selected cases sorted lexicographically by `caso`, and sort rows within each case by `int(n)`.
4. Emit columns `caso,n,concept:name,Cumulative net worth (EUR),po_item_value_eur,time:timestamp,User`, keeping `Cumulative net worth (EUR)` untouched from source and populating `po_item_value_eur` from that case's `Create Purchase Order Item` row.

## Sample Counts & Integrity

- **File:** `examples/bpi2019_sample.csv`
- **Size:** 114,115 bytes
- **SHA-256:** `2f0d0e8a2f73d7e8b17c7038e7695e4b6fd6c281993222ad0499a4e59b830ee8`
- **Cases:** 200 (`2000000000_00001` through `4507000367_00020`; 150 multi-receipt, 50 single-receipt)
- **Event rows:** 1,233 (`200` `Create Purchase Order Item` + `1,033` `Record Goods Receipt`)
- **Measured naive `SUM("Cumulative net worth (EUR)")` on `Record Goods Receipt`:** `1,268,265,240.0` EUR vs actual `po_item_value_eur` total `34,804,238.0` EUR (`36.44x` inflation; `148` false over-receipt cases where naive `SUM > po_item_value_eur * 1.01`).
