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
      <!-- 话题详情卡片 -->
      <div class="detail-card mb-6">
        <div class="p-6">
          <!-- 标题：中文主显 + 英文原标题灰色小字 -->
          <h1 class="font-serif mb-1" style="font-size: 28px; font-weight: 500; color: var(--ink); line-height: 1.3;">
            {{ cluster.core_title_zh || cluster.core_title }}
          </h1>
          <p v-if="cluster.core_title_zh && cluster.core_title_zh !== cluster.core_title"
             class="mb-3" style="font-size: 13px; color: #9A968D; line-height: 1.5;">
            {{ cluster.core_title }}
          </p>
          <div v-else class="mb-3"></div>

          <!-- 标签行 -->
          <div class="flex flex-wrap gap-2 mb-4">
            <span v-if="cluster.info_type" class="tag-type">{{ cluster.info_type }}</span>
            <span v-if="cluster.direction" class="tag-direction">{{ cluster.direction }}</span>
            <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
            <span v-if="cluster.low_fan_hit" class="tag-hot">低粉爆款</span>
            <span v-if="cluster.mined" class="tag-mined">已挖掘</span>
            <span v-else class="tag-unmined">未挖掘</span>
          </div>

          <!-- 摘要：中文优先 + 英文原文小字回退 -->
          <p v-if="cluster.summary_zh || cluster.summary" class="mb-1"
             style="color: #3A3935; font-size: 15px; line-height: 1.7;">
            {{ cluster.summary_zh || cluster.summary }}
          </p>
          <p v-if="cluster.summary_zh && cluster.summary && cluster.summary_zh !== cluster.summary"
             class="mb-4" style="color: #9A968D; font-size: 12px; line-height: 1.6; font-style: italic;">
            {{ cluster.summary }}
          </p>

          <!-- 要素 -->
          <div v-if="cluster.elements && Object.keys(cluster.elements).length > 0" class="mb-4">
            <h4 style="color: #3A3935; font-size: 14px; font-weight: 600; margin-bottom: 8px;">信息要素</h4>
            <div class="flex flex-wrap gap-2">
              <span v-for="(val, key) in cluster.elements" :key="key" class="element-tag" v-show="val">
                {{ key }}: {{ val }}
              </span>
            </div>
          </div>

          <!-- 底部信息 -->
          <div class="flex items-center justify-between pt-4" style="border-top: 1px solid var(--line);">
            <div class="flex items-center space-x-4" style="font-size: 13px; color: #6B6862;">
              <span>热度: <strong style="color: var(--clay);">{{ cluster.heat_score?.toFixed(1) || '-' }}</strong></span>
              <span>{{ cluster.candidates?.length || 0 }} 个候选选题</span>
              <span>{{ cluster.source_urls?.length || 0 }} 篇原文</span>
            </div>
            <span class="text-xs" style="color: #9A968D;">
              {{ cluster.created_at ? new Date(cluster.created_at).toLocaleDateString() : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 原文来源区域：卡片化 -->
      <div v-if="cluster.raw_infos?.length > 0 || cluster.source_urls?.length > 0" class="source-section mb-6">
        <h3 class="font-serif mb-3" style="font-size: 18px; font-weight: 500; color: var(--ink);">
          原文来源
          <span style="color: #6B6862; font-size: 14px; font-weight: 400;">
            ({{ cluster.raw_infos?.length || cluster.source_urls?.length }})
          </span>
        </h3>

        <!-- 新版：完整原文卡片 -->
        <div v-if="cluster.raw_infos?.length > 0" class="space-y-3">
          <a
            v-for="raw in cluster.raw_infos"
            :key="raw.id"
            :href="raw.url"
            target="_blank"
            rel="noopener noreferrer"
            class="source-card"
          >
            <div class="source-card-body">
              <div class="source-card-header">
                <span class="source-card-platform">{{ raw.source_name }}</span>
                <span v-if="raw.published_at" class="source-card-time">
                  {{ formatRelativeTime(raw.published_at) }}
                </span>
              </div>
              <div class="source-card-title">{{ raw.title }}</div>
              <div v-if="raw.summary" class="source-card-summary">{{ raw.summary }}</div>
              <div class="source-card-footer">
                <span v-if="raw.author" class="source-card-author">{{ raw.author }}</span>
                <span class="source-card-link">阅读原文 &rarr;</span>
              </div>
            </div>
          </a>
        </div>

        <!-- 兼容：raw_infos 缺失时仍用旧的 URL 列表 -->
        <div v-else class="space-y-2">
          <a
            v-for="(url, idx) in cluster.source_urls"
            :key="idx"
            :href="url"
            target="_blank"
            rel="noopener noreferrer"
            class="source-item"
          >
            <span class="source-index">{{ idx + 1 }}</span>
            <span class="source-url">{{ url }}</span>
            <span class="source-arrow">&rarr;</span>
          </a>
        </div>
      </div>

      <!-- 候选选题 + Agent 反馈 双栏布局 -->
      <div class="mining-result-layout" :class="{ 'has-feedback': miningDone && agentFeedback.length }">
      <!-- 左栏：候选选题列表 -->
      <div class="mining-result-left">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-serif" style="font-size: 18px; font-weight: 500; color: var(--ink);">
            候选选题
            <span style="color: #6B6862; font-size: 14px; font-weight: 400;">({{ cluster.candidates?.length || 0 }})</span>
          </h3>
        </div>

        <!-- Agent 进度条（挖掘进行中） -->
        <div v-if="miningIsRunning" class="mb-4">
          <AgentStatusBar
            v-for="(step, i) in miningSteps"
            :key="i"
            :agent-name="step.agent"
            :action="step.action"
            :is-active="i === miningStepIndex"
            :show-progress="i === miningStepIndex"
            :percent="i === miningStepIndex ? miningStepPercent : (i < miningStepIndex ? 100 : 0)"
            :avatar="step.avatar"
            class="mb-2"
          />
        </div>

        <div v-if="!cluster.candidates || cluster.candidates.length === 0" class="text-center py-12" style="background: var(--paper); border: 1px solid var(--line); border-radius: 16px;">
          <p style="color: #6B6862;">该话题尚未挖掘候选选题</p>
          <el-button
            class="mt-3"
            :loading="miningIsRunning"
            @click="triggerMining"
            style="background: var(--clay); color: var(--paper); border: none; border-radius: 10px;"
          >
            立即挖掘
          </el-button>
        </div>

        <div v-else class="space-y-4">
          <div
            v-for="candidate in cluster.candidates"
            :key="candidate.id"
            class="candidate-card"
            @click="selectCandidate(candidate)"
          >
            <div class="p-5">
              <div class="flex items-start justify-between">
                <!-- 左侧内容 -->
                <div class="flex-1">
                  <!-- 标题和判定 -->
                  <div class="flex items-center gap-2 mb-2">
                    <span class="verdict-badge" :class="getVerdictClass(candidate.verdict)">
                      {{ getVerdictIcon(candidate.verdict) }}
                    </span>
                    <h4 style="font-size: 16px; font-weight: 600; color: var(--ink);">
                      {{ candidate.title }}
                    </h4>
                    <span v-if="candidate.persona_divergence_flag" style="color: var(--sand);" title="Persona 分歧度高">
                      !
                    </span>
                  </div>

                  <!-- 标签行 -->
                  <div class="flex flex-wrap gap-2 mb-2">
                    <span v-if="candidate.business_sensitive" class="tag-business-sensitive" title="设计文档 3.3 节：需人工复核">
                      ⚠️ 商务敏感
                    </span>
                    <span v-if="candidate.direction" class="tag-direction-sm">{{ candidate.direction }}</span>
                    <span v-if="candidate.routine" class="tag-routine">{{ candidate.routine }}</span>
                    <span
                      v-for="dim in (candidate.dimension_combo || []).slice(0, 2)"
                      :key="dim"
                      class="tag-dim"
                    >
                      {{ dim }}
                    </span>
                  </div>

                  <!-- 价值承诺 -->
                  <p style="color: #6B6862; font-size: 14px; margin-bottom: 8px;">{{ candidate.value_promise }}</p>

                  <!-- Persona 评议摘要 -->
                  <div class="flex gap-4" style="font-size: 12px; color: #9A968D;">
                    <span v-for="pr in (candidate.persona_reviews || []).slice(0, 4)" :key="pr.persona">
                      {{ pr.persona }}: <strong style="color: #3A3935;">{{ pr.score }}</strong>
                    </span>
                  </div>
                </div>

                <!-- 右侧评分 + 操作 -->
                <div class="ml-4 text-right flex-shrink-0">
                  <div class="font-serif" :style="{ color: getScoreColor(candidate.weighted_score), fontSize: '32px', fontWeight: 500, lineHeight: 1.1 }">
                    {{ candidate.weighted_score?.toFixed(1) || '-' }}
                  </div>
                  <div style="font-size: 12px; color: #6B6862; margin-top: 4px;">加权总分</div>
                  <div v-if="!candidate.veto_passed" class="mt-2">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; background: var(--crimson); color: var(--paper);">一票否决</span>
                  </div>
                  <!-- 去创作按钮 -->
                  <el-button
                    type="primary"
                    size="small"
                    class="mt-3"
                    @click.stop="startCreation(candidate)"
                  >
                    去创作
                  </el-button>
                </div>
              </div>

              <!-- 展开的评分明细 -->
              <div v-if="expandedId === candidate.id && candidate.score" class="mt-4 pt-4" style="border-top: 1px solid var(--line);">
                <div class="grid grid-cols-3 md:grid-cols-6 gap-4 mb-3">
                  <div v-for="(label, key) in dimensionLabels" :key="key" class="text-center">
                    <div style="font-size: 12px; color: #6B6862;">{{ label }}</div>
                    <div style="font-size: 18px; font-weight: 600; color: var(--ink);">{{ candidate.score[key]?.toFixed(1) || '-' }}</div>
                  </div>
                </div>
                <div v-if="candidate.score.evidence" style="font-size: 12px; color: #9A968D;">
                  <div v-for="(ev, key) in candidate.score.evidence" :key="key" class="mb-1">
                    <strong>{{ dimensionLabels[key] }}:</strong> {{ ev }}
                  </div>
                </div>

                <!-- 角切入说明 -->
                <div v-if="candidate.angle_note" class="mt-3 p-3" style="background: var(--clay-tint); border-radius: 10px;">
                  <span style="font-size: 12px; font-weight: 600; color: var(--clay-deep);">切入说明: </span>
                  <span style="font-size: 13px; color: #3A3935;">{{ candidate.angle_note }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏：Agent 反馈面板 -->
      <div v-if="miningDone && agentFeedback.length" class="mining-result-right">
        <AgentFeedbackPanel
          :agents="agentFeedback"
          subtitle="选题挖掘流水线：沈知远 衍生候选 → 白景明 评分评估"
        />
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'
import { useAgentProgress } from '@/composables/useAgentProgress'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import AgentFeedbackPanel from '@/components/creation/AgentFeedbackPanel.vue'

const route = useRoute()
const router = useRouter()

// 优先用浏览器历史回退，能保留话题库分页/筛选状态；
// 没有历史（直接进入详情页）时才 fallback 到话题库首页。
const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/topic-clusters')
  }
}

const loading = ref(true)
const cluster = ref(null)
const expandedId = ref(null)
const miningDone = ref(false)
const selectedCandidateId = ref(null)

// Agent 进度（SSE 驱动）
const miningProgress = useAgentProgress()
const miningIsRunning = miningProgress.isRunning
const miningSteps = miningProgress.steps
const miningStepIndex = miningProgress.currentStepIndex
const miningStepPercent = miningProgress.stepPercent

const dimensionLabels = {
  pain_point: '痛点直击',
  value_density: '价值密度',
  propagation: '传播触发',
  differentiation: '差异化',
  freshness: '新鲜度',
  audience_fit: '受众适配',
}

// Agent 反馈数据（挖掘完成后展示）
const agentFeedback = computed(() => {
  const c = cluster.value
  if (!c?.candidates?.length || !miningDone.value) return []

  const candidates = c.candidates
  const selectedCount = candidates.filter(x => x.verdict === 'selected').length
  const backupCount = candidates.filter(x => x.verdict === 'backup').length
  const rejectedCount = candidates.filter(x => x.verdict === 'rejected').length
  const vetoedCount = candidates.filter(x => x.verdict === 'vetoed').length

  const agentA = {
    id: 'A',
    code: 'A',
    name: '沈知远 · 选题衍生员',
    role: '从话题信息中衍生候选选题',
    avatar: '/agents/agent-a.png',
    summary: `基于话题「${c.core_title_zh || c.core_title}」，共衍生 ${candidates.length} 个候选选题。`,
  }

  const selectedCandidate = candidates.find(x => x.id === selectedCandidateId.value)

  let agentB
  if (selectedCandidate) {
    // 展示选中候选的详细评价
    const verdictLabel = selectedCandidate.verdict === 'selected' ? '入选' : selectedCandidate.verdict === 'backup' ? '备选' : selectedCandidate.verdict === 'vetoed' ? '否决' : '淘汰'
    const personaText = (selectedCandidate.persona_reviews || [])
      .map(pr => `${pr.persona}（${pr.score}分）：${pr.rationale}`)
      .join('\n')
    agentB = {
      id: 'B',
      code: 'B',
      name: '白景明 · 选题评分员',
      role: '6 维度评分 + 入选判定',
      avatar: '/agents/agent-b.png',
      summary: `「${selectedCandidate.title}」— ${verdictLabel}，加权总分 ${selectedCandidate.weighted_score?.toFixed(1) ?? '-'}`,
      suggestions: personaText ? personaText.split('\n') : [],
    }
  } else {
    // 未选中任何候选时，显示总览
    agentB = {
      id: 'B',
      code: 'B',
      name: '白景明 · 选题评分员',
      role: '6 维度评分 + 入选判定',
      avatar: '/agents/agent-b.png',
      summary: `入选 ${selectedCount} · 备选 ${backupCount} · 淘汰 ${rejectedCount} · 否决 ${vetoedCount}`,
    }
  }

  return [agentA, agentB]
})

const selectCandidate = (candidate) => {
  expandedId.value = expandedId.value === candidate.id ? null : candidate.id
  selectedCandidateId.value = expandedId.value ? candidate.id : null
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
    // 如果已有候选选题，说明挖掘已完成，恢复反馈面板状态
    if (res.data?.candidates?.length > 0) {
      miningDone.value = true
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

const triggerMining = async () => {
  console.log('[triggerMining] clicked, cluster_id:', cluster.value?.id)
  if (!cluster.value?.id) return
  miningDone.value = false

  // 监听 SSE 结果
  const stopWatch = watch(() => miningProgress.result.value, (newResult) => {
    if (newResult) {
      console.log('[triggerMining] SSE result:', newResult)
      ElMessage.success(`挖掘完成，生成 ${newResult.total_candidates ?? '?'} 个候选`)
      miningDone.value = true
      loadCluster()
      stopWatch()
    }
  })

  // 监听 SSE 错误
  const stopErrorWatch = watch(() => miningProgress.error.value, (newError) => {
    if (newError) {
      console.error('[triggerMining] SSE error:', newError)
      ElMessage.error(`挖掘失败: ${newError}`)
      stopErrorWatch()
    }
  })

  try {
    console.log('[triggerMining] POST /topic-candidates/mine ...')
    const res = await post('/topic-candidates/mine', { cluster_id: cluster.value.id })
    console.log('[triggerMining] POST response:', res?.data)
    const data = res?.data || {}
    if (data.skipped) {
      ElMessage.info('该话题已经挖掘过')
      await loadCluster()
      miningDone.value = true
      return
    }
    const runId = data.run_id
    console.log('[triggerMining] run_id:', runId)
    if (runId) {
      miningProgress.start(`/api/v1/topic-candidates/stream/${runId}`)
    }
  } catch (error) {
    console.error('[triggerMining] POST failed:', error)
    const detail = error?.response?.data?.detail || error?.message || '挖掘失败'
    ElMessage.error(`挖掘失败: ${detail}`)
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

// 去创作
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
.detail-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}

.source-section {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 24px;
}

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
  color: var(--paper);
  font-size: 12px;
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

.source-arrow {
  color: var(--clay);
  font-size: 16px;
  flex-shrink: 0;
}

/* 新版原文卡片 */
.source-card {
  display: block;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  text-decoration: none;
  transition: all 0.2s cubic-bezier(.32, .72, 0, 1);
  overflow: hidden;
}
.source-card:hover {
  border-color: var(--clay);
  box-shadow: 0 4px 12px rgba(204, 120, 92, 0.10);
  transform: translateY(-1px);
}
.source-card-body {
  padding: 14px 16px;
}
.source-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.source-card-platform {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--clay-tint);
  color: var(--clay-deep);
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--clay-soft);
}
.source-card-time {
  font-size: 12px;
  color: #9A968D;
}
.source-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.45;
  margin-bottom: 6px;
}
.source-card-summary {
  font-size: 13px;
  color: #6B6862;
  line-height: 1.6;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 8px;
}
.source-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.source-card-author {
  color: #9A968D;
}
.source-card-link {
  color: var(--clay);
  font-weight: 500;
}

.candidate-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.24s cubic-bezier(.32, .72, 0, 1);
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}
.candidate-card:hover {
  box-shadow: 0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  transform: translateY(-2px);
}

.verdict-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.verdict-selected {
  background: var(--leaf);
  color: var(--paper);
}
.verdict-backup {
  background: var(--sand);
  color: var(--paper);
}
.verdict-rejected {
  background: var(--crimson);
  color: var(--paper);
}
.verdict-vetoed {
  background: var(--bone);
  color: #6B6862;
}

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

.tag-direction-sm {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
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

.tag-business-sensitive {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: #FFF3D6;
  color: #B27800;
  border: 1px solid #E8C880;
  cursor: help;
}

.tag-routine {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: var(--bone);
  color: #3A3935;
  border: 1px solid var(--line);
}

.tag-dim {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: #ECDCBF;
  color: var(--sand);
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

/* 挖掘结果双栏布局 */
.mining-result-layout {
  display: block;
}

.mining-result-layout.has-feedback {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .mining-result-layout.has-feedback {
    grid-template-columns: 1fr;
  }
}

.mining-result-left,
.mining-result-right {
  min-width: 0;
}
</style>
