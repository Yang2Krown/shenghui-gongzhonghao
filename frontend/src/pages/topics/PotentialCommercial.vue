<template>
  <div class="pc-page">
    <header class="pc-hero">
      <div class="pc-kicker"><span class="kicker-dot"></span>COMMERCIAL RADAR<span class="pc-window">近 10 天</span></div>
      <div class="pc-header">
        <div>
          <h1 class="pc-title">潜在商单</h1>
          <p class="pc-subtitle">从公众号投放内容里，快速找到值得跟进的品牌线索。</p>
        </div>
        <div class="pc-stats" v-if="total > 0">
          <div><b>{{ brandCount }}</b><span>品牌线索</span></div>
          <div><b>{{ total }}</b><span>篇文章</span></div>
        </div>
      </div>
    </header>

    <section class="pc-filters">
      <div class="filter-topline">
        <div>
          <span class="section-eyebrow">筛选线索</span>
          <p>先按判断置信度缩小范围，再定位甲方和内容方向。</p>
        </div>
        <button v-if="hasActiveFilters" class="reset-btn" @click="resetFilters">清除筛选</button>
      </div>

      <div class="status-row" role="tablist" aria-label="商单概率">
        <button
          v-for="option in levelOptions"
          :key="option.value"
          :class="['status-btn', option.tone, selectedLevel === option.value && 'is-on']"
          @click="toggleLevel(option.value)"
        >
          <span class="status-dot"></span>{{ option.label }}<em v-if="option.value === ''">{{ total || '全部' }}</em>
        </button>
      </div>

      <div class="filter-controls">
        <label class="select-field">
          <span class="select-label">甲方</span>
          <strong class="select-value">{{ selectedBrand || '全部' }}</strong>
          <select v-model="selectedBrand" @change="fetchGroups">
            <option v-for="opt in brandOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}<template v-if="opt.count"> · {{ opt.count }}</template>
            </option>
          </select>
        </label>
        <label class="select-field">
          <span class="select-label">内容方向</span>
          <strong class="select-value">{{ selectedCategory || '全部' }}</strong>
          <select v-model="selectedCategory" @change="fetchGroups">
            <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}<template v-if="opt.count"> · {{ opt.count }}</template>
            </option>
          </select>
        </label>
        <div class="search-field">
          <span class="search-icon">⌕</span>
          <input
            v-model="keyword"
            placeholder="搜索品牌、产品、标题或摘要"
            @keyup.enter="fetchGroups"
          />
          <button :disabled="loading" @click="fetchGroups">搜索</button>
        </div>
      </div>

      <div v-if="hasActiveFilters" class="active-filters">
        <span>当前筛选</span>
        <button v-if="selectedLevel" @click="toggleLevel('')">{{ selectedLevel === 'likely' ? '高概率' : '潜在' }} ×</button>
        <button v-if="selectedBrand" @click="selectedBrand = ''; fetchGroups()">{{ selectedBrand }} ×</button>
        <button v-if="selectedCategory" @click="selectedCategory = ''; fetchGroups()">{{ selectedCategory }} ×</button>
        <button v-if="keyword.trim()" @click="keyword = ''; fetchGroups()">“{{ keyword.trim() }}” ×</button>
      </div>
    </section>

    <div v-if="!loading && groups.length" class="result-heading">
      <div>
        <span class="section-eyebrow">BRAND SIGNALS</span>
        <h2>值得跟进的品牌线索</h2>
      </div>
      <span class="result-count">{{ brandCount }} 个品牌 · {{ total }} 篇文章</span>
    </div>

    <div v-if="loading" class="pc-loading">加载中...</div>
    <div v-else-if="groups.length === 0" class="pc-empty">
      <span class="empty-mark">—</span>
      <h3>暂时没有匹配的线索</h3>
      <p>可以清除筛选，或扩大搜索范围再试一次。</p>
    </div>

    <div v-else class="pc-grid">
      <section v-for="group in groups" :key="group.brand" class="brand-card">
        <div class="brand-head">
          <div class="brand-mark">{{ group.brand.slice(0, 1) }}</div>
          <div>
            <h2>{{ group.brand }}</h2>
            <p><span class="category-label">{{ group.category || '其他' }}</span><span class="category-separator">/</span>品牌投放线索</p>
          </div>
          <div class="brand-count"><b>{{ group.count }}</b><span>篇文章</span></div>
        </div>

        <div class="brand-meta">
          <div>
            <span>投放账号</span>
            <strong>{{ group.accounts.slice(0, 4).join('、') || '未知账号' }}</strong>
          </div>
          <div>
            <span>最新采集</span>
            <strong>{{ formatDate(group.last_time) }}</strong>
          </div>
        </div>

        <div class="placements-heading">
          <span class="placements-heading-title"><span class="article-icon">▤</span>投放文章</span>
          <span>{{ group.items.length > 5 ? `前 5 / 共 ${group.items.length}` : `${group.items.length} 篇` }}</span>
        </div>
        <div class="placements">
          <article v-for="item in group.items.slice(0, 5)" :key="item.id" class="placement">
            <div class="placement-main" @click="openDetail(item)">
              <span :class="['placement-dot', item.commercial_level]"></span>
              <div class="placement-title">{{ item.title }}</div>
              <div class="placement-sub">
                <span>{{ item.source_account_name || item.author || '未知账号' }}</span>
                <span>{{ timeLabel(item) }}</span>
              </div>
              <div v-if="item.product || item.advantages?.length" class="placement-insight">
                <span v-if="item.product" class="placement-product-tag">{{ item.product }}</span>
                <span v-for="adv in item.advantages?.slice(0, 2)" :key="`${item.id}-${adv}`" class="placement-advantage-tag">{{ adv }}</span>
              </div>
            </div>
            <button class="link-btn" @click.stop="openOriginal(item.url)">原文</button>
          </article>
        </div>

        <button v-if="group.items.length > 5" class="more-btn" @click="openGroup(group)">
          查看全部 {{ group.items.length }} 篇
        </button>
      </section>
    </div>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="560px" direction="rtl" :lock-scroll="false" @open="restoreDrawerScroll" @opened="restoreDrawerScroll" @closed="restoreDrawerScroll">
      <div v-if="detailItem" class="detail">
        <h3>{{ detailItem.title }}</h3>
        <div class="detail-tags">
          <span v-if="detailItem.commercial_brand">{{ detailItem.commercial_brand }}</span>
          <span v-if="detailItem.product">{{ detailItem.product }}</span>
          <span v-if="detailItem.commercial_category">{{ detailItem.commercial_category }}</span>
        </div>
        <dl>
          <div><dt>投放账号</dt><dd>{{ detailItem.source_account_name || detailItem.author || '未知账号' }}</dd></div>
          <div><dt>发布时间</dt><dd>{{ formatDateTime(detailItem.published_at) }}</dd></div>
          <div><dt>采集时间</dt><dd>{{ formatDateTime(detailItem.scraped_at) }}</dd></div>
        </dl>
        <section v-if="detailItem.advantages?.length">
          <h4>产品优势</h4>
          <div class="detail-markdown detail-markdown-ordered" v-html="renderMarkdown(detailItem.advantages, true)"></div>
        </section>
        <section v-if="detailItem.summary">
          <h4>摘要</h4>
          <div class="detail-markdown" v-html="renderMarkdown(detailItem.summary)"></div>
        </section>
        <div class="detail-actions">
          <el-button type="primary" @click="openOriginal(detailItem.url)">查看原文</el-button>
        </div>
      </div>

      <div v-else-if="detailGroup" class="detail">
        <h3>{{ detailGroup.brand }}</h3>
        <div class="placements drawer-list">
          <article v-for="item in detailGroup.items" :key="item.id" class="placement">
            <div class="placement-main" @click="openDetail(item)">
              <span :class="['placement-dot', item.commercial_level]"></span>
              <div class="placement-title">{{ item.title }}</div>
              <div class="placement-sub">
                <span>{{ item.source_account_name || item.author || '未知账号' }}</span>
                <span>{{ timeLabel(item) }}</span>
              </div>
            </div>
            <button class="link-btn" @click.stop="openOriginal(item.url)">原文</button>
          </article>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import api from '@/api/api'

