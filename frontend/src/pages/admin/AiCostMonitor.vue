<template>
  <div class="monitor-page">
    <div class="monitor-head">
      <div>
        <div class="kicker">后台监测</div>
        <h1>AI 调用成本</h1>
      </div>
      <button class="btn-ghost btn-uniform" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-loading="loading" class="monitor-grid">
      <section class="panel" v-for="item in summaryCards" :key="item.key">
        <div class="panel-title">{{ item.label }}</div>
        <div class="metric"><span>成本</span><strong>¥{{ item.data.cost_yuan ?? 0 }}</strong></div>
        <div class="metric"><span>调用</span><strong>{{ item.data.calls ?? 0 }}</strong></div>
        <div class="metric"><span>Token</span><strong>{{ item.data.total_tokens ?? 0 }}</strong></div>
        <div class="muted">失败 {{ item.data.failures ?? 0 }} 次 · 平均 {{ item.data.avg_duration_ms ?? 0 }}ms</div>
      </section>

      <section class="panel panel-main">
        <div class="panel-row">
          <div>
            <div class="panel-title">30 天趋势</div>
            <div class="muted">基于真实 LLM 调用日志；成本按调用时的模型单价快照计算。</div>
          </div>
          <div class="segmented">
            <button
              v-for="item in trendModes"
              :key="item.key"
              :class="{ active: trendMode === item.key }"
              @click="trendMode = item.key"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
        <div class="chart-wrap">
          <svg viewBox="0 0 860 260" role="img" aria-label="AI 调用成本 30 天趋势">
            <line x1="44" y1="30" x2="44" y2="214" class="axis" />
            <line x1="44" y1="214" x2="824" y2="214" class="axis" />
            <line v-for="tick in yTicks" :key="tick.y" x1="44" :y1="tick.y" x2="824" :y2="tick.y" class="grid-line" />
            <polyline v-if="trendPoints.length" :points="trendPolyline" class="trend-line" />
            <circle v-for="point in trendPoints" :key="point.date" :cx="point.x" :cy="point.y" r="3.5" class="trend-dot">
              <title>{{ point.date }}：{{ point.value }}{{ activeTrend.unit }}</title>
            </circle>
            <text x="44" y="238" class="axis-label">{{ firstTrendDate }}</text>
            <text x="824" y="238" text-anchor="end" class="axis-label">{{ lastTrendDate }}</text>
            <text x="44" y="22" class="axis-label">max {{ maxTrendValue }}{{ activeTrend.unit }}</text>
          </svg>
          <div v-if="!daily.length" class="empty-chart">暂无趋势数据</div>
        </div>
      </section>

      <section class="panel panel-main">
        <div class="panel-title">按功能统计（30 天）</div>
        <table class="admin-table">
          <thead><tr><th>功能</th><th>调用</th><th>Token</th><th>成本</th><th>失败率</th></tr></thead>
          <tbody>
            <tr v-for="item in byOperation" :key="item.operation">
              <td>{{ operationLabel(item.operation) }}</td>
              <td>{{ item.calls }}</td>
              <td>{{ item.total_tokens || 0 }}</td>
              <td>¥{{ item.cost_yuan }}</td>
              <td>{{ pct(item.failure_rate) }}</td>
            </tr>
            <tr v-if="!byOperation.length"><td colspan="5" class="empty-cell">暂无已记录 AI 成本</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel panel-main">
        <div class="panel-title">按模型统计（30 天）</div>
        <table class="admin-table">
          <thead><tr><th>Provider</th><th>模型</th><th>调用</th><th>Token</th><th>成本</th><th>失败率</th><th>平均耗时</th></tr></thead>
          <tbody>
            <tr v-for="item in byModel" :key="`${item.provider}:${item.model}`">
              <td>{{ item.provider }}</td>
              <td>{{ item.model }}</td>
              <td>{{ item.calls }}</td>
              <td>{{ item.total_tokens || 0 }}</td>
              <td>¥{{ item.cost_yuan }}</td>
              <td>{{ pct(item.failure_rate) }}</td>
              <td>{{ item.avg_duration_ms || 0 }}ms</td>
            </tr>
            <tr v-if="!byModel.length"><td colspan="7" class="empty-cell">暂无模型调用记录</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel panel-main">
        <div class="panel-row">
          <div>
            <div class="panel-title">模型单价配置</div>
            <div class="muted">单位：人民币 / 百万 token。修改后影响新调用，历史成本保留调用时快照。</div>
          </div>
        </div>
        <table class="admin-table">
          <thead><tr><th>Provider</th><th>模型</th><th>显示名</th><th>输入价</th><th>输出价</th><th>启用</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in pricingDrafts" :key="item.id">
              <td>{{ item.provider }}</td>
              <td>{{ item.model }}</td>
              <td><input v-model="item.display_name" class="table-input" /></td>
              <td><input v-model.number="item.input_price_per_million" type="number" min="0" step="0.000001" class="table-input short" /></td>
              <td><input v-model.number="item.output_price_per_million" type="number" min="0" step="0.000001" class="table-input short" /></td>
              <td><input v-model="item.enabled" type="checkbox" /></td>
              <td><button class="mini-btn" @click="savePricing(item)" :disabled="savingPricingId === item.id">保存</button></td>
            </tr>
            <tr v-if="!pricingDrafts.length"><td colspan="7" class="empty-cell">暂无模型单价配置</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel panel-main">
        <div class="panel-title">最近调用成本记录</div>
        <table class="admin-table">
          <thead><tr><th>时间</th><th>状态</th><th>模型</th><th>功能</th><th>Token</th><th>成本</th><th>耗时</th></tr></thead>
          <tbody>
            <tr v-for="item in recent" :key="item.id">
              <td>{{ fmtDate(item.created_at) }}</td>
              <td><span :class="['status-pill', item.status]">{{ item.status }}</span></td>
              <td>{{ item.provider }}/{{ item.model }}</td>
              <td>{{ operationLabel(item.operation) }}</td>
              <td>{{ item.token_usage.total_tokens || 0 }}</td>
              <td>¥{{ item.cost_yuan || 0 }}</td>
              <td>{{ item.duration_ms || 0 }}ms</td>
            </tr>
            <tr v-if="!recent.length"><td colspan="7" class="empty-cell">暂无记录</td></tr>
          </tbody>
        </table>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getAiCosts, updateLlmPricing } from '@/api/admin'

