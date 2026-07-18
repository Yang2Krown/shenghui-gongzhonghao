"""项目内的 xiaohongshu-cli 搜索入口。

0.6.4 已支持「最多点赞」排序，但命令行未暴露搜索时间筛选，
且内置 filters 默认为「不限」。这里在进入官方 CLI 前将搜索条件
锁定为「一周内 + 点赞从高到低」，其余登录、签名、输出逻辑仍由原 CLI 处理。
"""
from __future__ import annotations


XHS_SEARCH_FILTERS = [
    {"tags": ["popularity_descending"], "type": "sort_type"},
    {"tags": ["不限"], "type": "filter_note_type"},
    {"tags": ["一周内"], "type": "filter_note_time"},
    {"tags": ["不限"], "type": "filter_note_range"},
    {"tags": ["不限"], "type": "filter_pos_distance"},
]


def main() -> None:
    from xhs_cli import client_mixins

    client_mixins._SEARCH_DEFAULT_FILTERS = XHS_SEARCH_FILTERS
    from xhs_cli.cli import cli as cli_main

    cli_main()


if __name__ == "__main__":
    main()
