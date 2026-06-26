# 飞书商单 Brief 接入方案

> 目标：在系统里贴一个飞书文档/多维表格链接（客户给的商单写作要求），点「开始研究」，
> 系统自动读取内容 → AI 分析总结成结构化 brief → 喂进现有 practical 研究 + 创作流程。
> 不回写飞书。后期再加「brief 检查」环节。

---

## 0. 一句话结论（已实测验证 ✅）

**实测结果**：商单 brief 文档虽在**客户企业**（`my.feishu.cn`），但用**用户身份**
（`user_access_token`，即本人账号被授予阅读权）通过 wiki/docx API **能完整读到**。
> 测试用例：美图设计室 618 商单 brief（wiki 链接），用 `lark-cli docs +fetch --as user` 一次读出全文。
> 之前「跨租户读不到」的结论只适用于**应用身份（bot / tenant_access_token）**；换成用户授权即成立。

**因此「贴飞书链接 → 自动读」对主力场景可行。** 关键是鉴权必须走**用户 OAuth 授权**拿
`user_access_token`，而不是应用级 `tenant_access_token`（见第 3 节，已重写）。

主路顺序：飞书链接读取（用户授权）/ 粘贴 / 上传 → AI 结构化总结 → 接入现有 practical 流程。
真正高价值的是 BriefSummarizer（结构化）和后期 brief 检查，与来源无关，做了长期可用。

---

## 1. 关键约束：身份类型（实测已澄清）

飞书 API 读文档有两种身份，跨租户能力天差地别：

| 身份 | token | 跨客户企业文档 | 说明 |
|------|-------|----------------|------|
| 应用身份 bot | `tenant_access_token` | ❌ 读不到 | 只能读应用自己企业内的资源 |
| 用户身份 user | `user_access_token` | ✅ **能读** | 代表真人，只要本人对该文档有阅读权即可（**实测通过**） |

**结论：必须走用户身份。** 商单 brief 在客户企业里、客户把链接分享给你本人 →
你本人有阅读权 → 用 `user_access_token` 就能读。这正是本次实测验证的路径。

**产品化：多用户 = 每用户各自 OAuth 授权（已定）**
- 用户构成：**大多是个人版飞书 / 散户博主**（已确认）。商单是每个用户各自从客户那收的，
  不能共用运营者一个账号（会越权、混乱）。
- 与公众号配置的**关键差别**：公众号是每人粘贴自己的 AppID+Secret（app 级 token，无需真人授权）；
  飞书读文档要 `user_access_token`，必须真人 OAuth 授权，**且用户无需自建飞书应用**。
- 方案：**平台建 1 个自建应用**（app_id/app_secret 全局配置）+ **每个用户点【连接飞书】OAuth 授权一次**
  → 每人拿到专属 `user_access_token`/`refresh_token`，按 user_id 存表隔离。
- **个人版账号可授权自建应用读文档 = 已实测通过**（测试账号"用户054896"在 my.feishu.cn 读出客户文档），
  因此**不需要商店应用(ISV)上架**。
- token 自动续期：用 `refresh_token` 刷新（lark-cli 已自动；自研需实现）。

兜底来源依然保留（粘贴 / 上传 docx·pdf，复用 `extract_text()`），覆盖未授权或临时情况。

### 1.1 每用户飞书授权数据模型（对齐 wechat_accounts）
```python
class FeishuAuth(BaseModel):           # 按 user_id 隔离
    user_id: int                       # FK -> users.id，唯一
    feishu_user_name: str | None       # 显示用（如"用户054896"）
    feishu_open_id: str | None
    user_access_token: str             # 加密存
    refresh_token: str                 # 加密存
    expires_at: datetime
    scopes: str                        # docx/wiki/drive readonly
```

### 1.2 授权流程（二选一，第一期建议设备码式）
- **设备码式**（lark-cli 用的）：后端发起 → 返回 verify URL + user_code → 前端展示给用户打开同意 →
  后端轮询拿 token。**无需回调基建，实现快**，第一期首选。
- **网页跳转式（授权码模式）**：点按钮跳飞书 → 同意 → 回调地址带 code → 换 token。体验更顺，需配回调。

---

## 2. 整体架构

