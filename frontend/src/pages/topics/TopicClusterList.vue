<template>
  <div class="topic-cluster-list">
    <!-- 页面标题 -->
    <div class="mb-6" style="display: flex; justify-content: space-between; align-items: flex-start;">
      <div>
        <h1 class="font-serif text-ink" style="font-size: 30px; font-weight: 500; line-height: 1.2;">{{ pageTitle }}</h1>
        <p class="mt-1" style="color: #6B6862; font-size: 14px;">{{ pageSubtitle }}</p>
      </div>
    </div>

    <!-- 常驻筛选 -->
    <div class="filter-bar mb-5">
      <!-- 第一行：信息类型（预设页面已锁定类型，隐藏） -->
      <div class="filter-row" v-if="!PRESET">
        <span class="filter-label">类型：</span>
        <div class="filter-chips">
          <button
            v-for="opt in quickTypeOptions"
            :key="opt.value"
            @click="quickFilterByType(opt.value)"
            :class="['type-chip', filters.info_type === opt.value && 'type-chip-active', opt.highlight && 'type-chip-highlight']"
          >
            {{ opt.label }}
            <span v-if="opt.tip" class="chip-tip">{{ opt.tip }}</span>
          </button>
        </div>
      </div>

      <!-- 第二行：方向 -->
      <div class="filter-row">
        <span class="filter-label">方向：</span>
        <div class="filter-chips">
          <button
            v-for="opt in directionOptions"
            :key="opt.value"
            @click="quickFilterByDirection(opt.value)"
            :class="['type-chip', filters.direction === opt.value && 'type-chip-active']"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <!-- 第三行：时效 + 挖掘状态（潜在商单只在独立页面展示） -->
      <div class="filter-row">
        <span class="filter-label">时效：</span>
        <div class="filter-chips">
          <button
            v-for="opt in freshnessOptions"
            :key="opt.value"
            @click="quickFilterByFreshness(opt.value)"
            :class="['type-chip', filters.freshness === opt.value && 'type-chip-active']"
          >
            {{ opt.label }}
          </button>
        </div>
        <span class="filter-label-sep">|</span>
        <span class="filter-label">挖掘状态：</span>
        <div class="filter-chips">
          <button
            v-for="opt in minedOptions"
            :key="opt.value"
            @click="quickFilterByMined(opt.value)"
            :class="['type-chip', filters.mined === opt.value && 'type-chip-active']"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <span class="ml-2" style="color: #6B6862;">加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="clusters.length === 0" class="text-center py-20">
      <el-icon :size="64" style="color: var(--line);"><Folder /></el-icon>
      <h3 class="mt-4" style="color: #3A3935; font-size: 18px; font-weight: 600;">暂无话题</h3>
      <p class="mt-1" style="color: #6B6862; font-size: 14px;">需要先通过抓取和预处理生成话题</p>
    </div>

    <!-- 小时级时间轴：优先发布时间，缺失时使用抓取时间 -->
    <div v-else class="timeline-list">
      <section v-for="group in timelineGroups" :key="group.key" class="timeline-group">
        <div class="timeline-aside">
          <time>{{ group.label }}</time>
          <span class="timeline-dot"></span>
        </div>
        <div class="timeline-cards">
        <div
          v-for="cluster in group.items"
          :key="cluster.id"
          class="cluster-card"
          @click="goToDetail(cluster.id)"
        >
          <div class="p-5 cluster-card-body" style="position: relative;">
            <!-- 标题 -->
            <h3 class="font-serif" style="font-size: 22px; font-weight: 500; color: var(--ink); line-height: 1.45;
                                          display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
              {{ cluster.core_title_zh || cluster.latest_title || cluster.core_title }}
            </h3>
            <p v-if="cluster.core_title_zh && cluster.core_title_zh !== (cluster.latest_title || cluster.core_title)"
               class="mt-1.5" style="font-size: 12px; color: #9A968D; line-height: 1.5;
                                     display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
              {{ cluster.latest_title || cluster.core_title }}
            </p>

            <!-- 摘要 -->
            <p v-if="cluster.summary_zh || cluster.summary"
               class="mt-3"
               style="color: #6B6862; font-size: 15px; line-height: 1.75;
                      display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;">
              {{ cluster.summary_zh || cluster.summary }}
            </p>

            <!-- 弹性占位：内容短时空隙落在摘要下方，标签+评分行始终贴底 -->
            <div class="cluster-card-spacer"></div>

            <!-- 标签 -->
            <div class="flex flex-wrap gap-2 mt-4">
              <span v-if="cluster.info_type" class="tag-type">
                {{ cluster.info_type }}
              </span>
              <span v-if="cluster.direction" class="tag-direction">{{ cluster.direction }}</span>
              <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
              <span v-if="cluster.low_fan_hit" class="tag-hot">🔥 低粉爆款</span>
              <span v-if="cluster.mined && !cluster.needs_update" class="tag-mined">已挖掘</span>
              <span v-else-if="cluster.needs_update" class="tag-needs-update">待更新</span>
              <span v-else class="tag-unmined">待挖掘</span>
            </div>

            <!-- 评分行：价值 + 热度（克制版） -->
            <div class="score-row">
              <div class="score-item">
                <span class="score-label">价值</span>
                <span class="score-num">{{ cluster.display_score?.toFixed(1) || '-' }}</span>
              </div>
              <span class="score-sep">·</span>
              <div class="score-item">
                <span class="score-label">热度</span>
                <span class="score-num score-num-heat">{{ cluster.heat_score?.toFixed(1) || '-' }}</span>
              </div>
              <span class="score-sep">·</span>
              <div class="score-item" v-if="cluster.candidate_count > 0">
                <span class="score-label">选题</span>
                <span class="score-num score-num-pine">{{ cluster.candidate_count }}</span>
              </div>
              <span v-if="cluster.candidate_count > 0" class="score-sep">·</span>
              <div class="score-item">
                <span class="score-label">原文</span>
                <span class="score-num score-num-mute">{{ cluster.source_count || cluster.source_urls?.length || 0 }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      </section>
    </div>

    <!-- 加载更多 / 到底了 -->
    <div v-if="clusters.length > 0" class="load-more">
      <div v-if="loadingMore" class="load-more-text">
        <el-icon class="is-loading" :size="16" style="color: var(--clay);"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <span v-else-if="noMore" class="load-more-end">— 共 {{ pagination.total }} 条 —</span>
      <span v-else class="load-more-end" @click="loadNextPage" style="cursor: pointer;">加载更多</span>
    </div>
  </div>
</template>

<script>
export default { name: 'TopicClusters' }
</script>

<script setup>
defineOptions({ name: 'TopicClusterList' })

import { ref, reactive, onMounted, onUnmounted, onActivated, onDeactivated, watch, computed, nextTick } from 'vue'

import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Folder } from '@element-plus/icons-vue'
import { get } from '@/api/api'

