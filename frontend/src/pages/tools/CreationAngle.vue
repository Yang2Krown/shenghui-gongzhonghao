<template>
  <!-- Hero：外面单独放，用同宽容器包住保持对齐 -->
  <div :style="{ maxWidth: showPanel ? '1320px' : '860px', margin: '0 auto', transition: 'max-width 0.32s cubic-bezier(.32,.72,0,1)' }">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><EditPen /></el-icon>
        创作工具 · 创作角度
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        找到那个<span class="text-clay">没人写过</span>的角度
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        投喂任意信息源 —— 文字、PDF 或链接，可以一次给多个。AI 会替你拆出几个陌生化、有张力的切入口。
      </p>
    </div>
  </div>

  <!-- Flex 行：表单 + 右侧面板 -->
  <div class="creation-layout" :class="{ 'has-panel': showPanel }">
  <div ref="mainRef" style="max-width: 860px; margin: 0 auto; flex: 1; min-width: 0;">
    <!-- 信息源+偏好+按钮 整体，用于面板高度对齐 -->
    <div ref="formRef">

    <!-- 信息源面板 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div class="flex items-center" style="gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">信息源</div>
            <div class="text-xs text-ink-4">支持文字 / PDF / 链接，可添加多个</div>
          </div>
        </div>
        <span class="badge badge-clay" style="font-size: 12px; padding: 4px 11px;">
          已填 {{ filledCount }} / {{ sources.length }}
        </span>
      </div>
      <div style="padding: 22px;">
        <div v-for="(source, index) in sources" :key="index" class="src-card slide-up">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 13px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="src-number">{{ index + 1 }}</span>
              <div class="seg">
                <button v-for="kind in sourceKinds" :key="kind.key"
                  @click="source.kind = kind.key"
                  :class="['seg-btn', { 'seg-btn-active': source.kind === kind.key }]">
                  {{ kind.label }}
                </button>
              </div>
            </div>
            <button v-if="sources.length > 1" @click="removeSource(index)" class="btn-text text-ink-4" style="padding: 4px;">
              <el-icon :size="15"><Delete /></el-icon>
            </button>
          </div>

          <el-input v-if="source.kind === 'text'" v-model="source.text" type="textarea" :rows="4"
            placeholder="粘贴或输入文字内容，如新闻、笔记、观点、数据……" />

          <div v-else-if="source.kind === 'link'">
            <!-- 链接加载中 -->
            <div v-if="source.linkExtracting" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取链接内容…</span>
            </div>
            <!-- 链接已提取 -->
            <div v-else-if="source.linkTitle" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Link /></el-icon> {{ source.linkTitle }}
                  <span v-if="source.linkPlatform" class="text-xs text-ink-4" style="padding: 2px 8px; background: var(--line); border-radius: 12px;">{{ source.linkPlatform }}</span>
                </span>
                <button @click="removeLink(source)" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="source.linkContent" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ source.linkContent.slice(0, 200) }}…
              </div>
            </div>
            <!-- 链接输入框 -->
            <div v-else style="position: relative;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex: 1; position: relative;">
                  <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
                  <el-input v-model="source.url" placeholder="粘贴文章链接（公众号 / 小红书 / 知乎 / 抖音 等）"
                    style="padding-left: 38px;" />
                </div>
                <button @click="handleLinkExtract(source)" :disabled="!source.url || source.linkExtracting"
                  style="padding: 8px 16px; background: var(--clay); color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;"
                  :style="{ opacity: (!source.url || source.linkExtracting) ? 0.5 : 1 }">
                  确认
                </button>
              </div>
            </div>
          </div>

          <div v-else-if="source.kind === 'file'">
            <div v-if="source.fileUploading" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取文件内容…</span>
            </div>
            <div v-else-if="source.fileName" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Document /></el-icon> {{ source.fileName }}
                  <span v-if="source.fileText" class="text-xs text-ink-4">· {{ source.fileText.length }} 字</span>
                </span>
                <button @click="removeFile(source)" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="source.fileText" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ source.fileText.slice(0, 200) }}…
              </div>
            </div>
            <div v-else class="dropzone" :class="{ 'dropzone-active': source.dragOver }"
              @click="triggerFileInput(index)"
              @dragover.prevent="source.dragOver = true"
              @dragleave="source.dragOver = false"
              @drop="handleFileDrop(source, $event)">
              <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
              <div class="text-sm font-medium">点击或拖拽上传 PDF / Word / TXT / MD</div>
              <div class="text-xs text-ink-4" style="margin-top: 2px;">单文件不超过 20MB</div>
            </div>
            <input :ref="(el) => setFileInputRef(el, index)" type="file" accept=".pdf,.docx,.txt,.md" style="display:none"
              @change="(e) => handleFileUpload(source, e)" />
          </div>
        </div>
        <button @click="addSource" class="btn-ghost" style="border-style: dashed; margin-top: 8px;">
          <el-icon :size="16"><Plus /></el-icon> 添加信息源
        </button>
      </div>
    </div>

    <!-- 创作偏好 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">创作偏好 <span class="text-xs text-ink-4" style="font-weight: 400;">选填</span></div>
            <div class="text-xs text-ink-4">补充风格、语气、受众或任何额外要求</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px;">
          <button v-for="chip in styleChips" :key="chip" @click="toggleStyleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：写给一线从业者，语气克制但有锋芒，多用具体案例，避免空泛的大词……" />
      </div>
    </div>

    <!-- 生成按钮 -->
    <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate">
      <template v-if="progress.isRunning.value">
        <el-icon class="spin"><Loading /></el-icon> 正在挖掘角度…
      </template>
      <template v-else>{{ ctaLabel }}</template>
    </button>

    </div><!-- /formRef -->

    <p v-if="!canGenerate" class="text-xs text-ink-4" style="text-align: center; margin-top: 10px;">
      至少填写一个信息源即可开始
    </p>

    <!-- 错误提示 -->
    <div v-if="progress.error.value" class="card" style="margin-top: 16px; padding: 16px; border-color: var(--crimson);">
      <p class="text-sm" style="color: var(--crimson);">{{ progress.error.value }}</p>
    </div>
  </div>

  <!-- 右栏：滑入面板 -->
  <div v-if="showPanel" ref="panelRef" class="creation-panel" :style="{ height: panelHeight }">
    <div class="panel-inner">
      <div class="panel-header">
        <h3 class="font-serif text-ink" style="font-size: 17px; font-weight: 600;">{{ panelTitle }}</h3>
        <button class="panel-close" @click="closePanel">&times;</button>
      </div>
      <div class="panel-body">
        <!-- 挖掘中 -->
        <div v-if="panelMode === 'mining'" class="mining-progress">
          <div class="mining-avatar">
            <img :src="miningCurrentStep?.avatar || '/agents/agent-a.png'" :alt="miningCurrentStep?.agent" />
          </div>
          <div class="mining-agent-name">{{ miningCurrentStep?.agent || '沈知远 · 选题衍生员' }}</div>
          <div class="mining-action">{{ miningCurrentStep?.action || '正在分析信息源，衍生候选角度…' }}</div>
          <div class="mining-bar">
            <div class="mining-bar-fill" :class="{ 'no-step-transition': progress.noStepTransition.value }" :style="{ width: miningPercent + '%' }"></div>
          </div>
          <div class="mining-bar-meta">
            <span>第 {{ miningStepNo }} / {{ Math.max(progress.steps.value.length, 2) }} 步</span>
            <span>{{ miningPercent }}%</span>
          </div>
          <p class="mining-title">正在挖掘角度，请稍候…</p>
        </div>

        <!-- 角度轮播 -->
        <div v-else-if="currentCandidate" class="carousel fade-in">
          <div class="carousel-top">
            <span class="carousel-counter">推荐角度 · 第 {{ currentCandidateIndex + 1 }} / {{ totalCandidates }} 个</span>
            <button class="btn-reshuffle" @click="reshuffleCandidates" :disabled="totalCandidates <= 1">
              <span class="reshuffle-icon">↻</span> 换一批
            </button>
          </div>
          <transition name="angle-swap" mode="out-in">
            <div class="angle-hero" :key="currentCandidate.title">
              <div class="angle-hero-head">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span class="angle-index">{{ String(currentCandidateIndex + 1).padStart(2, '0') }}</span>
                  <span v-if="currentCandidate.routine || currentCandidate.direction" class="angle-direction">
                    {{ currentCandidate.routine || currentCandidate.direction }}
                  </span>
                </div>
                <span class="angle-verdict" :class="currentCandidate.verdict === 'selected' ? 'verdict-selected' : 'verdict-backup'">
                  {{ currentCandidate.verdict === 'selected' ? '推荐' : currentCandidate.verdict === 'backup' ? '备选' : currentCandidate.verdict }}
                </span>
              </div>
              <div class="angle-scroll">
                <h3 class="angle-title font-serif">{{ currentCandidate.title }}</h3>
                <p v-if="currentCandidate.summary || currentCandidate.value_promise" class="angle-summary">
                  {{ currentCandidate.summary || currentCandidate.value_promise }}
                </p>
                <div v-if="currentCandidate.angle_note" class="angle-info">
                  <div class="info-block">
                    <span class="info-label">角度说明</span>
                    <p class="info-text">{{ currentCandidate.angle_note }}</p>
                  </div>
                </div>

                <!-- 评分维度 -->
                <div v-if="currentCandidate.score" class="score-section">
                  <span class="info-label">评分维度</span>
                  <div class="score-grid">
                    <div v-for="dim in scoreDimensions" :key="dim.key"
                      v-show="currentCandidate.score[dim.key] != null" class="score-cell">
                      <span class="score-dim-label">{{ dim.label }}</span>
                      <span class="score-dim-value" :style="{ color: getScoreColor(currentCandidate.score[dim.key]) }">
                        {{ currentCandidate.score[dim.key] != null ? currentCandidate.score[dim.key].toFixed(1) : '—' }}
                      </span>
                    </div>
                  </div>
                  <!-- 评分依据 -->
                  <div v-if="getEvidenceData(currentCandidate.score.evidence).items.length" class="evidence-list">
                    <div v-for="item in getEvidenceData(currentCandidate.score.evidence).items" :key="item.label" class="evidence-item">
                      <span class="evidence-dim">{{ item.label }}</span>
                      <span class="evidence-text">{{ item.text }}</span>
                    </div>
                  </div>
                  <p v-else-if="getEvidenceData(currentCandidate.score.evidence).text" class="score-evidence">
                    {{ getEvidenceData(currentCandidate.score.evidence).text }}
                  </p>
                </div>
              </div>
              <div class="angle-hero-foot">
                <button class="btn-copy" @click="copyAngle(currentCandidate)">
                  <span class="copy-icon">⧉</span> 复制
                </button>
                <button class="btn-write-outline" @click="goToOutline(currentCandidate)">
                  用此角度写大纲 <span style="font-size: 12px;">→</span>
                </button>
              </div>
            </div>
          </transition>
          <div class="carousel-nav">
            <button class="nav-arrow" @click="prevCandidate" :disabled="totalCandidates <= 1" aria-label="上一个">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>
            </button>
            <div class="nav-dots">
              <button v-for="(c, i) in candidateList" :key="i" class="nav-dot"
                :class="{ active: i === currentCandidateIndex }" @click="currentCandidateIndex = i"
                :aria-label="`第 ${i + 1} 个`"></button>
            </div>
            <button class="nav-arrow" @click="nextCandidate" :disabled="totalCandidates <= 1" aria-label="下一个">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
          </div>
        </div>

        <div v-else class="empty-state"><p style="color: #6B6862;">暂无角度数据</p></div>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  EditPen, Document, Delete, Plus, Upload, Link,
  Edit, Loading, Refresh, ArrowRight, CopyDocument, Check
} from '@element-plus/icons-vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api, { uploadFile, extractLinkContent } from '@/api/api'

