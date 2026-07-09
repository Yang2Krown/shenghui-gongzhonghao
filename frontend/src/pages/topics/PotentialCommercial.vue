<template>
  <div class="pc-page">
    <div class="pc-header">
      <div>
        <h1 class="pc-title">潜在商单</h1>
        <p class="pc-subtitle">按品牌聚合公众号投放，快速查看投放账号、时间和链接</p>
      </div>
      <div class="pc-stats" v-if="total > 0">
        <div><b>{{ brandCount }}</b><span>品牌</span></div>
        <div><b>{{ total }}</b><span>篇文章</span></div>
      </div>
    </div>

    <div class="pc-filters">
      <div class="pc-filter-line">
        <span class="pc-filter-label">甲方</span>
        <button
          v-for="opt in brandOptions"
          :key="opt.value"
          :class="['pc-chip', selectedBrand === opt.value && 'is-on']"
          @click="toggleBrand(opt.value)"
        >
          {{ opt.label }}<em v-if="opt.count">{{ opt.count }}</em>
        </button>
      </div>
      <div class="pc-filter-line">
        <span class="pc-filter-label">方向</span>
        <button
          v-for="opt in categoryOptions"
          :key="opt.value"
          :class="['pc-chip', selectedCategory === opt.value && 'is-on']"
          @click="toggleCategory(opt.value)"
        >
          {{ opt.label }}<em v-if="opt.count">{{ opt.count }}</em>
        </button>
      </div>
      <div class="pc-toolbar">
        <input
          v-model="keyword"
          class="pc-search"
          placeholder="搜索品牌、产品、标题、摘要"
          @keyup.enter="fetchGroups"
        />
        <div class="pc-days">
          <button v-for="d in [7, 30, 90, 180]" :key="d" :class="{ on: days === d }" @click="changeDays(d)">
            {{ d }}天
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="pc-loading">加载中...</div>
    <div v-else-if="groups.length === 0" class="pc-empty">
      <h3>暂无潜在商单</h3>
      <p>极致了历史/当天接口入库后，DeepSeek 会自动判断并聚合到这里。</p>
    </div>

    <div v-else class="pc-grid">
      <section v-for="group in groups" :key="group.brand" class="brand-card">
        <div class="brand-head">
          <div>
            <h2>{{ group.brand }}</h2>
            <p>{{ group.category || '其他' }}</p>
          </div>
          <span :class="['brand-count', group.count >= 3 && 'hot']">{{ group.count }} 篇</span>
        </div>

        <div class="brand-meta">
          <div>
            <span>投放账号</span>
            <strong>{{ group.accounts.slice(0, 4).join('、') || '未知账号' }}</strong>
          </div>
          <div>
            <span>最新采集</span>
            <strong>{{ formatDateTime(group.last_time) }}</strong>
          </div>
        </div>

        <div class="placements">
          <article v-for="item in group.items.slice(0, 5)" :key="item.id" class="placement">
            <div class="placement-main" @click="openDetail(item)">
              <div class="placement-title">{{ item.title }}</div>
              <div class="placement-sub">
                <span>{{ item.source_account_name || item.author || '未知账号' }}</span>
                <span>{{ timeLabel(item) }}</span>
                <span :class="['level', item.commercial_level]">
                  {{ item.commercial_level === 'likely' ? '高概率' : '潜在' }}
                </span>
              </div>
              <div v-if="item.product || item.advantages?.length" class="placement-insight">
                <span v-if="item.product">{{ item.product }}</span>
                <span v-for="adv in item.advantages?.slice(0, 2)" :key="`${item.id}-${adv}`">{{ adv }}</span>
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

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="560px" direction="rtl">
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
          <div><dt>判断理由</dt><dd>{{ detailItem.reason || '暂无' }}</dd></div>
        </dl>
        <section v-if="detailItem.advantages?.length">
          <h4>产品优势</h4>
          <ul><li v-for="adv in detailItem.advantages" :key="adv">{{ adv }}</li></ul>
        </section>
        <section v-if="detailItem.evidence?.length">
          <h4>判断证据</h4>
          <ul><li v-for="ev in detailItem.evidence" :key="ev">{{ ev }}</li></ul>
        </section>
        <section v-if="detailItem.summary">
          <h4>摘要</h4>
          <p>{{ detailItem.summary }}</p>
        </section>
        <div class="detail-actions">
          <el-button type="primary" @click="openOriginal(detailItem.url)">查看原文</el-button>
          <el-button @click="rerunDetection(detailItem.id)">DeepSeek 重检</el-button>
        </div>
      </div>

      <div v-else-if="detailGroup" class="detail">
        <h3>{{ detailGroup.brand }}</h3>
        <div class="placements drawer-list">
          <article v-for="item in detailGroup.items" :key="item.id" class="placement">
            <div class="placement-main" @click="openDetail(item)">
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/api'

