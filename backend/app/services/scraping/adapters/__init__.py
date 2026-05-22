"""P0 adapter 集合：0 cookie 0 浏览器。

在 register_adapters() 里把所有 adapter 注册到 orchestrator。
"""

from app.services.scraping.orchestrator import orchestrator
from app.services.scraping.adapters.rss_adapter import RSSAdapter
from app.services.scraping.adapters.web_adapter import WebAdapter
from app.services.scraping.adapters.github_adapter import GitHubTrendingAdapter
from app.services.scraping.adapters.hackernews_adapter import HackerNewsAdapter
from app.services.scraping.adapters.exa_wechat_adapter import ExaWechatAdapter
from app.services.scraping.adapters.tophub_adapter import TopHubAdapter
from app.services.scraping.adapters.gzh_explosive_adapter import GzhExplosiveAdapter
from app.services.scraping.adapters.v2ex_adapter import V2EXAdapter
from app.services.scraping.adapters.reddit_adapter import RedditAdapter
from app.services.scraping.adapters.xhs_daily_adapter import XhsDailyAdapter


_REGISTERED = False


def register_adapters() -> None:
    """幂等地把所有 adapter 注册到 orchestrator。"""
    global _REGISTERED
    if _REGISTERED:
        return
    orchestrator.register(RSSAdapter())
    orchestrator.register(WebAdapter())
    orchestrator.register(GitHubTrendingAdapter())
    orchestrator.register(HackerNewsAdapter())
    orchestrator.register(ExaWechatAdapter())
    orchestrator.register(TopHubAdapter())
    orchestrator.register(GzhExplosiveAdapter())
    orchestrator.register(V2EXAdapter())
    orchestrator.register(RedditAdapter())
    orchestrator.register(XhsDailyAdapter())
    _REGISTERED = True


__all__ = ["register_adapters"]
