<template>
  <div class="topic-cluster-detail">
    <!-- 返回按钮 -->
    <div class="mb-4">
      <el-button text @click="goBack" style="color: #6B6862;">
        &larr; 返回内容资讯
      </el-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <span class="ml-2" style="color: #6B6862;">加载中...</span>
    </div>

    <template v-else-if="cluster">
      <div class="detail-layout" :class="{ 'is-split': anglePanelVisible }">
        <!-- 左侧：话题详情卡片 -->
        <div class="detail-card">
          <div class="p-6">
            <h1 class="font-serif mb-1" style="font-size: 28px; font-weight: 500; color: var(--ink); line-height: 1.3;">
              {{ cluster.core_title_zh || cluster.core_title }}
            </h1>
            <p v-if="cluster.core_title_zh && cluster.core_title_zh !== cluster.core_title"
               class="mb-3" style="font-size: 13px; color: #9A968D; line-height: 1.5;">
              {{ cluster.core_title }}
            </p>
            <div v-else class="mb-3"></div>

            <div class="flex flex-wrap gap-2 mb-4">
              <span v-if="cluster.info_type" class="tag-type">{{ cluster.info_type }}</span>
              <span v-if="cluster.direction" class="tag-direction">{{ cluster.direction }}</span>
              <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
              <span v-if="cluster.low_fan_hit" class="tag-hot">低粉爆款</span>
              <span v-if="cluster.mined" class="tag-mined">已挖掘</span>
              <span v-else class="tag-unmined">未挖掘</span>
            </div>

            <p v-if="cluster.summary_zh || cluster.summary" class="mb-1"
               style="color: #3A3935; font-size: 15px; line-height: 1.7;">
              {{ cluster.summary_zh || cluster.summary }}
            </p>
            <p v-if="cluster.summary_zh && cluster.summary && cluster.summary_zh !== cluster.summary"
               class="mb-4" style="color: #9A968D; font-size: 12px; line-height: 1.6; font-style: italic;">
              {{ cluster.summary }}
            </p>

            <div v-if="cluster.elements && Object.keys(cluster.elements).length > 0" class="mb-4">
              <h4 style="color: #3A3935; font-size: 14px; font-weight: 600; margin-bottom: 8px;">信息要素</h4>
              <div class="flex flex-wrap gap-2">
                <span v-for="(val, key) in cluster.elements" :key="key" class="element-tag" v-show="val">
                  {{ key }}: {{ val }}
                </span>
              </div>
            </div>

            <div v-if="cluster.raw_infos?.length > 0 || cluster.source_urls?.length > 0" class="mt-4 pt-4" style="border-top: 1px solid var(--line);">
              <h4 class="mb-3" style="color: #3A3935; font-size: 14px; font-weight: 600;">
                图文来源
                <span style="color: #6B6862; font-weight: 400;">({{ cluster.raw_infos?.length || cluster.source_urls?.length }})</span>
              </h4>
              <div v-if="cluster.raw_infos?.length > 0" class="space-y-2">
                <a v-for="raw in cluster.raw_infos" :key="raw.id" :href="raw.url" target="_blank" rel="noopener noreferrer" class="source-item">
                  <span class="source-card-platform-sm">{{ raw.source_name }}</span>
                  <span class="source-title-text">{{ raw.title }}</span>
                  <span v-if="raw.published_at" class="source-time-sm">{{ formatRelativeTime(raw.published_at) }}</span>
                  <span class="source-arrow">&rarr;</span>
                </a>
              </div>
              <div v-else class="space-y-2">
                <a v-for="(url, idx) in cluster.source_urls" :key="idx" :href="url" target="_blank" rel="noopener noreferrer" class="source-item">
                  <span class="source-index">{{ idx + 1 }}</span>
                  <span class="source-url">{{ url }}</span>
                  <span class="source-arrow">&rarr;</span>
                </a>
              </div>
            </div>

            <div class="mt-5 pt-4" style="border-top: 1px solid var(--line);">
              <el-button
                :loading="angleMining"
                @click="startAngleMining"
                style="background: var(--clay); color: var(--paper); border: none; border-radius: 10px; font-weight: 500;"
              >
                <svg v-if="!angleMining" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M14.5 6a3.5 3.5 0 0 0-4.9 4.4L3 17v4h4l6.6-6.6A3.5 3.5 0 0 0 18 9.5"/><circle cx="17" cy="7" r="0.5" fill="currentColor"/></svg>
                {{ cluster.candidates?.length > 0 ? '查看创作角度' : '挖掘创作角度' }}
              </el-button>
            </div>
          </div>
        </div>

        <!-- 右侧：挖掘面板 -->
        <div class="angle-panel">
          <div class="angle-panel-header">
            <h3 class="font-serif" style="font-size: 18px; font-weight: 500; color: var(--ink);">创作角度</h3>
            <button class="angle-panel-close" @click="closeAnglePanel">&times;</button>
          </div>
          <div class="angle-panel-body">
            <div v-if="angleMining" class="mb-4">
              <AgentStatusBar
                v-for="(step, i) in angleSteps"
                :key="i"
                :agent-name="step.agent"
                :action="step.action"
                :is-active="i === angleStepIndex"
                :show-progress="i === angleStepIndex"
                :percent="i === angleStepIndex ? angleStepPercent : (i < angleStepIndex ? 100 : 0)"
                :avatar="step.avatar"
                class="mb-2"
              />
            </div>

            <div v-if="angleResults.length > 0" class="space-y-2">
              <div v-for="candidate in angleResults" :key="candidate.id" class="angle-result-card" @click="toggleAngleExpand(candidate)">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span class="verdict-badge-sm" :class="getVerdictClass(candidate.verdict)">{{ getVerdictIcon(candidate.verdict) }}</span>
                      <span style="font-size: 15px; font-weight: 600; color: var(--ink); line-height: 1.4;">{{ candidate.title }}</span>
                    </div>
                    <p v-if="candidate.value_promise" style="font-size: 13px; color: #6B6862; line-height: 1.55; margin-bottom: 6px;">{{ candidate.value_promise }}</p>
                    <div class="flex flex-wrap gap-1.5 mb-2">
                      <span v-if="candidate.direction" class="tag-direction-xs">{{ candidate.direction }}</span>
                      <span v-if="candidate.routine" class="tag-routine-xs">{{ candidate.routine }}</span>
                      <span v-for="dim in (candidate.dimension_combo || []).slice(0, 2)" :key="dim" class="tag-dim-xs">{{ dim }}</span>
                    </div>

                    <!-- Agent 评议摘要 -->
                    <div v-if="candidate.persona_reviews?.length" class="persona-reviews">
                      <span v-for="pr in candidate.persona_reviews.slice(0, 3)" :key="pr.persona" class="persona-item">
                        {{ pr.persona }}: <strong>{{ pr.score }}</strong>
                      </span>
                    </div>

                    <!-- 6维评分（展开时显示） -->
                    <div v-if="expandedAngleId === candidate.id && candidate.score" class="score-grid mt-2">
                      <div v-for="(label, key) in dimensionLabels" :key="key" class="score-cell">
                        <span class="score-cell-label">{{ label }}</span>
                        <span class="score-cell-num">{{ candidate.score[key]?.toFixed(1) || '-' }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="ml-3 text-right flex-shrink-0">
                    <div class="font-serif" :style="{ color: getScoreColor(candidate.weighted_score), fontSize: '24px', fontWeight: 500, lineHeight: 1.1 }">{{ candidate.weighted_score?.toFixed(1) || '-' }}</div>
                    <div style="font-size: 11px; color: #9A968D; margin-top: 2px;">加权总分</div>
                    <div v-if="!candidate.veto_passed" class="mt-1">
                      <span style="display: inline-block; padding: 1px 6px; border-radius: 999px; font-size: 10px; background: var(--crimson); color: var(--paper);">一票否决</span>
                    </div>
                  </div>
                </div>
                <div class="mt-2" style="font-size: 12px; color: var(--clay); font-weight: 500; cursor: pointer;" @click.stop="useAngle(candidate)">用此角度写大纲 &rarr;</div>
              </div>
            </div>

            <div v-if="!angleMining && angleResults.length === 0" class="text-center py-16">
              <p style="color: #6B6862; font-size: 14px;">点击左侧按钮开始挖掘创作角度</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="text-center py-20">
      <h3 style="color: #3A3935; font-size: 18px;">话题不存在</h3>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
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
    router.push('/')
  }
}

