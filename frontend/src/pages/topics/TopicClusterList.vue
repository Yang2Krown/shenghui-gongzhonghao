<template>
  <div class="topic-cluster-list">
    <!-- 页面标题 -->
    <div class="mb-6" style="display: flex; justify-content: space-between; align-items: flex-start;">
      <div>
        <h1 class="font-serif text-ink" style="font-size: 30px; font-weight: 500; line-height: 1.2;">话题库</h1>
        <p class="mt-1" style="color: #6B6862; font-size: 14px;">信息聚合后的原始话题，点击可查看衍生的候选选题</p>
      </div>
      <el-button :icon="Refresh" :loading="refreshing" @click="manualRefresh">手动抓取</el-button>
    </div>

    <!-- 常驻筛选 -->
    <div class="filter-bar mb-5">
      <!-- 第一行：信息类型 -->
      <div class="filter-row">
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

      <!-- 第三行：时效 + 挖掘状态 -->
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

    <!-- 话题瀑布流：JS 分列 + flex 列布局，保证横向排序 + 瀑布流间距 -->
    <div v-else class="masonry">
      <div v-for="(col, ci) in masonryColumns" :key="ci" class="masonry-col">
        <div
          v-for="cluster in col"
          :key="cluster.id"
          class="cluster-card"
          @click="goToDetail(cluster.id)"
        >
          <div class="p-5" style="position: relative;">
            <!-- NEW 标签 -->
            <span v-if="isNew(cluster)" class="tag-new">NEW</span>
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

            <!-- 标签 -->
            <div class="flex flex-wrap gap-2 mt-4">
              <span v-if="cluster.info_type" class="tag-type">
                {{ cluster.info_type }}
              </span>
              <span v-if="cluster.direction" class="tag-direction">{{ cluster.direction }}</span>
              <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
              <span v-if="cluster.low_fan_hit" class="tag-hot">🔥 低粉爆款</span>
              <span v-if="cluster.mined" class="tag-mined">已挖掘</span>
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
import { ref, reactive, onMounted, onUnmounted, onActivated, onDeactivated, watch, computed, nextTick } from 'vue'

import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Folder, Refresh } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const refreshing = ref(false)
const clusters = ref([])

// ── 瀑布流横排：CSS columns 是竖着填的，需要重排数据模拟横向顺序 ──
const columnCount = ref(3)
const _updateCols = () => {
  // 用内容区实际宽度（减去侧边栏），不用 window.innerWidth
  const el = document.querySelector('.topic-cluster-list')
  const w = el ? el.clientWidth : window.innerWidth
  columnCount.value = w <= 500 ? 1 : w <= 800 ? 2 : 3
}
window.addEventListener('resize', _updateCols)
onUnmounted(() => window.removeEventListener('resize', _updateCols))

/**
 * 按横向顺序把数据分到各列：
 * [1,2,3,4,5,6,7,8,9] → Col0=[1,4,7] Col1=[2,5,8] Col2=[3,6,9]
 * 视觉上第一行从左到右就是 1,2,3（分数最高的前3个）
 */
const masonryColumns = computed(() => {
  const items = clusters.value
  const cols = columnCount.value
  const columns = Array.from({ length: cols }, () => [])
  items.forEach((item, i) => {
    columns[i % cols].push(item)
  })
  return columns
})

const manualRefresh = async () => {
  refreshing.value = true
  try {
    await post('/topic-clusters/refresh')
    ElMessage.success('已提交抓取任务，预计几分钟后刷新页面查看新数据')
  } catch (e) {
    ElMessage.error('提交失败，请稍后重试')
  } finally {
    refreshing.value = false
  }
}

