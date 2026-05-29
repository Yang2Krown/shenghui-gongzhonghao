# 前端页面迁移总结

## 迁移概览

按 Claude Design 设计稿，将前端页面从旧架构（话题库为核心）迁移到新架构（内容创作为核心）。

### 新导航结构

```
公众号创作台
├── 内容资讯          ← 首页（原话题库，改名+重构）
├── 创作工具（分组）
│   ├── 创作角度      ← 新建（原 CreationEditor 的角度体检拆出）
│   ├── 大纲生成      ← 新建（原 OutlinePanel 拆出）
│   ├── 正文生成      ← 新建（原 ContentPanel 拆出）
│   └── 标题生成      ← 重构（原 StandaloneTitleGeneration）
├── 内容仿写（分组）
│   ├── 公众号转小红书 ← 保留（原 WechatToXhs）
│   ├── 公众号仿写    ← 新建（后端未实现）
│   ├── 小红书转公众号 ← 新建（后端未实现）
│   ├── 抖音转公众号   ← 新建（后端未实现）
│   ├── 知乎转公众号   ← 新建（后端未实现）
│   └── 内容仿写      ← 新建（后端未实现）
├── 创作历史          ← 重构（原 GenerationHistory）
└── 个人信息          ← 重构（原 ProfileSettings，去掉风格训练）
```

## 已完成的迁移

### 1. 布局层
- **AppLayout.vue** — 完全重写，248px 侧边栏、可展开/折叠分组、面包屑导航
- **NavItem.vue** — 新建，自定义 SVG 图标的导航项组件
- **router.js** — 完全重写，匹配新导航结构，旧路由自动重定向

### 2. 内容资讯（FeedScreen）
- 从 TopicClusterList 迁移，保留：
  - 话题簇列表展示（卡片+瀑布流）
  - 类型筛选（全部/科技/商业/社会/文化/生活）
  - 手动抓取功能
  - 点击查看详情（详情+原文来源列表）
  - "用它创作"跳转到创作角度
- 接入后端 `/topic-clusters` API

### 3. 创作工具
- **创作角度（AngleTool）** — 新建，支持多信息源（文字/PDF/链接），调用 `/ai/angle` API
- **大纲生成（OutlineTool）** — 新建，支持多信息源+可选创作角度，调用 `/ai/outline` API
- **正文生成（BodyTool）** — 新建，给定大纲生成正文，调用 `/ai/body` API
- **标题生成（TitleTool）** — 从 StandaloneTitleGeneration 重构，支持文字/链接/文档三种来源
- 四个工具之间可通过参数传递实现接力（角度→大纲→正文→标题）

### 4. 内容仿写
- **公众号转小红书** — 保留原有功能，UI 按新设计重构
- **公众号仿写 / 小红书转公众号 / 抖音转公众号 / 知乎转公众号 / 内容仿写** — 新建页面，统一使用 RewriteTool 组件
- 所有仿写工具共用一套界面：转换方向示意 + 输入区 + 结果展示（标题+正文+标签）

### 5. 创作历史（HistoryScreen）
- 从 GenerationHistory 重构，保留：
  - 类型筛选（全部/创作工具/内容仿写）
  - 记录列表（类型标签、时间、字数、状态）
  - "查看"按钮跳转到对应页面

### 6. 个人信息（ProfileScreen）
- 从 ProfileSettings 简化，保留：
  - 用户头像+昵称+统计
  - 创作偏好（昵称、写作语气、个人简介）
  - 账户信息
  - 退出登录

### 7. 共享组件
- **MultiSourceInput** — 多信息源输入（文字/PDF/链接），用于创作角度和大纲生成
- **CopyBtn** — 复制按钮，带"已复制"反馈
- **Loading** — 加载状态，带旋转动画
- **RewriteTool** — 通用仿写工具组件，6个仿写页面共用

## 未实现的功能（需要后端支持）

### 高优先级
| 功能 | 说明 | 后端接口 |
|------|------|----------|
| 创作角度生成 | AI 分析信息源生成创作角度 | `POST /ai/angle` |
| 大纲生成 | AI 根据信息源+角度生成大纲 | `POST /ai/outline` |
| 正文生成 | AI 根据大纲生成正文 | `POST /ai/body` |
| 公众号仿写 | 给链接仿写公众号文章 | `POST /ai/rewrite` |
| 小红书转公众号 | 小红书笔记扩写为公众号长文 | `POST /ai/rewrite` |
| 抖音转公众号 | 抖音视频转公众号图文 | `POST /ai/rewrite` |
| 知乎转公众号 | 知乎回答转公众号长文 | `POST /ai/rewrite` |
| 内容仿写 | 输入文字内容进行风格仿写 | `POST /ai/rewrite` |

### 低优先级
| 功能 | 说明 |
|------|------|
| 文件上传 | PDF/Word 文件上传解析（前端 UI 已有，后端需处理） |
| 风格训练 | 原 ProfileSettings 的风格训练功能未迁移（新设计中未包含） |
| 候选选题清单 | 原 TopicCandidateList 未迁移（新设计中未包含） |
| 自定义选题 | 原 CustomTopic 未迁移（已重定向到创作角度） |
| 芒格标题生成/评分 | 原 MungerGeneration/TitleScorer 未迁移（已重定向到标题生成） |
| Chrome 扩展集成 | 原 WechatToXhs 的插件发布功能未迁移 |

## 已保留的旧路由（自动重定向）

| 旧路径 | 新路径 |
|--------|--------|
| `/topic-clusters` | `/` |
| `/topic-candidates` | `/` |
| `/creation` | `/` |
| `/creation/new` | `/` |
| `/creation/editor/:id` | `/` |
| `/creation/:id` | `/` |
| `/settings` | `/profile` |
| `/standalone-title` | `/title` |
| `/munger-generation` | `/title` |
| `/munger-scorer` | `/title` |
| `/custom-topic` | `/angle` |

## 保留的旧文件

以下旧页面文件仍保留在项目中，但不再被路由引用：
- `pages/topics/TopicClusterList.vue`
- `pages/topics/TopicClusterDetail.vue`
- `pages/topics/TopicCandidateList.vue`
- `pages/creation/CreationList.vue`
- `pages/creation/CreationEditor.vue`
- `pages/creation/CreationDraft.vue`
- `pages/titles/StandaloneTitleGeneration.vue`
- `pages/titles/MungerGeneration.vue`
- `pages/titles/TitleScorer.vue`
- `pages/conversion/WechatToXhs.vue`
- `pages/custom/CustomTopic.vue`
- `pages/history/GenerationHistory.vue`
- `pages/settings/ProfileSettings.vue`
- `components/creation/` (AgentStatusBar, AgentFeedbackPanel, OutlinePanel, TitlePanel, ContentPanel)
- `components/style/` (AddSourceModal, PreviewModal, RadarChart)

这些文件可以安全删除，确认新页面稳定后再清理。

## 技术变更

- 移除了 Element Plus 的 `el-menu` 导航，改用自定义 NavItem 组件（更灵活的样式控制）
- 侧边栏宽度从 240px 改为 248px
- 顶部栏简化为面包屑导航（移除了折叠按钮）
- 新增 `components/shared/` 目录存放跨页面复用的组件
- 新增 `pages/feed/`、`pages/tools/`、`pages/rewrite/`、`pages/history/`、`pages/profile/` 目录