const loading = ref(false)
const savingPricingId = ref(null)
const data = ref({ summary: {}, by_operation: [], by_model: [], daily: [], pricing: [], recent: [] })
const pricingDrafts = ref([])
const trendMode = ref('calls')
const trendModes = [
  { key: 'calls', label: '调用', unit: ' 次' },
  { key: 'total_tokens', label: 'Token', unit: '' },
  { key: 'cost_yuan', label: '成本', unit: ' 元' },
]
const summary = computed(() => data.value.summary || {})
const summaryCards = computed(() => [
  { key: 'today', label: '最近 24 小时', data: summary.value.today || {} },
  { key: 'last_7d', label: '最近 7 天', data: summary.value.last_7d || {} },
  { key: 'last_30d', label: '最近 30 天', data: summary.value.last_30d || {} },
])
const byOperation = computed(() => data.value.by_operation || [])
const byModel = computed(() => data.value.by_model || [])
const daily = computed(() => data.value.daily || [])
const recent = computed(() => data.value.recent || [])
const activeTrend = computed(() => trendModes.find(item => item.key === trendMode.value) || trendModes[0])
const trendValues = computed(() => daily.value.map(item => Number(item[trendMode.value] || 0)))
const maxTrendValue = computed(() => Math.max(1, ...trendValues.value))
const trendPoints = computed(() => {
  const rows = daily.value
  if (!rows.length) return []
  const left = 44
  const top = 30
  const width = 780
  const height = 184
  const gap = rows.length > 1 ? width / (rows.length - 1) : 0
  return rows.map((item, index) => {
    const value = Number(item[trendMode.value] || 0)
    return {
      date: item.date,
      value,
      x: left + gap * index,
      y: top + height - (value / maxTrendValue.value) * height,
    }
  })
})
const trendPolyline = computed(() => trendPoints.value.map(point => `${point.x},${point.y}`).join(' '))
const yTicks = computed(() => [30, 76, 122, 168, 214].map(y => ({ y })))
const firstTrendDate = computed(() => daily.value[0]?.date?.slice(5) || '-')
const lastTrendDate = computed(() => daily.value[daily.value.length - 1]?.date?.slice(5) || '-')

