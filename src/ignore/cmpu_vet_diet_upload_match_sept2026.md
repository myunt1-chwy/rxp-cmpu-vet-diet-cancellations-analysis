# CMPU vet diet prescriptions vs. customer uploads — September 2026

Query: `cmpu_vet_diet_upload_match_sept2026.sql` (same folder).
Run against connection `CHEWY` on 2026-10-23.

## Scope

- **Prescriptions:** `EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS` where
  `IS_VET_DIET_FLAG = TRUE`, `PRESCRIPTION_SOURCE = 'CMPU'`, and
  `RX_CREATION_DATETIME` in Sept 1–30, 2026. `IS_DELETED` not filtered.
- **Uploads:** `EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY` where
  `UPLOAD_TYPE = 'DIET_PRESCRIPTION'`.
- **Join:** `RX_ID` + `CUSTOMER_ID`. Upload `RX_ID` is brace-wrapped and can
  list several ids, so braces are stripped and the list split. Upload
  `CUSTOMER_ID` is VARCHAR and cast to NUMBER.

## Headline

55,286 CMPU vet diet prescriptions were created in September; 91.7% have
`APPROVAL_CHANNEL = CUSTOMER_UPLOAD`. Only **34.6%** of CUSTOMER_UPLOAD
prescriptions ever received an upload. Of the ~33K that never did, **89.9% were
customer canceled**. When a document is uploaded it is usually accepted (81%)
and the prescription is approved at the same moment.

## Approval channel mix and outcome

| APPROVAL_CHANNEL | Prescriptions | % | Ever approved | Median hrs to approve |
|---|---|---|---|---|
| CUSTOMER_UPLOAD | 50,695 | 91.7% | 14,682 (29%) | 26 |
| VERBAL | 2,793 | 5.1% | 1,527 (55%) | 41 |
| CUSTOMER_EMAIL | 1,224 | 2.2% | 1,224 (100%) | 28 |
| FAX | 350 | 0.6% | 290 (83%) | 58 |
| CLINIC_EMAIL | 87 | 0.2% | 50 (57%) | 46.5 |
| PH | 83 | 0.2% | 0 | — |
| SNAIL_MAIL | 54 | 0.1% | 54 (100%) | 84 |
| **Total** | **55,286** | | | |

Current `RX_STATUS` for CUSTOMER_UPLOAD: APPROVED 14,026 (28%),
SYSTEM_CLOSED 36,032 (71%), CLOSED 637, DENIED 0.

`CUSTOMER_CANCELED = TRUE` on 33,041 of 55,286 (59.8%) overall. Canceled
prescriptions show up as `RX_STATUS = SYSTEM_CLOSED` (a few `CLOSED`);
`MIN_CANCELED_DATETIME` is never populated, so the boolean is the only signal.

## Match to uploads

| APPROVAL_CHANNEL | Prescriptions | With upload | % | Checkout/order flows | Medicine cabinet | Accepted | Review req. | Rejected | Med hrs rx→upload | Med hrs upload→approve |
|---|---|---|---|---|---|---|---|---|---|---|
| CUSTOMER_UPLOAD | 50,695 | 17,522 | 34.6% | 14,801 | 2,730 | 14,181 | 2,857 | 476 | 18 | 0 |
| VERBAL | 2,793 | 348 | 12.5% | 310 | 38 | 131 | 182 | 35 | 0 | 21 |
| CUSTOMER_EMAIL | 1,224 | 225 | 18.4% | 199 | 27 | 192 | 2 | 28 | 2 | 25 |
| FAX | 350 | 15 | 4.3% | 11 | 4 | 1 | 9 | 5 | 0 | 22 |
| CLINIC_EMAIL | 87 | 11 | 12.6% | 10 | 1 | 2 | 5 | 4 | 70 | 0 |
| PH | 83 | 30 | 36.1% | 25 | 5 | 0 | 28 | 2 | 3.5 | — |
| SNAIL_MAIL | 54 | 2 | 3.7% | 2 | 0 | 2 | 0 | 0 | 45 | 8.5 |
| **Total** | **55,286** | **18,153** | **32.8%** | 15,358 | 2,805 | 14,509 | 3,083 | 550 | 17 | 0 |

Source and state columns are not mutually exclusive (a prescription can have
several uploads).

### CUSTOMER_UPLOAD: upload vs. customer cancel

| | Customer canceled | Not canceled | Total |
|---|---|---|---|
| Had an upload | 2,193 (12.5%) | 15,329 | 17,522 |
| No upload | 29,820 (89.9%) | 3,353 | 33,173 |

### First half vs. full month (CUSTOMER_UPLOAD)

| Metric | Sept 1–15 | Full Sept |
|---|---|---|
| Prescriptions | 26,094 | 50,695 |
| With upload | 34.0% | 34.6% |
| Upload accepted (of uploaded) | 81% | 81% |
| Upload rejected (of uploaded) | 2.0% | 2.7% |
| No upload → customer canceled | 89.9% | 89.9% |
| Median hrs rx → first upload | 18 | 18 |

