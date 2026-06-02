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
      <div ref="layoutRef" class="detail-layout" :class="{ 'has-panel': showPanel }" :style="{ height: layoutHeight }">
        <!-- 左栏：话题详情 -->
        <div ref="mainRef" class="detail-main">
          <div class="detail-card">
            <div class="p-6 card-body">
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
                 style="color: #4A4641; font-size: 16px; line-height: 1.8;
                        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
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
                <!-- 已挖掘：显示"查看选题"；未挖掘：显示"挖掘选题" -->
                <button
                  v-if="isMined"
                  class="btn-creative" style="font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;"
                  @click="showMinedCandidates"
                  :disabled="showPanel"
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
        </div>

        <!-- 右栏：面板（挖掘中 / 已挖掘的选题角度） -->
        <div v-if="showPanel" ref="panelRef" class="detail-panel" :style="{ height: panelHeight }">
          <div class="panel-inner">
            <!-- Panel Header -->
            <div class="panel-header">
              <div>
                <h3 class="t-h4 c-ink" style="font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;">{{ panelTitle }}</h3>
              </div>
              <button class="panel-close" @click="closePanel">&times;</button>
            </div>

            <!-- Panel Body -->
            <div class="panel-body">
              <!-- 挖掘中状态 -->
              <div v-if="miningRunning" class="mining-progress">
                <!-- 当前 Agent 头像 -->
                <div class="mining-avatar">
                  <img :src="miningCurrentStep?.avatar || '/agents/agent-a.png'" :alt="miningCurrentStep?.agent" />
                </div>

                <!-- Agent 名称 + 当前动作 -->
                <div class="mining-agent-name">{{ miningCurrentStep?.agent || '沈知远 · 选题衍生员' }}</div>
                <div class="mining-action">{{ miningCurrentStep?.action || '正在分析信息源，衍生候选选题…' }}</div>

                <!-- 进度条 -->
                <div class="mining-bar">
                  <div class="mining-bar-fill" :class="{ 'no-step-transition': miningProgress.noStepTransition.value }" :style="{ width: miningPercent + '%' }"></div>
                </div>
                <div class="mining-bar-meta">
                  <span>第 {{ miningStepNo }} / {{ Math.max(miningProgress.steps.value.length, 2) }} 步</span>
                  <span>{{ miningPercent }}%</span>
                </div>

                <!-- 标题（进度条下方） -->
                <p class="mining-title">正在挖掘选题，请稍候…</p>
              </div>

              <!-- 已挖掘：单卡轮播展示选题角度 -->
              <div v-else-if="currentCandidate" class="carousel fade-in">
                <!-- 顶部：计数 + 换一批 -->
                <div class="carousel-top">
                  <span class="carousel-counter">
                    推荐角度 · 第 {{ currentCandidateIndex + 1 }} / {{ totalCandidates }} 个
                  </span>
                  <button class="btn-reshuffle" @click="reshuffleCandidates" :disabled="totalCandidates <= 1">
                    <span class="reshuffle-icon">↻</span> 换一批
                  </button>
                </div>

                <!-- 主卡片 -->
                <transition name="angle-swap" mode="out-in">
                  <div class="angle-hero" :key="currentCandidate.id">
                    <!-- 头部：序号 / 方向 / 热度（固定） -->
                    <div class="angle-hero-head">
                      <div class="flex items-center gap-2.5">
                        <span class="angle-index">{{ String(currentCandidateIndex + 1).padStart(2, '0') }}</span>
                        <span v-if="currentCandidate.direction" class="angle-direction">{{ currentCandidate.direction }}</span>
                      </div>
                      <span class="angle-heat" :class="heatClass(currentCandidate.weighted_score)">
                        热度 {{ heatLabel(currentCandidate.weighted_score) }}
                      </span>
                    </div>

                    <!-- 中部：标题 + 各类简介信息（可滚动） -->
                    <div class="angle-scroll">
                      <h3 class="angle-title font-serif">{{ currentCandidate.title }}</h3>
                      <p v-if="currentCandidate.summary" class="angle-summary">{{ currentCandidate.summary }}</p>

                      <div class="angle-info">
                        <div v-if="currentCandidate.value_promise" class="info-block">
                          <span class="info-label">价值承诺</span>
                          <p class="info-text">{{ currentCandidate.value_promise }}</p>
                        </div>
                        <div v-if="currentCandidate.angle_note" class="info-block">
                          <span class="info-label">角度说明</span>
                          <p class="info-text">{{ currentCandidate.angle_note }}</p>
                        </div>
                      </div>

                      <!-- 评分维度 -->
                      <div v-if="currentCandidate.score" class="score-section">
                        <span class="info-label">评分维度</span>
                        <div class="score-grid">
                          <div
                            v-for="dim in scoreDimensions"
                            :key="dim.key"
                            v-show="currentCandidate.score[dim.key] != null"
                            class="score-cell"
                          >
                            <span class="score-dim-label">{{ dim.label }}</span>
                            <span class="score-dim-value" :style="{ color: getScoreColor(currentCandidate.score[dim.key]) }">
                              {{ currentCandidate.score[dim.key] != null ? currentCandidate.score[dim.key].toFixed(1) : '—' }}
                            </span>
                          </div>
                        </div>
                        <!-- 评分依据：对象形态逐条展示 -->
                        <div v-if="evidenceData.items.length" class="evidence-list">
                          <div v-for="item in evidenceData.items" :key="item.label" class="evidence-item">
                            <span class="evidence-dim">{{ item.label }}</span>
                            <span class="evidence-text">{{ item.text }}</span>
                          </div>
                        </div>
                        <!-- 评分依据：字符串形态 -->
                        <p v-else-if="evidenceData.text" class="score-evidence">{{ evidenceData.text }}</p>
                      </div>
                    </div>

                    <!-- 底部：操作按钮（固定） -->
                    <div class="angle-hero-foot">
                      <button class="btn-copy" @click="copyCandidate(currentCandidate)">
                        <span class="copy-icon">⧉</span> 复制
                      </button>
                      <button class="btn-write-outline" @click="startCreation(currentCandidate)">
                        用此角度写大纲 <span style="font-size: 12px;">→</span>
                      </button>
                    </div>
                  </div>
                </transition>

                <!-- 底部导航：上下箭头 + 圆点 -->
                <div class="carousel-nav">
                  <button class="nav-arrow" @click="prevCandidate" :disabled="totalCandidates <= 1" aria-label="上一个">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>
                  </button>
                  <div class="nav-dots">
                    <button
                      v-for="(c, i) in candidateList"
                      :key="c.id"
                      class="nav-dot"
                      :class="{ active: i === currentCandidateIndex }"
                      @click="goToCandidate(i)"
                      :aria-label="`第 ${i + 1} 个`"
                    ></button>
                  </div>
                  <button class="nav-arrow" @click="nextCandidate" :disabled="totalCandidates <= 1" aria-label="下一个">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </button>
                </div>
              </div>

              <!-- 空状态 -->
              <div v-else class="empty-state">
                <p style="color: #6B6862;">暂无选题数据</p>
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
const mainRef = ref(null)
const layoutRef = ref(null)
const panelRef = ref(null)
const panelHeight = ref('auto')
const layoutHeight = ref('auto')
let resizeObserver = null

