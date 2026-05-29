<template>
  <div class="standalone-workspace">
    <!-- 页头 -->
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">智能起标题</h1>
      <p class="text-sm text-ink-3 mt-1">从文章内容直接生成 5 个标题，并为每个标题给出简介与点击分析</p>
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

      <!-- 标题 + 评价：左右分列 -->
      <div v-if="allCandidates.length" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">
          生成标题
          <span class="text-sm text-ink-3 font-normal ml-2">共 {{ allCandidates.length }} 个 · 点击查看简介与点击分析</span>
        </h3>
        <div class="title-split">
          <!-- 左：标题列表 -->
          <div class="title-list">
            <div
              v-for="(c, i) in allCandidates"
              :key="c.id || i"
              class="title-item"
              :class="{ 'title-item-active': selectedIndex === i }"
              @click="selectedIndex = i"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="seq-badge">{{ i + 1 }}</span>
                <span class="title-item-text">{{ c.title }}</span>
              </div>
              <div class="flex items-center gap-2 mt-1.5 pl-7">
                <span class="text-xs text-ink-3">{{ c.method }}</span>
                <span class="text-xs text-ink-4">·</span>
                <span class="text-xs text-ink-3">{{ c.word_count }} 字</span>
                <el-button size="small" link class="ml-auto" @click.stop="copyTitle(c.title)">
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <!-- 右：评价详情 -->
          <div class="title-detail">
            <template v-if="selected">
              <p class="detail-title">{{ selected.title }}</p>

              <div class="detail-block">
                <div class="detail-block-head">
                  <span class="detail-tag tag-summary">简介</span>
                  <span class="detail-block-sub">这标题写什么 · 为什么这么取</span>
                </div>
                <p class="detail-text">{{ selected.b_summary || '暂无简介' }}</p>
              </div>

              <div class="detail-block">
                <div class="detail-block-head">
                  <span class="detail-tag tag-click">点击分析</span>
                  <span class="detail-block-sub">读者为什么会点</span>
                </div>
                <div v-if="selected.c_click_reason" class="detail-sub">
                  <span class="detail-sub-label">吸引点 / 会点原因</span>
                  <p class="detail-text">{{ selected.c_click_reason }}</p>
                </div>
                <div v-if="selected.c_no_click_reason" class="detail-sub">
                  <span class="detail-sub-label">可能划走的点</span>
                  <p class="detail-text">{{ selected.c_no_click_reason }}</p>
                </div>
                <div v-if="selected.c_improvement_suggestion" class="detail-sub">
                  <span class="detail-sub-label">改进建议</span>
                  <p class="detail-text">{{ selected.c_improvement_suggestion }}</p>
                </div>
                <p v-if="!selected.c_click_reason && !selected.c_no_click_reason && !selected.c_improvement_suggestion" class="detail-text">暂无点击分析</p>
              </div>
            </template>
            <div v-else class="detail-empty">
              <p class="text-ink-3">点击左侧任一标题查看评价</p>
            </div>
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
const selectedIndex = ref(0)

const progress = useAgentProgress()

const workflowSteps = [
  { name: '内容分析' },
  { name: '标题创作 A' },
  { name: '生成简介 B' },
  { name: '点击分析 C' },
]

const getStepStatus = (stepIndex) => {
  if (status.value === 'idle') return 'pending'
  const ci = progress.currentStepIndex.value
  if (ci < 0) return 'pending'
  if (stepIndex < ci) return 'done'
  if (stepIndex === ci) return progress.stepPercent.value >= 100 ? 'done' : 'active'
  return 'pending'
}

const allCandidates = computed(() => {
  if (!result.value) return []
  return result.value.candidates || []
})

const selected = computed(() => allCandidates.value[selectedIndex.value] || null)

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
    selectedIndex.value = 0
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
  selectedIndex.value = 0
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

/* 左右分列 */
.title-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: 20px;
  align-items: start;
}

@media (max-width: 720px) {
  .title-split {
    grid-template-columns: 1fr;
  }
}

/* 左：标题列表 */
.title-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.title-item {
  padding: 12px 14px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: all 0.18s;
}

.title-item:hover {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-1);
}

.title-item-active {
  border-color: var(--clay);
  background: rgba(204, 120, 92, 0.06);
  box-shadow: var(--sh-2);
}

.seq-badge {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--bone);
  color: var(--ink-3);
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.title-item-active .seq-badge {
  background: var(--clay);
  color: var(--paper);
}

.title-item-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
}

/* 右：详情 */
.title-detail {
  position: sticky;
  top: 16px;
  padding: 18px;
  background: var(--bone);
  border-radius: var(--r-lg);
  min-height: 200px;
}

.detail-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.5;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.detail-block + .detail-block {
  margin-top: 16px;
}

.detail-block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.detail-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 700;
}

.tag-summary {
  background: var(--pine-soft);
  color: var(--pine);
}

.tag-click {
  background: var(--clay);
  color: var(--paper);
}

.detail-block-sub {
  font-size: 12px;
  color: var(--ink-4);
}

.detail-sub + .detail-sub {
  margin-top: 10px;
}

.detail-sub-label {
  display: block;
  font-size: 12px;
  color: var(--ink-3);
  margin-bottom: 2px;
}

.detail-text {
  font-size: 14px;
  color: var(--ink);
  line-height: 1.7;
}

.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
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
