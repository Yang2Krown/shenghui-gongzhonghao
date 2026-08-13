<template>
  <div class="diagnosis-page">
    <header class="diagnosis-hero">
      <div>
        <span class="eyebrow">REUSE THE METHOD</span>
        <h1>初稿诊断</h1>
        <p>把一篇还没定稿的文章放进来，调用已经确认的方法论，先看问题，再决定怎么改。</p>
      </div>
      <div class="hero-note">
        <span class="hero-note-dot" />
        <div><strong>经验会被引用</strong><small>诊断结果会标注本次用了哪些经验，不会自动改写正文。</small></div>
      </div>
    </header>

    <div class="diagnosis-grid">
      <aside class="input-card">
        <div class="card-heading">
          <div><span class="eyebrow">01 · BRING A DRAFT</span><h2>放入初稿</h2></div>
          <el-tag size="small" effect="plain">支持文件 / 文字</el-tag>
        </div>

        <div class="mode-switch" role="tablist" aria-label="初稿输入方式">
          <button type="button" :class="{ active: inputMode === 'paste' }" @click="inputMode = 'paste'">粘贴文字</button>
          <button type="button" :class="{ active: inputMode === 'file' }" @click="inputMode = 'file'">上传文件</button>
        </div>

        <el-form label-position="top" @submit.prevent="submitDiagnosis">
          <el-form-item label="诊断名称（可选）">
            <el-input v-model="form.title" maxlength="200" placeholder="例如：八月选题会复盘初稿" />
          </el-form-item>

          <template v-if="inputMode === 'paste'">
            <el-form-item label="初稿正文" required>
              <el-input
                v-model="form.content"
                type="textarea"
                :autosize="{ minRows: 12, maxRows: 24 }"
                maxlength="150000"
                show-word-limit
                placeholder="粘贴完整初稿。保留标题、段落和小标题，诊断会更准确。"
              />
            </el-form-item>
          </template>
          <template v-else>
            <el-form-item label="初稿文件" required>
              <el-upload
                class="draft-upload"
                drag
                :auto-upload="false"
                :show-file-list="false"
                accept=".pdf,.docx,.txt,.md,.markdown"
                :on-change="handleFileChange"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="el-upload__text">把 PDF / Word / Markdown 拖到这里，或 <em>点击选择</em></div>
                <small>建议上传文字版文件，单文件不超过 20MB</small>
              </el-upload>
              <div v-if="selectedFile" class="selected-file"><el-icon><Document /></el-icon><span>{{ selectedFile.name }}</span><button type="button" @click="selectedFile = null">移除</button></div>
            </el-form-item>
          </template>

          <div class="context-heading"><span>给诊断一点上下文</span><small>商单 brief 选填</small></div>
          <div class="brief-panel">
            <template v-if="!structuredBrief">
              <div v-for="(source, index) in briefSources" :key="index" class="brief-source">
                <div class="brief-source-head">
                  <span class="brief-source-number">{{ index + 1 }}</span>
                  <div class="brief-tabs" role="tablist" aria-label="商单 brief 来源">
                    <button v-for="kind in briefSourceKinds" :key="kind.key" type="button"
                      :class="{ active: source.kind === kind.key }"
                      @click="setBriefSourceKind(source, kind.key, index)">
                      {{ kind.label }}
                    </button>
                  </div>
                  <button v-if="briefSources.length > 1" type="button" class="brief-remove" aria-label="移除 brief" @click="briefSources.splice(index, 1)">
                    <el-icon :size="14"><Delete /></el-icon>
                  </button>
                </div>

                <el-input v-if="source.kind === 'text'" v-model="source.text" type="textarea" :rows="5"
                  placeholder="粘贴商单要求：必提卖点、禁忌、调性、官网链接等" />

                <div v-else-if="source.kind === 'link'" class="brief-link-source">
                  <div class="brief-link-row">
                    <div class="brief-link-input">
                      <el-icon :size="15"><Link /></el-icon>
                      <input v-model="source.url" class="brief-link-native-input" type="url"
                        aria-label="飞书文档或 Wiki 链接" placeholder="粘贴飞书文档 / Wiki 链接"
                        @input="resetFeishuLinkState(source)" />
                    </div>
                    <button type="button" class="brief-open-button" :disabled="briefLoading || feishuExtLoading" @click="openFeishuBrief(source, index)">
                      <el-icon v-if="source.feishuState === 'parsing' || feishuExtLoading" class="is-loading" :size="13"><Loading /></el-icon>
                      {{ source.feishuState === 'waiting' ? '重新打开' : source.feishuState === 'parsing' ? '解析中…' : '打开并提取' }}
                    </button>
                  </div>
                  <div v-if="source.feishuState === 'waiting'" class="brief-link-guide">
                    已打开飞书 Brief：回到文档顶部，使用「飞书 Brief 导入」插件提取正文并发送到网站。
                    <span v-if="!feishuExtReady">未检测到插件，请安装或重新加载插件后刷新本页。</span>
                  </div>
                  <div v-else-if="source.feishuState === 'parsing'" class="brief-link-processing"><el-icon class="is-loading"><Loading /></el-icon> 正在回传并解析 brief…</div>
                  <div v-else-if="source.feishuState === 'error'" class="brief-link-error">{{ source.feishuError || '提取失败，请重新打开文档后重试。' }}</div>
                </div>

                <div v-else class="brief-file-source">
                  <div v-if="source.fileName" class="brief-selected-file">
                    <span><el-icon><Document /></el-icon>{{ source.fileName }}</span>
                    <button type="button" @click="source.fileName = ''; source.file = null">移除</button>
                  </div>
                  <label v-else class="brief-dropzone" :class="{ active: source.dragOver }"
                    :data-testid="`diagnosis-brief-upload-${index}`"
                    @dragover.prevent="source.dragOver = true" @dragleave="source.dragOver = false"
                    @drop.prevent="handleBriefDrop(source, $event)">
                    <el-icon :size="18"><Upload /></el-icon>
                    <span>点击或拖拽上传 PDF / Word / TXT / MD / 图片</span>
                    <input type="file" :accept="briefAccept" tabindex="-1" @change="handleBriefFile(source, $event)" />
                  </label>
                </div>
              </div>

              <div class="brief-actions">
                <button type="button" class="brief-add-button" @click="addBriefSource"><el-icon :size="14"><Plus /></el-icon> 添加 brief</button>
                <button type="button" class="brief-import-button" :disabled="briefLoading" @click="importBrief">
                  <el-icon v-if="briefLoading" class="is-loading" :size="13"><Loading /></el-icon>
                  {{ briefLoading ? '解析中…' : '读取并解析' }}
                </button>
              </div>
            </template>

            <template v-else>
              <BriefStructuredCard data-testid="diagnosis-brief-structured" :brief="structuredBrief">
                <template #actions><el-button text size="small" @click="clearBrief">清除</el-button></template>
              </BriefStructuredCard>
              <div class="brief-raw-toggle">
                <el-button text size="small" @click="showRawBrief = !showRawBrief">{{ showRawBrief ? '收起' : '查看 / 编辑' }} brief 原文</el-button>
              </div>
              <textarea v-show="showRawBrief" v-model="briefRawText" class="brief-raw-textarea" rows="8" maxlength="12000" />
            </template>
          </div>

          <el-button class="submit-button" type="primary" :loading="loading" native-type="submit">
            <el-icon v-if="!loading"><Lightning /></el-icon>
            {{ loading ? '正在匹配经验并诊断…' : '开始初稿诊断' }}
          </el-button>
        </el-form>
      </aside>

      <main class="result-column">
        <section v-if="loading" class="result-card loading-card">
          <div class="loading-orbit"><el-icon class="is-loading"><Loading /></el-icon></div>
          <h2>正在把初稿和经验对齐</h2>
          <p>先召回相关的已确认经验，再分析文章的问题和优先级。通常需要一点时间。</p>
        </section>

        <section v-else-if="diagnosis" class="result-card result-card-main">
          <div class="result-heading">
            <div><span class="eyebrow">02 · SEE THE DIAGNOSIS</span><h2>{{ diagnosis.title }}</h2><p>{{ diagnosis.content_char_count }} 字 · {{ sourceLabel(diagnosis.source_type) }} · {{ formatDate(diagnosis.created_at) }}</p></div>
            <el-button plain size="small" @click="resetResult">重新诊断</el-button>
          </div>

          <div class="assessment-strip">
            <div class="assessment-score" :class="scoreClass(diagnosis.analysis?.overall_score)"><strong>{{ diagnosis.analysis?.overall_score ?? '—' }}</strong><span>初稿状态</span></div>
            <div class="assessment-summary"><span>AI 总结</span><p>{{ diagnosis.analysis?.summary || '本次诊断没有生成总结。' }}</p></div>
          </div>

          <div v-if="diagnosis.analysis?.overall_assessment" class="assessment-detail">{{ diagnosis.analysis.overall_assessment }}</div>

          <div v-if="diagnosis.matched_experiences?.length" class="referenced-methods">
            <div class="section-title"><div><span class="eyebrow">METHODS IN USE</span><h3>本次调用的方法论</h3></div><span class="section-count">{{ diagnosis.matched_experiences.length }} 条</span></div>
            <div class="method-chip-list">
              <article v-for="method in diagnosis.matched_experiences" :key="method.id" class="method-chip">
                <div class="method-chip-top"><el-tag size="small" effect="plain">{{ method.category || '经验' }}</el-tag><span>{{ matchLabel(method.match_method) }}</span></div>
                <strong>{{ method.title }}</strong>
                <div class="method-preview prose" v-html="renderExperienceMarkdown(method.content)" />
              </article>
            </div>
          </div>
          <el-empty v-else class="no-methods" :image-size="52" description="本次没有匹配到已确认经验，以下为通用诊断" />

          <div v-if="diagnosis.analysis?.strengths?.length" class="diagnosis-section">
            <div class="section-title"><div><span class="eyebrow">WHAT ALREADY WORKS</span><h3>已有基础</h3></div></div>
            <div class="strength-list"><article v-for="item in diagnosis.analysis.strengths" :key="`${item.title}-${item.detail}`" class="strength-item"><el-icon><CircleCheck /></el-icon><div><strong>{{ item.title }}</strong><p>{{ item.detail }}</p><small v-if="item.evidence">依据：{{ item.evidence }}</small></div></article></div>
          </div>

          <div class="diagnosis-section">
            <div class="section-title"><div><span class="eyebrow">WHAT NEEDS WORK</span><h3>问题与改进建议</h3></div><span class="section-count">{{ diagnosis.analysis?.issues?.length || 0 }} 条</span></div>
            <div v-if="diagnosis.analysis?.issues?.length" class="issue-list">
              <article v-for="(item, index) in diagnosis.analysis.issues" :key="`${item.title}-${index}`" class="issue-item" :class="`severity-${item.severity}`">
                <div class="issue-head"><div><el-tag size="small" :type="severityType(item.severity)">{{ severityLabel(item.severity) }}</el-tag><strong>{{ item.title }}</strong></div><el-button v-if="!savedFindings.includes(index)" text type="primary" size="small" :loading="savingFinding === index" @click="saveFinding(index)">沉淀为待确认经验</el-button><el-tag v-else size="small" type="success" effect="plain">已进入待确认</el-tag></div>
                <p class="issue-problem">{{ item.problem }}</p>
                <div class="issue-fields"><div><span>正文依据</span><p>{{ item.evidence || '正文未提供明确依据' }}</p></div><div><span>建议动作</span><p>{{ item.recommendation }}</p></div></div>
                <div v-if="relatedMethods(item).length" class="issue-methods"><span>关联经验</span><el-tag v-for="method in relatedMethods(item)" :key="method.id" size="small" effect="plain">{{ method.title }}</el-tag></div>
              </article>
            </div>
            <el-empty v-else :image-size="48" description="暂未识别到需要优先处理的问题" />
          </div>

          <div v-if="diagnosis.analysis?.improvement_plan?.length" class="diagnosis-section plan-section">
            <div class="section-title"><div><span class="eyebrow">NEXT MOVES</span><h3>建议的修改顺序</h3></div></div>
            <div class="plan-list"><article v-for="item in diagnosis.analysis.improvement_plan" :key="`${item.priority}-${item.action}`" class="plan-item"><span class="plan-number">{{ item.priority }}</span><div><strong>{{ item.action }}</strong><p v-if="item.why">{{ item.why }}</p></div></article></div>
          </div>

          <div v-if="diagnosis.analysis?.questions?.length" class="questions-note"><el-icon><WarningFilled /></el-icon><div><strong>还需要确认</strong><p>{{ diagnosis.analysis.questions.join('；') }}</p></div></div>
        </section>

        <section v-else class="result-card empty-result">
          <div class="empty-mark">◎</div>
          <span class="eyebrow">THE METHOD COMES BACK</span>
          <h2>让经验真正参与下一篇文章</h2>
          <p>初稿诊断会把问题和已确认的方法论放在一起，告诉你这条建议为什么适用、应该先改哪里。</p>
          <div class="empty-flow"><span>放入初稿</span><el-icon><ArrowRight /></el-icon><span>匹配经验</span><el-icon><ArrowRight /></el-icon><span>得到行动计划</span></div>
        </section>
      </main>
    </div>

    <section v-if="history.length" class="history-section">
      <div class="section-title"><div><span class="eyebrow">RECENT DIAGNOSES</span><h2>最近的初稿诊断</h2></div><span class="section-count">保留诊断记录，方便回看</span></div>
      <div class="history-list">
        <button v-for="item in history" :key="item.id" type="button" class="history-item" :class="{ active: diagnosis?.id === item.id }" @click="openHistory(item.id)">
          <div><strong>{{ item.title }}</strong><span>{{ item.content_char_count }} 字 · {{ sourceLabel(item.source_type) }}</span></div><div class="history-meta"><el-tag size="small" :type="item.status === 'completed' ? 'success' : 'warning'">{{ item.status === 'completed' ? '已完成' : '处理中' }}</el-tag><small>{{ formatDate(item.created_at) }}</small></div>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, CircleCheck, Delete, Document, Lightning, Link, Loading, Plus, Upload, UploadFilled, WarningFilled } from '@element-plus/icons-vue'
