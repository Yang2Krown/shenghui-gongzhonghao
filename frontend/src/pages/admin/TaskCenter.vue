<template>
  <div class="task-center-page">
    <div class="page-head">
      <div>
        <div class="kicker">后台管理 · Celery</div>
        <h1>任务中心</h1>
        <p>监控抓取、AI 处理和发布任务的队列状态与失败重试。</p>
      </div>
      <div class="head-actions">
        <span class="refresh-note">{{ loading ? '刷新中…' : `页面可见时每 15 秒刷新 · ${lastUpdated}` }}</span>
        <button class="btn-ghost btn-sm" type="button" @click="loadAll">立即刷新</button>
      </div>
    </div>

    <div class="metric-grid">
      <div v-for="item in metricCards" :key="item.key" class="metric-card" :class="item.tone">
        <span>{{ item.label }}</span>
        <strong>{{ overview.counts?.[item.key] || 0 }}</strong>
        <small>最近 24 小时</small>
      </div>
    </div>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>队列概览</h2>
          <span class="muted">在线 Worker：{{ overview.workers?.length || 0 }}</span>
        </div>
        <span v-if="overview.inspect_error" class="warning-text">队列实时状态暂不可用</span>
      </div>
      <div class="table-scroll">
        <table class="admin-table">
          <thead>
            <tr><th>队列</th><th>执行中</th><th>等待中</th><th>定时任务</th><th>Worker</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="queue in overview.queues || []" :key="queue.queue">
              <td><strong>{{ queueLabel(queue.queue) }}</strong><div class="muted">{{ queue.queue }}</div></td>
              <td>{{ queue.active }}</td>
              <td>{{ queue.waiting }}</td>
              <td>{{ queue.scheduled }}</td>
              <td>{{ queue.workers || 0 }}</td>
              <td><span class="status-dot" :class="queue.active || queue.waiting ? 'busy' : 'ok'" />{{ queue.active || queue.waiting ? '处理中' : '空闲' }}</td>
            </tr>
            <tr v-if="!(overview.queues || []).length"><td colspan="6" class="empty-cell">暂无队列数据</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>任务记录</h2>
          <span class="muted">包含最近任务、重试任务和死信任务</span>
        </div>
        <div class="filters">
          <select v-model="filters.status" @change="loadTasks">
            <option value="all">全部状态</option>
            <option value="waiting">等待中</option>
            <option value="running">执行中</option>
            <option value="retrying">重试中</option>
            <option value="success">成功</option>
            <option value="dead_letter">死信</option>
          </select>
          <select v-model="filters.category" @change="loadTasks">
            <option value="">全部类型</option>
            <option value="scraping">抓取</option>
            <option value="ai">AI</option>
            <option value="publish">发布</option>
            <option value="default">系统</option>
          </select>
        </div>
      </div>
      <div class="table-scroll task-table-scroll">
        <table class="admin-table task-table">
          <thead>
            <tr><th>任务</th><th>类型 / 队列</th><th>状态</th><th>重试</th><th>创建时间</th><th>失败原因</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id">
              <td><strong>{{ task.task_name }}</strong><div class="muted task-id">{{ task.task_id }}</div></td>
              <td>{{ categoryLabel(task.category) }}<div class="muted">{{ task.queue }}</div></td>
              <td><el-tag size="small" :type="statusType(task.status)">{{ statusLabel(task.status) }}</el-tag></td>
              <td>{{ task.retry_count || 0 }}</td>
              <td>{{ fmtDate(task.created_at) }}</td>
              <td class="error-cell" :title="task.error_message || ''">{{ task.error_message || '—' }}</td>
              <td><button v-if="canRetry(task)" class="btn-ghost btn-sm" type="button" @click="retry(task)" :disabled="retryingId === task.id">{{ retryingId === task.id ? '投递中…' : '重试' }}</button></td>
            </tr>
            <tr v-if="!tasks.length"><td colspan="7" class="empty-cell">暂无任务记录</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getTaskCenterOverview, getTaskCenterTasks, retryTaskCenter } from '@/api/admin'

const overview = ref({ counts: {}, queues: [], workers: [] })
const tasks = ref([])
const loading = ref(false)
const retryingId = ref(null)
const lastUpdated = ref('—')
const filters = reactive({ status: 'all', category: '' })
const REFRESH_INTERVAL_MS = 15000
let refreshTimer = null

const metricCards = [
  { key: 'waiting', label: '等待中', tone: 'tone-blue' },
  { key: 'running', label: '执行中', tone: 'tone-orange' },
  { key: 'retrying', label: '重试中', tone: 'tone-purple' },
  { key: 'success', label: '成功', tone: 'tone-green' },
  { key: 'dead_letter', label: '死信', tone: 'tone-red' },
]

