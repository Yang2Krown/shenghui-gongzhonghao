<template>
  <div class="monitor-page">
    <div class="monitor-head">
      <div>
        <div class="kicker">后台监测</div>
        <h1>数据源健康</h1>
      </div>
      <button class="btn-ghost btn-uniform" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-loading="loading" class="monitor-grid">
      <section class="panel">
        <div class="metric"><span>启用数据源</span><strong>{{ summary.enabled_sources ?? 0 }}</strong></div>
        <div class="metric"><span>总数据源</span><strong>{{ summary.sources_total ?? 0 }}</strong></div>
      </section>
      <section class="panel">
        <div class="metric"><span>24 小时新增</span><strong>{{ summary.raw_infos_24h ?? 0 }}</strong></div>
        <div class="metric"><span>停滞源</span><strong>{{ summary.stale_sources ?? 0 }}</strong></div>
      </section>
      <section class="panel">
        <div class="metric"><span>无入库记录</span><strong>{{ summary.no_data_sources ?? 0 }}</strong></div>
        <div class="muted">按最近 24 小时是否有新内容判断停滞</div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('types')">
          <span>类型分布</span>
          <span class="panel-meta">{{ byType.length }} 类 · {{ openPanels.types ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.types" class="table-scroll compact-scroll">
          <table class="admin-table">
          <thead><tr><th>类型</th><th>数据源</th><th>启用</th><th>24 小时新增</th></tr></thead>
          <tbody>
            <tr v-for="item in byType" :key="item.source_type">
              <td>{{ item.source_type }}</td>
              <td>{{ item.sources }}</td>
              <td>{{ item.enabled }}</td>
              <td>{{ item.raw_infos_24h }}</td>
            </tr>
          </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('sources')">
          <span>数据源列表</span>
          <span class="panel-meta">{{ items.length }} 个源 · {{ openPanels.sources ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.sources" class="table-scroll">
          <table class="admin-table">
          <thead>
            <tr>
              <th>数据源</th>
              <th>类型</th>
              <th>状态</th>
              <th>24 小时新增</th>
              <th>总入库</th>
              <th>最近入库</th>
              <th>上次抓取</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td><strong>{{ item.name }}</strong><div class="muted">{{ item.platform }}</div></td>
              <td>{{ item.source_type }}</td>
              <td>
                <el-tag :type="!item.enabled ? 'info' : item.level === 'ok' ? 'success' : 'warning'" size="small">
                  {{ !item.enabled ? '停用' : item.level === 'ok' ? '正常' : '停滞' }}
                </el-tag>
              </td>
              <td>{{ item.raw_infos_24h }}</td>
              <td>{{ item.total_raw_infos }}</td>
              <td>{{ fmtDate(item.latest_raw_at) }}</td>
              <td>{{ fmtDate(item.last_fetched_at) }}</td>
            </tr>
          </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getSourceHealth } from '@/api/admin'
import { formatDateTimeMinute } from '@/utils/dateTime'

const loading = ref(false)
const data = ref({ summary: {}, by_type: [], items: [] })
const openPanels = reactive({
  types: false,
  sources: true,
})
const summary = computed(() => data.value.summary || {})
const byType = computed(() => data.value.by_type || [])
const items = computed(() => data.value.items || [])

async function load() {
  loading.value = true
  try {
    const resp = await getSourceHealth()
    data.value = resp.data || {}
  } finally {
    loading.value = false
  }
}

function fmtDate(value) {
  if (!value) return '-'
  return formatDateTimeMinute(value, '-')
}

function togglePanel(key) {
  openPanels[key] = !openPanels[key]
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
.metric strong { color: var(--ink); font-size: 24px; font-variant-numeric: tabular-nums; }
.muted { font-size: 12px; color: var(--ink-4); }
.table-scroll { margin-top: 14px; max-height: 420px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--paper); }
.table-scroll.compact-scroll { max-height: 260px; }
.table-scroll .admin-table th { position: sticky; top: 0; z-index: 1; }
.admin-table { width: 100%; min-width: 760px; border-collapse: collapse; }
.admin-table th, .admin-table td { text-align: left; padding: 11px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.admin-table th { font-size: 12px; color: var(--ink-4); font-weight: 700; background: var(--ivory); }
@media (max-width: 900px) {
  .monitor-grid { grid-template-columns: 1fr; }
  .table-scroll { max-height: 360px; }
}
</style>
