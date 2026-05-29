<template>
  <div class="history-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">创作历史</h1>
        <p class="page-desc">你的所有生成记录，可随时查看与复用</p>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <button v-for="t in tabs" :key="t" @click="tab = t"
        :class="['chip', tab === t && 'chip-active']">{{ t }}</button>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="loading-state">
      <svg class="spin" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5"/></svg>
      <p class="loading-text">加载中...</p>
    </div>

    <!-- 列表 -->
    <div v-else class="history-list">
      <div v-for="(h, i) in filteredList" :key="h.id || i" class="card history-card animate-slide-up"
        :style="{ animationDelay: `${i * 40}ms` }">
        <div class="card-icon" :style="{ background: iconBg(h.type) }">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <path v-if="h.type?.includes('角度')" d="M12 3l1.8 4.8L18.5 9 13.8 10.8 12 15.5 10.2 10.8 5.5 9l4.7-1.2L12 3z"/>
            <path v-else-if="h.type?.includes('大纲')" d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>
            <path v-else-if="h.type?.includes('正文')" d="M4 5h16M4 9h16M4 13h11M4 17h7"/>
            <path v-else-if="h.type?.includes('标题')" d="M5 5h14M9 5v14M15 5v6M13 11h4"/>
            <path v-else d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/>
          </svg>
        </div>
        <div class="card-info">
          <div class="card-meta">
            <span class="card-type">{{ h.type || '生成记录' }}</span>
            <span class="card-time">· {{ formatTime(h.created_at || h.time) }}</span>
            <span v-if="h.word_count" class="card-words">· {{ h.word_count }} 字</span>
          </div>
          <h4 class="card-title">{{ h.title || h.display_title || '未命名' }}</h4>
        </div>
        <span class="badge badge-leaf" style="flex-shrink: 0;">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
          {{ h.status || '已完成' }}
        </span>
        <button class="btn btn-ghost btn-sm" style="flex-shrink: 0;" @click="continueCreation(h)">查看</button>
      </div>

      <div v-if="filteredList.length === 0" class="empty-state">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--line)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
        <h3 class="empty-title">暂无记录</h3>
        <p class="empty-desc">使用创作工具后，记录会出现在这里</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api/api'

const router = useRouter()
const loading = ref(true)
const tab = ref('全部')
const records = ref([])

const tabs = ['全部', '创作工具', '内容仿写']
const createTools = ['创作角度', '大纲生成', '正文生成', '标题生成']

const filteredList = computed(() => {
  if (tab.value === '全部') return records.value
  if (tab.value === '创作工具') return records.value.filter(r => createTools.includes(r.type))
  return records.value.filter(r => !createTools.includes(r.type))
})

const formatTime = (dt) => {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  const diff = now - d
  if (diff < 86400000) return '今天'
  if (diff < 172800000) return '昨天'
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

const iconBg = (type) => {
  if (type?.includes('角度')) return 'var(--clay-tint)'
  if (type?.includes('大纲')) return 'var(--pine-soft)'
  if (type?.includes('正文')) return 'var(--sand-soft)'
  if (type?.includes('标题')) return 'var(--clay-tint)'
  return 'var(--bone)'
}

const continueCreation = (h) => {
  if (h.record_id) {
    router.push({ path: '/title', query: { record_id: h.record_id } })
  }
}

onMounted(async () => {
  try {
    const res = await get('/generation-records', { page: 1, page_size: 50 })
    records.value = res.data?.items || res.data || []
  } catch (e) {
    records.value = []
  }
  loading.value = false
})
</script>

<style scoped>
.history-page { max-width: 880px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 30px; line-height: 1.2; font-weight: 500; font-family: var(--serif); color: var(--ink); margin: 0; }
.page-desc { font-size: 14px; color: var(--ink-3); margin-top: 6px; }

.filter-bar { display: flex; gap: 8px; margin-bottom: 20px; }

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  border-radius: var(--r-pill);
  padding: 6px 13px;
  font-size: 13px;
  font-weight: 500;
  background: var(--paper);
  color: var(--ink-2);
  border: 1px solid var(--line);
  transition: all 0.15s;
}

.chip:hover { border-color: var(--clay-soft); color: var(--ink); }
.chip-active { background: var(--ink); color: var(--paper); border-color: var(--ink); }

.history-list { display: flex; flex-direction: column; gap: 10px; }

.history-card {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1) both;
}

.card-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--clay-deep);
}

.card-info { flex: 1; min-width: 0; }

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.card-type { font-size: 12px; color: var(--clay-deep); font-weight: 600; }
.card-time { font-size: 12px; color: var(--ink-4); }
.card-words { font-size: 12px; color: var(--ink-4); }

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: 0;
}

.loading-state { text-align: center; padding: 56px 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font-size: 14px; color: var(--ink-3); margin-top: 14px; }

.empty-state { text-align: center; padding: 70px 20px; }
.empty-title { font-size: 18px; font-weight: 600; color: var(--ink-2); margin-top: 16px; }
.empty-desc { font-size: 14px; color: var(--ink-3); margin-top: 6px; }

.animate-slide-up { animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1) both; }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