const loading = ref(true)
const cluster = ref(null)

const anglePanelVisible = ref(false)
const angleMining = ref(false)
const angleResults = ref([])
const expandedAngleId = ref(null)

const dimensionLabels = {
  pain_point: '痛点直击',
  value_density: '价值密度',
  propagation: '传播触发',
  differentiation: '差异化',
  freshness: '新鲜度',
  audience_fit: '受众适配',
}

const angleProgress = useAgentProgress()
const angleSteps = angleProgress.steps
const angleStepIndex = angleProgress.currentStepIndex
const angleStepPercent = angleProgress.stepPercent

onMounted(() => { loadCluster() })
onUnmounted(() => { angleProgress.stop() })

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

const startAngleMining = async () => {
  anglePanelVisible.value = true

  // 已挖掘过，直接从 cluster.candidates 读取展示
  if (cluster.value?.candidates?.length > 0) {
    angleResults.value = cluster.value.candidates
    return
  }

  // 未挖掘，走 SSE 挖掘流程
  angleMining.value = true
  angleResults.value = []

  const stopWatch = watch(() => angleProgress.result.value, (newResult) => {
    if (newResult) {
      angleMining.value = false
      loadCluster().then(() => {
        angleResults.value = cluster.value?.candidates || []
      })
      stopWatch()
    }
  })

  const stopErrorWatch = watch(() => angleProgress.error.value, (newError) => {
    if (newError) {
      angleMining.value = false
      ElMessage.error(`挖掘失败: ${newError}`)
      stopErrorWatch()
    }
  })

  try {
    const res = await post('/topic-candidates/mine', { cluster_id: cluster.value.id })
    const data = res?.data || {}
    const runId = data.run_id
    if (runId) {
      angleProgress.start(`/api/v1/topic-candidates/stream/${runId}`)
    }
  } catch (error) {
    angleMining.value = false
    const detail = error?.response?.data?.detail || error?.message || '挖掘失败'
    ElMessage.error(`挖掘失败: ${detail}`)
  }
}