async function load() {
  loading.value = true
  try {
    const resp = await getAiCosts()
    data.value = resp.data || {}
    pricingDrafts.value = (data.value.pricing || []).map(item => ({ ...item }))
  } finally {
    loading.value = false
  }
}

watch(() => data.value.pricing, (rows) => {
  pricingDrafts.value = (rows || []).map(item => ({ ...item }))
})

async function savePricing(item) {
  savingPricingId.value = item.id
  try {
    await updateLlmPricing(item.id, {
      display_name: item.display_name,
      input_price_per_million: Number(item.input_price_per_million || 0),
      output_price_per_million: Number(item.output_price_per_million || 0),
      currency: item.currency || 'CNY',
      enabled: Boolean(item.enabled),
      note: item.note,
    })
    ElMessage.success('模型单价已保存')
    await load()
  } finally {
    savingPricingId.value = null
  }
}

function operationLabel(value) {
  const map = {
    title_generation: '标题生成',
    content_generation: '正文生成',
    outline_generation: '大纲生成',
    content_polish: '文案润色',
    content_continuation: '正文续写',
    topic_mining: '选题挖掘',
    preprocess: '预处理',
    commercial_detection: '商单检测',
    feishu_brief: '飞书 Brief',
  }
  return map[value] || value || 'unknown'
}

function pct(value) {
  return `${Math.round(Number(value || 0) * 10000) / 100}%`
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
.panel-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.panel-row .panel-title { margin-bottom: 4px; }
.metric { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--line); color: var(--ink-3); }
.metric strong { color: var(--ink); font-size: 22px; font-variant-numeric: tabular-nums; }
.muted { font-size: 12px; color: var(--ink-4); }
.segmented { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--ivory); }
.segmented button { min-width: 64px; height: 30px; border: 0; border-radius: 6px; background: transparent; color: var(--ink-3); font-size: 13px; cursor: pointer; }
.segmented button.active { background: var(--paper); color: var(--ink); box-shadow: 0 1px 4px rgba(31, 38, 35, 0.08); font-weight: 700; }
.chart-wrap { position: relative; min-height: 260px; overflow-x: auto; }
.chart-wrap svg { display: block; width: 100%; min-width: 720px; height: 260px; }
.axis { stroke: var(--ink-4); stroke-width: 1; }
.grid-line { stroke: var(--line); stroke-width: 1; }
.trend-line { fill: none; stroke: var(--clay-deep); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
.trend-dot { fill: var(--paper); stroke: var(--clay-deep); stroke-width: 2; }
.axis-label { fill: var(--ink-4); font-size: 12px; }
.empty-chart { position: absolute; inset: 0; display: grid; place-items: center; color: var(--ink-4); font-size: 13px; pointer-events: none; }
.admin-table { width: 100%; border-collapse: collapse; }
.admin-table th, .admin-table td { text-align: left; padding: 11px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.admin-table th { font-size: 12px; color: var(--ink-4); font-weight: 700; background: var(--ivory); }
.table-input { width: 100%; height: 32px; border: 1px solid var(--line); border-radius: 6px; background: var(--paper); color: var(--ink); padding: 0 9px; font-size: 13px; box-sizing: border-box; }
.table-input.short { max-width: 120px; }
.mini-btn { height: 30px; padding: 0 12px; border: 1px solid var(--line); border-radius: 6px; background: var(--ivory); color: var(--ink); cursor: pointer; font-size: 13px; }
.mini-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.status-pill { display: inline-flex; align-items: center; min-width: 58px; height: 24px; border-radius: 999px; padding: 0 8px; justify-content: center; background: var(--ivory); color: var(--ink-3); font-size: 12px; font-weight: 700; }
.status-pill.success { background: rgba(67, 132, 91, 0.12); color: #2f6f4a; }
.status-pill.failed { background: rgba(176, 73, 58, 0.12); color: #9b3d31; }
.empty-cell { text-align: center !important; color: var(--ink-4); padding: 24px 10px !important; }
@media (max-width: 900px) {
  .monitor-grid { grid-template-columns: 1fr; }
  .panel-row { display: block; }
  .segmented { margin-top: 12px; }
}
</style>
