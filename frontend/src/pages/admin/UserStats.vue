<template>
  <div class="monitor-page">
    <div class="monitor-head">
      <div>
        <div class="kicker">后台监测</div>
        <h1>用户统计</h1>
      </div>
      <button class="btn-ghost btn-uniform" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-loading="loading" class="monitor-grid">
      <section class="panel" v-for="item in summaryCards" :key="item.label">
        <div class="panel-title">{{ item.label }}</div>
        <div class="big-number">{{ item.value }}</div>
        <div class="muted">{{ item.hint }}</div>
      </section>

      <section class="panel panel-main">
        <div class="panel-row">
          <div>
            <div class="panel-title">30 天趋势</div>
            <div class="muted">用户增长、收入、积分消耗和 AI 成本的日趋势。</div>
          </div>
          <div class="segmented">
            <button v-for="item in trendModes" :key="item.key" :class="{ active: trendMode === item.key }" @click="trendMode = item.key">
              {{ item.label }}
            </button>
          </div>
        </div>
        <div class="chart-wrap">
          <svg
            viewBox="0 0 860 318"
            role="img"
            aria-label="用户统计 30 天趋势"
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
                <rect width="170" height="128" rx="8" class="chart-tooltip-box" />
                <text x="12" y="22" class="tooltip-title">{{ trendHover.date }}</text>
                <text x="12" y="43" class="tooltip-line">{{ activeTrend.label }}：{{ formatTrendValue(trendHover.value) }}{{ activeTrend.unit }}</text>
                <text x="12" y="62" class="tooltip-line">新增用户：{{ trendHover.row.new_users || 0 }} 人</text>
                <text x="12" y="81" class="tooltip-line">收入：¥{{ formatMoney(trendHover.row.revenue_yuan || 0) }}</text>
                <text x="12" y="100" class="tooltip-line">积分消耗：{{ formatNumber(trendHover.row.credits_consumed || 0) }}</text>
                <text x="12" y="119" class="tooltip-line">AI：¥{{ formatMoney(trendHover.row.llm_cost_yuan || 0) }} / {{ trendHover.row.llm_calls || 0 }} 次</text>
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
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('topCost')">
          <span>高成本 / 高消耗用户（30 天）</span>
          <span class="panel-meta">{{ topCostUsers.length }} 人 · {{ openPanels.topCost ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.topCost" class="table-scroll">
          <table class="admin-table">
          <thead><tr><th>用户</th><th>余额</th><th>AI 调用</th><th>Token</th><th>AI 成本</th><th>积分消耗</th><th>充值</th><th>风险</th></tr></thead>
          <tbody>
            <tr v-for="item in topCostUsers" :key="item.id">
              <td>{{ displayUser(item) }}</td>
              <td>{{ item.balance }}</td>
              <td>{{ item.llm_calls_30d }}</td>
              <td>{{ item.llm_tokens_30d }}</td>
              <td>¥{{ item.llm_cost_yuan_30d }}</td>
              <td>{{ item.credits_consumed_30d }}</td>
              <td>¥{{ item.paid_yuan_30d }}</td>
              <td><span v-for="flag in item.risk_flags" :key="flag" class="risk-pill">{{ riskLabel(flag) }}</span></td>
            </tr>
            <tr v-if="!topCostUsers.length"><td colspan="8" class="empty-cell">暂无用户消耗记录</td></tr>
          </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('lowBalance')">
          <span>低余额用户</span>
          <span class="panel-meta">{{ lowBalanceUsers.length }} 人 · {{ openPanels.lowBalance ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.lowBalance" class="table-scroll compact-scroll">
          <table class="admin-table">
          <thead><tr><th>用户</th><th>余额</th><th>累计购买</th><th>累计消耗</th><th>30 天消耗</th><th>最近登录</th></tr></thead>
          <tbody>
            <tr v-for="item in lowBalanceUsers" :key="item.id">
              <td>{{ displayUser(item) }}</td>
              <td>{{ item.balance }}</td>
              <td>{{ item.total_purchased }}</td>
              <td>{{ item.total_consumed }}</td>
              <td>{{ item.credits_consumed_30d }}</td>
              <td>{{ fmtDate(item.last_login) }}</td>
            </tr>
            <tr v-if="!lowBalanceUsers.length"><td colspan="6" class="empty-cell">暂无低余额用户</td></tr>
          </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('payments')">
          <span>最近充值订单</span>
          <span class="panel-meta">{{ recentPayments.length }} 条 · {{ openPanels.payments ? '收起' : '展开' }}</span>
        </div>
        <div v-show="openPanels.payments" class="table-scroll compact-scroll">
          <table class="admin-table">
          <thead><tr><th>时间</th><th>用户</th><th>套餐</th><th>金额</th><th>积分</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="item in recentPayments" :key="item.id">
              <td>{{ fmtDate(item.paid_at || item.created_at) }}</td>
              <td>{{ item.username || item.phone || `#${item.user_id}` }}</td>
              <td>{{ item.package_name }}</td>
              <td>¥{{ item.amount_yuan }}</td>
              <td>{{ item.credits }}</td>
              <td><span :class="['status-pill', item.status]">{{ item.status }}</span></td>
            </tr>
            <tr v-if="!recentPayments.length"><td colspan="6" class="empty-cell">暂无充值订单</td></tr>
          </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getUserStats } from '@/api/admin'

const loading = ref(false)
const data = ref({ summary: {}, daily: [], top_cost_users: [], low_balance_users: [], recent_payments: [] })
const trendMode = ref('revenue_yuan')
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
  topCost: true,
  lowBalance: false,
  payments: false,
})
const trendModes = [
  { key: 'revenue_yuan', label: '收入', unit: ' 元' },
  { key: 'new_users', label: '新增用户', unit: ' 人' },
  { key: 'credits_consumed', label: '积分消耗', unit: '' },
  { key: 'llm_cost_yuan', label: 'AI 成本', unit: ' 元' },
  { key: 'llm_calls', label: 'AI 调用', unit: ' 次' },
]

const summary = computed(() => data.value.summary || {})
const daily = computed(() => data.value.daily || [])
const topCostUsers = computed(() => data.value.top_cost_users || [])
const lowBalanceUsers = computed(() => data.value.low_balance_users || [])
const recentPayments = computed(() => data.value.recent_payments || [])

const summaryCards = computed(() => [
  { label: '总用户', value: summary.value.total_users || 0, hint: `24h 活跃 ${summary.value.active_users_24h || 0}` },
  { label: '7 天新增', value: summary.value.new_users_7d || 0, hint: `付费用户 ${summary.value.paid_users || 0}` },
  { label: '30 天收入', value: `¥${summary.value.revenue_30d || 0}`, hint: `7 天 ¥${summary.value.revenue_7d || 0}` },
  { label: '30 天积分消耗', value: summary.value.credits_consumed_30d || 0, hint: `低余额 ${summary.value.low_balance_users || 0} 人` },
  { label: '30 天 AI 成本', value: `¥${summary.value.llm_cost_yuan_30d || 0}`, hint: `${summary.value.llm_calls_30d || 0} 次调用` },
  { label: '30 天 Token', value: summary.value.llm_tokens_30d || 0, hint: '真实 LLM usage 统计' },
])

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
  const x = trendHover.value.x > chart.right - 188 ? trendHover.value.x - 182 : trendHover.value.x + 12
  const y = trendHover.value.y < chart.top + 138 ? trendHover.value.y + 14 : trendHover.value.y - 142
  return `translate(${x}, ${y})`
})

