<template>
  <div class="scorer-workspace">
    <!-- 页头 -->
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">芒格版标题评分</h1>
      <p class="text-sm text-ink-3 mt-1">基于芒格多 Agent 协作方案，对标题进行多维度评分、诊断并生成改写建议</p>
    </header>

    <!-- 进度条 -->
    <div class="card p-4 mb-6" v-if="status !== 'idle'">
      <div class="flex items-center gap-4 flex-wrap">
        <div
          v-for="(step, i) in scorerSteps"
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
          <el-icon v-if="i < scorerSteps.length - 1" class="text-ink-4 mx-1"><ArrowRight /></el-icon>
        </div>
      </div>
      <div class="mt-3">
        <div class="overall-track">
          <div class="overall-fill" :style="{ width: progress.overallPercent.value + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- Agent 状态 -->
    <div v-if="scoring" class="mb-6">
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
      <h3 class="text-h4 font-sans text-ink mb-4">输入信息</h3>
      <div class="mb-4">
        <label class="label">标题内容</label>
        <el-input v-model="title" placeholder="请输入需要评分的标题" size="large" />
      </div>
      <div class="mb-4">
        <label class="label">文章摘要（可选）</label>
        <el-input
          v-model="summary"
          type="textarea"
          placeholder="请输入文章摘要（如提供，能更精准地评估标题与内容的一致性）"
          :autosize="{ minRows: 3, maxRows: 8 }"
          resize="none"
        />
      </div>
      <el-button type="primary" size="large" @click="score" :loading="scoring">
        开始评分
      </el-button>
    </div>

    <!-- 评分中占位 -->
    <div v-if="status === 'generating' && !result" class="card p-6 text-center py-16">
      <p class="text-ink-3">评分中，请稍候...</p>
    </div>

    <!-- 错误 -->
    <div v-if="status === 'failed'" class="card p-6 text-center py-16 mb-6">
      <el-icon :size="48" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4 mb-2">评分失败</h3>
      <p class="text-ink-3 mb-6">{{ errorMessage }}</p>
      <el-button @click="reset">重新输入</el-button>
    </div>

    <!-- 评分结果 -->
    <div v-if="result" class="result-area">
      <!-- 总分 -->
      <div class="card p-8 mb-6">
        <div class="score-hero">
          <div class="score-circle" :class="gradeClass">
            <span class="score-value">{{ result.total_score }}</span>
            <span class="score-unit">/100</span>
          </div>
          <div class="score-meta">
            <span class="grade-letter" :class="gradeClass">{{ result.grade }}</span>
            <p class="text-sm text-ink-3 mt-1 max-w-[240px] text-center">{{ result.grade_label }}</p>
          </div>
        </div>
      </div>

      <!-- 三维度评分 -->
      <div class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">三维度评分</h3>
        <div class="space-y-5">
          <div v-for="dim in dimScores" :key="dim.name">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm font-medium text-ink-2">{{ dim.name }}</span>
              <span class="text-sm font-bold text-ink">{{ dim.score.toFixed(1) }}/10</span>
            </div>
            <div class="dim-bar-track">
              <div
                class="dim-bar-fill"
                :class="scoreLevel(dim.score)"
                :style="{ width: (dim.score / 10 * 100) + '%' }"
              ></div>
            </div>
            <p v-if="dim.diagnosis" class="text-xs text-ink-3 mt-1">{{ dim.diagnosis }}</p>
          </div>
        </div>
      </div>

      <!-- 增强项评分 -->
      <div class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">增强项评分</h3>
        <div class="enhance-grid">
          <div v-for="item in enhanceItems" :key="item.name" class="enhance-card">
            <span class="text-sm font-medium text-ink-2 mb-2 block">{{ item.name }}</span>
            <div class="stars">
              <span v-for="n in 5" :key="n" class="star" :class="{ filled: n <= item.score }">&#9733;</span>
            </div>
            <span class="text-xs text-ink-3 mt-1 block text-center">{{ item.score.toFixed(1) }}/5</span>
          </div>
        </div>
        <div v-if="result.scores && result.scores.enhance_opportunities" class="enhance-hint mt-4">
          <p class="text-sm">{{ result.scores.enhance_opportunities }}</p>
        </div>
      </div>

      <!-- 红线审查 -->
      <div class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">红线审查</h3>
        <div class="redline-grid">
          <div class="redline-item" v-for="rl in redlineItems" :key="rl.label">
            <span class="text-sm text-ink-2">{{ rl.label }}</span>
            <span class="text-sm font-semibold" :class="rl.class">{{ rl.text }}</span>
          </div>
        </div>
        <div v-if="result.redlines && result.redlines.raw_redlines" class="redline-raw mt-3">
          <p class="text-sm text-ink-3">{{ result.redlines.raw_redlines }}</p>
        </div>
      </div>

      <!-- 综合诊断 -->
      <div v-if="result.diagnosis" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">综合诊断</h3>
        <div class="diagnosis-box">
          <template v-if="typeof result.diagnosis === 'string'">
            <p class="text-sm text-ink-2 leading-relaxed">{{ result.diagnosis }}</p>
          </template>
          <template v-else>
            <div v-for="(val, key) in result.diagnosis" :key="key" class="mb-2">
              <span class="text-sm font-medium text-ink-2">{{ key }}：</span>
              <span class="text-sm text-ink">{{ val }}</span>
            </div>
          </template>
        </div>
      </div>

      <!-- 结构分析 -->
      <div v-if="result.analysis && result.analysis.raw" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">结构分析</h3>
        <pre class="analysis-pre">{{ result.analysis.raw }}</pre>
      </div>

      <!-- 改写建议 -->
      <div v-if="result.rewrites && result.rewrites.length" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">改写建议</h3>
        <div class="space-y-3">
          <div v-for="(rw, i) in result.rewrites" :key="i" class="rewrite-card">
            <div class="flex items-center gap-3 mb-2">
              <span class="rank-badge rank-2">建议 {{ i + 1 }}</span>
              <span class="text-base font-semibold text-ink">{{ rw.title }}</span>
            </div>
            <div class="flex gap-4 text-sm ml-16">
              <span v-if="rw.fix" style="color: var(--crimson);">修复：{{ rw.fix }}</span>
              <span v-if="rw.keep" style="color: var(--leaf);">保留：{{ rw.keep }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 元信息 -->
      <div class="card p-4 mb-6 flex justify-center">
        <div class="meta-item">
          <span class="text-xs text-ink-3">耗时</span>
          <span class="text-lg font-bold text-ink">{{ result.duration_seconds.toFixed(1) }}s</span>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="bottom-actions">
        <el-button @click="reset">重新评分</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Check, CircleCloseFilled } from '@element-plus/icons-vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { post } from '@/api/api'