const router = useRouter()
const route = useRoute()

// 预设页面：'资讯型' / '实操案例型' / ''(综合)。靠 route.meta 区分，并锁定类型筛选。
const PRESET = route.meta?.preset || ''
const WECHAT_ONLY = route.meta?.wechatOnly === true
const defaultSortBy = 'timeline_at'
const scrollKey = `topic-list-scroll-${route.name || PRESET || 'all'}`
const pageTitle = PRESET === '资讯型'
    ? '资讯型'
    : PRESET === '实操案例型'
      ? '实操案例'
      : '内容资讯'
const pageSubtitle = PRESET === '资讯型'
    ? '聚合各平台的资讯型信息，按时间倒序排列'
    : PRESET === '实操案例型'
      ? '聚合各平台的实操案例，按创作价值排序'
      : '聚合各平台的热点资讯，点击任意一条查看详情与原文来源'

const loading = ref(false)
const clusters = ref([])

const timelineGroups = computed(() => {
  const groups = new Map()
  for (const item of clusters.value) {
    const date = item.timeline_at ? new Date(item.timeline_at) : null
    const valid = date && !Number.isNaN(date.getTime())
    const key = valid
      ? `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}-${date.getHours()}`
      : 'unknown'
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label: valid
          ? `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, '0')}:00`
          : '时间待补充',
        items: [],
      })
    }
    groups.get(key).items.push(item)
  }
  return [...groups.values()]
})

const filters = reactive({
  info_type: PRESET,         // 预设页面锁定为对应类型
  direction: '',
  freshness: '',
  mined: '',
  keyword: '',
  sort_by: defaultSortBy,
  sort_order: 'desc',
})

// 顶部快速分类 chips
const quickTypeOptions = [
  { value: '', label: '全部' },
  { value: '教程型', label: '教程型' },
  { value: '实操案例型', label: '实操案例' },
  { value: '观点分享型', label: '观点分享' },
  { value: '资讯型', label: '资讯型' },
]