const loadOverview = async () => {
  const resp = await getTaskCenterOverview()
  overview.value = resp.data || {}
}

const loadTasks = async () => {
  const resp = await getTaskCenterTasks({
    status: filters.status,
    category: filters.category || undefined,
    limit: 100,
  })
  tasks.value = resp.data?.items || []
}

const loadAll = async () => {
  if (loading.value) return
  loading.value = true
  try {
    await Promise.all([loadOverview(), loadTasks()])
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (e) {
    console.error('加载任务中心失败:', e)
  } finally {
    loading.value = false
  }
}

const retry = async (task) => {
  retryingId.value = task.id
  try {
    await retryTaskCenter(task.id)
    ElMessage.success('任务已重新投递')
    await loadAll()
  } finally {
    retryingId.value = null
  }
}

const canRetry = (task) => task.status === 'dead_letter' || task.status === 'failed' || task.is_dead_letter
const statusLabel = (value) => ({ waiting: '等待中', running: '执行中', retrying: '重试中', success: '成功', failed: '失败', dead_letter: '死信' }[value] || value || '未知')
const statusType = (value) => ({ waiting: 'info', running: 'warning', retrying: 'warning', success: 'success', failed: 'danger', dead_letter: 'danger' }[value] || 'info')
const categoryLabel = (value) => ({ scraping: '抓取', ai: 'AI', publish: '发布', default: '系统' }[value] || value || '系统')
const queueLabel = (value) => ({ scraping: '抓取队列', ai: 'AI 队列', publish: '发布队列', default: '系统队列' }[value] || value)
const fmtDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16) : '—'

const startRefresh = () => {
  if (!refreshTimer && !document.hidden) {
    refreshTimer = window.setInterval(loadAll, REFRESH_INTERVAL_MS)
  }
}

const stopRefresh = () => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

const handleVisibilityChange = () => {
  if (document.hidden) {
    stopRefresh()
    return
  }

  loadAll()
  startRefresh()
}

onMounted(() => {
  loadAll()
  document.addEventListener('visibilitychange', handleVisibilityChange)
  startRefresh()
})

onUnmounted(() => {
  stopRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.task-center-page { max-width: 1280px; margin: 0 auto; padding: 24px 12px 80px; }
.page-head, .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-head { margin-bottom: 20px; }
.kicker { color: var(--clay-deep); font-size: 13px; font-weight: 700; }
h1 { margin: 4px 0; font-family: var(--serif); font-size: 34px; color: var(--ink); }
h2 { margin: 0; font-size: 18px; color: var(--ink); }
.page-head p, .muted, .refresh-note { color: var(--ink-4); font-size: 12px; }
.head-actions, .filters { display: flex; align-items: center; gap: 10px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric-card { padding: 16px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--paper); }
.metric-card span, .metric-card small { display: block; color: var(--ink-3); font-size: 13px; }
.metric-card strong { display: block; margin: 8px 0 2px; color: var(--ink); font-size: 30px; font-variant-numeric: tabular-nums; }
.metric-card small { color: var(--ink-4); font-size: 11px; }
.tone-blue { border-top: 3px solid #4784b8; }.tone-orange { border-top: 3px solid #c77a34; }.tone-purple { border-top: 3px solid #8065a9; }.tone-green { border-top: 3px solid #4d9670; }.tone-red { border-top: 3px solid #b9554e; }
.panel { padding: 18px; margin-bottom: 16px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--paper); }
.panel-head { margin-bottom: 14px; }
.warning-text { color: var(--crimson); font-size: 12px; }
.table-scroll { max-height: 380px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); }
.task-table-scroll { max-height: 560px; }
.admin-table { width: 100%; min-width: 900px; border-collapse: collapse; }
.admin-table th, .admin-table td { padding: 11px 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }
.admin-table th { position: sticky; top: 0; z-index: 1; color: var(--ink-4); background: var(--ivory); font-size: 12px; }
.task-table td { max-width: 300px; }
.task-id { max-width: 210px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.error-cell { max-width: 300px; overflow: hidden; color: var(--crimson); text-overflow: ellipsis; white-space: nowrap; }
.status-dot { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: #6aa27c; }.status-dot.busy { background: #c77a34; }
.empty-cell { padding: 26px !important; color: var(--ink-4); text-align: center !important; }
select { min-width: 110px; padding: 7px 10px; border: 1px solid var(--line); border-radius: 6px; color: var(--ink); background: var(--paper); }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.page-head, .panel-head { align-items: flex-start; flex-direction: column; }.head-actions, .filters { flex-wrap: wrap; } }
</style>