import { useAgentProgress } from '@/composables/useAgentProgress'

const title = ref('')
const summary = ref('')
const status = ref('idle')
const scoring = ref(false)
const errorMessage = ref('')
const result = ref(null)

const progress = useAgentProgress()

const scorerSteps = [
  { name: '拆解 Agent' },
  { name: '三维度评分' },
  { name: '增强评审' },
  { name: '红线审查' },
  { name: '改写 Agent' },
]

const getStepStatus = (stepIndex) => {
  if (status.value === 'idle') return 'pending'
  const ci = progress.currentStepIndex.value
  if (ci < 0) return 'pending'
  if (stepIndex < ci) return 'done'
  if (stepIndex === ci) return progress.stepPercent.value >= 100 ? 'done' : 'active'
  return 'pending'
}

const gradeClass = computed(() => {
  if (!result.value) return ''
  const g = result.value.grade
  if (g === 'S') return 'grade-s'
  if (g === 'A') return 'grade-a'
  if (g === 'B') return 'grade-b'
  if (g === 'C') return 'grade-c'
  return 'grade-d'
})

const dimScores = computed(() => {
  if (!result.value || !result.value.scores) return []
  const s = result.value.scores
  return [
    { name: '信息缺口', score: s.gap?.score || 0, diagnosis: s.gap?.diagnosis || '' },
    { name: '社会位置', score: s.anchor?.score || 0, diagnosis: s.anchor?.diagnosis || '' },
    { name: '认知冲突', score: s.conflict?.score || 0, diagnosis: s.conflict?.diagnosis || '' },
  ]
})

const enhanceItems = computed(() => {
  if (!result.value || !result.value.scores || !result.value.scores.enhancement) return []
  const e = result.value.scores.enhancement
  return [
    { name: '联想光环', score: e['联想光环'] || 0 },
    { name: '对比结构', score: e['对比结构'] || 0 },
    { name: '因果承诺', score: e['因果承诺'] || 0 },
  ]
})

const redlineItems = computed(() => {
  if (!result.value || !result.value.redlines) return []
  const rl = result.value.redlines
  return [
    { label: '焦虑贩卖', text: rl.r1 ? '通过' : '未通过', class: rl.r1 ? 'text-leaf' : 'text-crimson' },
    { label: '承诺兑现', text: rl.r2 ? '通过' : (rl.high_risk_r2 ? '高风险' : '未通过'), class: rl.r2 ? 'text-leaf' : 'text-crimson' },
    { label: '操控词', text: rl.r3 ? '通过' : '未通过', class: rl.r3 ? 'text-leaf' : 'text-crimson' },
    { label: '命名状态', text: rl.r4_named_state ? '命中' : '未命中', class: rl.r4_named_state ? 'text-sand' : 'text-ink-3' },
    { label: '字数', text: `${rl.char_count}字 ${rl.char_ok ? '合规' : '超标'}`, class: rl.char_ok ? 'text-leaf' : 'text-crimson' },
  ]
})

