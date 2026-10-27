# Setup

## VDAM upload distribution (REFNUM 1)

Generate the distribution for uploads dated July 30 through October 20, 2026,
inclusive in UTC:

```sh
make create-vdam-upload-distribution START_DATE=2026-07-30 END_DATE=2026-10-21
```

Both dates are required; `END_DATE` is exclusive. The dates filter uploads,
not order placement. Require `UPLOAD_TYPE = 'DIET_PRESCRIPTION'`,
`ASSOCIATED_RESOURCE_TYPE = 'DIET_PRESCRIPTION'`, `HAS_ASSOCIATED_RX = TRUE`,
and `HAS_UPLOADED_FILE = TRUE`. Expand the brace-delimited `RX_ID` list and
deduplicate IDs within each upload; do not use `ASSOCIATED_RX_CNT` as a weight.
Each distinct prescription contributes its earliest qualifying order-linked
upload within the window, joined using the upload table's order ID directly.
For prescriptions linked to multiple orders, use the order on that earliest
matched upload; break timestamp ties by upload ID, then order ID.
`ORDER_PLACED_DTTM` is interpreted as UTC based on its four/five-hour offset
from the Eastern companion column; this is an inference, not a documented
timezone guarantee. No additional timezone shift is applied. Negative elapsed
hours and all outliers remain in the 50 equal-width bins.

The read-only runner uses browser SSO and a local ignored `.env` containing
`RXP_SNOWFLAKE_ACCOUNT`, `RXP_SNOWFLAKE_USER`, `RXP_SNOWFLAKE_DATABASE`,
`RXP_SNOWFLAKE_WAREHOUSE`, `RXP_SNOWFLAKE_SCHEMA`, and optionally
`RXP_SNOWFLAKE_ROLE`. Run `make setup` if dependencies are missing.

Add `PRINT_SQL=1` to print SQL without accessing Snowflake or writing files.
Add `CACHED=1` to redraw from a completed extract with matching dates and SQL.
Downloaded Parquet, executed SQL, and extraction provenance are saved under
`data/vdam-upload-distribution/<start>_<end>/`. The transparent PNG is under
`outputs/charts/vdam-upload-distribution/<start>_<end>/distribution.png`;
the 50-bin Markdown table and reconciliation counts are under
`outputs/tables/vdam-upload-distribution/<start>_<end>/distribution.md`.
All generated outputs are ignored by Git.

The same target also exports `distribution-by-cancel-reason.png` and
`distribution-by-cancel-reason.md` alongside those files. This five-panel chart
uses the same 50 bin boundaries for every group, with independent count scales
and the prescription total in each panel title. The Markdown table includes
group totals and 250 bin rows; bin percentages are within each group.
Five separate transparent figures are also exported to the same chart directory:
`distribution-not-cancelled.png`, `distribution-aged-orders.png`,
`distribution-customer-initiated.png`, `distribution-customer-requested.png`,
and `distribution-other.png`. They retain the shared bin boundaries and use
count scales appropriate to each group. Regenerate them from the existing
extract by adding `CACHED=1` to the Make command.
`ORDER_CANCEL_REASON` is taken from the selected upload's order at extraction
time, not reconstructed as of the upload date. Groups are:

- NULL: Not cancelled.
- `Aged Order`: Aged orders.
- `Customer Initiated Cancellation`: Customer initiated.
- `Customer Request`: Customer requested.
- Every other non-null value: Other.

Reason matching ignores case and leading/trailing whitespace. Prescription
deduplication happens before grouping, so every prescription belongs to exactly
one group. Existing caches without the cancellation-reason column require a
fresh run without `CACHED=1`.

Missing prescription IDs, missing/invalid order IDs, unmatched orders, and
missing order timestamps are reported separately at prescription-upload grain.
Repeated matched uploads are reduced to one observation per prescription.
Duplicate upload/prescription pairs or duplicate order-source rows fail validation
instead of silently multiplying observations. Uploads with missing timestamps
cannot be assigned to a date cohort. Empty results produce a table explaining
the result and no chart; a constant duration uses a one-hour plotting range.