import { feishuBriefSummarize, feishuBriefUpload } from '@/api/feishu'
import {
  createDraftDiagnosisExperience,
  createPastedDraftDiagnosis,
  createUploadedDraftDiagnosis,
  getDraftDiagnosis,
  listDraftDiagnoses,
} from '@/api/draftDiagnoses'
import BriefStructuredCard from '@/components/creation/BriefStructuredCard.vue'
import { renderExperienceMarkdown } from '@/utils/experienceMarkdown'
import { UPLOAD_POLICIES, validateUploadFile } from '@/utils/uploadPolicy'

const inputMode = ref('paste')
const loading = ref(false)
const savingFinding = ref(null)
const selectedFile = ref(null)
const diagnosis = ref(null)
const history = ref([])
const savedFindings = ref([])
const form = reactive({ title: '', content: '' })

const briefSourceKinds = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '飞书链接' },
  { key: 'text', label: '文本' },
]
const briefAccept = UPLOAD_POLICIES.brief.accept
const briefLoading = ref(false)
const feishuExtReady = ref(false)
const feishuExtLoading = ref(false)
const pendingFeishuUrl = ref('')
const pendingFeishuSourceIndex = ref(-1)
const structuredBrief = ref(null)
const briefRawText = ref('')
const showRawBrief = ref(false)

