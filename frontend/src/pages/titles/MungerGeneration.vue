<template>
  <div class="munger-workspace">
    <!-- 页头 -->
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">芒格版标题生成</h1>
      <p class="text-sm text-ink-3 mt-1">基于芒格多 Agent 协作方案的智能标题生成系统（≤20字 · 回环机制）</p>
    </header>

    <!-- 进度条 -->
    <div class="card p-4 mb-6" v-if="status !== 'idle'">
      <div class="flex items-center gap-4">
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
      <!-- 总进度条 -->
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
          placeholder="请输入文章全文或详细内容摘要..."
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
      <!-- 最终推荐 -->
      <div v-if="result.final_pick" class="card p-6 mb-6 final-card">
        <div class="flex items-center gap-2 mb-3">
          <span class="badge-primary">最终推荐</span>
        </div>
        <p class="text-2xl font-bold text-clay text-center py-4">{{ result.final_pick }}</p>
      </div>

      <!-- 定位语 -->
      <div v-if="result.positioning" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-3">定位语</h3>
        <div class="positioning-box">{{ result.positioning }}</div>
      </div>

      <!-- 三维度候选标题 -->
      <div v-if="result.all_titles && result.all_titles.length" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">
          三维度候选标题
          <span class="text-sm text-ink-3 font-normal ml-2">共 {{ result.all_titles.length }} 条</span>
        </h3>
        <div class="dimension-grid">
          <div v-for="dim in dimensionGroups" :key="dim.name" class="dimension-card card p-4">
            <h4 class="text-sm font-semibold text-ink-2 mb-3">{{ dim.name }}</h4>
            <div v-for="(t, i) in dim.titles" :key="i" class="candidate-item">
              <span class="text-sm font-medium text-ink">{{ t.title }}</span>
              <span class="badge-info mt-1">{{ t.dimension }}</span>
            </div>
            <p v-if="!dim.titles.length" class="text-sm text-ink-4 text-center py-3">无候选</p>
          </div>
        </div>
      </div>

      <!-- Top 5 增强标题 -->
      <div v-if="result.top5 && result.top5.length" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">Top 5 增强标题</h3>
        <div class="space-y-3">
          <div v-for="(t, i) in result.top5" :key="i" class="top5-card">
            <div class="flex items-center gap-3">
              <span class="rank-badge" :class="i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : 'rank-3'">
                TOP {{ i + 1 }}
              </span>
              <span class="text-base font-semibold text-ink flex-1">{{ t.title }}</span>
            </div>
            <div class="flex gap-2 mt-2 ml-16">
              <span class="badge-info">{{ t.dimension }}</span>
              <span v-if="t.enhancement" class="badge-warning">{{ t.enhancement }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 审判结果 -->
      <div v-if="result.verdicts && result.verdicts.length" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">审判结果</h3>
        <div class="space-y-3">
          <div
            v-for="(v, i) in result.verdicts"
            :key="i"
            class="verdict-card"
            :class="verdictCardClass(v.final_verdict)"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-base font-semibold text-ink">{{ v.title }}</span>
              <span class="verdict-badge" :class="verdictBadgeClass(v.final_verdict)">
                {{ v.final_verdict }}
              </span>
            </div>
            <div class="flex gap-4 text-sm text-ink-3">
              <span>拇指：{{ v.thumb }}</span>
              <span>字数：{{ v.word_count }}字</span>
            </div>
            <p v-if="v.redline" class="text-sm mt-1" style="color: var(--crimson);">红线：{{ v.redline }}</p>
          </div>
        </div>
      </div>

      <!-- 元信息 -->
      <div class="card p-6 mb-6">
        <div class="meta-grid">
          <div class="meta-item">
            <span class="text-xs text-ink-3">状态</span>
            <span class="text-lg font-bold" :class="result.success ? 'text-leaf' : 'text-crimson'">
              {{ result.success ? '通过' : '未通过' }}
            </span>
          </div>
          <div class="meta-item">
            <span class="text-xs text-ink-3">迭代轮数</span>
            <span class="text-lg font-bold text-ink">{{ result.loop_count }}</span>
          </div>
          <div class="meta-item">
            <span class="text-xs text-ink-3">耗时</span>
            <span class="text-lg font-bold text-ink">{{ result.duration_seconds.toFixed(1) }}s</span>
          </div>
        </div>
        <div v-if="result.failure_reasons && result.failure_reasons.length" class="failure-box mt-4">
          <h4 class="text-sm font-semibold text-crimson mb-2">失败原因</h4>
          <p v-for="(r, i) in result.failure_reasons" :key="i" class="text-sm text-crimson">{{ r }}</p>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="bottom-actions">
        <el-button @click="reset">
          重新生成
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Check, CircleCloseFilled } from '@element-plus/icons-vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { post } from '@/api/api'
import { useAgentProgress } from '@/composables/useAgentProgress'