Run the focused checks with:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_vdam_upload_distribution.py'
```

## Aged-order lifecycle-state distribution (REFNUM 4)

Keep the existing upload cohort and fetch only its latest prescription states:

```sh
make create-aged-upload-lifecycle-distribution START_DATE=2026-07-30 END_DATE=2026-10-21
```

This requires the completed REFNUM 1 upload cache for those dates. It does not
refresh uploads or orders. The current cohort contains 2,220 aged-order
prescriptions, selected after deduplicating prescriptions across all orders.
Both dates are required; the end is exclusive. `PRINT_SQL=1` reads the existing
cohort and prints the lifecycle-state query without querying or writing files.
`CACHED=1` renders saved states without contacting Snowflake; a cohort or SQL
mismatch requires a fresh state lookup. The cohort fingerprint covers selected
prescriptions, their upload/order IDs and delays, and all 50 global bin edges.

States are read from `EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS` by individual `RX_ID`.
The chart shows the latest available state at extraction time, including
nonterminal states; it does not reconstruct the state at upload or cancellation.
Duplicate source IDs stop the run. Unmatched prescriptions and null states are
retained as separate categories. Every stack sums to the existing aged-order
bin count; negative durations and outliers remain included.

The executed SQL, state Parquet, timestamps, and provenance are stored under
`data/vdam-upload-distribution/<start>_<end>/aged-lifecycle/`. The transparent
`distribution-aged-orders-by-lifecycle-state.png` goes in the dated chart
directory. The identically named `.md` file in the dated table directory contains
state totals, cohort percentages, and all bin-by-state counts. Existing figures
are preserved. An empty aged cohort produces an explanatory table and no PNG.

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_aged_upload_lifecycle_distribution.py'
```

## Environment setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
make init
```

Enter a project name and description, or press Enter to use
the repository folder name and the existing description (or
`Add your description here` when absent). Names must start
and end with a letter or digit and contain only letters, digits, `.`, `_`, or
`-`. Ctrl-C or end-of-input cancels without writing project configuration.

`make init` creates `.venv` with Python 3.12 (uv may download Python) and
synchronizes dependencies before prompting when configuration exists. It edits
only the project name and description, preserving dependencies, other settings,
and TOML formatting, then synchronizes again to refresh `uv.lock`. Explicitly
running `make init` again prompts again. Cancellation leaves `pyproject.toml`
unchanged; the preliminary synchronization may already have updated the
environment and lockfile.

For subsequent dependency synchronization, run `make setup`. It preserves
existing `pyproject.toml` without prompting. If configuration is absent, either
command prompts for metadata and generates it.
The initial runtime dependencies are defined in `scripts/setup.py`; the
development dependency group includes `pytest>=9.1.1` and `tomlkit>=0.13.3`.
After initialization, edit
`pyproject.toml` to change either list and rerun `make setup`.
An internet connection may be required to download Python and packages.
If dependency resolution fails, the requested constraints remain unchanged;
resolve the reported issue and rerun `make setup`.

Keep `pyproject.toml` and `uv.lock` in version control. Run Python commands
through `.venv/bin/python`.

To run the setup behavior checks after setup:

```sh
.venv/bin/python -m unittest discover -s tests
```

## Matt Pocock skills

With Node.js and npm (which provides `npx`) installed, run:

```sh
make setup-mattpocock-skills
```

This runs `npx skills@latest add mattpocock/skills` with flags to install all
skills for Codex without prompts, locally under `.agents/skills/`. It requires
internet access and does not depend on the Python environment. The CLI records
installed sources in `skills-lock.json`; keep that file and the installed skills
in version control. Rerunning the target fetches the latest upstream skills and
may overwrite local edits to those skills.

To uninstall this collection:

```sh
make uninstall-mattpocock-skills
```

This selects only entries whose source is `mattpocock/skills` in
`skills-lock.json`, then uses the CLI to remove their shared files and agent
links in this project and update the lockfile. Other skills and global
installations are preserved. Missing lockfiles or no
matching entries produce a successful no-op; invalid lockfiles report an error.
Node.js, npm, and internet access for `npx skills@latest` are required.
Uninstalling removes local edits to these skills. Run the setup target to
install them again.

See the [skills CLI reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
for installation options.

## CMPU vet-diet prescription matches to upload events

Run the read-only summary query:

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_upload_event_matches.sql --output-parquet data/cmpu-upload-event-matches/2026-09-01_2026-09-16/summary.parquet --sql-log-dir data/cmpu-upload-event-matches/2026-09-01_2026-09-16/sql
```