const createBriefSource = (kind = 'file') => ({
  kind,
  text: '',
  url: '',
  file: null,
  fileName: '',
  dragOver: false,
  feishuState: kind === 'link' ? 'idle' : '',
  feishuError: '',
})
const briefSources = ref([createBriefSource('link')])

const unwrap = (res) => (res && res.data !== undefined ? res.data : res)
const FEISHU_HOST_RE = /(^|\.)(feishu\.cn|feishu\.net|larkoffice\.com|larksuite\.com)$/i
const normalizeFeishuDocumentUrl = (value = '') => {
  try {
    const parsed = new URL(String(value).trim())
    if (!['http:', 'https:'].includes(parsed.protocol) || !FEISHU_HOST_RE.test(parsed.hostname)) return ''
    return `${parsed.origin}${parsed.pathname}`.replace(/\/+$/, '')
  } catch {
    return ''
  }
}

const composeBriefText = (brief = {}) => {
  const parts = []
  if (brief.brief) parts.push(brief.brief)
  if (brief.core_message) parts.push(`【核心主张】${brief.core_message}`)
  if (brief.must_cover?.length) parts.push('【必须覆盖】\n' + brief.must_cover.map((item) => `· ${item}`).join('\n'))
  if (brief.banned?.length) parts.push('【禁忌/红线】\n' + brief.banned.map((item) => `· ${item}`).join('\n'))
  if (brief.tone) parts.push(`【调性】${brief.tone}`)
  if (brief.cta) parts.push(`【引导动作】${brief.cta}`)
  if (brief.audience) parts.push(`【目标读者】${brief.audience}`)
  if (brief.publish) parts.push(`【发布档期】${brief.publish}`)
  if (brief.review_notes) parts.push(`【审核要求】${brief.review_notes}`)
  if (brief.notes) parts.push(`【其他】${brief.notes}`)
  return parts.join('\n\n')
}

