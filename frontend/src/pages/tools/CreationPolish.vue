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

    <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate" style="margin-bottom: 16px;">
      <template v-if="progress.isRunning.value">
        <el-icon class="spin"><Loading /></el-icon> 正在润色文案…
      </template>
      <template v-else>开始润色</template>
    </button>

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
    <div v-if="result && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
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

      <!-- 左右分栏 -->
      <div class="result-split">
        <!-- 左侧：润色后全文 -->
        <div class="result-left">
          <div class="card" style="padding: 18px 22px; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
              <h3 class="text-h4 font-sans text-ink">润色全文</h3>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div class="view-toggle">
                  <button class="toggle-btn" :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
                  <button class="toggle-btn" :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
                </div>
                <button class="btn-text btn-sm" @click="copyFullText">
                  <el-icon :size="15"><CopyDocument /></el-icon> 复制全文
                </button>
              </div>
            </div>

            <el-input
              v-if="viewMode === 'edit'"
              v-model="editableText"
              type="textarea"
              :autosize="{ minRows: 16, maxRows: 60 }"
              resize="vertical"
            />
            <div v-else class="content-preview prose" v-html="renderedHtml" />
          </div>
        </div>

        <!-- 右侧：Agent 反馈面板 -->
        <div class="result-right">
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
          <button class="btn-primary btn-sm" @click="copyFullText">
            <el-icon :size="14"><CopyDocument /></el-icon> 复制全文
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Document, Edit, Loading, Refresh, CopyDocument, Link, Upload } from '@element-plus/icons-vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import AgentFeedbackPanel from '@/components/creation/AgentFeedbackPanel.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api, { uploadFile, extractLinkContent } from '@/api/api'

const progress = useAgentProgress()

const prefChips = ['金句加持', '事实核查', '去AI味', '全面润色']
const inputModes = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]

const mode = ref('text')
const title = ref('')
const contentText = ref('')
const preference = ref('')
const selectedChips = ref([])
const result = ref(null)
const editableText = ref('')
const viewMode = ref('preview')

// 文件上传
const fileName = ref('')
const fileText = ref('')
const fileUploading = ref(false)
const dragOver = ref(false)

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
      ElMessage.warning('文件内容提取为空')
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
  if (data) {
    result.value = data
    editableText.value = data.final_text || ''
    ElMessage.success('润色完成')
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
  progress.stop()

  try {
    const body = { text }
    if (title.value.trim()) body.title = title.value.trim()
    if (preference.value.trim()) body.preference = preference.value.trim()

    const res = await api.post('/content-polish/generate', body, { timeout: 10000 })
    const data = res?.data || res
    const runId = data?.run_id

    if (runId) {
      progress.start(`/api/v1/content-polish/stream/${runId}`)
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
.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
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

/* 预览区 */
.content-preview {
  font-size: 15px;
  line-height: 1.85;
  color: var(--ink);
}
.content-preview :deep(p) {
  margin-bottom: 14px;
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
</style>