const closeAnglePanel = () => {
  anglePanelVisible.value = false
  angleProgress.stop()
}

const toggleAngleExpand = (candidate) => {
  expandedAngleId.value = expandedAngleId.value === candidate.id ? null : candidate.id
}

const useAngle = (candidate) => {
  router.push({
    path: '/outline',
    query: { angle: candidate.title, candidate_id: candidate.id, cluster_id: cluster.value?.id }
  })
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

const getVerdictIcon = (v) => ({ selected: 'S', backup: 'B', rejected: 'R', vetoed: 'V' }[v] || '?')
const getVerdictClass = (v) => ({ selected: 'verdict-selected', backup: 'verdict-backup', rejected: 'verdict-rejected', vetoed: 'verdict-vetoed' }[v] || '')
const getScoreColor = (s) => {
  if (!s) return 'var(--ink-3)'
  if (s >= 7) return 'var(--leaf)'
  if (s >= 5) return 'var(--sand)'
  return 'var(--crimson)'
}
</script>

<style scoped>
.detail-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: center;
  max-width: 1100px;
  margin: 0 auto;
}

.detail-layout.is-split {
  justify-content: stretch;
}

/* 左侧卡片 */
.detail-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  width: 800px;
  max-width: 100%;
  flex-shrink: 0;
  transition: width 0.35s cubic-bezier(.32, .72, 0, 1);
}

.is-split > .detail-card {
  width: 50%;
  min-width: 0;
}

/* 右侧面板：50% 宽度，和左侧等宽 */
.angle-panel {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  overflow: hidden;
  width: 0;
  opacity: 0;
  flex-shrink: 0;
  border-width: 0;
  transition: width 0.35s cubic-bezier(.32, .72, 0, 1), opacity 0.25s ease, border-width 0s 0.35s;
}

.is-split > .angle-panel {
  width: 50%;
  opacity: 1;
  border-width: 1px;
  transition: width 0.35s cubic-bezier(.32, .72, 0, 1), opacity 0.25s ease, border-width 0s;
}

.angle-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--line);
}

.angle-panel-close {
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 8px;
  font-size: 18px;
  color: #6B6862;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.angle-panel-close:hover { background: var(--bone); }

.angle-panel-body {
  padding: 14px 18px;
  max-height: calc(100vh - 140px);
  overflow-y: auto;
}

.angle-result-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(.32, .72, 0, 1);
}
.angle-result-card:hover {
  border-color: var(--clay);
  box-shadow: 0 4px 12px rgba(204, 120, 92, 0.10);
  transform: translateY(-1px);
}

.verdict-badge-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.verdict-selected { background: var(--leaf); color: var(--paper); }
.verdict-backup { background: var(--sand); color: var(--paper); }
.verdict-rejected { background: var(--crimson); color: var(--paper); }
.verdict-vetoed { background: var(--bone); color: #6B6862; }

.tag-direction-xs {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: #C9D4CD;
  color: var(--pine);
}
.tag-routine-xs {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: var(--bone);
  color: #3A3935;
  border: 1px solid var(--line);
}

.tag-dim-xs {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: #ECDCBF;
  color: var(--sand);
}

/* Agent 评议摘要 */
.persona-reviews {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #9A968D;
}
.persona-item strong {
  color: #3A3935;
}

/* 6维评分网格 */
.score-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px 12px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}
.score-cell {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.score-cell-label {
  font-size: 11px;
  color: #9A968D;
}
.score-cell-num {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  font-family: 'GT Sectra', 'Source Han Serif SC', serif;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  text-decoration: none;
  transition: all 0.15s;
}
.source-item:hover { border-color: var(--clay); background: var(--clay-tint); }

.source-card-platform-sm {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--clay-tint);
  color: var(--clay-deep);
  font-size: 11px;
  font-weight: 500;
  border: 1px solid var(--clay-soft);
  flex-shrink: 0;
}
.source-title-text {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #3A3935;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-time-sm { font-size: 11px; color: #9A968D; flex-shrink: 0; }
.source-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--clay);
  color: var(--paper);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.source-url {
  flex: 1;
  font-size: 13px;
  color: #3A3935;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-arrow { color: var(--clay); font-size: 14px; flex-shrink: 0; }

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
.tag-direction {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #C9D4CD;
  color: var(--pine);
}
.tag-freshness {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #ECDCBF;
  color: var(--sand);
}
.tag-hot {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--crimson);
  color: var(--paper);
}
.tag-mined {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--leaf);
  color: var(--paper);
}
.tag-unmined {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--bone);
  color: #6B6862;
  border: 1px solid var(--line);
}
.element-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  background: var(--bone);
  color: #3A3935;
  border: 1px solid var(--line);
}
</style>