const router = useRouter()
const progress = useAgentProgress()

const sourceKinds = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]

const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const sources = ref([{
  kind: 'file',
  text: '',
  url: '',
  fileName: '',
  fileText: '',
  fileUploading: false,
  dragOver: false,
  linkExtracting: false,
  linkTitle: '',
  linkContent: '',
  linkPlatform: '',
  linkAuthor: '',
}])
const fileInputs = reactive({})
const preference = ref('')

// ── 面板状态 ──
const showPanel = ref(false)
const mainRef = ref(null)
const formRef = ref(null)
const panelRef = ref(null)
const panelHeight = ref('auto')
const layoutHeight = ref('auto')
const panelMode = ref('mining')
const candidateList = ref([])
const currentCandidateIndex = ref(0)
let resizeObserver = null

const totalCandidates = computed(() => candidateList.value.length)
const currentCandidate = computed(() => candidateList.value[currentCandidateIndex.value] || null)

const panelTitle = computed(() => {
  if (panelMode.value === 'mining') return '发掘角度中'
  return '推荐角度'
})

const miningStepNo = computed(() => {
  const idx = progress.currentStepIndex.value
  return Math.min(Math.max(idx + 1, 1), 2)
})
const miningPercent = computed(() => Math.round(progress.stepPercent.value))
const miningCurrentStep = computed(() => {
  const i = progress.currentStepIndex.value
  return i >= 0 ? progress.steps.value[i] : null
})

