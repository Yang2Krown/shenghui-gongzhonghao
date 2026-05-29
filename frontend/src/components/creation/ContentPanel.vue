<template>
  <div class="content-panel">
    <!-- Agent 状态提示 -->
    <div v-if="generating" class="mb-6">
      <AgentStatusBar
        v-for="(step, i) in agentSteps"
        :key="i"
        :agent-name="step.agent"
        :action="step.action"
        :avatar="step.avatar"
        :is-active="i === currentStepIndex"
        :show-progress="i === currentStepIndex"
        :percent="i === currentStepIndex ? stepPercent : (i < currentStepIndex ? 100 : 0)"
        class="mb-2"
      />
    </div>

    <!-- 空状态：生成按钮 -->
    <div v-if="status === 'idle'" class="text-center py-16">
      <div class="mb-4">
        <el-icon :size="48" style="color: var(--line);"><Edit /></el-icon>
      </div>
      <h3 class="text-h4 font-sans text-ink mb-2">生成正文</h3>
      <p class="text-ink-3 mb-6">基于大纲和标题，AI 将生成完整的公众号文章</p>
      <el-button type="primary" size="large" @click="generateContent" :loading="generating">
        <el-icon><MagicStick /></el-icon>
        生成正文
      </el-button>
    </div>

    <!-- 生成中 -->
    <div v-if="status === 'generating'" class="text-center py-8">
      <p class="text-ink-3">正文生成中，请稍候...</p>
    </div>

    <!-- 失败 -->
    <div v-if="status === 'failed'" class="text-center py-16">
      <el-icon :size="48" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4 mb-2">生成失败</h3>
      <p class="text-ink-3 mb-6">{{ errorMessage }}</p>
      <el-button @click="generateContent">重试</el-button>
    </div>

    <!-- 完成：左右分栏 -->
    <div v-if="status === 'completed' && content" class="content-result-split">
      <!-- 左侧：可编辑正文 -->
      <div class="result-left">
        <!-- 统计信息 -->
        <div class="card p-4 mb-4">
          <h3 v-if="titleData?.title" class="selected-title">{{ titleData.title }}</h3>
          <div class="flex flex-wrap items-center gap-6 text-sm">
            <div>
              <span class="text-ink-3">字数：</span>
              <span class="font-medium text-ink">{{ editableText.length }} / 原 {{ content.final_word_count }}</span>
            </div>
            <div>
              <span class="text-ink-3">节数：</span>
              <span class="font-medium text-ink">{{ content.section_count }}</span>
            </div>
            <div>
              <span class="text-ink-3">改写次数：</span>
              <span class="font-medium text-ink">{{ content.rewrite_count }}</span>
            </div>
            <div>
              <span class="text-ink-3">诊断评分：</span>
              <span class="font-bold" :class="getScoreColor(content.diagnosis?.total_score)">
                {{ content.diagnosis?.total_score?.toFixed(1) || '-' }}
              </span>
            </div>
            <div v-if="content.diagnosis?.recommended_action" class="ml-auto">
              <span class="text-xs text-ink-3">建议：</span>
              <span class="text-xs font-semibold text-ink">{{ content.diagnosis.recommended_action }}</span>
            </div>
          </div>
          <p v-if="content.style_anchor" class="style-anchor-inline">{{ content.style_anchor }}</p>
          <div v-if="highlightFragments.length" class="hl-legend">
            <span class="hl-legend-item"><mark class="hl-gold">金句</mark></span>
            <span class="hl-legend-item"><mark class="hl-deai">去AI味改写</mark></span>
            <span class="text-ink-4 text-xs">预览模式下悬停查看</span>
          </div>
        </div>

        <!-- 正文编辑区 -->
        <div class="card p-5 mb-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-h4 font-sans text-ink">正文</h3>
            <div class="flex items-center gap-2">
              <div class="view-toggle">
                <button class="toggle-btn" :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
                <button class="toggle-btn" :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
              </div>
              <el-button link size="small" @click="copyText">
                <el-icon><DocumentCopy /></el-icon> 复制
              </el-button>
            </div>
          </div>

          <el-input
            v-if="viewMode === 'edit'"
            v-model="editableText"
            type="textarea"
            :autosize="{ minRows: 18, maxRows: 60 }"
            class="content-edit"
            resize="vertical"
          />
          <div v-else ref="previewRef" class="content-preview prose" v-html="renderedHtml" @mousemove="onPreviewMouseMove" @mouseleave="onPreviewMouseLeave" />
        </div>

      </div>

      <!-- 右侧：Agent 反馈 -->
      <div class="result-right">
        <AgentFeedbackPanel
          :agents="agentFeedback"
          subtitle="正文流水线：A 撰写 → B 金句 → C 去 AI 味 → D 8 维度诊断"
        />
      </div>
    </div>

    <!-- 固定底部操作栏 -->
    <div v-if="status === 'completed' && content" class="content-bottom-bar">
      <div class="bottom-bar-inner">
        <el-button @click="generateContent" :loading="generating">
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
        <el-button :loading="reevaluating" @click="reevaluateContent">
          <el-icon><Refresh /></el-icon>
          重新评估
        </el-button>
        <el-button type="primary" @click="confirmContent">
          确认正文
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, MagicStick, CircleCloseFilled, DocumentCopy, Document, Refresh, ArrowRight } from '@element-plus/icons-vue'
import AgentStatusBar from './AgentStatusBar.vue'
import AgentFeedbackPanel from './AgentFeedbackPanel.vue'
import { post } from '@/api/api'
import { reevaluateContent as reevaluateContentApi } from '@/api/creation'
import { useAgentProgress } from '@/composables/useAgentProgress'

