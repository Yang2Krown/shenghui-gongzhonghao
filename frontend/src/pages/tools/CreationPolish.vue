<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><MagicStick /></el-icon>
        创作工具 · 文案润色
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        粗稿变精品，<span class="text-clay">一键润色</span>
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        粘贴你的初稿文案，AI 会注入金句、核查事实、去除 AI 味，输出一篇可直接发布的公众号文章。
      </p>
    </div>

    <!-- 原文输入 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">文案来源</div>
            <div class="text-xs text-ink-4">支持文件 / 链接 / 文本</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <el-input v-model="title" placeholder="文章标题（选填）" style="margin-bottom: 14px;" />
        <div class="seg" style="margin-bottom: 16px;">
          <button v-for="m in inputModes" :key="m.key" @click="mode = m.key"
            :class="['seg-btn', { 'seg-btn-active': mode === m.key }]">
            {{ m.label }}
          </button>
        </div>
        <div class="tab-grid">
          <div v-show="mode === 'file'">
            <FileUploadZone v-model="fileName" policy="reference" :uploading="fileUploading"
              :meta-text="fileText ? `· ${fileText.length} 字` : ''"
              :preview-text="fileText ? fileText.slice(0, 200) + '…' : ''"
              title="点击或拖拽上传 PDF / Word / TXT / MD"
              @select="onFileSelect" @remove="removeFile" />
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
            <el-input v-model="contentText" type="textarea" :rows="10"
              placeholder="粘贴你的初稿文案……&#10;&#10;AI 将为你的文案注入金句、核查事实、去除 AI 味，输出可直接发布的公众号文章。" style="resize: none;" />
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 10px;">
          <span class="text-xs" :class="getContentText().trim().length < 50 ? 'text-ink-4' : 'text-pine'">
            {{ getContentText().trim().length }} 字{{ getContentText().trim().length < 50 ? '（至少 50 字）' : ' ✓' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 润色偏好 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">润色偏好 <span class="text-xs text-ink-4" style="font-weight: 400;">选填</span></div>
            <div class="text-xs text-ink-4">选择快捷偏好或自定义润色方向</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px;">
          <button v-for="chip in prefChips" :key="chip" @click="toggleChip(chip)"
            :class="['type-chip', { 'type-chip-active': selectedChips.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="2"
          placeholder="补充其他润色要求，例如：保持口语化风格、增加数据引用、控制在 1500 字以内……" />
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
      <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate" style="flex: 1;">
        <template v-if="progress.isRunning.value">
          <el-icon class="spin"><Loading /></el-icon> 正在润色文案…
        </template>
        <template v-else>开始润色 <CreditHint :cost="creditCost" /></template>
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
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">润色结果</h2>
          <span class="text-sm text-ink-4">{{ result.final_word_count || 0 }} 字</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 重新润色
        </button>
      </div>

      <!-- 统计信息 -->
      <div class="card" style="padding: 14px 22px; margin-bottom: 16px;">
        <div style="display: flex; flex-wrap: wrap; gap: 16px;" class="text-sm">
          <div v-if="result.agent_b_sentence_count">
            <span class="text-ink-4">金句注入</span>
            <span class="font-medium text-ink" style="margin-left: 4px;">{{ result.agent_b_sentence_count }} 句</span>
          </div>
          <div v-if="result.agent_e_correction_count">
            <span class="text-ink-4">事实纠错</span>
            <span class="font-medium text-ink" style="margin-left: 4px;">{{ result.agent_e_correction_count }} 处</span>
          </div>
          <div v-if="result.agent_c_rewrite_count">
            <span class="text-ink-4">去 AI 味改写</span>
            <span class="font-medium text-ink" style="margin-left: 4px;">{{ result.agent_c_rewrite_count }} 处</span>
          </div>
          <div v-if="result.style_anchor">
            <span class="text-ink-4">风格锚点</span>
            <span class="font-medium text-ink" style="margin-left: 4px;">{{ result.style_anchor }}</span>
          </div>
        </div>
      </div>

      <!-- 左右分栏（对比模式下全宽，隐藏右侧 Agent 评价） -->
      <div :class="viewMode === 'diff' ? 'result-full' : 'result-split'">
        <!-- 左侧：润色后全文 -->
        <div class="result-left">
          <div class="card" style="padding: 18px 22px; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
              <h3 class="text-h4 font-sans text-ink">{{ viewMode === 'diff' ? '原文 / 润色对比' : '润色全文' }}</h3>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div class="view-toggle">
                  <button class="toggle-btn" :class="{ active: viewMode === 'diff' }" @click="viewMode = 'diff'">对比</button>
                  <button class="toggle-btn" :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
                  <button class="toggle-btn" :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
                </div>
                <button class="btn-text btn-sm" @click="copyFullText">
                  <el-icon :size="15"><CopyDocument /></el-icon> 复制全文
                </button>
              </div>
            </div>

            <template v-if="viewMode === 'diff'">
              <div class="diff-legend">
                <span class="diff-legend-item"><span class="diff-chip diff-chip-del"></span>原文删除 / 改写
                  <em v-if="diffStats">−{{ diffStats.removed }} 字</em>
                </span>
                <span class="diff-legend-item"><span class="diff-chip diff-chip-ins"></span>润色新增
                  <em v-if="diffStats">+{{ diffStats.added }} 字</em>
                </span>
              </div>
              <div class="diff-pane">
                <div class="diff-col">
                  <div class="diff-col-head">原文</div>
                  <div class="content-preview diff-view" v-html="diffOriginalHtml" />
                </div>
                <div class="diff-col">
                  <div class="diff-col-head">润色后</div>
                  <div class="content-preview diff-view" v-html="diffPolishedHtml" />
                </div>
              </div>
            </template>
            <el-input
              v-else-if="viewMode === 'edit'"
              v-model="editableText"
              type="textarea"
              :autosize="{ minRows: 16, maxRows: 60 }"
              resize="vertical"
            />
            <div v-else class="content-preview prose" v-html="renderedHtml" />
          </div>
        </div>

        <!-- 右侧：Agent 反馈面板（对比模式下隐藏） -->
        <div v-if="viewMode !== 'diff'" class="result-right">
          <AgentFeedbackPanel
            :agents="agentFeedback"
            subtitle="润色流水线：B 金句加持 → D 事实核查 → E 联网纠错 → C 去 AI 味"
          />
        </div>
      </div>

      <!-- 底部统计 -->
      <div class="card" style="padding: 14px 22px; margin-top: 16px;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <span class="text-sm text-ink-3">润色后共 {{ editableText.length }} 字</span>
          <div style="display: flex; gap: 8px;">
            <button class="btn-ghost btn-sm" @click="copyFullText">
              <el-icon :size="14"><CopyDocument /></el-icon> 复制全文
            </button>
            <button class="btn-primary btn-sm" @click="showPublishChoice = true">
              <el-icon :size="14"><Promotion /></el-icon> 发布到公众号
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 多模型对比结果 -->
    <div v-if="multiModelResult && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">对比结果</h2>
          <span class="text-sm text-ink-4">选择你更喜欢的润色效果</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <!-- 模型选择按钮 -->
      <div class="model-switch">
        <button
          v-for="(modelData, provider) in multiModelResult.comparison?.models || {}"
          :key="provider"
          class="model-tab"
          :class="{ active: selectedProvider === provider, failed: !modelData.success }"
          @click="selectedProvider = provider"
        >
          <span class="model-tab-name">{{ providerLabel(provider) }}</span>
          <span v-if="modelData.success" class="model-tab-meta">{{ modelData.final_word_count }} 字</span>
          <span v-else class="model-tab-meta failed">失败</span>
        </button>
      </div>

      <!-- 选中模型的结果 -->
      <div v-if="selectedModelData" class="card" style="padding: 18px 22px;">
        <template v-if="selectedModelData.success">
          <!-- 统计信息 -->
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 14px;">
            <div style="display: flex; flex-wrap: wrap; gap: 16px;" class="text-sm">
              <div v-if="selectedModelData.agent_b_sentence_count">
                <span class="text-ink-4">金句</span>
                <span class="font-medium text-ink" style="margin-left: 4px;">{{ selectedModelData.agent_b_sentence_count }} 句</span>
              </div>
              <div v-if="selectedModelData.agent_e_correction_count">
                <span class="text-ink-4">纠错</span>
                <span class="font-medium text-ink" style="margin-left: 4px;">{{ selectedModelData.agent_e_correction_count }} 处</span>
              </div>
              <div v-if="selectedModelData.agent_c_rewrite_count">
                <span class="text-ink-4">去AI味</span>
                <span class="font-medium text-ink" style="margin-left: 4px;">{{ selectedModelData.agent_c_rewrite_count }} 处</span>
              </div>
              <div v-if="selectedModelData.word_change_pct">
                <span class="text-ink-4">变化</span>
                <span class="font-medium text-ink" style="margin-left: 4px;">{{ selectedModelData.word_change_pct }}%</span>
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="view-toggle">
                <button class="toggle-btn" :class="{ active: mmViewMode === 'diff' }" @click="mmViewMode = 'diff'">对比</button>
                <button class="toggle-btn" :class="{ active: mmViewMode === 'full' }" @click="mmViewMode = 'full'">全文</button>
              </div>
              <button class="btn-text btn-sm" @click="copyText(selectedModelData.final_text)">
                <el-icon :size="15"><CopyDocument /></el-icon> 复制全文
              </button>
            </div>
          </div>

          <!-- 对比视图：原文 / 润色左右铺开 -->
          <template v-if="mmViewMode === 'diff'">
            <div class="diff-legend">
              <span class="diff-legend-item"><span class="diff-chip diff-chip-del"></span>原文删除 / 改写
                <em v-if="mmDiffStats">−{{ mmDiffStats.removed }} 字</em>
              </span>
              <span class="diff-legend-item"><span class="diff-chip diff-chip-ins"></span>润色新增
                <em v-if="mmDiffStats">+{{ mmDiffStats.added }} 字</em>
              </span>
            </div>
            <div class="diff-pane">
              <div class="diff-col">
                <div class="diff-col-head">原文</div>
                <div class="content-preview diff-view" v-html="mmDiffOriginalHtml" />
              </div>
              <div class="diff-col">
                <div class="diff-col-head">{{ providerLabel(selectedProvider) }} 润色后</div>
                <div class="content-preview diff-view" v-html="mmDiffPolishedHtml" />
              </div>
            </div>
          </template>
          <div v-else class="content-preview" style="white-space: pre-wrap;">{{ selectedModelData.final_text }}</div>
        </template>

        <div v-else class="plan-error">
          <p class="text-sm" style="color: var(--crimson);">{{ selectedModelData.error || '润色失败' }}</p>
        </div>
      </div>
    </div>
  </div>

  <!-- 保存草稿 / 发布到公众号 弹窗 -->
  <PublishChoiceDialog
    v-model="showPublishChoice"
    :title="title || '润色结果'"
    @save-draft="handleSaveDraft"
    @publish="handlePublishToEditor"
  />
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick, Document, Edit, Loading, Refresh, CopyDocument, Link, Promotion } from '@element-plus/icons-vue'
import FileUploadZone from '@/components/upload/FileUploadZone.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import AgentFeedbackPanel from '@/components/creation/AgentFeedbackPanel.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import { diffText } from '@/utils/textDiff'
import { publishToWechatEditor } from '@/utils/publishToEditor'
import PublishChoiceDialog from '@/components/PublishChoiceDialog.vue'
import api, { uploadFile, extractLinkContent } from '@/api/api'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'

const creditStore = useCreditStore()

const router = useRouter()
const progress = useAgentProgress()

const prefChips = ['金句加持', '事实核查', '去AI味', '全面润色']
const inputModes = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]

