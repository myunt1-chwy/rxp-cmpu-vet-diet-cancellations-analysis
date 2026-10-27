"""Format inspectable Markdown tables without an additional dependency."""


def markdown_table(frame):
    def cell(value):
        return str(value).replace('|', r'\|').replace('\n', ' ')

    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(cell(value) for value in row) + ' |'
                      for row in frame.itertuples(index=False, name=None)])


def table_layout(root, analysis, period):
    """Flat dated table directory and a filename prefix preserving run variants."""
    from datetime import date, timedelta
    from pathlib import Path

    start = date.fromisoformat(period[:10])
    end = date.fromisoformat(period[11:21])
    if period[10:11] != '_' or start >= end:
        raise ValueError('require an inclusive start and later exclusive end')
    variant = period[21:].strip('_')
    prefix = f'{analysis}_{variant}_' if variant else f'{analysis}_'
    return Path(root) / 'outputs/tables' / f'{start}_{end - timedelta(days=1)}', prefix