const setStructuredBrief = (brief) => {
  structuredBrief.value = brief || null
  briefRawText.value = brief ? (brief.raw_text || composeBriefText(brief)) : ''
}

const clearBrief = () => {
  setStructuredBrief(null)
  briefSources.value = [createBriefSource('link')]
  briefLoading.value = false
  feishuExtLoading.value = false
  pendingFeishuUrl.value = ''
  pendingFeishuSourceIndex.value = -1
  showRawBrief.value = false
}

const setBriefSourceKind = (source, kind, index = -1) => {
  source.kind = kind
  source.feishuState = kind === 'link' ? 'idle' : ''
  source.feishuError = ''
  if (kind !== 'link' && pendingFeishuSourceIndex.value === index) {
    pendingFeishuUrl.value = ''
    pendingFeishuSourceIndex.value = -1
  }
}

const resetFeishuLinkState = (source) => {
  source.feishuState = 'idle'
  source.feishuError = ''
}

const addBriefSource = () => briefSources.value.push(createBriefSource())

const setBriefSourceFile = (source, file) => {
  if (!file) return
  const errorMessage = validateUploadFile(file, 'brief')
  if (errorMessage) {
    ElMessage.error(errorMessage)
    return
  }
  source.file = file
  source.fileName = file.name
}

const handleBriefFile = (source, event) => {
  setBriefSourceFile(source, event.target.files?.[0])
  event.target.value = ''
}

const handleBriefDrop = (source, event) => {
  source.dragOver = false
  setBriefSourceFile(source, event.dataTransfer?.files?.[0])
}

const openFeishuBrief = (source, index) => {
  const rawUrl = source.url?.trim() || ''
  const normalizedUrl = normalizeFeishuDocumentUrl(rawUrl)
  if (!normalizedUrl) {
    source.feishuState = 'error'
    source.feishuError = '请粘贴有效的飞书文档 / Wiki 链接。'
    ElMessage.warning(source.feishuError)
    return false
  }
  const opened = window.open(rawUrl, '_blank')
  if (!opened) {
    source.feishuState = 'error'
    source.feishuError = '浏览器拦截了新标签页，请允许本站打开飞书文档后重试。'
    ElMessage.error(source.feishuError)
    return false
  }
  source.feishuState = 'waiting'
  source.feishuError = ''
  pendingFeishuUrl.value = normalizedUrl
  pendingFeishuSourceIndex.value = index
  ElMessage.success('已打开飞书文档，请按提示用插件提取并发送')
  return true
}

const importBrief = async () => {
  const linkIndex = briefSources.value.findIndex((source) => source.kind === 'link')
  if (linkIndex >= 0) {
    const source = briefSources.value[linkIndex]
    if (source.feishuState === 'waiting' || source.feishuState === 'parsing') {
      ElMessage.info('请回到已打开的飞书 Brief，完成插件提取并点击“发送到网站”')
      return
    }
    openFeishuBrief(source, linkIndex)
    return
  }

  briefLoading.value = true
  try {
    const parts = []
    for (const source of briefSources.value) {
      if (source.kind === 'text' && source.text?.trim()) parts.push(source.text.trim())
      if (source.kind === 'file' && source.file) {
        const data = unwrap(await feishuBriefUpload(source.file))
        if (data.raw_text) parts.push(data.raw_text)
      }
    }
    const rawText = parts.join('\n\n---\n\n')
    if (!rawText.trim()) {
      ElMessage.warning('未读到 brief 内容')
      return
    }
    setStructuredBrief(unwrap(await feishuBriefSummarize(rawText, '')))
    ElMessage.success('brief 已导入并解析')
  } catch (error) {
    const message = error?.response?.data?.detail || error?.message || 'brief 导入失败'
    ElMessage.error(typeof message === 'string' ? message : 'brief 导入失败')
  } finally {
    briefLoading.value = false
  }
}

const postToFeishuExtension = (type, payload = {}) => {
  window.postMessage({ __gzhFeishuBrief: true, dir: 'to-ext', type, payload }, '*')
}