const mode = ref('file')
const title = ref('')
const contentText = ref('')
const preference = ref('')
const selectedChips = ref([])
const result = ref(null)
const editableText = ref('')
const originalText = ref('')
const viewMode = ref('diff')
const multiModelMode = ref(false)
const showPublishChoice = ref(false)
const multiModelResult = ref(null)
const creditCost = computed(() => (multiModelMode.value ? 30 : 6))
const selectedProvider = ref('')
const mmViewMode = ref('diff')

// 模型标签：对外只显示方案 A / B，不暴露具体模型名（DeepSeek=A，中转站=B）
const providerLabels = {
  deepseek: '方案 A',
  aigocode: '方案 B',
}
const providerLabel = (p) => {
  if (providerLabels[p]) return providerLabels[p]
  // 兜底：按出现顺序映射成方案 A / B / C…
  const keys = Object.keys(multiModelResult.value?.comparison?.models || {})
  const idx = keys.indexOf(p)
  return idx >= 0 ? `方案 ${String.fromCharCode(65 + idx)}` : p
}

// 文件上传
const fileName = ref('')
const fileText = ref('')
const fileUploading = ref(false)

// 链接提取
const linkUrl = ref('')
const linkTitle = ref('')
const linkContent = ref('')
const linkPlatform = ref('')
const linkExtracting = ref(false)