```
前端：商单 brief 输入区
  ├─ Tab1 贴飞书链接（docx / wiki / bitable 记录）
  ├─ Tab2 粘贴文本
  └─ Tab3 上传文件(docx/pdf/txt)   ← 复用现有 extract_text
        │
        ▼
后端 BriefSourceResolver（来源层，可插拔）
  ├─ FeishuDocReader     ← docx raw_content API
  ├─ FeishuBitableReader ← bitable records API
  ├─ FeishuWikiResolver  ← wiki node → obj_token 再转上面两者
  ├─ PastedTextReader
  └─ FileReader          ← 现有 extract_text()
        │  得到「原始 brief 文本」
        ▼
BriefSummarizer（AI 总结，新增）
  把杂乱要求 → 结构化 StructuredBrief
  { product, brief, banned[], tone, must_cover[], audience, ... }
        │
        ▼
复用现有 practical 流程
  research_product(product, brief)  →  前端研究确认/卖点选择  →
  generate_practical_draft(..., brief_banned, brief_tone)
        │
        ▼
（后期）brief 检查：成稿 vs StructuredBrief 逐项核对
```

---

## 3. 飞书 API 选型（用户身份直读）

### 3.1 鉴权（用户 OAuth，已实测可行）
1. 飞书后台建「自建应用」→ 拿 `app_id` + `app_secret`。
2. 开权限范围（应用后台勾选并发版）：
   - 文档：`docx:document:readonly`
   - 知识库：`wiki:wiki:readonly`（wiki 链接必需）
   - 多维表格：`bitable:app:readonly`（brief 在表格里时）
   - 云空间：`drive:drive:readonly`
3. **用户授权拿 `user_access_token`**（关键，跨租户靠这个）：
   - OAuth 授权码流程：用户跳转飞书授权 → 回调拿 code → 换 `user_access_token` + `refresh_token`。
   - `user_access_token` 有效期短，用 `refresh_token` 自动续期；服务端持久化（按 memory 约定 secret 不进仓库）。
   - 运营者只需授权一次，后端长期用这套 token 读所有商单文档。
4. **不需要**把应用加为客户文档的协作者——靠的是**你本人**已有的阅读权。

> 验证记录：`lark-cli config init` 建应用 → `lark-cli auth login --scope "docx:document:readonly wiki:wiki:readonly drive:drive:readonly"`
> 用户授权 → `lark-cli docs +fetch --api-version v2 --doc <wiki链接> --as user` 成功读出客户企业文档全文。
> 自研产品即把 lark-cli 这套 OAuth + token 刷新逻辑实现到后端；或第一期直接在后端 shell 调 lark-cli 也能跑通。

### 3.2 读文档内容
| 类型 | 接口 | 返回 |
|------|------|------|
| 新版文档纯文本 | `GET /open-apis/docx/v1/documents/{document_id}/raw_content` | 纯文本，最适合喂 AI |
| 文档结构化块 | `GET /open-apis/docx/v1/documents/{document_id}/blocks` | 需要保留结构时用 |
| 多维表格筛选行 | `POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search` | brief 在表格里时 |
| 表格字段定义 | `GET .../tables/{table_id}/fields` | 列名→brief 字段映射 |
| 知识库节点转 token | `GET /open-apis/wiki/v2/spaces/get_node?token={node_token}` | wiki 链接先转成 obj_token |

### 3.3 从链接解析 token（resolver 核心）
- `feishu.cn/docx/{document_id}` → docx
- `feishu.cn/base/{app_token}?table={table_id}&view=...` → bitable
- `feishu.cn/wiki/{node_token}` → 先调 wiki get_node 拿 `obj_type` + `obj_token`，再分发
- 旧版 `feishu.cn/docs/{token}` → 旧文档 API（如确实遇到再加）

---

## 4. 后端落地

### 4.1 新增文件
```
app/services/feishu/
  __init__.py
  client.py          # user_access_token 持久化 + refresh 自动续期 + httpx 封装
  reader.py          # BriefSourceResolver：链接/文本/文件 → 原始文本
  summarizer.py      # 原始文本 → StructuredBrief（调 LLM）
app/schemas/brief.py # StructuredBrief / BriefSourceRequest
app/api/v1/brief.py  # 新接口（见 4.3）
```

### 4.2 配置（app/core/config.py）
```python
FEISHU_APP_ID: str = ""
FEISHU_APP_SECRET: str = ""   # 走 .env / .env.production，不硬编码
FEISHU_API_BASE: str = "https://open.feishu.cn/open-apis"
```
> 按 memory 约定：secret 不进仓库，服务器值放 .env.production。

### 4.3 新接口
```
POST /api/v1/brief/resolve
  body: { source_type: "feishu_link"|"text"|"file", value: str / 文件 }
  resp: { raw_text: str, doc_title: str }      # 先把内容拉回来给用户确认

POST /api/v1/brief/summarize
  body: { raw_text: str }
  resp: StructuredBrief                          # AI 总结结果，前端可编辑

# 之后直接复用现有 POST /practical/research（传 summarized.product / brief）
```
> 拆成 resolve / summarize 两步，是为了让用户在「研究确认」之前先看一眼读到的内容和总结，
> 与你现有 practical「两段式 + 中间确认」的设计一致。

