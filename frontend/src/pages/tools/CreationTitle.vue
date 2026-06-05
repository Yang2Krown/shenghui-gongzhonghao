<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><ChatDotSquare /></el-icon>
        创作工具 · 标题生成
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        写一个让人<span class="text-clay">忍不住点开</span>的标题
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        给定正文 —— 可以是文件、链接或文本，AI 会生成多个候选标题并按吸引力打分。
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
            <el-input v-model="value" type="textarea" :rows="5"
              placeholder="粘贴文章正文……" style="resize: none;" />
          </div>
        </div>
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
          <button v-for="chip in styleChips" :key="chip" @click="toggleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：风格克制不标题党，控制在 20 字内，突出反差感……" />
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
      <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate" style="flex: 1;">
        <template v-if="progress.isRunning.value">
          <el-icon class="spin"><Loading /></el-icon> 正在打磨标题…
        </template>
        <template v-else>生成标题</template>
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
      <PipelineStepper current="title" />
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">推荐标题</h2>
          <span class="text-sm text-ink-4">按综合评分排序</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <!-- Top 推荐 -->
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div v-for="(rec, index) in result.recommendations" :key="rec.rank || index"
          class="card lift slide-up" :style="{ padding: '18px 22px', display: 'flex', alignItems: 'center', gap: '18px', animationDelay: `${index * 50}ms` }">
          <div style="flex-shrink: 0; text-align: center; width: 54px;">
            <div class="font-serif" :style="{ fontSize: '26px', fontWeight: 600, color: (rec.final_score || rec.score) >= 7 ? 'var(--clay)' : 'var(--ink-3)', lineHeight: 1 }">
              {{ (rec.final_score || rec.score || 0).toFixed(1) }}
            </div>
            <div class="text-xs text-ink-4" style="margin-top: 3px;">综合分</div>
          </div>
          <div style="width: 1px; align-self: stretch; background: var(--line);"></div>
          <div style="flex: 1;">
            <h3 class="font-serif text-ink" style="font-size: 18px; line-height: 1.4; font-weight: 600;">{{ rec.title }}</h3>
            <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
              <span v-if="rec.method" class="badge badge-clay">{{ rec.method }}</span>
              <span v-if="rec.b_score" class="badge badge-info">评审 {{ rec.b_score.toFixed(1) }}</span>
              <span v-if="rec.c_click_willingness" class="badge badge-success">点击意愿 {{ rec.c_click_willingness.toFixed(1) }}</span>
            </div>
            <p v-if="rec.reason" class="text-xs text-ink-4" style="margin-top: 6px;">{{ rec.reason }}</p>
          </div>
          <button class="btn-text btn-sm" @click="copyText(rec.title)">
            <el-icon :size="15"><CopyDocument /></el-icon> 复制
          </button>
        </div>
      </div>

      <!-- 全部候选（可展开） -->
      <details v-if="result.candidates?.length" style="margin-top: 20px;">
        <summary class="text-sm text-ink-4 font-semibold cursor-pointer" style="padding: 8px 0; letter-spacing: .03em;">
          查看全部 {{ result.candidates.length }} 个候选标题
        </summary>
        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px;">
          <div v-for="c in result.candidates" :key="c.id"
            style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid var(--line); border-radius: var(--r-md);"
            :style="{ opacity: c.is_eliminated ? 0.45 : 1 }">
            <span class="font-serif text-sm" :style="{ color: c.is_eliminated ? 'var(--ink-4)' : 'var(--clay)', fontWeight: 600, width: '36px', textAlign: 'center' }">
              {{ c.final_score?.toFixed(1) || '-' }}
            </span>
            <span style="flex: 1;" class="text-sm" :style="{ textDecoration: c.is_eliminated ? 'line-through' : 'none', color: c.is_eliminated ? 'var(--ink-4)' : 'var(--ink)' }">
              {{ c.title }}
            </span>
            <span v-if="c.method" class="text-xs text-ink-4">{{ c.method }}</span>
            <span v-if="c.is_eliminated" class="text-xs" style="color: var(--crimson);">已淘汰</span>
            <button v-else class="btn-text btn-sm" @click="copyText(c.title)" style="padding: 2px 6px;">
              <el-icon :size="13"><CopyDocument /></el-icon>
            </button>
          </div>
        </div>
      </details>
    </div>

    <!-- 多模型对比结果 -->
    <div v-if="multiModelResult && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">对比结果</h2>
          <span class="text-sm text-ink-4">选择你更喜欢的标题风格</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <!-- 选题分析 -->
      <div v-if="multiModelResult.extracted_topic" class="card" style="padding: 18px 22px; margin-bottom: 16px;">
        <div style="display: flex; gap: 16px; flex-wrap: wrap;">
          <div>
            <span class="text-xs text-ink-4">主题</span>
            <p class="text-sm font-medium text-ink">{{ multiModelResult.extracted_topic.title }}</p>
          </div>
          <div>
            <span class="text-xs text-ink-4">方向</span>
            <span class="badge badge-info" style="margin-left: 6px;">{{ multiModelResult.extracted_topic.direction }}</span>
          </div>
          <div>
            <span class="text-xs text-ink-4">套路</span>
            <span class="text-sm text-ink" style="margin-left: 6px;">{{ multiModelResult.extracted_topic.method }}</span>
          </div>
        </div>
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
              {{ modelData.count }} 个标题
            </span>
            <span v-else class="text-xs" style="color: var(--crimson);">生成失败</span>
          </div>

          <!-- 标题列表 -->
          <div v-if="modelData.success && modelData.candidates.length" class="plan-titles">
            <div
              v-for="(c, i) in modelData.candidates"
              :key="i"
              class="plan-title-card"
            >
              <div style="display: flex; align-items: flex-start; gap: 12px;">
                <span class="plan-rank" :class="i === 0 ? 'rank-first' : ''">
                  {{ i + 1 }}
                </span>
                <div style="flex: 1; min-width: 0;">
                  <p class="plan-title-text">{{ c.title }}</p>
                  <div style="display: flex; align-items: center; gap: 6px; margin-top: 6px;">
                    <span v-if="c.method" class="badge badge-clay" style="font-size: 11px;">{{ c.method }}</span>
                    <span class="text-xs text-ink-4">{{ c.word_count }} 字</span>
                  </div>
                  <p v-if="c.explanation" class="text-xs text-ink-4" style="margin-top: 6px; line-height: 1.5;">{{ c.explanation }}</p>
                </div>
                <button class="btn-text btn-sm" @click="copyText(c.title)" style="flex-shrink: 0; padding: 4px 8px;">
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
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotSquare, Document, Link, Upload, Edit, Loading, Refresh, CopyDocument, Check } from '@element-plus/icons-vue'
import PipelineStepper from '@/components/creation/PipelineStepper.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api, { uploadFile, extractLinkContent } from '@/api/api'