## Shipped prescriptions vs. uploads

Query: `cmpu_vet_diet_shipped_upload_match_sept2026.sql`.

`RXP_PRESCRIPTIONS` has no shipped flag. Proxy used: `FIRST_RX_USAGE_STATUS =
'APPROVED'` and `FIRST_ORDER_ID IS NOT NULL` (first order using the Rx was
approved). Not validated against fulfillment data.

| APPROVAL_CHANNEL | Shipped | With upload | % | Checkout/order flows | Medicine cabinet | Accepted | Review req. | Rejected | No upload | Med hrs upload→approve |
|---|---|---|---|---|---|---|---|---|---|---|
| CUSTOMER_UPLOAD | 14,009 | 13,462 | 96.1% | 11,283 | 2,184 | 13,426 | 2 | 33 | 547 | 0 |
| VERBAL | 1,487 | 152 | 10.2% | 134 | 18 | 129 | 0 | 23 | 1,335 | 21 |
| CUSTOMER_EMAIL | 1,198 | 220 | 18.4% | 194 | 27 | 187 | 2 | 28 | 978 | 25 |
| FAX | 282 | 4 | 1.4% | 4 | 0 | 1 | 0 | 3 | 278 | 22 |
| SNAIL_MAIL | 52 | 2 | 3.8% | 2 | 0 | 2 | 0 | 0 | 50 | 8.5 |
| CLINIC_EMAIL | 47 | 2 | 4.3% | 2 | 0 | 2 | 0 | 0 | 45 | 0 |
| **Total** | **17,075** | **13,842** | **81.1%** | 11,619 | 2,229 | 13,747 | 4 | 87 | 3,233 | 0 |

- 96% of shipped CUSTOMER_UPLOAD prescriptions had an (accepted) upload, vs.
  34.6% of all CUSTOMER_UPLOAD prescriptions — the upload is the gate to
  shipping.
- 547 shipped CUSTOMER_UPLOAD prescriptions have no matching upload; likely
  approved another way or upload not linked to the `RX_ID`. Worth checking.
- Other channels rarely involve an upload (≤18%).

## First-order cancellation reasons

Query: `cmpu_vet_diet_order_cancel_reasons_sept2026.sql`.

`RXP_PRESCRIPTIONS.FIRST_ORDER_ID` joined to `EDLDB.ECOM.ORDERS.ORDER_ID`.
Canceled = `ORDER_STATUS = 'X'`. Only the first order per prescription.

| Cancel reason | All Rx | % of canceled | CU with upload | CU no upload | Other channels |
|---|---|---|---|---|---|
| Aged Order | 13,789 | 49.1% | 421 | 13,097 | 271 |
| Customer Initiated Cancellation | 6,581 | 23.4% | 580 | 5,693 | 308 |
| Customer Request | 2,827 | 10.1% | 575 | 2,059 | 193 |
| Other cancel reasons | 4,885 | 17.4% | 188 | 4,545 | 152 |
| **Subtotal: canceled orders** | **28,082** | 100% | 1,764 | 25,394 | 924 |
| Order not canceled | 22,587 | | 14,132 | 5,206 | 3,249 |
| No first order found | 4,617 | | 1,626 | 2,573 | 418 |
| **Total** | **55,286** | | 17,522 | 33,173 | 4,591 |

CU = `APPROVAL_CHANNEL = CUSTOMER_UPLOAD`.

"Other cancel reasons" (4,885): Prescription Issue 2,732, Payment Declined
1,414, No Response 329, Other 176, canceled with no reason 114, Pharmacy
Rejection 65, Duplicate Order 33, Fraud 13, Payment Issue 7, Reseller 1,
Inventory Issue 1.

- **Aged Order dominates no-upload cancellations.** 13,097 of 25,394 (52%)
  canceled CU orders without an upload aged out.
- **Customer-driven cancels are about a third.** Customer Initiated
  Cancellation + Customer Request = 9,408 (33%); 7,752 had no upload, 1,155
  came after an upload.
- **Cancels are rare after an upload.** Only 1,764 of 17,522 CU prescriptions
  with an upload had their first order canceled, mostly customer-driven.
- **Ties to `CUSTOMER_CANCELED`.** 27,604 of 28,082 canceled orders belong to
  prescriptions flagged `CUSTOMER_CANCELED`, so the flag largely reflects the
  order being canceled, including system Aged Order cancels.
- ~5,400 `CUSTOMER_CANCELED` prescriptions have a first order that was not
  canceled (mostly `ORDER_STATUS = 'D'`); the vet diet item may have been
  removed from an order that otherwise shipped. Not visible at order level.
- 4,617 prescriptions have no `FIRST_ORDER_ID` or no match in `ECOM.ORDERS`.

## Time from order placed to first upload

Query: `cmpu_vet_diet_order_to_upload_time_sept2026.sql`.

