<template>
  <div class="pc-page">
    <!-- 页头 -->
    <div class="pc-header">
      <div>
        <h1 class="pc-title">潜在商单</h1>
        <p class="pc-subtitle">公众号来源中自动识别的商业推广内容，按时间线浏览</p>
      </div>
      <div class="pc-header-stats" v-if="total > 0">
        <div class="pc-stat">
          <span class="pc-stat-num">{{ total }}</span>
          <span class="pc-stat-label">篇商单</span>
        </div>
        <div class="pc-stat-divider"></div>
        <div class="pc-stat">
          <span class="pc-stat-num">{{ timeline.length }}</span>
          <span class="pc-stat-label">活跃日</span>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="pc-filters">
      <div class="pc-filter-row">
        <span class="pc-filter-label">甲方</span>
        <div class="pc-chips">
          <button
            v-for="opt in brandOptions"
            :key="opt.value"
            @click="toggleBrand(opt.value)"
            :class="['pc-chip', selectedBrand === opt.value && 'pc-chip--on']"
          >
            {{ opt.label }}
            <span v-if="opt.count" class="pc-chip-n">{{ opt.count }}</span>
          </button>
        </div>
      </div>
      <div class="pc-filter-row">
        <span class="pc-filter-label">功能</span>
        <div class="pc-chips">
          <button
            v-for="opt in categoryOptions"
            :key="opt.value"
            @click="toggleCategory(opt.value)"
            :class="['pc-chip', selectedCategory === opt.value && 'pc-chip--on']"
          >
            {{ opt.label }}
            <span v-if="opt.count" class="pc-chip-n">{{ opt.count }}</span>
          </button>
        </div>
      </div>
      <div class="pc-filter-bar">
        <div class="pc-search">
          <svg class="pc-search-icon" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
            <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
          </svg>
          <input
            v-model="keyword"
            @keyup.enter="fetchTimeline"
            placeholder="搜索标题或摘要..."
            class="pc-search-input"
          />
        </div>
        <div class="pc-range-group">
          <button
            v-for="d in [7, 14, 30, 90]"
            :key="d"
            @click="changeDays(d)"
            :class="['pc-range-btn', days === d && 'pc-range-btn--on']"
          >{{ d }}天</button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="pc-loading">
      <div class="pc-spinner"></div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="timeline.length === 0" class="pc-empty">
      <div class="pc-empty-art">
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
          <rect x="12" y="8" width="40" height="48" rx="4" stroke="var(--line)" stroke-width="2" fill="var(--paper)"/>
          <rect x="20" y="20" width="24" height="3" rx="1.5" fill="var(--bone)"/>
          <rect x="20" y="27" width="18" height="3" rx="1.5" fill="var(--bone)"/>
          <rect x="20" y="34" width="22" height="3" rx="1.5" fill="var(--bone)"/>
          <circle cx="46" cy="46" r="12" fill="var(--clay-tint)" stroke="var(--clay-soft)" stroke-width="2"/>
          <path d="M42 46h8M46 42v8" stroke="var(--clay)" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <p class="pc-empty-title">暂无潜在商单</p>
      <p class="pc-empty-hint">系统会自动识别公众号来源中的商业推广内容并归类到此</p>
    </div>

    <!-- 时间轴 -->
    <div v-else class="pc-timeline">
      <div v-for="group in timeline" :key="group.date" class="pc-day">
        <!-- 日期标签 -->
        <div class="pc-day-head">
          <div class="pc-day-dot"></div>
          <span class="pc-day-text">{{ formatDayLabel(group.date) }}</span>
          <span class="pc-day-count">{{ group.items.length }}</span>
        </div>

        <!-- 卡片 -->
        <div class="pc-day-list">
          <div
            v-for="item in group.items"
            :key="item.id"
            class="pc-card"
            @click="openDetail(item)"
          >
            <div class="pc-card-top">
              <span class="pc-card-source">{{ item.source_name }}</span>
              <span class="pc-card-time">{{ formatTime(item.scraped_at) }}</span>
            </div>
            <div class="pc-card-title">{{ item.title }}</div>
            <div class="pc-card-desc" v-if="item.summary">{{ truncate(item.summary, 100) }}</div>
            <div class="pc-card-foot">
              <div class="pc-card-tags">
                <span v-if="item.commercial_brand" class="pc-tag pc-tag--brand">{{ item.commercial_brand }}</span>
                <span v-if="item.commercial_category" class="pc-tag pc-tag--cat">{{ item.commercial_category }}</span>
                <span v-if="item.product" class="pc-tag pc-tag--prod">{{ item.product }}</span>
              </div>
              <span
                :class="['pc-level', item.commercial_level === 'likely' ? 'pc-level--high' : 'pc-level--mid']"
              >
                {{ item.commercial_level === 'likely' ? '高概率' : '潜在' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detailItem?.title" size="520px" direction="rtl">
      <div v-if="detailItem" class="pc-detail">
        <div class="pc-detail-meta">
          <div class="pc-meta-row"><span class="pc-meta-k">来源</span><span>{{ detailItem.source_name }}</span></div>
          <div class="pc-meta-row"><span class="pc-meta-k">抓取时间</span><span>{{ formatDateTime(detailItem.scraped_at) }}</span></div>
          <div class="pc-meta-row" v-if="detailItem.published_at"><span class="pc-meta-k">发布时间</span><span>{{ formatDateTime(detailItem.published_at) }}</span></div>
          <div class="pc-meta-row">
            <span class="pc-meta-k">判定</span>
            <span :class="['pc-level', detailItem.commercial_level === 'likely' ? 'pc-level--high' : 'pc-level--mid']">
              {{ detailItem.commercial_level === 'likely' ? '高概率商单' : '潜在商单' }}
            </span>
          </div>
          <div class="pc-meta-row" v-if="detailItem.commercial_brand">
            <span class="pc-meta-k">甲方</span>
            <span class="pc-tag pc-tag--brand">{{ detailItem.commercial_brand }}</span>
          </div>
          <div class="pc-meta-row" v-if="detailItem.commercial_category">
            <span class="pc-meta-k">功能方向</span>
            <span class="pc-tag pc-tag--cat">{{ detailItem.commercial_category }}</span>
          </div>
          <div class="pc-meta-row" v-if="detailItem.product">
            <span class="pc-meta-k">推广产品</span><span>{{ detailItem.product }}</span>
          </div>
          <div class="pc-meta-row" v-if="detailItem.reason">
            <span class="pc-meta-k">理由</span><span style="color: var(--ink-3)">{{ detailItem.reason }}</span>
          </div>
        </div>

        <div class="pc-detail-section" v-if="detailItem.summary">
          <h3>摘要</h3>
          <p>{{ detailItem.summary }}</p>
        </div>

        <div class="pc-detail-actions">
          <el-button type="primary" @click="openOriginal(detailItem.url)" :disabled="!detailItem.url">查看原文</el-button>
          <el-button @click="rerunDetection(detailItem.id)">重新检测</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/api'

// ── 硬编码默认筛选项（API 返回数据后按计数合并） ─────────────
const DEFAULT_BRANDS = [
  '全部', '字节跳动', '腾讯', '阿里巴巴', '百度',
  'DeepSeek', '智谱AI', '月之暗面', '科大讯飞', 'Meta',
]
const DEFAULT_CATEGORIES = [
  '全部', '编程开发', '内容创作', '图像生成', '视频制作',
  '办公效率', 'AI平台', '数据分析', '教育学习', '营销推广', '其他',
]

const loading = ref(false)
const timeline = ref([])
const total = ref(0)

const brandOptions = ref([])
const categoryOptions = ref([])
const selectedBrand = ref('')
const selectedCategory = ref('')
const keyword = ref('')
const days = ref(14)

const drawerVisible = ref(false)
const detailItem = ref(null)

// ── 数据加载 ──────────────────────────────────────────

const buildDefaultOptions = (labels) =>
  labels.map(l => ({ value: l === '全部' ? '' : l, label: l, count: 0 }))

const mergeOptions = (defaults, apiItems) => {
  // api 返回有 count 的条目优先，default 中没有的补在后面
  const apiMap = new Map(apiItems.map(i => [i.value, i]))
  const merged = []
  // 先放"全部"
  merged.push({ value: '', label: '全部', count: 0 })
  // 再按 default 顺序放
  for (const d of defaults) {
    if (d.value === '') continue
    const apiItem = apiMap.get(d.value)
    if (apiItem) {
      merged.push(apiItem)
      apiMap.delete(d.value)
    } else {
      merged.push(d)
    }
  }
  // 最后放 API 独有的
  for (const [, v] of apiMap) merged.push(v)
  return merged
}

const fetchFilters = async () => {
  // 先显示默认选项
  brandOptions.value = buildDefaultOptions(DEFAULT_BRANDS)
  categoryOptions.value = buildDefaultOptions(DEFAULT_CATEGORIES)

  try {
    const res = await api.get('/commercial/filters')
    const data = res.data?.data || res.data || {}
    const apiBrands = data.brands || []
    const apiCats = data.categories || []
    if (apiBrands.length > 0) {
      brandOptions.value = mergeOptions(buildDefaultOptions(DEFAULT_BRANDS), apiBrands)
    }
    if (apiCats.length > 0) {
      categoryOptions.value = mergeOptions(buildDefaultOptions(DEFAULT_CATEGORIES), apiCats)
    }
  } catch (e) {
    // API 失败时保留默认选项
    console.warn('筛选维度 API 不可用，使用默认选项', e)
  }
}

const fetchTimeline = async () => {
  loading.value = true
  try {
    const params = { days: days.value }
    if (selectedBrand.value) params.brand = selectedBrand.value
    if (selectedCategory.value) params.category = selectedCategory.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()

    const res = await api.get('/commercial/timeline', { params })
    const data = res.data?.data || res.data || {}
    timeline.value = data.timeline || []
    total.value = data.total || 0
  } catch (e) {
    console.error('获取时间轴失败:', e)
    ElMessage.error('获取潜在商单失败')
  } finally {
    loading.value = false
  }
}

// ── 交互 ──────────────────────────────────────────────
const toggleBrand = (val) => {
  selectedBrand.value = selectedBrand.value === val ? '' : val
  fetchTimeline()
}
const toggleCategory = (val) => {
  selectedCategory.value = selectedCategory.value === val ? '' : val
  fetchTimeline()
}
const changeDays = (d) => {
  days.value = d
  fetchTimeline()
}
const openDetail = (item) => {
  detailItem.value = item
  drawerVisible.value = true
}
const openOriginal = (url) => {
  if (url) window.open(url, '_blank')
}
const rerunDetection = async (id) => {
  try {
    await api.post(`/commercial/raw-infos/${id}/detect`)
    ElMessage.success('已提交重新检测任务')
  } catch (e) {
    ElMessage.error('提交失败')
  }
}

// ── 格式化 ────────────────────────────────────────────
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const formatDayLabel = (dateStr) => {
  if (!dateStr || dateStr === 'unknown') return '未知'
  const d = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(); yesterday.setDate(today.getDate() - 1)
  const m = d.getMonth() + 1, day = d.getDate()
  if (d.toDateString() === today.toDateString()) return `今天 · ${m}/${day}`
  if (d.toDateString() === yesterday.toDateString()) return `昨天 · ${m}/${day}`
  return `${m}月${day}日 周${WEEKDAYS[d.getDay()]}`
}

const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const formatDateTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

const truncate = (t, n) => (!t ? '' : t.length > n ? t.slice(0, n) + '...' : t)

onMounted(() => {
  fetchFilters()
  fetchTimeline()
})
</script>

<style scoped>
.pc-page { max-width: 1080px; margin: 0 auto; }

/* ── Header ── */
.pc-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-bottom: 24px;
}
.pc-title {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', ui-serif, Georgia, serif;
  font-size: 28px; font-weight: 600; color: var(--ink);
  letter-spacing: -.01em; margin: 0; line-height: 1.2;
}
.pc-subtitle { margin: 4px 0 0; font-size: 13.5px; color: var(--ink-4); }

.pc-header-stats {
  display: flex; align-items: center; gap: 14px;
  padding: 8px 18px; background: var(--paper);
  border: 1px solid var(--line); border-radius: var(--r-pill);
}
.pc-stat { display: flex; align-items: baseline; gap: 4px; }
.pc-stat-num { font-size: 18px; font-weight: 700; color: var(--clay); font-variant-numeric: tabular-nums; }
.pc-stat-label { font-size: 12px; color: var(--ink-4); }
.pc-stat-divider { width: 1px; height: 18px; background: var(--line); }

/* ── Filters ── */
.pc-filters {
  display: flex; flex-direction: column; gap: 10px;
  padding: 14px 18px; margin-bottom: 24px;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--r-lg);
}
.pc-filter-row { display: flex; align-items: flex-start; gap: 10px; }
.pc-filter-label {
  font-size: 12px; font-weight: 700; color: var(--ink-4);
  text-transform: uppercase; letter-spacing: .06em;
  padding-top: 6px; min-width: 32px; flex-shrink: 0;
}
.pc-chips { display: flex; flex-wrap: wrap; gap: 5px; }

