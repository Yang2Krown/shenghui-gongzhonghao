# 公众号转小红书 · 发布助手（Chrome 插件 · 内部版）

让网页生成好的长文，在**用户自己浏览器、用户自己已登录的小红书账号**里自动填充、排版。
不需要服务器开浏览器，不需要扫码，天然多账号。

## 一、安装（一次性，约 5 步）

1. 下载/拷贝整个 `xhs-extension` 文件夹到本地。
2. Chrome 地址栏打开 `chrome://extensions`。
3. 右上角打开「**开发者模式**」。
4. 点「**加载已解压的扩展程序**」，选中 `xhs-extension` 文件夹。
5. 看到「公众号转小红书 · 发布助手」出现即成功。

> 之后保持在 Chrome 里**登录你自己的小红书**即可，发布时用的就是这个号。

## 二、配置网页域名（重要）

插件只在指定网页上生效。编辑 `manifest.json` 的 `content_scripts[].matches`，
加入你访问网页的地址，例如：

```json
"matches": [
  "http://localhost/*",
  "http://192.168.0.246/*",
  "https://你的正式域名/*"
]
```

改完回 `chrome://extensions` 点插件的「**重新加载**」。

## 三、网页如何调用插件（前端对接）

插件通过 `window.postMessage` 通信，前端不用知道插件 ID。

**发起发布：**

```js
window.postMessage({
  __gzhXhs: true,
  dir: 'to-ext',
  type: 'publish',
  payload: {
    title: '标题',
    description: '发布页正文描述（可选，长文用）',
    blocks: [
      { type: 'text',  content: '第一段...\n第二段...' },
      { type: 'image', url: 'https://oss公网可访问的图片url', alt: '' },
      { type: 'text',  content: '继续...' }
    ]
  }
}, '*');
```

- `blocks` 按原文顺序排列；图片用**公网可访问的 url**（你现在的 OSS 链接即可，
  插件后台会 fetch 下来再塞进小红书）。
- 段落定位：图片会插到它前面那段文字之后。

**接收进度 / 模板 / 完成：**

```js
window.addEventListener('message', (e) => {
  const m = e.data;
  if (!m || m.__gzhXhs !== true || m.dir !== 'to-page') return;
  switch (m.type) {
    case 'ready':      /* 插件已安装就绪 / 或流程已就绪待发布 */ break;
    case 'progress':   console.log('进度', m.step, m.detail); break;
    case 'templates':  /* m.templates 是模板名数组，展示给用户选 */ break;
    case 'error':      console.error('出错', m.error); break;
  }
});
```

**用户选好模板后，回传选择：**

```js
window.postMessage({
  __gzhXhs: true, dir: 'to-ext',
  type: 'selectTemplate', payload: { name: '用户选的模板名' }
}, '*');
```

之后插件会自动「选模板 → 下一步 → 填描述」，最后推 `{type:'ready'}`。
**v1 不自动点发布**——请用户在小红书标签页里检查无误后自己点「发布」。

## 四、流程总览

```
网页 postMessage(publish)
   → 插件打开/复用小红书长文页
   → 进入编辑器 → 填标题 → 填正文
   → 后台 fetch 各图片 → 逐张塞进小红书(用户号上传到小红书CDN)
   → 一键排版 → 把模板列表推回网页
网页展示模板 → 用户选 → postMessage(selectTemplate)
   → 插件 选模板 → 下一步 → 填描述 → 推 ready
用户在小红书页确认 → 手动点「发布」
```

## 五、与本地 Python 版的区别

| | 本地 Python(CDP) | 本插件 |
|---|---|---|
| 在哪运行 | 跑后端那台机器 | 每个用户自己的浏览器 |
| 小红书登录 | 该机器的 Chrome profile | 用户浏览器里已登录的号 |
| 图片上传 | `setFileInputFiles`(磁盘路径) | fetch 字节→页面内重建 File→塞输入框 |
| 多账号 | 难 | 天然支持 |
| 部署 | 服务器够不着用户 | 服务器只生成内容，发布在用户端 |

## 六、已知边界 / 待办

- v1 不自动发布（安全）。需要的话可加「自动点发布」开关。
- 图片节点是否插到精确位置依赖小红书把图插在光标处；若发现位置不准，
  退而求其次会聚在文末，不影响发布。
- 图标指纹 `M6.91635 8.25017` 若小红书改版需更新（见 `publish-main.js`）。