// 话题方向 chips —— 必须与后端 rules.py DIRECTION_KEYWORDS 的 key 完全一致，
// 否则筛选出来永远是空（value 是拿去等值匹配 InfoCluster.direction 的）。
const directionOptions = [
  { value: '', label: '全部' },
  { value: '大模型', label: '大模型' },
  { value: 'Coding Agent', label: 'Coding Agent' },
  { value: 'Agent 工作流', label: 'Agent 工作流' },
  { value: 'AI 视频/短剧', label: 'AI 视频/短剧' },
  { value: '出图/设计', label: '出图/设计' },
  { value: 'HTML/内容交付', label: 'HTML/内容交付' },
  { value: 'Agent 基础设施', label: 'Agent 基础设施' },
]

// 时效 chips
const freshnessOptions = [
  { value: '', label: '全部' },
  { value: 'today', label: '今日' },
  { value: 'yesterday', label: '昨日' },
  { value: 'earlier', label: '两天前' },
]

// 挖掘状态 chips
const minedOptions = [
  { value: '', label: '全部' },
  { value: 'true', label: '已挖掘' },
  { value: 'false', label: '未挖掘' },
  { value: 'needs_update', label: '待更新' },
]

const hasAnyFilter = computed(() =>
  !!(filters.info_type || filters.direction || filters.freshness || filters.mined || filters.keyword)
)

const quickFilterByType = (typeValue) => {
  filters.info_type = typeValue
  reloadFromStart()
}

const quickFilterByDirection = (val) => {
  filters.direction = val
  reloadFromStart()
}

const quickFilterByFreshness = (val) => {
  filters.freshness = val
  reloadFromStart()
}

const quickFilterByMined = (val) => {
  filters.mined = val
  reloadFromStart()
}

const resetAllFilters = () => {
  filters.info_type = ''
  filters.direction = ''
  filters.freshness = ''
  filters.mined = ''
  filters.keyword = ''
  reloadFromStart()
}

const reloadFromStart = () => {
  clusters.value = []
  syncToQuery()
  loadClusters()
}

const pagination = reactive({
  page: 1,
  pageSize: 30,
  total: 0,
})
const loadingMore = ref(false)
const noMore = computed(() => clusters.value.length >= pagination.total)

// 从 URL query 还原状态（首次进入 / 浏览器后退时）
// 改成无限滚动后不再保存 page，刷新统一从第 1 页开始
const restoreFromQuery = () => {
  const q = route.query
  filters.info_type   = PRESET || (q.info_type ?? '')
  filters.direction   = q.direction   ?? ''
  filters.freshness   = q.freshness   ?? ''
  filters.mined       = q.mined       ?? ''
  filters.keyword     = q.keyword     ?? ''
  filters.sort_by     = q.sort_by     ?? defaultSortBy
  filters.sort_order  = q.sort_order  ?? 'desc'
  pagination.page     = 1
  pagination.pageSize = 30
}

// 把筛选状态写进 URL query（不再写 page，刷新都从头开始）
const syncToQuery = () => {
  const q = {}
  if (filters.sort_by !== 'display_score') q.sort_by = filters.sort_by
  if (filters.sort_order !== 'desc')    q.sort_order = filters.sort_order
  if (filters.info_type)                q.info_type = filters.info_type
  if (filters.direction)                q.direction = filters.direction
  if (filters.freshness)                q.freshness = filters.freshness
  if (filters.mined)                    q.mined = filters.mined
  if (filters.keyword)                  q.keyword = filters.keyword
  router.replace({ query: q })
}

// keep-alive 期间用 isActive 守门，避免离开期间 route.query 抖动触发重载
const isActive = ref(true)

// 离开列表页时保存滚动位置到 sessionStorage
const saveScroll = () => {
  try { sessionStorage.setItem(scrollKey, String(window.scrollY)) } catch {}
}

// 记录"上次真正加载用的 query"，用来区分"筛选变化"(要重载) 和"从详情页返回"(不重载)
let lastLoadedQueryStr = JSON.stringify(route.query)

// 详情页挖掘完成后返回：定点把对应卡片标为"已挖掘"
const _pendingMinedId = ref(null)
try {
  const minedId = sessionStorage.getItem('topic-mined-id')
  if (minedId) {
    _pendingMinedId.value = minedId
    sessionStorage.removeItem('topic-mined-id')
  }
} catch {}