const props = defineProps({
  candidateId: { type: [Number, String], default: null },
  outlineData: { type: Object, default: null },
  titleData: { type: Object, default: null },
  initialContent: { type: Object, default: null },
})

const emit = defineEmits(['complete', 'next-step', 'save-draft'])

// 状态
const status = ref('idle')
const generating = ref(false)
const content = ref(null)
const editableText = ref('')
const viewMode = ref('preview')
const errorMessage = ref('')
const saving = ref(false)
const reevaluating = ref(false)

// Agent 进度（SSE 驱动）
const progress = useAgentProgress()
const agentSteps = progress.steps
const currentStepIndex = progress.currentStepIndex
const stepPercent = progress.stepPercent

// 监听 SSE 结果
watch(() => progress.result.value, (newResult) => {
  if (newResult) {
    content.value = newResult
    editableText.value = newResult.final_text || ''
    status.value = 'completed'
    ElMessage.success('正文生成完成')
    generating.value = false
  }
})

// 监听 SSE 错误
watch(() => progress.error.value, (newError) => {
  if (newError) {
    status.value = 'failed'
    errorMessage.value = newError
    generating.value = false
    ElMessage.error('正文生成失败')
  }
})

// 加载已有正文内容（从草稿恢复）
watch(() => props.initialContent, (ic) => {
  if (ic && !content.value) {
    content.value = ic
    editableText.value = ic.final_text || ic.content || ''
    status.value = 'completed'
  }
}, { immediate: true })

onUnmounted(() => {
  progress.stop()
  reevaluateProgress.stop()
})

const generateContent = async () => {
  const outlineId = props.outlineData?.id ?? props.outlineData?.outline_id
  if (!props.candidateId || !outlineId) {
    ElMessage.warning('缺少选题或大纲信息')
    return
  }

  status.value = 'generating'
  generating.value = true
  errorMessage.value = ''

  try {
    const res = await post('/content-generation/generate', {
      candidate_id: Number(props.candidateId),
      outline_id: Number(outlineId),
    })

    const runId = res.data.run_id
    if (runId) {
      progress.start(`/api/v1/content-generation/stream/${runId}`)
    }
  } catch (error) {
    status.value = 'failed'
    errorMessage.value = error?.response?.data?.detail || error?.message || '生成失败'
    generating.value = false
    ElMessage.error('正文生成失败')
  }
}

const confirmContent = () => {
  emit('complete', { ...content.value, final_text: editableText.value })
  emit('next-step')
  ElMessage.success('正文已确认')
}

const saveDraft = () => {
  emit('save-draft', { ...content.value, final_text: editableText.value })
}

// 保存编辑后的正文（本地状态更新，正文暂无独立 PATCH 接口）
const saveContent = () => {
  if (content.value) {
    content.value.final_text = editableText.value
    content.value.final_word_count = editableText.value.length
  }
  saving.value = true
  setTimeout(() => {
    saving.value = false
    ElMessage.success('正文已保存')
  }, 300)
}