const canGenerate = computed(() => {
  return getContentText().trim().length >= 50 && !progress.isRunning.value
})

const getContentText = () => {
  if (mode.value === 'file') return fileText.value
  if (mode.value === 'link') return linkContent.value
  return contentText.value
}

const onFileSelect = async (file) => {
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

const removeFile = () => { fileName.value = ''; fileText.value = '' }

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
    linkTitle.value = ''; linkContent.value = ''; linkPlatform.value = ''
  } finally {
    linkExtracting.value = false
  }
}

const removeLink = () => { linkUrl.value = ''; linkTitle.value = ''; linkContent.value = ''; linkPlatform.value = '' }

const toggleChip = (chip) => {
  const idx = selectedChips.value.indexOf(chip)
  if (idx >= 0) {
    selectedChips.value.splice(idx, 1)
  } else {
    selectedChips.value.push(chip)
  }
  // 同步到 preference
  const extra = preference.value.replace(/金句加持|事实核查|去AI味|全面润色/g, '').replace(/[、，,]\s*/g, ' ').trim()
  const parts = [...selectedChips.value]
  if (extra) parts.push(extra)
  preference.value = parts.join('、')
}

// 监听进度结果
watch(() => progress.result.value, (data) => {
  if (data?.final_text) {
    result.value = data
    editableText.value = data.final_text || ''
    ElMessage.success('润色完成')
    // 刷新积分余额
    creditStore.fetchBalance()
  }
  // 多模型对比结果
  if (data?.comparison) {
    multiModelResult.value = data
    const models = data.comparison?.models || {}
    const keys = Object.keys(models)
    // 默认选中第一个成功的模型，没有则选第一个
    selectedProvider.value = keys.find(k => models[k]?.success) || keys[0] || ''
    mmViewMode.value = 'diff'
    ElMessage.success('对比完成')
  }
})

