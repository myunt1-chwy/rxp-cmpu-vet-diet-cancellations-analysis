"""Format inspectable Markdown tables without an additional dependency."""


def markdown_table(frame):
    def cell(value):
        return str(value).replace('|', r'\|').replace('\n', ' ')

    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(cell(value) for value in row) + ' |'
                      for row in frame.itertuples(index=False, name=None)])
