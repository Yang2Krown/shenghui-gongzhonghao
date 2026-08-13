<template>
  <div class="monitor-page">
    <div class="monitor-head">
      <div>
        <div class="kicker">后台监测</div>
        <h1>安全健康</h1>
      </div>
      <button class="btn-ghost btn-uniform" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-loading="loading" class="monitor-grid">
      <section class="panel panel-main hero-panel">
        <div>
          <div class="panel-title">P2 安全基线</div>
          <div class="hero-status">
            <span :class="['status-dot', displayedOverall.level]"></span>
            <strong>{{ displayedOverall.message || '加载中' }}</strong>
          </div>
          <div class="muted">当前环境：{{ data.environment || '-' }}。这里展示运行时、部署边界、密钥治理和持续安全项。</div>
          <div v-if="handledCount" class="muted">已处理并收起 {{ handledCount }} 项；风险内容变化后会自动重新显示。</div>
        </div>
        <div>
          <div class="hero-actions">
            <button class="btn-ghost btn-sm" type="button" @click="showHandled = !showHandled">
              {{ showHandled ? '隐藏已处理' : `显示已处理${handledCount ? ` (${handledCount})` : ''}` }}
            </button>
            <button v-if="handledCount" class="btn-ghost btn-sm" type="button" @click="clearHandled">清空处理状态</button>
          </div>
          <div class="count-grid">
            <div class="count-card ok"><span>正常</span><strong>{{ displayedCounts.ok || 0 }}</strong></div>
            <div class="count-card warn"><span>待关注</span><strong>{{ displayedCounts.warn || 0 }}</strong></div>
            <div class="count-card critical"><span>高风险</span><strong>{{ displayedCounts.critical || 0 }}</strong></div>
          </div>
        </div>
      </section>

      <section v-for="group in displayGroups" :key="group.key" class="panel panel-main">
        <div class="panel-title">
          <span>{{ group.title }}</span>
          <span v-if="group.hiddenCount && !showHandled" class="panel-meta">{{ group.hiddenCount }} 项已处理并收起</span>
        </div>
        <div class="health-grid">
          <div v-for="item in group.items" :key="item.title" :class="['health-card', item.level]">
            <div class="health-top">
              <div>
                <strong>{{ item.title }}</strong>
                <div class="health-value">{{ item.value || '—' }}</div>
              </div>
              <el-tag :type="tagType(item.level)" size="small">{{ levelLabel(item.level) }}</el-tag>
            </div>
            <div class="health-message">{{ item.message }}</div>
            <ul v-if="item.actions?.length" class="action-list">
              <li v-for="action in item.actions" :key="action">{{ action }}</li>
            </ul>
            <div v-if="item.level !== 'ok'" class="card-actions">
              <button v-if="!item.handled" class="btn-ghost btn-sm" type="button" @click="markHealthHandled(item)">标记已处理</button>
              <button v-else class="btn-ghost btn-sm" type="button" @click="restoreHandled(item.key)">重新显示</button>
              <span v-if="item.handledAt" class="muted">处理于 {{ fmtDate(item.handledAt) }}</span>
            </div>
          </div>
          <div v-if="!group.items.length" class="quiet-card">这个分组当前没有未处理的安全项。</div>
        </div>
      </section>

      <section class="panel panel-main">
        <div class="panel-title">LLM 成本防护 / 熔断</div>
        <div class="guard-summary">
          <div :class="['guard-card', costGuard.overall?.blocked ? 'critical' : 'ok']">
            <span>24 小时成本</span>
            <strong>¥{{ costGuard.overall?.cost_yuan_24h || 0 }}</strong>
            <div class="muted">全局预算 ¥{{ costGuard.overall?.daily_budget_yuan || 0 }}</div>
          </div>
          <div class="guard-card">
            <span>Provider 预算</span>
            <strong>¥{{ costGuard.overall?.provider_daily_budget_yuan || 0 }}</strong>
            <div class="muted">单 provider / 24h</div>
          </div>
          <div class="guard-card">
            <span>熔断窗口</span>
            <strong>{{ costGuard.breaker?.window_minutes || 0 }} 分钟</strong>
            <div class="muted">失败率阈值 {{ pct(costGuard.breaker?.failure_rate) }}</div>
          </div>
          <div :class="['guard-card', visibleHighCostUsers.length ? 'critical' : 'ok']">
            <span>用户成本预警</span>
            <strong>{{ visibleHighCostUsers.length }}</strong>
            <div class="muted">阈值 ¥{{ costGuard.user_warning_yuan || 0 }} / 24h</div>
          </div>
        </div>
        <div v-if="visibleHighCostUsers.length" class="warning-strip">
          <div v-for="item in visibleHighCostUsers.slice(0, 4)" :key="item.user_id" class="warning-card">
            <strong>{{ displayUser(item) }}</strong>
            <span>24h 成本 ¥{{ item.cost_yuan_24h }} · {{ item.calls_24h }} 次 · {{ item.total_tokens_24h }} token</span>
            <button v-if="!isUserHandled(item)" class="btn-ghost btn-sm" type="button" @click="markUserHandled(item)">标记已处理</button>
            <button v-else class="btn-ghost btn-sm" type="button" @click="restoreHandled(userKey(item))">重新显示</button>
          </div>
        </div>
        <div class="table-scroll">
          <table class="admin-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>24h 调用</th>
                <th>24h 成本</th>
                <th>窗口调用</th>
                <th>窗口失败</th>
                <th>失败率</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in providerRows" :key="item.provider">
                <td><strong>{{ item.provider }}</strong></td>
                <td>{{ item.calls_24h }}</td>
                <td>¥{{ item.cost_yuan_24h }}</td>
                <td>{{ item.calls_window }}</td>
                <td>{{ item.failures_window }}</td>
                <td>{{ pct(item.failure_rate_window) }}</td>
                <td>
                  <el-tag :type="item.blocked ? 'danger' : 'success'" size="small">
                    {{ item.blocked ? reasonLabel(item.reason) : '正常' }}
                  </el-tag>
                  <div v-if="item.retry_after_seconds" class="muted">{{ item.retry_after_seconds }} 秒后重试</div>
                </td>
              </tr>
              <tr v-if="!providerRows.length">
                <td colspan="7" class="empty-cell">暂无 LLM 调用记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="usersOpen = !usersOpen">
          <span>单用户成本预警</span>
          <span class="panel-meta">{{ visibleHighCostUsers.length }} 人待处理，{{ hiddenHighCostUsers.length }} 人已处理 · {{ usersOpen ? '收起' : '展开' }}</span>
        </div>
        <div v-show="usersOpen" class="table-scroll">
          <table class="admin-table">
            <thead>
              <tr>
                <th>用户</th>
                <th>24h 成本</th>
                <th>24h 调用</th>
                <th>24h Token</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in visibleHighCostUsers" :key="item.user_id">
                <td>
                  <strong>{{ displayUser(item) }}</strong>
                  <div class="muted">#{{ item.user_id }} · {{ item.email || '—' }}</div>
                </td>
                <td>¥{{ item.cost_yuan_24h }}</td>
                <td>{{ item.calls_24h }}</td>
                <td>{{ item.total_tokens_24h }}</td>
                <td>
                  <button v-if="!isUserHandled(item)" class="btn-ghost btn-sm" type="button" @click="markUserHandled(item)">标记已处理</button>
                  <button v-else class="btn-ghost btn-sm" type="button" @click="restoreHandled(userKey(item))">重新显示</button>
                </td>
              </tr>
              <tr v-if="!visibleHighCostUsers.length">
                <td colspan="5" class="empty-cell">暂无未处理的高成本用户预警</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="secretsOpen = !secretsOpen">
          <span>外部服务密钥配置状态</span>
          <span class="panel-meta">{{ configuredSecrets }}/{{ secretRows.length }} 已配置 · {{ secretsOpen ? '收起' : '展开' }}</span>
        </div>
        <div v-show="secretsOpen" class="secret-grid">
          <div v-for="item in secretRows" :key="item.name" class="secret-row">
            <span>{{ item.name }}</span>
            <el-tag :type="item.configured ? 'success' : 'info'" size="small">
              {{ item.configured ? '已配置' : '未配置' }}
            </el-tag>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSecurityHealth } from '@/api/admin'
