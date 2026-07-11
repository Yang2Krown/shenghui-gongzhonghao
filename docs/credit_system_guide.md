# 积分系统使用指南

## 已创建的文件

### 数据库模型
- `backend/app/models/credit.py` - 积分账户、交易记录、套餐模型

### 配置文件
- `backend/app/core/credit_config.py` - 操作定价、套餐配置

### 服务层
- `backend/app/services/credit_service.py` - 积分业务逻辑

### 中间件
- `backend/app/core/credit_guard.py` - 积分检查依赖注入

### API 路由
- `backend/app/api/v1/credits.py` - 积分相关接口

### 数据库迁移
- `backend/alembic/versions/c7a1e4f5d8b2_add_credit_system_tables.py`

---

## API 接口列表

### 用户接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/credits/balance` | 查询积分余额 |
| GET | `/api/v1/credits/account` | 获取账户详情 |
| POST | `/api/v1/credits/check?operation=xxx` | 检查积分是否足够 |
| GET | `/api/v1/credits/transactions` | 查询交易记录 |
| GET | `/api/v1/credits/consumption-stats` | 获取消耗统计 |
| GET | `/api/v1/credits/packages` | 获取套餐列表 |
| GET | `/api/v1/credits/operation-costs` | 获取操作定价 |
| GET | `/api/v1/credits/estimate?articles_per_month=10` | 估算月度成本 |

### 管理员接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/credits/admin/gift` | 赠送积分 |

---

## 如何在现有路由中集成积分检查

### 方式一：使用依赖注入（推荐）

```python
from fastapi import APIRouter, Depends
from app.core.credit_guard import check_content_generation_credits

router = APIRouter()

@router.post("/generate")
async def generate_content(
    # ... 其他参数 ...
    credit_info: dict = Depends(check_content_generation_credits),  # 自动检查积分
):
    """生成正文（需要积分）"""
    user = credit_info["user"]
    credit_service = credit_info["credit_service"]
    
    try:
        # 执行业务逻辑
        result = await do_content_generation(...)
        
        # 成功后扣费
        await credit_service.deduct_credits(
            user_id=user.id,
            operation="content_generation",
            operation_id=result.get("task_id"),
            token_usage=result.get("usage"),
        )
        
        return {"code": 200, "data": result}
        
    except Exception as e:
        # 失败不扣费
        raise HTTPException(status_code=500, detail=str(e))
```

### 方式二：手动检查

```python
from app.services.credit_service import CreditService
from app.db.session import get_db

@router.post("/generate")
async def generate_content(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    credit_service = CreditService(db)
    
    # 手动检查余额
    check = await credit_service.check_balance(current_user.id, "content_generation")
    if not check["sufficient"]:
        raise HTTPException(402, f"积分不足，需要 {check['required']}，当前 {check['balance']}")
    
    try:
        result = await do_content_generation(...)
        await credit_service.deduct_credits(current_user.id, "content_generation", result.get("task_id"))
        return {"code": 200, "data": result}
    except Exception:
        raise
```

---

## 已预定义的积分检查依赖

| 依赖函数 | 操作类型 | 积分消耗 |
|----------|----------|----------|
| `check_topic_mining_credits` | topic_mining | 2积分 |
| `check_outline_generation_credits` | outline_generation | 3积分 |
| `check_content_generation_credits` | content_generation | 10积分 |
| `check_content_polish_credits` | content_polish | 8积分 |
| `check_title_generation_credits` | title_generation | 3积分 |
| `check_content_continuation_credits` | content_continuation | 1积分 |
| `check_content_transform_credits` | content_transform | 2积分 |
| `check_content_imitate_credits` | content_imitate | 3积分 |

---

## 操作定价表

| 操作 | 积分 | 折合人民币 | 说明 |
|------|------|-----------|------|
| 选题挖掘 | 2 | ¥0.20 | Agent A→A2→B |
| 大纲生成 | 3 | ¥0.30 | Agent A→B→C→D |
| 正文生成 | 10 | ¥1.00 | Agent A→B→D→E→C |
| 文案润色 | 8 | ¥0.80 | Agent B→D→E→C |
| 标题生成 | 3 | ¥0.30 | Agent A→B→C→D |
| 正文续写 | 1 | ¥0.10 | 单次LLM调用 |
| 标题评分 | 1 | ¥0.10 | 单次LLM调用 |
| 内容转写 | 2 | ¥0.20 | 风格转换 |
| 内容仿写 | 3 | ¥0.30 | 风格模仿 |

---

## 积分套餐

| 套餐 | 到账积分 | 价格 | 赠送 |
|------|------|------|------|
| 300 元充值 | 3000 | ¥300 | 无 |
| 500 元充值 | 5250 | ¥500 | 赠送 250 积分（5%） |
| 1000 元充值 | 11000 | ¥1000 | 赠送 1000 积分（10%） |
| 2000 元充值 | 24000 | ¥2000 | 赠送 4000 积分（20%） |

---

## 业务规则

1. **新用户赠送**：注册即送 20 积分（约1篇完整文章）
2. **失败不扣费**：只有操作成功后才扣减积分
3. **积分永久有效**：充值积分、开通创作工具赠送的 6000 积分及其他赠送积分，均不会因订阅到期而清零。
4. **订阅到期**：仅影响创作工具权益；重新开通后可继续使用账户中保留的全部积分。
5. **余额不足**：返回 402 状态码，提示需要充值

---

## 部署步骤

1. 执行数据库迁移：
```bash
cd backend
alembic upgrade head
```

2. 重启后端服务：
```bash
# 线上
docker-compose -f docker-compose.prod.yml --env-file backend/.env.production restart backend
docker-compose -f docker-compose.prod.yml --env-file backend/.env.production restart frontend
```

3. 验证接口：
```bash
# 查询余额
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/credits/balance

# 查询套餐
curl http://localhost:8000/api/v1/credits/packages
```

---

## 后续扩展

- [ ] 支付集成（微信支付/支付宝）
- [ ] 积分充值页面（前端）
- [ ] 积分余额显示（顶部导航栏）
- [ ] 操作前确认弹窗（显示需要消耗的积分）
- [ ] 积分不足时的充值引导
