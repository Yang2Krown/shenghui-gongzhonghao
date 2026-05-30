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
      <!-- 双栏布局：左侧详情 + 右侧面板 -->
      <div class="detail-layout" :class="{ 'has-panel': showPanel }">
        <!-- 左栏：话题详情 -->
        <div class="detail-main">
          <div class="detail-card">
            <div class="p-6">
              <!-- 标签行 -->
              <div class="flex flex-wrap gap-2 mb-4">
                <span v-if="cluster.info_type" class="tag-type">{{ cluster.info_type }}</span>
                <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
                <span v-if="isNew(cluster)" class="tag-new">NEW</span>
                <span v-if="cluster.heat_score" class="tag-heat">热度 {{ cluster.heat_score?.toFixed(0) }}</span>
              </div>

              <!-- 标题 -->
              <h1 class="font-serif" style="font-size: 28px; font-weight: 500; color: var(--ink); line-height: 1.25;">
                {{ cluster.core_title_zh || cluster.latest_title || cluster.core_title }}
              </h1>

              <!-- 摘要 -->
              <p v-if="cluster.summary_zh || cluster.summary"
                 class="mt-4"
                 style="color: #6B6862; font-size: 15px; line-height: 1.75;
                        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
                {{ cluster.summary_zh || cluster.summary }}
              </p>

              <!-- 信息要素 -->
              <div v-if="cluster.elements && Object.keys(cluster.elements).length > 0" class="mt-5">
                <div class="flex items-center gap-2 mb-3">
                  <span class="section-bar"></span>
                  <h4 class="t-h4 c-ink">信息要素</h4>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span v-for="(val, key) in cluster.elements" :key="key" class="element-tag" v-show="val">
                    <span class="element-key">{{ key }}</span>
                    <span class="element-val">{{ val }}</span>
                  </span>
                </div>
              </div>

              <!-- 原文来源 -->
              <div v-if="cluster.raw_infos?.length > 0 || cluster.source_urls?.length > 0" class="mt-6 pt-5" style="border-top: 1px solid var(--line);">
                <div class="flex items-center gap-2 mb-4">
                  <span class="section-bar"></span>
                  <h4 class="t-h4 c-ink">原文来源</h4>
                  <span class="t-xs c-ink4">{{ cluster.raw_infos?.length || cluster.source_urls?.length }} 篇</span>
                </div>

                <!-- 完整原文卡片 -->
                <div v-if="cluster.raw_infos?.length > 0" class="flex flex-col gap-2">
                  <a
                    v-for="raw in cluster.raw_infos"
                    :key="raw.id"
                    :href="raw.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="source-card"
                  >
                    <div class="source-card-header">
                      <span class="source-platform">{{ raw.source_name }}</span>
                      <span v-if="raw.published_at" class="source-time">
                        {{ formatRelativeTime(raw.published_at) }}
                      </span>
                    </div>
                    <div class="source-title">{{ raw.title }}</div>
                    <div v-if="raw.summary" class="source-summary">{{ raw.summary }}</div>
                    <div class="source-footer">
                      <span v-if="raw.author" class="source-author">{{ raw.author }}</span>
                      <span class="source-link">阅读原文 &rarr;</span>
                    </div>
                  </a>
                </div>

                <!-- 兼容旧的 URL 列表 -->
                <div v-else class="flex flex-col gap-2">
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
              <div class="flex justify-between items-center mt-5 pt-4" style="border-top: 1px solid var(--line);">
                <span class="t-xs c-ink4">
                  主要来源 · {{ cluster.source_count || cluster.source_urls?.length || 0 }} 篇原文
                </span>
                <!-- 已挖掘：显示"选题角度"；未挖掘：显示"用它创作" -->
                <button
                  v-if="isMined"
                  class="btn-creative"
                  @click="showMinedCandidates"
                  :disabled="showPanel"
                >
                  <span class="btn-creative-icon">✨</span>
                  选题角度
                </button>
                <button
                  v-else
                  class="btn-creative"
                  @click="startMining"
                  :disabled="miningRunning"
                >
                  <span class="btn-creative-icon">✨</span>
                  {{ miningRunning ? '挖掘中...' : '用它创作' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：面板（挖掘中 / 已挖掘的选题角度） -->
        <div v-if="showPanel" class="detail-panel">
          <div class="panel-inner">
            <!-- Panel Header -->
            <div class="panel-header">
              <div>
                <div class="flex items-center gap-2">
                  <span class="panel-icon">✨</span>
                  <h3 class="t-h4 c-ink">{{ panelTitle }}</h3>
                </div>
                <p class="t-xs c-ink3 mt-1">{{ panelSubtitle }}</p>
              </div>
              <button class="panel-close" @click="closePanel">&times;</button>
            </div>

            <!-- Panel Body -->
            <div class="panel-body">
              <!-- 挖掘中状态 -->
              <div v-if="miningRunning" class="loading-state">
                <el-icon class="is-loading" :size="24" style="color: var(--clay);"><Loading /></el-icon>
                <p class="mt-2" style="color: #6B6862;">正在挖掘选题，请稍候…</p>
                <div v-if="miningStepText" class="mt-2" style="font-size: 13px; color: var(--ink-3);">
                  {{ miningStepText }}
                </div>
              </div>

              <!-- 已挖掘：展示选题角度列表 -->
              <div v-else-if="panelCandidates.length > 0" class="fade-in">
                <div class="flex items-center justify-between mb-3">
                  <span class="t-sm c-ink3" style="font-weight: 600;">推荐选题 · {{ panelCandidates.length }} 个</span>
                </div>

                <div v-for="(candidate, i) in panelCandidates" :key="candidate.id" class="angle-card slide-up" :style="{ animationDelay: `${i * 50}ms` }">
                  <div class="flex justify-between items-center mb-2">
                    <span class="verdict-badge-sm" :class="getVerdictClass(candidate.verdict)">
                      {{ getVerdictIcon(candidate.verdict) }}
                    </span>
                    <div class="font-serif" :style="{ color: getScoreColor(candidate.weighted_score), fontSize: '24px', fontWeight: 500 }">
                      {{ candidate.weighted_score?.toFixed(1) || '-' }}
                    </div>
                  </div>
                  <h4 class="t-h4 c-ink" style="line-height: 1.4;">{{ candidate.title }}</h4>
                  <p v-if="candidate.summary" class="t-sm c-ink3 mt-1.5">{{ candidate.summary }}</p>
                  <p v-else class="t-sm c-ink3 mt-1.5">{{ candidate.value_promise }}</p>
                  <div class="flex gap-2 mt-3">
                    <button class="btn-use-angle" @click="startCreation(candidate)">
                      用此选题创作 <span style="font-size: 13px;">→</span>
                    </button>
                  </div>
                </div>
              </div>

              <!-- 空状态 -->
              <div v-else class="empty-state">
                <p style="color: #6B6862;">暂无选题数据</p>
              </div>
            </div>

            <!-- Panel Footer -->
            <div class="panel-footer">
              <button class="btn btn-clay" style="flex: 1;" @click="goOutline">
                直接写大纲
              </button>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'
import { useAgentProgress } from '@/composables/useAgentProgress'

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

// 判断是否已挖掘
const isMined = computed(() => {
  return cluster.value?.mined === true || (cluster.value?.candidates?.length > 0)
})

// 面板状态
const showPanel = ref(false)
const panelMode = ref('mining') // 'mining' | 'candidates'
const miningRunning = ref(false)
const miningStepText = ref('')

// Agent 进度（SSE）
const miningProgress = useAgentProgress()

// 面板标题
const panelTitle = computed(() => {
  if (panelMode.value === 'mining') return '挖掘选题中'
  return '选题角度'
})

const panelSubtitle = computed(() => {
  if (panelMode.value === 'mining') return 'AI 正在分析资讯，生成候选选题…'
  return `基于「${cluster.value?.core_title_zh || cluster.value?.latest_title || ''}」生成`
})

// 面板中的候选列表
const panelCandidates = computed(() => {
  if (panelMode.value === 'candidates') {
    return cluster.value?.candidates || []
  }
  return []
})

// 显示已挖掘的选题
const showMinedCandidates = () => {
  panelMode.value = 'candidates'
  showPanel.value = true
}

// 开始挖掘
const startMining = async () => {
  if (!cluster.value?.id) return
  miningRunning.value = true
  panelMode.value = 'mining'
  showPanel.value = true

  // 监听 SSE 结果
  const stopWatch = watch(() => miningProgress.result.value, (newResult) => {
    if (newResult) {
      ElMessage.success(`挖掘完成，生成 ${newResult.total_candidates ?? '?'} 个候选`)
      miningRunning.value = false
      loadCluster().then(() => {
        panelMode.value = 'candidates'
      })
      stopWatch()
    }
  })

  // 监听 SSE 错误
  const stopErrorWatch = watch(() => miningProgress.error.value, (newError) => {
    if (newError) {
      ElMessage.error(`挖掘失败: ${newError}`)
      miningRunning.value = false
      stopErrorWatch()
    }
  })

  // 监听步骤更新
  const stopStepsWatch = watch(() => miningProgress.steps.value, (steps) => {
    const current = steps[miningProgress.currentStepIndex.value]
    if (current) {
      miningStepText.value = current.action
    }
  })

  try {
    const res = await post('/topic-candidates/mine', { cluster_id: cluster.value.id })
    const data = res?.data || {}
    if (data.skipped) {
      ElMessage.info('该话题已经挖掘过')
      await loadCluster()
      miningRunning.value = false
      panelMode.value = 'candidates'
      return
    }
    const runId = data.run_id
    if (runId) {
      miningProgress.start(`/api/v1/topic-candidates/stream/${runId}`)
    }
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message || '挖掘失败'
    ElMessage.error(`挖掘失败: ${detail}`)
    miningRunning.value = false
  }
}

const closePanel = () => {
  showPanel.value = false
  miningRunning.value = false
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
  miningProgress.stop()
})

const loadCluster = async () => {
  loading.value = true
  try {
    const res = await get(`/topic-clusters/${route.params.id}`)
    cluster.value = res.data
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
  const map = { '24h': '24h 内', '7d': '7 天内', '30d': '30 天内', 'expired': '大于 30 天' }
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

const getVerdictIcon = (verdict) => {
  const icons = { selected: 'S', backup: 'B', rejected: 'R', vetoed: 'V' }
  return icons[verdict] || '?'
}

const getVerdictClass = (verdict) => {
  const classes = {
    selected: 'verdict-selected',
    backup: 'verdict-backup',
    rejected: 'verdict-rejected',
    vetoed: 'verdict-vetoed',
  }
  return classes[verdict] || ''
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
/* 双栏布局 */
.detail-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  max-width: 820px;
  margin: 0 auto;
  transition: max-width 0.32s cubic-bezier(.32,.72,0,1);
}

.detail-layout.has-panel {
  max-width: 1280px;
}

.detail-main {
  flex: 1;
  min-width: 0;
}

.detail-panel {
  width: 460px;
  flex-shrink: 0;
  position: relative;
}

.panel-inner {
  display: flex;
  flex-direction: column;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: var(--sh-2);
  overflow: hidden;
}

/* Panel Header */
.panel-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-icon {
  font-size: 18px;
}

.panel-close {
  background: transparent;
  border: none;
  font-size: 20px;
  line-height: 1;
  padding: 2px 8px;
  cursor: pointer;
  color: var(--ink-4);
  transition: color 0.15s;
}

.panel-close:hover {
  color: var(--ink);
}

/* Panel Body */
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  max-height: 600px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

/* Angle Card */
.angle-card {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--paper);
  margin-bottom: 12px;
  transition: all 0.18s;
}

.angle-card:hover {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-1);
}

.verdict-badge-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
}