// 布局高度
const calcLayoutHeight = () => {
  if (mainRef.value) {
    const top = mainRef.value.getBoundingClientRect().top
    layoutHeight.value = (window.innerHeight - top - 24) + 'px'
  } else {
    layoutHeight.value = (window.innerHeight - 108) + 'px'
  }
}

const syncPanelHeight = () => {
  if (formRef.value) {
    panelHeight.value = formRef.value.offsetHeight + 'px'
  }
}

watch(showPanel, (val) => {
  if (val) {
    nextTick(() => {
      syncPanelHeight()
      requestAnimationFrame(() => {
        syncPanelHeight()
        if (formRef.value && !resizeObserver) {
          resizeObserver = new ResizeObserver(() => syncPanelHeight())
          resizeObserver.observe(formRef.value)
        }
      })
    })
  } else {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }
})

onMounted(() => {
  calcLayoutHeight()
  window.addEventListener('resize', calcLayoutHeight)
})

onUnmounted(() => {
  window.removeEventListener('resize', calcLayoutHeight)
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
  progress.stop()
})

const filledCount = computed(() =>
  sources.value.filter(s => s.text || s.url || s.fileText).length
)

const canGenerate = computed(() => filledCount.value > 0 && !progress.isRunning.value)

const ctaLabel = computed(() => {
  if (progress.isRunning.value) return null // 用 template slot
  if (candidateList.value.length > 0) return '重新生成角度'
  return '生成创作角度'
})