onMounted(() => {
  restoreFromQuery()
  lastLoadedQueryStr = JSON.stringify(route.query)
  loadClusters(true)
})

// 数据加载完后，把待标记的 mined 状态刷上去
watch(clusters, (list) => {
  if (_pendingMinedId.value && list.length) {
    const c = list.find(x => String(x.id) === _pendingMinedId.value)
    if (c) {
      c.mined = true
      _pendingMinedId.value = null
    }
  }
})

onBeforeRouteLeave(() => {
  saveScroll()
})

// keep-alive：离开（进详情）时保存滚动并停掉 query 监听；
// 返回时恢复滚动 —— 不重载，所以"加载更多"的内容和原位置都还在，也不会闪回顶部
onDeactivated(() => {
  isActive.value = false
  saveScroll()
})
onActivated(() => {
  isActive.value = true
  // 详情页挖掘完成后返回：定点把对应卡片标为"已挖掘"，避免整页重载丢失滚动/分页
  try {
    const minedId = sessionStorage.getItem('topic-mined-id')
    if (minedId) {
      const c = clusters.value.find(x => String(x.id) === minedId)
      if (c) c.mined = true
      sessionStorage.removeItem('topic-mined-id')
    }
  } catch {}
  const saved = parseInt(sessionStorage.getItem(scrollKey) || '0', 10)
  if (saved > 0) {
    nextTick(() => window.scrollTo({ top: saved, behavior: 'instant' }))
  }
})

// 只有"筛选/排序真正变化"才重载；从详情返回时 query 和上次加载的一样 → 不重载
watch(() => route.query, (newQ) => {
  if (!isActive.value) return
  if (!['TopicClusters', 'Home', 'ContentInfo', 'ContentInfoNews', 'ContentInfoCases', 'ContentInfoCommercial'].includes(route.name)) return
  const s = JSON.stringify(newQ)
  if (s === lastLoadedQueryStr) return
  lastLoadedQueryStr = s
  restoreFromQuery()
  clusters.value = []
  loadClusters()
})

