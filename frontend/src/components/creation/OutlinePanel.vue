<template>
  <div class="outline-panel">
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
        <el-icon :size="48" style="color: var(--line);"><Document /></el-icon>
      </div>
      <h3 class="text-h4 font-sans text-ink mb-2">开始生成大纲</h3>
      <p class="text-ink-3 mb-6">基于选题信息，AI 将自动生成文章大纲</p>
      <el-button type="primary" size="large" @click="generateOutline" :loading="generating">
        <el-icon><MagicStick /></el-icon>
        生成大纲
      </el-button>
    </div>

    <!-- 生成中 -->
    <div v-if="status === 'generating'" class="text-center py-8">
      <p class="text-ink-3">大纲生成中，请稍候...</p>
    </div>

    <!-- 失败 -->
    <div v-if="status === 'failed'" class="text-center py-16">
      <el-icon :size="48" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4 mb-2">生成失败</h3>
      <p class="text-ink-3 mb-6">{{ errorMessage }}</p>
      <el-button @click="generateOutline">重试</el-button>
    </div>

    <!-- 完成：左右分栏 -->
    <div v-if="status === 'completed' && outline" class="outline-result-split">
      <!-- 左侧：大纲内容 -->
      <div class="result-left">
        <div class="card p-5 mb-4">
          <div class="flex items-center justify-between mb-3 gap-3">
            <h3 class="text-h3 font-sans text-ink flex-1 min-w-0 break-words">{{ outline.title }}</h3>
            <div class="flex items-center gap-3 flex-shrink-0">
              <span :class="outline.passed === 'passed' ? 'badge-success' : 'badge-warning'">
                {{ outline.passed === 'passed' ? '通过' : '未通过' }}
              </span>
              <span class="text-2xl font-bold" :class="getScoreColor(outline.total_score)">
                {{ outline.total_score?.toFixed(1) || '-' }}
              </span>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <div class="flex flex-wrap gap-4 text-sm text-ink-3">
              <span v-if="outline.direction">{{ outline.direction }}</span>
              <span v-if="outline.routine">{{ outline.routine }}</span>
              <span>{{ outline.section_count }} 节</span>
              <span>{{ outline.total_words }} 字</span>
            </div>
            <!-- 视图切换 -->
            <div class="view-toggle">
              <button
                class="toggle-btn"
                :class="{ active: viewMode === 'edit' }"
                @click="viewMode = 'edit'"
              >编辑</button>
              <button
                class="toggle-btn"
                :class="{ active: viewMode === 'preview' }"
                @click="viewMode = 'preview'"
              >预览</button>
            </div>
          </div>
        </div>

        <!-- 编辑模式 -->
        <div v-if="viewMode === 'edit'" class="space-y-3">
          <div
            v-for="(section, idx) in outline.sections"
            :key="section.section_number || idx"
            class="card p-4"
          >
            <div class="flex items-start gap-3">
              <span class="flex-shrink-0 w-7 h-7 rounded-full bg-clay-tint text-clay-deep flex items-center justify-center text-xs font-bold">
                {{ section.section_number || idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <el-input
                  v-model="section.title"
                  class="section-title-input"
                  placeholder="小标题"
                />
                <ul v-if="section.core_points?.length" class="mt-2 space-y-1">
                  <li
                    v-for="(point, pi) in section.core_points"
                    :key="pi"
                    class="text-sm text-ink-3 flex items-start gap-2"
                  >
                    <span class="text-clay mt-1">·</span>
                    <el-input
                      v-model="section.core_points[pi]"
                      class="point-input flex-1"
                      :autosize="{ minRows: 1, maxRows: 3 }"
                      type="textarea"
                      resize="none"
                    />
                  </li>
                </ul>
                <p v-if="section.notes" class="text-xs text-ink-4 mt-2 italic">备注：{{ section.notes }}</p>
              </div>
              <div class="flex flex-col items-end gap-1 flex-shrink-0">
                <span class="text-xs text-ink-4">{{ section.word_count || 0 }} 字</span>
                <el-button link size="small" @click="copySection(section)">
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 预览模式 -->
        <div v-else class="space-y-3">
          <div
            v-for="(section, idx) in outline.sections"
            :key="section.section_number || idx"
            class="preview-section"
          >
            <div class="flex items-start gap-3">
              <span class="flex-shrink-0 w-7 h-7 rounded-full bg-clay-tint text-clay-deep flex items-center justify-center text-xs font-bold">
                {{ section.section_number || idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <h4 class="text-base font-semibold text-ink mb-1">{{ section.title || '未命名小节' }}</h4>
                <ul v-if="section.core_points?.length" class="space-y-1">
                  <li
                    v-for="(point, pi) in section.core_points"
                    :key="pi"
                    class="text-sm text-ink-2 flex items-start gap-2"
                  >
                    <span class="text-clay mt-1">·</span>
                    <span>{{ point }}</span>
                  </li>
                </ul>
                <p v-if="section.notes" class="text-xs text-ink-4 mt-2 italic">备注：{{ section.notes }}</p>
              </div>
              <div class="flex flex-col items-end gap-1 flex-shrink-0">
                <span class="text-xs text-ink-4">{{ section.word_count || 0 }} 字</span>
                <el-button link size="small" @click="copySection(section)">
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 保存按钮（仅编辑模式） -->
        <div v-if="viewMode === 'edit'" class="mt-6 flex justify-center">
          <el-button type="primary" @click="saveOutline" :loading="saving">
            <el-icon><Document /></el-icon>
            保存编辑
          </el-button>
        </div>
      </div>

      <!-- 右侧：Agent 反馈 -->
      <div class="result-right">
        <AgentFeedbackPanel
          :agents="agentFeedback"
          subtitle="大纲流水线：A 起稿 → B 评审挑选 → C 读者挑刺 → D 6 维度自检"
        />
      </div>
    </div>

    <!-- 固定底部操作栏 -->
    <div v-if="status === 'completed' && outline" class="outline-bottom-bar">
      <div class="bottom-bar-inner">
        <el-button @click="generateOutline" :loading="generating">
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
        <el-button :loading="reevaluating" @click="reevaluateOutline">
          <el-icon><Aim /></el-icon>
          重新评估
        </el-button>
        <el-button type="primary" @click="goNextStep">
          下一步
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, MagicStick, CircleCloseFilled, DocumentCopy, Refresh, ArrowRight, Aim } from '@element-plus/icons-vue'
import AgentStatusBar from './AgentStatusBar.vue'
import AgentFeedbackPanel from './AgentFeedbackPanel.vue'
import outlineApi from '@/api/outline'
import { useAgentProgress } from '@/composables/useAgentProgress'

const props = defineProps({
  candidateId: { type: [Number, String], default: null },
  outlineId: { type: [Number, String], default: null },
})

const emit = defineEmits(['complete', 'next-step'])

// 状态
const status = ref('idle') // idle | generating | completed | failed
const generating = ref(false)
const viewMode = ref('preview') // edit | preview
const outline = ref(null)
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
    outline.value = JSON.parse(JSON.stringify(newResult))
    status.value = 'completed'
    emit('complete', newResult)
    ElMessage.success('大纲生成完成')
    generating.value = false
  }
})