const addSource = () => {
  sources.value.push({
    kind: 'file',
    text: '',
    url: '',
    fileName: '',
    fileText: '',
    fileUploading: false,
    dragOver: false,
    linkExtracting: false,
    linkTitle: '',
    linkContent: '',
    linkPlatform: '',
    linkAuthor: '',
  })
}

const removeSource = (index) => {
  sources.value.splice(index, 1)
  delete fileInputs[index]
}

const setFileInputRef = (el, index) => {
  if (el) fileInputs[index] = el
}

const triggerFileInput = (index) => {
  const input = fileInputs[index]
  if (input) {
    input.value = ''
    input.click()
  }
}

const toggleStyleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value
      ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip
      : chip
  }
}

const handleFileUpload = async (source, event) => {
  const file = event.target.files?.[0]
  if (!file) return

  source.fileName = file.name
  source.fileUploading = true
  source.fileText = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    source.fileText = data.text || ''
    if (!source.fileText) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      source.fileName = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    source.fileName = ''
  } finally {
    source.fileUploading = false
  }
}

const removeFile = (source) => {
  source.fileName = ''
  source.fileText = ''
}

const removeLink = (source) => {
  source.url = ''
  source.linkTitle = ''
  source.linkContent = ''
  source.linkPlatform = ''
  source.linkAuthor = ''
}

const handleLinkExtract = async (source) => {
  const url = (source.url || '').trim()
  if (!url) return

  source.linkExtracting = true
  try {
    const res = await extractLinkContent(url)
    const data = res.data || res
    source.linkTitle = data.title || '未知标题'
    source.linkContent = data.content || ''
    source.linkPlatform = data.platform || '网页'
    source.linkAuthor = data.author || ''
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '链接提取失败')
    source.linkTitle = ''
    source.linkContent = ''
    source.linkPlatform = ''
  } finally {
    source.linkExtracting = false
  }
}