// 计算可用高度：从布局自身顶部（返回按钮下方）到 viewport 底部，减去底部留白
const calcLayoutHeight = () => {
  if (layoutRef.value) {
    const top = layoutRef.value.getBoundingClientRect().top
    layoutHeight.value = (window.innerHeight - top - 24) + 'px'
  } else {
    layoutHeight.value = (window.innerHeight - 108) + 'px'
  }
}

// 同步右侧面板高度 = 左侧内容高度
const syncPanelHeight = () => {
  if (mainRef.value) {
    panelHeight.value = mainRef.value.offsetHeight + 'px'
  }
}

watch(showPanel, (val) => {
  if (val) {
    nextTick(() => {
      syncPanelHeight()
      // 再等一帧确保布局完成
      requestAnimationFrame(() => {
        syncPanelHeight()
        // 用 ResizeObserver 持续监听左侧高度变化
        if (mainRef.value && !resizeObserver) {
          resizeObserver = new ResizeObserver(() => syncPanelHeight())
          resizeObserver.observe(mainRef.value)
        }
      })
    })
  } else {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})
const panelMode = ref('mining') // 'mining' | 'candidates'
const miningRunning = ref(false)

// Agent 进度（轮询，绕开 SSE 避免反代缓冲）
const miningProgress = useAgentProgress()
const MINING_TOTAL_STEPS = 2        // 挖掘固定 2 个 Agent

const miningStepNo = computed(() => {
  const idx = miningProgress.currentStepIndex.value
  return Math.min(Math.max(idx + 1, 1), MINING_TOTAL_STEPS)
})
const miningPercent = computed(() => Math.round(miningProgress.stepPercent.value))

// 当前显示的 Agent（从 composable 的 steps 取，和大纲/正文/标题用法一致）
const miningCurrentStep = computed(() => {
  const i = miningProgress.currentStepIndex.value
  return i >= 0 ? miningProgress.steps.value[i] : null
})

// 监听 composable 完成：isRunning 变 false 且有 result 时触发成功回调
// 需要同时 watch result 和 isRunning，因为 _finishStep 先设 result 再延迟设 isRunning=false
watch(
  [() => miningProgress.result.value, () => miningProgress.isRunning.value],
  ([r, running]) => {
    if (r && !running) {
      onMiningSuccess(r)
    }
  }
)

// 面板标题// 面板标题
const panelTitle = computed(() => {
  if (panelMode.value === 'mining') return '挖掘选题中'
  return '选题角度'
})

const panelSubtitle = computed(() => {
  if (panelMode.value === 'mining') return 'AI 正在分析资讯，生成候选选题…'
  return `基于「${cluster.value?.core_title_zh || cluster.value?.latest_title || ''}」生成`
})

// 面板中的候选列表（本地副本，支持"换一批"重新排序）
const candidateList = ref([])
const currentCandidateIndex = ref(0)

const totalCandidates = computed(() => candidateList.value.length)
const currentCandidate = computed(() => candidateList.value[currentCandidateIndex.value] || null)

// 从 cluster 同步候选到本地列表，并重置到第一个
const syncCandidates = () => {
  candidateList.value = [...(cluster.value?.candidates || [])]
  currentCandidateIndex.value = 0
}

// 上一个 / 下一个（循环切换）
const prevCandidate = () => {
  if (totalCandidates.value === 0) return
  currentCandidateIndex.value =
    (currentCandidateIndex.value - 1 + totalCandidates.value) % totalCandidates.value
}
const nextCandidate = () => {
  if (totalCandidates.value === 0) return
  currentCandidateIndex.value = (currentCandidateIndex.value + 1) % totalCandidates.value
}
const goToCandidate = (i) => {
  currentCandidateIndex.value = i
}

// 换一批：暂无后端重新生成接口，先在前端打乱当前候选顺序
const reshuffleCandidates = () => {
  if (totalCandidates.value <= 1) return
  candidateList.value = [...candidateList.value].sort(() => Math.random() - 0.5)
  currentCandidateIndex.value = 0
}

// 评分维度映射（对应 score 字段）
const scoreDimensions = [
  { key: 'pain_point', label: '痛点直击' },
  { key: 'value_density', label: '价值密度' },
  { key: 'propagation', label: '传播触发' },
  { key: 'differentiation', label: '差异化' },
  { key: 'freshness', label: '新鲜度' },
  { key: 'audience_fit', label: '受众适配' },
]

// evidence 兼容：可能是对象（按维度给理由）或字符串（散文）
const evidenceData = computed(() => {
  let ev = currentCandidate.value?.score?.evidence
  if (ev == null || ev === '') return { items: [], text: '' }
  // 字符串形态：可能是 JSON 字符串，尝试解析
  if (typeof ev === 'string') {
    const t = ev.trim()
    if (t.startsWith('{')) {
      try { ev = JSON.parse(t) } catch { return { items: [], text: ev } }
    } else {
      return { items: [], text: ev }
    }
  }
  // 对象形态：转成「维度名 → 理由」列表
  if (ev && typeof ev === 'object') {
    const labelMap = Object.fromEntries(scoreDimensions.map(d => [d.key, d.label]))
    const items = Object.entries(ev)
      .filter(([, v]) => v != null && v !== '')
      .map(([k, v]) => ({ label: labelMap[k] || k, text: String(v) }))
    return { items, text: '' }
  }
  return { items: [], text: String(ev) }
})

// 热度标签：根据综合分映射
const heatLabel = (score) => {
  if (score == null) return '—'
  if (score >= 7) return '高'
  if (score >= 5) return '中'
  return '低'
}
const heatClass = (score) => {
  if (score == null) return 'heat-low'
  if (score >= 7) return 'heat-high'
  if (score >= 5) return 'heat-mid'
  return 'heat-low'
}

// 复制当前选题
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

// 显示已挖掘的选题
const showMinedCandidates = () => {
  panelMode.value = 'candidates'
  showPanel.value = true
  syncCandidates()
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
    panelMode.value = 'candidates'
    syncCandidates()
    nextTick(syncPanelHeight)
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

    // 把快照喂给 composable（它会处理 step 切换动画、100% 补满、归零等）
    miningProgress.applySnapshot(d)

    if (d.error) {
      stopPolling()
      onMiningError(d.error)
      return
    }
    if (d.done && d.result) {
      stopPolling()
      // composable 的 _finishStep 已经在处理完成动画
      // 等 isRunning=false 后由外部 watch(result) 触发 onMiningSuccess
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
  showPanel.value = true


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

const closePanel = () => {
  showPanel.value = false
  miningRunning.value = false
  stopPolling()

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
  document.body.style.overflow = 'hidden'
  calcLayoutHeight()
  window.addEventListener('resize', calcLayoutHeight)
  loadCluster()
})

onUnmounted(() => {
  document.body.style.overflow = ''
  window.removeEventListener('resize', calcLayoutHeight)
  stopPolling()

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
    nextTick(calcLayoutHeight)
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
  align-items: stretch;
  max-width: 820px;
  margin: 0 auto;
  height: 100%;
  transition: max-width 0.32s cubic-bezier(.32,.72,0,1);
}

.detail-layout.has-panel {
  max-width: 1280px;
}

.detail-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.detail-panel {
  width: 460px;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}

.panel-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
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

/* 挖掘进度 */
.mining-progress {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

/* 当前 Agent 头像 */
.mining-avatar {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--paper);
  border: 2px solid var(--clay-soft);
  box-shadow: 0 0 0 6px var(--clay-tint);
  animation: avatarPulse 1.8s ease-in-out infinite;
}

.mining-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* 头像四周自带留白，放大裁掉一圈 */
  transform: scale(1.12);
}

@keyframes avatarPulse {
  0%, 100% { box-shadow: 0 0 0 6px var(--clay-tint); }
  50% { box-shadow: 0 0 0 11px rgba(204,120,92,0); }
}

.mining-agent-name {
  margin-top: 16px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
}

.mining-action {
  margin-top: 6px;
  max-width: 320px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink-3);
  text-align: center;
}

.mining-bar {
  width: 100%;
  max-width: 320px;
  height: 6px;
  margin-top: 24px;
  border-radius: 999px;
  background: var(--line);
  overflow: hidden;
}

.mining-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--clay-soft), var(--clay));
  transition: width 1s ease;
}