const onFeishuExtensionMessage = (event) => {
  if (event?.source !== window) return
  const message = event?.data
  if (!message || message.__gzhFeishuBrief !== true || message.dir !== 'to-page') return
  if (message.type === 'ready') {
    feishuExtReady.value = true
    return
  }
  if (message.type === 'error') {
    feishuExtLoading.value = false
    const source = briefSources.value[pendingFeishuSourceIndex.value]
    if (source) {
      source.feishuState = 'error'
      source.feishuError = message.error || '飞书插件读取失败'
    }
    ElMessage.error(message.error || '飞书插件读取失败')
    return
  }
  if (message.type !== 'extracted') return
  const payload = message.payload || {}
  if (!payload.rawText?.trim()) {
    feishuExtLoading.value = false
    ElMessage.warning('插件没有提取到正文')
    return
  }
  const extractedUrl = normalizeFeishuDocumentUrl(payload.sourceUrl || '')
  if (pendingFeishuUrl.value && extractedUrl !== pendingFeishuUrl.value) {
    const source = briefSources.value[pendingFeishuSourceIndex.value]
    if (source) {
      source.feishuState = 'error'
      source.feishuError = '提取到的文档与刚才打开的链接不一致，请回到对应 Brief 重试。'
    }
    feishuExtLoading.value = false
    ElMessage.error('提取到的文档与刚才打开的链接不一致，请回到对应 Brief 重试')
    return
  }
  const source = briefSources.value[pendingFeishuSourceIndex.value]
  if (source) source.feishuState = 'parsing'
  feishuExtLoading.value = true
  briefSources.value = [Object.assign(createBriefSource('text'), {
    text: payload.markdown || payload.rawText,
    url: payload.sourceUrl || '',
  })]
  void importBrief().finally(() => {
    feishuExtLoading.value = false
    pendingFeishuUrl.value = ''
    pendingFeishuSourceIndex.value = -1
  })
}

const resetResult = () => {
  diagnosis.value = null
  savedFindings.value = []
  if (inputMode.value === 'paste') form.content = ''
  selectedFile.value = null
}

const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile?.raw || null
}

