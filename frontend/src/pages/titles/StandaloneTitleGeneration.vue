<template>
  <div class="standalone-workspace">
    <!-- 页头 -->
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">智能起标题</h1>
      <p class="text-sm text-ink-3 mt-1">基于 4 Agent 协作流水线（A创作 → B评分 → C点击预测 → D综合判定），从文章内容直接生成高质量标题</p>
    </header>

    <!-- 进度条 -->
    <div class="card p-4 mb-6" v-if="status !== 'idle'">
      <div class="flex items-center gap-4 flex-wrap">
        <div
          v-for="(step, i) in workflowSteps"
          :key="i"
          class="flex items-center gap-2"
        >
          <div
            class="step-indicator"
            :class="{
              'step-done': getStepStatus(i) === 'done',
              'step-active': getStepStatus(i) === 'active',
              'step-pending': getStepStatus(i) === 'pending',
            }"
          >
            <el-icon v-if="getStepStatus(i) === 'done'" :size="14"><Check /></el-icon>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span class="text-sm" :class="getStepStatus(i) === 'done' ? 'text-ink font-medium' : 'text-ink-3'">
            {{ step.name }}
          </span>
          <el-icon v-if="i < workflowSteps.length - 1" class="text-ink-4 mx-1"><ArrowRight /></el-icon>
        </div>
      </div>
      <div class="mt-3">
        <div class="overall-track">
          <div class="overall-fill" :style="{ width: progress.overallPercent.value + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- Agent 状态 -->
    <div v-if="generating" class="mb-6">
      <AgentStatusBar
        v-for="(step, i) in progress.steps.value"
        :key="i"
        :agent-name="step.agent"
        :action="step.action"
        :avatar="step.avatar"
        :is-active="i === progress.currentStepIndex.value"
        :show-progress="i === progress.currentStepIndex.value"
        :percent="i === progress.currentStepIndex.value ? progress.stepPercent.value : (i < progress.currentStepIndex.value ? 100 : 0)"
        class="mb-2"
      />
    </div>

    <!-- 输入区 -->
    <div v-if="status === 'idle'" class="card p-6 mb-6">
      <h3 class="text-h4 font-sans text-ink mb-4">输入文章内容</h3>
      <div class="mb-4">
        <label class="label">文章全文 / 内容摘要</label>
        <el-input
          v-model="content"
          type="textarea"
          placeholder="请输入文章全文或详细内容摘要，系统会自动分析选题和大纲，然后生成多个标题候选..."
          :autosize="{ minRows: 6, maxRows: 16 }"
          resize="none"
        />
      </div>
      <el-button type="primary" size="large" @click="generate" :loading="generating">
        生成标题
      </el-button>
    </div>

    <!-- 生成中占位 -->
    <div v-if="status === 'generating' && !result" class="card p-6 text-center py-16">
      <p class="text-ink-3">标题生成中，请稍候...</p>
    </div>

    <!-- 错误 -->
    <div v-if="status === 'failed'" class="card p-6 text-center py-16 mb-6">
      <el-icon :size="48" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4 mb-2">生成失败</h3>
      <p class="text-ink-3 mb-6">{{ errorMessage }}</p>
      <el-button @click="reset">重新输入</el-button>
    </div>

    <!-- 结果展示 -->
    <div v-if="result" class="result-area">
      <!-- 提取的选题信息 -->
      <div v-if="result.extracted_topic" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-3">选题分析</h3>
        <div class="extracted-info">
          <div class="info-row">
            <span class="info-label">主题</span>
            <span class="info-value">{{ result.extracted_topic.title }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">方向</span>
            <span class="badge-info">{{ result.extracted_topic.direction }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">套路</span>
            <span class="info-value">{{ result.extracted_topic.method }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">价值承诺</span>
            <span class="info-value">{{ result.extracted_topic.value_promise }}</span>
          </div>
        </div>
      </div>

      <!-- 推荐标题 Top 5 -->
      <div v-if="topTitles.length" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">
          推荐标题 Top {{ topTitles.length }}
          <span v-if="result.meta" class="text-sm text-ink-3 font-normal ml-2">
            候选 {{ result.meta.total_candidates || topTitles.length }} · 覆盖 {{ result.meta.covered_methods || '-' }} 种套路
          </span>
        </h3>
        <div class="space-y-3">
          <div v-for="(t, i) in topTitles" :key="i" class="title-card">
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-2">
                  <span class="rank-badge" :class="i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : 'rank-3'">
                    TOP {{ i + 1 }}
                  </span>
                  <span class="text-xs text-ink-3">{{ t.method }}</span>
                  <span class="text-xs text-ink-3">·</span>
                  <span class="text-xs text-ink-3">{{ t.word_count }} 字</span>
                </div>
                <p class="text-base font-semibold text-ink">{{ t.title }}</p>
                <p v-if="t.reason" class="text-sm text-ink-3 mt-2">{{ t.reason }}</p>
              </div>
              <div class="ml-2 text-right flex-shrink-0 flex flex-col items-end gap-1">
                <div class="text-2xl font-bold" :class="getScoreColor(t.score || t.final_score)">
                  {{ ((t.score || t.final_score) ?? 0).toFixed(1) }}
                </div>
                <div class="text-xs text-ink-3">综合评分</div>
                <el-button size="small" link @click.stop="copyTitle(t.title)">
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 全部候选标题 -->
      <div v-if="allCandidates.length" class="card p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-h4 font-sans text-ink">
            全部候选
            <span class="text-sm text-ink-3 font-normal ml-2">共 {{ allCandidates.length }} 条</span>
          </h3>
          <el-button text size="small" @click="showAllCandidates = !showAllCandidates">
            {{ showAllCandidates ? '收起' : '展开' }}
          </el-button>
        </div>
        <div v-if="showAllCandidates" class="space-y-2">
          <div
            v-for="(c, i) in allCandidates"
            :key="i"
            class="candidate-row"
            :class="{ 'candidate-eliminated': c.is_eliminated, 'candidate-top5': c.is_top5 }"
          >
            <div class="flex items-center gap-3 flex-1 min-w-0">
              <span class="text-xs text-ink-4 w-6 text-center flex-shrink-0">#{{ c.sequence }}</span>
              <span class="text-sm text-ink flex-1 truncate">{{ c.title }}</span>
              <span class="text-xs text-ink-3 flex-shrink-0">{{ c.method }}</span>
            </div>
            <div class="flex items-center gap-3 flex-shrink-0">
              <span v-if="c.is_top5" class="badge-primary text-xs">Top5</span>
              <span v-if="c.is_eliminated" class="badge-danger text-xs">淘汰</span>
              <span v-if="c.final_score" class="text-sm font-semibold" :class="getScoreColor(c.final_score)">
                {{ c.final_score.toFixed(1) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 元信息 -->
      <div v-if="result.meta" class="card p-6 mb-6">
        <div class="meta-grid">
          <div class="meta-item">
            <span class="text-xs text-ink-3">候选数</span>
            <span class="text-lg font-bold text-ink">{{ result.meta.total_candidates || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="text-xs text-ink-3">淘汰数</span>
            <span class="text-lg font-bold text-ink">{{ result.meta.eliminated_count || 0 }}</span>
          </div>
          <div class="meta-item">
            <span class="text-xs text-ink-3">重生次数</span>
            <span class="text-lg font-bold text-ink">{{ result.meta.regeneration_count || 0 }}</span>
          </div>
          <div class="meta-item">
            <span class="text-xs text-ink-3">耗时</span>
            <span class="text-lg font-bold text-ink">{{ (result.meta.duration_seconds || 0).toFixed(1) }}s</span>
          </div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="bottom-actions">
        <el-button @click="reset">重新生成</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Check, CircleCloseFilled, DocumentCopy } from '@element-plus/icons-vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { post } from '@/api/api'
import { useAgentProgress } from '@/composables/useAgentProgress'
import generationRecordApi from '@/api/generationRecord'

const route = useRoute()

const content = ref('')
const status = ref('idle') // idle | generating | completed | failed
const generating = ref(false)
const errorMessage = ref('')
const result = ref(null)
const showAllCandidates = ref(false)

const progress = useAgentProgress()

const workflowSteps = [
  { name: '内容分析' },
  { name: '标题创作 A' },
  { name: '评审筛选 B' },
  { name: '点击预测 C' },
  { name: '综合判定 D' },
]

const getStepStatus = (stepIndex) => {
  if (status.value === 'idle') return 'pending'
  const ci = progress.currentStepIndex.value
  if (ci < 0) return 'pending'
  if (stepIndex < ci) return 'done'
  if (stepIndex === ci) return progress.stepPercent.value >= 100 ? 'done' : 'active'
  return 'pending'
}

const topTitles = computed(() => {
  if (!result.value) return []
  const recs = result.value.recommendations || []
  if (recs.length) return recs.slice(0, 5)
  const cands = result.value.candidates || []
  return cands.filter(c => c.is_top5).slice(0, 5)
})

const allCandidates = computed(() => {
  if (!result.value) return []
  return result.value.candidates || []
})

const getScoreColor = (score) => {
  if (!score) return 'text-ink-3'
  if (score >= 8) return 'text-leaf'
  if (score >= 6) return 'text-sand'
  return 'text-crimson'
}

const copyTitle = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

// 监听 SSE 结果
watch(() => progress.result.value, (newResult) => {
  if (newResult) {
    result.value = newResult
    status.value = 'completed'
    generating.value = false
    ElMessage.success('标题生成完成')
  }
})

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
})

// 从历史记录恢复
onMounted(async () => {
  const recordId = route.query.record_id
  if (recordId) {
    try {
      const res = await generationRecordApi.get(recordId)
      const record = res.data
      if (record.output_snapshot && record.status === 'completed') {
        result.value = record.output_snapshot
        status.value = 'completed'
        ElMessage.success('已从历史记录恢复生成结果')
      }
    } catch (e) {
      console.warn('恢复历史记录失败:', e)
    }
  }
})

const generate = async () => {
  if (!content.value || content.value.length < 10) {
    ElMessage.warning('请输入文章内容（至少10个字符）')
    return
  }

  status.value = 'generating'
  generating.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const res = await post('/standalone-title/generate', { content: content.value }, { timeout: 300000 })
    const data = res.data || res
    const runId = data.run_id

    if (runId) {
      progress.start(`/api/v1/standalone-title/stream/${runId}`)
    } else {
      status.value = 'failed'
      errorMessage.value = '未获取到任务 ID'
      generating.value = false
    }
  } catch (e) {
    console.error('生成失败:', e)
    status.value = 'failed'
    errorMessage.value = e.response?.data?.detail || e.message || '生成失败，请重试'
    generating.value = false
  }
}

const reset = () => {
  progress.stop()
  status.value = 'idle'
  generating.value = false
  result.value = null
  errorMessage.value = ''
  showAllCandidates.value = false
}

onBeforeRouteLeave(async (to, from, next) => {
  if (!result.value && !generating.value) return next()
  try {
    await ElMessageBox.confirm(
      '离开后当前生成结果将丢失，确定离开吗？',
      '确认离开',
      { confirmButtonText: '仍然离开', cancelButtonText: '留在此页', type: 'warning' }
    )
    next()
  } catch { next(false) }
})

const handleBeforeUnload = (e) => {
  if (result.value || generating.value) { e.preventDefault(); e.returnValue = '' }
}
onMounted(() => window.addEventListener('beforeunload', handleBeforeUnload))
onUnmounted(() => window.removeEventListener('beforeunload', handleBeforeUnload))
</script>

<style scoped>
.standalone-workspace {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 80px;
}

/* 进度步骤 */
.step-indicator {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-done {
  background: var(--leaf);
  color: var(--paper);
}

.step-active {
  background: var(--clay);
  color: var(--paper);
  animation: pulse 1.5s ease-in-out infinite;
}

.step-pending {
  background: var(--bone);
  color: var(--ink-3);
  border: 1px solid var(--line);
}

.overall-track {
  width: 100%;
  height: 4px;
  background: var(--bone);
  border-radius: 2px;
  overflow: hidden;
}

.overall-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--clay-deep), var(--clay));
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* 提取信息 */
.extracted-info {
  background: var(--bone);
  border-radius: var(--r-md);
  padding: 16px;
}

.info-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 6px 0;
}

.info-row + .info-row {
  border-top: 1px solid var(--line);
}

.info-label {
  font-size: 13px;
  color: var(--ink-3);
  width: 60px;
  flex-shrink: 0;
}

.info-value {
  font-size: 14px;
  color: var(--ink);
}

/* 标题卡片 */
.title-card {
  padding: 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  transition: all 0.2s;
}

.title-card:hover {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-2);
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

/* 候选行 */
.candidate-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}

.candidate-eliminated {
  opacity: 0.5;
  background: rgba(184, 84, 80, 0.04);
}

.candidate-top5 {
  border-color: var(--clay-soft);
}

/* 元信息 */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 600px) {
  .meta-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.meta-item {
  text-align: center;
  padding: 12px;
  background: var(--bone);
  border-radius: var(--r-md);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 底部操作 */
.bottom-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