// 重新评估正文（只跑 Agent D）
const reevaluateProgress = useAgentProgress()
const reevaluateContent = async () => {
  if (!editableText.value || !content.value) return
  reevaluating.value = true
  try {
    const outlineSections = props.outlineData?.sections || []
    const res = await reevaluateContentApi({
      text: editableText.value,
      title: props.titleData?.title || props.outlineData?.title || '',
      style_anchor: content.value.style_anchor || '',
      sections: outlineSections.map(s => ({
        section_number: s.section_number || 0,
        subtitle: s.title || '',
        core_points: s.core_points || [],
        word_estimate: s.word_count || 500,
      })),
      gold_sentences: (content.value.gold_sentences || []).map(g => ({
        sentence_type: g.sentence_type,
        location: g.location,
        section_number: g.section_number || 1,
        content: g.content,
      })),
    })
    const runId = res.data.run_id
    if (runId) {
      reevaluateProgress.start(`/api/v1/content-generation/stream/${runId}`)
    }
  } catch (e) {
    reevaluating.value = false
    ElMessage.error('重新评估请求失败')
  }
}

// 监听重新评估结果
watch(() => reevaluateProgress.result.value, (newResult) => {
  if (newResult) {
    // 更新诊断结果
    if (content.value) {
      content.value.diagnosis = newResult
    }
    ElMessage.success('重新评估完成')
    reevaluating.value = false
  }
})

watch(() => reevaluateProgress.error.value, (newError) => {
  if (newError) {
    ElMessage.error(`重新评估失败: ${newError}`)
    reevaluating.value = false
  }
})