.pc-chip {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 4px 11px; font-size: 12.5px; font-weight: 500;
  color: var(--ink-3); background: transparent;
  border: 1px solid var(--line); border-radius: var(--r-pill);
  cursor: pointer; transition: all .12s; font-family: inherit;
  line-height: 1.4;
}
.pc-chip:hover { color: var(--ink-2); border-color: var(--clay-soft); background: var(--clay-tint); }
.pc-chip--on { color: #fff; background: var(--clay); border-color: var(--clay); font-weight: 600; }
.pc-chip--on:hover { background: var(--clay-deep); border-color: var(--clay-deep); color: #fff; }
.pc-chip-n { font-size: 10.5px; font-weight: 700; opacity: .65; }

.pc-filter-bar {
  display: flex; align-items: center; gap: 10px;
  margin-top: 4px; padding-top: 10px;
  border-top: 1px solid var(--line);
}

.pc-search {
  position: relative; flex: 1; max-width: 340px;
}
.pc-search-icon {
  position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
  color: var(--ink-4); pointer-events: none;
}
.pc-search-input {
  width: 100%; padding: 7px 12px 7px 32px;
  font-size: 13px; font-family: inherit;
  border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--ivory); color: var(--ink); outline: none;
  transition: border-color .12s;
}
.pc-search-input:focus { border-color: var(--clay-soft); }
.pc-search-input::placeholder { color: var(--ink-4); }

.pc-range-group { display: flex; gap: 3px; margin-left: auto; }
.pc-range-btn {
  padding: 5px 10px; font-size: 12px; font-family: inherit;
  color: var(--ink-4); background: transparent;
  border: 1px solid transparent; border-radius: var(--r-pill);
  cursor: pointer; transition: all .12s; font-weight: 500;
}
.pc-range-btn:hover { color: var(--ink-2); background: var(--bone); }
.pc-range-btn--on { color: var(--clay-deep); background: var(--clay-tint); border-color: var(--clay-soft); font-weight: 600; }

/* ── Loading ── */
.pc-loading { display: flex; justify-content: center; padding: 80px 0; }
.pc-spinner {
  width: 22px; height: 22px; border-radius: 50%;
  border: 2.5px solid var(--line); border-top-color: var(--clay);
  animation: pc-spin .7s linear infinite;
}
@keyframes pc-spin { to { transform: rotate(360deg); } }

/* ── Empty ── */
.pc-empty {
  text-align: center; padding: 64px 0 80px;
  display: flex; flex-direction: column; align-items: center;
}
.pc-empty-art {
  width: 96px; height: 96px; border-radius: 50%;
  background: var(--ivory); border: 1px solid var(--line);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 18px;
}
.pc-empty-title { font-size: 15px; font-weight: 600; color: var(--ink-2); margin: 0 0 6px; }
.pc-empty-hint { font-size: 13px; color: var(--ink-4); margin: 0; }

/* ── Timeline ── */
.pc-timeline { position: relative; }

.pc-day { position: relative; padding-left: 96px; }
.pc-day + .pc-day { margin-top: 4px; }

.pc-day-head {
  position: absolute; left: 0; top: 0;
  width: 80px; text-align: right;
  display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
}
.pc-day-dot {
  position: absolute; right: -14px; top: 4px;
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--clay); border: 2px solid var(--ivory);
  z-index: 2;
}
.pc-day-text { font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.2; }
.pc-day-count {
  font-size: 11px; color: var(--ink-4); font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.pc-day-list {
  display: flex; flex-direction: column; gap: 8px;
  padding: 0 0 20px 16px;
  border-left: 2px solid var(--line);
}
.pc-day:last-child .pc-day-list { border-left-color: transparent; }

/* ── Card ── */
.pc-card {
  padding: 12px 16px;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--r-md); cursor: pointer;
  transition: all .12s;
}
.pc-card:hover {
  border-color: var(--clay-soft);
  box-shadow: 0 2px 8px rgba(31,31,30,.06);
}

