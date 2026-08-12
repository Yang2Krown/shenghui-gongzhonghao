from fastapi import APIRouter

from app.api.v1 import auth, topics, creation, users, ai, styles, topic_candidates, topic_clusters, outlines, content_generation, title_generation, title_munger, standalone_title, wechat_to_xhs, generation_records, image_proxy, xhs_publish, xhs_debug, creation_tools, progress, content_transform, content_imitate, wechat_draft, content_continuation, content_polish, wechat_accounts, credits, credit_purchase, practical, feishu_brief, images, commercial, admin, announcements, _test_gzh_fetch, courses, xhs, xhs_agent, team, meetings, content_versions, experience, article_reviews

api_router = APIRouter()

api_router.include_router(xhs.router, prefix="/xhs", tags=["小红书素材"])
api_router.include_router(xhs.admin_router, prefix="/admin/xhs-monitoring", tags=["小红书采集监测"])
api_router.include_router(xhs_agent.router, prefix="/xhs-agent", tags=["小红书本地采集节点"])
api_router.include_router(xhs_agent.admin_router, prefix="/admin/xhs-monitoring", tags=["小红书本地采集节点管理"])

# 团队协作（P0）
api_router.include_router(team.router, prefix="/team", tags=["团队协作"])

# 会议方法论沉淀（Phase 1b，仅员工/管理员）
api_router.include_router(meetings.router, prefix="/meetings", tags=["会议建议"])

# 文章版本与经验库（Phase 1c）
api_router.include_router(content_versions.router, prefix="/creations", tags=["文章版本"])
api_router.include_router(experience.router, prefix="/experience", tags=["经验库"])
api_router.include_router(article_reviews.router, prefix="/reviews", tags=["文章复盘"])

# 通用进度轮询
api_router.include_router(
    progress.router,
    tags=["进度"]
)

# 认证路由
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["认证"]
)

# 选题路由
api_router.include_router(
    topics.router,
    prefix="/topics",
    tags=["选题"]
)

# 创作路由
api_router.include_router(
    creation.router,
    prefix="/creations",
    tags=["创作"]
)

# 用户路由
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["用户"]
)

# 管理员后台
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["管理员后台"]
)

# 系统公告（所有已登录用户可读取）
api_router.include_router(
    announcements.router,
    prefix="/announcements",
    tags=["系统公告"]
)

# AI服务路由
api_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["AI服务"]
)

# 风格档案路由
api_router.include_router(
    styles.router,
    prefix="/styles",
    tags=["风格档案"]
)

# 候选选题路由
api_router.include_router(
    topic_candidates.router,
    prefix="/topic-candidates",
    tags=["候选选题"]
)

# 话题库路由
api_router.include_router(
    topic_clusters.router,
    prefix="/topic-clusters",
    tags=["话题库"]
)

# 潜在商单路由
api_router.include_router(
    commercial.router,
    prefix="/commercial",
    tags=["潜在商单"]
)

# 大纲路由
api_router.include_router(
    outlines.router,
    prefix="/outlines",
    tags=["大纲"]
)

# 正文生成路由
api_router.include_router(
    content_generation.router,
    prefix="/content-generation",
    tags=["正文生成"]
)

# 标题生成路由
api_router.include_router(
    title_generation.router,
    prefix="/title-generation",
    tags=["标题生成"]
)

# 芒格版标题生成与评分路由
api_router.include_router(
    title_munger.router,
    prefix="/title-munger",
    tags=["芒格版标题"]
)

# 独立标题生成路由
api_router.include_router(
    standalone_title.router,
    prefix="/standalone-title",
    tags=["独立标题生成"]
)

# 公众号转小红书路由
api_router.include_router(
    wechat_to_xhs.router,
    prefix="/wechat-to-xhs",
    tags=["公众号转小红书"]
)

# 生成记录路由
api_router.include_router(
    generation_records.router,
    prefix="/generation-records",
    tags=["生成记录"]
)

# 图片代理路由
api_router.include_router(
    image_proxy.router,
    prefix="/image-proxy",
    tags=["图片代理"]
)

# 小红书发布路由
api_router.include_router(
    xhs_publish.router,
    prefix="/xhs-publish",
    tags=["小红书发布"]
)

# 小红书调试路由（临时）
api_router.include_router(
    xhs_debug.router,
    prefix="/xhs-debug",
    tags=["小红书调试"]
)

# 创作工具路由
api_router.include_router(
    creation_tools.router,
    prefix="/creation-tools",
    tags=["创作工具"]
)

# 内容转写路由
api_router.include_router(
    content_transform.router,
    prefix="/content-transform",
    tags=["内容转写"]
)

# 内容仿写路由
api_router.include_router(
    content_imitate.router,
    prefix="/content-imitate",
    tags=["内容仿写"]
)

# 微信公众号草稿箱路由
api_router.include_router(
    wechat_draft.router,
    prefix="/wechat-draft",
    tags=["微信公众号草稿箱"]
)

# 正文续写路由
api_router.include_router(
    content_continuation.router,
    prefix="/content-continuation",
    tags=["正文续写"]
)

# 文案润色路由
api_router.include_router(
    content_polish.router,
    prefix="/content-polish",
    tags=["文案润色"]
)

# 微信公众号账号管理路由
api_router.include_router(
    wechat_accounts.router,
    prefix="/wechat-accounts",
    tags=["公众号账号"]
)

# 积分系统路由
api_router.include_router(
    credits.router,
    prefix="/credits",
    tags=["积分系统"]
)

# 积分购买路由
api_router.include_router(
    credit_purchase.router,
    prefix="/credits",
    tags=["积分购买"]
)

# 实操 / 商稿创作流
api_router.include_router(
    practical.router,
    prefix="/practical",
    tags=["实操创作"]
)

# 飞书商单 brief 接入
api_router.include_router(
    feishu_brief.router,
    prefix="/feishu",
    tags=["飞书商单brief"]
)

# 图片上传路由
api_router.include_router(
    images.router,
    prefix="/images",
    tags=["图片上传"]
)

# 课程资料路由
api_router.include_router(
    courses.router,
    prefix="/courses",
    tags=["课程资料"]
)


# ──── ⚠️ 临时测试路由：公众号抓取可视化 ────────────────────────
# 实验性：只是让你看"公众号抓到了什么"，feature 验证完后：
#   ① 删 backend/app/api/v1/_test_gzh_fetch.py
#   ② 从这里移除这两行 include_router
# 不动模型 / 不动表 / 不动 preprocess / 不动 Agent 流水线
api_router.include_router(
    _test_gzh_fetch.router,
    prefix="/_test_gzh_fetch",
    tags=["⚠️临时·公众号抓取测试"]
)