const content = ref('')
const status = ref('idle') // idle | generating | completed | failed
const generating = ref(false)
const errorMessage = ref('')
const result = ref(null)

const progress = useAgentProgress()

const workflowSteps = [
  { name: '策划 Agent' },
  { name: '三维度生成' },
  { name: '增强 Agent' },
  { name: '审判 Agent' },
]

const getStepStatus = (stepIndex) => {
  if (status.value === 'idle') return 'pending'
  const ci = progress.currentStepIndex.value
  if (ci < 0) return 'pending'
  if (stepIndex < ci) return 'done'
  if (stepIndex === ci) return progress.stepPercent.value >= 100 ? 'done' : 'active'
  return 'pending'
}

const dimensionGroups = computed(() => {
  if (!result.value || !result.value.all_titles) return []
  const groups = { '信息缺口': [], '社会位置': [], '认知冲突': [] }
  for (const t of result.value.all_titles) {
    if (groups[t.dimension]) groups[t.dimension].push(t)
  }
  return Object.entries(groups).map(([name, titles]) => ({ name, titles }))
})

const verdictCardClass = (verdict) => {
  if (verdict === '发布') return 'verdict-pass'
  if (verdict === '备选') return 'verdict-backup'
  return 'verdict-reject'
}

const verdictBadgeClass = (verdict) => {
  if (verdict === '发布') return 'badge-success'
  if (verdict === '备选') return 'badge-warning'
  return 'badge-danger'
}

// 监听 SSE 结果
import { watch } from 'vue'

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
    const res = await post('/title-munger/munger-generate', { content: content.value }, { timeout: 180000 })
    const data = res.data || res
    const runId = data.run_id

    if (runId) {
      progress.start(`/api/v1/title-munger/stream/${runId}`)
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
.munger-workspace {
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

/* 总进度条 */
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

/* 定位语 */
.positioning-box {
  background: var(--sand-soft);
  border: 1px solid var(--sand);
  border-radius: var(--r-md);
  padding: 16px;
  font-size: 15px;
  line-height: 1.7;
  color: var(--ink-2);
}

/* 三维度候选 */
.dimension-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 768px) {
  .dimension-grid {
    grid-template-columns: 1fr;
  }
}

.dimension-card {
  border: 1px solid var(--line);
}

.candidate-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--bone);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.candidate-item:last-child {
  border-bottom: none;
}

/* Top 5 卡片 */
.top5-card {
  padding: 16px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  transition: all 0.2s;
}

.top5-card:hover {
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

/* 审判卡片 */
.verdict-card {
  padding: 16px;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
}

.verdict-pass {
  background: rgba(92, 138, 92, 0.06);
  border-color: var(--leaf);
}

.verdict-backup {
  background: rgba(196, 155, 92, 0.06);
  border-color: var(--sand);
}

.verdict-reject {
  background: rgba(184, 84, 80, 0.06);
  border-color: var(--crimson);
}

.verdict-badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-weight: 600;
}

/* 最终推荐卡片 */
.final-card {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-clay);
}

/* 元信息 */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
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

.failure-box {
  background: rgba(184, 84, 80, 0.06);
  border-radius: var(--r-md);
  padding: 16px;
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
