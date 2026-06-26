<template>
  <div class="page-wrap">
    <!-- Hero + 步骤条 -->
    <div class="tool-hero">
      <div class="kicker"><el-icon :size="14"><MagicStick /></el-icon> 创作工具 · 实操 / 商稿</div>
      <h1 class="serif">输入一个产品，<span class="text-clay">AI 先调研，再带你写实操文</span></h1>
      <p class="desc">产品太新搜不到？AI 联网调研最新信息 → 你确认 → 选要演示的功能 → 生成实操脚本。截图你自己补，文字 AI 包了。</p>
      <div class="step-bar">
        <div v-for="(s, i) in stepLabels" :key="i" class="step-item" :class="{ active: stepIndex === i, done: stepIndex > i }">
          <div class="step-dot">{{ stepIndex > i ? '✓' : i + 1 }}</div>
          <span class="step-label">{{ s }}</span>
        </div>
      </div>
    </div>

    <!-- ① 填写表单 -->
    <div v-if="stage === 'form' && !progress.isRunning.value" class="fade-in">
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div>
              <div class="text-sm font-semibold text-ink">产品信息</div>
              <div class="text-xs text-ink-4">填写产品名和创作模板，AI 开始调研</div>
            </div>
          </div>
        </div>
        <div style="padding: 22px;">
          <div class="form-section">
            <label class="form-label">产品 / 工具名 <span class="req">*</span></label>
            <input class="input" v-model="form.product" type="text" placeholder="请输入产品名称">
          </div>
          <div class="form-section">
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <label class="form-label" style="margin-bottom:0;">商单 brief <span class="opt">选填</span></label>
              <el-button text size="small" type="primary" @click="briefDialog = true">
                <el-icon style="margin-right:4px;"><MagicStick /></el-icon> 导入飞书 / 文件 brief
              </el-button>
            </div>

            <!-- 未解析：直接编辑文本 -->
            <textarea v-if="!structuredBrief" class="input textarea" v-model="form.brief" style="margin-top:8px;"
              placeholder="粘贴商单要求：必提卖点、禁忌、调性、官网链接等；或点右上角从飞书链接/文件自动导入"></textarea>

            <!-- 已解析：结构化卡片 + 折叠的原文 -->
            <template v-else>
              <BriefStructuredCard :brief="structuredBrief">
                <template #actions>
                  <el-button text size="small" @click="clearBrief">清除</el-button>
                </template>
              </BriefStructuredCard>
              <div class="raw-toggle">
                <el-button text size="small" @click="showRawBrief = !showRawBrief">
                  {{ showRawBrief ? '收起' : '查看 / 编辑' }}写作要求原文（喂给 AI 研究）
                </el-button>
              </div>
              <textarea v-show="showRawBrief" class="input textarea" v-model="form.brief" rows="15" style="margin-top:6px; min-height:340px;"></textarea>
            </template>
          </div>
          <!-- 创作模板切换已隐藏，默认走「工具主线」（form.template = 'tool'） -->
        </div>
      </div>
      <button class="cta-bar" style="margin-top: 20px;" :disabled="!form.product.trim()" @click="startResearch">
        开始研究 <CreditHint :cost="3" />
      </button>
    </div>

    <!-- 进度（研究 / 成稿 共用） -->
    <div v-if="progress.isRunning.value" class="fade-in" style="margin-top: 8px;">
      <AgentStatusBar v-for="(step, idx) in progress.steps.value" :key="idx"
        :agent-name="step.agent" :action="step.action" :avatar="step.avatar"
        :is-active="idx === progress.currentStepIndex.value"
        :show-progress="idx === progress.currentStepIndex.value"
        :percent="idx === progress.currentStepIndex.value ? progress.stepPercent.value : (idx < progress.currentStepIndex.value ? 100 : 0)"
        style="margin-bottom: 8px;" />
    </div>

    <div v-if="progress.error.value" class="card" style="padding: 16px; border: 1px solid var(--crimson);">
      <p class="text-sm" style="color: var(--crimson);">{{ progress.error.value }}</p>
    </div>

    <!-- ② 研究确认 + 选功能点（一屏） -->
    <div v-if="stage === 'review' && research && !progress.isRunning.value" class="fade-in">
      <div v-if="research.insufficient" class="info-banner">⚠️ <span>部分信息联网搜索不足，已尽量填写，可手动补充</span></div>

      <!-- 产品定位 -->
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">🎯</div>
            <span class="text-sm font-semibold text-ink">产品定位</span>
          </div>
        </div>
        <div style="padding: 22px;">
          <textarea class="input textarea" v-model="research.positioning" rows="2"></textarea>
        </div>
      </div>

      <!-- 产品优势 -->
      <div class="card" v-if="research.advantages && research.advantages.length">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: #EEF3EE; color: var(--leaf);">🏆</div>
            <span class="text-sm font-semibold text-ink">产品优势</span>
            <span class="text-xs text-ink-4" style="margin-left: auto;">共 {{ research.advantages.length }} 条</span>
          </div>
        </div>
        <div style="padding: 22px;">
          <div class="adv-list">
            <div class="adv-item" v-for="(a, i) in research.advantages" :key="i">
              <span class="adv-num">{{ i + 1 }}</span><span class="adv-text">{{ a }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 参考资料 -->
      <div class="card" v-if="research.references && research.references.length">
        <details class="ref-details">
          <summary class="panel-head" style="margin-bottom: 0;">
            <div class="ph-left">
              <div class="panel-icon" style="background: var(--sand-soft); color: var(--sand);">📄</div>
              <span class="text-sm font-semibold text-ink">参考资料</span>
              <span class="ref-count">{{ research.references.length }} 篇</span>
            </div>
          </summary>
          <div style="padding: 22px;">
            <div class="ref-article-list">
              <div class="ref-article-row" v-for="(r, i) in research.references" :key="i">
                <span v-if="r.source" class="ref-src-badge" :class="{ 'is-wechat': r.source === '公众号' }">{{ r.source }}</span>
                <span class="ref-article-title">{{ r.title || r.url }}</span>
                <a :href="r.url" target="_blank" class="btn-ref-visit">点击访问</a>
              </div>
            </div>
          </div>
        </details>
      </div>

      <!-- 选择实操段 -->
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">✅</div>
            <div>
              <div class="text-sm font-semibold text-ink">选择实操段</div>
              <div class="text-xs text-ink-4">打勾的功能点会写进文章（需你自己实操 + 截图）</div>
            </div>
          </div>
          <span class="select-count">已选 {{ selected.length }} / {{ selectableFeatures.length }}</span>
        </div>
        <div style="padding: 22px;">
          <div class="feature-list">
            <div v-for="(f, i) in selectableFeatures" :key="i" class="feature-card" :class="{ selected: selected.includes(f.name) }" @click="toggleSelect(f.name)">
              <div class="feature-top">
                <div class="feature-check"><span class="check-empty"></span></div>
                <div class="feature-info">
                  <div class="feature-name">{{ f.name }}</div>
                  <div class="feature-desc" v-if="f.desc">{{ f.desc }}</div>
                </div>
                <span :class="f.recommend ? 'tag-recommend' : 'tag-skip'">{{ f.recommend ? '推荐' : '可选' }}</span>
              </div>
              <div class="feature-reason" v-if="f.reason">💡 {{ f.reason }}</div>
              <template v-if="f.steps && f.steps.length">
                <div class="feature-steps-toggle" @click.stop="toggleSteps(i)">{{ openSteps.has(i) ? '▼' : '▶' }} 查看 {{ f.steps.length }} 步操作</div>
                <ol class="feature-steps" v-show="openSteps.has(i)">
                  <li v-for="(s, j) in f.steps" :key="j">{{ s }}</li>
                </ol>
              </template>
            </div>
            <button class="add-feature-btn" @click="addFeature">+ 手动添加功能点</button>
          </div>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn-ghost" @click="stage = 'form'">← 重新研究</button>
        <button class="btn-clay" :disabled="!selected.length" @click="startDraft">生成实操脚本 <CreditHint :cost="10" /></button>
      </div>
    </div>

    <!-- ③ 成稿 -->
    <div v-if="stage === 'result' && draft && !progress.isRunning.value" class="fade-in">
      <div class="success-banner">
        <span style="font-size: 20px;">✅</span>
        <div>
          <div class="text-sm font-semibold">生成完成</div>
          <div class="text-xs text-ink-4">{{ draft.word_count }} 字 · 截图位请按段落自行补上</div>
        </div>
      </div>
      <div class="card result-card">
        <div class="result-header">
          <h2 class="serif text-ink" style="font-size: 22px; font-weight: 600; flex: 1; min-width: 0;">{{ draft.title }}</h2>
          <div class="result-actions">
            <button class="btn-ghost btn-sm" @click="copy(draft.text)">📋 复制全文</button>
            <button class="btn-clay btn-sm" @click="toEditor">🚀 公众号编辑器</button>
          </div>
        </div>
        <div class="article" v-html="renderedDraft"></div>
      </div>
      <div class="action-bar" style="justify-content: flex-end; gap: 10px;">
        <button class="btn-ghost" @click="stage = 'review'">← 修改功能点</button>
        <button class="btn-ghost" @click="reset">↺ 再写一篇</button>
      </div>
    </div>

    <!-- brief 导入弹窗 -->
    <el-dialog v-model="briefDialog" title="导入商单 brief" width="520px" destroy-on-close>
      <el-radio-group v-model="briefSource" style="margin-bottom: 14px;">
        <el-radio-button label="feishu_link">飞书链接</el-radio-button>
        <el-radio-button label="file">上传文件</el-radio-button>
      </el-radio-group>

      <div v-if="briefSource === 'feishu_link'">
        <el-input v-model="briefLink" placeholder="粘贴飞书文档/wiki 链接（需先在「设置」连接飞书）" />
        <p class="brief-dlg-tip">用你绑定的飞书身份读取，仅你本人能访问的文档可读。</p>
      </div>
      <div v-else>
        <el-upload drag :auto-upload="false" :show-file-list="true" :limit="1"
          accept=".docx,.pdf,.txt,.md" :on-change="onPickFile">
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽或<em>点击上传</em> docx / pdf / txt</div>
        </el-upload>
      </div>

      <template #footer>
        <el-button @click="briefDialog = false">取消</el-button>
        <el-button type="primary" :loading="briefLoading" @click="importBrief">读取并解析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick, UploadFilled } from '@element-plus/icons-vue'
