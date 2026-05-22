from fastapi import APIRouter

from app.api.v1 import auth, topics, creation, users, ai, styles, topic_candidates, topic_clusters, outlines, content_generation

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