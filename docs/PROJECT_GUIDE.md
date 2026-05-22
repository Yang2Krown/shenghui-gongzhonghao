# AI 公众号内容运营平台 — 项目说明文档

> 面向开发者的完整指南，涵盖架构、原理、使用方法，以及 Spring Boot 开发者的 Python/FastAPI 对照说明。

---

## 目录

1. [项目概览](#1-项目概览)
2. [技术栈速查（Spring Boot 对照）](#2-技术栈速查)
3. [项目结构](#3-项目结构)
4. [环境搭建与启动](#4-环境搭建与启动)
5. [数据流：从信息抓取到每日选题](#5-数据流)
6. [选题挖掘原理（Agent A / B）](#6-选题挖掘原理)
7. [前端架构说明](#7-前端架构)
8. [API 接口一览](#8-api-接口)
9. [核心数据模型](#9-核心数据模型)
10. [Python / FastAPI 常见问题（Spring Boot 视角）](#10-python-常见问题)
11. [部署方式](#11-部署)
12. [常见问题排查](#12-常见问题)

---

## 1. 项目概览

这是一个**公众号内容运营辅助平台**，核心功能是用 AI 自动化完成"选题挖掘 → 内容创作"的工作流：

```
抓取信息源 → 预处理聚类 → AI 衍生候选选题 → AI 评分筛选 → 生成每日选题清单 → 创作内容
```

**一句话总结**：你告诉系统"关注哪些信息源"，系统自动帮你从海量信息中提炼出值得写的选题，并给出评分和建议。

---

## 2. 技术栈速查

### Spring Boot 开发者对照表

| 概念 | Spring Boot (Java) | 本项目 (Python) |
|------|-------------------|----------------|
| Web 框架 | Spring Web (Tomcat) | **FastAPI** (uvicorn) |
| 依赖注入 | `@Autowired` / `@Bean` | **Depends()** 函数（见下文详解） |
| ORM | JPA / MyBatis | **SQLAlchemy** (async) |
| 数据库迁移 | Flyway / Liquibase | **Alembic** |
| 校验 | `@Valid` + Bean Validation | **Pydantic** BaseModel |
| 配置管理 | `application.yml` + `@Value` | **pydantic-settings** + `.env` 文件 |
| 异步任务 | `@Async` + `ThreadPoolTaskExecutor` | **Celery** (Redis 做 broker) |
| 认证 | Spring Security + JWT | **python-jose** (JWT) + 手写 `Depends(get_current_user)` |
| API 文档 | Springdoc (Swagger) | **FastAPI 内置** `/docs` |
| 包管理 | Maven (`pom.xml`) / Gradle | **pip** (`requirements.txt`) / `pyproject.toml` |
| 虚拟环境 | 无（Maven 管理依赖） | **`.venv/`**（必须激活） |

### 前端技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 + Composition API | UI 框架（类比 React） |
| Vite | 构建工具（类比 webpack） |
| Pinia | 状态管理（类比 Redux / Vuex） |
| Element Plus | UI 组件库（类比 Ant Design） |
| Tiptap | 富文本编辑器 |
| Tailwind CSS | 原子化 CSS |
| Axios | HTTP 客户端 |

---

## 3. 项目结构

```
gzh/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── main.py             # ← 相当于 Spring Boot 的 @SpringBootApplication
│   │   ├── core/
│   │   │   ├── config.py       # ← 相当于 application.yml（用 pydantic-settings 读 .env）
│   │   │   └── security.py     # ← 相当于 SecurityConfig + JWT 工具类
│   │   ├── models/             # ← 相当于 @Entity 类
│   │   ├── schemas/            # ← 相当于 DTO / Request / Response 类
│   │   ├── api/v1/             # ← 相当于 @RestController
│   │   ├── services/           # ← 相当于 @Service 类
│   │   ├── crud/               # ← 相当于 @Repository
│   │   ├── db/
│   │   │   ├── session.py      # ← 相当于 DataSource + EntityManagerFactory
│   │   │   ├── base.py         # ← 相当于 BaseEntity（id, created_at, updated_at）
│   │   │   └── init_db.py      # ← 相当于 data.sql / schema.sql
│   │   └── tasks/              # ← 相当于 @Scheduled 任务（但用 Celery）
│   ├── .env                    # 环境变量（不提交 git）
│   ├── alembic/                # 数据库迁移（类比 Flyway）
│   ├── requirements.txt        # ← 相当于 pom.xml 的 <dependencies>
│   └── run_mining.py           # 独立运行的挖掘脚本
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── api/                # HTTP 请求封装
│       ├── stores/             # 状态管理（类比 Redux）
│       ├── pages/              # 页面组件
│       ├── components/         # 通用组件
│       └── router.js           # 路由配置
└── docker-compose.yml          # 一键部署（7 个服务）
```

---

## 4. 环境搭建与启动

### 4.1 前置要求

- Python 3.9+（项目用 3.9，不能用 `X | None` 语法）
- Node.js 18+
- PostgreSQL 16 + pgvector 扩展（或用 SQLite 开发模式）
- Redis（Celery 用）

### 4.2 后端启动

```bash
cd backend

# 1. 创建虚拟环境（只需一次）
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖（只需一次）
pip install -r requirements.txt

# 3. 配置环境变量（只需一次）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 等

# 4. 启动
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后访问 http://127.0.0.1:8000/docs 可看到 Swagger API 文档。

### 4.3 前端启动

```bash
cd frontend

# 1. 安装依赖（只需一次）
npm install

# 2. 启动开发服务器
npm run dev
```

访问 http://localhost:3000

### 4.4 `.env` 关键配置

```env
# LLM 密钥（必须）
DEEPSEEK_API_KEY=sk-xxx          # DeepSeek API（便宜，用于预处理）
ANTHROPIC_API_KEY=sk-ant-xxx     # Claude API（贵，用于 Agent A/B 挖掘）

# 数据库（留空则自动用 SQLite 开发模式）
POSTGRES_PASSWORD=               # 留空 = 用 SQLite
# POSTGRES_PASSWORD=xxx          # 填写 = 用 PostgreSQL + pgvector

# LLM 提供商切换
LLM_PROVIDER=deepseek            # deepseek / anthropic
```

---

## 5. 数据流

### 完整流水线

```
┌─────────────────────────────────────────────────────────────────┐
│  第 1 步：信息抓取（Scraping）                                    │
│                                                                   │
│  SourceRegistry（种子数据，从 Excel 导入）                         │
│       ↓                                                           │
│  Scraping Orchestrator（根据 source_type 分发给不同 adapter）      │
│       ├── rss_adapter（RSS 订阅源）                               │
│       ├── web_adapter（网页爬虫）                                 │
│       ├── github_adapter（GitHub trending）                       │
│       ├── hackernews_adapter（Hacker News）                       │
│       └── exa_wechat_adapter（微信搜索）                          │
│       ↓                                                           │
│  RawInfo 表（原始信息，state=pending）                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  第 2 步：预处理（Preprocessing）                                │
│                                                                   │
│  RawInfo                                                         │
│       ↓                                                           │
│  ① 向量化：DashScope text-embedding-v3 → 存入 pgvector           │
│       ↓                                                           │
│  ② 聚类：pgvector 余弦相似度 > 0.85 → 合并为 InfoCluster          │
│       ↓                                                           │
│  ③ LLM 富化：提取 info_type / elements / direction               │
│       ↓                                                           │
│  ④ 规则打标：freshness / heat_score / low_fan_hit                 │
│       ↓                                                           │
│  InfoCluster 表（state=mined=false）                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  第 3 步：选题挖掘（Topic Mining）← 核心！                       │
│                                                                   │
│  InfoCluster（1 条）                                              │
│       ↓                                                           │
│  Agent A（衍生员）：LLM 衍生 3-8 个候选选题                       │
│       ├── 套路匹配：4 类信息 × N 种套路                           │
│       ├── 8 维度组合创新                                          │
│       └── 4 Persona 评议（AI专家/百万粉博主/产品经理/运营专家）    │
│       ↓                                                           │
│  Agent B（评分员）：LLM 评分 + 一票否决                            │
│       ├── 一票否决检查（硬性淘汰）                                 │
│       ├── 6 维度评分（痛点/价值/传播/差异化/新鲜度/受众）          │
│       ├── 加权总分计算                                            │
│       └── 入选/备选/淘汰 判定                                     │
│       ↓                                                           │
│  TopicCandidate + PersonaReview + CandidateScore                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  第 4 步：排名生成每日清单（Ranking）                             │
│                                                                   │
│  TopicCandidate（所有 scored 候选）                               │
│       ↓                                                           │
│  ① 跨聚类去重（标题相似度）                                       │
│       ↓                                                           │
│  ② 方向多样性约束（单方向最多 40%，最少 3 个方向）                │
│       ↓                                                           │
│  ③ Top N 输出                                                    │
│       ↓                                                           │
│  DailyTopicList（每日选题清单）                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  第 5 步：前端展示                                                │
│                                                                   │
│  候选选题清单页 → 筛选/排序/查看详情                               │
│  每日选题页 → 查看当日 Top 选题                                   │
│  创作编辑器 → 基于选题撰写内容                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 选题挖掘原理

### 6.1 整体设计哲学

> **"创作者而非过滤器"** — Agent A 不是从一堆烂选题里挑好的，而是从一条信息衍生出多种好选题。

传统做法：抓 100 条 → 过滤掉 90 条 → 剩 10 条。
本项目做法：抓 1 条 → 衍生 5 个好选题 → 独立评分 → 输出 Top 选题。

### 6.2 Agent A — 选题衍生员

**文件**：`backend/app/services/topic_mining/agent_a_deriver.py`

**输入**：1 个 InfoCluster（预处理后的信息聚类）

**输出**：3-8 个候选选题，每个带有 4 个 Persona 的独立评议

**工作原理**：

```
1. 加载系统提示词（agent_a_system.txt）
2. 加载《选题套路库》作为参考资产
3. 根据信息类型确定衍生量：
   ├── 资讯型：5-8 个
   ├── 实操案例型：4-6 个
   ├── 观点分享型：4-6 个
   └── 教程型：3-5 个
4. 构建 Prompt → 调用 LLM（temperature=0.4）
5. 解析 JSON 输出 → 校验 Schema
```

**每个候选选题包含**：

| 字段 | 说明 |
|------|------|
| `title` | 草标题（14-22 字） |
| `direction` | 内容方向（6 选 1） |
| `routine` | 套路名（如 "1.1.1 深度解读型"） |
| `dimension_combo` | 维度组合（如 `["态度=吹爆", "结构=列表"]`） |
| `value_promise` | 价值承诺（1 句话） |
| `angle_note` | 切入说明 |
| `persona_reviews` | 4 个 Persona 的评分和理由 |

**4 Persona 评议**：

每个候选选题都由 4 个"虚拟专家"独立打分（1-10 分）：

| Persona | 角色定位 | 关注点 |
|---------|---------|--------|
| AI 专家 | 技术深度 | 信息准确性、技术价值 |
| 百万粉博主 | 传播敏感度 | 标题吸引力、话题热度 |
| 产品经理 | 用户价值 | 痛点解决、实用性 |
| 运营专家 | 数据表现 | 转化率、受众匹配度 |

**分歧度** = max(4 人分数) - min(4 人分数)，如果 >= 4 分，标记为高分歧。

### 6.3 Agent B — 选题评分员

**文件**：`backend/app/services/topic_mining/agent_b_scorer.py`

**输入**：Agent A 的候选列表 + 元数据

**输出**：评分后的候选列表 + 统计

**评分流程**：

```
1. 一票否决检查（硬性淘汰，如涉及虚假信息等）
2. 6 维度独立评分（1-10 分，每项附 1 句依据）
3. 加权总分计算（程序化计算，不依赖 LLM 算术）
4. 判定入选/备选/淘汰
```

**6 维度及权重**：

| 维度 | 权重 | 说明 |
|------|------|------|
| 痛点直击度 | 20% | 选题是否直击目标受众的核心痛点 |
| 价值密度 | 20% | 单篇能提供多少可感知的干货/信息量 |
| 传播触发器 | 15% | 是否有转发动机（社交货币、情绪、实用） |
| 差异化 | 15% | 与同方向已有内容的差异程度 |
| 新鲜度 | 10% | 信息的时效性和新鲜程度 |
| 受众适配度 | 20% | 与目标受众画像的匹配程度 |

**判定规则**：

```
weighted_score >= 7.0  →  selected（入选）
5.0 <= weighted_score < 7.0  →  backup（备选）
weighted_score < 5.0  →  rejected（淘汰）
一票否决未通过  →  vetoed（否决）
```

**关键设计**：加权总分和判定是**程序化计算**的，不是让 LLM 算的（LLM 算术不可靠）。

### 6.4 套路库 & 评分卡

这些都是**提示词资产**，存放在 `backend/app/services/topic_mining/assets/`：

| 文件 | 用途 |
|------|------|
| `选题套路库.md` | 4 类信息 × 多种写作套路 + 8 维度创新方法 |
| `选题评分卡.md` | 6 维度评分锚点（1/4/7/10 分别什么样） |
| `content_directions.md` | 6 大内容方向定义 |
| `标题套路库.md` | 12 种标题模式（标题生成 Agent 用） |
| `大纲模板库.md` | 17 种大纲骨架（大纲生成 Agent 用） |

这些文件被 Agent 的 Prompt 动态加载，相当于给 LLM "开卷考试"。

---

## 7. 前端架构

### 7.1 页面结构

```
登录/注册页
    ↓
AppLayout（侧边栏 + 顶栏 + 内容区）
    ├── 每日选题（TopicList.vue）      ← 首页
    ├── 选题详情（TopicDetail.vue）
    ├── 候选选题清单（TopicCandidateList.vue）← 挖掘结果
    ├── 我的创作（CreationList.vue）
    ├── 新建/编辑创作（CreationEditor.vue）
    ├── 个人设置（ProfileSettings.vue）
    └── 风格设置（StyleSettings.vue）
```

### 7.2 API 调用流程

```
Vue 组件
  ↓ 调用
stores/（Pinia 状态管理）
  ↓ 调用
api/*.js（业务 API 函数）
  ↓ 调用
api/api.js（Axios 实例 + 拦截器）
  ↓ 自动添加
Authorization: Bearer <token>
  ↓ 请求
FastAPI 后端
```

**api.js 拦截器做了什么**：
1. **请求拦截**：自动注入 JWT token 到 Header
2. **响应拦截**：自动解包 `response.data.data`（后端返回 `{code, message, data}`，前端只拿到 `data`）
3. **401 处理**：自动尝试刷新 token，失败则跳转登录页

### 7.3 前端路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | TopicList | 首页 — 每日选题 |
| `/topic-candidates` | TopicCandidateList | 候选选题清单（可触发挖掘） |
| `/topics/:id` | TopicDetail | 选题详情 |
| `/creation` | CreationList | 我的创作列表 |
| `/creation/new` | CreationEditor | 新建创作 |
| `/creation/:id` | CreationEditor | 编辑创作 |
| `/settings` | ProfileSettings | 个人设置 |
| `/settings/style` | StyleSettings | 写作风格设置 |

---

## 8. API 接口

### 8.1 认证 `/api/v1/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/register` | 注册 |
| POST | `/login` | 登录（返回 access_token + refresh_token） |
| POST | `/refresh` | 刷新 token |
| GET | `/me` | 获取当前用户 |

### 8.2 选题 `/api/v1/topic-candidates`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/mine` | 触发选题挖掘（body: `{limit: 3}`） |
| GET | `/` | 获取候选选题列表（支持筛选、排序、分页） |
| GET | `/{id}` | 获取候选选题详情 |
| GET | `/stats/overview` | 统计概览 |
| GET | `/daily-list/{date}` | 获取每日选题清单 |
| POST | `/daily-list/generate` | 生成每日选题清单 |

### 8.3 内容创作 `/api/v1/creations`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/` | 创建内容 |
| GET | `/` | 列表 |
| GET | `/{id}` | 详情 |
| PUT | `/{id}` | 更新 |
| DELETE | `/{id}` | 删除 |
| POST | `/{id}/publish` | 发布 |
| POST | `/generate` | AI 生成内容 |

---

## 9. 核心数据模型

### ER 关系图

```
User ──1:N──> UserProfile
User ──1:N──> StyleProfile
User ──1:N──> ContentCreation

SourceRegistry ──1:N──> SourceAccount
SourceRegistry ──1:N──> RawInfo（抓取的原始信息）

RawInfo ──N:1──> InfoCluster（聚类后）

InfoCluster ──1:N──> TopicCandidate（衍生的候选选题）
TopicCandidate ──1:N──> PersonaReview（4 个 Persona 的评议）
TopicCandidate ──1:1──> CandidateScore（6 维度评分）

TopicCandidate ──N:M──> DailyTopicList（每日选题清单）
```

### 关键表说明

| 表 | 说明 | 关键字段 |
|----|------|----------|
| `RawInfo` | 原始抓取信息 | url, title, summary, embedding(pgvector), state |
| `InfoCluster` | 聚类后的信息 | core_title, info_type, elements(JSON), centroid(pgvector), mined |
| `TopicCandidate` | 候选选题 | title, direction, routine, weighted_score, verdict |
| `PersonaReview` | Persona 评议 | persona, score(1-10), rationale |
| `CandidateScore` | 维度评分 | pain_point, value_density, propagation, differentiation, freshness, audience_fit, evidence(JSON) |
| `DailyTopicList` | 每日选题清单 | list_date, top_n, items(JSON), direction_distribution |

### SQLAlchemy 模型 vs JPA Entity 对照

```python
# Python (SQLAlchemy)
class TopicCandidate(BaseModel):       # 继承 BaseModel（自带 id, created_at, updated_at）
    __tablename__ = "topic_candidates"

    info_cluster_id = Column(Integer, ForeignKey("info_clusters.id"))
    title = Column(String(200), nullable=False)
    weighted_score = Column(Float, default=0.0)
    verdict = Column(String(20), default="pending")

    # 关系
    persona_reviews = relationship("PersonaReview", back_populates="candidate")
    score = relationship("CandidateScore", back_populates="candidate", uselist=False)
```

```java
// Java (JPA) 等价写法
@Entity
@Table(name = "topic_candidates")
public class TopicCandidate extends BaseEntity {

    @ManyToOne
    @JoinColumn(name = "info_cluster_id")
    private InfoCluster infoCluster;

    @Column(nullable = false)
    private String title;

    @Column
    private Double weightedScore;

    @OneToMany(mappedBy = "candidate")
    private List<PersonaReview> personaReviews;

    @OneToOne(mappedBy = "candidate")
    private CandidateScore score;
}
```

---

## 10. Python / FastAPI 常见问题

### 10.1 `Depends()` — FastAPI 的依赖注入

Spring Boot 用 `@Autowired` 自动注入 Bean。FastAPI 用 `Depends()` 函数手动声明依赖：

```python
# FastAPI 的依赖注入
@router.get("/topics")
async def get_topics(
    db: AsyncSession = Depends(get_db),       # 注入数据库 session
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):
    # db 和 current_user 由 FastAPI 自动解析并传入
    pass

# get_db 是一个 generator 函数（相当于 @Bean）
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session          # yield 之前的代码 = @PostConstruct
                               # yield 之后的代码 = @PreDestroy
```

**类比 Spring**：
- `Depends(get_db)` ≈ `@Autowired EntityManager`
- `Depends(get_current_user)` ≈ `@AuthenticationPrincipal User user`

### 10.2 async/await — Python 的异步编程

Python 的 `async/await` 类似 Java 的 `CompletableFuture`，但语法更简洁：

```python
# Python (async/await)
async def get_user(user_id: int, db: AsyncSession):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

```java
// Java (Spring WebFlux / CompletableFuture)
public Mono<User> getUser(Long userId) {
    return userRepository.findById(userId);
}
```

**重要**：本项目**同时使用 async 和 sync 两种模式**：
- **FastAPI 路由**：用 async + `AsyncSession`（异步）
- **Celery 任务**：用 sync + `SessionLocal`（同步，因为 Celery worker 不支持 async）

### 10.3 Pydantic — 数据校验

Pydantic 之于 Python ≈ Bean Validation 之于 Java：

```python
# Python (Pydantic)
class CandidateFromA(BaseModel):
    title: str = Field(min_length=10, max_length=40)
    direction: str
    score: float = Field(ge=0, le=10)

# 自动校验：title 长度不对会 422，score 超范围会 422
```

```java
// Java (Bean Validation)
public class CandidateFromA {
    @Size(min = 10, max = 40)
    private String title;

    @NotNull
    private String direction;

    @Min(0) @Max(10)
    private Double score;
}
```

### 10.4 虚拟环境 — Python 的"依赖隔离"

Java 项目用 Maven 管理依赖，每个项目独立。Python 默认全局安装包，所以需要虚拟环境：

```bash
# 创建虚拟环境（只需一次）
python3 -m venv .venv

# 激活（每次打开终端都要执行）
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 退出虚拟环境
deactivate
```

**类比**：`.venv/` 就像一个独立的 Maven 本地仓库，只包含这个项目需要的包。

### 10.5 `yield` — 依赖注入的生命周期

Python 的 `yield` 关键字在依赖注入中有特殊含义：

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session        # ← 这里把 session 交给路由函数使用
            await session.commit()   # yield 之后 = 请求结束后的清理
        except Exception:
            await session.rollback()
        finally:
            await session.close()
```

**类比 Spring**：
- `yield session` 之前 → `@PostConstruct`（初始化）
- `yield session` 本身 → 把资源注入给调用方
- `yield session` 之后 → `@PreDestroy`（清理）

### 10.6 `asyncio.run()` vs 同步调用

```bash
# 同步脚本直接运行
python run_mining.py

# 如果脚本内部用了 async，需要用 asyncio.run()
python -c "import asyncio; asyncio.run(main())"
```

### 10.7 requirements.txt vs pom.xml

```txt
# requirements.txt（Python）
fastapi==0.109.0          # ← 相当于 <dependency>
uvicorn==0.27.0           #   groupId:artifactId:version
sqlalchemy==2.0.25
```

```xml
<!-- pom.xml（Java）-->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
    <version>3.2.0</version>
</dependency>
```

---

## 11. 部署

### 11.1 Docker Compose（推荐）

```bash
# 一键启动所有服务
docker-compose up -d

# 7 个服务：
# - frontend (Node.js, port 3000)
# - backend (FastAPI, port 8000)
# - postgres (PostgreSQL 16 + pgvector)
# - redis (Redis 7)
# - celery-worker (异步任务)
# - celery-beat (定时任务调度)
# - nginx (反向代理, port 80/443)
```

### 11.2 本地开发模式

```bash
# 终端 1：后端
cd backend && source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2：前端
cd frontend
npm run dev
```

### 11.3 Celery 定时任务

```bash
# 启动 Celery worker
celery -A app.tasks worker -l info

# 启动定时调度器
celery -A app.tasks beat -l info
```

已配置的定时任务：
- 每日 6:00 — 全量抓取
- 每小时 — RSS 抓取
- 每 6 小时 — 微信搜索
- 每 30 分钟 — 预处理

---

## 12. 常见问题排查

### 12.1 启动报 ModuleNotFoundError

```bash
# 确保激活了虚拟环境
source .venv/bin/activate

# 确认当前 Python 路径
which python
# 应该显示 .../backend/.venv/bin/python
```

### 12.2 数据库连接失败

```bash
# 检查 .env 中 POSTGRES_PASSWORD
# 留空 = 使用 SQLite（开发模式）
# 填写 = 使用 PostgreSQL（需要先启动 PostgreSQL）
```

### 12.3 前端 401 Unauthorized

检查 `frontend/src/api/api.js` 是否正确导入和使用了 `get`/`post` 方法（而非直接用 axios）：

```javascript
// ✅ 正确
import { get, post } from '@/api/api'
const res = await get('/topic-candidates', params)

// ❌ 错误（没有自动注入 token）
import axios from 'axios'
const res = await axios.get('/api/v1/topic-candidates')
```

### 12.4 后端端口被占用

```bash
# 查找占用 8000 端口的进程
lsof -i :8000

# 杀掉进程
kill <PID>
```

### 12.5 Python 版本兼容

本项目使用 Python 3.9，不能使用 3.10+ 的语法：

```python
# ❌ Python 3.10+ 语法（本项目不能用）
def get_user() -> User | None:
    ...

# ✅ Python 3.9 兼容写法
from typing import Optional
def get_user() -> Optional[User]:
    ...
```