const DEFAULT_BRANDS = ['全部', '字节跳动', '腾讯', '阿里巴巴', '百度', 'DeepSeek', '智谱AI', '月之暗面', '科大讯飞', '其他']
const DEFAULT_CATEGORIES = ['全部', '编程开发', '内容创作', '图像生成', '视频制作', '办公效率', 'AI平台', '数据分析', '教育学习', '营销推广', '硬件产品', '其他']
const levelOptions = [
  { label: '全部线索', value: '', tone: 'all' },
  { label: '高概率', value: 'likely', tone: 'likely' },
  { label: '潜在', value: 'suspected', tone: 'suspected' },
]

const loading = ref(false)
const groups = ref([])
const total = ref(0)
const brandCount = ref(0)
const brandOptions = ref([])
const categoryOptions = ref([])
const selectedBrand = ref('')
const selectedCategory = ref('')
const selectedLevel = ref('')
const keyword = ref('')
const DISPLAY_WINDOW_DAYS = 10

const drawerVisible = ref(false)
const detailItem = ref(null)
const detailGroup = ref(null)
const drawerScrollY = ref(0)
const drawerTitle = computed(() => detailItem.value?.title || detailGroup.value?.brand || '商单详情')
const hasActiveFilters = computed(() => Boolean(
  selectedLevel.value || selectedBrand.value || selectedCategory.value || keyword.value.trim()
))

