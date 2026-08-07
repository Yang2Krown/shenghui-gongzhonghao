<template>
  <div class="profile-card feishu-connect-card">
    <div class="integration-card-inner">
      <div class="integration-card-header">
        <div>
          <h3>飞书 Brief 插件</h3>
          <p>无需绑定飞书账号，用浏览器插件读取你当前有权限查看的 Brief。</p>
        </div>
      </div>

      <div class="feishu-summary">
        <div class="feishu-summary-icon" aria-hidden="true">↗</div>
        <div>
          <strong>把读取动作放在飞书页面完成</strong>
          <span>先打开有权限的文档，再从浏览器插件提取文字，确认后发送回网站分析。</span>
        </div>
      </div>

      <div class="guide-actions">
        <el-button type="primary" @click="tutorialVisible = true">查看安装教程</el-button>
        <a class="guide-download-btn" :href="pluginDownloadUrl" download>
          <span aria-hidden="true">↓</span> 下载插件 ZIP
        </a>
      </div>
    </div>
  </div>

  <el-dialog
    v-model="tutorialVisible"
    title="飞书 Brief 插件安装教程"
    width="760px"
    top="5vh"
    destroy-on-close
    align-center
    :close-on-click-modal="false"
    class="feishu-tutorial-dialog"
    modal-class="feishu-tutorial-modal"
  >
    <div class="feishu-tutorial">
      <div class="tutorial-intro">
        <div class="tutorial-intro-mark" aria-hidden="true">飞</div>
        <div>
          <strong>用你当前的飞书权限读取 Brief</strong>
          <p>插件只读取当前打开文档中你能看到的文字，不需要在网站绑定飞书账号。</p>
        </div>
      </div>

      <div class="tutorial-steps">
        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">1</span>
            <div class="tutorial-step-copy">
              <h4>下载并解压插件</h4>
              <p>点击下方“下载插件 ZIP”，将压缩包解压到一个固定文件夹。后续不要随意移动或删除这个文件夹。</p>
              <a class="tutorial-inline-link" :href="pluginDownloadUrl" download>下载 feishu-brief-extension-0.2.4.zip</a>
            </div>
          </div>
          <div class="tutorial-image-placeholder" aria-label="步骤一截图待补充">
            <span>待补充截图 01</span>
            <small>建议：下载文件与解压后的插件文件夹</small>
          </div>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">2</span>
            <div class="tutorial-step-copy">
              <h4>在 Chrome 中加载插件</h4>
              <p>在地址栏打开 <code>chrome://extensions</code>，开启右上角“开发者模式”，点击“加载已解压的扩展程序”，选择刚才解压的文件夹。</p>
              <p class="tutorial-muted">更新插件时，用新文件覆盖原文件夹，然后回到扩展管理页点击“重新加载”。</p>
            </div>
          </div>
          <div class="tutorial-image-placeholder" aria-label="步骤二截图待补充">
            <span>待补充截图 02</span>
            <small>建议：Chrome 扩展管理页与“加载已解压的扩展程序”</small>
          </div>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">3</span>
            <div class="tutorial-step-copy">
              <h4>从实操 / 商稿打开 Brief</h4>
              <p>回到「实操 / 商稿」，在“飞书链接”输入框粘贴文档或 Wiki 链接，点击“打开并提取”。网站会打开对应的飞书页面。</p>
              <el-button text type="primary" class="tutorial-practical-link" @click="goToPractical">现在去实操 / 商稿</el-button>
            </div>
          </div>
          <div class="tutorial-image-placeholder" aria-label="步骤三截图待补充">
            <span>待补充截图 03</span>
            <small>建议：网站中的飞书链接输入框</small>
          </div>
        </section>

        <section class="tutorial-step tutorial-step--important">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">4</span>
            <div class="tutorial-step-copy">
              <h4>从头到尾加载，再提取正文</h4>
              <p>确认当前账号可以正常查看 Brief。请先将 Brief 从头到尾加载一遍，再点击浏览器右上角的插件，选择“提取当前文档”。</p>
              <div class="tutorial-warning">提取中请勿离开、点击或刷新飞书页面。长文档请等待提取完成后再进行下一步。</div>
            </div>
          </div>
          <div class="tutorial-image-placeholder" aria-label="步骤四截图待补充">
            <span>待补充截图 04</span>
            <small>建议：打开的飞书 Brief 与浏览器插件按钮</small>
          </div>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">5</span>
            <div class="tutorial-step-copy">
              <h4>确认内容并发送回网站</h4>
              <p>在插件预览区检查标题、正文和字数是否完整；确认无误后点击“发送到网站”。浏览器回到网站后，系统会继续进行 Brief 解析。</p>
            </div>
          </div>
          <div class="tutorial-image-placeholder" aria-label="步骤五截图待补充">
            <span>待补充截图 05</span>
            <small>建议：插件预览与“发送到网站”按钮</small>
          </div>
        </section>
      </div>

      <div class="tutorial-notice">
        <strong>遇到问题时先检查</strong>
        <ul>
          <li>飞书页面显示“没有权限”时，需要先让文档所有者给当前飞书账号开通阅读权限。</li>
          <li>提取内容不完整时，回到文档顶部重新加载，等待页面内容全部出现后再提取。</li>
          <li>插件没有反应时，在 <code>chrome://extensions</code> 中确认插件已启用，并点击一次“重新加载”。</li>
        </ul>
      </div>

      <div class="tutorial-footer">
        <span>安装一次后，之后只需打开有权限的 Brief 并提取即可。</span>
        <div class="tutorial-footer-actions">
          <a class="guide-download-btn" :href="pluginDownloadUrl" download>
            <span aria-hidden="true">↓</span> 下载插件 ZIP
          </a>
          <el-button type="primary" @click="goToPractical">去实操 / 商稿</el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const tutorialVisible = ref(false)