import { formatDateTimeMinute } from '@/utils/dateTime'

const HANDLED_KEY = 'gzh-security-health-handled-v1'

const loading = ref(false)
const secretsOpen = ref(false)
const usersOpen = ref(true)
const showHandled = ref(false)
const handled = ref({})
const data = ref({ overall: {}, counts: {}, groups: [], secret_presence: [], cost_guard: {} })

const groups = computed(() => data.value.groups || [])
const secretRows = computed(() => data.value.secret_presence || [])
const configuredSecrets = computed(() => secretRows.value.filter(item => item.configured).length)
const costGuard = computed(() => data.value.cost_guard || {})
const providerRows = computed(() => costGuard.value.providers || [])
const highCostUsers = computed(() => costGuard.value.high_cost_users || [])
const displayGroups = computed(() => groups.value.map(group => {
  const items = (group.items || []).map(item => enrichHealthItem(group, item))
  const hiddenCount = items.filter(item => item.handled && item.level !== 'ok').length
  return {
    ...group,
    hiddenCount,
    items: showHandled.value ? items : items.filter(item => !item.handled || item.level === 'ok'),
  }
}))
const displayedCounts = computed(() => {
  const result = { ok: 0, warn: 0, critical: 0 }
  for (const group of displayGroups.value) {
    for (const item of group.items) {
      result[item.level] = (result[item.level] || 0) + 1
    }
  }
  return result
})
const handledHealthCount = computed(() => groups.value.reduce((total, group) => {
  return total + (group.items || []).filter(item => isHealthHandled(group, item) && item.level !== 'ok').length
}, 0))
const visibleHighCostUsers = computed(() => highCostUsers.value.filter(item => showHandled.value || !isUserHandled(item)))
const hiddenHighCostUsers = computed(() => highCostUsers.value.filter(item => isUserHandled(item)))
const handledCount = computed(() => handledHealthCount.value + hiddenHighCostUsers.value.length)
const displayedOverall = computed(() => {
  if (displayedCounts.value.critical > 0) return { level: 'critical', message: '仍有未处理的高风险项' }
  if (displayedCounts.value.warn > 0) return { level: 'warn', message: '仍有未处理的待关注项' }
  if (handledCount.value > 0) return { level: 'ok', message: '未处理项已清空' }
  return data.value.overall || {}
})

