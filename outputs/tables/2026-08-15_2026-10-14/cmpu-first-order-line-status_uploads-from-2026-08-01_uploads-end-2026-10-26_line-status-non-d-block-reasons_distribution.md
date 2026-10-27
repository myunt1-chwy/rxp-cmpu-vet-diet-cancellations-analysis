# Distribution

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| channel | order_group | order_status_group | cancel_reason | cancellation_reason_group | block_reason | upload_group | order_lines | percent_of_cohort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CLINIC_EMAIL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 5 | 0.004830311168645484 |
| CLINIC_EMAIL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 104 | 0.10047047230782608 |
| CLINIC_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 5 | 0.004830311168645484 |
| CLINIC_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CLINIC_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2 | 0.0019321244674581936 |
| CLINIC_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.0028981867011872906 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 2 | 0.0019321244674581936 |
| CLINIC_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CLINIC_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| CLINIC_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 5 | 0.004830311168645484 |
| CLINIC_EMAIL | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 2 | 0.0019321244674581936 |
| CLINIC_EMAIL | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Customer Request | With cancellation reason | OTHER | No matching upload | 2 | 0.0019321244674581936 |
| CLINIC_EMAIL | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CLINIC_EMAIL | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 440 | 0.4250673828408026 |
| CUSTOMER_EMAIL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 1976 | 1.9089389738486953 |
| CUSTOMER_EMAIL | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | S | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | S | C | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_EMAIL | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 8 | 0.007728497869832774 |
| CUSTOMER_EMAIL | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 5 | 0.004830311168645484 |
| CUSTOMER_EMAIL | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_EMAIL | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_EMAIL | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Payment Declined | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Payment Declined | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Payment Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_EMAIL | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | C | A | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 27 | 0.026083680310685614 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | C | C | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 10 | 0.009660622337290968 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | C | R | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 24949 | 24.102286669307237 |
| CUSTOMER_UPLOAD | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 4980 | 4.810989923970903 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | R | R | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 11 | 0.010626684571020065 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | S | C | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | S | S | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | S | S | [No cancellation reason recorded] | No cancellation reason | [No block reason recorded] | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.006762435636103678 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | A | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 68 | 0.06569223189357859 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 15 | 0.014490933505936452 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 5 | 0.004830311168645484 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | C | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 239 | 0.23088887386125415 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 4112 | 3.972447905094046 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 19 | 0.018355182440852838 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 682 | 0.6588544434032441 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2235 | 2.1591490923845313 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 234 | 0.22605856269260866 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1306 | 1.2616772772502005 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 58 | 0.056031609556287616 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 864 | 0.8346777699419397 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | Has matching upload | 32 | 0.030913991479331097 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 491 | 0.4743365567609865 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 113 | 0.10916503241138795 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | Has matching upload | 5 | 0.004830311168645484 |
| CUSTOMER_UPLOAD | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 70 | 0.06762435636103678 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 30 | 0.028981867011872903 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 11 | 0.010626684571020065 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 10 | 0.009660622337290968 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 5 | 0.004830311168645484 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | R | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 15 | 0.014490933505936452 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 13 | 0.01255880903847826 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | S | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 275 | 0.2656671142755016 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 15769 | 15.233835363674128 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 39 | 0.03767642711543478 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 251 | 0.24248162066600332 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2622 | 2.533015176837692 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 160 | 0.1545699573966555 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1895 | 1.8306879329166386 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OTHER | Has matching upload | 53 | 0.05120129838764213 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 3601 | 3.478790103658478 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 38 | 0.036710364881705676 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1625 | 1.5698511298097824 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 11 | 0.010626684571020065 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 413 | 0.398983702530117 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | No matching upload | 50 | 0.04830311168645484 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 309 | 0.2985132302222909 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 4980 | 4.810989923970903 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 11 | 0.010626684571020065 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 456 | 0.44052437858046817 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2884 | 2.786123482074715 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 253 | 0.2444137451334615 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2450 | 2.366852472636287 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | Has matching upload | 66 | 0.06376010742612039 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | No matching upload | 866 | 0.8366098944093978 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 53 | 0.05120129838764213 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 565 | 0.5458251620569398 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 7 | 0.006762435636103678 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 8 | 0.007728497869832774 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 123 | 0.11882565474867891 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE/PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | No matching upload | 78 | 0.07535285423086956 |
| CUSTOMER_UPLOAD | X | X | Customer Initiated Cancellation | With cancellation reason | [No block reason recorded] | Has matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 254 | 0.2453798073671906 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1995 | 1.9272941562895483 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 444 | 0.42893163177571897 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1044 | 1.0085689720131772 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 284 | 0.2743616743790635 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 680 | 0.6569223189357859 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OTHER | Has matching upload | 48 | 0.04637098721899665 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OTHER | No matching upload | 415 | 0.40091582699757516 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 34 | 0.032846115946789295 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | No matching upload | 208 | 0.20094094461565215 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 34 | 0.032846115946789295 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | No matching upload | 23 | 0.022219431375769226 |
| CUSTOMER_UPLOAD | X | X | Customer Request | With cancellation reason | [No block reason recorded] | Has matching upload | 5 | 0.004830311168645484 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OTHER | Has matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OTHER | No matching upload | 25 | 0.02415155584322742 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Duplicate Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Fraud | With cancellation reason | OTHER | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Inventory Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 5 | 0.004830311168645484 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 438 | 0.4231352583733444 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 7 | 0.006762435636103678 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 13 | 0.01255880903847826 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | OTHER | No matching upload | 94 | 0.09080984997053511 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.01255880903847826 |
| CUSTOMER_UPLOAD | X | X | No Response | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 20 | 0.019321244674581937 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 102 | 0.09853834784036787 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 27 | 0.026083680310685614 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 76 | 0.07342072976341135 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 18 | 0.017389120207123743 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 32 | 0.030913991479331097 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OTHER | Has matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OTHER | No matching upload | 33 | 0.03188005371306019 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.01255880903847826 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Other | With cancellation reason | PET_ID_MISMATCH | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 10 | 0.009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1883 | 1.8190951861118894 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 143 | 0.13814689942326083 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 23 | 0.022219431375769226 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | OTHER | No matching upload | 444 | 0.42893163177571897 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | OUT_OF_REFILLS | No matching upload | 136 | 0.13138446378715718 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 25 | 0.02415155584322742 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Payment Declined | With cancellation reason | [No block reason recorded] | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.006762435636103678 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OTHER | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Payment Issue | With cancellation reason | OUT_OF_REFILLS | No matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 85 | 0.08211528986697324 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 18 | 0.017389120207123743 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.0028981867011872906 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 18 | 0.017389120207123743 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | OTHER | No matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | X | Pharmacy Rejection | With cancellation reason | OUT_OF_REFILLS | No matching upload | 7 | 0.006762435636103678 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 60 | 0.05796373402374581 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2964 | 2.863408460773043 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 4 | 0.003864248934916387 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 64 | 0.061827982958662195 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 406 | 0.3922212668940133 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 42 | 0.040574613816622064 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 271 | 0.2618028653405852 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OTHER | Has matching upload | 18 | 0.017389120207123743 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OTHER | No matching upload | 748 | 0.7226145508293644 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 6 | 0.005796373402374581 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS | No matching upload | 256 | 0.24731193183464878 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 58 | 0.056031609556287616 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | Prescription Issue | With cancellation reason | PET_ID_MISMATCH | No matching upload | 8 | 0.007728497869832774 |
| CUSTOMER_UPLOAD | X | X | Reseller | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 7 | 0.006762435636103678 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 69 | 0.06665829412730769 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 11 | 0.010626684571020065 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 36 | 0.034778240414247485 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 36 | 0.034778240414247485 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OTHER | Has matching upload | 2 | 0.0019321244674581936 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 20 | 0.019321244674581937 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 9 | 0.008694560103561871 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| CUSTOMER_UPLOAD | X | X | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 2 | 0.0019321244674581936 |
| FAX | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 7 | 0.006762435636103678 |
| FAX | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 566 | 0.5467912242906688 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 11 | 0.010626684571020065 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 4 | 0.003864248934916387 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.003864248934916387 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 2 | 0.0019321244674581936 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 3 | 0.0028981867011872906 |
| FAX | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 4 | 0.003864248934916387 |
| FAX | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2 | 0.0019321244674581936 |
| FAX | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| FAX | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 7 | 0.006762435636103678 |
| FAX | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.003864248934916387 |
| FAX | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | No matching upload | 3 | 0.0028981867011872906 |
| FAX | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 5 | 0.004830311168645484 |
| FAX | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.003864248934916387 |
| FAX | X | X | Duplicate Order | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| FAX | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 16 | 0.015456995739665549 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2 | 0.0019321244674581936 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | OTHER | No matching upload | 2 | 0.0019321244674581936 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Pharmacy Rejection | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | Prescription Issue | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| FAX | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| PH | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 1 | 0.0009660622337290968 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | INSUFFICIENT_REFILLS_REMAINING | Has matching upload | 1 | 0.0009660622337290968 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 3 | 0.0028981867011872906 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 10 | 0.009660622337290968 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 4 | 0.003864248934916387 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.0028981867011872906 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| PH | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 2 | 0.0019321244674581936 |
| PH | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 3 | 0.0028981867011872906 |
| PH | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 4 | 0.003864248934916387 |
| PH | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 6 | 0.005796373402374581 |
| PH | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 5 | 0.004830311168645484 |
| PH | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| PH | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 5 | 0.004830311168645484 |
| PH | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 6 | 0.005796373402374581 |
| PH | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 4 | 0.003864248934916387 |
| PH | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 9 | 0.008694560103561871 |
| PH | X | X | Customer Request | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Duplicate Order | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Payment Declined | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| PH | X | X | [No cancellation reason recorded] | No cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| SNAIL_MAIL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 2 | 0.0019321244674581936 |
| SNAIL_MAIL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 127 | 0.1226899036835953 |
| SNAIL_MAIL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| SNAIL_MAIL | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | C | C | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | C | C | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | Has matching upload | 286 | 0.27629379884652167 |
| VERBAL | D | D | [No cancellation reason recorded] | No cancellation reason | [Not applicable: status D] | No matching upload | 2764 | 2.6701960140272236 |
| VERBAL | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | S | C | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 65 | 0.06279404519239129 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 27 | 0.026083680310685614 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 68 | 0.06569223189357859 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 17 | 0.016423057973394647 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 54 | 0.05216736062137123 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | OTHER | No matching upload | 11 | 0.010626684571020065 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 5 | 0.004830311168645484 |
| VERBAL | X | D | [No cancellation reason recorded] | No cancellation reason | PET_ID_MISMATCH | No matching upload | 3 | 0.0028981867011872906 |
| VERBAL | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 6 | 0.005796373402374581 |
| VERBAL | X | X | Aged Order | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 209 | 0.20190700684938123 |
| VERBAL | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 3 | 0.0028981867011872906 |
| VERBAL | X | X | Aged Order | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 61 | 0.05892979625747491 |
| VERBAL | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 20 | 0.019321244674581937 |
| VERBAL | X | X | Aged Order | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 100 | 0.09660622337290968 |
| VERBAL | X | X | Aged Order | With cancellation reason | OTHER | No matching upload | 42 | 0.040574613816622064 |
| VERBAL | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS | No matching upload | 30 | 0.028981867011872903 |
| VERBAL | X | X | Aged Order | With cancellation reason | OUT_OF_REFILLS/PET_ID_MISMATCH | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Aged Order | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 7 | 0.006762435636103678 |
| VERBAL | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Aged Order | With cancellation reason | PET_ID_MISMATCH | No matching upload | 3 | 0.0028981867011872906 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 10 | 0.009660622337290968 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 159 | 0.15360389516292638 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 25 | 0.02415155584322742 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 132 | 0.12752021485224077 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 29 | 0.028015804778143808 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 167 | 0.16133239303275917 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | OTHER | No matching upload | 29 | 0.028015804778143808 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | OUT_OF_REFILLS | No matching upload | 10 | 0.009660622337290968 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 4 | 0.003864248934916387 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Customer Initiated Cancellation | With cancellation reason | PET_ID_MISMATCH | No matching upload | 5 | 0.004830311168645484 |
| VERBAL | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 4 | 0.003864248934916387 |
| VERBAL | X | X | Customer Request | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 75 | 0.07245466752968226 |
| VERBAL | X | X | Customer Request | With cancellation reason | INSUFFICIENT_REFILLS_REMAINING | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 23 | 0.022219431375769226 |
| VERBAL | X | X | Customer Request | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 76 | 0.07342072976341135 |
| VERBAL | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 28 | 0.027049742544414713 |
| VERBAL | X | X | Customer Request | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 65 | 0.06279404519239129 |
| VERBAL | X | X | Customer Request | With cancellation reason | OTHER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Customer Request | With cancellation reason | OTHER | No matching upload | 12 | 0.011592746804749162 |
| VERBAL | X | X | Customer Request | With cancellation reason | OUT_OF_REFILLS | No matching upload | 13 | 0.01255880903847826 |
| VERBAL | X | X | Customer Request | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 3 | 0.0028981867011872906 |
| VERBAL | X | X | Customer Request | With cancellation reason | PET_ID_MISMATCH | No matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | X | Duplicate Order | With cancellation reason | OTHER | No matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | X | Fraud | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | X | Fraud | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Fraud | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Fraud | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Fraud | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 8 | 0.007728497869832774 |
| VERBAL | X | X | No Response | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 16 | 0.015456995739665549 |
| VERBAL | X | X | No Response | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | No Response | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | No Response | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Other | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 7 | 0.006762435636103678 |
| VERBAL | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Other | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 8 | 0.007728497869832774 |
| VERBAL | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Other | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 5 | 0.004830311168645484 |
| VERBAL | X | X | Other | With cancellation reason | OTHER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Other | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Other | With cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Payment Declined | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 41 | 0.03960855158289297 |
| VERBAL | X | X | Payment Declined | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 4 | 0.003864248934916387 |
| VERBAL | X | X | Payment Declined | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 3 | 0.0028981867011872906 |
| VERBAL | X | X | Payment Declined | With cancellation reason | OTHER | No matching upload | 8 | 0.007728497869832774 |
| VERBAL | X | X | Payment Declined | With cancellation reason | OUT_OF_REFILLS | No matching upload | 6 | 0.005796373402374581 |
| VERBAL | X | X | Pharmacy Rejection | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Pharmacy Rejection | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | X | Pharmacy Rejection | With cancellation reason | OTHER | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | Has matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 51 | 0.049269173920183935 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | Has matching upload | 8 | 0.007728497869832774 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 11 | 0.010626684571020065 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 3 | 0.0028981867011872906 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | NEW_VD_CUSTOMER | No matching upload | 27 | 0.026083680310685614 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | OTHER | Has matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | OTHER | No matching upload | 13 | 0.01255880903847826 |
| VERBAL | X | X | Prescription Issue | With cancellation reason | PAST_EXPIRATION_DATE | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | [No cancellation reason recorded] | No cancellation reason | CANCELED_AUTHORIZATION | No matching upload | 1 | 0.0009660622337290968 |
| VERBAL | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_ITEM_AUTHORIZATION | No matching upload | 2 | 0.0019321244674581936 |
| VERBAL | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | Has matching upload | 4 | 0.003864248934916387 |
| VERBAL | X | X | [No cancellation reason recorded] | No cancellation reason | NEW_VD_CUSTOMER | No matching upload | 4 | 0.003864248934916387 |
| VERBAL | X | X | [No cancellation reason recorded] | No cancellation reason | OUT_OF_REFILLS | No matching upload | 1 | 0.0009660622337290968 |