.btn-use-angle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--ink);
  color: var(--paper);
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-use-angle:hover {
  background: var(--ink-2);
}

/* Panel Footer */
.panel-footer {
  padding: 14px 24px;
  border-top: 1px solid var(--line);
  background: var(--paper);
  display: flex;
  gap: 10px;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-family: inherit;
  font-weight: 500;
  font-size: 14px;
  border-radius: 10px;
  padding: 9px 16px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.18s cubic-bezier(.32,.72,0,1);
  white-space: nowrap;
}

.btn-clay {
  background: var(--clay);
  color: #fff;
  box-shadow: 0 8px 24px rgba(204,120,92,.18);
}

.btn-clay:hover {
  background: var(--clay-deep);
}

/* Creative Button */
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

.btn-creative-icon {
  font-size: 14px;
}

/* Detail Card */
.detail-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}

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

/* Element Tags */
.element-tag {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 6px 13px;
  background: var(--clay-tint);
  border: 1px solid var(--clay-soft);
  border-radius: 999px;
}

.element-key {
  font-size: 12px;
  color: var(--clay-deep);
  font-weight: 600;
}

.element-val {
  font-size: 13px;
  color: var(--ink-2);
  font-weight: 600;
}

/* Source Cards */
.source-card {
  display: block;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px 14px;
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
  gap: 8;
  margin-bottom: 4px;
}

.source-platform {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--clay-tint);
  color: var(--clay-deep);
  font-size: 11px;
  font-weight: 500;
  border: 1px solid var(--clay-soft);
}

.source-time {
  font-size: 12px;
  color: var(--ink-4);
}

.source-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-summary {
  font-size: 12px;
  color: var(--ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.source-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 12px;
}

.source-author {
  color: var(--ink-4);
}

.source-link {
  color: var(--clay-deep);
  font-weight: 500;
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

/* Animation */
.fade-in {
  animation: fadeIn 0.28s cubic-bezier(.32,.72,0,1);
}

.slide-up {
  animation: slideUp 0.3s cubic-bezier(.32,.72,0,1) both;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
