<template>
  <div class="profile-card feishu-connect-card">
    <div class="integration-card-inner">
      <div class="integration-card-header">
        <div>
          <h3>飞书 Brief 插件</h3>
          <p>无需绑定飞书账号，用浏览器插件读取你当前有权限查看的 Brief。</p>
        </div>
        <el-tag type="success" effect="light">推荐用法</el-tag>
      </div>

      <div class="plugin-guide">
        <div class="guide-step">
          <span class="guide-step-number">1</span>
          <div>
            <b>下载并解压插件</b>
            <p>先下载下面的 ZIP 压缩包，解压到一个不会随意移动的文件夹。</p>
          </div>
        </div>
        <div class="guide-step">
          <span class="guide-step-number">2</span>
          <div>
            <b>在 Chrome 中加载</b>
            <p>打开 <code>chrome://extensions</code>，开启右上角“开发者模式”，点击“加载已解压的扩展程序”，选择刚才解压的文件夹。</p>
          </div>
        </div>
        <div class="guide-step">
          <span class="guide-step-number">3</span>
          <div>
            <b>打开 Brief 并提取</b>
            <p>回到「实操 / 商稿」粘贴飞书链接，点击“打开并提取”，再按页面提示使用浏览器右上角插件。</p>
          </div>
        </div>
      </div>

      <div class="guide-notice">
        <strong>使用前请确认</strong>
        <span>当前飞书账号有文档权限；提取过程中请勿离开、点击或刷新飞书页面。</span>
      </div>

      <div class="guide-actions">
        <a class="guide-download-btn" href="/plugins/feishu-brief-extension-0.2.4.zip" download>
          <span aria-hidden="true">↓</span> 下载插件 ZIP
        </a>
        <el-button type="primary" @click="goToPractical">去实操 / 商稿导入 Brief</el-button>
        <span class="guide-hint">这是开发者模式版本，更新后在扩展页点击“重新加载”</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
const goToPractical = () => router.push('/creation/practical')
</script>

<style scoped>
.integration-card-inner { padding: 2px 0; }
.integration-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.integration-card-header h3 { margin: 0 0 5px; color: var(--ink); font-size: 17px; font-weight: 600; }
.integration-card-header p { margin: 0; color: var(--ink-4); font-size: 13px; line-height: 1.6; }
.plugin-guide {
  display: grid;
  gap: 10px;
  padding: 16px 18px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 12px;
  background: var(--paper, #fff);
}
.guide-step { display: flex; align-items: flex-start; gap: 11px; }
.guide-step-number {
  display: inline-flex;
  width: 23px;
  height: 23px;
  flex: 0 0 23px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--clay, #b86d53);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}
.guide-step b { display: block; margin: 1px 0 3px; color: var(--ink-2, #3a3935); font-size: 13px; }
.guide-step p { margin: 0; color: var(--ink-4); font-size: 12px; line-height: 1.6; }
.guide-step code { padding: 1px 4px; border-radius: 4px; background: var(--bone, #f3eee7); color: var(--clay-deep, #8e513f); font-size: 11px; }
.guide-notice {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 9px;
  margin-top: 12px;
  padding: 11px 13px;
  border: 1px solid #e9c2ad;
  border-radius: 9px;
  background: #fff5ee;
  color: #8f4d38;
  font-size: 12px;
  line-height: 1.6;
}
.guide-notice strong { color: #8a3d29; }
.guide-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 15px; }
.guide-download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  box-sizing: border-box;
  padding: 0 14px;
  border: 1px solid var(--clay, #b86d53);
  border-radius: 6px;
  background: #fff;
  color: var(--clay-deep, #8e513f);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: background .18s, color .18s, border-color .18s;
}
.guide-download-btn:hover { background: var(--clay-tint, #fbede7); border-color: var(--clay-deep, #8e513f); color: var(--clay-deep, #8e513f); }
.guide-hint { color: var(--ink-4); font-size: 11px; }
@media (max-width: 768px) {
  .integration-card-header { align-items: flex-start; }
  .guide-actions { align-items: flex-start; flex-direction: column; gap: 7px; }
}
</style>