Scope: 16,430 Sept CMPU vet diet prescriptions with both a first order in
`ECOM.ORDERS` and a diet upload. Time = first upload `CREATED_TS_UTC` minus
`ORDER_PLACED_DTTM` (both UTC; `ORDER_PLACED_DTTM` is EST + 4 h in Sept).
1,723 uploaded prescriptions excluded for no matching first order.

| Order → first upload | Orders | % | Cum. % | Canceled | Aged Order | Customer cancel* |
|---|---|---|---|---|---|---|
| Before order | 138 | 0.8% | 0.8% | 10 | 2 | 8 |
| < 1 hr | 5,275 | 32.1% | 32.9% | 789 | 161 | 546 |
| 1–6 hrs | 978 | 6.0% | 38.9% | 112 | 23 | 78 |
| 6–24 hrs | 2,557 | 15.6% | 54.4% | 262 | 61 | 183 |
| 1–2 days | 2,171 | 13.2% | 67.6% | 213 | 39 | 142 |
| 2–3 days | 1,506 | 9.2% | 76.8% | 137 | 28 | 99 |
| 3–5 days | 1,733 | 10.5% | 87.4% | 162 | 43 | 105 |
| 5–7 days | 1,024 | 6.2% | 93.6% | 84 | 31 | 41 |
| 7+ days | 1,048 | 6.4% | 100% | 109 | 52 | 37 |
| **Total** | **16,430** | | | 1,878 | 440 | 1,239 |

\* Customer Initiated Cancellation + Customer Request.

| Group | Orders | p10 | p25 | p50 | p75 | p90 | p95 | Mean (hrs) |
|---|---|---|---|---|---|---|---|---|
| All | 16,430 | 0.02 | 0.10 | 18.3 | 66.2 | 137.6 | 182.9 | 41.8 |
| Order canceled | 1,878 | 0.02 | 0.07 | 7.4 | 51.9 | 122.2 | 181.2 | 36.1 |
| Order not canceled | 14,552 | 0.02 | 0.12 | 19.6 | 67.8 | 138.9 | 183.0 | 42.5 |

- **Two peaks.** A third upload within an hour (p25 = 6 minutes, i.e. at
  checkout / thank-you); the rest spread over days. Median 18 hours; 13% after
  5+ days.
- **Late uploads meet the Aged Order cutoff.** 7+ day uploads have the highest
  Aged Order share (5% vs ~3% under an hour). Aged Order threshold not
  confirmed.
- **Upload delay doesn't predict cancellation for uploaders.** Canceled orders
  had a shorter median (7.4 h) than non-canceled (19.6 h); cancels among
  uploaders look customer-driven.
- 138 uploads precede the order — likely tied to an earlier order, PDP upload,
  or Rx reuse.

## Takeaways

1. **Loss is driven by non-upload, not rejection.** About 65% of
   CUSTOMER_UPLOAD prescriptions never get a document, and ~90% of those end
   customer canceled (~30K in the month). Rejected uploads are <3%.
2. **Upload acceptance = approval.** Median upload→approval is 0 hours, so the
   ACCEPTED upload state appears to trigger approval.
3. **Uploaders act fast.** Median 18 hours from prescription creation to first
   upload.
4. **Open backlog.** ~2,860 CUSTOMER_UPLOAD prescriptions have an upload still
   in REVIEW_REQUIRED.
5. **Surface mix.** Checkout/order flows account for ~85% of uploads; medicine
   cabinet (My Prescriptions, Pet Portal) ~15%.

## Caveats / open questions

- `MIN_VALIDATED_DATETIME`, `MIN_PHARMACIST_REVIEW_DATETIME`,
  `MIN_AWAITING_CUSTOMER_DATETIME`, `MIN_DUR_DATETIME` are 0% populated for
  CMPU vet diet — no time-to-validation is available. `MIN_VET_REVIEW_DATETIME`
  equals creation (median 0 h).
- Mapping of `CLIENT_SOURCE` to Segment `van-damme` vs. `pet-healthcare` flows
  is inferred from page names.
- Mechanism behind `CUSTOMER_CANCELED` (order/item cancel vs. explicit Rx
  cancel) not confirmed; `STATE_CHANGE_REASON` not yet examined.
- `PH` channel meaning (phone?) not confirmed; 0 approvals.

## Related Segment findings

- Upload events live in `EDLDB.SEGMENT.SEGMENT_HITS` /
  `SEGMENT_HITS_PRODUCTS` under `EVENT_CATEGORY = 'van-damme'` (main flow) and
  `'pet-healthcare'` (`upload-authorization`, `auth-file-upload`,
  `auth-file-submit`, `auth-upload-close`).
- `ORDER_ID` is null on all of these events; `CUSTOMER_ID` is ~100% populated.
- `pet-healthcare` events carry `PROPERTIES:eventData:prescriptionId`, which
  matches `RXP_PRESCRIPTIONS.RX_ID` + `CUSTOMER_ID` at 98.9%.