const defaults = (labels) => labels.map(label => ({ label, value: label === '全部' ? '' : label, count: 0 }))
const mergeOptions = (base, apiItems) => {
  const map = new Map((apiItems || []).map(i => [i.value, i]))
  const out = [{ label: '全部', value: '', count: 0 }]
  for (const item of base) {
    if (!item.value) continue
    out.push(map.get(item.value) || item)
    map.delete(item.value)
  }
  for (const [, item] of map) out.push(item)
  // “其他”始终作为兜底分类，放在所有已知和动态分类之后。
  const otherIndex = out.findIndex(item => item.value === '其他')
  if (otherIndex >= 0) out.push(out.splice(otherIndex, 1)[0])
  return out
}

const fetchFilters = async () => {
  brandOptions.value = defaults(DEFAULT_BRANDS)
  categoryOptions.value = defaults(DEFAULT_CATEGORIES)
  try {
    const res = await api.get('/commercial/filters')
    const data = res.data || {}
    brandOptions.value = mergeOptions(defaults(DEFAULT_BRANDS), data.brands || [])
    categoryOptions.value = mergeOptions(defaults(DEFAULT_CATEGORIES), data.categories || [])
  } catch (e) {
    console.warn('commercial filters fallback', e)
  }
}

const fetchGroups = async () => {
  loading.value = true
  try {
    // 接口按相同窗口预筛一次；前端仍会再次过滤，确保任何异常数据都不会露出。
    const params = { days: DISPLAY_WINDOW_DAYS }
    if (selectedLevel.value) params.level = selectedLevel.value
    if (selectedBrand.value) params.brand = selectedBrand.value
    if (selectedCategory.value) params.category = selectedCategory.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    const res = await api.get('/commercial/groups', { params })
    const data = res.data || {}
    groups.value = keepRecentGroups(data.groups || [])
    total.value = groups.value.reduce((sum, group) => sum + group.count, 0)
    brandCount.value = groups.value.length
  } catch (e) {
    console.error(e)
    ElMessage.error('获取潜在商单失败')
  } finally {
    loading.value = false
  }
}