const pluginDownloadUrl = '/plugins/feishu-brief-extension-0.2.4.zip'

const goToPractical = () => {
  tutorialVisible.value = false
  router.push('/creation/practical')
}
</script>

<style scoped>
.feishu-connect-card {
  position: relative;
  box-sizing: border-box;
  min-height: 244px;
  padding: 24px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 16px;
  background: var(--paper, #fff);
  display: flex;
  flex-direction: column;
}

.integration-card-inner { padding: 2px 0; }
.integration-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.integration-card-header h3 { margin: 0 0 5px; color: var(--ink); font-size: 17px; font-weight: 600; }
.integration-card-header p { margin: 0; color: var(--ink-4); font-size: 13px; line-height: 1.6; }

.feishu-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 15px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 11px;
  background: var(--paper, #fff);
}
.feishu-summary-icon {
  display: inline-flex;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--clay, #b86d53);
  color: #fff;
  font-size: 17px;
  font-weight: 700;
}
.feishu-summary strong { display: block; margin-bottom: 2px; color: var(--ink-2, #3a3935); font-size: 13px; }
.feishu-summary span { display: block; color: var(--ink-4); font-size: 12px; line-height: 1.5; }

.guide-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: auto; padding-top: 15px; }
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

.feishu-tutorial { color: var(--ink-2, #3a3935); }
.tutorial-intro {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
  padding: 14px 16px;
  border: 1px solid #ead6c7;
  border-radius: 11px;
  background: #fff8f2;
}
.tutorial-intro-mark {
  display: inline-flex;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: var(--clay, #b86d53);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
}
.tutorial-intro strong { display: block; margin: 1px 0 4px; font-size: 14px; }
.tutorial-intro p { margin: 0; color: var(--ink-4); font-size: 12px; line-height: 1.6; }

.tutorial-steps { display: grid; gap: 12px; }
.tutorial-step {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px;
  gap: 16px;
  padding: 15px 16px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 11px;
  background: var(--paper, #fff);
}
.tutorial-step--important { border-color: #e7b79f; background: #fffaf7; }
.tutorial-step-main { display: flex; align-items: flex-start; gap: 11px; min-width: 0; }
.tutorial-step-number {
  display: inline-flex;
  width: 25px;
  height: 25px;
  flex: 0 0 25px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--clay, #b86d53);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}
.tutorial-step-copy { min-width: 0; }
.tutorial-step-copy h4 { margin: 1px 0 5px; color: var(--ink-2, #3a3935); font-size: 14px; font-weight: 650; }
.tutorial-step-copy p { margin: 0; color: var(--ink-3, #66615a); font-size: 12px; line-height: 1.7; }
.tutorial-step-copy code,
.tutorial-notice code {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--bone, #f3eee7);
  color: var(--clay-deep, #8e513f);
  font-size: 11px;
}
.tutorial-muted { margin-top: 5px !important; color: var(--ink-4) !important; }
.tutorial-inline-link { display: inline-block; margin-top: 7px; color: var(--clay-deep, #8e513f); font-size: 12px; text-decoration: none; }
.tutorial-inline-link:hover { text-decoration: underline; }
.tutorial-practical-link { margin: 6px 0 0 -8px; padding: 0 8px; font-size: 12px; }
.tutorial-warning {
  margin-top: 10px;
  padding: 8px 10px;
  border-left: 3px solid var(--clay, #b86d53);
  border-radius: 0 6px 6px 0;
  background: #fff0e8;
  color: #8a3d29;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.6;
}
.tutorial-image-placeholder {
  display: flex;
  min-height: 106px;
  box-sizing: border-box;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px;
  border: 1px dashed #d6c6b8;
  border-radius: 8px;
  background: #fbf8f4;
  color: var(--ink-4);
  text-align: center;
}
.tutorial-image-placeholder span { color: var(--clay-deep, #8e513f); font-size: 12px; font-weight: 650; }
.tutorial-image-placeholder small { max-width: 150px; font-size: 10px; line-height: 1.45; }

.tutorial-notice {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid #e9c2ad;
  border-radius: 10px;
  background: #fff5ee;
  color: #8f4d38;
  font-size: 12px;
  line-height: 1.6;
}
.tutorial-notice strong { display: block; margin-bottom: 5px; color: #8a3d29; }
.tutorial-notice ul { margin: 0; padding-left: 18px; }
.tutorial-notice li + li { margin-top: 3px; }

.tutorial-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 16px;
  color: var(--ink-4);
  font-size: 11px;
  line-height: 1.5;
}
.tutorial-footer-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 9px; }

:global(.feishu-tutorial-modal .el-dialog) { max-width: calc(100vw - 32px); }
:global(.feishu-tutorial-modal .el-dialog__body) { padding: 4px 22px 22px; }

@media (max-width: 768px) {
  .feishu-connect-card { min-height: 0; }
  .integration-card-header { align-items: flex-start; }
  .guide-actions { align-items: flex-start; flex-direction: column; gap: 8px; }
  .tutorial-step { grid-template-columns: 1fr; gap: 11px; }
  .tutorial-image-placeholder { min-height: 90px; }
  .tutorial-footer { align-items: flex-start; flex-direction: column; }
  .tutorial-footer-actions { width: 100%; flex-wrap: wrap; }
  :global(.feishu-tutorial-modal .el-dialog__body) { padding: 2px 16px 16px; }
}
</style>