/* 归零瞬间禁用过渡，避免出现 100%→0% 的倒退动画 */
.mining-bar-fill.no-transition {
  transition: none;
}


.mining-bar-meta {
  width: 100%;
  max-width: 320px;
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--ink-4);
}

.mining-title {
  margin-top: 18px;
  font-size: 13px;
  color: var(--ink-4);
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

/* ===== 选题角度轮播 ===== */
.carousel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.carousel-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.carousel-counter {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-3);
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
}

.btn-reshuffle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  border: none;
  color: var(--clay-deep);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.15s;
}
.btn-reshuffle:hover:not(:disabled) { color: var(--clay); }
.btn-reshuffle:disabled { opacity: 0.4; cursor: not-allowed; }
.reshuffle-icon { font-size: 14px; }

/* 主卡片 */
.angle-hero {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--clay-soft);
  border-radius: 16px;
  background: var(--paper);
  box-shadow: var(--sh-1);
  padding: 22px;
}

.angle-hero-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.angle-index {
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
  font-size: 28px;
  font-weight: 600;
  color: var(--clay);
  line-height: 1;
}

.angle-direction {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}

.angle-heat {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.heat-high { background: rgba(92,138,92,.12); color: var(--leaf); }
.heat-mid { background: var(--sand-soft); color: #8a6d33; }
.heat-low { background: #F0EBE5; color: var(--ink-4); }

/* 中部可滚动区 */
.angle-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  margin-right: -4px;
}

.angle-title {
  font-size: 22px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.4;
  margin-bottom: 10px;
}

.angle-summary {
  font-size: 14px;
  line-height: 1.75;
  color: var(--ink-3);
}

/* 简介信息块 */
.angle-info {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.info-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-4);
  letter-spacing: 0.03em;
  margin-bottom: 5px;
}

.info-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-3);
}