const handleFileDrop = async (source, event) => {
  event.preventDefault()
  source.dragOver = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return

  source.fileName = file.name
  source.fileUploading = true
  source.fileText = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    source.fileText = data.text || ''
    if (!source.fileText) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      source.fileName = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    source.fileName = ''
  } finally {
    source.fileUploading = false
  }
}

// 监听 SSE 结果
watch(() => progress.result.value, (data) => {
  if (data?.angles) {
    candidateList.value = data.angles
    currentCandidateIndex.value = 0
    panelMode.value = 'candidates'
    nextTick(syncPanelHeight)
  }
})

const handleGenerate = async () => {
  progress.stop()
  candidateList.value = []
  currentCandidateIndex.value = 0

  // 打开面板
  panelMode.value = 'mining'
  showPanel.value = true

  // 构造信息源
  const apiSources = sources.value
    .filter(s => s.text || s.url || s.fileText)
    .map(s => {
      if (s.kind === 'text') return { type: 'text', content: s.text }
      if (s.kind === 'link') {
        // 优先使用前端已提取的内容，否则发送链接让后端提取
        if (s.linkTitle) {
          // 已提取成功，发送组合内容
          const parts = []
          if (s.linkTitle) parts.push(`标题：${s.linkTitle}`)
          if (s.linkAuthor) parts.push(`作者：${s.linkAuthor}`)
          if (s.linkContent) parts.push(s.linkContent)
          return { type: 'text', content: parts.join('\n') }
        }
        return { type: 'link', content: s.url }
      }
      if (s.kind === 'file') return { type: 'text', content: s.fileText || '' }
      return { type: 'text', content: '' }
    })

  try {
    // 1. 调用后端获取 run_id
    const res = await api.post('/topic-candidates/mine-adhoc', {
      sources: apiSources,
      preference: preference.value,
    }, { timeout: 10000 })

    const runId = res?.run_id || res?.data?.run_id
    if (!runId) {
      ElMessage.error('未能获取任务 ID')
      showPanel.value = false
      return
    }

    // 2. 连接 SSE 流
    progress.start(`/api/v1/topic-candidates/stream/${runId}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
    showPanel.value = false
  }
}

const closePanel = () => {
  showPanel.value = false
  progress.stop()
}

const goToOutline = (candidate) => {
  router.push({
    path: '/creation/new',
    query: {
      candidate_id: candidate.id,
      topic_title: candidate.title,
    }
  })
}

const copyAngle = (angle) => {
  const text = `${angle.title}\n${angle.summary || angle.value_promise || ''}`.trim()
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制')
}

// 评分维度
const scoreDimensions = [
  { key: 'pain_point', label: '痛点直击' },
  { key: 'value_density', label: '价值密度' },
  { key: 'propagation', label: '传播触发' },
  { key: 'differentiation', label: '差异化' },
  { key: 'freshness', label: '新鲜度' },
  { key: 'audience_fit', label: '受众适配' },
]

const getScoreColor = (score) => {
  if (!score) return 'var(--ink-3)'
  if (score >= 7) return 'var(--leaf)'
  if (score >= 5) return 'var(--sand)'
  return 'var(--crimson)'
}

const getEvidenceData = (evidence) => {
  let ev = evidence
  if (ev == null || ev === '') return { items: [], text: '' }
  if (typeof ev === 'string') {
    const t = ev.trim()
    if (t.startsWith('{')) {
      try { ev = JSON.parse(t) } catch { return { items: [], text: ev } }
    } else {
      return { items: [], text: ev }
    }
  }
  if (ev && typeof ev === 'object') {
    const labelMap = Object.fromEntries(scoreDimensions.map(d => [d.key, d.label]))
    const items = Object.entries(ev)
      .filter(([, v]) => v != null && v !== '')
      .map(([k, v]) => ({ label: labelMap[k] || k, text: String(v) }))
    return { items, text: '' }
  }
  return { items: [], text: String(ev) }
}

const prevCandidate = () => {
  if (totalCandidates.value === 0) return
  currentCandidateIndex.value =
    (currentCandidateIndex.value - 1 + totalCandidates.value) % totalCandidates.value
}
const nextCandidate = () => {
  if (totalCandidates.value === 0) return
  currentCandidateIndex.value = (currentCandidateIndex.value + 1) % totalCandidates.value
}
const reshuffleCandidates = () => {
  if (totalCandidates.value <= 1) return
  candidateList.value = [...candidateList.value].sort(() => Math.random() - 0.5)
  currentCandidateIndex.value = 0
}
</script>

<style scoped>
.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker {
  display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700;
  letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint);
  border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px;
}
.soft-panel { background: radial-gradient(120% 80% at 100% 0%, rgba(204,120,92,.06) 0%, transparent 55%), var(--paper); }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.src-card {
  position: relative; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper);
  padding: 16px 18px 16px 20px; overflow: hidden; transition: border-color .18s, box-shadow .18s;
  margin-bottom: 12px;
}
.src-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: linear-gradient(var(--clay-soft), var(--clay)); opacity: .55;
}
.src-card:focus-within { border-color: var(--clay-soft); box-shadow: var(--sh-2); }
.src-card:focus-within::before { opacity: 1; }
.src-number { width: 26px; height: 26px; border-radius: 8px; background: var(--clay); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; font-family: var(--serif); }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.cta-bar {
  width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px;
  background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s;
}
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.dropzone-active { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.type-chip { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--paper); color: #6B6862; border: 1px solid var(--line); cursor: pointer; transition: all 0.15s; }
.type-chip:hover { background: #F0EDE3; color: var(--ink); }
.type-chip-active { background: var(--clay); color: #fff; border-color: var(--clay); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
.slide-up { animation: slideUp .3s cubic-bezier(.32,.72,0,1) both; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.lift { transition: transform .2s cubic-bezier(.32,.72,0,1), box-shadow .2s, border-color .2s; }
.lift:hover { transform: translateY(-3px); box-shadow: var(--sh-3); border-color: var(--clay-soft); }

/* ── 双栏布局 ── */
.creation-layout {
  display: flex;
  gap: 20px;
  align-items: stretch;
  max-width: 860px;
  margin: 0 auto;
  height: 100%;
  transition: max-width 0.32s cubic-bezier(.32,.72,0,1);
}
.creation-layout.has-panel { max-width: 1320px; }
.creation-panel {
  width: 460px;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}
.panel-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: var(--sh-2);
  overflow: hidden;
}
.panel-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}
.panel-close {
  background: transparent; border: none; font-size: 22px; line-height: 1;
  padding: 2px 8px; cursor: pointer; color: var(--ink-4); transition: color 0.15s;
}
.panel-close:hover { color: var(--ink); }
.panel-body { flex: 1; overflow-y: auto; padding: 20px; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 0; }

/* 挖掘进度 */
.mining-progress { height: 100%; min-height: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; }
.mining-avatar {
  width: 96px; height: 96px; border-radius: 50%; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  background: var(--paper); border: 2px solid var(--clay-soft);
  box-shadow: 0 0 0 6px var(--clay-tint);
  animation: avatarPulse 1.8s ease-in-out infinite;
}
.mining-avatar img { width: 100%; height: 100%; object-fit: cover; transform: scale(1.12); }
@keyframes avatarPulse {
  0%, 100% { box-shadow: 0 0 0 6px var(--clay-tint); }
  50% { box-shadow: 0 0 0 11px rgba(204,120,92,0); }
}
.mining-agent-name { margin-top: 16px; font-size: 15px; font-weight: 600; color: var(--ink); font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif; }
.mining-action { margin-top: 6px; max-width: 320px; font-size: 13px; line-height: 1.6; color: var(--ink-3); text-align: center; }
.mining-bar { width: 100%; max-width: 320px; height: 6px; margin-top: 24px; border-radius: 999px; background: var(--line); overflow: hidden; }
.mining-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--clay-soft), var(--clay)); transition: width 1s ease; }
.mining-bar-fill.no-step-transition { transition: none; }
.mining-bar-meta { width: 100%; max-width: 320px; margin-top: 8px; display: flex; justify-content: space-between; font-size: 12px; color: var(--ink-4); }
.mining-title { margin-top: 18px; font-size: 13px; color: var(--ink-4); }

/* 轮播 */
.carousel { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.carousel-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.carousel-counter { font-size: 13px; font-weight: 600; color: var(--ink-3); font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif; }
.btn-reshuffle { display: inline-flex; align-items: center; gap: 5px; background: transparent; border: none; color: var(--clay-deep); font-size: 13px; font-weight: 600; cursor: pointer; transition: color 0.15s; }
.btn-reshuffle:hover:not(:disabled) { color: var(--clay); }
.btn-reshuffle:disabled { opacity: 0.4; cursor: not-allowed; }
.reshuffle-icon { font-size: 14px; }

/* 主卡片 */
.angle-hero { flex: 1; min-height: 0; display: flex; flex-direction: column; border: 1px solid var(--clay-soft); border-radius: 16px; background: var(--paper); box-shadow: var(--sh-1); padding: 22px; }
.angle-hero-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.angle-index { font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif; font-size: 28px; font-weight: 600; color: var(--clay); line-height: 1; }
.angle-direction { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 500; background: var(--clay-tint); color: var(--clay-deep); border: 1px solid var(--clay-soft); }
.angle-verdict { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.verdict-selected { background: rgba(92,138,92,.12); color: var(--leaf); }
.verdict-backup { background: var(--sand-soft); color: #8a6d33; }
.angle-scroll { flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px; margin-right: -4px; }
.angle-title { font-size: 22px; font-weight: 500; color: var(--ink); line-height: 1.4; margin-bottom: 10px; }
.angle-summary { font-size: 14px; line-height: 1.75; color: var(--ink-3); }
.angle-info { display: flex; flex-direction: column; gap: 14px; margin-top: 16px; }
.info-label { display: block; font-size: 11px; font-weight: 600; color: var(--ink-4); letter-spacing: 0.03em; margin-bottom: 5px; }
.info-text { font-size: 13px; line-height: 1.7; color: var(--ink-3); }
/* 评分维度 */
.score-section { margin-top: 18px; padding-top: 16px; border-top: 1px dashed var(--line); }
.score-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; }
.score-cell { display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 10px 6px; border: 1px solid var(--line); border-radius: 10px; background: var(--paper); }
.score-dim-label { font-size: 11px; color: var(--ink-4); font-weight: 500; }
.score-dim-value { font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif; font-size: 20px; font-weight: 600; line-height: 1; }
.score-evidence { margin-top: 12px; padding: 10px 12px; border-radius: 10px; background: var(--paper-2, #F6F1EB); font-size: 12px; line-height: 1.75; color: var(--ink-3); white-space: pre-line; }
.evidence-list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.evidence-item { display: flex; gap: 8px; font-size: 12px; line-height: 1.7; }
.evidence-dim { flex-shrink: 0; font-weight: 600; color: var(--ink-3); min-width: 56px; }
.evidence-text { color: var(--ink-4); }

.angle-hero-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); }
.btn-copy { display: inline-flex; align-items: center; gap: 5px; background: transparent; border: none; color: var(--ink-3); font-size: 13px; font-weight: 500; cursor: pointer; transition: color 0.15s; }
.btn-copy:hover { color: var(--ink); }
.copy-icon { font-size: 14px; }
.btn-write-outline { display: inline-flex; align-items: center; gap: 5px; padding: 8px 14px; background: var(--clay); color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; box-shadow: 0 6px 16px rgba(204,120,92,.20); transition: background 0.15s, transform 0.15s; font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif; }
.btn-write-outline:hover { background: var(--clay-deep); }
.btn-write-outline:active { transform: translateY(1px); }

/* 底部导航 */
.carousel-nav { display: flex; align-items: center; justify-content: center; gap: 18px; margin-top: 18px; }
.nav-arrow { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--line); background: var(--paper); color: var(--ink-3); cursor: pointer; transition: all 0.15s; }
.nav-arrow:hover:not(:disabled) { border-color: var(--clay-soft); color: var(--clay); background: var(--clay-tint); }
.nav-arrow:disabled { opacity: 0.35; cursor: not-allowed; }
.nav-dots { display: flex; align-items: center; gap: 8px; }
.nav-dot { width: 8px; height: 8px; border-radius: 999px; border: none; padding: 0; background: var(--clay-soft); cursor: pointer; transition: all 0.22s cubic-bezier(.32,.72,0,1); }
.nav-dot.active { width: 22px; background: var(--clay); }

/* 卡片切换动画 */
.angle-swap-enter-active, .angle-swap-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.angle-swap-enter-from { opacity: 0; transform: translateY(8px); }
.angle-swap-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