const DEFAULT_BRANDS = ['全部', '字节跳动', '腾讯', '阿里巴巴', '百度', 'DeepSeek', '智谱AI', '月之暗面', '科大讯飞', '其他']
const DEFAULT_CATEGORIES = ['全部', '编程开发', '内容创作', '图像生成', '视频制作', '办公效率', 'AI平台', '数据分析', '教育学习', '营销推广', '硬件产品', '其他']

const loading = ref(false)
const groups = ref([])
const total = ref(0)
const brandCount = ref(0)
const brandOptions = ref([])
const categoryOptions = ref([])
const selectedBrand = ref('')
const selectedCategory = ref('')
const keyword = ref('')
const days = ref(30)

const drawerVisible = ref(false)
const detailItem = ref(null)
const detailGroup = ref(null)
const drawerTitle = computed(() => detailItem.value?.title || detailGroup.value?.brand || '商单详情')

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
    const params = { days: days.value }
    if (selectedBrand.value) params.brand = selectedBrand.value
    if (selectedCategory.value) params.category = selectedCategory.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    const res = await api.get('/commercial/groups', { params })
    const data = res.data || {}
    groups.value = data.groups || []
    total.value = data.total || 0
    brandCount.value = data.brand_count || groups.value.length
  } catch (e) {
    console.error(e)
    ElMessage.error('获取潜在商单失败')
  } finally {
    loading.value = false
  }
}