// 监听 SSE 错误
watch(() => progress.error.value, (newError) => {
  if (newError) {
    status.value = 'failed'
    errorMessage.value = newError
    generating.value = false
    ElMessage.error('大纲生成失败')
  }
})

// 加载已有大纲
onMounted(async () => {
  if (props.outlineId) {
    try {
      const res = await outlineApi.getOutline(props.outlineId)
      outline.value = JSON.parse(JSON.stringify(res.data))
      status.value = 'completed'
    } catch (e) {
      console.error('加载大纲失败:', e)
    }
  }
})

onUnmounted(() => {
  progress.stop()
  reevaluateProgress.stop()
})

// 生成大纲
const generateOutline = async () => {
  if (!props.candidateId) {
    ElMessage.warning('缺少选题候选 ID')
    return
  }

  status.value = 'generating'
  generating.value = true
  errorMessage.value = ''

  try {
    const res = await outlineApi.generateOutline({
      candidate_id: props.candidateId,
    })

    const runId = res.data.run_id
    if (runId) {
      progress.start(`/api/v1/outlines/stream/${runId}`)
    }
  } catch (error) {
    status.value = 'failed'
    errorMessage.value = error?.response?.data?.detail || error?.message || '生成失败，请重试'
    generating.value = false
    ElMessage.error('大纲生成失败')
  }
}