const loadClusters = async (restoreScroll = false) => {
  loading.value = true
  try {
    const params = {
      page: 1,
      page_size: pagination.pageSize,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      balanced: false,
    }
    if (filters.info_type) params.info_type = filters.info_type
    if (filters.direction) params.direction = filters.direction
    if (filters.freshness) params.freshness = filters.freshness
    if (filters.mined === 'needs_update') {
      params.needs_update = true
    } else if (filters.mined) {
      params.mined = filters.mined
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (WECHAT_ONLY) params.wechat_only = true

    const res = await get('/topic-clusters', params)
    clusters.value = res.data.items || []
    pagination.total = res.data.total
    pagination.page = 1
  } catch (error) {
    ElMessage.error('加载内容资讯失败')
    console.error(error)
  } finally {
    loading.value = false
    if (restoreScroll) {
      const saved = parseInt(sessionStorage.getItem(scrollKey) || '0', 10)
      if (saved > 0) {
        nextTick(() => setTimeout(() => window.scrollTo({ top: saved, behavior: 'instant' }), 100))
      }
    }
  }
}

const loadNextPage = async () => {
  if (loadingMore.value || noMore.value) return
  loadingMore.value = true
  try {
    const nextPage = pagination.page + 1
    const params = {
      page: nextPage,
      page_size: pagination.pageSize,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      balanced: false,
    }
    if (filters.info_type) params.info_type = filters.info_type
    if (filters.direction) params.direction = filters.direction
    if (filters.freshness) params.freshness = filters.freshness
    if (filters.mined === 'needs_update') {
      params.needs_update = true
    } else if (filters.mined) {
      params.mined = filters.mined
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (WECHAT_ONLY) params.wechat_only = true

    const res = await get('/topic-clusters', params)
    const newItems = res.data.items || []
    clusters.value = [...clusters.value, ...newItems]
    pagination.page = nextPage
    pagination.total = res.data.total
  } catch (error) {
    ElMessage.error('加载更多失败')
  } finally {
    loadingMore.value = false
  }
}

const goToDetail = (id) => {
  router.push(`/topic-clusters/${id}`)
}

const formatFreshness = (val) => {
  const map = { 'today': '今日', 'yesterday': '昨日', 'earlier': '两天前' }
  return map[val] || val
}
</script>

<style scoped>
/* 滚动加载状态条 */
.load-more {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 32px 0 48px;
  color: var(--ink-3);
  font-size: 13px;
  letter-spacing: 0.02em;
}
.load-more-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.load-more-end {
  color: var(--ink-4);
  position: relative;
  padding: 0 8px;
}

/* 小时级时间轴：时间、轴点和竖线共用同一条对齐轴。 */
.timeline-list { position: relative; }
.timeline-group { --timeline-axis: 124px; display: grid; grid-template-columns: var(--timeline-axis) minmax(0, 1fr); gap: 24px; position: relative; padding-bottom: 28px; }
.timeline-group::before { content: ''; position: absolute; left: calc(var(--timeline-axis) - 1px); top: 24px; bottom: -4px; width: 1px; background: var(--line); }
.timeline-group:last-child::before { bottom: 38px; }
.timeline-aside { position: relative; padding-top: 8px; text-align: right; color: var(--ink-3); font-size: 13px; line-height: 20px; font-variant-numeric: tabular-nums; }
.timeline-aside time { display: block; padding-right: 20px; white-space: nowrap; }
.timeline-dot { position: absolute; right: -8px; top: 10px; width: 10px; height: 10px; border-radius: 50%; background: var(--clay); border: 3px solid var(--ivory); box-sizing: content-box; z-index: 1; }
.timeline-cards { min-width: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
@media (max-width: 1180px) { .timeline-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .timeline-group { --timeline-axis: 82px; gap: 16px; }.timeline-aside time { padding-right: 16px; }.timeline-cards { grid-template-columns: 1fr; } }

@media (max-width: 768px) {
  .filter-row { flex-wrap: wrap; }
  .filter-label { min-width: auto; text-align: left; }
}

.cluster-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(.32, .72, 0, 1);
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  overflow: hidden;        /* 长内容不撑破卡片 */
  word-break: break-word;  /* 长单词/URL 自动换行 */
  display: flex;           /* 让内部 body 撑满等高卡片 */
  flex-direction: column;
}
.cluster-card:hover {
  box-shadow: 0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  transform: translateY(-2px);
}
/* 卡片主体竖向排布，spacer 吸收多余高度，标签+评分行贴底 */
.cluster-card-body {
  display: flex;
  flex-direction: column;
  flex: 1;
}
.cluster-card-spacer {
  flex: 1 1 auto;
  min-height: 0;
}

/* 评分行：价值/热度/选题/原文（克制版，纯文字 + 衬线数字）*/
.score-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.score-item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}
.score-label {
  font-size: 12px;
  color: #9A968D;
  letter-spacing: 0.02em;
}
.score-num {
  font-family: 'GT Sectra', 'Source Han Serif SC', serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--clay-deep);
  line-height: 1;
}
.score-num-heat { color: var(--pine); }
.score-num-pine { color: var(--pine); }
.score-num-mute { color: var(--ink-3); font-weight: 500; }
.score-sep { color: #C8C2B6; font-size: 12px; }

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

/* 教程 / 实操推荐徽标（绿色高亮） */
.tag-type-recommend {
  background: #DAF0DC !important;
  color: #2A6B3A !important;
  border-color: #A8D6B0 !important;
  font-weight: 600 !important;
}

/* 筛选区容器 */
.filter-bar {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px 20px;
}

/* 筛选行：标签 + chips 水平对齐 */
.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.filter-label {
  flex-shrink: 0;
  color: #6B6862;
  font-size: 13px;
}

.filter-label-sep {
  color: var(--line);
  font-size: 13px;
  margin: 0 4px;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

/* 顶部 chip 筛选 */
.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  background: var(--paper);
  color: #6B6862;
  border: 1px solid var(--line);
  cursor: pointer;
  transition: all 0.15s;
}
.type-chip:hover {
  background: #F0EDE3;
  color: var(--ink);
}
.type-chip-active {
  background: var(--clay);
  color: #fff;
  border-color: var(--clay);
}
.type-chip-highlight {
  border-color: #A8D6B0;
  background: #F4FBF6;
  color: #2A6B3A;
}
.type-chip-highlight.type-chip-active {
  background: var(--clay);
  color: #fff;
  border-color: var(--clay);
}
.chip-tip {
  font-size: 11px;
  opacity: 0.8;
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

.tag-needs-update {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #E6A23C;
  color: #fff;
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

.source-link {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--clay);
  background: var(--clay-tint);
  text-decoration: none;
  transition: background 0.15s;
}
.source-link:hover {
  background: var(--clay-soft);
}
</style>
