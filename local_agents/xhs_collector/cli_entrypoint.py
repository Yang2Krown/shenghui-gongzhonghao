"""给 xiaohongshu-cli 注入「一周内」过滤，并让排序过滤与 --sort 保持一致。"""
from xhs_cli import client_mixins


def _search_filters(sort: str) -> list[dict[str, object]]:
    return [
        {"tags": [sort], "type": "sort_type"},
        {"tags": ["不限"], "type": "filter_note_type"},
        {"tags": ["一周内"], "type": "filter_note_time"},
        {"tags": ["不限"], "type": "filter_note_range"},
        {"tags": ["不限"], "type": "filter_pos_distance"},
    ]


_original_search_notes = client_mixins.ReadingEndpointsMixin.search_notes


def _search_notes_with_matching_filters(self, *args, **kwargs):
    sort = str(kwargs.get("sort") or "general")
    client_mixins._SEARCH_DEFAULT_FILTERS = _search_filters(sort)
    return _original_search_notes(self, *args, **kwargs)


client_mixins.ReadingEndpointsMixin.search_notes = _search_notes_with_matching_filters

from xhs_cli.cli import cli

if __name__ == "__main__":
    cli()
