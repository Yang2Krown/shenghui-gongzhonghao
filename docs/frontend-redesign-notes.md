# 前端重构记录

## 已完成的修改

### 1. 侧边栏导航重构 (AppLayout.vue)
- **旧导航结构**：
  - 话题库 → 内容资讯
  - 我的创作
  - 自定义选题
  - 标题工具（子菜单：智能起标题 / 芒格标题生成 / 芒格标题评分）
  - 公众号转小红书
  - 生成记录
  - 设置

- **新导航结构**（严格按照设计稿）：
  - 内容资讯
  - 创作工具（可折叠分组）
    - 创作角度
    - 大纲生成
    - 正文生成
    - 标题生成
  - 内容仿写（可折叠分组）
    - 转写
    - 仿写
  - 创作历史
  - 个人信息

### 2. 页面重命名
- "话题库" → "内容资讯" (TopicClusterList.vue)
- "生成记录" → "创作历史" (GenerationHistory.vue)
- "设置" → "个人信息" (ProfileSettings.vue, 路由变更)

### 3. 新增页面
| 页面 | 路由 | 文件路径 |
|------|------|----------|
| 创作角度 | `/creation/angle` | `pages/tools/CreationAngle.vue` |
| 大纲生成 | `/creation/outline` | `pages/tools/CreationOutline.vue` |
| 正文生成 | `/creation/body` | `pages/tools/CreationBody.vue` |
| 标题生成 | `/creation/title` | `pages/tools/CreationTitle.vue` |
| 转写 | `/content-transform` | `pages/rewrite/ContentTransform.vue` |
| 仿写 | `/content-imitate` | `pages/rewrite/ContentImitate.vue` |

### 4. 新增共享组件
- `PipelineStepper.vue` - 创作流程进度条（角度→大纲→正文→标题）

### 5. 路由变更
- 新增路由：`/creation/angle`, `/creation/outline`, `/creation/body`, `/creation/title`, `/content-transform`, `/content-imitate`, `/creation-history`, `/profile`
- 保留旧路由兼容：`/topic-clusters`, `/history`, `/settings`, `/creation`
- 旧路由重定向：`/topics` → `/content-info`

---

## 丢失的后端交互（需要后续完善）

### 创作工具页面（4个）

#### 创作角度 (`CreationAngle.vue`)
- **当前状态**：使用模拟数据（MOCK_ANGLES）
- **需要接入的 API**：
  - `POST /api/v1/outlines/inspect-angle` - 生成创作角度
  - 请求参数：信息源列表（文字/PDF/链接）、创作偏好
  - 返回：角度列表（tag, title, desc, heat）

#### 大纲生成 (`CreationOutline.vue`)
- **当前状态**：使用模拟数据（MOCK_OUTLINE）
- **需要接入的 API**：
  - `POST /api/v1/outlines/generate` - 生成大纲
  - 请求参数：信息源列表、创作偏好
  - 返回：大纲标题 + 章节列表（h, points[]）

#### 正文生成 (`CreationBody.vue`)
- **当前状态**：使用模拟数据（MOCK_BODY）
- **需要接入的 API**：
  - `POST /api/v1/ai/generate` - 生成正文
  - 请求参数：大纲内容、创作偏好
  - 返回：正文文本

#### 标题生成 (`CreationTitle.vue`)
- **当前状态**：使用模拟数据（MOCK_TITLES）
- **需要接入的 API**：
  - `POST /api/v1/ai/generate` - 生成标题
  - 请求参数：正文内容（文字/链接/文档）、创作偏好
  - 返回：标题列表（title, score, tags[]）

### 内容仿写页面（2个）

#### 转写 (`ContentTransform.vue`)
- **当前状态**：使用模拟数据
- **需要接入的 API**：
  - `POST /api/v1/ai/transform` - 平台转写
  - 请求参数：源平台、目标平台、原文内容、额外要求
  - 返回：标题、正文、标签

#### 仿写 (`ContentImitate.vue`)
- **当前状态**：使用模拟数据
- **需要接入的 API**：
  - `POST /api/v1/ai/imitate` - 内容仿写
  - 请求参数：参考内容（链接/文字）、额外要求
  - 返回：标题、正文

### 共享功能缺失

1. **多信息源上传** - 创作角度和大纲生成页面支持多信息源（文字/PDF/链接），但 PDF 上传功能需要后端支持文件存储
2. **文件上传处理** - 当前只是前端选择文件名，需要后端接收和处理文件
3. **创作流程接力** - 页面间的参数传递（角度→大纲→正文→标题）已通过 query 实现，但需要后端支持状态恢复
4. **历史记录保存** - 新页面的生成结果需要保存到创作历史

### 现有页面路由兼容

以下旧路由已保留并重定向，确保用户书签和分享链接不失效：
- `/topics` → `/content-info`
- `/history` → `/creation-history`
- `/settings` → `/profile`
- `/topic-clusters` → `/content-info`（保留兼容）

### 侧边栏折叠功能
- 新侧边栏支持折叠/展开（点击顶部按钮）
- 折叠后宽度 64px，展开后 248px
- 折叠状态下只显示图标
