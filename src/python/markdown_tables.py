"""Format inspectable Markdown tables without an additional dependency."""


MAX_MARKDOWN_BYTES = 1_000_000
MAX_TABLE_BYTES = 900_000
PREVIEW_BYTES = 64_000
PREVIEW_ROWS = 25


def markdown_table(frame):
    """Render a full small table or an explicitly labeled, bounded preview."""
    def cell(value):
        return str(value).replace('|', r'\|').replace('\\n', ' ')

    lines = ['| ' + ' | '.join(frame.columns) + ' |',
             '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |']
    size = len('\n'.join(lines).encode('utf-8'))
    preview = list(lines) if size <= PREVIEW_BYTES else []
    preview_size = size
    preview_rows = 0
    for row in frame.itertuples(index=False, name=None):
        line = '| ' + ' | '.join(cell(value) for value in row) + ' |'
        row_bytes = len(line.encode('utf-8')) + 1
        if preview and preview_rows < PREVIEW_ROWS and preview_size + row_bytes <= PREVIEW_BYTES:
            preview.append(line)
            preview_rows += 1
            preview_size += row_bytes
        if size + row_bytes > MAX_TABLE_BYTES:
            notice = (f'> **Table preview:** {preview_rows:,} of {len(frame):,} rows shown; '
                      'the full table exceeds the Markdown size budget. '
                      'Use the associated data/ exports for complete records.')
            return notice + ('\n\n' + '\n'.join(preview) if preview else '')
        lines.append(line)
        size += row_bytes
    if size > MAX_TABLE_BYTES:
        return f'> Table omitted: {len(frame):,} rows; column headings exceed the Markdown size budget.'
    return '\n'.join(lines)


def write_text(path, text, encoding=None, errors=None, newline=None):
    """Preserve text exports, enforcing a 1 MB limit on complete Markdown files."""
    from pathlib import Path

    path = Path(path)
    if path.suffix.lower() == '.md':
        codec = encoding or 'utf-8'
        encoded = text.encode(codec, errors or 'strict')
        import os
        line_ending = os.linesep if newline is None else newline
        file_bytes = (text.replace('\n', line_ending).encode(codec, errors or 'strict')
                      if line_ending not in ('', '\n') else encoded)
        if len(file_bytes) > MAX_MARKDOWN_BYTES:
            preview = encoded[:PREVIEW_BYTES].decode(codec, errors='ignore')
            if '\n' in preview:
                preview = preview.rsplit('\n', 1)[0]
            text = ('> **Size-limited Markdown export:** the full document exceeded 1 MB. '
                    'Only a preview is shown. Use the associated data/ exports for complete records.\n\n' + preview)
        encoding = codec
    return path.write_text(text, encoding=encoding, errors=errors, newline=newline)


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