const toggleBrand = (value) => {
  selectedBrand.value = selectedBrand.value === value ? '' : value
  fetchGroups()
}
const toggleCategory = (value) => {
  selectedCategory.value = selectedCategory.value === value ? '' : value
  fetchGroups()
}
const changeDays = (value) => {
  days.value = value
  fetchGroups()
}
const openDetail = (item) => {
  detailGroup.value = null
  detailItem.value = item
  drawerVisible.value = true
}
const openGroup = (group) => {
  detailItem.value = null
  detailGroup.value = group
  drawerVisible.value = true
}
const openOriginal = (url) => {
  if (url) window.open(url, '_blank')
}
const rerunDetection = async (id) => {
  try {
    await api.post(`/commercial/raw-infos/${id}/detect`, null, { params: { force_llm: true } })
    ElMessage.success('已提交 DeepSeek 重检')
  } catch (e) {
    ElMessage.error('提交失败')
  }
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

onMounted(() => {
  fetchFilters()
  fetchGroups()
})
</script>

<style scoped>
.pc-page { max-width: 1240px; margin: 0 auto; }
.pc-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; margin-bottom: 22px; }
.pc-title { margin: 0; color: var(--ink); font-size: 28px; font-weight: 700; }
.pc-subtitle { margin: 6px 0 0; color: var(--ink-4); font-size: 14px; }
.pc-stats { display: flex; gap: 10px; }
.pc-stats div { min-width: 86px; padding: 10px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }
.pc-stats b { display: block; color: var(--clay); font-size: 20px; }
.pc-stats span { color: var(--ink-4); font-size: 12px; }
.pc-filters { padding: 14px 16px; margin-bottom: 20px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }
.pc-filter-line { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 10px; }
.pc-filter-label { width: 34px; color: var(--ink-4); font-size: 12px; font-weight: 700; }
.pc-chip { border: 1px solid var(--line); background: var(--paper-soft, #fff); color: var(--ink-3); border-radius: 999px; padding: 5px 10px; font-size: 12px; cursor: pointer; }
.pc-chip.is-on { border-color: var(--clay); color: var(--clay); background: var(--clay-tint); }
.pc-chip em { margin-left: 5px; font-style: normal; color: var(--ink-4); }
.pc-toolbar { display: flex; justify-content: space-between; gap: 12px; }
.pc-search { flex: 1; min-width: 220px; height: 34px; padding: 0 12px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.pc-days { display: flex; gap: 4px; }
.pc-days button { height: 34px; padding: 0 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; cursor: pointer; }
.pc-days button.on { border-color: var(--clay); color: var(--clay); background: var(--clay-tint); }
.pc-loading, .pc-empty { padding: 54px 20px; text-align: center; color: var(--ink-4); border: 1px dashed var(--line); border-radius: 8px; background: var(--paper); }
.pc-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.brand-card { padding: 16px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }
.brand-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.brand-head h2 { margin: 0; color: var(--ink); font-size: 20px; }
.brand-head p { margin: 4px 0 0; color: var(--ink-4); font-size: 13px; }
.brand-count { align-self: flex-start; border-radius: 999px; background: var(--bone); color: var(--ink-3); padding: 5px 10px; font-size: 12px; }
.brand-count.hot { color: var(--clay); background: var(--clay-tint); }
.brand-meta { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }
.brand-meta div { padding: 9px; border-radius: 8px; background: rgba(0,0,0,.025); min-width: 0; }
.brand-meta span { display: block; margin-bottom: 4px; color: var(--ink-4); font-size: 12px; }
.brand-meta strong { display: block; color: var(--ink-2); font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.detail ul { margin: 0; padding-left: 18px; color: var(--ink-3); font-size: 13px; line-height: 1.7; }
.placements { display: flex; flex-direction: column; gap: 8px; }
.placement { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.placement-main { min-width: 0; flex: 1; cursor: pointer; }
.placement-title { color: var(--ink); font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.placement-sub { display: flex; gap: 10px; margin-top: 5px; color: var(--ink-4); font-size: 12px; }
.placement-insight { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.placement-insight span { max-width: 100%; padding: 3px 7px; border-radius: 999px; background: rgba(80, 52, 31, .05); color: var(--ink-3); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.level { color: #7a5a00; }
.level.likely { color: #b42318; }
.link-btn, .more-btn { border: 1px solid var(--line); border-radius: 8px; background: var(--paper); color: var(--ink-3); cursor: pointer; }
.link-btn { padding: 6px 9px; }
.more-btn { width: 100%; margin-top: 10px; padding: 8px; }
.detail h3 { margin: 0 0 12px; color: var(--ink); line-height: 1.35; }
.detail-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.detail-tags span { border-radius: 999px; padding: 5px 9px; background: var(--clay-tint); color: var(--clay); font-size: 12px; }
.detail dl { margin: 0 0 16px; }
.detail dl div { display: grid; grid-template-columns: 78px 1fr; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.detail dt { color: var(--ink-4); }
.detail dd { margin: 0; color: var(--ink-2); }
.detail h4 { margin: 16px 0 8px; color: var(--ink); }
.detail p { color: var(--ink-3); line-height: 1.7; }
.detail-actions { display: flex; gap: 8px; margin-top: 18px; }
.drawer-list { margin-top: 12px; }
@media (max-width: 900px) {
  .pc-header, .pc-toolbar { flex-direction: column; align-items: stretch; }
  .pc-grid { grid-template-columns: 1fr; }
  .brand-meta { grid-template-columns: 1fr; }
}
</style>