import { feishuBriefRead, feishuBriefUpload, feishuBriefSummarize } from '@/api/feishu'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import BriefStructuredCard from '@/components/creation/BriefStructuredCard.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import { publishToWechatEditor } from '@/utils/publishToEditor'
import api from '@/api/api'
import { marked } from 'marked'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'

const router = useRouter()
const creditStore = useCreditStore()
const progress = useAgentProgress()

const stepLabels = ['产品信息', '研究确认', '选择功能点', '生成成稿']
const templates = [
  { key: 'tool', icon: '🔧', label: '工具主线', hint: '开头引入 + 实操指导 + 结尾升华，主线是工具' },
  { key: 'case', icon: '📖', label: '案例主线', hint: '核心是案例，工具只是其中一小部分' },
]

const stage = ref('form')          // form | review | result
const form = ref({ product: '', brief: '', template: 'tool' })

// brief 导入
const briefDialog = ref(false)
const briefSource = ref('feishu_link')
const briefLink = ref('')
const briefFile = ref(null)
const briefLoading = ref(false)
const structuredBrief = ref(null)
const showRawBrief = ref(false)

const clearBrief = () => { structuredBrief.value = null; form.value.brief = ''; showRawBrief.value = false }
const research = ref(null)
const selected = ref([])
const draft = ref(null)
const openSteps = ref(new Set())