const toggleLevel = (value) => {
  selectedLevel.value = selectedLevel.value === value ? '' : value
  fetchGroups()
}
const resetFilters = () => {
  selectedLevel.value = ''
  selectedBrand.value = ''
  selectedCategory.value = ''
  keyword.value = ''
  fetchGroups()
}
const rememberDrawerScroll = () => {
  drawerScrollY.value = document.scrollingElement?.scrollTop || window.scrollY || document.documentElement.scrollTop || 0
}
const restoreDrawerScroll = () => {
  const restore = () => {
    if (document.scrollingElement) document.scrollingElement.scrollTop = drawerScrollY.value
    document.documentElement.scrollTop = drawerScrollY.value
    document.body.scrollTop = drawerScrollY.value
    window.scrollTo({ left: 0, top: drawerScrollY.value, behavior: 'auto' })
  }
  nextTick(() => {
    restore()
    requestAnimationFrame(restore)
  })
}
const openDetail = (item) => {
  detailGroup.value = null
  detailItem.value = item
  rememberDrawerScroll()
  drawerVisible.value = true
}
const openGroup = (group) => {
  detailItem.value = null
  detailGroup.value = group
  rememberDrawerScroll()
  drawerVisible.value = true
}
const openOriginal = (url) => {
  if (url) window.open(url, '_blank')
}
const renderMarkdown = (value, ordered = false) => {
  const source = Array.isArray(value)
    ? value
      .filter(Boolean)
      .map(item => String(item).trim())
      .map((item, index) => {
        if (/^[-*+]\s/.test(item) || /^\d+[.)、]\s?/.test(item)) return item
        return ordered ? `${index + 1}. ${item}` : `- ${item}`
      })
      .join('\n')
    : String(value || '')
  return marked.parse(source, { breaks: true })
}

