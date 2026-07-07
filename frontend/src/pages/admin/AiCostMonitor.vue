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
          <svg
            viewBox="0 0 860 300"
            role="img"
            aria-label="AI 调用成本 30 天趋势"
            @mouseleave="trendHover = null"
          >
            <line :x1="chart.left" :y1="chart.top" :x2="chart.left" :y2="chart.bottom" class="axis" />
            <line :x1="chart.left" :y1="chart.bottom" :x2="chart.right" :y2="chart.bottom" class="axis" />
            <g v-for="tick in yTicks" :key="tick.value">
              <line :x1="chart.left" :y1="tick.y" :x2="chart.right" :y2="tick.y" class="grid-line" />
              <text :x="chart.left - 10" :y="tick.y + 4" text-anchor="end" class="axis-label">{{ tick.label }}</text>
            </g>
            <g v-for="tick in xTicks" :key="tick.date">
              <line :x1="tick.x" :y1="chart.bottom" :x2="tick.x" :y2="chart.bottom + 5" class="axis-tick" />
              <text :x="tick.x" :y="chart.bottom + 24" text-anchor="middle" class="axis-label">{{ tick.label }}</text>
            </g>
            <polyline v-if="trendPoints.length" :points="trendPolyline" class="trend-line" />
            <circle v-for="point in trendPoints" :key="point.date" :cx="point.x" :cy="point.y" r="3.5" class="trend-dot">
              <title>{{ point.date }}：{{ formatTrendValue(point.value) }}{{ activeTrend.unit }}</title>
            </circle>
            <g v-if="trendHover" class="hover-layer">
              <line :x1="trendHover.x" :y1="chart.top" :x2="trendHover.x" :y2="chart.bottom" class="hover-line" />
              <line :x1="chart.left" :y1="trendHover.y" :x2="chart.right" :y2="trendHover.y" class="hover-line" />
              <circle :cx="trendHover.x" :cy="trendHover.y" r="5.5" class="hover-dot" />
              <g :transform="tooltipTransform">
                <rect width="154" height="92" rx="8" class="chart-tooltip-box" />
                <text x="12" y="22" class="tooltip-title">{{ trendHover.date }}</text>
                <text x="12" y="43" class="tooltip-line">{{ activeTrend.label }}：{{ formatTrendValue(trendHover.value) }}{{ activeTrend.unit }}</text>
                <text x="12" y="62" class="tooltip-line">Token：{{ formatTrendValue(trendHover.row.total_tokens || 0) }}</text>
                <text x="12" y="81" class="tooltip-line">成本：¥{{ formatMoney(trendHover.row.cost_yuan || 0) }}</text>
              </g>
            </g>
            <rect
              v-for="area in trendHitAreas"
              :key="area.point.date"
              :x="area.x"
              :y="chart.top"
              :width="area.width"
              :height="chart.height"
              class="trend-hit-area"
              @mouseenter="setTrendHover(area.point)"
              @mousemove="setTrendHover(area.point)"
            />
            <text :x="chart.left" y="18" class="axis-label">
              纵轴：{{ activeTrend.label }}，上限 {{ formatTrendValue(maxTrendValue) }}{{ activeTrend.unit }}
            </text>
          </svg>
          <div v-if="!daily.length" class="empty-chart">暂无趋势数据</div>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('operation')">
          <span>按功能统计（30 天）</span>
          <span class="panel-meta">{{ byOperation.length }} 项 · {{ openPanels.operation ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.operation" class="table-scroll compact-scroll">
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
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('model')">
          <span>按模型统计（30 天）</span>
          <span class="panel-meta">{{ byModel.length }} 个模型 · {{ openPanels.model ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.model" class="table-scroll">
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
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-row panel-title-clickable" @click="togglePanel('pricing')">
          <div>
            <div class="panel-title">模型单价配置</div>
            <div class="muted">单位：人民币 / 百万 token。修改后影响新调用，历史成本保留调用时快照。</div>
          </div>
          <span class="panel-meta">{{ pricingDrafts.length }} 条 · {{ openPanels.pricing ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.pricing" class="table-scroll">
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
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('recent')">
          <span>最近调用成本记录</span>
          <span class="panel-meta">{{ recent.length }} 条 · {{ openPanels.recent ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.recent" class="table-scroll">
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
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getAiCosts, updateLlmPricing } from '@/api/admin'

const loading = ref(false)
const savingPricingId = ref(null)
const data = ref({ summary: {}, by_operation: [], by_model: [], daily: [], pricing: [], recent: [] })
const pricingDrafts = ref([])
const trendMode = ref('calls')
const trendHover = ref(null)
const chart = {
  left: 58,
  right: 824,
  top: 32,
  bottom: 222,
  width: 766,
  height: 190,
}
const openPanels = reactive({
  operation: true,
  model: true,
  pricing: false,
  recent: true,
})
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
const maxTrendValue = computed(() => niceCeil(Math.max(1, ...trendValues.value)))
const trendPoints = computed(() => {
  const rows = daily.value
  if (!rows.length) return []
  const gap = rows.length > 1 ? chart.width / (rows.length - 1) : 0
  return rows.map((item, index) => {
    const value = Number(item[trendMode.value] || 0)
    return {
      date: item.date,
      row: item,
      value,
      x: chart.left + gap * index,
      y: chart.top + chart.height - (value / maxTrendValue.value) * chart.height,
    }
  })
})
const trendPolyline = computed(() => trendPoints.value.map(point => `${point.x},${point.y}`).join(' '))
const trendHitAreas = computed(() => {
  const points = trendPoints.value
  return points.map((point, index) => {
    const previous = points[index - 1]
    const next = points[index + 1]
    const left = previous ? (previous.x + point.x) / 2 : chart.left
    const right = next ? (point.x + next.x) / 2 : chart.right
    return { point, x: left, width: Math.max(1, right - left) }
  })
})
const yTicks = computed(() => {
  return [1, 0.75, 0.5, 0.25, 0].map(ratio => {
    const value = maxTrendValue.value * ratio
    return {
      value,
      label: formatAxisValue(value),
      y: chart.top + (1 - ratio) * chart.height,
    }
  })
})
const xTicks = computed(() => {
  const points = trendPoints.value
  if (!points.length) return []
  const indexes = new Set([0, points.length - 1])
  const step = Math.max(1, Math.ceil(points.length / 6))
  for (let index = step; index < points.length - 1; index += step) {
    indexes.add(index)
  }
  return [...indexes].sort((a, b) => a - b).map(index => ({
    date: points[index].date,
    label: points[index].date?.slice(5) || '-',
    x: points[index].x,
  }))
})
const tooltipTransform = computed(() => {
  if (!trendHover.value) return ''
  const x = trendHover.value.x > chart.right - 170 ? trendHover.value.x - 166 : trendHover.value.x + 12
  const y = trendHover.value.y < chart.top + 102 ? trendHover.value.y + 14 : trendHover.value.y - 106
  return `translate(${x}, ${y})`
})

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

function togglePanel(key) {
  openPanels[key] = !openPanels[key]
}

function setTrendHover(point) {
  trendHover.value = point
}

function niceCeil(value) {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const scaled = value / magnitude
  const niceStep = [1, 2, 5, 10].find(step => scaled <= step) || 10
  return niceStep * magnitude
}

function formatAxisValue(value) {
  if (trendMode.value === 'cost_yuan') return `¥${formatMoney(value)}`
  return formatTrendValue(value)
}

function formatTrendValue(value) {
  const number = Number(value || 0)
  if (trendMode.value === 'cost_yuan') return formatMoney(number)
  if (Math.abs(number) >= 1000000) return `${Math.round(number / 10000) / 100}M`
  if (Math.abs(number) >= 1000) return `${Math.round(number / 100) / 10}K`
  return `${Math.round(number * 100) / 100}`
}

function formatMoney(value) {
  return (Math.round(Number(value || 0) * 100) / 100).toFixed(2)
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
.panel-meta { margin-left: auto; color: var(--ink-4); font-size: 12px; font-weight: 600; white-space: nowrap; }
.panel-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.panel-collapsible .panel-row { margin-bottom: 0; }
.panel-row .panel-title { margin-bottom: 4px; }
.metric { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--line); color: var(--ink-3); }
.metric strong { color: var(--ink); font-size: 22px; font-variant-numeric: tabular-nums; }
.muted { font-size: 12px; color: var(--ink-4); }
.segmented { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--ivory); }
.segmented button { min-width: 64px; height: 30px; border: 0; border-radius: 6px; background: transparent; color: var(--ink-3); font-size: 13px; cursor: pointer; }
.segmented button.active { background: var(--paper); color: var(--ink); box-shadow: 0 1px 4px rgba(31, 38, 35, 0.08); font-weight: 700; }
.chart-wrap { position: relative; min-height: 300px; overflow-x: auto; }
.chart-wrap svg { display: block; width: 100%; min-width: 760px; height: 300px; }
.axis { stroke: var(--ink-4); stroke-width: 1; }
.axis-tick { stroke: var(--ink-4); stroke-width: 1; }
.grid-line { stroke: var(--line); stroke-width: 1; }
.trend-line { fill: none; stroke: var(--clay-deep); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
.trend-dot { fill: var(--paper); stroke: var(--clay-deep); stroke-width: 2; }
.trend-dot:hover { fill: var(--clay-deep); }
.axis-label { fill: var(--ink-4); font-size: 12px; }
.hover-layer { pointer-events: none; }
.hover-line { stroke: rgba(176, 91, 63, 0.42); stroke-width: 1; stroke-dasharray: 4 4; pointer-events: none; }
.hover-dot { fill: var(--paper); stroke: var(--clay-deep); stroke-width: 3; pointer-events: none; }
.trend-hit-area { fill: transparent; cursor: crosshair; }
.chart-tooltip-box { fill: var(--paper); stroke: var(--line); filter: drop-shadow(0 8px 18px rgba(31, 38, 35, 0.14)); }
.tooltip-title { fill: var(--ink); font-size: 13px; font-weight: 700; }
.tooltip-line { fill: var(--ink-3); font-size: 12px; }
.empty-chart { position: absolute; inset: 0; display: grid; place-items: center; color: var(--ink-4); font-size: 13px; pointer-events: none; }
.table-scroll { margin-top: 14px; max-height: 420px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--paper); }
.table-scroll.compact-scroll { max-height: 300px; }
.table-scroll .admin-table th { position: sticky; top: 0; z-index: 1; }
.admin-table { width: 100%; min-width: 760px; border-collapse: collapse; }
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
  .panel-row.panel-title-clickable { display: flex; }
  .segmented { margin-top: 12px; }
  .table-scroll { max-height: 360px; }
}
</style>
