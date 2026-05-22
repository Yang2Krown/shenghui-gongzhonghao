# 外部 Skill 脚本

这些脚本来自 SkillHub，原始路径在 `~/.workbuddy/skills/`。
为了**让服务器部署不依赖本机环境**，把它们 vendor 进 repo。

## 来源

- `gzh_explosive/fetch_gzh_trends.py` ← `gzh-explosive-content-detector/scripts/`
  - 公众号爆款 4 类榜（低粉/阅读/原创/数据增长）
  - 接 onetotenvip.com SkillHub API
  - 0 cookie
  
- `xhs_daily/xhs_daily_fetcher.py` ← `xhs-daily-breaking/scripts/`
  - 小红书每日爆款 TOP50（25 个分类）
  - 接 onetotenvip.com SkillHub API
  - 0 cookie
  - 每日 19:00 更新

## 更新策略

如果原 skill 升级了，手动 `cp` 覆盖即可。
