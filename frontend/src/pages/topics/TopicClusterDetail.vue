<template>
  <div class="topic-cluster-detail">
    <!-- 返回按钮 -->
    <div class="mb-4">
      <el-button text @click="goBack" style="color: #6B6862;">
        &larr; 返回话题库
      </el-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <span class="ml-2" style="color: #6B6862;">加载中...</span>
    </div>

    <template v-else-if="cluster">
      <!-- 单栏布局 -->
      <div class="detail-layout">
        <div class="detail-main">
          <div class="detail-card">
            <div class="p-6 card-body">
              <!-- 标签行 -->
              <div class="flex flex-wrap gap-2 mb-4">
                <span v-if="cluster.info_type" class="tag-type">{{ cluster.info_type }}</span>
                <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
                <span v-if="isNew(cluster)" class="tag-new">NEW</span>
                <span v-if="cluster.heat_score" class="tag-heat">热度 {{ cluster.heat_score?.toFixed(0) }}</span>
                <span v-if="cluster.needs_update" class="tag-needs-update-detail">待更新</span>
                <span v-else-if="cluster.mined" class="tag-mined-detail">已挖掘</span>
              </div>

              <!-- 标题 -->
              <h1 class="font-serif" style="font-size: 28px; font-weight: 500; color: var(--ink); line-height: 1.25;">
                {{ cluster.core_title_zh || cluster.latest_title || cluster.core_title }}
              </h1>

              <!-- 摘要（详情页完整展示正文级事实摘要） -->
              <p v-if="cluster.summary_zh || cluster.summary"
                 class="mt-4"
                 style="color: #4A4641; font-size: 16px; line-height: 1.8; white-space: pre-wrap;">
                {{ cluster.summary_zh || cluster.summary }}
              </p>

              <!-- 弹性占位：内容少时把多余空白留在简介和信息要素之间 -->
              <div class="flex-spacer"></div>

              <!-- 信息要素 -->
              <div v-if="cluster.elements && Object.keys(cluster.elements).length > 0" class="mt-14">
                <div class="flex items-center gap-2 mb-2">
                  <span class="section-bar"></span>
                  <h4 style="font-size: 13px; font-weight: 600; color: var(--ink-3);">信息要素</h4>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span v-for="(val, key) in cluster.elements" :key="key" class="element-tag" v-show="val">
                    <span class="element-key">{{ key }}</span>
                    <span class="element-val">{{ val }}</span>
                  </span>
                </div>
              </div>

              <!-- 原文来源 -->
              <div v-if="cluster.raw_infos?.length > 0 || cluster.source_urls?.length > 0" class="mt-4 pt-4 source-section" style="border-top: 1px solid var(--line);">
                <div class="flex items-center gap-2 mb-2">
                  <span class="section-bar"></span>
                  <h4 style="font-size: 12px; font-weight: 600; color: var(--ink-4);">原文来源</h4>
                </div>

                <!-- 完整原文卡片 -->
                <div v-if="cluster.raw_infos?.length > 0" class="flex flex-col gap-2 source-scroll">
                  <a
                    v-for="raw in cluster.raw_infos"
                    :key="raw.id"
                    :href="raw.has_snapshot ? '/api/v1/article-snapshots/' + raw.id : raw.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="source-card"
                  >
                    <div class="source-card-header">
                      <span class="source-platform">{{ raw.source_name }}</span>
                      <span
                        v-if="raw.commercial_level && raw.commercial_level !== 'none'"
                        class="source-commercial-badge"
                        :title="raw.commercial_meta?.reason || '命中商业推广结构信号'"
                      >
                        {{ raw.commercial_level === 'likely' ? '高概率商单' : '潜在商单' }}
                      </span>
                      <span v-if="raw.published_at" class="source-time">
                        {{ formatRelativeTime(raw.published_at) }}
                      </span>
                    </div>
                    <div class="source-title-row">
                      <span class="source-title">{{ raw.title }}</span>
                      <span class="source-link">阅读原文 &rarr;</span>
                    </div>
                  </a>
                </div>

                <!-- 兼容旧的 URL 列表 -->
                <div v-else class="flex flex-col gap-2 source-scroll">
                  <a
                    v-for="(url, idx) in cluster.source_urls"
                    :key="idx"
                    :href="url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="source-item"
                  >
                    <span class="source-index">{{ idx + 1 }}</span>
                    <span class="source-url-text">{{ url }}</span>
                    <span class="source-arrow">&rarr;</span>
                  </a>
                </div>
              </div>

              <!-- 底部操作栏 -->
              <div class="flex justify-end items-center mt-3 pt-3" style="border-top: 1px solid var(--line);">
                <button
                  v-if="cluster.needs_update && !miningRunning"
                  class="btn-creative btn-re-mine" style="font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;"
                  @click="startMining"
                >
                  重新挖掘
                </button>
                <button
                  v-else-if="isMined && !miningRunning"
                  class="btn-creative" style="font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;"
                  @click="scrollToResults"
                >
                  查看选题
                </button>
                <button
                  v-else
                  class="btn-creative" style="font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;"
                  @click="startMining"
                  :disabled="miningRunning"
                >
                  {{ miningRunning ? '挖掘中...' : '挖掘选题' }}
                </button>
              </div>
            </div>
          </div>

          <!-- ===== 挖掘进度（内联在话题卡片下方） ===== -->
          <div v-if="miningRunning" class="mining-inline-section fade-in">
            <!-- Agent 状态条 -->
            <AgentStatusBar
              v-for="(step, i) in miningProgress.steps.value"
              :key="i"
              :agent-name="step.agent"
              :action="step.action"
              :avatar="step.avatar"
              :is-active="i === miningProgress.currentStepIndex.value"
              :show-progress="i === miningProgress.currentStepIndex.value"
              :no-transition="miningProgress.noStepTransition.value"
              :percent="i === miningProgress.currentStepIndex.value ? miningProgress.stepPercent.value : (i < miningProgress.currentStepIndex.value ? 100 : 0)"
            />
          </div>

          <!-- ===== 候选选题瀑布流 ===== -->
          <div v-if="!miningRunning && candidateList.length > 0" ref="resultsRef" class="candidates-section fade-in">
            <div class="candidates-header">
              <div class="flex items-center gap-2">
                <span class="section-bar"></span>
                <h3 class="candidates-title">选题角度</h3>
                <span class="candidates-count">共 {{ candidateList.length }} 个</span>
              </div>
            </div>

            <div class="waterfall">
              <div
                v-for="(c, idx) in candidateList"
                :key="c.id"
                class="waterfall-card"
                :style="{ animationDelay: (idx * 0.06) + 's' }"
              >
                <!-- 卡片头部：序号 + 方向 + 分数 -->
                <div class="wc-head">
                  <div class="flex items-center gap-2">
                    <span class="wc-index">{{ String(idx + 1).padStart(2, '0') }}</span>
                    <span v-if="c.direction" class="wc-direction">{{ c.direction }}</span>
                    <span v-if="c.routine" class="wc-routine">{{ c.routine }}</span>
                  </div>
                  <span class="wc-score" :class="scoreClass(c.weighted_score)">
                    {{ c.weighted_score != null ? c.weighted_score.toFixed(1) : '—' }}
                  </span>
                </div>

                <!-- 标题 -->
                <h3 class="wc-title">{{ c.title }}</h3>

                <!-- 摘要（优先显示充实后的） -->
                <p v-if="c.enriched_summary || c.summary" class="wc-summary">
                  {{ c.enriched_summary || c.summary }}
                </p>

                <!-- 可写性信息 -->
                <div v-if="c.feasibility_verdict" class="wc-feasibility">
                  <span class="wc-feas-label">可写性</span>
                  <span
                    class="wc-feas-badge"
                    :class="{
                      'feas-pass': c.feasibility_verdict === 'pass',
                      'feas-weak': c.feasibility_verdict === 'weak_pass',
                      'feas-fail': c.feasibility_verdict === 'fail',
                    }"
                  >{{ c.feasibility_verdict === 'pass' ? '通过' : c.feasibility_verdict === 'weak_pass' ? '弱通过' : '不通过' }}</span>
                  <span v-if="c.feasibility_score != null" class="wc-feas-score">{{ c.feasibility_score.toFixed(1) }}</span>
                </div>

                <!-- 操作按钮 -->
                <div class="wc-actions">
                  <button class="btn-copy" @click="copyCandidate(c)">
                    <span class="copy-icon">⧉</span> 复制
                  </button>
                  <button class="btn-write-outline" @click="startCreation(c)">
                    用此角度写大纲 <span style="font-size: 12px;">→</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 404 -->
    <div v-else class="text-center py-20">
      <h3 style="color: #3A3935; font-size: 18px;">话题不存在</h3>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'