const getScoreColor = (score) => {
  if (!score) return 'text-ink-3'
  if (score >= 8) return 'text-leaf'
  if (score >= 6) return 'text-sand'
  return 'text-crimson'
}

const copyAllOutline = async () => {
  if (!outline.value) return
  const lines = [outline.value.title || '', '']
  outline.value.sections?.forEach((s, i) => {
    lines.push(`${s.section_number || i + 1}. ${s.title}`)
    s.core_points?.forEach((p) => lines.push(`  · ${p}`))
    if (s.notes) lines.push(`  备注：${s.notes}`)
    lines.push('')
  })
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    ElMessage.success('已复制完整大纲')
  } catch {
    ElMessage.error('复制失败')
  }
}

const copySection = async (section) => {
  const lines = [`${section.section_number}. ${section.title}`]
  section.core_points?.forEach((p) => lines.push(`  · ${p}`))
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    ElMessage.success('已复制本节')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 保存编辑后的大纲
const saveOutline = async () => {
  if (!outline.value?.id) return
  saving.value = true
  try {
    await outlineApi.updateOutline(outline.value.id, {
      title: outline.value.title,
      sections: outline.value.sections,
    })
    ElMessage.success('大纲已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// 下一步
const goNextStep = () => {
  emit('next-step')
}

// 重新评估大纲（只跑 B→C→D）
const reevaluateProgress = useAgentProgress()
const reevaluateOutline = async () => {
  if (!outline.value?.id) return
  reevaluating.value = true
  try {
    const res = await outlineApi.reevaluateOutline(outline.value.id)
    const runId = res.data.run_id
    if (runId) {
      // 用新的 SSE 连接获取重新评估结果
      reevaluateProgress.start(`/api/v1/outlines/stream/${runId}`)
    }
  } catch (e) {
    reevaluating.value = false
    ElMessage.error('重新评估请求失败')
  }
}

// 监听重新评估结果
watch(() => reevaluateProgress.result.value, (newResult) => {
  if (newResult) {
    outline.value = JSON.parse(JSON.stringify(newResult))
    emit('complete', newResult)
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
const D_DIM_LABELS = {
  hook: { label: '开头钩子强度', weight: 20 },
  value_ladder: { label: '价值阶梯递进', weight: 20 },
  rhythm: { label: '节奏感', weight: 15 },
  title_scan: { label: '小标题扫读友好度', weight: 15 },
  trigger: { label: '传播触发点完整度', weight: 20 },
  length: { label: '长度与节数匹配', weight: 10 },
}

const agentFeedback = computed(() => {
  const o = outline.value
  if (!o) return []

  const gp = o.generation_process || {}
  const insp = o.inspection_score || {}
  const reviewObj = o.review || {}
  const criticismObj = o.criticism || {}
  const inspectionObj = o.inspection || {}

  // Agent A
  const agentA = {
    id: 'A',
    code: 'A',
    name: '顾清和 · 大纲创作员',
    role: '生成 3 个大纲候选骨架',
    avatar: '/agents/outline-a.png',
    summary: gp.selected_candidate
      ? `共生成 ${gp.attempts || 1} 轮候选；最终选用候选 #${gp.selected_candidate}。`
      : `共尝试 ${gp.attempts || 1} 轮。`,
  }
  if (o.candidates && o.candidates.length) {
    agentA.issues = o.candidates.map((c) => ({
      location: `候选 #${c.candidate_number} · ${c.hook_type || ''}`,
      text: `${c.skeleton_feature || ''} · ${c.total_words || 0} 字 · ${c.sections?.length || 0} 节`,
    }))
  }

  // Agent B 评审
  const agentB = {
    id: 'B',
    code: 'B',
    name: '陆言之 · 大纲评审员',
    role: '从候选骨架里挑选最佳并补传播标签',
    avatar: '/agents/outline-b.png',
    summary: gp.review_reason || reviewObj.review_reason || '',
  }
  if (reviewObj.selected_candidate) {
    agentB.summary = `选中候选 #${reviewObj.selected_candidate}。${reviewObj.review_reason || ''}`
  }

  // Agent C 挑刺
  const agentC = {
    id: 'C',
    code: 'C',
    name: '刁亦凡 · 大纲挑刺员',
    role: '模拟读者立场指出大纲不顺畅之处',
    avatar: '/agents/outline-c.png',
    summary: criticismObj.overall_feeling || gp.criticism || '',
  }
  const problemSections =
    criticismObj.problem_sections || gp.problem_sections || []
  if (Array.isArray(problemSections) && problemSections.length) {
    agentC.issues = problemSections.map((p) => ({
      location:
        typeof p === 'object'
          ? `第 ${p.section_number || '?'} 节 · ${p.title || ''}`
          : '',
      text:
        typeof p === 'object'
          ? p.problem || p.reason || p.description || JSON.stringify(p)
          : String(p),
    }))
  }

  // Agent D 6 维度自检
  const agentD = {
    id: 'D',
    code: 'D',
    name: '简行舟 · 大纲自检员',
    role: '6 维度评分 + 通过/打回判定',
    avatar: '/agents/outline-d.png',
    score: o.total_score ?? inspectionObj.total_score,
    verdict: (o.passed || inspectionObj.verdict) === 'passed' ? '通过' : '未通过',
    verdictPassed: (o.passed || inspectionObj.verdict) === 'passed',
  }
  const dims = []
  Object.entries(D_DIM_LABELS).forEach(([key, conf]) => {
    const dim = insp[key]
    const direct = inspectionObj[`${key}_score`]
    if (dim) {
      dims.push({
        key,
        label: conf.label,
        weight: conf.weight,
        score: dim.score ?? dim.total ?? dim,
        evaluation: dim.evaluation || dim.reason || '',
        suggestions: dim.suggestions || [],
      })
    } else if (typeof direct === 'number') {
      dims.push({ key, label: conf.label, weight: conf.weight, score: direct })
    }
  })
  if (dims.length) agentD.dimensions = dims

  const deductions = inspectionObj.deduction_reasons || []
  if (Array.isArray(deductions) && deductions.length) {
    agentD.issues = deductions.map((d) =>
      typeof d === 'object'
        ? { location: d.dimension || '', text: d.reason || JSON.stringify(d) }
        : { text: String(d) }
    )
  }

  return [agentA, agentB, agentC, agentD]
})
</script>

<style scoped>
.outline-result-split {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .outline-result-split {
    grid-template-columns: 1fr;
  }
}

.result-left,
.result-right {
  min-width: 0;
}

.section-title-input :deep(.el-input__wrapper) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
}

.section-title-input :deep(.el-input__inner) {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.section-title-input :deep(.el-input__inner:focus) {
  border-bottom: 1px dashed var(--clay-soft);
}

.point-input :deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.5;
}

.point-input :deep(.el-textarea__inner:focus) {
  border-bottom: 1px dashed var(--clay-soft);
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

/* 预览模式 */
.preview-section {
  padding: 16px 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  transition: box-shadow 0.2s ease;
}

.preview-section:hover {
  box-shadow: var(--sh-1);
}

/* 固定底部操作栏 */
.outline-bottom-bar {
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

.bottom-bar-inner {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
  width: 100%;
}

.badge-warning {
  background: rgba(200, 145, 60, 0.12);
  color: var(--sand);
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
}
</style>