### 4.4 复用点
- 文件解析：`app/utils/file_extractor.py::extract_text`（docx/pdf/txt/图片 OCR 都有）
- 研究/创作：`research_product(product, brief)` / `generate_practical_draft(..., brief_banned, brief_tone)`
- 进度流：`progress_store` + SSE，沿用 practical 的 run_id 模式
- 积分：沿用 `CreditService`，给 brief 解析/总结按需定价（或并入 research）

### 4.5 StructuredBrief 字段（按真实 brief 校准）
> 字段设计参考实测的「美图设计室 618」brief，覆盖其全部要素：

```python
class StructuredBrief(BaseModel):
    product: str            # 产品/工具名（如「美图设计室」）→ research 的 product
    brief: str              # 归纳后的写作要求正文 → research 的 brief
    core_message: str | None  # 核心主张（如「别人卷生成，美图卷成果」）
    must_cover: list[str]   # 必须传达的点（0门槛/案例展示/影像节带图…）→ 后期 brief 检查
    tone: str | None        # 调性（如「通俗易懂、避免晦涩术语」）→ draft 的 brief_tone
    banned: list[str]       # 红线/禁忌（如「不提竞品」「不拼广」）→ draft 的 brief_banned
    cta: str | None         # 引导动作（评论区领福利/专属链接+邀请码）
    audience: str | None    # 目标读者
    publish: str | None     # 发布档期（如「6/18 早8点&中午11点」）
    review_notes: str | None  # 审核要求（成片需品牌方确认、提供生成链接等）
    notes: str | None       # 其他约束
```
> 真实 brief 里图片、嵌入表格(`<sheet>`/`<bitable>`)、链接较多；纯文本总结即可满足写作，
> 嵌入表格如含关键信息可后续按 token 下钻（lark-sheets / lark-base），第一期可忽略。

---

## 5. 前端改动
- 在「实操/商稿创作」入口前加一个 **brief 来源区**（Tab：飞书链接 / 粘贴 / 上传）。
- 「读取」后展示原始内容 + AI 总结的 StructuredBrief，**允许用户编辑**。
- 确认后把 product + brief 带入现有研究流程，后续不变。

---

## 6. 后期：Brief 检查环节（先占位，后实现）
- 成稿生成后，新增 `POST /api/v1/brief/check`：
  - 输入：成稿正文 + StructuredBrief
  - LLM 逐项核对：must_cover 是否都写到、banned 是否误用、tone/audience 是否符合、字数等硬约束
  - 输出：逐条 ✅/⚠️/❌ + 修改建议，前端展示成 checklist
- 与生成流程解耦，可对任意成稿单独跑。

---

## 7. 风险 / 待确认
1. **租户归属（最重要）**：你收到的 brief 文档到底在你自己的飞书企业，还是客户企业？
   决定第一期是否要做飞书 API 直读，还是先只做粘贴/上传 + 转存指引。
2. 飞书应用审批：自建应用开权限需企业管理员发版，若你不是管理员需协调。
3. wiki / 旧版 docs 链接形态多，第一期可只支持 docx + bitable，其余按需补。
4. raw_content 会丢表格/图片结构；若 brief 关键信息在表格里，可能要改用 blocks 接口。

---

## 8. 建议的实施顺序（按实测结果调整）
1. **P0（主路）**：飞书链接读取（用户授权，docx + wiki）+ 粘贴/上传兜底 → BriefSummarizer → 接 practical。
   - 实测已证明飞书直读可行，直接作为第一期主功能。
   - 第一期后端可先 shell 调已配置好的 lark-cli 跑通，二期再把 OAuth/刷新逻辑原生化到后端。
2. **P1**：brief 检查环节（成稿 vs StructuredBrief 逐项核对）。← 你提到的下一步，价值高。
3. **P2（可选）**：bitable 链接 + 嵌入表格下钻。

## 9. 已定 / 待定

**已定：**
- 多用户：每用户各自 OAuth 授权，平台 1 个自建应用 + 按 user_id 存 token（个人版可用，实测通过）。
- 不做商店应用(ISV)上架。

**待你拍板：**
- **授权流程**：第一期用设备码式（无回调、快）还是直接做网页跳转式？
- **鉴权实现**：后端原生实现飞书 OAuth+刷新，还是第一期先 shell 调 lark-cli 验证打通再原生化？
  ⚠️ 注意：lark-cli 的 token 存在本机单份，**不天然支持多用户隔离**；多用户最终一定要后端原生存
  per-user token。shell 调 lark-cli 只适合「你自己单用户」的快速验证，不适合多用户正式版。