import { useAgentProgress } from '@/composables/useAgentProgress'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'

const route = useRoute()
const router = useRouter()

const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/topic-clusters')
  }
}

const loading = ref(true)
const cluster = ref(null)
const resultsRef = ref(null)

// 判断是否已挖掘
const isMined = computed(() => {
  return cluster.value?.mined === true || (cluster.value?.candidates?.length > 0)
})

const panelMode = ref('mining') // 'mining' | 'candidates'
const miningRunning = ref(false)

// Agent 进度（轮询，绕开 SSE 避免反代缓冲）
const miningProgress = useAgentProgress()
const MINING_TOTAL_STEPS = 3        // 挖掘 3 个 Agent（衍生 → 可写性审计 → 评分）

// 监听 composable 完成：isRunning 变 false 且有 result 时触发成功回调
watch(
  [() => miningProgress.result.value, () => miningProgress.isRunning.value],
  ([r, running]) => {
    if (r && !running) {
      onMiningSuccess(r)
    }
  }
)

// 面板中的候选列表（本地副本）
const candidateList = ref([])

// 从 cluster 同步候选到本地列表
const syncCandidates = () => {
  candidateList.value = [...(cluster.value?.candidates || [])]
}

// 评分维度映射
const scoreDimensions = [
  { key: 'pain_point', label: '痛点直击' },
  { key: 'value_density', label: '价值密度' },
  { key: 'propagation', label: '传播触发' },
  { key: 'differentiation', label: '差异化' },
  { key: 'freshness', label: '新鲜度' },
  { key: 'audience_fit', label: '受众适配' },
]

