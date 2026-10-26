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

## CMPU prescription first-order Sankey (REFNUM 14)

```bash
make cmpu-prescription-first-order-status
make cmpu-prescription-first-order-status START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
make cmpu-prescription-first-order-status CACHED=1
make cmpu-prescription-first-order-status PRINT_SQL=1
```

Defaults select prescriptions created August 15 through October 14, 2026,
and search uploads from August 1 through October 14, UTC. `START_DATE` and
`UPLOAD_START_DATE` are inclusive; `END_DATE` is exclusive for both windows.
Upload start must be on or before prescription start. Dates are explicit:
these defaults implement the requested August 1/August 15 boundaries.
`PRINT_SQL=1` validates dates and prints the SQL
without querying, writing files or invoking Docker. `CACHED=1` skips Snowflake
and checks that the SQL, dates and extract SHA-256 match before regenerating
tables and rendering. A fresh run uses the repository's read-only Snowflake
runner and browser SSO. Cortex is not used.

Select CMPU vet-diet prescriptions, without deletion or prescription-status
filters. Count each RX_ID once. Use only FIRST_ORDER_ID for the order join;
there is no order-placement-date requirement. Latest ORDER_STATUS = X means
canceled, grouped as Aged Order, Customer Initiated Cancellation, Customer
Request, Other cancellation reason, or Canceled - missing reason. Retain Not
canceled, No first order ID, First order not found, Unknown order status and
unknown approval channels explicitly. A NULL cancellation reason alone does
not imply that an order was not canceled.

Upload presence means at least one DIET_PRESCRIPTION upload entity in the upload
search window matching both expanded RX_ID and numeric CUSTOMER_ID. Brace-delimited
IDs and repeated uploads are deduplicated. HAS_UPLOADED_FILE,
HAS_ASSOCIATED_RX and ASSOCIATED_RESOURCE_TYPE are not filters; a matching
entity does not independently verify a file. No upload-after-prescription
requirement is imposed. Missing/malformed upload identifiers are audited for
the whole upload window. Duplicate prescription, order or upload source keys
fail validation rather than silently selecting a record.

The three-stage Sankey shows approval channel → channel-specific matching
upload presence → first-order cancellation group. It is a categorical breakdown,
not a chronological sequence. Each stage totals the same prescription cohort;
the two transition totals must not be added together as prescriptions.

Artifacts use `cmpu-prescription-first-order-status/<start>_<exclusive-end>/`,
with `_uploads-from-<upload-start>` appended when upload and prescription starts
differ. Both windows are recorded in the metadata and diagram subtitles;
caches cannot be reused across different upload starts. Earlier same-window
results remain in their original directories. The audit separately counts
prescriptions matched only through uploads before prescription-cohort start.

- `data/`: rendered SQL, source and classified Parquet, extraction timestamp,
  warehouse and source fingerprints, plus SQL history.
- `outputs/tables/`: summary, full distribution, prescription details, flow
  counts and audits in Markdown.
- `outputs/diagrams/`: editable `sankey.mmd`, transparent `sankey.png` and README,
  plus a second `sankey-customer-upload.mmd`/`.png` restricted to approval channel
  CUSTOMER_UPLOAD. Both use approval channel → upload presence → first-order
  status/reason. The second diagram uses the same validated extract.

Focused `customer-upload-summary.md`, `customer-upload-distribution.md` and
`customer-upload-flows.md` tables accompany the second diagram; their
percentages use only CUSTOMER_UPLOAD prescriptions as the denominator.
Both diagrams label nodes with counts and percentages rounded to two decimals.
The main diagram uses all cohort prescriptions as its denominator; the focused
diagram uses only CUSTOMER_UPLOAD prescriptions, including at the final status
stage. Percentages are not conditional on the preceding node. Flow tables use
the same scope-specific denominators.
Each diagram includes a title with its scope, inclusive date range and
percentage denominator; titles are retained in the editable Mermaid source.
Because the Mermaid Sankey renderer does not draw frontmatter titles, the
pipeline adds a visible title band to its SVG output and exports the PNG using
Chromium/Puppeteer bundled in the same Mermaid Docker image, preserving SVG
colors and text styling. Titled SVG companions are saved alongside
both PNGs. Rendering and conversion are staged to preserve an existing PNG if
either step fails.
Node labels, including counts and percentages, are bold 21px (an additional
25% above the previous 16.8px labels). Titles remain 33.6px and subtitles
21.6px, with the same title-band spacing. The Mermaid label override is applied
before measuring the SVG so the enlarged labels fit the export.
Both diagrams use an adjusted multicolor palette: blue, orange, purple, pink,
coral and gray, with light blue replacing green tones. Matching-upload branches
are orange; no-matching-upload branches are light blue. Category colors stay
consistent between the full and focused diagrams. Links inherit their source node's color.
Links use normal blending at 75% opacity so SVG and PNG exports retain the
palette against a transparent background.

The existing Mermaid helper renders through `minlag/mermaid-cli:latest` in
Docker. Docker must already be installed and running; the target does not
install or start it. Render failures preserve the previous PNG and return an
error. An empty cohort produces tables and removes stale Sankey artifacts.

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_cmpu_prescription_first_order_status.py'
```