watch(() => progress.error.value, (err) => {
  if (err) {
    ElMessage.error('润色失败：' + err)
  }
})

const handleGenerate = async () => {
  const text = getContentText().trim()
  if (text.length < 50) {
    ElMessage.warning('请输入至少 50 个字符的文案')
    return
  }

  result.value = null
  editableText.value = ''
  originalText.value = text
  multiModelResult.value = null
  progress.stop()

  // 多模型对比模式
  if (multiModelMode.value) {
    try {
      const body = { text }
      if (title.value.trim()) body.title = title.value.trim()
      body.providers = ['deepseek', 'aigocode']

      const res = await api.post('/content-polish/compare', body, { timeout: 300000 })
      const data = res?.data || res
      const runId = data?.comparison?.run_id

      if (runId) {
        progress.start(runId)
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
    const body = { text }
    if (title.value.trim()) body.title = title.value.trim()
    if (preference.value.trim()) body.preference = preference.value.trim()

    const res = await api.post('/content-polish/generate', body, { timeout: 10000 })
    const data = res?.data || res
    const runId = data?.run_id

    if (runId) {
      progress.start(runId)
    } else {
      progress.error.value = '未获取到任务 ID'
    }
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

const copyFullText = () => {
  const text = editableText.value || result.value?.final_text || ''
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制润色全文')
}

const copyText = (text) => {
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制')
}

// 保存草稿（简单提示）
const handleSaveDraft = () => {
  ElMessage.success('草稿已保存')
}

// 发布到公众号编辑器
const handlePublishToEditor = async () => {
  const text = editableText.value || result.value?.final_text || ''
  // 多模型模式下用选中模型的数据
  const finalText = multiModelResult.value && selectedModelData.value
    ? (selectedModelData.value.final_text || text)
    : text
  // 润色结果作为正文，用户输入的标题保留
  await publishToWechatEditor(router, finalText, title.value)
}

// 简易 markdown 渲染
const renderedHtml = computed(() => {
  const txt = editableText.value || ''
  return txt
    .split(/\n\n+/)
    .map((para) => {
      const trimmed = para.trim()
      if (!trimmed) return ''
      if (trimmed.startsWith('### ')) return `<h3>${escapeHtml(trimmed.slice(4))}</h3>`
      if (trimmed.startsWith('## ')) return `<h2>${escapeHtml(trimmed.slice(3))}</h2>`
      if (trimmed.startsWith('# ')) return `<h2>${escapeHtml(trimmed.slice(2))}</h2>`
      return `<p>${escapeHtml(trimmed).replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
})

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// 双栏对比：把 diff 操作序列分别渲染成「原文侧」和「润色侧」
// 原文侧 = equal + delete（标红删除线），润色侧 = equal + insert（标绿）
function opsToSideHtml(ops, side) {
  return ops
    .map((op) => {
      if (side === 'original' && op.type === 'insert') return ''
      if (side === 'polished' && op.type === 'delete') return ''
      const html = escapeHtml(op.text).replace(/\n/g, '<br>')
      if (op.type === 'insert') return `<ins class="diff-ins">${html}</ins>`
      if (op.type === 'delete') return `<del class="diff-del">${html}</del>`
      return html
    })
    .join('')
}

function opsStats(ops) {
  let added = 0
  let removed = 0
  for (const op of ops) {
    if (op.type === 'insert') added += op.text.replace(/\s/g, '').length
    else if (op.type === 'delete') removed += op.text.replace(/\s/g, '').length
  }
  return { added, removed }
}

// 单模型对比
const diffOps = computed(() => {
  const o = originalText.value
  const p = editableText.value
  if (!o || !p) return []
  return diffText(o, p)
})
const diffOriginalHtml = computed(() => opsToSideHtml(diffOps.value, 'original'))
const diffPolishedHtml = computed(() => opsToSideHtml(diffOps.value, 'polished'))
const diffStats = computed(() => opsStats(diffOps.value))

// 多模型：当前选中模型的数据 / diff
const selectedModelData = computed(() => {
  const models = multiModelResult.value?.comparison?.models || {}
  return models[selectedProvider.value] || null
})
const mmDiffOps = computed(() => {
  const m = selectedModelData.value
  const o = originalText.value
  if (!m?.success || !o || !m.final_text) return []
  return diffText(o, m.final_text)
})
const mmDiffOriginalHtml = computed(() => opsToSideHtml(mmDiffOps.value, 'original'))
const mmDiffPolishedHtml = computed(() => opsToSideHtml(mmDiffOps.value, 'polished'))
const mmDiffStats = computed(() => opsStats(mmDiffOps.value))

// Agent 反馈面板数据
const agentFeedback = computed(() => {
  if (!result.value) return []
  const r = result.value
  const agents = []

  // Agent B - 金句加持
  const goldSentences = r.gold_sentences || []
  if (goldSentences.length || r.agent_b_sentence_count) {
    agents.push({
      code: 'B',
      name: '居怀金 · 金句催化员',
      role: '注入点睛金句',
      avatar: '/agents/content-b.png',
      summary: `共催化 ${r.agent_b_sentence_count || goldSentences.length} 条金句`,
      issues: goldSentences.map(g => ({
        text: g.content || g.text || g,
        location: `${g.location || ''} · ${g.sentence_type || ''}`,
      })),
      issuesLabel: '注入的金句',
    })
  }

  // Agent D - 事实核查
  const factualSummary = r.factual_summary
  if (factualSummary || r.agent_d_error_count) {
    const issues = []
    if (factualSummary?.potential_errors?.length) {
      issues.push(...factualSummary.potential_errors.map(e => ({
        text: e.claim || '',
        location: `第${e.section_number || '?'}节 · ${e.error_type || ''}`,
      })))
    }
    agents.push({
      code: 'D',
      name: '韩知微 · 事实总结员',
      role: '检查事实准确性',
      avatar: '/agents/content-d.png',
      summary: factualSummary?.summary_text || `检查了 ${factualSummary?.total_claims_checked || 0} 条事实陈述，发现 ${factualSummary?.error_count || r.agent_d_error_count || 0} 条潜在错误`,
      issues,
      issuesLabel: '潜在事实错误',
    })
  }

  // Agent E - 联网纠错
  const corrections = r.factual_corrections
  if (corrections || r.agent_e_correction_count) {
    const issues = []
    if (corrections?.corrections?.length) {
      issues.push(...corrections.corrections.map(c => ({
        text: `${c.original_claim || ''} → ${c.corrected_claim || ''}`,
        location: `第${c.section_number || '?'}节 · ${c.error_type || ''} · ${c.confidence || ''}`,
      })))
    }
    agents.push({
      code: 'E',
      name: '齐鉴真 · 联网纠错员',
      role: '联网验证事实',
      avatar: '/agents/content-e.png',
      summary: `共纠错 ${corrections?.total_corrections || r.agent_e_correction_count || 0} 处${corrections?.high_confidence_corrections ? `，${corrections.high_confidence_corrections} 处高置信度` : ''}`,
      issues,
      issuesLabel: '纠错记录',
    })
  }

  // Agent C - 去 AI 味
  const rewriteTable = r.rewrite_table || []
  if (rewriteTable.length || r.agent_c_rewrite_count) {
    // 按类型统计
    const typeCounts = {}
    for (const w of rewriteTable) {
      const t = w.ai_taste_type || '其他'
      typeCounts[t] = (typeCounts[t] || 0) + 1
    }
    const typeSummary = Object.entries(typeCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([t, n]) => `${t}×${n}`)
      .join('、')
    const highCount = rewriteTable.filter(w => String(w.priority || '').includes('🚫')).length
    const warnCount = rewriteTable.filter(w => String(w.priority || '').includes('⚠️')).length
    agents.push({
      code: 'C',
      name: '景澄之 · 正文改写员',
      role: '改写机器腔表达',
      avatar: '/agents/content-c.png',
      summary: `共改写 ${r.agent_c_rewrite_count || rewriteTable.length} 处${highCount ? `，${highCount} 处高优先级` : ''}${warnCount ? `，${warnCount} 处中优先级` : ''}。${typeSummary ? `涉及：${typeSummary}。` : ''}`,
      issues: [],
      issuesLabel: '改写对照表',
    })
  }

  return agents
})

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
.cta-bar { position: relative; width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.type-chip { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--paper); color: #6B6862; border: 1px solid var(--line); cursor: pointer; transition: all 0.15s; }
.type-chip:hover { background: #F0EDE3; color: var(--ink); }
.type-chip-active { background: var(--clay); color: #fff; border-color: var(--clay); }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.dropzone-active { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.tab-grid > div { min-height: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.btn-text { display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px; border: none; background: transparent; color: var(--clay-deep); font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; border-radius: var(--r-sm); transition: all .14s; }
.btn-text:hover { background: var(--clay-tint); }
.btn-ghost { display: inline-flex; align-items: center; gap: 5px; padding: 7px 14px; border: 1px solid var(--line); background: var(--paper); color: var(--ink-2); font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; border-radius: var(--r-md); transition: all .14s; }
.btn-ghost:hover { border-color: var(--clay-soft); color: var(--clay-deep); }
.btn-primary { display: inline-flex; align-items: center; gap: 5px; padding: 8px 18px; border: none; background: var(--clay); color: white; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: var(--r-md); transition: all .14s; }
.btn-primary:hover { background: var(--clay-deep); }
.btn-sm { padding: 5px 10px; font-size: 12px; }

/* 左右分栏 */
.result-split {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 20px;
  align-items: start;
}
@media (max-width: 900px) {
  .result-split {
    grid-template-columns: 1fr;
  }
}
.result-full { display: block; }

/* 双栏对比：原文 | 润色后 */
.diff-pane {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 720px) {
  .diff-pane { grid-template-columns: 1fr; }
}
.diff-col {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  overflow: hidden;
  background: var(--paper);
}
.diff-col-head {
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3);
  background: var(--bone);
  border-bottom: 1px solid var(--line);
}
.diff-col .diff-view {
  padding: 14px 16px;
  max-height: 70vh;
  overflow-y: auto;
}

/* 预览区 */
.content-preview {
  font-size: 15px;
  line-height: 1.85;
  color: var(--ink);
}
.content-preview :deep(p) {
  margin-bottom: 14px;
  text-align: justify;
  text-justify: inter-ideograph;
}
.content-preview :deep(h2) {
  font-size: 20px;
  font-weight: 700;
  margin: 20px 0 10px;
}
.content-preview :deep(h3) {
  font-size: 17px;
  font-weight: 600;
  margin: 16px 0 8px;
}

/* 对比视图 */
.diff-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  padding: 9px 14px;
  margin-bottom: 12px;
  background: var(--bone);
  border-radius: var(--r-md);
  font-size: 12px;
  color: var(--ink-3);
}
.diff-legend-item { display: inline-flex; align-items: center; gap: 6px; }
.diff-legend-item em { font-style: normal; font-weight: 600; color: var(--ink-2); }
.diff-chip { width: 12px; height: 12px; border-radius: 3px; }
.diff-chip-ins { background: rgba(70, 145, 90, 0.28); }
.diff-chip-del { background: rgba(184, 84, 80, 0.22); }
.diff-view {
  white-space: pre-wrap;
  word-break: break-word;
}
.diff-view :deep(ins.diff-ins) {
  text-decoration: none;
  background: rgba(70, 145, 90, 0.16);
  color: #2f7a45;
  border-radius: 2px;
  padding: 0 1px;
  box-shadow: inset 0 -2px 0 rgba(70, 145, 90, 0.45);
}
.diff-view :deep(del.diff-del) {
  text-decoration: line-through;
  text-decoration-color: rgba(184, 84, 80, 0.7);
  background: rgba(184, 84, 80, 0.10);
  color: #b85450;
  border-radius: 2px;
  padding: 0 1px;
}

/* 编辑/预览切换 */
.view-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--bone);
  border-radius: var(--r-pill);
}
.toggle-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border: none;
  background: transparent;
  color: var(--ink-3);
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--r-pill);
  cursor: pointer;
  transition: all .18s;
}
.toggle-btn:hover { color: var(--ink); }
.toggle-btn.active {
  background: var(--paper);
  color: var(--clay-deep);
  box-shadow: var(--sh-1);
}

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

.multi-model-toggle .toggle-label {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.multi-model-toggle .toggle-checkbox {
  opacity: 0;
  width: 0;
  height: 0;
}

.multi-model-toggle .toggle-slider {
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

.multi-model-toggle .toggle-slider:before {
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

.multi-model-toggle .toggle-checkbox:checked + .toggle-slider {
  background-color: var(--clay);
}

.multi-model-toggle .toggle-checkbox:checked + .toggle-slider:before {
  transform: translateX(16px);
}

/* 多模型：模型选择按钮 */
.model-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.model-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  border: 1px solid var(--line);
  background: var(--paper);
  border-radius: var(--r-pill);
  font-family: inherit;
  cursor: pointer;
  transition: all .16s;
}
.model-tab:hover { border-color: var(--clay-soft); }
.model-tab.active {
  border-color: var(--clay);
  background: var(--clay-tint);
  box-shadow: 0 4px 14px rgba(204,120,92,.18);
}
.model-tab-name { font-size: 14px; font-weight: 600; color: var(--ink); }
.model-tab.active .model-tab-name { color: var(--clay-deep); }
.model-tab-meta { font-size: 12px; color: var(--ink-4); }
.model-tab-meta.failed { color: var(--crimson); }
.model-tab.failed { opacity: .75; }

.plan-error {
  padding: 20px;
  text-align: center;
  background: rgba(184, 84, 80, 0.03);
  border-radius: var(--r-md);
}
</style>