async function load() {
  loading.value = true
  try {
    const resp = await getUserStats()
    data.value = resp.data || {}
  } finally {
    loading.value = false
  }
}

function displayUser(item) {
  return item.username || item.phone || `#${item.id}`
}

function riskLabel(flag) {
  const map = { low_balance: '低余额', high_cost_no_payment: '高成本未充值' }
  return map[flag] || flag
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
  if (['revenue_yuan', 'llm_cost_yuan'].includes(trendMode.value)) return `¥${formatMoney(value)}`
  return formatTrendValue(value)
}

function formatTrendValue(value) {
  const number = Number(value || 0)
  if (['revenue_yuan', 'llm_cost_yuan'].includes(trendMode.value)) return formatMoney(number)
  return formatNumber(number)
}

function formatNumber(value) {
  const number = Number(value || 0)
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
.panel-title { margin-bottom: 12px; font-weight: 700; color: var(--ink); }
.panel-collapsible { padding-bottom: 14px; }
.panel-collapsible .panel-title { margin-bottom: 0; }
.panel-title-clickable { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: pointer; }
.panel-title-clickable:hover { color: var(--clay-deep); }
.panel-meta { color: var(--ink-4); font-size: 12px; font-weight: 600; white-space: nowrap; }
.panel-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.panel-row .panel-title { margin-bottom: 4px; }
.big-number { color: var(--ink); font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; margin-bottom: 4px; }
.muted { font-size: 12px; color: var(--ink-4); }
.segmented { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--ivory); }
.segmented button { min-width: 76px; height: 30px; border: 0; border-radius: 6px; background: transparent; color: var(--ink-3); font-size: 13px; cursor: pointer; }
.segmented button.active { background: var(--paper); color: var(--ink); box-shadow: 0 1px 4px rgba(31, 38, 35, 0.08); font-weight: 700; }
.chart-wrap { position: relative; min-height: 318px; overflow-x: auto; }
.chart-wrap svg { display: block; width: 100%; min-width: 760px; height: 318px; }
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
.table-scroll { margin-top: 14px; max-height: 420px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--paper); }
.table-scroll.compact-scroll { max-height: 300px; }
.table-scroll .admin-table th { position: sticky; top: 0; z-index: 1; }
.admin-table { width: 100%; min-width: 760px; border-collapse: collapse; }
.admin-table th, .admin-table td { text-align: left; padding: 11px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.admin-table th { font-size: 12px; color: var(--ink-4); font-weight: 700; background: var(--ivory); }
.empty-cell { text-align: center !important; color: var(--ink-4); padding: 24px 10px !important; }
.risk-pill { display: inline-flex; height: 22px; align-items: center; padding: 0 8px; border-radius: 999px; margin-right: 5px; background: rgba(176, 73, 58, 0.12); color: #9b3d31; font-size: 12px; font-weight: 700; }
.status-pill { display: inline-flex; align-items: center; min-width: 58px; height: 24px; border-radius: 999px; padding: 0 8px; justify-content: center; background: var(--ivory); color: var(--ink-3); font-size: 12px; font-weight: 700; }
.status-pill.PAID { background: rgba(67, 132, 91, 0.12); color: #2f6f4a; }
.status-pill.PENDING { background: rgba(180, 132, 62, 0.14); color: #8a5d24; }
@media (max-width: 900px) {
  .monitor-grid { grid-template-columns: 1fr; }
  .panel-row { display: block; }
  .segmented { margin-top: 12px; }
  .table-scroll { max-height: 360px; }
}
</style>
