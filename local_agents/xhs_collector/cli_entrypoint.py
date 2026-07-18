"""给 xiaohongshu-cli 注入「一周内 + 最多点赞」搜索过滤。"""
from xhs_cli import client_mixins

client_mixins._SEARCH_DEFAULT_FILTERS = [
    {"tags": ["popularity_descending"], "type": "sort_type"},
    {"tags": ["不限"], "type": "filter_note_type"},
    {"tags": ["一周内"], "type": "filter_note_time"},
    {"tags": ["不限"], "type": "filter_note_range"},
    {"tags": ["不限"], "type": "filter_pos_distance"},
]

from xhs_cli.cli import cli

if __name__ == "__main__":
    cli()