const formatDate = (iso) => {
  if (!iso) return '未知'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
const formatDateTime = (iso) => {
  if (!iso) return '未知'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
const timeLabel = (item) => {
  if (item.published_at) return `发布 ${formatDateTime(item.published_at)}`
  if (item.scraped_at) return `采集 ${formatDateTime(item.scraped_at)}`
  return '时间未知'
}

const isWithinDisplayWindow = (item) => {
  // 潜在商单按文章发布时间判断时间窗口，不使用采集时间替代。
  const timestamp = item.published_at
  const time = timestamp ? new Date(timestamp).getTime() : NaN
  return Number.isFinite(time) && time >= Date.now() - DISPLAY_WINDOW_DAYS * 24 * 60 * 60 * 1000
}

const keepRecentGroups = (sourceGroups) => sourceGroups
  .map((group) => {
    const items = (group.items || []).filter(isWithinDisplayWindow)
    const accounts = [...new Set(items
      .map(item => item.source_account_name || item.author)
      .filter(Boolean))]
    return {
      ...group,
      items,
      accounts,
      count: items.length,
      last_time: items.reduce((latest, item) => {
        const value = item.published_at
        return !latest || (value && new Date(value) > new Date(latest)) ? value : latest
      }, null),
    }
  })
  .filter(group => group.items.length > 0)

onMounted(() => {
  fetchFilters()
  fetchGroups()
})
</script>

<style scoped>
.pc-page { max-width: 1240px; margin: 0 auto; padding-bottom: 48px; }
.pc-hero { margin-bottom: 24px; }
.pc-kicker { display: flex; align-items: center; gap: 8px; margin-bottom: 13px; color: var(--clay); font-size: 10px; font-weight: 800; letter-spacing: .16em; }
.kicker-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--clay); box-shadow: 0 0 0 4px var(--clay-tint); }
.pc-window { margin-left: 5px; padding: 4px 8px; border-radius: 999px; background: var(--bone); color: var(--ink-4); font-size: 10px; letter-spacing: .02em; }
.pc-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; }
.pc-title { margin: 0; color: var(--ink); font-family: "Source Han Serif SC", "Songti SC", "STSong", "Noto Serif SC", Georgia, serif; font-size: 30px; font-weight: 500; letter-spacing: 0; line-height: 1.2; }
.pc-subtitle { max-width: 520px; margin: 12px 0 0; color: var(--ink-4); font-size: 14px; line-height: 1.6; }
.pc-stats { display: flex; gap: 28px; padding: 4px 2px 2px; }
.pc-stats div { min-width: 82px; }
.pc-stats b { display: block; color: var(--clay); font-family: var(--font-serif, var(--serif)); font-size: 30px; font-weight: 500; letter-spacing: -.04em; line-height: 1; }
.pc-stats span { display: block; margin-top: 8px; color: var(--ink-4); font-size: 11px; }
.pc-filters { padding: 20px; margin-bottom: 34px; border: 1px solid var(--line); border-radius: 16px; background: var(--paper); box-shadow: 0 13px 34px rgba(71, 54, 39, .055); }
.filter-topline { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-eyebrow { color: var(--clay); font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.filter-topline p { margin: 6px 0 0; color: var(--ink-4); font-size: 12px; }
.reset-btn { border: 0; padding: 2px 0; background: transparent; color: var(--clay); font: inherit; font-size: 12px; cursor: pointer; }
.reset-btn:hover { color: var(--clay-deep, var(--clay)); text-decoration: underline; }
.status-row { display: flex; gap: 6px; margin-top: 18px; padding: 4px; border-radius: 10px; background: var(--ivory); width: fit-content; }
.status-btn { display: inline-flex; align-items: center; gap: 7px; border: 0; border-radius: 7px; padding: 8px 11px; background: transparent; color: var(--ink-4); font: inherit; font-size: 12px; cursor: pointer; transition: background .18s ease, color .18s ease, box-shadow .18s ease; }
.status-btn:hover { color: var(--ink); }
.status-btn.is-on { background: var(--paper); color: var(--ink); box-shadow: 0 2px 8px rgba(71, 54, 39, .1); }
.status-btn em { color: var(--ink-4); font-size: 11px; font-style: normal; }
.status-btn.is-on em { color: var(--clay); }
.status-dot, .placement-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-4); }
.status-btn.likely .status-dot, .placement-dot.likely { background: #b95f43; }
.status-btn.suspected .status-dot, .placement-dot.suspected { background: #d49a57; }
.filter-controls { display: grid; grid-template-columns: 180px 190px minmax(240px, 1fr); gap: 10px; margin-top: 14px; }
.select-field, .search-field { display: flex; align-items: center; min-width: 0; height: 42px; border: 1px solid var(--line); border-radius: 9px; background: var(--ivory); transition: border-color .18s ease, box-shadow .18s ease; }
.select-field:focus-within, .search-field:focus-within { border-color: var(--clay-soft, var(--clay)); box-shadow: 0 0 0 3px var(--clay-tint); }
.select-field { position: relative; padding: 0 12px; cursor: pointer; overflow: hidden; }
.select-label, .select-value, .select-field::after { position: relative; z-index: 1; pointer-events: none; }
.select-label { flex: none; margin-right: 9px; color: var(--ink-4); font-size: 11px; }
.select-value { min-width: 0; overflow: hidden; color: var(--ink-2); font-size: 13px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.select-field select { position: absolute; z-index: 2; inset: 0; width: 100%; height: 100%; border: 0; outline: 0; opacity: 0; cursor: pointer; }
.select-field::after { content: '⌄'; margin-left: auto; color: var(--ink-4); font-size: 13px; }
.search-field { padding-left: 12px; }
.search-icon { margin-right: 8px; color: var(--clay); font-size: 20px; line-height: 1; transform: rotate(-20deg); }
.search-field input { min-width: 0; flex: 1; height: 100%; border: 0; outline: 0; background: transparent; color: var(--ink); font: inherit; font-size: 13px; }
.search-field input::placeholder { color: var(--ink-4); }
.search-field button { height: 30px; margin-right: 5px; padding: 0 12px; border: 0; border-radius: 6px; background: var(--clay); color: var(--paper); font: inherit; font-size: 12px; cursor: pointer; }
.search-field button:hover { background: var(--clay-deep, var(--clay)); }
.search-field button:disabled { cursor: wait; opacity: .6; }
.active-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin-top: 13px; color: var(--ink-4); font-size: 11px; }
.active-filters button { padding: 5px 8px; border: 1px solid var(--clay-tint); border-radius: 999px; background: var(--clay-tint); color: var(--clay); font: inherit; cursor: pointer; }
.active-filters button:hover { border-color: var(--clay-soft, var(--clay)); }
.result-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 15px; }
.result-heading h2 { margin: 5px 0 0; color: var(--ink); font-family: var(--font-serif, var(--serif)); font-size: 23px; font-weight: 500; letter-spacing: -.025em; }
.result-count { padding-bottom: 3px; color: var(--ink-4); font-size: 12px; }
.pc-loading, .pc-empty { padding: 70px 20px; text-align: center; color: var(--ink-4); border: 1px dashed var(--line); border-radius: 15px; background: var(--paper); }
.empty-mark { display: block; margin-bottom: 9px; color: var(--clay); font-family: var(--font-serif, var(--serif)); font-size: 34px; }
.pc-empty h3 { margin: 0; color: var(--ink-2); font-size: 16px; font-weight: 600; }
.pc-empty p { margin: 8px 0 0; font-size: 13px; }
.pc-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 17px; }
.brand-card { min-width: 0; padding: 20px; border: 1px solid var(--line); border-radius: 15px; background: var(--paper); transition: border-color .18s ease, transform .18s ease, box-shadow .18s ease; }
.brand-card:hover { border-color: var(--clay-soft, var(--line)); box-shadow: 0 16px 34px rgba(71, 54, 39, .075); transform: translateY(-2px); }
.brand-head { display: grid; grid-template-columns: 42px minmax(0, 1fr) auto; align-items: center; gap: 11px; margin-bottom: 18px; }
.brand-mark { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 12px; background: var(--clay-tint); color: var(--clay); font-family: var(--font-serif, var(--serif)); font-size: 21px; }
.brand-head h2 { margin: 0; color: var(--ink); font-family: var(--font-serif, var(--serif)); font-size: 22px; font-weight: 500; letter-spacing: -.025em; }
.brand-head p { display: flex; align-items: center; gap: 7px; margin: 5px 0 0; color: var(--ink-4); font-size: 12px; }
.category-label { color: var(--clay); }
.category-separator { color: var(--line-deep, var(--line)); }
.brand-count { display: flex; align-items: baseline; gap: 5px; white-space: nowrap; color: var(--ink-4); }
.brand-count b { color: var(--clay); font-family: var(--font-serif, var(--serif)); font-size: 24px; font-weight: 500; }
.brand-count span { font-size: 11px; }
.brand-meta { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(90px, .65fr); gap: 9px; padding: 11px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.brand-meta div { min-width: 0; }
.brand-meta span { display: block; margin-bottom: 5px; color: var(--ink-4); font-size: 10px; letter-spacing: .04em; }
.brand-meta strong { display: block; color: var(--ink-2); font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.placements-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 18px 0 10px; color: var(--ink-4); font-size: 11px; }
.placements-heading-title { display: inline-flex; align-items: center; gap: 7px; color: var(--ink-2); font-size: 13px; font-weight: 750; }
.article-icon { display: inline-grid; width: 21px; height: 21px; place-items: center; border-radius: 6px; background: var(--clay); color: var(--paper); font-size: 12px; line-height: 1; }
.placements { display: flex; flex-direction: column; gap: 8px; }
.placement { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 13px; border: 1px solid var(--bone); border-radius: 10px; background: var(--ivory); transition: border-color .18s ease, background .18s ease, box-shadow .18s ease; }
.placement:hover { border-color: var(--clay-soft, var(--clay)); background: var(--paper); box-shadow: 0 5px 14px rgba(71, 54, 39, .06); }
.placement:last-child { border-bottom: 1px solid var(--bone); }
.placement-main { display: grid; grid-template-columns: 7px minmax(0, 1fr); column-gap: 9px; min-width: 0; flex: 1; cursor: pointer; }
.placement-main:hover .placement-title { color: var(--clay); }
.placement-dot { grid-row: 1 / span 3; align-self: start; margin-top: 6px; }
.placement-dot.likely { box-shadow: 0 0 0 3px rgba(185, 95, 67, .12); }
.placement-dot.suspected { box-shadow: 0 0 0 3px rgba(212, 154, 87, .12); }
.placement-title, .placement-sub, .placement-insight { grid-column: 2; }
.placement-title { display: -webkit-box; color: var(--ink); font-size: 15px; font-weight: 700; line-height: 1.5; overflow: hidden; text-overflow: ellipsis; white-space: normal; -webkit-box-orient: vertical; -webkit-line-clamp: 2; transition: color .18s ease; }
.placement-sub { display: flex; gap: 9px; margin-top: 6px; color: var(--ink-4); font-size: 11px; }
.placement-sub span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.placement-insight { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.placement-insight span { display: inline-flex; align-items: center; max-width: 100%; padding: 4px 9px; border: 1px solid var(--line); border-radius: 999px; background: var(--paper); color: var(--ink-3); font-size: 11px; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.placement-insight .placement-product-tag { border-color: rgba(204, 120, 92, .32); background: var(--clay-tint); color: var(--clay-deep, var(--clay)); font-weight: 650; }
.placement-insight .placement-advantage-tag { background: var(--paper); color: var(--ink-3); }
.link-btn, .more-btn { border: 1px solid var(--line); border-radius: 7px; background: var(--paper); color: var(--ink-3); cursor: pointer; transition: border-color .18s ease, color .18s ease, background .18s ease; }
.link-btn:hover, .more-btn:hover { border-color: var(--clay-soft, var(--clay)); background: var(--clay-tint); color: var(--clay); }
.link-btn { flex: none; padding: 6px 8px; font-size: 11px; }
.more-btn { width: 100%; margin-top: 10px; padding: 8px; font-size: 12px; }
.detail ul { margin: 0; padding-left: 18px; color: var(--ink-3); font-size: 13px; line-height: 1.7; }
.detail-markdown { color: var(--ink-3); font-size: 13px; line-height: 1.75; }
.detail-markdown :deep(p) { margin: 0 0 9px; }
.detail-markdown :deep(p:last-child) { margin-bottom: 0; }
.detail-markdown :deep(ul), .detail-markdown :deep(ol) { margin: 0 0 9px; padding-left: 20px; }
.detail-markdown :deep(li) { margin: 3px 0; }
.detail-markdown-ordered :deep(ol) { padding-left: 0; list-style: none; counter-reset: advantage; }
.detail-markdown-ordered :deep(li) { position: relative; padding-left: 24px; counter-increment: advantage; }
.detail-markdown-ordered :deep(li)::before { position: absolute; left: 0; color: var(--clay); content: counter(advantage) '、'; font-weight: 700; }
.detail-markdown :deep(strong) { color: var(--ink-2); font-weight: 700; }
.detail-markdown :deep(a) { color: var(--clay); text-decoration: underline; text-underline-offset: 2px; }
.detail-markdown :deep(blockquote) { margin: 8px 0; padding: 6px 11px; border-left: 3px solid var(--clay-soft, var(--clay)); background: var(--ivory); color: var(--ink-3); }
.detail-markdown :deep(code) { padding: 2px 5px; border-radius: 4px; background: var(--ivory); color: var(--clay-deep, var(--clay)); font-size: .92em; }
.detail-markdown :deep(pre) { max-width: 100%; padding: 10px; overflow-x: auto; border-radius: 7px; background: var(--ink); color: var(--paper); }
.detail-markdown :deep(pre code) { padding: 0; background: transparent; color: inherit; }
.detail h3 { margin: 0 0 12px; color: var(--ink); line-height: 1.35; }
.detail-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.detail-tags span { border-radius: 999px; padding: 5px 9px; background: var(--clay-tint); color: var(--clay); font-size: 12px; }
.detail dl { margin: 0 0 16px; }
.detail dl div { display: grid; grid-template-columns: 78px 1fr; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.detail dt { color: var(--ink-4); }
.detail dd { margin: 0; color: var(--ink-2); }
.detail h4 { margin: 16px 0 8px; color: var(--ink); }
.detail p { color: var(--ink-3); line-height: 1.7; }
.detail-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 28px; padding-top: 16px; border-top: 1px solid var(--line); }
.drawer-list { margin-top: 12px; }
@media (max-width: 900px) {
  .filter-controls { grid-template-columns: 1fr 1fr; }
  .search-field { grid-column: 1 / -1; }
  .pc-grid { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .pc-header, .filter-topline, .result-heading { align-items: flex-start; flex-direction: column; }
  .pc-title { font-size: 30px; }
  .pc-stats { width: 100%; justify-content: space-between; gap: 12px; padding-top: 15px; border-top: 1px solid var(--line); }
  .pc-stats div { flex: 1; }
  .pc-filters { padding: 16px; }
  .status-row { width: 100%; }
  .status-btn { flex: 1; justify-content: center; padding-left: 6px; padding-right: 6px; }
  .filter-controls { grid-template-columns: 1fr; }
  .search-field { grid-column: auto; }
  .brand-card { padding: 16px; }
  .brand-meta { grid-template-columns: 1fr; gap: 10px; }
  .result-count { padding: 0; }
}
</style>