.pc-card-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}
.pc-card-source { font-size: 11.5px; color: var(--ink-4); font-weight: 500; }
.pc-card-time { font-size: 11px; color: var(--ink-4); font-variant-numeric: tabular-nums; }

.pc-card-title {
  font-size: 14.5px; font-weight: 600; color: var(--ink);
  line-height: 1.45; margin-bottom: 4px;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.pc-card-desc {
  font-size: 12.5px; color: var(--ink-3); line-height: 1.55;
  margin-bottom: 8px;
  display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}

.pc-card-foot {
  display: flex; align-items: center; justify-content: space-between;
}
.pc-card-tags { display: flex; flex-wrap: wrap; gap: 4px; }

.pc-tag {
  display: inline-block; padding: 1px 8px;
  font-size: 11px; font-weight: 600; border-radius: 4px;
  line-height: 1.5;
}
.pc-tag--brand { background: var(--clay-tint); color: var(--clay-deep); }
.pc-tag--cat { background: var(--pine-soft, #E8EDEB); color: var(--pine, #3F5C52); }
.pc-tag--prod { background: var(--bone); color: var(--ink-3); }

.pc-level {
  font-size: 11px; font-weight: 700; padding: 2px 8px;
  border-radius: var(--r-pill); flex-shrink: 0;
}
.pc-level--high { background: var(--sand-soft, #ECDCBF); color: #7A5A2E; }
.pc-level--mid { background: var(--bone); color: var(--ink-3); }

/* ── Detail drawer ── */
.pc-detail { padding: 0 4px; }

.pc-detail-meta {
  display: flex; flex-direction: column; gap: 9px;
  padding: 14px 16px; background: var(--ivory);
  border-radius: var(--r-md); margin-bottom: 18px;
}
.pc-meta-row {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--ink-2);
}
.pc-meta-k {
  font-weight: 600; color: var(--ink-3); min-width: 64px; flex-shrink: 0;
}

.pc-detail-section { margin-bottom: 18px; }
.pc-detail-section h3 {
  font-size: 13px; font-weight: 700; color: var(--ink);
  margin: 0 0 6px; letter-spacing: .02em;
}
.pc-detail-section p {
  font-size: 13.5px; color: var(--ink-2); line-height: 1.7; margin: 0;
}

.pc-detail-actions {
  display: flex; gap: 8px; padding-top: 14px;
  border-top: 1px solid var(--line);
}
</style>
