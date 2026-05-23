<template>
  <div class="creation-draft">
    <!-- 顶部：返回 + 操作 -->
    <header class="draft-header mb-6">
      <div class="flex items-center justify-between">
        <div>
          <el-button text @click="router.push('/creation')" class="text-ink-3">
            <el-icon><ArrowLeft /></el-icon>
            返回创作列表
          </el-button>
          <h1 class="text-h2 font-serif text-ink mt-2">
            {{ creation.title || '无标题' }}
          </h1>
          <div class="flex items-center gap-3 mt-2">
            <span :class="['c-status', `c-status-${creation.status || 'draft'}`]">
              {{ getStatusName(creation.status) }}
            </span>
            <span class="text-sm text-ink-3">
              {{ creation.word_count || 0 }} 字 · 更新于 {{ formatDate(creation.updated_at) }}
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <el-button @click="saveDraft" :loading="saving">
            <el-icon><Document /></el-icon>
            保存
          </el-button>
        </div>
      </div>
    </header>

    <!-- 溯源链接 -->
    <div v-if="creation.cluster_id || creation.candidate_id" class="traceback-bar mb-5">
      <span class="traceback-label">溯源：</span>
      <el-button
        v-if="creation.cluster_id"
        size="small"
        link
        type="primary"
        @click="router.push(`/topic-clusters/${creation.cluster_id}`)"
      >
        <el-icon><Connection /></el-icon>
        话题簇 #{{ creation.cluster_id }}
      </el-button>
      <el-button
        v-if="creation.candidate_id"
        size="small"
        link
        type="primary"
        @click="router.push(`/topic-clusters/${creation.cluster_id || ''}`)"
      >
        <el-icon><Tickets /></el-icon>
        选题候选 #{{ creation.candidate_id }}
      </el-button>
      <span v-if="creation.topic_title" class="text-sm text-ink-3 ml-2">
        「{{ creation.topic_title }}」
      </span>
    </div>

    <!-- 主体：左右分栏 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <div v-else-if="!creation.id" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">创作不存在</h3>
      <el-button type="primary" class="mt-4" @click="router.push('/creation')">返回列表</el-button>
    </div>

    <div v-else class="draft-split">
      <!-- 左侧：正文 -->
      <div class="draft-left">
        <!-- 风格锚点 -->
        <div v-if="creation.style_anchor" class="style-anchor mb-4">
          <span class="anchor-label">风格锚点</span>
          <span class="anchor-text">{{ creation.style_anchor }}</span>
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
          <div v-else class="content-preview prose" v-html="renderedHtml" />
        </div>
      </div>

      <!-- 右侧：Agent 反馈（已存档的快照数据） -->
      <div class="draft-right">
        <div class="draft-badge">
          <el-icon :size="12"><Clock /></el-icon>
          存档快照
        </div>
        <AgentFeedbackPanel
          :agents="agentFeedback"
          subtitle="已存档的创作流水线数据 · 点击评估打分可更新诊断"
        />
      </div>
    </div>

    <!-- Agent 评估进度 -->
    <div v-if="reevaluating" class="mb-6">
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

    <!-- 固定底部操作栏 -->
    <div v-if="creation.id" class="draft-bottom-bar">
      <div class="bottom-bar-inner">
        <el-button @click="saveDraft" :loading="saving">
          <el-icon><Document /></el-icon>
          保存草稿
        </el-button>
        <el-button @click="reevaluateContent" :loading="reevaluating">
          <el-icon><Aim /></el-icon>
          评估打分
          <el-icon class="el-icon--right"><Refresh /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Document, DocumentCopy, Edit,
  Connection, Tickets, Loading, Refresh, Aim, Clock
} from '@element-plus/icons-vue'
import AgentFeedbackPanel from '@/components/creation/AgentFeedbackPanel.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useCreationStore } from '@/stores/creation'
import { useAgentProgress } from '@/composables/useAgentProgress'
import { reevaluateContent as reevaluateContentApi } from '@/api/creation'

const route = useRoute()
const router = useRouter()
const creationStore = useCreationStore()

// 状态
const loading = ref(false)
const saving = ref(false)
const reevaluating = ref(false)
const creation = ref({})
const editableText = ref('')
const viewMode = ref('preview')