const scoreLevel = (score) => {
  if (score >= 7) return 'level-high'
  if (score >= 4) return 'level-mid'
  return 'level-low'
}

watch(() => progress.result.value, (newResult) => {
  if (newResult) {
    result.value = newResult
    status.value = 'completed'
    scoring.value = false
    ElMessage.success('评分完成')
  }
})

watch(() => progress.error.value, (newError) => {
  if (newError) {
    status.value = 'failed'
    errorMessage.value = newError
    scoring.value = false
    ElMessage.error('评分失败')
  }
})

onUnmounted(() => {
  progress.stop()
})

const score = async () => {
  if (!title.value) {
    ElMessage.warning('请输入标题内容')
    return
  }

  status.value = 'generating'
  scoring.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const res = await post('/title-munger/munger-score', {
      title: title.value,
      summary: summary.value || undefined,
    }, { timeout: 120000 })

    const data = res.data || res
    const runId = data.run_id

    if (runId) {
      progress.start(`/api/v1/title-munger/stream/${runId}`)
    } else {
      status.value = 'failed'
      errorMessage.value = '未获取到任务 ID'
      scoring.value = false
    }
  } catch (e) {
    console.error('评分失败:', e)
    status.value = 'failed'
    errorMessage.value = e.response?.data?.detail || e.message || '评分失败，请重试'
    scoring.value = false
  }
}

const reset = () => {
  progress.stop()
  status.value = 'idle'
  scoring.value = false
  result.value = null
  errorMessage.value = ''
}
</script>

<style scoped>
.scorer-workspace {
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

/* 总分 */
.score-hero {
  display: flex;
  align-items: center;
  gap: 32px;
  justify-content: center;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bone);
}

.score-circle.grade-s {
  background: linear-gradient(135deg, var(--crimson), var(--sand));
  color: var(--paper);
}

.score-circle.grade-a {
  background: linear-gradient(135deg, var(--leaf), #73d13d);
  color: var(--paper);
}

.score-circle.grade-b {
  background: linear-gradient(135deg, var(--clay), var(--clay-soft));
  color: var(--paper);
}

.score-circle.grade-c {
  background: linear-gradient(135deg, var(--sand), var(--sand-soft));
  color: var(--paper);
}

.score-circle.grade-d {
  background: var(--bone);
  color: var(--ink-4);
}

.score-value {
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
}

.score-unit {
  font-size: 14px;
  opacity: 0.8;
}

.score-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.grade-letter {
  font-size: 32px;
  font-weight: 800;
}

.grade-letter.grade-s { color: var(--crimson); }
.grade-letter.grade-a { color: var(--leaf); }
.grade-letter.grade-b { color: var(--clay); }
.grade-letter.grade-c { color: var(--sand); }
.grade-letter.grade-d { color: var(--ink-4); }

/* 维度评分条 */
.dim-bar-track {
  width: 100%;
  height: 8px;
  background: var(--bone);
  border-radius: 4px;
  overflow: hidden;
}

.dim-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.level-high { background: var(--leaf); }
.level-mid { background: var(--sand); }
.level-low { background: var(--crimson); }

/* 增强项 */
.enhance-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.enhance-card {
  padding: 16px;
  background: var(--bone);
  border-radius: var(--r-md);
  text-align: center;
}

.stars {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.star {
  font-size: 18px;
  color: var(--line);
}

.star.filled {
  color: var(--sand);
}

.enhance-hint {
  background: var(--sand-soft);
  border-radius: var(--r-md);
  padding: 12px;
  color: var(--ink-2);
}

/* 红线 */
.redline-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.redline-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bone);
  border-radius: var(--r-md);
}

.redline-raw {
  padding: 12px;
  background: var(--bone);
  border-radius: var(--r-md);
  white-space: pre-line;
}

/* 诊断 */
.diagnosis-box {
  padding: 16px;
  background: var(--bone);
  border-radius: var(--r-md);
}

/* 分析 */
.analysis-pre {
  background: var(--bone);
  border-radius: var(--r-md);
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-x: auto;
  color: var(--ink-2);
}

/* 改写卡片 */
.rewrite-card {
  padding: 16px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}

.rank-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: 11px;
  font-weight: 700;
}

.rank-2 {
  background: var(--sand);
  color: var(--paper);
}

/* 元信息 */
.meta-item {
  text-align: center;
  padding: 12px 24px;
  background: var(--bone);
  border-radius: var(--r-md);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 底部 */
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
