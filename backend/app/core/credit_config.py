"""积分系统配置：操作定价、套餐定义。"""

# ====== 操作积分定价 ======
# 基于 DeepSeek（默认最便宜 provider）成本 × 3-5 倍
OPERATION_COSTS = {
    "topic_mining": {
        "base_credits": 2,
        "description": "选题挖掘",
        "estimated_tokens": 15000,
        "estimated_cost_yuan": 0.03,
    },
    "outline_generation": {
        "base_credits": 3,
        "description": "大纲生成",
        "estimated_tokens": 25000,
        "estimated_cost_yuan": 0.05,
    },
    "content_generation": {
        "base_credits": 10,
        "description": "正文生成",
        "estimated_tokens": 60000,
        "estimated_cost_yuan": 0.15,
    },
    "content_polish": {
        "base_credits": 8,
        "description": "文案润色",
        "estimated_tokens": 45000,
        "estimated_cost_yuan": 0.10,
    },
    "title_generation": {
        "base_credits": 3,
        "description": "标题生成",
        "estimated_tokens": 25000,
        "estimated_cost_yuan": 0.05,
    },
    "content_continuation": {
        "base_credits": 1,
        "description": "正文续写",
        "estimated_tokens": 8000,
        "estimated_cost_yuan": 0.02,
    },
    "title_scoring": {
        "base_credits": 1,
        "description": "标题评分",
        "estimated_tokens": 5000,
        "estimated_cost_yuan": 0.01,
    },
    "content_transform": {
        "base_credits": 2,
        "description": "内容转写",
        "estimated_tokens": 15000,
        "estimated_cost_yuan": 0.03,
    },
    "content_imitate": {
        "base_credits": 3,
        "description": "内容仿写",
        "estimated_tokens": 20000,
        "estimated_cost_yuan": 0.04,
    },
    "practical_research": {
        "base_credits": 3,
        "description": "产品研究（实操类）",
        "estimated_tokens": 20000,
        "estimated_cost_yuan": 0.05,
    },
    "practical_draft": {
        "base_credits": 10,
        "description": "实操成稿",
        "estimated_tokens": 60000,
        "estimated_cost_yuan": 0.15,
    },
}

# ====== 积分套餐定义 ======
CREDIT_PACKAGES = [
    {
        "name": "体验包",
        "credits": 100,
        "price_yuan": 0.01,
        "original_price_yuan": None,
        "description": "测试套餐，可创作约 5 篇完整文章",
        "badge": "测试",
        "sort_order": 1,
    },
    {
        "name": "标准包",
        "credits": 500,
        "price_yuan": 39,
        "original_price_yuan": 49.5,
        "description": "最受欢迎，可创作约 27 篇完整文章",
        "badge": "推荐",
        "sort_order": 2,
    },
    {
        "name": "专业包",
        "credits": 1200,
        "price_yuan": 79,
        "original_price_yuan": 118.8,
        "description": "专业运营首选，可创作约 66 篇完整文章",
        "badge": "超值",
        "sort_order": 3,
    },
    {
        "name": "团队包",
        "credits": 3000,
        "price_yuan": 169,
        "original_price_yuan": 297,
        "description": "团队批量采购，可创作约 166 篇完整文章",
        "badge": None,
        "sort_order": 4,
    },
]

# ====== 新用户赠送配置 ======
NEW_USER_GIFT_CREDITS = 20  # 新用户注册赠送积分

# ====== 完整创作流程示例 ======
FULL_CREATION_FLOW = {
    "steps": [
        {"operation": "topic_mining", "label": "选题挖掘"},
        {"operation": "outline_generation", "label": "大纲生成"},
        {"operation": "content_generation", "label": "正文生成"},
        {"operation": "title_generation", "label": "标题生成"},
    ],
    "total_credits": 18,  # 2 + 3 + 10 + 3
    "total_yuan": 1.80,
}


def get_operation_cost(operation: str) -> dict:
    """获取操作的积分成本配置"""
    if operation not in OPERATION_COSTS:
        raise ValueError(f"未知操作类型: {operation}")
    return OPERATION_COSTS[operation]


def get_operation_credits(operation: str) -> int:
    """获取操作需要的积分数量"""
    return get_operation_cost(operation)["base_credits"]


def estimate_monthly_cost(articles_per_month: int) -> dict:
    """估算月度成本"""
    cost_per_article = FULL_CREATION_FLOW["total_credits"]
    total_credits = cost_per_article * articles_per_month
    total_yuan = total_credits * 0.10  # 1积分 = ¥0.10

    # 推荐套餐
    recommended_package = None
    for pkg in sorted(CREDIT_PACKAGES, key=lambda x: x["credits"]):
        if pkg["credits"] >= total_credits:
            recommended_package = pkg
            break
    if not recommended_package:
        recommended_package = CREDIT_PACKAGES[-1]

    return {
        "articles_per_month": articles_per_month,
        "credits_per_article": cost_per_article,
        "total_credits_needed": total_credits,
        "estimated_yuan": round(total_yuan, 2),
        "recommended_package": recommended_package["name"],
        "recommended_price": recommended_package["price_yuan"],
    }
