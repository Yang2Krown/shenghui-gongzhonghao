<template>
  <div class="title-panel">
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
        <el-icon :size="48" style="color: var(--line);"><MagicStick /></el-icon>
      </div>
      <h3 class="text-h4 font-sans text-ink mb-2">生成标题</h3>
      <p class="text-ink-3 mb-6">基于大纲，AI 将生成多个标题候选并推荐 Top 3</p>
      <el-button type="primary" size="large" @click="generateTitles" :loading="generating">
        <el-icon><MagicStick /></el-icon>
        生成标题
      </el-button>
    </div>

    <!-- 生成中 -->
    <div v-if="status === 'generating'" class="text-center py-8">
      <p class="text-ink-3">标题生成中，请稍候...</p>
    </div>

    <!-- 失败 -->
    <div v-if="status === 'failed'" class="text-center py-16">
      <el-icon :size="48" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4 mb-2">生成失败</h3>
      <p class="text-ink-3 mb-6">{{ errorMessage }}</p>
      <el-button @click="generateTitles">重试</el-button>
    </div>

    <!-- 完成：标题结果展示（左右分栏） -->
    <div v-if="status === 'completed' && titles.length" class="title-result-split">
      <!-- 左侧：标题候选 -->
      <div class="result-left">
        <div class="left-header">
          <div class="flex items-center gap-4">
            <h3 class="text-h4 font-sans text-ink">推荐标题 Top {{ titles.length }}</h3>
            <span v-if="meta" class="text-xs text-ink-3">
              候选 {{ meta.total_candidates || titles.length }} · 套路 {{ meta.covered_methods || '-' }} · 重生 {{ meta.regeneration_count || 0 }} 次
            </span>
          </div>
          <div class="view-toggle">
            <button class="toggle-btn" :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
            <button class="toggle-btn" :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
          </div>
        </div>
        <div class="space-y-4">
          <div
            v-for="(title, i) in titles"
            :key="i"
            class="title-card"
            :class="{ 'title-card-selected': selectedIndex === i }"
            @click="selectTitle(i)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-2">
                  <span class="rank-badge" :class="i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : 'rank-3'">
                    TOP {{ i + 1 }}
                  </span>
                  <span class="text-xs text-ink-3">{{ title.method }}</span>
                  <span class="text-xs text-ink-3">·</span>
                  <span class="text-xs text-ink-3">{{ (title.editable_title || title.title).length }} 字</span>
                </div>
                <!-- 编辑模式 -->
                <el-input
                  v-if="viewMode === 'edit'"
                  v-model="title.editable_title"
                  type="textarea"
                  :autosize="{ minRows: 1, maxRows: 3 }"
                  class="title-edit-input"
                  resize="none"
                  @click.stop
                />
                <!-- 预览模式 -->
                <p v-else class="text-base font-semibold text-ink">{{ title.editable_title || title.title }}</p>
                <p v-if="title.reason" class="text-sm text-ink-3 mt-2">{{ title.reason }}</p>
              </div>
              <div class="ml-2 text-right flex-shrink-0 flex flex-col items-end gap-1">
                <div class="text-2xl font-bold" :class="getScoreColor(title.score || title.final_score)">
                  {{ ((title.score || title.final_score) ?? 0).toFixed(1) }}
                </div>
                <div class="text-xs text-ink-3">综合评分</div>
                <div class="flex items-center gap-1">
                  <el-button
                    size="small"
                    link
                    @click.stop="copyTitle(title.editable_title || title.title)"
                  >
                    <el-icon><DocumentCopy /></el-icon>
                  </el-button>
                  <el-button
                    v-if="viewMode === 'edit'"
                    size="small"
                    link
                    :loading="title._saving"
                    @click.stop="saveTitle(title, i)"
                  >
                    <el-icon><Document /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：Agent 反馈 -->
      <div class="result-right">
        <AgentFeedbackPanel :agents="agentFeedback" subtitle="标题流水线：A 创作 → B 评分 → C 点击预测 → D 综合判定 Top 5" />
      </div>
    </div>

    <!-- 固定底部操作栏 -->
    <div v-if="status === 'completed' && titles.length" class="title-bottom-bar">
      <div class="bottom-bar-inner">
        <el-button @click="generateTitles" :loading="generating">
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
        <el-button :loading="reevaluating" :disabled="selectedIndex === null" @click="reevaluateTitle">
          <el-icon><Aim /></el-icon>
          重新评估
        </el-button>
        <el-button type="primary" @click="confirmTitle" :disabled="selectedIndex === null">
          确认标题
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, CircleCloseFilled, DocumentCopy, Document, Refresh, ArrowRight, Aim } from '@element-plus/icons-vue'
import AgentStatusBar from './AgentStatusBar.vue'
import AgentFeedbackPanel from './AgentFeedbackPanel.vue'
import { get, post } from '@/api/api'
import { updateTitleCandidate, reevaluateTitleCandidate } from '@/api/creation'
import { useAgentProgress } from '@/composables/useAgentProgress'