Events are read from `EDLDB.SEGMENT.SEGMENT_HITS_PRODUCTS_UNION`.
The event filters come from the supplied `src/ignore/rxp` query, with its
undefined `c` reference removed. The query's `date_window` CTE sets both cohorts
to September 1–15, 2026, inclusive: start `2026-09-01`, exclusive end
`2026-09-16`. Events use `SESSION_DATE_EST`;
prescriptions use `RX_CREATION_DATETIME` without a timezone conversion.
Only `PRESCRIPTION_SOURCE = 'CMPU'` and `IS_VET_DIET_FLAG = TRUE` prescriptions
qualify. No status or deletion filters are added.

Match on customer and product IDs without timestamp ordering. Repeated events
cannot inflate the distinct-prescription count. The summary includes missing
keys, duplicate prescription IDs, and repeated customer/product pairs; those
pairs indicate association, not proof that an upload created a prescription.
The reviewed Markdown summary belongs under
`outputs/tables/cmpu-upload-event-matches/2026-09-01_2026-09-16/summary.md`.
The previous October results remain in the parent directory.

### Match the prescription ID recorded in event properties

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_upload_prescription_id_matches.sql --output-parquet data/cmpu-upload-event-matches/2026-09-01_2026-09-16/prescription-id/matches.parquet --sql-log-dir data/cmpu-upload-event-matches/2026-09-01_2026-09-16/prescription-id/sql
.venv/bin/python -m src.python.summarize_cmpu_prescription_id_matches
```

Uses the same September dates and upload-event filters. Extracts
`properties:eventData:prescriptionId` and `properties:prescriptionId`, preferring
the nested value when both are filled. Blank/JSON-null IDs are missing;
conflicting values are audited. Joins the selected ID directly to `RX_ID`
without requiring event customer or product IDs. The full outer join retains
all cohort prescriptions and events for completeness checks and comparison
with the original customer/product association method.

The source extract and summary metadata are under the dated `prescription-id/`
data directory. Markdown summary and event-type field coverage are under
`outputs/tables/cmpu-upload-event-matches/2026-09-01_2026-09-16/prescription-id/`.
Rerun only the summarizer to use the existing extract.

## Later canceled orders for September CMPU vet-diet prescriptions

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_later_cancelled_orders.sql --output-parquet data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/links.parquet --sql-log-dir data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/sql
.venv/bin/python -m src.python.summarize_cmpu_later_cancelled_orders
```

The cohort is CMPU vet-diet prescriptions created September 1–15, 2026,
inclusive. Links combine FIRST_ORDER_ID with all available prescription usage
action history, reduced to distinct prescription/order pairs. A qualifying
order was placed strictly after prescription creation and has latest status
Canceled. Orders and cancellations may occur after September 15. Cancellation
reasons are not filtered; missing reasons remain explicit. Cancellation
timestamps are checked against order placement, and order UTC/Eastern timestamp
companions must agree where available. RX_CREATION_DATETIME is interpreted as UTC.