const router = useRouter()
const progress = useAgentProgress()

const inputModes = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]
const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const mode = ref('file')
const value = ref('')
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
const multiModelMode = ref(false) // 多模型对比模式
const multiModelResult = ref(null) // 多模型对比结果

const canGenerate = computed(() => {
  let hasContent = false
  if (mode.value === 'link') {
    hasContent = !!linkTitle.value
  } else if (mode.value === 'file') {
    hasContent = !!fileText.value
  } else {
    hasContent = value.value.trim().length > 10
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

const dragOver = ref(false)

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

watch(() => progress.result.value, (data) => {
  if (data?.recommendations) {
    result.value = data
  }
  // 多模型对比结果
  if (data?.comparison) {
    multiModelResult.value = data
  }
})

const handleGenerate = async () => {
  result.value = null
  multiModelResult.value = null
  progress.stop()

  let content = ''
  if (mode.value === 'link' && linkTitle.value) {
    // 优先使用链接提取的内容
    const parts = []
    if (linkTitle.value) parts.push(`标题：${linkTitle.value}`)
    if (linkContent.value) parts.push(linkContent.value)
    content = parts.join('\n')
  } else if (mode.value === 'file') {
    content = fileText.value
  } else {
    content = value.value.trim()
  }

  if (!content || content.length < 10) {
    ElMessage.warning('请输入至少 10 个字符的正文内容')
    return
  }

  // 多模型对比模式
  if (multiModelMode.value) {
    try {
      progress.start('multi-model')
      const res = await api.post('/standalone-title/compare', {
        content,
        providers: ['deepseek', 'aigocode'],
      }, { timeout: 300000 })

      const data = res?.data || res
      const runId = data?.comparison?.run_id

      if (runId) {
        progress.start(`/api/v1/standalone-title/compare/stream/${runId}`)
      } else {
        progress.error.value = '未获取到任务 ID'
      }
    } catch (err) {
      progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
    }
    return
  }

  // 单模型模式（原有逻辑）
  try {
    // 创建选题候选
    const sources = [{ type: 'text', content }]
    const res = await api.post('/topic-candidates/create-adhoc', {
      sources,
      preference: preference.value,
    }, { timeout: 10000 })

    const data = res?.data || res
    const candidateId = data?.data?.candidate_id || data?.candidate_id
    if (!candidateId) {
      ElMessage.error('未能创建选题')
      return
    }

    // 存储正文到 sessionStorage
    sessionStorage.setItem('creation_title_content_text', content)

    // 跳转到编辑器，只生成标题
    router.push({
      path: '/creation/new',
      query: {
        candidate_id: candidateId,
        topic_title: data?.data?.title || data?.title || content.slice(0, 30),
        auto_generate_title: 'true',
      }
    })
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
  }
}

const copyText = (text) => {
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制')
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
.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
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
