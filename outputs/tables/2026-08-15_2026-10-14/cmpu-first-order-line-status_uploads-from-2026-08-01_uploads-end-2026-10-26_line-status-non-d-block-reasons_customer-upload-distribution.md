# Customer-Upload-Distribution

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| channel | order_group | order_status_group | cancel_reason | cancellation_reason_group | block_reason | upload_group | order_lines | percent_of_cohort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CUSTOMER_UPLOAD | C | A | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 27 | 0.028400126222783213 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 10 | 0.010518565267697486 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 24949 | 26.24276848637846 |
| CUSTOMER_UPLOAD | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 4980 | 5.238245503313348 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 11 | 0.011570421794467234 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | S | S | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | S | S | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.00736299568738824 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 68 | 0.07152624382034291 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 15 | 0.015777847901546228 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 5 | 0.005259282633848743 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 239 | 0.25139370989796994 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 4112 | 4.325234038077206 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 19 | 0.019985274008625223 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 682 | 0.7173661512569686 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2235 | 2.350899337330388 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 234 | 0.24613442726412119 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1306 | 1.3737246239612917 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 58 | 0.06100767855264542 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 864 | 0.9088040391290628 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | Has matching upload | 32 | 0.033659408856631955 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 491 | 0.5164615546439466 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 113 | 0.1188597875249816 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | Has matching upload | 5 | 0.005259282633848743 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 70 | 0.07362995687388241 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 30 | 0.031555695803092455 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 11 | 0.011570421794467234 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 10 | 0.010518565267697486 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 5 | 0.005259282633848743 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 15 | 0.015777847901546228 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 13 | 0.013674134848006732 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 275 | 0.28926054486168085 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 15769 | 16.586725570632165 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 39 | 0.041022404544020195 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 251 | 0.2640159882192069 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2622 | 2.7579678131902807 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 160 | 0.16829704428315978 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1895 | 1.9932681182286736 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OTHER | Has matching upload | 53 | 0.05574839591879668 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 3601 | 3.787735352897865 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 38 | 0.039970548017250446 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1625 | 1.7092668560008415 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 11 | 0.011570421794467234 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 413 | 0.43441674555590615 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | No matching upload | 50 | 0.05259282633848743 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 309 | 0.3250236667718523 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 4980 | 5.238245503313348 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 11 | 0.011570421794467234 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 456 | 0.47964657620700535 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2884 | 3.033554223203955 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 253 | 0.2661197012727464 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2450 | 2.577048490585884 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | Has matching upload | 66 | 0.06942253076680341 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | No matching upload | 866 | 0.9109077521826023 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 53 | 0.05574839591879668 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 565 | 0.5942989376249079 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 7 | 0.00736299568738824 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 8 | 0.008414852214157989 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 123 | 0.1293783527926791 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE/PET_ID_MISMATCH | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | No matching upload | 78 | 0.08204480908804039 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | [No block reason recorded] | Has matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 254 | 0.2671715577995161 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1995 | 2.0984537709056483 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 444 | 0.4670242978857684 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1044 | 1.0981382139476175 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 284 | 0.2987272536026086 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 680 | 0.715262438203429 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OTHER | Has matching upload | 48 | 0.050489113284947935 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OTHER | No matching upload | 415 | 0.43652045860944566 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 34 | 0.035763121910171454 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | No matching upload | 208 | 0.2187861575681077 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 34 | 0.035763121910171454 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | No matching upload | 23 | 0.024192700115704218 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | [No block reason recorded] | Has matching upload | 5 | 0.005259282633848743 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OTHER | Has matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OTHER | No matching upload | 25 | 0.026296413169243714 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | OTHER | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Inventory Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 5 | 0.005259282633848743 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 438 | 0.4607131587251499 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 7 | 0.00736299568738824 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 13 | 0.013674134848006732 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | OTHER | No matching upload | 94 | 0.09887451351635637 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.013674134848006732 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 20 | 0.021037130535394973 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 102 | 0.10728936573051435 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 27 | 0.028400126222783213 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 76 | 0.07994109603450089 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 18 | 0.018933417481855473 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 32 | 0.033659408856631955 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OTHER | Has matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OTHER | No matching upload | 33 | 0.034711265383401704 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.013674134848006732 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PET_ID_MISMATCH | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 10 | 0.010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1883 | 1.9806458399074367 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 143 | 0.15041548332807406 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 23 | 0.024192700115704218 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | OTHER | No matching upload | 444 | 0.4670242978857684 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | OUT_OF_REFILLS | No matching upload | 136 | 0.14305248764068582 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 25 | 0.026296413169243714 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | PET_ID_MISMATCH | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | [No block reason recorded] | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.00736299568738824 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OTHER | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OUT_OF_REFILLS | No matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 85 | 0.08940780477542863 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 18 | 0.018933417481855473 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.003155569580309246 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 18 | 0.018933417481855473 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | OTHER | No matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | OUT_OF_REFILLS | No matching upload | 7 | 0.00736299568738824 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 60 | 0.06311139160618491 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2964 | 3.117702745345535 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 4 | 0.004207426107078994 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 64 | 0.06731881771326391 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 406 | 0.4270537498685179 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 42 | 0.044177974124329444 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 271 | 0.2850531187546019 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OTHER | Has matching upload | 18 | 0.018933417481855473 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OTHER | No matching upload | 748 | 0.786788682023772 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 6 | 0.006311139160618492 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS | No matching upload | 256 | 0.26927527085305564 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 58 | 0.06100767855264542 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PET_ID_MISMATCH | No matching upload | 8 | 0.008414852214157989 |
| CUSTOMER_UPLOAD | X | X | Reseller | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 7 | 0.00736299568738824 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 69 | 0.07257810034711265 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 11 | 0.011570421794467234 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 36 | 0.037866834963710946 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 36 | 0.037866834963710946 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 2 | 0.002103713053539497 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 20 | 0.021037130535394973 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 9 | 0.009466708740927737 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0010518565267697486 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 2 | 0.002103713053539497 |
