# 前端 smoke / 回归门禁

本流程来自 2026-07-31 商稿 brief 上传事故：构建成功不能证明真实文件选择器、拖拽、键盘操作或布局正确。

## 本地必跑

在 `frontend/` 目录执行：

    npm ci
    npm run test:regression

`test:regression` 分为两层：

| 层级 | 命令 | 覆盖内容 | 是否请求真实后端 |
| --- | --- | --- | --- |
| 规则回归 | `npm run test:unit` | 文件扩展名、10 MiB 边界 | 否 |
| 浏览器 smoke | `npm run test:smoke` | 实际 Vite 预览、认证/权益 mock、点击、键盘、第二个 `v-for` 上传区、拖拽中的 `.dropzone-active` 反馈、重复选择、错误重试、桌面和窄屏截图 | 否，上传/总结接口均被 mock |

`npm run test:smoke` 默认先 build，再启动临时的本地 Vite preview，退出时会关闭它。截图位于 `cypress/screenshots/`，不提交 Git；涉及上传区 CSS、`label/input`、拖拽或响应式布局的改动必须人工查看桌面和窄屏截图。

如已有临时环境，可显式指向它：

    CYPRESS_BASE_URL=http://127.0.0.1:4173 npm run test:smoke

## 商稿上传必须覆盖

1. 首个与新增后的第二个 brief 上传区均能触发文件选择器，且无浏览器未捕获异常。
2. 上传区可通过键盘聚焦，用 Enter 或 Space 触发选择器；不得恢复 `v-for` 中的动态 `$refs.click()`。
3. `.pdf/.docx/.txt/.md`、10 MiB 边界、非法扩展名、超限文件、拖拽中高亮、落下后清除状态、移除后的同名重选均正确处理。
4. 成功路径固定为 `POST /api/v1/feishu/brief/upload` 再 `POST /api/v1/feishu/brief/summarize`；失败后允许重试。
5. 1536 宽桌面和 390 宽窄屏下，上传框必须是完整、居中的 flex 容器，页面不得横向溢出。

## 发布后真实会话 smoke

本地 Cypress 的 `selectFile` 会绕过原生 chooser，不能替代生产交互验证。前端部署完成、容器状态确认后，使用真实登录会话运行：

    SMOKE_TARGET_URL=https://gzh.midonghub.com npm run smoke:production

脚本会打开有界面的浏览器，并在登录后检查上传区 DOM / 布局。按脚本提示手动验证全部 chooser、键盘 Enter/Space、桌面和窄屏视觉；只打开后取消，不要提交真实 brief。它会输出 console、network 和截图到 `output/playwright/practical-upload/`。

记录结论时分开写明：

- 本地构建与 mock 回归是否通过；
- 生产真实 chooser / 视觉 smoke 是否通过；
- 后端真实文件解析或实际接口是否另行验证。