const props = defineProps({
  candidateId: { type: [Number, String], default: null },
  outlineData: { type: Object, default: null },
})

const emit = defineEmits(['complete', 'next-step'])

// 状态
const status = ref('idle')
const generating = ref(false)
const viewMode = ref('preview') // edit | preview
const titles = ref([])
const candidatesAll = ref([])
const meta = ref(null)
const selectedIndex = ref(null)
const errorMessage = ref('')
const reevaluating = ref(false)

// Agent 进度（SSE 驱动）
const progress = useAgentProgress()
const agentSteps = progress.steps
const currentStepIndex = progress.currentStepIndex
const stepPercent = progress.stepPercent

// 监听 SSE 结果
watch(() => progress.result.value, (newResult) => {
  if (newResult) {
    candidatesAll.value = newResult.candidates || []
    meta.value = newResult.meta || null
    // 从 candidatesAll 中取 top 5 展示
    const allCands = candidatesAll.value
    const top5 = allCands.filter((c) => c.is_top5)
    const recommendations = newResult.recommendations || newResult.titles || []
    // 合并：top5 优先，不足则用 recommendations 补
    const source = top5.length >= 3 ? top5 : recommendations
    titles.value = source.slice(0, 5).map((t) => ({
      ...t,
      editable_title: t.title,
    }))
    status.value = 'completed'
    selectedIndex.value = 0
    ElMessage.success('标题生成完成')
    generating.value = false
  }
})

// 监听 SSE 错误
watch(() => progress.error.value, (newError) => {
  if (newError) {
    status.value = 'failed'
    errorMessage.value = newError
    generating.value = false
    ElMessage.error('标题生成失败')
  }
})

onUnmounted(() => {
  progress.stop()
  reevaluateProgress.stop()
})

const generateTitles = async () => {
  if (!props.candidateId) {
    ElMessage.warning('缺少选题候选 ID')
    return
  }
  if (!props.outlineData) {
    ElMessage.warning('请先完成大纲生成')
    return
  }

  status.value = 'generating'
  generating.value = true
  errorMessage.value = ''
  selectedIndex.value = null

  try {
    const candidateRes = await get(`/topic-candidates/${props.candidateId}`)
    const candidate = candidateRes.data?.data || candidateRes.data || candidateRes

    const outline = props.outlineData
    const sections = Array.isArray(outline?.sections) ? outline.sections : []
    const sectionTitles = sections.map((s) => s?.title).filter(Boolean)
    const keyPoints = sections.flatMap((s) => s?.core_points || s?.key_points || [])

    const payload = {
      topic: {
        title: candidate?.title || '',
        direction: candidate?.direction || '',
        method: candidate?.routine || candidate?.method || '',
        value_promise: candidate?.value_promise || '',
      },
      outline: {
        section_titles: sectionTitles,
        key_points: keyPoints,
        spread_tags: outline?.spread_tags || [],
      },
    }

    const res = await post('/title-generation/', payload)

    const runId = res.data.run_id
    if (runId) {
      // SSE 模式：连接进度流
      progress.start(`/api/v1/title-generation/stream/${runId}`)
    }
  } catch (error) {
    status.value = 'failed'
    errorMessage.value = error?.response?.data?.detail || error?.message || '生成失败'
    generating.value = false
    ElMessage.error('标题生成失败')
  }
}

