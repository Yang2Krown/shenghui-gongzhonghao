"""Seed 脚本：把 3 个 Excel 表格的内容导入 SourceRegistry / SourceAccount。

单独执行：
    python -m app.db.seeds.seed_sources_from_table1
    python -m app.db.seeds.seed_accounts_from_table2
    python -m app.db.seeds.seed_rss_from_table3

一次跑完：
    python -m app.db.seeds
"""

from pathlib import Path

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seeds"
TABLE1_PATH = SEEDS_DIR / "AI选题信息源.xlsx"
TABLE2_PATH = SEEDS_DIR / "关注博主整理_AI信息源.xlsx"
TABLE3_PATH = SEEDS_DIR / "新闻源.xlsx"