const copyText = async () => {
  try {
    await navigator.clipboard.writeText(editableText.value)
    ElMessage.success('正文已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

const copySentence = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 收集需要高亮的文本片段
const highlightFragments = computed(() => {
  if (!content.value) return []
  const fragments = []

  // Agent B 金句
  const goldSentences = content.value.gold_sentences || []
  for (const s of goldSentences) {
    if (s.content && s.content.length >= 4) {
      fragments.push({ text: s.content, type: 'gold', label: s.sentence_type || '金句' })
    }
  }

  // Agent C 改写后文本
  const rewrites = content.value.rewrite_table || []
  for (const r of rewrites) {
    if (r.rewritten_text && r.rewritten_text.length >= 4) {
      fragments.push({ text: r.rewritten_text, type: 'deai', label: r.ai_taste_subtype || '去AI味' })
    }
  }

  // 按长度从长到短排序，避免短片段先匹配导致长片段断裂
  fragments.sort((a, b) => b.text.length - a.text.length)
  return fragments
})

// 对一段已 escapeHtml 的文本做高亮标记
function applyHighlights(html) {
  const frags = highlightFragments.value
  if (!frags.length) return html

  for (const frag of frags) {
    const escaped = escapeHtml(frag.text)
    if (!escaped) continue
    const idx = html.indexOf(escaped)
    if (idx === -1) continue
    const cls = frag.type === 'gold' ? 'hl-gold' : 'hl-deai'
    const tipLabel = frag.type === 'gold' ? '金句' : '去AI味改写'
    const tipDetail = escapeHtml(frag.label)
    const tag = `<mark class="${cls}" data-hl-type="${tipLabel}" data-hl-detail="${tipDetail}">${escaped}</mark>`
    html = html.substring(0, idx) + tag + html.substring(idx + escaped.length)
  }
  return html
}

const renderedHtml = computed(() => {
  const txt = editableText.value || ''
  // 简单的 markdown-ish 渲染：段落 + ## / ### 标题
  const raw = txt
    .split(/\n\n+/)
    .map((para) => {
      const trimmed = para.trim()
      if (!trimmed) return ''
      if (trimmed.startsWith('### ')) return `<h3>${inlineMarkdown(escapeHtml(trimmed.slice(4)))}</h3>`
      if (trimmed.startsWith('## ')) return `<h2>${inlineMarkdown(escapeHtml(trimmed.slice(3)))}</h2>`
      if (trimmed.startsWith('# ')) return `<h2>${inlineMarkdown(escapeHtml(trimmed.slice(2)))}</h2>`
      return `<p>${inlineMarkdown(escapeHtml(trimmed)).replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
  return applyHighlights(raw)
})

function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 行内 Markdown：**加粗**、*斜体*、`代码`
function inlineMarkdown(html) {
  return html
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
}

// ── 自定义高亮 Tooltip（即时响应） ────────────────────
let hlTooltipEl = null
let lastMark = null

function ensureTooltip() {
  if (hlTooltipEl) return hlTooltipEl
  hlTooltipEl = document.createElement('div')
  hlTooltipEl.className = 'hl-tooltip'
  hlTooltipEl.style.display = 'none'
  document.body.appendChild(hlTooltipEl)
  return hlTooltipEl
}

function showTip(mark) {
  if (mark === lastMark) return
  lastMark = mark
  const tip = ensureTooltip()
  if (!mark) { tip.style.display = 'none'; return }
  const type = mark.dataset.hlType
  const detail = mark.dataset.hlDetail
  const isGold = mark.classList.contains('hl-gold')
  tip.innerHTML = `<span class="hl-tip-badge ${isGold ? 'hl-tip-gold' : 'hl-tip-deai'}">${type}</span><span class="hl-tip-detail">${detail}</span>`
  const rect = mark.getBoundingClientRect()
  tip.style.left = `${rect.left + rect.width / 2}px`
  tip.style.top = `${rect.top - 6}px`
  tip.style.display = 'flex'
}

function onPreviewMouseMove(e) {
  const mark = e.target.closest('mark[data-hl-type]')
  showTip(mark || null)
}

function onPreviewMouseLeave() {
  lastMark = null
  if (hlTooltipEl) hlTooltipEl.style.display = 'none'
}

const previewRef = ref(null)

onUnmounted(() => {
  if (hlTooltipEl) { hlTooltipEl.remove(); hlTooltipEl = null }
})

const getScoreColor = (score) => {
  if (!score) return 'text-ink-3'
  if (score >= 8) return 'text-leaf'
  if (score >= 6) return 'text-sand'
  return 'text-crimson'
}

// ── Agent 反馈数据组装 ────────────────────────────
const D_DIM_LABELS = {
  title_fulfillment: { label: '标题承诺兑现度', weight: 20 },
  outline_alignment: { label: '大纲结构对应度', weight: 15 },
  word_compliance: { label: '字数合规', weight: 10 },
  style_consistency: { label: '风格统一性', weight: 15 },
  deai_thoroughness: { label: '去 AI 味彻底度', weight: 15 },
  gold_sentence_completeness: { label: '金句完整度', weight: 10 },
  opening_quality: { label: '开头质量', weight: 10 },
  ending_quality: { label: '结尾升华度', weight: 5 },
}

const agentFeedback = computed(() => {
  const c = content.value
  if (!c) return []

  // Agent A 撰写
  const agentA = {
    id: 'A',
    code: 'A',
    name: '温如言 · 正文创作员',
    role: '定风格锚点 + 分节铺陈',
    avatar: '/agents/content-a.png',
    summary: c.style_anchor ? `风格锚点：${c.style_anchor}` : '',
  }

  // Agent B 金句催化
  const gold = c.gold_sentences || []
  const agentB = {
    id: 'B',
    code: 'B',
    name: '居怀金 · 正文催化员',
    role: '注入 3-5 个高传播金句',
    avatar: '/agents/content-b.png',
    summary: gold.length
      ? `共催化 ${gold.length} 个金句，类型涵盖 ${[...new Set(gold.map((g) => g.sentence_type))].length} 种。`
      : '',
    issues: gold.map((g) => ({
      location: `${g.location} · ${g.sentence_type}`,
      text: g.content,
    })),
  }

  // Agent C 去 AI 味
  const rewrites = c.rewrite_table || []
  const highRewrites = rewrites.filter((r) =>
    String(r.priority || '').includes('🚫')
  )
  const agentC = {
    id: 'C',
    code: 'C',
    name: '景澄之 · 正文改写员',
    role: '扫描 6 类 AI 味并按优先级改写',
    avatar: '/agents/content-c.png',
    summary: rewrites.length
      ? `共改写 ${rewrites.length} 处${highRewrites.length ? `（${highRewrites.length} 处高优先级）` : ''}。`
      : c.rewrite_count
        ? `共改写 ${c.rewrite_count} 处。`
        : '',
    issues: rewrites.slice(0, 20).map((r) => ({
      location: `${r.location} · ${r.ai_taste_subtype || r.ai_taste_type}`,
      text: `${r.priority ? r.priority + ' ' : ''}${r.reason || ''}`,
    })),
  }

  // Agent D 8 维度自检
  const diag = c.diagnosis || {}
  const dims = diag.dimensions || {}
  const agentD = {
    id: 'D',
    code: 'D',
    name: '钟可期 · 正文诊断员',
    role: '8 维度评分 + 三档修改建议',
    avatar: '/agents/content-d.png',
    score: diag.total_score,
    verdict: diag.recommended_action,
    verdictPassed: diag.recommended_action === '接受发布',
    summary: diag.recommended_action ? `建议处理路径：${diag.recommended_action}` : '',
    dimensions: Object.entries(D_DIM_LABELS)
      .map(([key, conf]) => {
        const d = dims[key]
        if (!d) return null
        return {
          key,
          label: conf.label,
          weight: conf.weight,
          score: d.score,
          evaluation: d.evaluation,
          suggestions: d.suggestions || [],
        }
      })
      .filter(Boolean),
    priorities: {
      high: diag.high_priority || [],
      medium: diag.medium_priority || [],
      low: diag.low_priority || [],
    },
  }

  return [agentA, agentB, agentC, agentD]
})
</script>

<style scoped>
.view-toggle {
  display: inline-flex;
  background: var(--bone);
  border-radius: var(--r-pill);
  padding: 3px;
  flex-shrink: 0;
}

.toggle-btn {
  padding: 4px 14px;
  border: none;
  background: transparent;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3);
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1.4;
}

.toggle-btn.active {
  background: var(--paper);
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.selected-title {
  font-size: 20px;
  line-height: 1.4;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.style-anchor-inline {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
  font-size: 13px;
  color: var(--ink-3);
  line-height: 1.6;
}

.content-result-split {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .content-result-split {
    grid-template-columns: 1fr;
  }
}

.result-left,
.result-right {
  min-width: 0;
}

.style-anchor {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--clay-tint);
  border-radius: var(--r-md);
  border-left: 3px solid var(--clay);
}

.anchor-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--clay-deep);
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.anchor-text {
  font-size: 13px;
  color: var(--ink);
  font-style: italic;
}

.content-edit :deep(.el-textarea__inner) {
  font-family: var(--font-serif, inherit);
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink);
  background: var(--paper);
}

.content-preview {
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink);
  min-height: 200px;
}

.content-preview :deep(h2) {
  font-size: 22px;
  font-weight: 600;
  margin: 24px 0 12px;
  color: var(--ink);
}

.content-preview :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  margin: 20px 0 10px;
  color: var(--ink);
}

.content-preview :deep(p) {
  margin-bottom: 14px;
}

/* 高亮：金句（暖色） */
.content-preview :deep(.hl-gold) {
  background: rgba(218, 165, 32, 0.15);
  color: inherit;
  border-bottom: 2px solid var(--sand);
  padding: 1px 2px;
  border-radius: 2px;
  cursor: default;
}

/* 高亮：去AI味改写（冷色） */
.content-preview :deep(.hl-deai) {
  background: rgba(107, 142, 35, 0.12);
  color: inherit;
  border-bottom: 2px solid var(--leaf, #6b8e23);
  padding: 1px 2px;
  border-radius: 2px;
  cursor: default;
}

/* 图例 */
.hl-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}

.hl-legend-item .hl-gold {
  background: rgba(218, 165, 32, 0.15);
  color: var(--ink);
  border-bottom: 2px solid var(--sand);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: default;
}

.hl-legend-item .hl-deai {
  background: rgba(107, 142, 35, 0.12);
  color: var(--ink);
  border-bottom: 2px solid var(--leaf, #6b8e23);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: default;
}

.gold-sentence-row {
  padding: 12px 14px;
  background: var(--ivory, var(--bone));
  border-radius: var(--r-md);
  border-left: 3px solid var(--sand);
}

.gold-type-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--sand);
  color: var(--paper);
  border-radius: var(--r-pill);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  white-space: nowrap;
}

/* 固定底部操作栏 */
.content-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 240px;
  right: 0;
  z-index: 100;
  background: var(--paper);
  border-top: 1px solid var(--line);
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);
  height: 65px;
  display: flex;
  align-items: center;
}

.content-bottom-bar .bottom-bar-inner {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
  width: 100%;
}
</style>

<style>
/* 高亮 Tooltip（挂在 body，不能 scoped） */
.hl-tooltip {
  position: fixed;
  z-index: 9999;
  transform: translate(-50%, -100%);
  background: var(--ink, #2c2c2c);
  border-radius: 8px;
  padding: 6px 12px;
  pointer-events: none;
  white-space: nowrap;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.18);
}

.hl-tooltip::after {
  content: '';
  position: absolute;
  bottom: -5px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid var(--ink, #2c2c2c);
}

.hl-tip-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  line-height: 1.4;
}

.hl-tip-gold {
  background: rgba(218, 165, 32, 0.25);
  color: #f0d060;
}

.hl-tip-deai {
  background: rgba(107, 142, 35, 0.25);
  color: #a0d468;
}

.hl-tip-detail {
  font-size: 12px;
  color: rgba(255,255,255,0.85);
  font-weight: 500;
}
</style>
