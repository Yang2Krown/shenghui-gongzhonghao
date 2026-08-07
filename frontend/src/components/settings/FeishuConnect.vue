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
      <div class="tutorial-browser-note" role="note">
        <strong>使用要求</strong>
        <span>目前只支持 Google Chrome（谷歌浏览器）</span>
      </div>

      <div class="tutorial-steps">
        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">1</span>
            <div class="tutorial-step-copy">
              <h4>下载并解压插件</h4>
              <p>在个人中心的飞书 Brief 插件卡片中，点击“下载插件 ZIP”。下载完成后，将压缩包解压到一个固定位置，后续不要随意移动或删除这个文件夹。</p>
              <a class="tutorial-inline-link" :href="pluginDownloadUrl" download>下载 feishu-brief-extension-0.2.4.zip</a>
            </div>
          </div>
          <figure class="tutorial-shot-figure">
            <img class="tutorial-shot" src="/images/feishu-tutorial/01-download.webp" alt="在个人中心点击下载插件 ZIP" loading="lazy" decoding="async" />
          </figure>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">2</span>
            <div class="tutorial-step-copy">
              <h4>打开 Chrome 扩展管理页并开启开发者模式</h4>
              <p>在 Chrome 地址栏输入 <code>chrome://extensions</code> 并回车，确认进入“扩展程序”页面。点击右上角“开发者模式”，页面上会出现“加载未打包的扩展程序”按钮。</p>
            </div>
          </div>
          <figure class="tutorial-shot-figure">
            <img class="tutorial-shot" src="/images/feishu-tutorial/02-developer-mode.webp" alt="Chrome 扩展管理页开启开发者模式" loading="lazy" decoding="async" />
          </figure>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">3</span>
            <div class="tutorial-step-copy">
              <h4>加载已解压的插件文件夹</h4>
              <p>点击“加载未打包的扩展程序”。在文件选择窗口中选择解压后的 <code>feishu-brief-extension-0.2.4</code> 文件夹，选择文件夹本身，不要进入文件夹再选某个文件，最后点击“选择”。</p>
            </div>
          </div>
          <figure class="tutorial-shot-figure">
            <img class="tutorial-shot" src="/images/feishu-tutorial/03-select-folder.webp" alt="在文件选择窗口选择解压后的插件文件夹" loading="lazy" decoding="async" />
          </figure>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">4</span>
            <div class="tutorial-step-copy">
              <h4>确认插件开启，并固定到浏览器工具栏</h4>
              <p>回到扩展管理页，在“飞书 Brief 导入”卡片右下角确认开关为蓝色。然后点击浏览器右上角的拼图图标，找到“飞书 Brief 导入”，点击图钉将它固定到工具栏。</p>
            </div>
          </div>
          <div class="tutorial-shot-grid">
            <figure class="tutorial-shot-figure">
              <img class="tutorial-shot" src="/images/feishu-tutorial/04-enable.webp" alt="确认飞书 Brief 导入插件开关为蓝色" loading="lazy" decoding="async" />
            </figure>
            <figure class="tutorial-shot-figure">
              <img class="tutorial-shot" src="/images/feishu-tutorial/05-pin.webp" alt="将飞书 Brief 导入插件固定到浏览器工具栏" loading="lazy" decoding="async" />
            </figure>
          </div>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">5</span>
            <div class="tutorial-step-copy">
              <h4>在实操 / 商稿中打开 Brief</h4>
              <p>进入「实操 / 商稿」，选择“飞书链接”，在输入框粘贴飞书文档或 Wiki 链接，点击“打开并提取”。网站会打开对应的飞书页面。</p>
              <el-button text type="primary" class="tutorial-practical-link" @click="goToPractical">现在去实操 / 商稿</el-button>
            </div>
          </div>
          <figure class="tutorial-shot-figure">
            <img class="tutorial-shot" src="/images/feishu-tutorial/06-paste-link.webp" alt="在实操商稿中选择飞书链接并点击打开并提取" loading="lazy" decoding="async" />
          </figure>
        </section>

        <section class="tutorial-step tutorial-step--important">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">6</span>
            <div class="tutorial-step-copy">
              <h4>从头到尾加载 Brief，再提取正文</h4>
              <p>进入飞书页面后，先确认当前账号有权限查看文档。请将 Brief 从头到尾加载一遍，再点击工具栏中的飞书插件，点击“提取当前文档”。</p>
              <div class="tutorial-warning">提取中请勿离开、点击或刷新飞书页面。长文档请等待提取完成后再进行下一步。</div>
            </div>
          </div>
          <figure class="tutorial-shot-figure">
            <img class="tutorial-shot" src="/images/feishu-tutorial/07-extract.webp" alt="在飞书页面点击插件并提取当前文档" loading="lazy" decoding="async" />
          </figure>
        </section>

        <section class="tutorial-step">
          <div class="tutorial-step-main">
            <span class="tutorial-step-number">7</span>
            <div class="tutorial-step-copy">
              <h4>检查内容并发送到网站</h4>
              <p>插件显示提取成功后，检查标题、字数和正文是否完整。确认无误后点击“发送到网站”，浏览器回到网站后，系统会继续读取并解析 Brief。</p>
            </div>
          </div>
          <figure class="tutorial-shot-figure">
            <img class="tutorial-shot" src="/images/feishu-tutorial/08-send.webp" alt="在插件预览区检查内容并发送到网站" loading="lazy" decoding="async" />
          </figure>
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
.tutorial-browser-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 9px 12px;
  border: 1px solid #ead6c7;
  border-radius: 8px;
  background: #fff8f2;
  color: var(--ink-3, #66615a);
  font-size: 12px;
  line-height: 1.5;
}
.tutorial-browser-note strong { color: var(--clay-deep, #8e513f); font-weight: 650; }

.tutorial-steps { display: grid; gap: 12px; }
.tutorial-step {
  display: flex;
  flex-direction: column;
  gap: 13px;
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
.tutorial-shot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding-left: 36px;
}
.tutorial-shot-figure {
  margin: 0;
  padding: 8px;
  border: 1px solid #eadfd7;
  border-radius: 9px;
  background: #fbf8f4;
}
.tutorial-shot {
  display: block;
  width: 100%;
  height: auto;
  max-height: 360px;
  object-fit: contain;
  border-radius: 5px;
  background: #fff;
}
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
  justify-content: flex-end;
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
  .tutorial-step { gap: 11px; }
  .tutorial-shot-grid { grid-template-columns: 1fr; padding-left: 0; }
  .tutorial-shot { max-height: 280px; }
  .tutorial-footer { align-items: flex-start; flex-direction: column; }
  .tutorial-footer-actions { width: 100%; flex-wrap: wrap; }
  :global(.feishu-tutorial-modal .el-dialog__body) { padding: 2px 16px 16px; }
}
</style>