// 热度/分数映射
const heatLabel = (score) => {
  if (score == null) return '—'
  if (score >= 7) return '高'
  if (score >= 5) return '中'
  return '低'
}

const scoreClass = (score) => {
  if (score == null) return 'score-low'
  if (score >= 7) return 'score-high'
  if (score >= 5) return 'score-mid'
  return 'score-low'
}

// 复制选题
const copyCandidate = async (c) => {
  if (!c) return
  const text = `${c.title}\n${c.summary || c.value_promise || ''}`.trim()
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制选题')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 滚动到结果区域
const scrollToResults = () => {
  if (resultsRef.value) {
    resultsRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// ── 轮询挖掘进度（绕开 SSE）──────────────────────
let pollTimer = null
const POLL_INTERVAL = 1500

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const onMiningSuccess = (result) => {
  ElMessage.success(`挖掘完成，生成 ${result?.total_candidates ?? '?'} 个候选`)
  miningRunning.value = false
  // 标记该话题已挖掘，返回列表页时定点刷新标签
  try { sessionStorage.setItem('topic-mined-id', String(cluster.value?.id || route.params.id)) } catch {}
  loadCluster().then(() => {
    syncCandidates()
    nextTick(() => {
      if (resultsRef.value) {
        resultsRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  })
}

const onMiningError = (msg) => {
  ElMessage.error(`挖掘失败: ${msg}`)
  miningRunning.value = false
}

const pollProgress = async (runId) => {
  try {
    const res = await get(`/topic-candidates/progress/${runId}`)
    const d = res?.data || {}
    if (d.exists === false) return  // run 还没建好或已清理，下次再试

    // 把快照喂给 composable（它会处理 step 切换动画、归零等）
    miningProgress.applySnapshot(d)

    if (d.error) {
      stopPolling()
      onMiningError(d.error)
      return
    }
    if (d.done && d.result) {
      stopPolling()
      // 等进度条动画到 100% 后关闭面板、刷新数据
      const resultData = d.result
      setTimeout(() => {
        onMiningSuccess(resultData)
      }, 1500)
    }
  } catch {
    // 单次轮询失败忽略，下次继续
  }
}

// 开始挖掘
const startMining = async () => {
  if (!cluster.value?.id) return
  // 先停掉旧轮询（防止多次点击导致泄漏）
  stopPolling()
  miningProgress.reset()
  miningRunning.value = true
  panelMode.value = 'mining'

  try {
    const res = await post('/topic-candidates/mine', { cluster_id: cluster.value.id })
    const data = res?.data || {}
    if (data.skipped) {
      ElMessage.info('该话题已经挖掘过')
      await loadCluster()
      miningRunning.value = false
      panelMode.value = 'candidates'
      syncCandidates()
      return
    }
    const runId = data.run_id
    if (runId) {
      // 立即查一次，之后定时轮询
      pollProgress(runId)
      pollTimer = setInterval(() => pollProgress(runId), POLL_INTERVAL)
    }
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '挖掘失败'
    ElMessage.error(`挖掘失败: ${detail}`)
    miningRunning.value = false
  }
}

const goOutline = () => {
  router.push({
    path: '/creation/new',
    query: {
      cluster_id: cluster.value?.id,
      topic_title: cluster.value?.core_title_zh || cluster.value?.latest_title,
    }
  })
}

onMounted(() => {
  loadCluster()
})

onUnmounted(() => {
  stopPolling()
})

const loadCluster = async () => {
  loading.value = true
  try {
    const res = await get(`/topic-clusters/${route.params.id}`)
    cluster.value = res.data
    // 如果已有候选，同步到本地
    if (cluster.value?.candidates?.length > 0) {
      syncCandidates()
    }
  } catch (error) {
    if (error.response?.status === 404) {
      cluster.value = null
    } else {
      ElMessage.error('加载话题详情失败')
    }
  } finally {
    loading.value = false
  }
}

const formatFreshness = (val) => {
  const map = { 'today': '今日', 'yesterday': '昨日', 'earlier': '两天前' }
  return map[val] || val
}

const formatRelativeTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return '刚刚'
  if (h < 24) return `${h} 小时前`
  const days = Math.floor(h / 24)
  if (days < 30) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}

const isNew = (cluster) => {
  if (!cluster.created_at) return false
  const created = new Date(cluster.created_at)
  const now = new Date()
  return (now - created) < 60 * 60 * 1000
}

const getScoreColor = (score) => {
  if (!score) return 'var(--ink-3)'
  if (score >= 7) return 'var(--leaf)'
  if (score >= 5) return 'var(--sand)'
  return 'var(--crimson)'
}

const startCreation = (candidate) => {
  router.push({
    path: '/creation/new',
    query: {
      candidate_id: candidate.id,
      cluster_id: cluster.value?.id,
      topic_title: candidate.title,
      topic_direction: candidate.direction,
    }
  })
}
</script>

<style scoped>
/* ===== 布局 ===== */
.topic-cluster-detail {
  padding: 0 32px 24px;
  max-width: 960px;
  margin: 0 auto;
}

.detail-layout {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.detail-main {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ===== 话题卡片 ===== */
.detail-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.card-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.flex-spacer {
  flex: 1 0 0;
  min-height: 16px;
}

.source-section {
  flex: 0 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.card-body > * { flex-shrink: 0; }
.card-body > .source-section { flex-shrink: 1; }

/* Section Bar */
.section-bar {
  width: 4px;
  height: 15px;
  border-radius: 2px;
  background: var(--clay);
}

/* Tags */
.tag-type {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}

.tag-freshness {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--sand-soft);
  color: #8a6d33;
}

.tag-new {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--clay);
  color: #fff;
}

.tag-heat {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(92,138,92,.12);
  color: var(--leaf);
}

.tag-mined-detail {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--leaf);
  color: var(--paper);
}

.tag-needs-update-detail {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #E6A23C;
  color: #fff;
}

/* Element Tags */
.element-tag {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 4px 10px;
  background: #F3EDE7;
  border: 1px solid #D5CCC4;
  border-radius: 999px;
}

.element-key {
  font-size: 10px;
  color: #9C8B7A;
  font-weight: 600;
}

.element-val {
  font-size: 11px;
  color: var(--ink-3);
  font-weight: 600;
}

/* Source Cards */
.source-card {
  display: block;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  text-decoration: none;
  transition: all 0.18s;
}

.source-card:hover {
  border-color: var(--clay);
  background: var(--clay-tint);
}

.source-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.source-platform {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 999px;
  background: #F3EDE7;
  color: #9C8B7A;
  font-size: 10px;
  font-weight: 500;
  border: 1px solid #D5CCC4;
}

.source-time {
  margin-left: auto;
  font-size: 11px;
  color: var(--ink-4);
}

.source-commercial-badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 999px;
  background: #FFE3B3;
  color: #7A3E00;
  border: 1px solid #F1C77F;
  font-size: 10px;
  font-weight: 600;
}

.source-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.source-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-link {
  color: var(--clay-deep);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

/* Source Item (legacy) */
.source-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  text-decoration: none;
  transition: all 0.15s;
}

.source-item:hover {
  border-color: var(--clay);
  background: var(--clay-tint);
}

.source-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--clay);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.source-url-text {
  flex: 1;
  font-size: 13px;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-arrow {
  color: var(--clay);
  font-size: 16px;
  flex-shrink: 0;
}

.source-scroll {
  flex: 1;
  min-height: 0;
  /* 默认只显示约 2.5 条，更多原文滚动查看 */
  max-height: 166px;
  overflow-y: auto;
  padding-right: 4px;
}

/* 原文来源滚动条：细窄、低调 */
.source-scroll::-webkit-scrollbar {
  width: 6px;
}
.source-scroll::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 3px;
}
.source-scroll::-webkit-scrollbar-thumb:hover {
  background: var(--ink-4);
}
.source-scroll::-webkit-scrollbar-track {
  background: transparent;
}

/* ===== 挖掘进度（内联） ===== */
.mining-inline-section {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  padding: 24px 28px;
}

.agent-bars {
  display: flex;
  flex-direction: column;
  gap: 0;
}

@keyframes pulse-ring {
  0%, 100% { box-shadow: 0 0 0 3px rgba(204, 120, 92, 0.2); }
  50% { box-shadow: 0 0 0 6px rgba(204, 120, 92, 0.1); }
}

/* ===== 候选选题瀑布流 ===== */
.candidates-section {
  padding-top: 8px;
}

.candidates-header {
  margin-bottom: 20px;
}

.candidates-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
}

.candidates-count {
  font-size: 13px;
  color: var(--ink-4);
  font-weight: 400;
}

/* 瀑布流布局 - 横向排列 */
.waterfall {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.waterfall-card {
  flex: 1 1 calc(50% - 8px);
  min-width: 280px;
  max-width: calc(50% - 8px);
  display: flex;
  flex-direction: column;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 20px;
  transition: border-color 0.18s, box-shadow 0.18s;
  animation: cardAppear 0.35s cubic-bezier(.32,.72,0,1) both;
}

.waterfall-card:hover {
  border-color: var(--clay-soft);
  box-shadow: 0 4px 12px rgba(31,31,30,.06);
}

/* 卡片头部 */
.wc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.wc-index {
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--clay);
  line-height: 1;
}

.wc-direction {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}

.wc-routine {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: var(--sand-soft);
  color: #8a6d33;
}

.wc-score {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 28px;
  padding: 0 8px;
  border-radius: 8px;
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
}

.score-high {
  background: rgba(92,138,92,.12);
  color: var(--leaf);
}

.score-mid {
  background: var(--sand-soft);
  color: #8a6d33;
}

.score-low {
  background: #F0EBE5;
  color: var(--ink-4);
}

/* 卡片标题 */
.wc-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.5;
  margin-bottom: 10px;
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
}

/* 卡片摘要 */
.wc-summary {
  font-size: 13px;
  line-height: 1.75;
  color: var(--ink-3);
  margin-bottom: 12px;
}

/* 可写性 */
.wc-feasibility {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
  font-size: 12px;
}

.wc-feas-label {
  font-weight: 600;
  color: var(--ink-4);
}

.wc-feas-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.feas-pass {
  background: #e6f7e6;
  color: #2d7a2d;
}

.feas-weak {
  background: #fff7e6;
  color: #b37a00;
}

.feas-fail {
  background: #fde8e8;
  color: #c53030;
}

.wc-feas-score {
  font-weight: 700;
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
  color: var(--ink-3);
}

/* 操作按钮 */
.wc-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;        /* 把操作行顶到卡片底部，留白落在简介和按钮之间 */
  padding-top: 14px;
  border-top: 1px solid var(--line);
}

