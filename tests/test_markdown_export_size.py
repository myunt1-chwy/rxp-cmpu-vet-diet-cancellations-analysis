"""Byte-bounded Markdown rendering and a shared guard across all generators."""
import ast
from pathlib import Path

import pandas as pd
import pytest

from src.python import markdown_tables as output


def test_small_table_and_small_export_are_unchanged(tmp_path):
    table=output.markdown_table(pd.DataFrame({'name':['a|b'],'count':[3]}))
    assert table=='| name | count |\n| --- | --- |\n| a\\|b | 3 |'
    text='# Summary\n\n'+table+'\n'
    path=tmp_path/'summary.md'
    assert output.write_text(path,text)==len(text)
    assert path.read_text()==text


@pytest.mark.parametrize('name',['table.md','table.MD'])
def test_one_mb_exact_boundary_and_oversize_files(tmp_path,name):
    path=tmp_path/name
    exact='x'*output.MAX_MARKDOWN_BYTES
    output.write_text(path,exact)
    assert path.stat().st_size==output.MAX_MARKDOWN_BYTES
    assert path.read_text()==exact
    output.write_text(path,exact+'x')
    assert path.stat().st_size<=output.MAX_MARKDOWN_BYTES
    assert 'Size-limited Markdown export' in path.read_text()
    assert 'Only a preview is shown' in path.read_text()


def test_utf8_bytes_determine_the_limit_and_preview_stays_valid(tmp_path):
    path=tmp_path/'unicode.md'
    text='猫'*400_000  # 400k characters, 1.2 MB in UTF-8.
    output.write_text(path,text)
    assert path.stat().st_size<=output.MAX_MARKDOWN_BYTES
    assert 'Size-limited Markdown export' in path.read_text(encoding='utf-8')
    assert '\ufffd' not in path.read_text(encoding='utf-8')


def test_large_table_preview_does_not_change_full_parquet_data(tmp_path):
    frame=pd.DataFrame({'id':range(20_000),'value':['é'*40]*20_000})
    text=output.markdown_table(frame)
    assert '**Table preview:** 25 of 20,000 rows shown' in text
    assert len(text.encode('utf-8'))<output.MAX_MARKDOWN_BYTES
    assert '| 24 |' in text and '| 25 |' not in text
    frame.to_parquet(tmp_path/'full.parquet',index=False)
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'full.parquet'),frame)
    output.write_text(tmp_path/'table.md','# Details\n\n'+text)
    assert (tmp_path/'table.md').stat().st_size<=output.MAX_MARKDOWN_BYTES


def test_large_table_stops_formatting_before_materializing_all_rows():
    class HugeTable:
        columns=['value']
        visited=0
        def __len__(self):return 1_000_000
        def itertuples(self,**kwargs):
            for _ in range(len(self)):
                self.visited+=1
                yield ('x'*1000,)
    frame=HugeTable()
    text=output.markdown_table(frame)
    assert frame.visited<1000
    assert '1,000,000 rows' in text
    assert len(text.encode('utf-8'))<=output.MAX_MARKDOWN_BYTES


def test_single_huge_cell_or_heading_cannot_make_a_large_preview(tmp_path):
    for frame in [pd.DataFrame({'value':['x'*2_000_000]}),pd.DataFrame(columns=['x'*2_000_000])]:
        text=output.markdown_table(frame)
        assert len(text.encode('utf-8'))<=output.MAX_MARKDOWN_BYTES
        output.write_text(tmp_path/'table.md',text)
        assert (tmp_path/'table.md').stat().st_size<=output.MAX_MARKDOWN_BYTES


def test_file_guard_handles_multiple_individually_small_tables_and_notes(tmp_path):
    table=output.markdown_table(pd.DataFrame({'value':['x'*600_000]}))
    assert 'Table preview' not in table
    text='# Report\n\n'+table+'\n\n'+table
    output.write_text(tmp_path/'report.md',text)
    assert (tmp_path/'report.md').stat().st_size<=output.MAX_MARKDOWN_BYTES
    assert 'Size-limited Markdown export' in (tmp_path/'report.md').read_text()


@pytest.mark.parametrize('extension',['.sql','.json','.mmd','.svg','.txt'])
def test_non_markdown_text_is_not_truncated(tmp_path,extension):
    text='x'*(output.MAX_MARKDOWN_BYTES+1)
    path=tmp_path/('source'+extension)
    assert output.write_text(path,text)==len(text)
    assert path.read_text()==text


def test_active_generators_use_the_shared_writer_and_table_formatter():
    root=Path(__file__).resolve().parents[1]
    bypasses=[]
    for path in (root/'src/python').glob('*.py'):
        if path.name=='markdown_tables.py':continue
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='write_text':
                bypasses.append(f'{path.name}:{node.lineno}')
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='markdown_table':
                bypasses.append(f'duplicate formatter {path.name}:{node.lineno}')
    assert bypasses==[],bypasses


def test_limit_includes_newline_translation(tmp_path):
    path=tmp_path/'windows.md'
    text='a\n'*400_000  # 800k bytes in memory, 1.2 MB with CRLF file endings.
    output.write_text(path,text,newline='\r\n')
    assert path.stat().st_size<=output.MAX_MARKDOWN_BYTES
    assert 'Size-limited Markdown export' in path.read_text()