const stepIndex = computed(() => ({ form: 0, review: 2, result: 3 }[stage.value]))
const templateHint = computed(() => templates.find(t => t.key === form.value.template)?.hint || '')
const selectableFeatures = computed(() => (research.value?.features || []).filter(f => f.name?.trim()))
const renderedDraft = computed(() => marked.parse(draft.value?.text || ''))

const toggleSelect = (name) => {
  const i = selected.value.indexOf(name)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(name)
}
const toggleSteps = (i) => {
  const s = openSteps.value
  s.has(i) ? s.delete(i) : s.add(i)
  openSteps.value = new Set(s)
}
const addFeature = () => {
  const name = (window.prompt('功能点名称') || '').trim()
  if (!name) return
  research.value.features.push({ name, desc: '', steps: [], recommend: true, reason: '手动添加' })
  selected.value.push(name)
}

const unwrap = (res) => (res && res.data !== undefined ? res.data : res)

const onPickFile = (f) => { briefFile.value = f?.raw || null }

// 把结构化 brief 拼成可读文本，喂进 research 的 brief
const composeBriefText = (sb) => {
  const parts = []
  if (sb.brief) parts.push(sb.brief)
  if (sb.core_message) parts.push(`【核心主张】${sb.core_message}`)
  if (sb.must_cover?.length) parts.push('【必须覆盖】\n' + sb.must_cover.map(x => '· ' + x).join('\n'))
  if (sb.banned?.length) parts.push('【禁忌/红线】\n' + sb.banned.map(x => '· ' + x).join('\n'))
  if (sb.tone) parts.push(`【调性】${sb.tone}`)
  if (sb.cta) parts.push(`【引导动作】${sb.cta}`)
  if (sb.audience) parts.push(`【目标读者】${sb.audience}`)
  if (sb.publish) parts.push(`【发布档期】${sb.publish}`)
  if (sb.notes) parts.push(`【其他】${sb.notes}`)
  return parts.join('\n\n')
}

