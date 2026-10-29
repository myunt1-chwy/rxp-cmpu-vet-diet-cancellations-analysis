"""REFNUM 51: entity-grain elapsed time from creation to current state change."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
NAME = 'cmpu-upload-entity-state-change-distributions'
TEMPLATE = ROOT / 'src/sql/cmpu_upload_entity_state_change_distributions.sql'
VERSION = 1
POPULATIONS = ('all-study-linked', 'aged-order')
ENTITY_COLUMNS = ['upload_id', 'upload_customer_id', 'state_name', 'created_ts_utc', 'state_changed_ts_utc']
PALETTE = ['#4E79A7', '#F28E2C', '#E15759', '#76B7B2', '#59A14F', '#B07AA1', '#9C755F', '#EDC948', '#FF9DA7', '#BAB0AC']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parameters(start, end, upload_start, as_of):
    start, end, upload_start, as_of = map(date.fromisoformat, [start, end, upload_start, as_of])
    if start >= end or upload_start > start or as_of < end:
        raise ValueError('require upload start <= study start < exclusive study end <= as-of date')
    return dict(start_date=str(start), end_date=str(end), upload_start_date=str(upload_start),
                upload_end_date=str(end + timedelta(days=11)), as_of_date=str(as_of))


def render_sql(start, end, upload_start, as_of):
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        **parameters(start, end, upload_start, as_of))


def validate(frame, params):
    """Validate source versions before reducing joins to one row per entity."""
    f = frame.rename(columns=str.lower).copy()
    for col in ['created_ts_utc', 'state_changed_ts_utc', 'rx_creation_datetime', 'order_cancel_time']:
        f[col] = pd.to_datetime(f[col], utc=True, format='mixed', errors='raise')
    if f.upload_id.isna().any():
        raise ValueError('missing UPLOAD_ID')
    if f.groupby('upload_id')[ENTITY_COLUMNS[1:]].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting entity states, timestamps or customers')
    matched = f.matched_rx_id.notna()
    rx = f.loc[matched]
    if (rx.groupby('matched_rx_id')[['rx_customer_id', 'rx_creation_datetime', 'first_order_id',
                                      'first_orderitem_id', 'first_order_line_id']]
            .nunique(dropna=False).gt(1).any().any()):
        raise ValueError('conflicting prescription source values')
    if (rx.upload_rx_id.ne(rx.matched_rx_id).any() or rx.upload_customer_id.ne(rx.rx_customer_id).any()
            or not rx.upload_rx_id.str.fullmatch(r'[A-Za-z0-9_-]+').all()):
        raise ValueError('invalid RX/customer match')
    if not rx.rx_creation_datetime.between(pd.Timestamp(params['start_date'], tz='UTC'),
            pd.Timestamp(params['end_date'], tz='UTC'), inclusive='left').all():
        raise ValueError('prescription outside study window')
    created = f.created_ts_utc.dropna()
    if not created.between(pd.Timestamp(params['upload_start_date'], tz='UTC'),
                           pd.Timestamp(params['upload_end_date'], tz='UTC'), inclusive='left').all():
        raise ValueError('entity creation outside discovery window')
    line = f.matched_order_id.notna() | f.matched_order_line_id.notna()
    if (not f.loc[line, ['matched_order_id', 'matched_order_line_id']].notna().all().all()
            or f.loc[line, 'matched_order_id'].ne(f.loc[line, 'first_order_id']).any()
            or f.loc[line, 'matched_order_line_id'].ne(f.loc[line, 'first_order_line_id']).any()):
        raise ValueError('first-order join keys disagree')
    if (not f.loc[line, 'reason_variants'].eq(1).all()
            or f.loc[line, 'cancel_variants'].gt(1).any()):
        raise ValueError('conflicting first-order cancellation source values')
    if (f.loc[line].groupby(['matched_order_id', 'matched_order_line_id'])[
            ['order_cancel_reason', 'order_cancel_time']].nunique(dropna=False).gt(1).any().any()):
        raise ValueError('conflicting first-order cancellation associations')
    expected = (matched & line & f.order_cancel_reason.astype('string').str.strip().str.lower().eq('aged order')
                & f.order_cancel_time.le(pd.Timestamp(params['as_of_date'], tz='UTC'))).fillna(False)
    if not f.aged_association.eq(expected).all():
        raise ValueError('aged cutoff evidence disagrees')
    f['aged_association'] = expected
    # Full source keeps expansions outside the study; associations contain only
    # matching prescriptions, with identical entity/prescription/line rows collapsed.
    associations = f.loc[matched].drop_duplicates(
        ['upload_id', 'matched_rx_id', 'first_order_id', 'first_order_line_id']).copy()
    counts = associations.groupby('upload_id').agg(
        matched_prescriptions=('matched_rx_id', 'nunique'), aged_entity=('aged_association', 'any'))
    entities = f[ENTITY_COLUMNS].drop_duplicates('upload_id').merge(counts, on='upload_id', how='left')
    if entities.matched_prescriptions.isna().any():
        raise ValueError('discovered entity has no matching study prescription')
    entities['missing_creation'] = entities.created_ts_utc.isna()
    entities['missing_state_change'] = entities.state_changed_ts_utc.isna()
    entities['unknown_discovery_window'] = entities.missing_creation
    entities['elapsed_hours'] = (entities.state_changed_ts_utc - entities.created_ts_utc).dt.total_seconds() / 3600
    entities['usable_duration'] = entities.elapsed_hours.notna()
    entities['negative_duration'] = entities.elapsed_hours.lt(0)
    # JSON string labels keep literal states distinguishable from missing states.
    entities['state_label'] = entities.state_name.map(lambda s: '[NULL state]' if pd.isna(s) else json.dumps(s))
    audit = pd.DataFrame([
        ('source association rows', len(f)), ('distinct source association rows', len(f.drop_duplicates())),
        ('identical source/expansion rows collapsed', len(f)-len(f.drop_duplicates())),
        ('matched prescription associations', len(associations)),
        ('unmatched RX expansions retained in source', int((~matched).sum())),
        ('all entities', len(entities)), ('aged entities', int(entities.aged_entity.sum())),
        ('entities with multiple matched prescriptions', int(entities.matched_prescriptions.gt(1).sum())),
    ], columns=['measure', 'count'])
    return associations, entities, audit


def statistics(entities, states):
    rows = []
    for state in states:
        group = entities.loc[entities.state_label.eq(state)]
        values = group.loc[group.usable_duration, 'elapsed_hours']
        q1, median, q3 = values.quantile([.25, .5, .75], interpolation='linear')
        iqr = q3-q1
        inside = values.loc[values.between(q1-1.5*iqr, q3+1.5*iqr)]
        low, high = inside.min(), inside.max()
        rows.append(dict(state_label=state, entities=len(group), usable=len(values),
            missing_creation=int(group.missing_creation.sum()), missing_state_change=int(group.missing_state_change.sum()),
            missing_duration=int((~group.usable_duration).sum()), negative=int(group.negative_duration.sum()),
            mean=values.mean(), minimum=values.min(), q1=q1, median=median, q3=q3, maximum=values.max(),
            lower_fence=q1-1.5*iqr, upper_fence=q3+1.5*iqr, lower_whisker=low, upper_whisker=high,
            outliers=int((values.lt(low) | values.gt(high)).sum())))
    return pd.DataFrame(rows)


def boxplot(entities, stats, states, domain, title, subtitle):
    """Explicit marks use exported linear quantiles and observed Tukey whiskers."""
    s = stats.copy()
    s['count_label'] = s.apply(lambda r: f"n={r.usable:,} / {r.entities:,}", axis=1)
    colors = alt.Scale(domain=states, range=[PALETTE[i % len(PALETTE)] for i in range(len(states))])
    base = alt.Chart(alt.Data(values=json.loads(s.to_json(orient='records')))).encode(
        y=alt.Y('state_label:N', sort=states, title='Final state', axis=alt.Axis(labelLimit=260)),
        color=alt.Color('state_label:N', scale=colors, legend=None))
    scale = alt.Scale(type='symlog', constant=1/3600, domain=domain, nice=False)
    tick_hours = [1/60, 5/60, 30/60, 1, 6, 24, 48, 72, 120, 240]
    axis = alt.Axis(values=[value for value in tick_hours if domain[0] <= value <= domain[1]],
        labelExpr="datum.value < 1 ? [format(datum.value * 60, '.0f'), datum.value == 1/60 ? 'minute' : 'minutes'] : [format(datum.value, '.0f'), datum.value == 1 ? 'hour' : 'hours']",
        labelAngle=0, labelOverlap=False, labelLineHeight=16, labelPadding=8)
    def x(field):
        return alt.X(field+':Q', title='Time from entity creation to current state change', scale=scale, axis=axis)
    whisker = base.mark_rule(strokeWidth=2).encode(x=x('lower_whisker'), x2='upper_whisker:Q')
    caps = [base.mark_tick(orient='vertical', size=16, thickness=2).encode(x=x(field))
            for field in ['lower_whisker', 'upper_whisker']]
    box = base.mark_bar(size=28, opacity=.65).encode(x=x('q1'), x2='q3:Q')
    median = base.mark_tick(orient='vertical', size=30, thickness=3).encode(
        x=x('median'), color=alt.value('#222222'))
    usable = entities.loc[entities.usable_duration].merge(stats[['state_label','lower_whisker','upper_whisker']], on='state_label')
    outliers = usable.loc[usable.elapsed_hours.lt(usable.lower_whisker) | usable.elapsed_hours.gt(usable.upper_whisker)]
    points = alt.Chart(alt.Data(values=outliers[['state_label','elapsed_hours']].to_dict('records'))).mark_circle(
        size=20, opacity=.35).encode(x=x('elapsed_hours'),
            y=alt.Y('state_label:N', sort=states), color=alt.Color('state_label:N', scale=colors, legend=None))
    counts = base.mark_text(align='left', dx=12, color='#333333', fontSize=13).encode(
        x=alt.value(1500), text='count_label:N', color=alt.value('#333333'))
    zero = alt.Chart(pd.DataFrame({'zero':[0]})).mark_rule(color='#888888', strokeDash=[3,3]).encode(x=x('zero'))
    return (zero + whisker + caps[0] + caps[1] + box + median + points + counts).properties(
        width=1500, height=max(200, len(states)*56), padding={'left':10,'right':160,'top':10,'bottom':10},
        title=alt.Title(title, subtitle=subtitle, anchor='start', fontSize=23, subtitleFontSize=14, offset=18)
    ).configure(background='transparent', font='Arial', axis=alt.AxisConfig(labelFontSize=13, titleFontSize=16,
        titlePadding=14)).configure_view(stroke=None)


def write_outputs(frame, metadata, directory, charts, tables):
    params = metadata['parameters']
    associations, entities, audit = validate(frame, params)
    states = sorted(entities.state_label.unique()) or ['[No entities]']
    values = entities.loc[entities.usable_duration, 'elapsed_hours']
    domain = [min(float(values.min()), 0.) if len(values) else 0., max(float(values.max()), 0.) if len(values) else 0.]
    # Shared full-range domain including zero; pad for endpoint marks/singletons.
    domain = [domain[0]*1.1 if domain[0]<0 else -1/3600, domain[1]*1.1 if domain[1]>0 else 1/3600]
    for path in [directory, charts, tables]:
        path.mkdir(parents=True, exist_ok=True)
    exports = {'associations': associations, 'audit': audit}
    note = ('One UPLOAD_ID per population. All current states and all matching entities; no ACCEPTED or 60-second filter. '
        'Elapsed hours = (STATE_CHANGED_TS_UTC − CREATED_TS_UTC) / 3600 seconds. '
        'Negative durations remain usable and flagged. Missing timestamps remain in exports and counts but not duration marks. '
        'Null creation dates have unknown discovery-window membership and are retained for audit. '
        'Aged membership requires any matched first-order pair with normalized reason Aged Order and cancellation at/before '
        f"{params['as_of_date']} 00:00 UTC. Current state changes are not censored at cancellation or cutoff. "
        'Quantiles use linear interpolation; whiskers are observed extrema within 1.5×IQR fences. All outliers retained. '
        'Shared symmetric-log hours axis, linear-region constant one second. n = usable / total entities. '
        f"Prescription window [{params['start_date']}, {params['end_date']}); upload creation window "
        f"[{params['upload_start_date']}, {params['upload_end_date']}) UTC. "
        f"Extracted {metadata['extracted_at_utc']}; source SHA-256 {metadata['parquet_sha256']}.\n\n")
    for population in POPULATIONS:
        selected = entities if population == POPULATIONS[0] else entities.loc[entities.aged_entity]
        population_audit = [('entities', len(selected)),
            ('null states', int(selected.state_name.isna().sum())),
            ('zero durations', int(selected.elapsed_hours.eq(0).sum()))]
        population_audit += [(column, int(selected[column].sum())) for column in
            ['usable_duration', 'missing_creation', 'missing_state_change', 'unknown_discovery_window', 'negative_duration']]
        audit = pd.concat([audit, pd.DataFrame([(population+': '+key, value) for key, value in population_audit],
            columns=['measure','count'])], ignore_index=True)
        stats = statistics(selected, states)
        if stats.entities.sum() != len(selected) or stats.usable.sum() != selected.usable_duration.sum():
            raise ValueError('state counts do not reconcile')
        exports[population+'-entities'] = selected
        exports[population+'-statistics'] = stats
        subtitle = [f"CMPU vet diet · CUSTOMER_UPLOAD · Rx {params['start_date']} to {params['end_date']} exclusive (UTC)",
            f"Uploads {params['upload_start_date']} to {params['upload_end_date']} exclusive (UTC)",
            f"{len(selected):,} entities · {int(selected.usable_duration.sum()):,} usable durations · n = usable / total",
            'Median, quartiles, 1.5×IQR whiskers and all outliers · One-second linear region around zero']
        if population == POPULATIONS[1]:
            subtitle.insert(2, f"Aged first-order cancellation ≤ {params['as_of_date']} 00:00 UTC · Current entity states")
        chart = boxplot(selected, stats, states, domain,
            'Upload entity time to current state · '+('All study-linked entities' if population == POPULATIONS[0] else 'Aged-order entities'), subtitle)
        chart.save(charts/f'{population}.png', scale_factor=2)
        write_text(tables/f'{population}-statistics.md', f'# {population} statistics\n\n'+note+markdown_table(stats)+'\n')
    aged = exports['aged-order-entities']
    exports['audit'] = audit
    if not set(aged.upload_id).issubset(set(entities.upload_id)) or entities.upload_id.duplicated().any():
        raise ValueError('population reconciliation failed')
    for name, data in exports.items():
        data.to_parquet(directory/f'{name}.parquet', index=False)
    write_text(tables/'summary.md', '# REFNUM 51: upload entities\n\n'+note+markdown_table(audit)+'\n\n'
        '## Entity preview (first 25; complete populations in data/)\n\n'+markdown_table(entities.head(25))+'\n')
    write_text(tables/'audit.md', '# Source audit\n\n'+note+markdown_table(audit)+'\n')
    write_text(directory/'analysis.json', json.dumps(dict(metadata, version=VERSION, populations=POPULATIONS,
        shared_state_order=states, shared_hours_domain=domain, symlog_constant_hours=1/3600,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        exports={name+'.parquet':digest(directory/f'{name}.parquet') for name in exports}), indent=2)+'\n')
    return audit


def load_source(params, sql, cached):
    identity = dict(version=VERSION, parameters=params, populations=POPULATIONS,
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(), implementation_sha256=digest(Path(__file__)))
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    period = f"{params['start_date']}_{params['end_date']}_uploads-{params['upload_start_date']}_{params['upload_end_date']}_asof-{params['as_of_date']}_{key}"
    directory = ROOT/'data'/NAME/period
    parquet, manifest = directory/'source.parquet', directory/'source.json'
    if cached:
        metadata = json.loads(manifest.read_text())
        if (metadata.get('identity') != json.loads(json.dumps(identity)) or metadata.get('sql') != sql
                or metadata.get('parquet_sha256') != digest(parquet)):
            raise ValueError('cached SQL, dates, populations or source fingerprint differs; rerun fresh')
        frame = pd.read_parquet(parquet)
        validate(frame, params)
    else:
        directory.mkdir(parents=True, exist_ok=True)
        query_dir = ROOT/'src/autogenerated'/NAME/period
        query_dir.mkdir(parents=True, exist_ok=True)
        query = query_dir/'extract.sql'
        write_text(query, sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable, str(ROOT/'.agents/skills/rxp-sql/scripts/run_snowflake_query.py'),
            str(query), '--output-parquet', str(parquet.relative_to(ROOT)),
            '--sql-log-dir', str((query_dir/'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
        frame = pd.read_parquet(parquet)
        validate(frame, params)
        metadata = dict(identity=identity, parameters=params, sql=sql, parquet_sha256=digest(parquet),
                        extracted_at_utc=datetime.now(timezone.utc).isoformat())
        write_text(manifest, json.dumps(metadata, indent=2)+'\n')
    return frame, metadata, directory, period


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True, help='Exclusive prescription end; uploads extend 11 days.')
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
@click.option('--as-of-date', default='2026-10-27', show_default=True, help='Inclusive aged cancellation cutoff at 00:00 UTC.')
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, upload_start_date, as_of_date, cached, print_sql):
    try:
        params = parameters(start_date, end_date, upload_start_date, as_of_date)
        sql = render_sql(start_date, end_date, upload_start_date, as_of_date)
        if print_sql:
            click.echo(sql)
            return
        frame, metadata, directory, period = load_source(params, sql, cached)
        dated = f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
        charts = ROOT/'outputs/charts'/dated/NAME
        tables = ROOT/'outputs/tables'/dated/NAME
        audit = write_outputs(frame, metadata, directory, charts, tables)
        click.echo(audit.to_string(index=False))
        click.echo(f'Charts: {charts}\nTables: {tables}\nComplete data: {directory}')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()