const selectTitle = (index) => {
  selectedIndex.value = index
}

const confirmTitle = () => {
  if (selectedIndex.value !== null) {
    const chosen = titles.value[selectedIndex.value]
    emit('complete', { ...chosen, title: chosen.editable_title || chosen.title })
    emit('next-step')
    ElMessage.success('标题已确认')
  }
}

const copyTitle = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

const getScoreColor = (score) => {
  if (!score) return 'text-ink-3'
  if (score >= 8) return 'text-leaf'
  if (score >= 6) return 'text-sand'
  return 'text-crimson'
}

// 保存单个标题候选
const saveTitle = async (title, index) => {
  if (!title.id) {
    ElMessage.warning('该标题无 ID，无法保存')
    return
  }
  title._saving = true
  try {
    await updateTitleCandidate(title.id, {
      title: title.editable_title || title.title,
    })
    ElMessage.success('标题已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    title._saving = false
  }
}

// 重新评估选中的标题（只跑 B+C）
const reevaluateProgress = useAgentProgress()
const reevaluateTitle = async () => {
  if (selectedIndex.value === null) return
  const title = titles.value[selectedIndex.value]
  if (!title?.id) {
    ElMessage.warning('该标题无 ID，无法重新评估')
    return
  }
  reevaluating.value = true
  try {
    const res = await reevaluateTitleCandidate(title.id)
    const runId = res.data.run_id
    if (runId) {
      reevaluateProgress.start(`/api/v1/title-generation/stream/${runId}`)
    }
  } catch (e) {
    reevaluating.value = false
    ElMessage.error('重新评估请求失败')
  }
}

// 监听重新评估结果
watch(() => reevaluateProgress.result.value, (newResult) => {
  if (newResult) {
    // 更新对应候选的评分
    const updated = newResult
    const idx = titles.value.findIndex(t => t.id === updated.id)
    if (idx !== -1) {
      titles.value[idx] = { ...titles.value[idx], ...updated, editable_title: updated.title }
    }
    // 同步更新 candidatesAll
    const cIdx = candidatesAll.value.findIndex(c => c.id === updated.id)
    if (cIdx !== -1) {
      candidatesAll.value[cIdx] = { ...candidatesAll.value[cIdx], ...updated }
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

// ── Agent 反馈数据组装 ────────────────────────────
const B_DIMENSIONS = [
  { key: 'three_eyes', label: '三个一眼达标度', weight: 0.25 },
  { key: 'emotion_trigger', label: '情绪触发力度', weight: 0.20 },
  { key: 'specificity', label: '具体性', weight: 0.15 },
  { key: 'length_compliance', label: '长度合规', weight: 0.10 },
  { key: 'method_maturity', label: '套路成熟度', weight: 0.15 },
  { key: 'outline_consistency', label: '与大纲一致性', weight: 0.15 },
]

const agentFeedback = computed(() => {
  if (!candidatesAll.value.length && !titles.value.length) return []

  const cands = candidatesAll.value
  const eliminated = cands.filter((c) => c.is_eliminated)

  // 当前选中的标题
  const selected = selectedIndex.value !== null ? titles.value[selectedIndex.value] : null
  // 从 candidatesAll 找完整数据（含 b_score_details 等）
  const sel = selected ? cands.find((c) => c.id === selected.id) || selected : null

  // Agent A 概览（全局）
  const agentA = {
    id: 'A',
    code: 'A',
    name: '甄意浓 · 标题创作员',
    role: '生成多套路标题候选',
    avatar: '/agents/title-a.png',
    summary: meta.value
      ? `共生成 ${meta.value.total_candidates ?? cands.length} 个候选，覆盖 ${meta.value.covered_methods ?? '-'} 种套路；一票否决淘汰 ${meta.value.eliminated_count ?? eliminated.length} 个；重生 ${meta.value.regeneration_count ?? 0} 次。`
      : `共 ${cands.length} 个候选`,
    issuesLabel: '淘汰原因',
    issues: eliminated.map((c) => ({
      location: c.title,
      text: c.elimination_reason || '被一票否决',
    })),
  }

  // Agent B 评分（仅选中标题的 6 维度）
  const agentB = {
    id: 'B',
    code: 'B',
    name: '尚怀瑾 · 标题评审员',
    role: '6 维度评分 + 一票否决扫描',
    avatar: '/agents/title-b.png',
    score: sel?.b_score ?? null,
    summary: sel ? `「${sel.title}」综合评分 ${(sel.b_score ?? 0).toFixed(1)}/10` : '请点击左侧标题查看评分',
  }
  if (sel) {
    const details = sel.b_score_details || {}
    agentB.dimensions = B_DIMENSIONS.map((d) => ({
      label: d.label,
      score: details[d.key] ?? 0,
      max: 10,
    }))
  }

  // Agent C 点击预测（仅选中标题）
  const agentC = {
    id: 'C',
    code: 'C',
    name: '于思齐 · 标题预测员',
    role: '模拟真实读者的点击意愿',
    avatar: '/agents/title-c.png',
    score: sel?.c_click_willingness ?? null,
    summary: sel
      ? `「${sel.title}」点击意愿 ${(sel.c_click_willingness ?? 0).toFixed(1)}/10`
      : '请点击左侧标题查看预测',
  }
  if (sel) {
    agentC.issues = [
      sel.c_click_reason ? { location: '吸引点', text: sel.c_click_reason } : null,
      sel.c_no_click_reason ? { location: '顾虑点', text: sel.c_no_click_reason } : null,
      sel.c_improvement_suggestion ? { location: '改进建议', text: sel.c_improvement_suggestion } : null,
    ].filter(Boolean)
  }

  // Agent D 综合判定（仅选中标题）
  const agentD = {
    id: 'D',
    code: 'D',
    name: '丁既明 · 标题判定员',
    role: '加权综合评分，输出 Top 5',
    avatar: '/agents/title-d.png',
    score: sel?.final_score ?? null,
    verdict: sel?.is_top3 ? 'Top 3' : sel?.is_top5 ? 'Top 5' : null,
    verdictPassed: !!sel?.is_top3 || !!sel?.is_top5,
    summary: sel
      ? `综合 ${(sel.final_score ?? 0).toFixed(2)} = B ${(sel.b_score ?? 0).toFixed(1)} × 60% + C ${(sel.c_click_willingness ?? 0).toFixed(1)} × 40%`
      : '',
  }

  return [agentA, agentB, agentC, agentD]
})
</script>

<style scoped>
.title-result-split {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .title-result-split {
    grid-template-columns: 1fr;
  }
}

.result-left,
.result-right {
  min-width: 0;
}

.left-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.title-card:hover {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-2);
}

.title-card-selected {
  border-color: var(--clay);
  box-shadow: var(--sh-clay);
  background: var(--clay-tint);
}

.title-edit-input :deep(.el-textarea__inner) {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  background: transparent;
  border: none;
  padding: 0;
  box-shadow: none;
  line-height: 1.5;
}

.title-edit-input :deep(.el-textarea__inner:focus) {
  border-bottom: 1px dashed var(--clay-soft);
}

.rank-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: 11px;
  font-weight: 700;
}

.rank-1 {
  background: var(--clay);
  color: var(--paper);
}

.rank-2 {
  background: var(--sand);
  color: var(--paper);
}

.rank-3 {
  background: var(--pine-soft);
  color: var(--pine);
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

/* 固定底部操作栏 */
.title-bottom-bar {
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

.title-bottom-bar .bottom-bar-inner {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
  width: 100%;
}
</style>