const filters = reactive({
  info_type: '',
  direction: '',
  freshness: '',
  mined: '',
  keyword: '',
  sort_by: 'display_score',   // 默认按"公众号创作价值"加权排序（教程/实操优先）
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

// 话题方向 chips
const directionOptions = [
  { value: '', label: '全部' },
  { value: '大模型', label: '大模型' },
  { value: 'Coding Agent', label: 'Coding Agent' },
  { value: 'AI视频', label: 'AI视频' },
  { value: 'AI绘画', label: 'AI绘画' },
  { value: 'AI音频', label: 'AI音频' },
  { value: '效率工具', label: '效率工具' },
  { value: '观点型', label: '观点型' },
  { value: '实践型', label: '实践型' },
  { value: '教程型', label: '教程型' },
  { value: '解决问题型', label: '解决问题型' },
  { value: '资讯型', label: '资讯型' },
  { value: '整活型', label: '整活型' },
]

// 时效 chips
const freshnessOptions = [
  { value: '', label: '全部' },
  { value: '24h', label: '24h 内' },
  { value: '7d', label: '7 天内' },
  { value: '30d', label: '30 天内' },
  { value: 'expired', label: '大于 30 天' },
]

// 挖掘状态 chips
const minedOptions = [
  { value: '', label: '全部' },
  { value: 'true', label: '已挖掘' },
  { value: 'false', label: '未挖掘' },
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
  filters.info_type   = q.info_type   ?? ''
  filters.direction   = q.direction   ?? ''
  filters.freshness   = q.freshness   ?? ''
  filters.mined       = q.mined       ?? ''
  filters.keyword     = q.keyword     ?? ''
  filters.sort_by     = q.sort_by     ?? 'display_score'
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
  try { sessionStorage.setItem('topic-list-scroll', String(window.scrollY)) } catch {}
}

onMounted(() => {
  nextTick(_updateCols)
  restoreFromQuery()
  loadClusters(true)
})

onBeforeRouteLeave(() => {
  saveScroll()
})

// 浏览器后退/前进时，URL query 变化要重新载入（但只在当前真正激活时响应）
watch(() => route.query, (newQ, oldQ) => {
  if (!isActive.value) return
  if (route.name !== 'TopicClusters' && route.name !== 'Home') return
  const same = JSON.stringify(newQ) === JSON.stringify(oldQ)
  if (same) return
  restoreFromQuery()
  clusters.value = []
  loadClusters(true)
})

const loadClusters = async (restoreScroll = false) => {
  loading.value = true
  try {
    const params = {
      page: 1,
      page_size: pagination.pageSize,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      balanced: true,
    }
    if (filters.info_type) params.info_type = filters.info_type
    if (filters.direction) params.direction = filters.direction
    if (filters.freshness) params.freshness = filters.freshness
    if (filters.mined) params.mined = filters.mined
    if (filters.keyword) params.keyword = filters.keyword

    const res = await get('/topic-clusters', params)
    clusters.value = res.data.items || []
    pagination.total = res.data.total
    pagination.page = 1
  } catch (error) {
    ElMessage.error('加载话题库失败')
    console.error(error)
  } finally {
    loading.value = false
    if (restoreScroll) {
      const saved = parseInt(sessionStorage.getItem('topic-list-scroll') || '0', 10)
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
    if (filters.mined) params.mined = filters.mined
    if (filters.keyword) params.keyword = filters.keyword

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
  const map = { '24h': '24h 内', '7d': '7 天内', '30d': '30 天内', 'expired': '大于 30 天' }
  return map[val] || val
}

const isNew = (cluster) => {
  if (!cluster.created_at) return false
  const created = new Date(cluster.created_at)
  const now = new Date()
  return (now - created) < 60 * 60 * 1000  // 1 小时内
}
</script>

<style scoped>
/* NEW 标签 */
.tag-new {
  position: absolute;
  top: 12px;
  right: 12px;
  background: #E8453C;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  line-height: 1.4;
}

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

/* 瀑布流：JS 分列 + flex 实现横向排序 + 自适应高度 */
.masonry {
  display: flex;
  gap: 20px;
}
.masonry-col {
  flex: 1;
  min-width: 0;          /* 防止长文本撑宽列 */
  display: flex;
  flex-direction: column;
  gap: 20px;
}
@media (max-width: 900px) { .masonry-col { min-width: calc(50% - 10px); } }
@media (max-width: 640px) { .masonry { flex-direction: column; } }

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
}
.cluster-card:hover {
  box-shadow: 0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  transform: translateY(-2px);
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