.btn-copy {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  border: none;
  color: var(--ink-3);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s;
}
.btn-copy:hover { color: var(--ink); }
.copy-icon { font-size: 14px; }

.btn-write-outline {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  background: var(--clay);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(204,120,92,.20);
  transition: background 0.15s, transform 0.15s;
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
}
.btn-write-outline:hover { background: var(--clay-deep); }
.btn-write-outline:active { transform: translateY(1px); }

/* ===== Creative Button ===== */
.btn-creative {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: transparent;
  color: var(--clay-deep);
  border: 1px solid var(--line);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.18s;
}

.btn-creative:hover:not(:disabled) {
  background: var(--clay-tint);
  border-color: var(--clay-soft);
  color: var(--clay);
}

.btn-creative:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-re-mine {
  border-color: #E6A23C;
  color: #E6A23C;
}
.btn-re-mine:hover:not(:disabled) {
  background: #E6A23C;
  border-color: #E6A23C;
  color: #fff;
}

/* ===== 动画 ===== */
.fade-in {
  animation: fadeIn 0.28s cubic-bezier(.32,.72,0,1);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes cardAppear {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 响应式 ===== */
@media (max-width: 700px) {
  .topic-cluster-detail {
    padding: 0 16px 24px;
  }

  .waterfall {
    flex-direction: column;
  }

  .waterfall-card {
    flex: 1 1 100%;
    max-width: 100%;
  }

  .mining-inline-section {
    padding: 16px 18px;
  }
}
</style>
