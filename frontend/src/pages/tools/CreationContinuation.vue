<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><EditPen /></el-icon>
        创作工具 · 正文续写
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        文章写到一半，<span class="text-clay">结尾怎么收</span>
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        给定已写正文 —— 可以是文件、链接或文本，AI 会分析内容脉络，给出多个自然收尾的续写方案。
      </p>
    </div>

    <!-- 正文来源 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">正文来源</div>
            <div class="text-xs text-ink-4">支持文件 / 链接 / 文本</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div class="seg" style="margin-bottom: 16px;">
          <button v-for="m in inputModes" :key="m.key" @click="mode = m.key"
            :class="['seg-btn', { 'seg-btn-active': mode === m.key }]">
            {{ m.label }}
          </button>
        </div>
        <div class="tab-grid">
          <div v-show="mode === 'file'">
            <div v-if="fileUploading" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取文件内容…</span>
            </div>
            <div v-else-if="fileName" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Document /></el-icon> {{ fileName }}
                  <span v-if="fileText" class="text-xs text-ink-4">· {{ fileText.length }} 字</span>
                </span>
                <button @click="removeFile()" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="fileText" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ fileText.slice(0, 200) }}…
              </div>
            </div>
            <div v-else class="dropzone" :class="{ 'dropzone-active': dragOver }"
              @click="$refs.fileInput?.click()"
              @dragover.prevent="dragOver = true"
              @dragleave="dragOver = false"
              @drop="handleFileDrop">
              <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
              <div class="text-sm font-medium">点击或拖拽上传 PDF / Word / TXT / MD</div>
            </div>
            <input ref="fileInput" type="file" accept=".pdf,.docx,.txt,.md" style="display:none"
              @change="handleFileUpload" />
          </div>

          <div v-show="mode === 'link'">
            <div v-if="linkExtracting" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取链接内容…</span>
            </div>
            <div v-else-if="linkTitle" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Link /></el-icon> {{ linkTitle }}
                  <span v-if="linkPlatform" class="text-xs text-ink-4" style="padding: 2px 8px; background: var(--line); border-radius: 12px;">{{ linkPlatform }}</span>
                </span>
                <button @click="removeLink()" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="linkContent" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ linkContent.slice(0, 200) }}…
              </div>
            </div>
            <div v-else style="position: relative;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex: 1; position: relative;">
                  <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
                  <el-input v-model="linkUrl" placeholder="粘贴文章链接（公众号 / 小红书 / 知乎 / 抖音 等）"
                    style="padding-left: 38px;" />
                </div>
                <button @click="handleLinkExtract()" :disabled="!linkUrl || linkExtracting"
                  style="padding: 8px 16px; background: var(--clay); color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;"
                  :style="{ opacity: (!linkUrl || linkExtracting) ? 0.5 : 1 }">
                  确认
                </button>
              </div>
            </div>
          </div>

          <div v-show="mode === 'text'">
            <el-input v-model="contentText" type="textarea" :rows="8"
              placeholder="粘贴你已经写好的文章正文……&#10;&#10;AI 会分析你的内容脉络和逻辑走向，然后给出多个自然收尾的续写方案。" style="resize: none;" />
          </div>
        </div>
      </div>
    </div>

    <!-- 续写偏好 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">续写偏好 <span class="text-xs text-ink-4" style="font-weight: 400;">选填</span></div>
            <div class="text-xs text-ink-4">补充收尾风格、升华方向或任何额外要求</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px;">
          <button v-for="chip in styleChips" :key="chip" @click="toggleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：希望结尾呼应开头、升华到个人成长层面、给出行动号召……" />
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
      <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate" style="flex: 1;">
        <template v-if="progress.isRunning.value">
          <el-icon class="spin"><Loading /></el-icon> 正在构思续写方案…
        </template>
        <template v-else>生成续写 <CreditHint :cost="1" /></template>
      </button>
      <div class="multi-model-toggle">
        <label class="toggle-label">
          <input type="checkbox" v-model="multiModelMode" class="toggle-checkbox" />
          <span class="toggle-slider"></span>
        </label>
        <span class="text-sm text-ink-3">多模型对比</span>
      </div>
    </div>

    <!-- Agent 进度 -->
    <div v-if="progress.isRunning.value" style="margin-top: 24px;" class="fade-in">
      <AgentStatusBar
        v-for="(step, idx) in progress.steps.value"
        :key="idx"
        :agent-name="step.agent"
        :action="step.action"
        :avatar="step.avatar"
        :is-active="idx === progress.currentStepIndex.value"
        :show-progress="idx === progress.currentStepIndex.value"
        :percent="idx === progress.currentStepIndex.value ? progress.stepPercent.value : (idx < progress.currentStepIndex.value ? 100 : 0)"
        class="mb-2"
      />
    </div>

    <div v-if="progress.error.value" class="card" style="margin-top: 16px; padding: 16px; border-color: var(--crimson);">
      <p class="text-sm" style="color: var(--crimson);">{{ progress.error.value }}</p>
    </div>

    <!-- 结果 -->
    <div v-if="result && !progress.isRunning.value && !multiModelResult" class="fade-in" style="margin-top: 32px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">续写方案</h2>
          <span class="text-sm text-ink-4">{{ result.plans?.length || 0 }} 个方案供选择</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <!-- 内容脉络分析 -->
      <div v-if="result.analysis" class="card" style="padding: 18px 22px; margin-bottom: 20px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep); width: 28px; height: 28px; border-radius: 7px;">
            <el-icon :size="14"><DataAnalysis /></el-icon>
          </div>
          <span class="text-sm font-semibold text-ink">内容脉络分析</span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 16px;">
          <div v-if="result.analysis.main_theme">
            <span class="text-xs text-ink-4">核心主题</span>
            <p class="text-sm font-medium text-ink" style="margin-top: 2px;">{{ result.analysis.main_theme }}</p>
          </div>
          <div v-if="result.analysis.writing_style">
            <span class="text-xs text-ink-4">写作风格</span>
            <p class="text-sm font-medium text-ink" style="margin-top: 2px;">{{ result.analysis.writing_style }}</p>
          </div>
          <div v-if="result.analysis.logical_flow">
            <span class="text-xs text-ink-4">逻辑走向</span>
            <p class="text-sm font-medium text-ink" style="margin-top: 2px;">{{ result.analysis.logical_flow }}</p>
          </div>
          <div v-if="result.analysis.emotional_tone">
            <span class="text-xs text-ink-4">情感基调</span>
            <p class="text-sm font-medium text-ink" style="margin-top: 2px;">{{ result.analysis.emotional_tone }}</p>
          </div>
        </div>
      </div>

      <!-- 续写方案列表 -->
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <div v-for="(plan, index) in result.plans" :key="index"
          class="card lift slide-up" :style="{ animationDelay: `${index * 60}ms` }">
          <!-- 方案标题 -->
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 22px; border-bottom: 1px solid var(--line);">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--clay); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px;">
                {{ index + 1 }}
              </div>
              <div>
                <div class="text-sm font-semibold text-ink">{{ plan.approach }}</div>
                <div class="text-xs text-ink-4">{{ plan.description }}</div>
              </div>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="btn-text btn-sm" @click="copyText(plan.content)">
                <el-icon :size="15"><CopyDocument /></el-icon> 复制全文
              </button>
              <button class="btn-text btn-sm" style="color: var(--clay-deep);" @click="selectedPlanContent = plan.content; showPublishChoice = true">
                <el-icon :size="15"><Promotion /></el-icon> 发布
              </button>
            </div>
          </div>
          <!-- 方案内容 -->
          <div style="padding: 18px 22px;">
            <div class="continuation-preview" style="padding: 14px 18px; background: var(--bone); border-radius: var(--r-md); border-left: 3px solid var(--clay);">
              <p class="text-sm text-ink-3" style="margin-bottom: 8px; font-style: italic;">衔接过渡：</p>
              <p class="text-sm text-ink" style="line-height: 1.7;">{{ plan.transition }}</p>
            </div>
            <div style="margin-top: 14px; padding: 14px 18px; background: var(--bone); border-radius: var(--r-md);">
              <p class="text-sm text-ink-3" style="margin-bottom: 8px; font-style: italic;">续写正文：</p>
              <p class="text-sm text-ink" style="line-height: 1.8; white-space: pre-wrap;">{{ plan.content }}</p>
            </div>
            <div v-if="plan.key_points?.length" style="margin-top: 12px;">
              <p class="text-xs text-ink-4" style="margin-bottom: 6px;">要点提示：</p>
              <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                <span v-for="point in plan.key_points" :key="point" class="badge badge-warm">{{ point }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 多模型对比结果 -->
    <div v-if="multiModelResult && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">对比结果</h2>
          <span class="text-sm text-ink-4">选择你更喜欢的续写风格</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <!-- 方案对比 -->
      <div class="comparison-container">
        <div
          v-for="(modelData, provider, index) in multiModelResult.comparison?.models || {}"
          :key="provider"
          class="comparison-column"
        >
          <!-- 方案标题 -->
          <div class="plan-header">
            <div class="plan-badge">
              {{ index === 0 ? 'A' : 'B' }}
            </div>
            <span v-if="modelData.success" class="text-xs text-ink-4">
              {{ modelData.count }} 个方案
            </span>
            <span v-else class="text-xs" style="color: var(--crimson);">生成失败</span>
          </div>

          <!-- 内容脉络分析 -->
          <div v-if="modelData.success && modelData.analysis?.main_theme" style="padding: 14px 16px; border-bottom: 1px solid var(--line);">
            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
              <div v-if="modelData.analysis.main_theme">
                <span class="text-xs text-ink-4">核心主题</span>
                <p class="text-xs font-medium text-ink" style="margin-top: 1px;">{{ modelData.analysis.main_theme }}</p>
              </div>
              <div v-if="modelData.analysis.writing_style">
                <span class="text-xs text-ink-4">写作风格</span>
                <p class="text-xs font-medium text-ink" style="margin-top: 1px;">{{ modelData.analysis.writing_style }}</p>
              </div>
            </div>
          </div>

          <!-- 续写方案列表 -->
          <div v-if="modelData.success && modelData.plans?.length" class="plan-titles">
            <div
              v-for="(plan, i) in modelData.plans"
              :key="i"
              class="plan-title-card"
            >
              <div style="display: flex; align-items: flex-start; gap: 12px;">
                <span class="plan-rank" :class="i === 0 ? 'rank-first' : ''">
                  {{ i + 1 }}
                </span>
                <div style="flex: 1; min-width: 0;">
                  <p class="plan-title-text">{{ plan.approach }}</p>
                  <p v-if="plan.description" class="text-xs text-ink-4" style="margin-top: 4px;">{{ plan.description }}</p>
                  <div style="margin-top: 8px; padding: 10px 12px; background: var(--paper); border-radius: var(--r-sm); border-left: 3px solid var(--clay);">
                    <p class="text-xs text-ink-3" style="margin-bottom: 4px; font-style: italic;">衔接过渡：</p>
                    <p class="text-xs text-ink" style="line-height: 1.6;">{{ plan.transition }}</p>
                  </div>
                  <div style="margin-top: 8px; padding: 10px 12px; background: var(--paper); border-radius: var(--r-sm);">
                    <p class="text-xs text-ink-3" style="margin-bottom: 4px; font-style: italic;">续写正文：</p>
                    <p class="text-xs text-ink" style="line-height: 1.7; white-space: pre-wrap;">{{ plan.content }}</p>
                  </div>
                </div>
                <button class="btn-text btn-sm" @click="copyText(plan.content)" style="flex-shrink: 0; padding: 4px 8px;">
                  <el-icon :size="14"><CopyDocument /></el-icon>
                </button>
              </div>
            </div>
          </div>

          <div v-else-if="!modelData.success" class="plan-error">
            <p class="text-sm" style="color: var(--crimson);">{{ modelData.error }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 保存草稿 / 发布到公众号 弹窗 -->
  <PublishChoiceDialog
    v-model="showPublishChoice"
    :title="contentText.slice(0, 30) || '续写结果'"
    @save-draft="handleSaveDraft"
    @publish="handlePublishToEditor"
  />
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { EditPen, Document, Link, Upload, Edit, Loading, Refresh, CopyDocument, DataAnalysis, Promotion } from '@element-plus/icons-vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import { publishToWechatEditor } from '@/utils/publishToEditor'
import PublishChoiceDialog from '@/components/PublishChoiceDialog.vue'
import api, { uploadFile, extractLinkContent } from '@/api/api'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'

const creditStore = useCreditStore()

const router = useRouter()

const progress = useAgentProgress()

const inputModes = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]

const styleChips = ['呼应开头', '金句收尾', '行动号召', '反思升华', '故事延续', '悬念留白']

const mode = ref('text')
const contentText = ref('')
const fileName = ref('')
const fileText = ref('')
const fileUploading = ref(false)
const linkUrl = ref('')
const linkExtracting = ref(false)
const linkTitle = ref('')
const linkContent = ref('')
const linkPlatform = ref('')
const preference = ref('')
const result = ref(null)
const multiModelMode = ref(false)
const multiModelResult = ref(null)
const showPublishChoice = ref(false)
const selectedPlanContent = ref('')
const dragOver = ref(false)

const canGenerate = computed(() => {
  let hasContent = false
  if (mode.value === 'link') {
    hasContent = !!linkTitle.value
  } else if (mode.value === 'file') {
    hasContent = !!fileText.value
  } else {
    hasContent = contentText.value.trim().length > 50
  }
  return hasContent && !progress.isRunning.value
})

const handleFileUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  fileName.value = file.name
  fileUploading.value = true
  fileText.value = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    fileText.value = data.text || ''
    if (!fileText.value) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      fileName.value = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    fileName.value = ''
  } finally {
    fileUploading.value = false
  }
}