async function load() {
  loading.value = true
  try {
    const resp = await getSecurityHealth()
    data.value = resp.data || {}
  } finally {
    loading.value = false
  }
}

function levelLabel(level) {
  return { ok: '正常', warn: '待关注', critical: '高风险' }[level] || level
}

function tagType(level) {
  return { ok: 'success', warn: 'warning', critical: 'danger' }[level] || 'info'
}

function pct(value) {
  return `${Math.round(Number(value || 0) * 10000) / 100}%`
}

function reasonLabel(reason) {
  const map = {
    provider_daily_budget_exceeded: '预算超限',
    provider_failure_breaker: '失败熔断',
  }
  return map[reason] || reason || '已拦截'
}

function displayUser(item) {
  return item.username || item.phone || item.email || `用户 #${item.user_id}`
}

function healthKey(group, item) {
  return `health:${data.value.environment || 'env'}:${group.key}:${item.title}`
}

function healthSignature(item) {
  return [item.level, item.value ?? '', item.message ?? '', (item.actions || []).join('|')].join('::')
}

function userKey(item) {
  return `user-cost:${item.user_id}`
}

function userSignature(item) {
  return [costGuard.value.user_warning_yuan || 0, item.cost_yuan_24h || 0, item.calls_24h || 0, item.total_tokens_24h || 0].join('::')
}

function isHandled(key, signature) {
  const record = handled.value[key]
  return Boolean(record && record.signature === signature)
}

function isHealthHandled(group, item) {
  return isHandled(healthKey(group, item), healthSignature(item))
}

function isUserHandled(item) {
  return isHandled(userKey(item), userSignature(item))
}

function enrichHealthItem(group, item) {
  const key = healthKey(group, item)
  const record = handled.value[key]
  return {
    ...item,
    key,
    handled: isHandled(key, healthSignature(item)),
    handledAt: record?.handledAt,
  }
}

function saveHandled() {
  localStorage.setItem(HANDLED_KEY, JSON.stringify(handled.value))
}

function markHandled(key, signature) {
  handled.value = {
    ...handled.value,
    [key]: { signature, handledAt: new Date().toISOString() },
  }
  saveHandled()
}

function markHealthHandled(item) {
  markHandled(item.key, healthSignature(item))
  ElMessage.success('已处理，默认视图会收起这一项')
}

function markUserHandled(item) {
  markHandled(userKey(item), userSignature(item))
  ElMessage.success('用户成本预警已处理')
}

function restoreHandled(key) {
  const next = { ...handled.value }
  delete next[key]
  handled.value = next
  saveHandled()
}

function clearHandled() {
  handled.value = {}
  saveHandled()
  ElMessage.success('已清空处理状态')
}

