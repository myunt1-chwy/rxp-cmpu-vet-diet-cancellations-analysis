# Non-D-Distribution

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| channel | order_group | order_status_group | cancel_reason | cancellation_reason_group | block_reason | upload_group | order_lines | percent_of_cohort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CUSTOMER_UPLOAD | C | A | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 27 | 0.04144855006831335 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 10 | 0.015351314840116056 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 11 | 0.01688644632412766 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | S | S | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | S | S | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.01074592038808124 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 68 | 0.10438894091278918 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 15 | 0.023026972260174083 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 5 | 0.007675657420058028 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 239 | 0.36689642467877376 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 4112 | 6.312460662255722 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 19 | 0.029167498196220505 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 682 | 1.0469596720959151 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2235 | 3.4310188667659385 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 234 | 0.3592207672587157 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1306 | 2.0048817181191567 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 58 | 0.08903762607267313 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 864 | 1.3263536021860272 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | Has matching upload | 32 | 0.04912420748837138 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 491 | 0.7537495586496984 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 113 | 0.17346985769331144 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | Has matching upload | 5 | 0.007675657420058028 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 70 | 0.1074592038808124 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 30 | 0.04605394452034817 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 11 | 0.01688644632412766 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 10 | 0.015351314840116056 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 5 | 0.007675657420058028 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 15 | 0.023026972260174083 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 13 | 0.019956709292150872 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 275 | 0.42216115810319155 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 15769 | 24.207488371379007 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 39 | 0.05987012787645262 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 251 | 0.385318002486913 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2622 | 4.02511475107843 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 160 | 0.2456210374418569 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1895 | 2.9090741622019927 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OTHER | Has matching upload | 53 | 0.0813619686526151 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 3601 | 5.528008473925792 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 38 | 0.05833499639244101 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1625 | 2.494588661518859 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 11 | 0.01688644632412766 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 413 | 0.6340093028967931 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | No matching upload | 50 | 0.07675657420058028 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 309 | 0.47435562855958613 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 4980 | 7.6449547903777955 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 11 | 0.01688644632412766 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 456 | 0.7000199567092922 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2884 | 4.42731919988947 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 253 | 0.3883882654549362 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2450 | 3.761072135828434 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | Has matching upload | 66 | 0.10131867794476597 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | No matching upload | 866 | 1.3294238651540504 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 53 | 0.0813619686526151 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 565 | 0.8673492884665571 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 7 | 0.01074592038808124 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 8 | 0.012281051872092845 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 123 | 0.18882117253342748 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE/PET_ID_MISMATCH | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | No matching upload | 78 | 0.11974025575290524 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | [No block reason recorded] | Has matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 254 | 0.38992339693894784 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1995 | 3.062587310603153 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 444 | 0.6815983789011529 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1044 | 1.6026772693081162 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 284 | 0.435977341459296 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 680 | 1.0438894091278919 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OTHER | Has matching upload | 48 | 0.07368631123255708 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OTHER | No matching upload | 415 | 0.6370795658648163 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 34 | 0.05219447045639459 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | No matching upload | 208 | 0.31930734867441396 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 34 | 0.05219447045639459 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | No matching upload | 23 | 0.03530802413226693 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | [No block reason recorded] | Has matching upload | 5 | 0.007675657420058028 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OTHER | Has matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OTHER | No matching upload | 25 | 0.03837828710029014 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | OTHER | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Inventory Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 5 | 0.007675657420058028 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 438 | 0.6723875899970833 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 7 | 0.01074592038808124 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 13 | 0.019956709292150872 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | OTHER | No matching upload | 94 | 0.14430235949709092 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.019956709292150872 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 20 | 0.030702629680232112 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 102 | 0.15658341136918377 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 27 | 0.04144855006831335 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 76 | 0.11666999278488202 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 18 | 0.0276323667122089 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 32 | 0.04912420748837138 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OTHER | Has matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OTHER | No matching upload | 33 | 0.050659338972382985 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.019956709292150872 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PET_ID_MISMATCH | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 10 | 0.015351314840116056 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1883 | 2.8906525843938535 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 143 | 0.2195238022136596 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 23 | 0.03530802413226693 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | OTHER | No matching upload | 444 | 0.6815983789011529 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | OUT_OF_REFILLS | No matching upload | 136 | 0.20877788182557835 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 25 | 0.03837828710029014 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | PET_ID_MISMATCH | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | [No block reason recorded] | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.01074592038808124 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OTHER | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OUT_OF_REFILLS | No matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 85 | 0.13048617614098648 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 18 | 0.0276323667122089 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.004605394452034817 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 18 | 0.0276323667122089 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | OTHER | No matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | OUT_OF_REFILLS | No matching upload | 7 | 0.01074592038808124 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 60 | 0.09210788904069633 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2964 | 4.550129718610399 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 4 | 0.006140525936046423 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 64 | 0.09824841497674276 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 406 | 0.6232633825087118 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 42 | 0.06447552232848744 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 271 | 0.41602063216714513 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OTHER | Has matching upload | 18 | 0.0276323667122089 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OTHER | No matching upload | 748 | 1.148278350040681 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 6 | 0.009210788904069634 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS | No matching upload | 256 | 0.39299365990697105 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 58 | 0.08903762607267313 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PET_ID_MISMATCH | No matching upload | 8 | 0.012281051872092845 |
| CUSTOMER_UPLOAD | X | X | Reseller | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 7 | 0.01074592038808124 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 69 | 0.10592407239680078 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 11 | 0.01688644632412766 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 36 | 0.0552647334244178 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 36 | 0.0552647334244178 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 2 | 0.0030702629680232113 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 20 | 0.030702629680232112 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 9 | 0.01381618335610445 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0015351314840116057 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 2 | 0.0030702629680232113 |