Source SQL, Parquet and SHA-256 metadata are under
`data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/`.
Summary, cancellation-reason and qualifying-link Markdown tables are under
`outputs/tables/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/`.
Each prescription counts once in the headline; reason-specific prescription
counts may overlap. The summarizer reuses the cached extract without connecting.

### Actual prescription-item shipments

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_prescription_shipments.sql --output-parquet data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/shipments.parquet --sql-log-dir data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/sql
.venv/bin/python -m src.python.summarize_cmpu_prescription_shipments
```

Requires the cancellation analysis extract above. Uses a non-null
ORDER_LINE_SHIPPED_DTTM in ORDER_LINE_COST_MEASURES_RXP as shipment evidence,
joined directly by RX_ID. Counts distinct prescriptions, separating any shipped
order, shipped orders placed after prescription creation, the canceled-order
prescription subset, and shipping on the same canceled order. Current order
status alone is not used to determine shipping. Missing order-line coverage is
audited. The summary is `shipments.md` in the same table directory; source data
and SHA-256 metadata remain in the cancellation analysis data directory.

## CMPU first-order-line Sankey (REFNUM 14)

```bash
make cmpu-prescription-first-order-status
make cmpu-prescription-first-order-status START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
make cmpu-prescription-first-order-status CACHED=1
make cmpu-prescription-first-order-status PRINT_SQL=1
.venv/bin/python -m pytest -q tests/test_cmpu_first_order_line_status.py
```

REFNUM 14 now uses `src/sql/cmpu_first_order_line_status.sql` and
`EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP`. Join prescriptions using
**FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID**.
There is no RX_ID join to the order-line source and no dependency on ECOM.ORDERS.

Count each matched **(ORDER_ID, ORDER_LINE_ID) once**, collapsing the source's
shipment rows before joining. Prescriptions without first-order keys, invalid
item IDs or unmatched order lines appear in the audit and association details;
they are excluded from the Sankey denominator. Multiple prescriptions sharing
a line count once. Conflicting channel/upload/status classifications for a
shared line fail validation, as do conflicting shipment statuses or
duplicate shipment/line source keys. Do not interpret shipment rows as lines.

Defaults retain CMPU vet-diet prescriptions created August 15–October 14,
2026 and upload search August 1–October 14 (UTC). Starts are inclusive; END_DATE
is exclusive for both windows. Upload start must not exceed prescription start.
No prescription-status/deletion or order-placement-date filter is applied.

The full and CUSTOMER_UPLOAD figures use the order: **approval channel → first-order cancel
reason → first-order line status → item block reason → matching upload or not**.
Cancel reason is the raw trimmed ORDER_CANCEL_REASON; blank/null reasons appear
as `[No cancellation reason recorded]` and do not imply an uncanceled order.
The line stage uses ORDER_ORDER_LINE_STATUS codes directly (C, D, R, S, X),
with blank/null codes shown as `[Unknown line status]`. The source has no separate
line-cancellation-reason field in this analysis.

Actual ORDER_ITEM_BLOCK_REASON is shown only for known non-D line statuses.
D lines use `[Not applicable: status D]` and unknown statuses use an explicit
not-applicable node so every line still reaches the final upload split.
Blank/null actual block reasons appear as `[No block reason recorded]`.
Conflicting shipment statuses, cancellation reasons or block reasons fail validation.

The third figure, `sankey-non-d.png`, includes only CUSTOMER_UPLOAD lines with a
known non-D final line status. Its percentages use that restricted denominator. This figure
omits the explicit line-status column: channel → cancel reason → item block →
upload presence. It retains all non-D statuses (including C/R/S), with status
labels on the separate block/upload paths; it does not filter to X only. Column
headers identify Approval channel, First-order cancel reason, Item block reason
and Matching upload; visible node labels omit those repeated prefixes. The
cancel-reason stage uses purple and the item-block stage light blue, replacing
the gray defaults. Full node IDs remain in Mermaid sources and flow tables.
Full and CUSTOMER_UPLOAD figures retain their respective line denominators.
The same source cache can be reused with CACHED=1.

Upload presence retains DIET_PRESCRIPTION upload entities matched on expanded
RX_ID and numeric CUSTOMER_ID. Repeated uploads are deduplicated. No uploaded-file,
association flag or upload-after-creation requirement is applied; a matching
entity does not independently verify a file. Source-key audits cover the entire
upload window.

Item-block nodes and final upload nodes are separate for each line status.
For example X and D each have their own Has matching upload / No matching upload
endpoints. Block-reason nodes retain the status too, preventing X/D paths from
merging before the final split. Counts and percentages retain each figure's
whole-population denominator, not the individual status subtotal.

All four transitions in each figure conserve its distinct-line population.
Do not add the transition totals. Node and flow percentages use the figure's
whole population, rounded to two decimal places, rather than the parent node.

Older artifacts used `cmpu-first-order-line-status/<start>_<exclusive-end>/`, with
`_uploads-from-<upload-start>` when starts differ, followed by `_line-status`
for the prior status-only figures. The current four-stage figures use
`_line-status-non-d-block-reasons`; their source cache uses `_block-reasons`.
Previous all-status block-reason figures remain under `_line-status-block-reasons`. Earlier
figures and their extracts are preserved. The previous prescription-count
artifacts remain under `cmpu-prescription-first-order-status/`.

- `data/`: source Parquet, extraction timestamp, warehouse and SHA-256
  fingerprints. Rendered SQL and SQL history now use `src/autogenerated/`.
  Cached mode requires unchanged SQL/dates/data.
- `outputs/tables/`: association details, distinct order lines, full/focused
  distributions and flows (including block reason), non-D-focused distributions,
  flows and line details, non-D block-reason totals,
  eligibility/source audits and order-vs-line-status table.
- `src/diagrams/<start>_<last-prescription-day>/`: generated full, CUSTOMER_UPLOAD,
  and non-D-focused Mermaid source data. Dates are inclusive.
- `outputs/diagrams/<start>_<last-prescription-day>/`: transparent PNGs, titled
  SVGs and companion notes with descriptive filenames. Existing styling is retained.

`PRINT_SQL=1` validates dates and prints SQL without side effects; `CACHED=1`
regenerates tables/figures without Snowflake. Fresh queries use the repository's
read-only rxp-sql runner and browser SSO. Cortex is not used. The separate
order-to-approval timing analysis is unchanged by this REFNUM 14 revision.

## First order to first-usage approval distributions

```bash
make cmpu-order-to-approval-distributions
make cmpu-order-to-approval-distributions START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
make cmpu-order-to-approval-distributions CACHED=1
make cmpu-order-to-approval-distributions PRINT_SQL=1
.venv/bin/python -m pytest -q tests/test_cmpu_order_to_approval_distributions.py
```

Select CMPU vet-diet prescriptions with approval channel CUSTOMER_UPLOAD. Defaults
cover prescription creation August 15–October 14 and uploads August 1–October 14,
2026 (UTC, end date exclusive). Match DIET_PRESCRIPTION upload entities using
expanded RX_ID and numeric CUSTOMER_ID; repeated uploads cannot multiply rows.
Only FIRST_ORDER_ID is used. Require a matched order with known status other
than X and both timestamps; duration is FIRST_USAGE_APPROVED_DATETIME minus
ORDER_PLACED_DTTM in hours. There is no approval-date, prescription-status or
deletion filter. Negative values and the entire observed range are retained.
Order status reflects the extraction snapshot. Upload presence does not require
upload before approval and does not establish a causal effect.

Two stacked histograms use prescription counts, shared axes, and integer-aligned
one-hour intervals [lower, upper). A separate PNG table gives N, minimum, 25th,
median, 75th and 95th percentiles in hours, using unbinned linear interpolation.
Empty groups are labeled; an entirely empty eligible cohort produces no figures.

Outputs use `cmpu-order-to-approval-distributions/<start>_<exclusive-end>_uploads-from-<upload-start>/`
(the suffix is omitted when upload and prescription starts coincide):
- `data/`: prescription-level Parquet, executed SQL/history, extraction metadata,
  warehouse and SQL/Parquet fingerprints; cached mode requires unchanged inputs.
- `outputs/charts/`: transparent `distributions.png`, `statistics.png`, README.
- `outputs/tables/`: Markdown prescription details, one-hour bins, statistics,
  eligibility by upload group and upload-source audits. Eligibility exclusions
  are mutually exclusive; negative and over-24-hour durations are audit subsets.

The script rejects duplicate source keys and UTC/Eastern order timestamp
inconsistencies above one second. It checks missing Eastern companions separately.
Missing approval is excluded and never counted as a zero-hour approval.

## First-order-line timing distributions (REFNUM 16)

```bash
make cmpu-first-order-line-approval-distribution
make cmpu-first-order-line-approval-distribution WITH_UPLOAD=1
make cmpu-first-order-line-upload-distribution CACHED=1
make cmpu-upload-to-approval-distribution CACHED=1
make cmpu-upload-to-approval-distribution PRINT_SQL=1
```

Defaults select CMPU vet-diet CUSTOMER_UPLOAD prescriptions created August 15
through October 14, 2026 UTC. `START_DATE` is inclusive and `END_DATE=2026-10-15`
is exclusive. Upload-matched analyses search DIET_PRESCRIPTION upload entities
in `[UPLOAD_START_DATE, END_DATE + 11 days)`, defaulting to August 1 through
October 25 inclusive. Approval timestamps have no date limit. The overall
approval analysis does not require a matching upload.

Join the certified `ORDER_LINE_COST_MEASURES_RXP` view on both
`FIRST_ORDER_ID = ORDER_ID` and numeric `FIRST_ORDERITEM_ID = ORDER_LINE_ID`.
Count each distinct matched order/line pair once, requiring current
`ORDER_ORDER_LINE_STATUS = 'D'`. Collapse shipment rows using the latest populated
approval; conflicting statuses or creation timestamps reject the extract,
including missing/populated mixtures. UTC/Eastern creation companions must
agree within one second where populated. Missing companions are audited.

The three targets calculate hours as follows:

| Target | Timing difference | Negative durations |
| --- | --- | --- |
| `cmpu-first-order-line-approval-distribution` | Latest approval minus line creation | Retained |
| `cmpu-first-order-line-upload-distribution` | Earliest matching upload entity creation minus line creation | Excluded |
| `cmpu-upload-to-approval-distribution` | Latest approval minus earliest matching upload entity creation | Excluded |

Upload entities match by expanded RX_ID and numeric CUSTOMER_ID; the earliest
matching entity within the upload search window supplies the upload time.
Multiple uploads cannot multiply lines. Matching does not establish file
presence and need not precede approval or follow line creation. Both timing
endpoints are required; the upload-minus-line calculation does not require
approval. Excluded negatives remain in details and eligibility audits. Zero
and all nonnegative outliers are retained.

Every target produces a transparent Altair count histogram with integer-aligned
one-hour bins `[lower, upper)` and an exact empirical cumulative distribution
with labeled verticals at 24, 72, 144 and 240 hours. The full observed eligible
range is shown. Empty populations produce tables and remove stale figures.
Statistics use unbinned durations and linear interpolation: N, minimum, p25,
median, p75 and p95. Histogram and cumulative totals reconcile to eligible
unique lines. Missing keys, unmatched lines, status exclusions, missing timing
endpoints and upload-source identifier quality are audited at explicit grains.

Charts live directly in `outputs/charts/<start>_<last-prescription-day>/`, using
inclusive dates. For the default run this is `outputs/charts/2026-08-15_2026-10-14/`.
Filenames identify the measure, upload window, negative filter and figure type:

- `cmpu-d-lines_line-creation-to-upload_uploads-2026-08-01_2026-10-25_nonnegative_histogram.png`
- `cmpu-d-lines_line-creation-to-upload_uploads-2026-08-01_2026-10-25_nonnegative_cumulative.png`

Each analysis has matching Markdown notes, and the target prints their path.
Markdown associations, unique lines, eligibility, hourly counts, cumulative
counts/fractions and statistics go under `outputs/tables/cmpu-first-order-line-approval-distribution/`.
Their dated variant directories distinguish measures and filters.

SQL templates live in `src/sql/`: `cmpu_first_order_line_approval_distribution.sql`
and `cmpu_upload_to_max_approval_extract.sql`. Rendered queries and execution
history live under `src/autogenerated/cmpu-first-order-line-approval-distribution/`.
The complete dated query is named `cmpu_upload_to_max_approval_extract.sql` for
upload-matched extracts. SQL-only mode validates dates and prints SQL without
creating files. Fresh execution uses the read-only Snowflake runner with SSO.

Source Parquet, extraction metadata and SQL/Parquet SHA-256 fingerprints remain
under `data/cmpu-first-order-line-approval-distribution/`. Upload variants include
`_uploads-end-2026-10-26` in their identity to distinguish the extended window.
The three upload-matched measures share the same source extract. `CACHED=1`
verifies SQL, dates and the extract fingerprint without querying Snowflake.
`START_DATE`, exclusive `END_DATE` and `UPLOAD_START_DATE` are supported overrides.

The corrected cohort retains 104,307 prescriptions, of which 33,220 have uploads.
There are 24,944 D-status lines with uploads: the upload-to-approval analysis
includes 24,938 after six missing-approval exclusions (median about 49 seconds,
p75 4.77 hours, p95 25.07 hours). The upload-minus-line analysis includes 24,701
after excluding 243 negative durations (median 22.76 hours). Rendered figures
and notes using uploads only through October 14 were removed at user request;
underlying data, tables and source files remain available.

## Sankeys with the extended upload window

```bash
make cmpu-first-order-line-status
make cmpu-first-order-line-status CACHED=1
make cmpu-first-order-line-status PRINT_SQL=1
# Existing target remains an alias:
make cmpu-prescription-first-order-status CACHED=1
```

The Sankeys use prescriptions in `[START_DATE, END_DATE)` and uploads in
`[UPLOAD_START_DATE, END_DATE + 11 days)`: August 15–October 14 and August 1–October
25 inclusive by default. The three views are all channels, CUSTOMER_UPLOAD and
non-D CUSTOMER_UPLOAD lines. Existing join, status, block and flow rules above
remain unchanged. Titles and table notes show both date ranges.

Mermaid files live directly in `src/diagrams/2026-08-15_2026-10-14/`, named
`cmpu-first-order-lines_<scope>_uploads-2026-08-01_2026-10-25_sankey.mmd`,
where scope is `all`, `customer-upload` or `non-d`. Transparent PNGs and titled
SVGs use the same descriptive basenames under
`outputs/diagrams/2026-08-15_2026-10-14/`. Generated sources and figures are
ignored by Git. Targets print both directories. Source extracts remain under
`data/`; rendered SQL and execution history use
`src/autogenerated/cmpu-first-order-line-status/`. Cache identity includes the
exclusive upload end date, preserving earlier extracts.

The refreshed Sankey cohort has 113,608 prescriptions and 103,514 matched
unique lines, including 95,071 CUSTOMER_UPLOAD lines. Its 24,944 CUSTOMER_UPLOAD
D-status lines with uploads exactly reconcile to the timing analysis before
missing-approval exclusions.