function loadHandled() {
  try {
    handled.value = JSON.parse(localStorage.getItem(HANDLED_KEY) || '{}')
  } catch {
    handled.value = {}
  }
}

function fmtDate(value) {
  if (!value) return '—'
  try {
    return formatDateTimeMinute(value, '-')
  } catch {
    return value
  }
}

onMounted(() => {
  loadHandled()
  load()
})
</script>

<style scoped>
.monitor-page { max-width: 1180px; margin: 0 auto; padding: 24px 12px 80px; }
.monitor-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.kicker { color: var(--clay-deep); font-size: 13px; font-weight: 700; }
h1 { margin: 4px 0 0; font-family: var(--serif); font-size: 34px; color: var(--ink); }
.monitor-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.panel { background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); padding: 18px; }
.panel-main { grid-column: 1 / -1; }
.panel-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; font-weight: 700; color: var(--ink); }
.hero-panel { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 18px; align-items: center; }
.hero-actions { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 10px; }
.hero-status { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 22px; color: var(--ink); }
.status-dot { width: 12px; height: 12px; border-radius: 50%; background: #6a776f; }
.status-dot.ok { background: #2f8f55; }
.status-dot.warn { background: #b7791f; }
.status-dot.critical { background: #c0392b; }
.count-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.count-card { border: 1px solid var(--line); border-radius: var(--r-sm); padding: 12px; background: var(--ivory); }
.count-card span { display: block; color: var(--ink-4); font-size: 12px; }
.count-card strong { display: block; margin-top: 4px; font-size: 28px; color: var(--ink); }
.count-card.warn strong { color: #9a6a1d; }
.count-card.critical strong { color: #a33a2c; }
.muted { font-size: 12px; color: var(--ink-4); line-height: 1.6; }
.health-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.health-card { border: 1px solid var(--line); border-radius: var(--r-sm); padding: 14px; background: var(--ivory); }
.health-card.warn { border-color: #e3b665; background: #fff8e8; }
.health-card.critical { border-color: #dfa29a; background: #fff0ef; }
.health-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.health-value { margin-top: 5px; max-width: 520px; color: var(--ink-4); font-size: 12px; overflow-wrap: anywhere; }
.health-message { margin-top: 10px; color: var(--ink-3); font-size: 13px; line-height: 1.55; }
.action-list { margin: 10px 0 0; padding-left: 18px; color: var(--ink-3); font-size: 13px; line-height: 1.6; }
.card-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.quiet-card { border: 1px dashed var(--line); border-radius: var(--r-sm); padding: 18px; color: var(--ink-4); background: var(--ivory); font-size: 13px; }
.panel-collapsible { padding-bottom: 14px; }
.panel-collapsible .panel-title { margin-bottom: 0; }
.panel-title-clickable { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: pointer; }
.panel-meta { color: var(--ink-4); font-size: 12px; font-weight: 600; white-space: nowrap; }
.secret-grid { margin-top: 14px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.secret-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--ivory); font-size: 13px; color: var(--ink); }
.guard-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.guard-card { border: 1px solid var(--line); border-radius: var(--r-sm); padding: 12px 14px; background: var(--ivory); }
.guard-card.critical { border-color: #dfa29a; background: #fff0ef; }
.guard-card span { display: block; color: var(--ink-4); font-size: 12px; }
.guard-card strong { display: block; margin-top: 4px; color: var(--ink); font-size: 24px; font-variant-numeric: tabular-nums; }
.table-scroll { max-height: 360px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--paper); }
.table-scroll .admin-table th { position: sticky; top: 0; z-index: 1; }
.admin-table { width: 100%; min-width: 780px; border-collapse: collapse; }
.admin-table th, .admin-table td { text-align: left; padding: 11px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.admin-table th { font-size: 12px; color: var(--ink-4); font-weight: 700; background: var(--ivory); }
.empty-cell { text-align: center !important; color: var(--ink-4); padding: 24px 10px !important; }
.warning-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.warning-card { border: 1px solid #dfa29a; border-radius: var(--r-sm); padding: 10px 12px; background: #fff0ef; color: var(--ink-3); font-size: 13px; }
.warning-card strong { display: block; color: var(--ink); margin-bottom: 4px; }
.warning-card .btn-ghost { margin-top: 8px; }
@media (max-width: 900px) {
  .monitor-grid, .hero-panel, .health-grid, .secret-grid, .guard-summary, .warning-strip { grid-template-columns: 1fr; }
  .count-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .hero-actions { justify-content: flex-start; flex-wrap: wrap; }
}
</style>