const importBrief = async () => {
  briefLoading.value = true
  try {
    // 1) 取原文
    let title = '', rawText = ''
    if (briefSource.value === 'feishu_link') {
      if (!briefLink.value.trim()) { ElMessage.warning('请粘贴飞书链接'); return }
      const d = unwrap(await feishuBriefRead('feishu_link', briefLink.value.trim()))
      title = d.title || ''; rawText = d.raw_text || ''
    } else {
      if (!briefFile.value) { ElMessage.warning('请先选择文件'); return }
      const d = unwrap(await feishuBriefUpload(briefFile.value))
      title = d.title || ''; rawText = d.raw_text || ''
    }
    if (!rawText.trim()) { ElMessage.warning('未读到内容'); return }

    // 2) 结构化总结
    const sb = unwrap(await feishuBriefSummarize(rawText, title))
    structuredBrief.value = sb
    if (!form.value.product.trim() && sb.product) form.value.product = sb.product
    form.value.brief = composeBriefText(sb)
    briefDialog.value = false
    ElMessage.success('brief 已导入并解析')
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message || '导入失败'
    ElMessage.error(typeof msg === 'string' ? msg : '导入失败')
  } finally {
    briefLoading.value = false
  }
}

const startResearch = async () => {
  if (!form.value.product.trim()) return
  progress.stop(); draft.value = null
  try {
    const res = await api.post('/practical/research', {
      product: form.value.product.trim(),
      brief: form.value.brief.trim(),
    }, { timeout: 10000 })
    const runId = (res?.data || res)?.run_id
    if (runId) progress.start(`/api/v1/practical/stream/${runId}`)
    else progress.error.value = '未获取到任务 ID'
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

const startDraft = async () => {
  if (!selected.value.length) return
  progress.stop()
  try {
    const res = await api.post('/practical/draft', {
      research: research.value,
      selected: selected.value,
      template: form.value.template,
      brief_banned: structuredBrief.value?.banned || [],
      brief_tone: structuredBrief.value?.tone || null,
    }, { timeout: 10000 })
    const runId = (res?.data || res)?.run_id
    if (runId) progress.start(`/api/v1/practical/stream/${runId}`)
    else progress.error.value = '未获取到任务 ID'
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

watch(() => progress.result.value, (data) => {
  if (!data) return
  if (Array.isArray(data.features)) {          // 研究结果
    research.value = data
    selected.value = (data.features || []).filter(f => f.recommend && f.name).map(f => f.name)
    openSteps.value = new Set()
    stage.value = 'review'
    creditStore.fetchBalance()
  } else if (typeof data.text === 'string') {  // 成稿结果
    draft.value = data
    stage.value = 'result'
    creditStore.fetchBalance()
  }
})

const copy = (text) => {
  navigator.clipboard?.writeText(text).then(() => ElMessage.success('已复制全文')).catch(() => ElMessage.error('复制失败'))
}
const toEditor = async () => {
  await publishToWechatEditor(router, draft.value?.text || '', draft.value?.title || '')
}
const reset = () => {
  progress.stop()
  stage.value = 'form'
  form.value = { product: '', brief: '', template: 'tool' }
  research.value = null; selected.value = []; draft.value = null
  structuredBrief.value = null
}

onUnmounted(() => progress.stop())
</script>

<style scoped>
.page-wrap { max-width: 860px; margin: 0 auto; padding: 8px 0 64px; }
.brief-dlg-tip { font-size: 12px; color: var(--ink-4, #999); margin-top: 8px; }
.raw-toggle { margin-top: 8px; }
.serif { font-family: "Source Han Serif SC", "Songti SC", "Noto Serif SC", Georgia, serif; font-weight: 500; }

.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }
.tool-hero h1 { font-size: 38px; line-height: 1.15; letter-spacing: -.01em; color: var(--ink); }
.tool-hero .desc { margin-top: 12px; font-size: 15px; color: var(--ink-3); line-height: 1.6; max-width: 620px; }

.step-bar { display: flex; align-items: center; margin-top: 24px; padding: 16px 24px; background: linear-gradient(135deg, rgba(204,120,92,.04), rgba(63,92,82,.04)); border: 1px solid rgba(204,120,92,.12); border-radius: 14px; }
.step-item { display: flex; align-items: center; gap: 10px; flex: 1; position: relative; }
.step-item:last-child { flex: 0 0 auto; }
.step-item:not(:last-child)::after { content: ''; flex: 1; height: 1px; background: linear-gradient(90deg, var(--clay-soft), rgba(204,120,92,.08)); margin: 0 14px; }
.step-item.done:not(:last-child)::after { background: linear-gradient(90deg, var(--clay), var(--clay-soft)); }
.step-dot { width: 30px; height: 30px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; background: var(--bone); color: var(--ink-4); border: 1.5px solid var(--line); flex-shrink: 0; transition: all .3s; }
.step-label { font-size: 13px; font-weight: 500; color: var(--ink-4); white-space: nowrap; transition: color .3s; }
.step-item.done .step-dot { background: var(--clay); color: #fff; border-color: var(--clay); box-shadow: 0 2px 8px rgba(204,120,92,.2); }
.step-item.done .step-label { color: var(--clay-deep); font-weight: 600; }
.step-item.active .step-dot { background: #fff; color: var(--clay-deep); border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,.12), 0 2px 8px rgba(204,120,92,.15); }
.step-item.active .step-label { color: var(--ink); font-weight: 600; }

.card { background: var(--paper); border-radius: var(--r-lg); box-shadow: var(--sh-1); overflow: hidden; margin-bottom: 16px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.ph-left { display: flex; align-items: center; gap: 11px; flex: 1; }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 17px; }

.text-sm { font-size: 13px; } .text-xs { font-size: 12px; } .font-semibold { font-weight: 600; }
.text-ink { color: var(--ink); } .text-ink-3 { color: var(--ink-3); } .text-ink-4 { color: var(--ink-4); } .text-clay { color: var(--clay); }

.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.template-hint { margin-top: 10px; font-size: 13px; color: var(--ink-4); line-height: 1.5; }

.form-section { margin-bottom: 22px; }
.form-section:last-of-type { margin-bottom: 0; }
.form-label { display: block; font-size: 13px; font-weight: 600; color: var(--ink-2); margin-bottom: 8px; }
.req { color: var(--crimson); } .opt { font-weight: 400; color: var(--ink-4); }
.input { width: 100%; padding: 10px 14px; border: 1.5px solid var(--line); border-radius: var(--r-md); background: var(--paper); font-family: inherit; font-size: 14px; color: var(--ink); outline: none; transition: border-color .18s, box-shadow .18s; }
.input:hover { border-color: var(--clay-soft); }
.input:focus { border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,.12); }
.textarea { resize: vertical; min-height: 72px; line-height: 1.6; }

.info-banner { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-radius: var(--r-md); background: var(--sand-soft); color: var(--sand); font-size: 13px; font-weight: 500; margin-bottom: 16px; }

.ref-details summary { list-style: none; cursor: pointer; }
.ref-details summary::-webkit-details-marker { display: none; }
.ref-count { margin-left: auto; font-size: 11px; font-weight: 600; color: var(--clay-deep); background: var(--clay-tint); padding: 2px 8px; border-radius: var(--r-pill); }
.ref-article-list { display: flex; flex-direction: column; }
.ref-article-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--line); }
.ref-article-row:last-child { border-bottom: none; }
.ref-src-badge { flex-shrink: 0; margin-right: 8px; font-size: 11px; font-weight: 500; color: var(--ink-4); background: var(--line); padding: 2px 7px; border-radius: 5px; white-space: nowrap; }
.ref-src-badge.is-wechat { color: #07803a; background: rgba(7, 193, 96, 0.12); }
.ref-article-title { font-size: 13px; color: var(--ink-2); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-ref-visit { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 500; color: var(--clay-deep); text-decoration: none; white-space: nowrap; margin-left: 12px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line); transition: all .15s; }
.btn-ref-visit:hover { background: var(--clay-tint); border-color: var(--clay); color: var(--clay); }

.select-count { font-size: 12px; font-weight: 600; color: var(--clay-deep); background: var(--clay-tint); padding: 4px 10px; border-radius: var(--r-pill); white-space: nowrap; }

.adv-list { display: flex; flex-direction: column; gap: 10px; }
.adv-item { display: flex; align-items: flex-start; gap: 10px; }
.adv-num { flex-shrink: 0; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-size: 12px; font-weight: 600; background: var(--clay-tint); color: var(--clay-deep); border: 1px solid rgba(204,120,92,.18); }
.adv-text { font-size: 14px; color: var(--ink); line-height: 22px; padding-top: 1px; }

.feature-list { display: flex; flex-direction: column; gap: 10px; }
.feature-card { border: 1.5px solid var(--line); border-radius: var(--r-md); padding: 14px 16px; cursor: pointer; transition: all .18s; background: var(--paper); }
.feature-card:hover { border-color: var(--clay-soft); background: var(--ivory); }
.feature-card.selected { border-color: var(--clay); background: var(--clay-tint); }
.feature-top { display: flex; align-items: flex-start; gap: 10px; }
.feature-check { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
.check-empty { width: 18px; height: 18px; border-radius: 4px; border: 1.5px solid var(--line); display: block; }
.feature-card.selected .check-empty { border-color: var(--clay); background: var(--clay); position: relative; }
.feature-card.selected .check-empty::after { content: '✓'; color: #fff; font-size: 11px; font-weight: 700; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }
.feature-info { flex: 1; min-width: 0; }
.feature-name { font-size: 14px; font-weight: 600; color: var(--ink); line-height: 1.4; }
.feature-desc { font-size: 12px; color: var(--ink-3); margin-top: 2px; line-height: 1.5; }
.feature-reason { font-size: 12px; color: var(--ink-4); margin-top: 8px; padding-left: 32px; line-height: 1.5; }
.feature-steps-toggle { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--clay-deep); margin-top: 8px; padding-left: 32px; cursor: pointer; }
.feature-steps-toggle:hover { color: var(--clay); }
.feature-steps { margin: 8px 0 0 32px; padding-left: 16px; }
.feature-steps li { font-size: 12px; color: var(--ink-3); line-height: 1.7; margin-bottom: 2px; }
.tag-recommend { font-size: 11px; padding: 2px 8px; border-radius: var(--r-pill); background: #EEF3EE; color: var(--leaf); white-space: nowrap; flex-shrink: 0; font-weight: 600; }
.tag-skip { font-size: 11px; padding: 2px 8px; border-radius: var(--r-pill); background: var(--bone); color: var(--ink-4); white-space: nowrap; flex-shrink: 0; }
.add-feature-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px; border: 1.5px dashed var(--line); border-radius: var(--r-md); background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; cursor: pointer; transition: all .15s; }
.add-feature-btn:hover { border-color: var(--clay-soft); color: var(--clay-deep); background: var(--ivory); }

.action-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 24px; }

.cta-bar { position: relative; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }

.btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: 1.5px solid var(--line); border-radius: var(--r-md); background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .18s; }
.btn-ghost:hover { border-color: var(--clay-soft); color: var(--clay-deep); background: var(--ivory); }
.btn-clay { display: inline-flex; align-items: center; gap: 6px; padding: 8px 20px; border: none; border-radius: var(--r-md); background: var(--clay); color: #fff; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .18s; }
.btn-clay:hover:not([disabled]) { background: var(--clay-deep); }
.btn-clay[disabled] { background: var(--bone); color: var(--ink-4); cursor: not-allowed; }
.btn-sm { padding: 6px 12px; font-size: 12px; }

.success-banner { display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-radius: var(--r-md); background: #EEF3EE; color: var(--leaf); margin-bottom: 18px; }
.result-card { padding: 0; }
.result-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; border-bottom: 1px solid var(--line); gap: 16px; }
.result-actions { display: flex; gap: 8px; flex-shrink: 0; }
.article { font-size: 15px; line-height: 1.85; color: var(--ink); background: var(--ivory); padding: 24px 28px; max-height: 520px; overflow: auto; }
.article :deep(h1), .article :deep(h2), .article :deep(h3) { font-family: "Source Han Serif SC", serif; color: var(--ink); margin: 18px 0 10px; line-height: 1.3; font-weight: 600; }
.article :deep(h2) { font-size: 19px; } .article :deep(h3) { font-size: 16px; }
.article :deep(p) { margin: 10px 0; }
.article :deep(ul), .article :deep(ol) { margin: 10px 0; padding-left: 24px; }
.article :deep(li) { margin: 4px 0; }
.article :deep(strong) { color: var(--clay-deep); }

.fade-in { animation: fadeIn .32s cubic-bezier(.32,.72,0,1); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