const removeFile = () => {
  fileName.value = ''
  fileText.value = ''
}

const handleLinkExtract = async () => {
  const url = (linkUrl.value || '').trim()
  if (!url) return

  linkExtracting.value = true
  try {
    const res = await extractLinkContent(url)
    const data = res.data || res
    linkTitle.value = data.title || '未知标题'
    linkContent.value = data.content || ''
    linkPlatform.value = data.platform || '网页'
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '链接提取失败')
    linkTitle.value = ''
    linkContent.value = ''
    linkPlatform.value = ''
  } finally {
    linkExtracting.value = false
  }
}

const removeLink = () => {
  linkUrl.value = ''
  linkTitle.value = ''
  linkContent.value = ''
  linkPlatform.value = ''
}

const handleFileDrop = async (event) => {
  event.preventDefault()
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return

  fileName.value = file.name
  fileUploading.value = true
  fileText.value = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    fileText.value = data.text || ''
    if (!fileText.value) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      fileName.value = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    fileName.value = ''
  } finally {
    fileUploading.value = false
  }
}

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip : chip
  }
}

const getContent = () => {
  if (mode.value === 'link' && linkTitle.value) {
    const parts = []
    if (linkTitle.value) parts.push(`标题：${linkTitle.value}`)
    if (linkContent.value) parts.push(linkContent.value)
    return parts.join('\n')
  } else if (mode.value === 'file') {
    return fileText.value
  } else {
    return contentText.value.trim()
  }
}

