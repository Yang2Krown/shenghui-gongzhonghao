<template>
  <div class="commercial-page">
    <div class="page-head mb-6">
      <div>
        <h1 class="font-serif page-title">疑似商单</h1>
        <p class="page-subtitle">抓取后自动识别的商业软文线索，按发布时间倒序排列</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadItems">刷新</el-button>
    </div>

    <div class="filter-bar mb-5">
      <div class="filter-row">
        <span class="filter-label">等级：</span>
        <div class="filter-chips">
          <button
            v-for="opt in levelOptions"
            :key="opt.value"
            @click="setLevel(opt.value)"
            :class="['type-chip', filters.level === opt.value && 'type-chip-active']"
          >
            {{ opt.label }}
          </button>
        </div>
        <span class="filter-label-sep">|</span>
        <div class="search-wrap">
          <el-input
            v-model="filters.keyword"
            placeholder="搜索标题、摘要、正文"
            clearable
            class="keyword-input"
            @keyup.enter="reload"
            @clear="reload"
          />
          <button class="btn-search" @click="reload">搜索</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="30"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <div v-else-if="items.length === 0" class="empty-state">
      <div class="empty-icon">
        <el-icon :size="30"><Document /></el-icon>
      </div>
      <h3>暂无疑似商单</h3>
      <p>新抓取内容完成检测后会出现在这里</p>
    </div>

    <div v-else class="commercial-list">
      <a
        v-for="item in items"
        :key="item.id"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer"
        class="commercial-row"
      >
        <div class="row-main">
          <div class="row-meta">
            <span class="source">{{ item.source_name }}</span>
            <span class="dot">·</span>
            <span>{{ formatDate(item.published_at || item.scraped_at) }}</span>
            <span
              class="level-badge"
              :class="item.commercial_level === 'likely' ? 'level-likely' : 'level-suspected'"
            >
              {{ levelText(item.commercial_level) }}
            </span>
          </div>
          <h3 class="font-serif">{{ item.title }}</h3>
          <p v-if="item.summary">{{ item.summary }}</p>
          <div class="reason">
            <span v-if="item.product" class="product">{{ item.product }}</span>
            <span>{{ item.reason || '命中商业推广结构信号' }}</span>
          </div>
        </div>
        <el-button
          size="small"
          @click.prevent="rerunDetect(item)"
          :loading="detectingId === item.id"
        >
          重跑检测
        </el-button>
      </a>
    </div>

    <div v-if="items.length > 0" class="pagination-wrap">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 30, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Loading, Refresh } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'

const loading = ref(false)
const detectingId = ref(null)
const items = ref([])

const filters = reactive({
  level: '',
  keyword: '',
})

const levelOptions = [
  { value: '', label: '全部' },
  { value: 'likely', label: '高可能' },
  { value: 'suspected', label: '疑似' },
]

const pagination = reactive({
  page: 1,
  pageSize: 30,
  total: 0,
})

const loadItems = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    if (filters.level) params.level = filters.level
    if (filters.keyword) params.keyword = filters.keyword
    const res = await get('/commercial/raw-infos', params)
    items.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (error) {
    ElMessage.error('加载疑似商单失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const reload = () => {
  pagination.page = 1
  loadItems()
}

const setLevel = (level) => {
  filters.level = level
  reload()
}

const rerunDetect = async (item) => {
  detectingId.value = item.id
  try {
    await post(`/commercial/raw-infos/${item.id}/detect`)
    ElMessage.success('已提交重跑检测任务')
  } catch (error) {
    ElMessage.error('提交检测失败')
  } finally {
    detectingId.value = null
  }
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadItems()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  loadItems()
}

const levelText = (level) => {
  if (level === 'likely') return '高可能'
  if (level === 'suspected') return '疑似'
  return '无'
}

const formatDate = (dateString) => {
  if (!dateString) return '未知时间'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(loadItems)
</script>

<style scoped>
.commercial-page {
  width: 100%;
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.page-title {
  color: var(--ink);
  font-size: 30px;
  font-weight: 500;
  line-height: 1.2;
}
.page-subtitle {
  margin-top: 6px;
  color: #6B6862;
  font-size: 14px;
}
.filter-bar {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px 20px;
}
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
.search-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.keyword-input {
  width: 360px;
}
.btn-search {
  flex-shrink: 0;
  height: 36px;
  padding: 0 18px;
  border-radius: 10px;
  border: 1px solid var(--clay);
  background: var(--clay);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.btn-search:hover {
  background: var(--clay-deep);
  border-color: var(--clay-deep);
}
.loading-state,
.empty-state {
  min-height: 340px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #9A968D;
}
.empty-state h3 {
  color: var(--ink);
  font-size: 18px;
  font-weight: 600;
  margin-top: 2px;
}
.empty-state p {
  color: #9A968D;
  font-size: 14px;
}
.empty-icon {
  width: 58px;
  height: 58px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: var(--paper);
  color: #9A968D;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 2px rgba(31,31,30,.04);
}
.commercial-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.commercial-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 20px;
  color: inherit;
  text-decoration: none;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.03);
  transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
}
.commercial-row:hover {
  border-color: var(--clay-soft);
  box-shadow: 0 4px 12px rgba(31, 31, 30, .06);
  transform: translateY(-1px);
}
.row-main {
  flex: 1;
  min-width: 0;
}
.row-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: #8A857C;
  font-size: 12px;
}
.source {
  color: var(--ink-3);
  font-weight: 600;
}
.dot {
  color: #C8C2B6;
}
.level-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.level-likely {
  color: #7A3E00;
  background: #FFE3B3;
  border: 1px solid #F1C77F;
}
.level-suspected {
  color: #7A5200;
  background: #FFF0CC;
  border: 1px solid #F0D798;
}
.commercial-row h3 {
  margin-top: 8px;
  color: var(--ink);
  font-size: 20px;
  font-weight: 500;
  line-height: 1.45;
  letter-spacing: 0;
}
.commercial-row p {
  margin-top: 7px;
  color: #6B6862;
  font-size: 15px;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.reason {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  color: #7A5200;
  font-size: 13px;
}
.product {
  color: #7A3E00;
  font-weight: 700;
}
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 22px;
}
@media (max-width: 720px) {
  .page-head,
  .filter-row,
  .search-wrap,
  .commercial-row {
    align-items: stretch;
    flex-direction: column;
  }
  .keyword-input {
    width: 100%;
  }
  .filter-label-sep {
    display: none;
  }
}
</style>
