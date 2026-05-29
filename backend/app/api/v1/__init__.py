from fastapi import APIRouter

from app.api.v1 import auth, topics, creation, users, ai, styles, topic_candidates, topic_clusters, outlines, content_generation, title_generation, title_munger, standalone_title, wechat_to_xhs, generation_records, image_proxy, xhs_publish, xhs_debug

api_router = APIRouter()

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