// 监听进度结果
watch(() => progress.result.value, (data) => {
  if (data?.plans) {
    result.value = data
    // 刷新积分余额
    creditStore.fetchBalance()
  }
  // 多模型对比结果
  if (data?.comparison) {
    multiModelResult.value = data
  }
})

const handleGenerate = async () => {
  const content = getContent()

  if (!content || content.length < 50) {
    ElMessage.warning('请输入至少 50 个字符的正文内容')
    return
  }

  result.value = null
  multiModelResult.value = null
  progress.stop()

  // 多模型对比模式
  if (multiModelMode.value) {
    try {
      progress.start('multi-model')
      const res = await api.post('/content-continuation/compare', {
        content,
        preference: preference.value,
        providers: ['deepseek', 'aigocode'],
      }, { timeout: 300000 })

      const data = res?.data || res
      const runId = data?.comparison?.run_id

      if (runId) {
        progress.start(`/api/v1/content-continuation/compare/stream/${runId}`)
      } else {
        progress.error.value = '未获取到任务 ID'
      }
    } catch (err) {
      progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
    }
    return
  }

  // 单模型模式
  try {
    const res = await api.post('/content-continuation/generate', {
      content,
      preference: preference.value,
    }, { timeout: 10000 })

    const data = res?.data || res
    const runId = data?.run_id

    if (runId) {
      progress.start(`/api/v1/content-continuation/stream/${runId}`)
    } else {
      progress.error.value = '未获取到任务 ID'
    }
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

const copyText = (text) => {
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制')
}

const handleSaveDraft = () => {
  ElMessage.success('草稿已保存')
}

const handlePublishToEditor = () => {
  // 原文 + 续写内容拼接
  const inputContent = contentText.value || fileText.value || linkContent.value || ''
  const continuation = selectedPlanContent.value || ''
  const fullText = inputContent
    ? `${inputContent}\n\n${continuation}`
    : continuation
  publishToWechatEditor(router, fullText, '')
}

onUnmounted(() => {
  progress.stop()
})
</script>

<style scoped>
.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }
.soft-panel { background: radial-gradient(120% 80% at 100% 0%, rgba(204,120,92,.06) 0%, transparent 55%), var(--paper); }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.cta-bar { position: relative; width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
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
.badge { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: var(--r-pill); font-size: 12px; font-weight: 500; }
.badge-info { background: rgba(66,133,244,.10); color: #4285f4; }
.badge-warm { background: var(--clay-tint); color: var(--clay-deep); }
.btn-text { display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px; border: none; background: transparent; color: var(--clay-deep); font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; border-radius: var(--r-sm); transition: all .14s; }
.btn-text:hover { background: var(--clay-tint); }
.btn-ghost { display: inline-flex; align-items: center; gap: 5px; padding: 7px 14px; border: 1px solid var(--line); background: var(--paper); color: var(--ink-2); font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; border-radius: var(--r-md); transition: all .14s; }
.btn-ghost:hover { border-color: var(--clay-soft); color: var(--clay-deep); }
.btn-sm { padding: 5px 10px; font-size: 12px; }
.btn-outline { display: inline-flex; align-items: center; gap: 5px; padding: 8px 18px; border: 1px solid var(--clay-soft); background: transparent; color: var(--clay-deep); font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: var(--r-md); transition: all .14s; }
.btn-outline:hover { background: var(--clay-tint); }
.btn-primary { display: inline-flex; align-items: center; gap: 5px; padding: 8px 18px; border: none; background: var(--clay); color: white; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: var(--r-md); transition: all .14s; }
.btn-primary:hover { background: var(--clay-deep); }

/* 多模型对比开关 */
.multi-model-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bone);
  border-radius: var(--r-pill);
  white-space: nowrap;
}

.toggle-label {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.toggle-checkbox {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--line);
  transition: .3s;
  border-radius: 20px;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

.toggle-checkbox:checked + .toggle-slider {
  background-color: var(--clay);
}

.toggle-checkbox:checked + .toggle-slider:before {
  transform: translateX(16px);
}

/* 方案对比样式 */
.comparison-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 768px) {
  .comparison-container {
    grid-template-columns: 1fr;
  }
}

.comparison-column {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  overflow: hidden;
}

.plan-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--bone);
  border-bottom: 1px solid var(--line);
}

.plan-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink);
  background: var(--bone);
  border: 1px solid var(--line);
}

.plan-titles {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-title-card {
  padding: 14px 16px;
  background: var(--bone);
  border-radius: var(--r-md);
  transition: all 0.2s;
}

.plan-title-card:hover {
  background: #E8E4D9;
}

.plan-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--paper);
  border: 1px solid var(--line);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3);
  flex-shrink: 0;
}

.plan-rank.rank-first {
  background: var(--clay);
  border-color: var(--clay);
  color: white;
}

.plan-title-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.5;
  margin: 0;
}

.plan-error {
  padding: 20px;
  text-align: center;
  background: rgba(184, 84, 80, 0.03);
}
</style>