/* 评分维度 */
.score-section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed var(--line);
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 10px;
}

.score-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 10px 6px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--paper);
}

.score-dim-label {
  font-size: 11px;
  color: var(--ink-4);
  font-weight: 500;
}

.score-dim-value {
  font-family: 'Source Han Serif SC', 'Songti SC', Georgia, serif;
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
}

.score-evidence {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--paper-2, #F6F1EB);
  font-size: 12px;
  line-height: 1.75;
  color: var(--ink-3);
  white-space: pre-line;
}

/* 评分依据（逐条） */
.evidence-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-item {
  display: flex;
  gap: 8px;
  font-size: 12px;
  line-height: 1.7;
}

.evidence-dim {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--ink-3);
  min-width: 56px;
}

.evidence-text {
  color: var(--ink-4);
}

.angle-hero-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
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

/* 底部导航 */
.carousel-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-top: 18px;
}

.nav-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--ink-3);
  cursor: pointer;
  transition: all 0.15s;
}
.nav-arrow:hover:not(:disabled) {
  border-color: var(--clay-soft);
  color: var(--clay);
  background: var(--clay-tint);
}
.nav-arrow:disabled { opacity: 0.35; cursor: not-allowed; }

.nav-dots {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  border: none;
  padding: 0;
  background: var(--clay-soft);
  cursor: pointer;
  transition: all 0.22s cubic-bezier(.32,.72,0,1);
}
.nav-dot.active {
  width: 22px;
  background: var(--clay);
}

/* 卡片切换动画 */
.angle-swap-enter-active,
.angle-swap-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.angle-swap-enter-from { opacity: 0; transform: translateY(8px); }
.angle-swap-leave-to { opacity: 0; transform: translateY(-8px); }

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

/* Source Scroll */
.source-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.topic-cluster-detail {
  padding: 0 32px 24px;
}

/* Detail Card */
.detail-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
  min-height: 0;
}

/* 卡片内容区：撑满卡片高度，内部 flex 让来源列表可滚动 */
.card-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 弹性占位：吸收多余空白，使其留在简介与信息要素之间 */
.flex-spacer {
  flex: 1 0 0;
  min-height: 16px;
}

/* 原文来源区：不主动占空间，但内容多时可在内部滚动 */
.source-section {
  flex: 0 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 固定区块（标题/简介/信息要素等）不收缩，只让原文来源区收缩 + 内部滚动，
   避免内容多时简介被挤压裁切成半行 */
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
  justify-content: space-between;
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
  font-size: 11px;
  color: var(--ink-4);
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

.source-summary {
  font-size: 11px;
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
  margin-top: 4px;
  font-size: 12px;
}

.source-author {
  color: var(--ink-4);
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