const submitDiagnosis = async () => {
  if (inputMode.value === 'paste' && !form.content.trim()) {
    ElMessage.warning('请先粘贴初稿正文')
    return
  }
  if (inputMode.value === 'file' && !selectedFile.value) {
    ElMessage.warning('请先选择初稿文件')
    return
  }
  const hasUnparsedBrief = briefSources.value.some((source) => (
    source.kind === 'text' && source.text?.trim()
  ) || (
    source.kind === 'file' && source.file
  ) || (
    source.kind === 'link' && source.url?.trim()
  ))
  if (hasUnparsedBrief && !structuredBrief.value) {
    ElMessage.warning('请先点击“读取并解析”完成商单 brief 解析，或清空 brief')
    return
  }
  loading.value = true
  savedFindings.value = []
  try {
    const data = inputMode.value === 'file'
      ? await createUploadedDraftDiagnosis({ file: selectedFile.value, title: form.title, brief_context: briefContextForSubmit() })
      : await createPastedDraftDiagnosis({
        title: form.title.trim() || null,
        content: form.content,
        brief_context: briefContextForSubmit(),
      })
    diagnosis.value = data.diagnosis
    await loadHistory()
    ElMessage.success('初稿诊断完成')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '初稿诊断失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

const briefContextForSubmit = () => {
  if (!structuredBrief.value) return null
  return {
    ...structuredBrief.value,
    raw_text: briefRawText.value.trim() || composeBriefText(structuredBrief.value),
  }
}

const loadHistory = async () => {
  try {
    const data = await listDraftDiagnoses({ page: 1, page_size: 12 })
    history.value = data.items || []
  } catch {
    // 历史记录加载失败不影响提交诊断。
  }
}

const openHistory = async (id) => {
  if (diagnosis.value?.id === id) return
  try {
    const data = await getDraftDiagnosis(id)
    diagnosis.value = data.diagnosis
    setStructuredBrief(data.diagnosis.brief_context)
    savedFindings.value = []
  } catch {
    ElMessage.error('诊断记录加载失败')
  }
}

const saveFinding = async (index) => {
  if (!diagnosis.value) return
  savingFinding.value = index
  try {
    await createDraftDiagnosisExperience(diagnosis.value.id, { finding_index: index })
    savedFindings.value = [...savedFindings.value, index]
    ElMessage.success('已进入待确认经验，确认后才会正式参与后续诊断')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '沉淀失败，请稍后重试')
  } finally {
    savingFinding.value = null
  }
}

const relatedMethods = (item) => {
  const ids = item?.experience_ids || []
  return (diagnosis.value?.matched_experiences || []).filter((method) => ids.includes(method.id))
}

const sourceLabel = (value) => ({ file: '文件上传', pasted: '文字粘贴' }[value] || '初稿')
const matchLabel = (value) => ({ semantic: '语义匹配', 'semantic+keyword': '语义 + 关键词', keyword_fallback: '关键词匹配' }[value] || '已引用')
const severityLabel = (value) => ({ high: '优先处理', medium: '建议优化', low: '可选优化' }[value] || '建议优化')
const severityType = (value) => ({ high: 'danger', medium: 'warning', low: 'info' }[value] || 'warning')
const scoreClass = (value) => value == null ? 'score-empty' : value >= 80 ? 'score-good' : value >= 60 ? 'score-mid' : 'score-low'
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '刚刚'

onMounted(() => {
  loadHistory()
  window.addEventListener('message', onFeishuExtensionMessage)
  postToFeishuExtension('ping')
})

onUnmounted(() => {
  window.removeEventListener('message', onFeishuExtensionMessage)
})
</script>

<style scoped>
.diagnosis-page { max-width: 1440px; margin: 0 auto; color: var(--ink); }
.diagnosis-hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 32px; padding: 12px 0 30px; border-bottom: 1px solid var(--line); }
.eyebrow { display: block; color: var(--clay-deep); font: 700 10px/1.2 'Fraunces', ui-serif, Georgia, serif; letter-spacing: .16em; }
.diagnosis-hero h1 { margin: 10px 0 8px; font: 700 clamp(32px, 4vw, 50px)/1.05 'Noto Serif SC', 'Songti SC', serif; letter-spacing: -.04em; }
.diagnosis-hero p { max-width: 650px; margin: 0; color: var(--ink-3); font-size: 14px; line-height: 1.8; }
.hero-note { display: flex; gap: 10px; align-items: flex-start; max-width: 290px; padding: 13px 15px; border: 1px solid #e9ddcd; border-radius: var(--r-md); background: rgba(255, 252, 247, .75); }
.hero-note-dot { width: 9px; height: 9px; margin-top: 4px; border-radius: 50%; background: #6b9c69; box-shadow: 0 0 0 4px rgba(107, 156, 105, .14); flex-shrink: 0; }
.hero-note strong, .hero-note small { display: block; }
.hero-note strong { font-size: 13px; }
.hero-note small { margin-top: 4px; color: var(--ink-4); font-size: 11px; line-height: 1.5; }
.diagnosis-grid { display: grid; grid-template-columns: minmax(320px, 390px) minmax(0, 1fr); gap: 20px; align-items: start; margin-top: 22px; }
.input-card, .result-card, .history-section { border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); box-shadow: 0 10px 30px rgba(93, 67, 47, .05); }
.input-card { position: sticky; top: 80px; padding: 22px; }
.card-heading, .result-heading, .section-title, .issue-head, .history-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-heading h2, .result-heading h2, .section-title h2 { margin: 7px 0 0; font: 700 23px/1.2 'Noto Serif SC', 'Songti SC', serif; letter-spacing: -.02em; }
.mode-switch { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin: 22px 0 18px; padding: 4px; border-radius: var(--r-md); background: var(--ivory); }
.mode-switch button { padding: 9px 8px; border: 0; border-radius: 8px; background: transparent; color: var(--ink-3); cursor: pointer; font: inherit; font-size: 13px; transition: all .15s; }
.mode-switch button.active { background: var(--paper); color: var(--clay-deep); box-shadow: 0 3px 10px rgba(93, 67, 47, .08); font-weight: 600; }
.input-card :deep(.el-form-item) { margin-bottom: 14px; }
.input-card :deep(.el-form-item__label) { padding-bottom: 5px; color: var(--ink-2); font-size: 12px; }
.input-card :deep(.el-textarea__inner), .input-card :deep(.el-input__wrapper) { border-color: #e9dfd2; background: #fffdf9; box-shadow: none; }
.input-card :deep(.el-textarea__inner):focus, .input-card :deep(.el-input__wrapper.is-focus) { border-color: var(--clay); box-shadow: 0 0 0 1px var(--clay-soft); }
.draft-upload :deep(.el-upload-dragger) { width: 100%; min-height: 170px; padding: 26px 14px; border-color: #e9dfd2; background: #fffdf9; }
.draft-upload :deep(.el-upload-dragger:hover) { border-color: var(--clay); }
.upload-icon { margin-bottom: 9px; color: var(--clay); font-size: 30px; }
.draft-upload .el-upload__text { color: var(--ink-3); font-size: 12px; line-height: 1.7; }
.draft-upload .el-upload__text em { color: var(--clay-deep); font-style: normal; }
.draft-upload small { display: block; margin-top: 6px; color: var(--ink-4); font-size: 10px; }
.selected-file { display: flex; align-items: center; gap: 7px; margin-top: 8px; padding: 8px 10px; border-radius: 8px; background: var(--ivory); color: var(--ink-2); font-size: 12px; }
.selected-file span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.selected-file button { border: 0; background: transparent; color: var(--clay-deep); cursor: pointer; font-size: 11px; }
.context-heading { display: flex; align-items: center; justify-content: space-between; margin: 20px 0 11px; color: var(--ink-2); font-size: 12px; font-weight: 600; }
.context-heading small { color: var(--ink-4); font-size: 10px; font-weight: 400; }
.brief-panel { padding: 11px; border: 1px solid #e9dfd2; border-radius: 12px; background: #fffdf9; }
.brief-source + .brief-source { margin-top: 9px; }
.brief-source-head { display: flex; align-items: center; gap: 7px; margin-bottom: 9px; }
.brief-source-number { display: grid; place-items: center; width: 23px; height: 23px; border-radius: 7px; background: var(--clay); color: white; font-size: 12px; font-weight: 700; flex-shrink: 0; }
.brief-tabs { display: inline-flex; gap: 2px; padding: 3px; border-radius: 999px; background: #f0ebe2; }
.brief-tabs button { padding: 5px 9px; border: 0; border-radius: 999px; background: transparent; color: var(--ink-3); cursor: pointer; font: inherit; font-size: 11px; }
.brief-tabs button.active { background: var(--paper); color: var(--clay-deep); box-shadow: 0 2px 6px rgba(93, 67, 47, .08); font-weight: 600; }
.brief-remove { margin-left: auto; padding: 3px; border: 0; background: transparent; color: var(--ink-4); cursor: pointer; }
.brief-link-row { display: flex; align-items: stretch; gap: 7px; }
.brief-link-input { display: flex; align-items: center; gap: 7px; min-width: 0; flex: 1; padding: 0 10px; border: 1px solid #e3d9cb; border-radius: 10px; background: #fff; color: var(--ink-4); }
.brief-link-native-input { width: 100%; min-width: 0; height: 35px; border: 0; outline: 0; background: transparent; color: var(--ink-2); font: inherit; font-size: 11px; }
.brief-link-native-input::placeholder { color: var(--ink-4); }
.brief-open-button, .brief-import-button { display: inline-flex; align-items: center; justify-content: center; gap: 5px; border: 0; border-radius: 9px; background: var(--clay); color: #fff; cursor: pointer; font: inherit; font-size: 11px; font-weight: 600; white-space: nowrap; }
.brief-open-button { padding: 0 10px; }
.brief-open-button:disabled, .brief-import-button:disabled { cursor: wait; opacity: .65; }
.brief-link-guide, .brief-link-processing, .brief-link-error { margin-top: 7px; padding: 8px 9px; border-radius: 8px; font-size: 10px; line-height: 1.6; }
.brief-link-guide { background: #fff7e7; color: #8b6c35; }.brief-link-guide span { display: block; margin-top: 3px; color: var(--clay-deep); }
.brief-link-processing { display: flex; align-items: center; gap: 5px; background: #f7f3ed; color: var(--ink-3); }.brief-link-error { background: #fff1ed; color: #b4513f; }
.brief-file-source { min-height: 70px; }.brief-dropzone { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; min-height: 70px; padding: 8px; border: 1px dashed #d9cbb9; border-radius: 9px; color: var(--ink-3); cursor: pointer; font-size: 10px; text-align: center; }.brief-dropzone.active, .brief-dropzone:hover { border-color: var(--clay); background: #fff8ef; }.brief-dropzone input { display: none; }
.brief-selected-file { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 10px; border-radius: 8px; background: var(--ivory); color: var(--ink-2); font-size: 11px; }.brief-selected-file span { display: flex; align-items: center; gap: 6px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.brief-selected-file button { flex-shrink: 0; border: 0; background: transparent; color: var(--clay-deep); cursor: pointer; font-size: 10px; }
.brief-actions { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; }.brief-add-button { display: inline-flex; align-items: center; gap: 4px; padding: 7px 9px; border: 1px dashed #d9cbb9; border-radius: 8px; background: transparent; color: var(--ink-2); cursor: pointer; font: inherit; font-size: 11px; }.brief-add-button:hover { border-color: var(--clay); color: var(--clay-deep); }.brief-import-button { padding: 8px 12px; }
.brief-raw-toggle { margin-top: 4px; text-align: right; }.brief-raw-textarea { width: 100%; min-height: 135px; box-sizing: border-box; padding: 9px; border: 1px solid #e9dfd2; border-radius: 8px; outline: none; resize: vertical; background: #fffdf9; color: var(--ink-2); font: inherit; font-size: 11px; line-height: 1.6; }.brief-raw-textarea:focus { border-color: var(--clay); box-shadow: 0 0 0 1px var(--clay-soft); }
.submit-button { width: 100%; height: 42px; margin-top: 4px; border: 0; background: var(--clay-deep); font-weight: 600; letter-spacing: .02em; }
.submit-button:hover { background: #99533e; }
.result-column { min-width: 0; }
.result-card { min-height: 640px; padding: 28px; }
.result-heading { align-items: flex-start; padding-bottom: 20px; border-bottom: 1px solid var(--line); }
.result-heading h2 { margin-top: 8px; font-size: 26px; }
.result-heading p { margin: 7px 0 0; color: var(--ink-4); font-size: 11px; }
.assessment-strip { display: grid; grid-template-columns: 105px minmax(0, 1fr); gap: 18px; margin: 20px 0 10px; padding: 16px; border-radius: var(--r-md); background: #fbf5ed; }
.assessment-score { display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 74px; border-right: 1px solid #eadbc9; }
.assessment-score strong { font: 700 31px/1 'Fraunces', ui-serif, Georgia, serif; }
.assessment-score span, .assessment-summary > span { color: var(--ink-4); font-size: 10px; }
.score-good strong { color: #648d60; }.score-mid strong { color: #b67b44; }.score-low strong { color: #b25d4c; }.score-empty strong { color: var(--ink-4); }
.assessment-summary { align-self: center; }.assessment-summary p { margin: 6px 0 0; color: var(--ink); font-size: 14px; line-height: 1.75; }
.assessment-detail { padding: 0 2px 15px; color: var(--ink-2); font-size: 13px; line-height: 1.8; }
.section-title { align-items: flex-end; margin: 25px 0 13px; }.section-title h3 { margin: 6px 0 0; font: 700 18px/1.2 'Noto Serif SC', 'Songti SC', serif; }.section-count { color: var(--ink-4); font-size: 11px; }
.method-chip-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.method-chip { min-width: 0; padding: 13px 14px; border: 1px solid #e9ddcd; border-radius: var(--r-md); background: #fffaf3; }
.method-chip-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--ink-4); font-size: 10px; }.method-chip strong { display: block; margin: 10px 0 5px; font-size: 14px; }.method-preview { max-height: 76px; overflow: hidden; color: var(--ink-3); font-size: 11px; line-height: 1.65; }.method-preview :deep(p) { margin: 0; }.method-preview :deep(h1), .method-preview :deep(h2), .method-preview :deep(h3), .method-preview :deep(ul), .method-preview :deep(ol) { margin: 0 0 4px; font-size: 12px; }.no-methods { margin: 8px 0; padding: 8px; border: 1px dashed #eadbc9; border-radius: var(--r-md); }
.diagnosis-section { margin-top: 22px; padding-top: 3px; }.strength-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.strength-item { display: flex; gap: 9px; padding: 12px; border-radius: var(--r-md); background: #f6f8f0; }.strength-item > .el-icon { margin-top: 2px; color: #6f9c6b; }.strength-item strong { font-size: 13px; }.strength-item p, .strength-item small { display: block; margin: 5px 0 0; color: var(--ink-3); font-size: 11px; line-height: 1.6; }.strength-item small { color: var(--ink-4); }
.issue-list { display: flex; flex-direction: column; gap: 10px; }.issue-item { padding: 15px; border: 1px solid #eadfd3; border-left: 3px solid #d4b07b; border-radius: var(--r-md); background: #fffdf9; }.issue-item.severity-high { border-left-color: #bd6a57; }.issue-item.severity-low { border-left-color: #a7a29a; }.issue-head > div { display: flex; align-items: center; gap: 8px; min-width: 0; }.issue-head strong { font-size: 14px; }.issue-problem { margin: 10px 0; color: var(--ink); font-size: 13px; line-height: 1.7; }.issue-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.issue-fields > div { padding: 10px; border-radius: 8px; background: var(--ivory); }.issue-fields span, .issue-methods > span { color: var(--ink-4); font-size: 10px; }.issue-fields p { margin: 5px 0 0; color: var(--ink-2); font-size: 11px; line-height: 1.65; }.issue-methods { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 10px; }.issue-methods > span { margin-right: 2px; }
.plan-list { display: flex; flex-direction: column; gap: 8px; }.plan-item { display: flex; gap: 11px; align-items: flex-start; padding: 11px 12px; border-radius: var(--r-md); background: #f8f5ee; }.plan-number { display: flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--clay-tint); color: var(--clay-deep); font: 700 12px/1 'Fraunces', ui-serif, Georgia, serif; flex-shrink: 0; }.plan-item strong { font-size: 13px; }.plan-item p { margin: 4px 0 0; color: var(--ink-3); font-size: 11px; line-height: 1.6; }
.questions-note { display: flex; gap: 9px; margin-top: 22px; padding: 12px 14px; border-radius: var(--r-md); background: #fff7e7; color: #8b6c35; }.questions-note > .el-icon { margin-top: 2px; }.questions-note strong { font-size: 12px; }.questions-note p { margin: 5px 0 0; font-size: 11px; line-height: 1.6; }
.loading-card, .empty-result { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }.loading-orbit { display: grid; place-items: center; width: 58px; height: 58px; margin-bottom: 18px; border-radius: 50%; background: var(--clay-tint); color: var(--clay-deep); font-size: 23px; }.loading-card h2, .empty-result h2 { margin: 0; font: 700 25px/1.3 'Noto Serif SC', 'Songti SC', serif; }.loading-card p, .empty-result p { max-width: 430px; margin: 10px 0 0; color: var(--ink-3); font-size: 13px; line-height: 1.8; }.empty-mark { margin-bottom: 18px; color: var(--clay); font: 400 60px/1 'Fraunces', ui-serif, Georgia, serif; }.empty-result .eyebrow { margin-bottom: 9px; }.empty-flow { display: flex; align-items: center; gap: 11px; margin-top: 27px; color: var(--ink-3); font-size: 12px; }.empty-flow .el-icon { color: var(--clay); }
.history-section { margin-top: 20px; padding: 22px; }.history-section h2 { font-size: 21px; }.history-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }.history-item { display: flex; justify-content: space-between; gap: 10px; min-width: 0; padding: 13px; border: 1px solid #e9dfd2; border-radius: var(--r-md); background: #fffdf9; color: var(--ink); cursor: pointer; text-align: left; transition: all .15s; }.history-item:hover, .history-item.active { border-color: var(--clay-soft); background: #fff8ef; }.history-item strong, .history-item span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.history-item strong { max-width: 180px; font-size: 13px; }.history-item span, .history-meta small { margin-top: 6px; color: var(--ink-4); font-size: 10px; }.history-meta { flex-direction: column; align-items: flex-end; gap: 3px; }
@media (max-width: 1100px) { .diagnosis-grid { grid-template-columns: 330px minmax(0, 1fr); }.method-chip-list, .history-list { grid-template-columns: 1fr 1fr; } }
@media (max-width: 820px) { .diagnosis-hero { align-items: flex-start; flex-direction: column; }.hero-note { max-width: none; width: 100%; }.diagnosis-grid { display: block; }.input-card { position: static; margin-bottom: 16px; }.result-card { min-height: 520px; padding: 20px 16px; }.strength-list, .issue-fields, .method-chip-list, .history-list { grid-template-columns: 1fr; }.history-section { padding: 18px 14px; }.history-item strong { max-width: 220px; } }
@media (max-width: 500px) { .diagnosis-hero h1 { font-size: 34px; }.result-heading { align-items: flex-start; flex-direction: column; }.result-heading .el-button { width: 100%; }.assessment-strip { grid-template-columns: 82px minmax(0, 1fr); gap: 11px; }.issue-head { align-items: flex-start; flex-direction: column; }.issue-head .el-button { padding-left: 0; }.empty-flow { gap: 6px; font-size: 11px; } }
</style>
