<template>
  <div class="monitor-page">
    <div class="monitor-head">
      <div>
        <div class="kicker">后台监测</div>
        <h1>接口健康</h1>
      </div>
      <button class="btn-ghost btn-uniform" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-loading="loading" class="monitor-grid">
      <section class="panel">
        <div class="panel-title">最近 1 小时</div>
        <div class="metric"><span>请求</span><strong>{{ oneHour.requests ?? 0 }}</strong></div>
        <div class="metric"><span>5xx</span><strong>{{ oneHour.errors_5xx ?? 0 }}</strong></div>
        <div class="metric"><span>P95</span><strong>{{ oneHour.p95_ms ?? 0 }}ms</strong></div>
      </section>
      <section class="panel">
        <div class="panel-title">最近 24 小时</div>
        <div class="metric"><span>请求</span><strong>{{ day.requests ?? 0 }}</strong></div>
        <div class="metric"><span>错误率</span><strong>{{ percent(day.error_rate) }}</strong></div>
        <div class="metric"><span>平均耗时</span><strong>{{ day.avg_ms ?? 0 }}ms</strong></div>
      </section>
      <section class="panel">
        <div class="panel-title">说明</div>
        <div class="muted">从后端中间件采集接口状态、耗时和用户 ID。新启用后，数据会随访问逐步积累。</div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('endpoints')">
          <span>接口排行</span>
          <span class="panel-meta">{{ endpoints.length }} 个接口 · {{ openPanels.endpoints ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.endpoints" class="table-scroll">
          <table class="admin-table">
          <thead><tr><th>接口</th><th>请求</th><th>5xx</th><th>4xx</th><th>错误率</th><th>平均</th><th>P95</th><th>最近</th></tr></thead>
          <tbody>
            <tr v-for="item in endpoints" :key="item.endpoint">
              <td><strong>{{ item.endpoint }}</strong></td>
              <td>{{ item.requests }}</td>
              <td>{{ item.errors_5xx }}</td>
              <td>{{ item.errors_4xx }}</td>
              <td>{{ percent(item.error_rate) }}</td>
              <td>{{ item.avg_ms }}ms</td>
              <td>{{ item.p95_ms }}ms</td>
              <td>{{ fmtDate(item.latest_at) }}</td>
            </tr>
            <tr v-if="!endpoints.length"><td colspan="8" class="empty-cell">暂无请求日志</td></tr>
          </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('errors')">
          <span>最近 5xx</span>
          <span class="panel-meta">{{ recentErrors.length }} 条 · {{ openPanels.errors ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.errors" class="table-scroll compact-scroll">
          <table class="admin-table">
          <thead><tr><th>时间</th><th>用户</th><th>接口</th><th>状态码</th><th>耗时</th></tr></thead>
          <tbody>
            <tr v-for="item in recentErrors" :key="item.id">
              <td>{{ fmtDate(item.created_at) }}</td>
              <td>{{ item.user_id || '-' }}</td>
              <td>{{ item.method }} {{ item.path }}</td>
              <td><el-tag type="danger" size="small">{{ item.status_code }}</el-tag></td>
              <td>{{ item.duration_ms }}ms</td>
            </tr>
            <tr v-if="!recentErrors.length"><td colspan="5" class="empty-cell">最近没有 5xx</td></tr>
          </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getApiHealth } from '@/api/admin'

const loading = ref(false)
const data = ref({ summary: {}, endpoints: [], recent_errors: [] })
const openPanels = reactive({
  endpoints: true,
  errors: true,
})
const oneHour = computed(() => data.value.summary?.last_1h || {})
const day = computed(() => data.value.summary?.last_24h || {})
const endpoints = computed(() => data.value.endpoints || [])
const recentErrors = computed(() => data.value.recent_errors || [])

async function load() {
  loading.value = true
  try {
    const resp = await getApiHealth()
    data.value = resp.data || {}
  } finally {
    loading.value = false
  }
}

function percent(value) {
  return `${Math.round((value || 0) * 10000) / 100}%`
}

function togglePanel(key) {
  openPanels[key] = !openPanels[key]
}

function fmtDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16)
}

onMounted(load)
</script>

<style scoped>
.monitor-page { max-width: 1180px; margin: 0 auto; padding: 24px 12px 80px; }
.monitor-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.kicker { color: var(--clay-deep); font-size: 13px; font-weight: 700; }
h1 { margin: 4px 0 0; font-family: var(--serif); font-size: 34px; color: var(--ink); }
.monitor-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.panel { background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); padding: 18px; }
.panel-main { grid-column: 1 / -1; }
.panel-title { margin-bottom: 14px; font-weight: 700; color: var(--ink); }
.panel-collapsible { padding-bottom: 14px; }
.panel-collapsible .panel-title { margin-bottom: 0; }
.panel-title-clickable { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: pointer; }
.panel-title-clickable:hover { color: var(--clay-deep); }
.panel-meta { color: var(--ink-4); font-size: 12px; font-weight: 600; white-space: nowrap; }
.metric { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--line); color: var(--ink-3); }
.metric strong { color: var(--ink); font-size: 22px; font-variant-numeric: tabular-nums; }
.muted { font-size: 13px; color: var(--ink-4); line-height: 1.6; }
.table-scroll { margin-top: 14px; max-height: 420px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--paper); }
.table-scroll.compact-scroll { max-height: 300px; }
.table-scroll .admin-table th { position: sticky; top: 0; z-index: 1; }
.admin-table { width: 100%; min-width: 760px; border-collapse: collapse; }
.admin-table th, .admin-table td { text-align: left; padding: 11px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.admin-table th { font-size: 12px; color: var(--ink-4); font-weight: 700; background: var(--ivory); }
.empty-cell { text-align: center !important; color: var(--ink-4); padding: 24px 10px !important; }
@media (max-width: 900px) {
  .monitor-grid { grid-template-columns: 1fr; }
  .table-scroll { max-height: 360px; }
}
</style>
