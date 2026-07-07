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
            <span :class="['status-dot', overall.level]"></span>
            <strong>{{ overall.message || '加载中' }}</strong>
          </div>
          <div class="muted">当前环境：{{ data.environment || '-' }}。这里展示运行时、部署边界、密钥治理和持续安全项。</div>
        </div>
        <div class="count-grid">
          <div class="count-card ok"><span>正常</span><strong>{{ counts.ok || 0 }}</strong></div>
          <div class="count-card warn"><span>待关注</span><strong>{{ counts.warn || 0 }}</strong></div>
          <div class="count-card critical"><span>高风险</span><strong>{{ counts.critical || 0 }}</strong></div>
        </div>
      </section>

      <section v-for="group in groups" :key="group.key" class="panel panel-main">
        <div class="panel-title">{{ group.title }}</div>
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
          </div>
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
import { getSecurityHealth } from '@/api/admin'

const loading = ref(false)
const secretsOpen = ref(false)
const data = ref({ overall: {}, counts: {}, groups: [], secret_presence: [], cost_guard: {} })

const overall = computed(() => data.value.overall || {})
const counts = computed(() => data.value.counts || {})
const groups = computed(() => data.value.groups || [])
const secretRows = computed(() => data.value.secret_presence || [])
const configuredSecrets = computed(() => secretRows.value.filter(item => item.configured).length)
const costGuard = computed(() => data.value.cost_guard || {})
const providerRows = computed(() => costGuard.value.providers || [])

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
.hero-panel { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 18px; align-items: center; }
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
.panel-collapsible { padding-bottom: 14px; }
.panel-collapsible .panel-title { margin-bottom: 0; }
.panel-title-clickable { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: pointer; }
.panel-meta { color: var(--ink-4); font-size: 12px; font-weight: 600; white-space: nowrap; }
.secret-grid { margin-top: 14px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.secret-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--ivory); font-size: 13px; color: var(--ink); }
.guard-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
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
@media (max-width: 900px) {
  .monitor-grid, .hero-panel, .health-grid, .secret-grid, .guard-summary { grid-template-columns: 1fr; }
  .count-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