// Agent 进度（SSE 驱动）
const progress = useAgentProgress()
const agentSteps = progress.steps
const currentStepIndex = progress.currentStepIndex
const stepPercent = progress.stepPercent

// 加载创作数据
onMounted(async () => {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    const data = await creationStore.fetchCreationById(id)
    creation.value = data || {}
    // 尝试解析 JSON 内容（包含 agent 数据），否则按纯文本
    const raw = data?.content || ''
    let text = raw
    if (raw && raw !== 'null') {
      try {
        const parsed = JSON.parse(raw)
        if (typeof parsed === 'object' && parsed && parsed.final_text) {
          text = parsed.final_text
          // 将 agent 数据合并到 creation 用于 agentFeedback
          creation.value = { ...creation.value, ...parsed }
        }
      } catch {}
    }
    editableText.value = text
  } catch (e) {
    console.error('加载创作失败:', e)
  } finally {
    loading.value = false
  }
})

// 保存草稿（存为 JSON，保留 agent 数据）
const saveDraft = async () => {
  if (!creation.value.id) return
  saving.value = true
  try {
    // 重建完整内容对象：保留 agent 数据，更新编辑后的文本
    const contentObj = {
      final_text: editableText.value,
      final_word_count: editableText.value.length,
      style_anchor: creation.value.style_anchor,
      gold_sentences: creation.value.gold_sentences,
      rewrite_table: creation.value.rewrite_table,
      diagnosis: creation.value.diagnosis,
      section_count: creation.value.section_count,
      rewrite_count: creation.value.rewrite_count,
    }
    const plain = editableText.value.replace(/[#*`>_~\-]/g, '').trim()
    const summary = plain.slice(0, 120)
    await creationStore.updateCreation(creation.value.id, {
      content: JSON.stringify(contentObj),
      summary: summary || null,
      word_count: editableText.value.length,
    })
    // 同步本地状态
    creation.value.content = JSON.stringify(contentObj)
    creation.value.final_text = contentObj.final_text
    creation.value.word_count = editableText.value.length
  } catch (e) {
    console.error('保存失败:', e)
  } finally {
    saving.value = false
  }
}

// 评估打分（调用 Agent D 重新诊断）
const reevaluateContent = async () => {
  if (!editableText.value) {
    ElMessage.warning('正文为空，无法评估')
    return
  }
  reevaluating.value = true
  try {
    const goldSentences = (creation.value.gold_sentences || []).map(g => ({
      sentence_type: g.sentence_type || g.sentenceType,
      location: g.location,
      section_number: g.section_number || 1,
      content: g.content,
    }))
    const res = await reevaluateContentApi({
      text: editableText.value,
      title: creation.value.topic_title || creation.value.title || '',
      style_anchor: creation.value.style_anchor || '',
      sections: [],
      gold_sentences: goldSentences,
    })
    const runId = res.data.run_id
    if (runId) {
      progress.start(`/api/v1/content-generation/stream/${runId}`)
    }
  } catch (e) {
    reevaluating.value = false
    ElMessage.error('评估请求失败')
  }
}

// 监听评估结果
watch(() => progress.result.value, (newResult) => {
  if (newResult) {
    creation.value.diagnosis = newResult
    ElMessage.success('评估完成')
    reevaluating.value = false
  }
})

watch(() => progress.error.value, (newError) => {
  if (newError) {
    ElMessage.error(`评估失败: ${newError}`)
    reevaluating.value = false
  }
})

onUnmounted(() => {
  progress.stop()
})

// 复制正文
const copyText = async () => {
  try {
    await navigator.clipboard.writeText(editableText.value)
    ElMessage.success('正文已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 正文渲染
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
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

// ── Agent 反馈数据（从已保存的 content 重建） ────────────
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
  const c = creation.value
  if (!c.id) return []

  // Agent A · 正文撰写员（存档快照）
  const agentA = {
    id: 'A',
    code: 'A',
    name: '温如言 · 正文创作员',
    role: '定风格锚点 + 分节铺陈',
    avatar: '/agents/content-a.png',
    summary: c.style_anchor
      ? `风格锚点：${c.style_anchor}`
      : '（存档中无风格锚点记录，仅为正文文本快照）',
  }

  // Agent B · 金句催化员（存档快照）
  const gold = c.gold_sentences || []
  const agentB = {
    id: 'B',
    code: 'B',
    name: '居怀金 · 正文催化员',
    role: '注入 3-5 个高传播金句',
    avatar: '/agents/content-b.png',
    summary: gold.length
      ? `存档快照：共 ${gold.length} 个金句，类型 ${[...new Set(gold.map((g) => g.sentence_type))].length} 种。`
      : '（存档中无金句数据）',
    issues: gold.length
      ? gold.map((g) => ({
          location: `${g.location} · ${g.sentence_type}`,
          text: g.content,
        }))
      : [{ location: '记录', text: '此创作在存档时未包含金句数据' }],
  }

  // Agent C · 去 AI 味改写员（存档快照）
  const rewrites = c.rewrite_table || []
  const agentC = {
    id: 'C',
    code: 'C',
    name: '景澄之 · 正文改写员',
    role: '扫描 6 类 AI 味并按优先级改写',
    avatar: '/agents/content-c.png',
    summary: rewrites.length
      ? `存档快照：共改写 ${rewrites.length} 处。`
      : c.rewrite_count
        ? `存档记录：共改写 ${c.rewrite_count} 处（明细未存档）。`
        : '（存档中无改写数据）',
    issues: rewrites.length
      ? rewrites.slice(0, 20).map((r) => ({
          location: `${r.location} · ${r.ai_taste_subtype || r.ai_taste_type}`,
          text: `${r.priority ? r.priority + ' ' : ''}${r.reason || ''}`,
        }))
      : [{ location: '记录', text: '此创作在存档时未包含改写明细' }],
  }

  // Agent D · 8 维度自检诊断员（可能由存档提供或评估打分更新）
  const diag = c.diagnosis || {}
  const dims = diag.dimensions || {}
  const hasDiagnosis = diag.total_score !== undefined && diag.total_score !== null
  const agentD = {
    id: 'D',
    code: 'D',
    name: '钟可期 · 正文诊断员',
    role: '8 维度评分 + 三档修改建议',
    avatar: '/agents/content-d.png',
    score: diag.total_score,
    verdict: diag.recommended_action,
    verdictPassed: diag.recommended_action === '接受发布',
    summary: hasDiagnosis
      ? `建议处理路径：${diag.recommended_action}`
      : '尚未评估 · 点击底部"评估打分"按钮运行 8 维度诊断',
    dimensions: hasDiagnosis
      ? Object.entries(D_DIM_LABELS)
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
          .filter(Boolean)
      : [],
    priorities: hasDiagnosis
      ? {
          high: diag.high_priority || [],
          medium: diag.medium_priority || [],
          low: diag.low_priority || [],
        }
      : { high: [], medium: [], low: [] },
  }

  return [agentA, agentB, agentC, agentD]
})

// 工具函数
const getStatusName = (status) => {
  const map = { draft: '草稿', published: '已发布', archived: '已归档' }
  return map[status] || status
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diff = Math.abs(now - date)
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
  if (days === 1) return '今天'
  if (days === 2) return '昨天'
  if (days <= 7) return `${days - 1}天前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.draft-header {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

/* 溯源栏 */
.traceback-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--ivory);
  border-radius: var(--r-md);
  border: 1px solid var(--line);
}

.traceback-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-3);
  flex-shrink: 0;
}

/* 左右分栏 */
.draft-split {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .draft-split {
    grid-template-columns: 1fr;
  }
}

.draft-left,
.draft-right {
  min-width: 0;
}

/* 存档快照徽标 */
.draft-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 10px;
  padding: 3px 10px;
  background: var(--bone);
  color: var(--ink-3);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

/* 风格锚点（草稿页——哑光版本） */
.style-anchor {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bone);
  border-radius: var(--r-md);
  border-left: 3px solid var(--ink-4);
  opacity: 0.85;
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

/* 正文编辑/预览 */
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

/* 视图切换 */
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

/* 状态徽标 */
.c-status {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.c-status-draft {
  background: var(--bone);
  color: #6B6862;
  border: 1px solid var(--line);
}

.c-status-published {
  background: #DAF0DC;
  color: #2A6B3A;
  border: 1px solid #A8D6B0;
}

.c-status-archived {
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}

/* 固定底部操作栏 */
.draft-bottom-bar {
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

.draft-bottom-bar .bottom-bar-inner {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
  width: 100%;
}
</style>
