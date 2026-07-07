<template>
  <div class="admin-page">
    <div class="admin-head">
      <div>
        <div class="kicker">管理员后台</div>
        <h1>后台监测</h1>
      </div>
      <button class="btn-ghost btn-uniform" @click="loadAll" :disabled="loading">刷新</button>
    </div>

    <div v-loading="loading" class="admin-grid">
      <section class="panel panel-main">
        <div class="panel-title">
          <span>系统状态</span>
          <el-tag :type="overview.overall?.level === 'ok' ? 'success' : 'warning'">
            {{ overview.overall?.message || '加载中' }}
          </el-tag>
        </div>
        <div class="signal-grid">
          <div v-for="(item, key) in overview.signals" :key="key" class="signal">
            <div class="signal-name">{{ signalLabels[key] || key }}</div>
            <div class="signal-value">{{ item.value }}</div>
            <div :class="['signal-msg', item.level]">{{ item.message }}</div>
          </div>
        </div>
        <div v-if="currentAlerts.length" class="alert-strip">
          <div v-for="item in currentAlerts" :key="item.key" :class="['alert-card', item.level]">
            <div class="alert-title">{{ item.title }}</div>
            <div class="alert-message">{{ item.message }}</div>
            <div class="alert-actions">
              <button class="btn-ghost btn-sm" @click="goAlertTarget(item.key)">查看相关</button>
            </div>
          </div>
        </div>
        <div v-else class="alert-empty">当前没有需要处理的监测告警</div>
      </section>

      <section class="panel">
        <div class="panel-title">内容链路</div>
        <div class="metric"><span>2 小时新增资讯</span><strong>{{ pipeline.raw_infos_2h ?? 0 }}</strong></div>
        <div class="metric"><span>24 小时新增资讯</span><strong>{{ pipeline.raw_infos_24h ?? 0 }}</strong></div>
        <div class="metric"><span>24 小时新增信息簇</span><strong>{{ pipeline.clusters_24h ?? 0 }}</strong></div>
        <div class="metric"><span>待预处理</span><strong>{{ pipeline.pending_raw_infos ?? 0 }}</strong></div>
        <div class="muted">最近采集：{{ fmtDate(pipeline.latest_raw_scraped_at) }}</div>
      </section>

      <section class="panel">
        <div class="panel-title">任务运行</div>
        <div class="metric"><span>等待中</span><strong>{{ tasks.pending_24h ?? 0 }}</strong></div>
        <div class="metric"><span>处理中</span><strong>{{ tasks.processing_24h ?? 0 }}</strong></div>
        <div class="metric"><span>24 小时失败</span><strong>{{ tasks.failed_24h ?? 0 }}</strong></div>
        <div class="muted">最近完成：{{ fmtDate(tasks.latest_completed_at) }}</div>
      </section>

      <section class="panel">
        <div class="panel-title">用户概览</div>
        <div class="metric"><span>总用户</span><strong>{{ users.total ?? 0 }}</strong></div>
        <div class="metric"><span>24 小时活跃</span><strong>{{ users.active_24h ?? 0 }}</strong></div>
        <div class="metric"><span>管理员</span><strong>{{ users.admins ?? 0 }}</strong></div>
        <div class="metric"><span>低余额用户</span><strong>{{ users.low_credit_users ?? 0 }}</strong></div>
      </section>

      <section class="panel panel-main">
        <div class="panel-title">
          <span>安全预警</span>
          <el-tag :type="securityAlerts.length ? 'danger' : 'success'">
            {{ securityAlerts.length ? `${securityAlerts.length} 条需要关注` : '当前平稳' }}
          </el-tag>
        </div>
        <div v-if="securityAlerts.length" class="security-grid">
          <div v-for="item in securityAlerts" :key="item.key" :class="['security-card', item.level]">
            <div class="security-top">
              <strong>{{ item.title }}</strong>
              <el-tag :type="item.level === 'critical' ? 'danger' : 'warning'" size="small">{{ item.levelLabel }}</el-tag>
            </div>
            <div class="security-desc">{{ item.message }}</div>
            <div class="security-meta">{{ item.time }}</div>
          </div>
        </div>
        <div v-else class="alert-empty">最近敏感操作和系统告警未发现异常峰值</div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('roles')">
          <div>
            <span>后台角色</span>
            <span class="muted title-note">按职责分配：运营 / 客服 / 财务 / 审计 / 管理员</span>
          </div>
          <button class="btn-ghost btn-sm" type="button">{{ openPanels.roles ? '收起' : '展开' }}</button>
        </div>
        <div v-show="openPanels.roles" class="panel-body">
          <div v-if="userStore.isSuperAdmin" class="grant-row">
            <el-input v-model="phone" placeholder="输入用户手机号" clearable />
            <el-select v-model="roleDraft" placeholder="选择角色">
              <el-option label="管理员" value="admin" />
              <el-option label="运营" value="ops" />
              <el-option label="客服" value="support" />
              <el-option label="财务" value="finance" />
              <el-option label="审计" value="auditor" />
              <el-option label="普通用户" value="user" />
            </el-select>
            <button class="btn-primary btn-uniform" @click="grantRole" :disabled="!phone || saving">更新角色</button>
          </div>
          <div class="table-scroll compact-scroll">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>用户</th>
                  <th>手机号</th>
                  <th>角色</th>
                  <th>状态</th>
                  <th>最近登录</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in admins" :key="item.id">
                  <td>
                    <strong>{{ item.full_name || item.username }}</strong>
                    <div class="muted">{{ item.email || '—' }}</div>
                  </td>
                  <td>{{ item.phone || '—' }}</td>
                  <td>
                    <el-tag :type="item.is_superuser ? 'danger' : 'info'" size="small">
                      {{ roleLabel(item) }}
                    </el-tag>
                  </td>
                  <td>{{ item.is_active ? '启用' : '禁用' }}</td>
                  <td>{{ fmtDate(item.last_login) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section ref="historySection" class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('history')">
          <span>监测历史</span>
          <button class="btn-ghost btn-sm" type="button">{{ openPanels.history ? '收起' : '展开' }}</button>
        </div>
        <div v-show="openPanels.history" class="table-scroll">
          <table class="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>状态</th>
              <th>2 小时资讯</th>
              <th>24 小时信息簇</th>
              <th>待预处理</th>
              <th>失败任务</th>
              <th>24 小时活跃</th>
              <th>低余额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in snapshots" :key="item.id">
              <td>{{ fmtDate(item.generated_at) }}</td>
              <td><el-tag :type="item.level === 'ok' ? 'success' : 'warning'" size="small">{{ item.message || item.level }}</el-tag></td>
              <td>{{ item.raw_infos_2h }}</td>
              <td>{{ item.clusters_24h }}</td>
              <td>{{ item.pending_raw_infos }}</td>
              <td>{{ item.failed_tasks_24h }}</td>
              <td>{{ item.active_users_24h }}</td>
              <td>{{ item.low_credit_users }}</td>
            </tr>
            <tr v-if="!snapshots.length">
              <td colspan="8" class="empty-cell">暂无历史快照，等待 Celery Beat 跑一次监测任务</td>
            </tr>
          </tbody>
          </table>
        </div>
      </section>

      <section ref="alertsSection" class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('alerts')">
          <span>告警历史</span>
          <button class="btn-ghost btn-sm" type="button">{{ openPanels.alerts ? '收起' : '展开' }}</button>
        </div>
        <div v-show="openPanels.alerts" class="table-scroll">
          <table class="admin-table">
          <thead>
            <tr>
              <th>告警</th>
              <th>级别</th>
              <th>状态</th>
              <th>当前值</th>
              <th>阈值</th>
              <th>最近触发</th>
              <th>备注</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in alertRows" :key="item.id">
              <td>
                <strong>{{ item.title }}</strong>
                <div class="muted">{{ item.message }}</div>
              </td>
              <td><el-tag :type="item.level === 'critical' ? 'danger' : 'warning'" size="small">{{ item.level }}</el-tag></td>
              <td>{{ item.status === 'open' ? '未恢复' : '已恢复' }}</td>
              <td>{{ item.value ?? '—' }}</td>
              <td>{{ item.threshold ?? '—' }}</td>
              <td>{{ fmtDate(item.last_triggered_at) }}</td>
              <td class="note-cell">{{ item.note || '—' }}</td>
              <td class="action-cell">
                <button class="btn-ghost btn-sm" @click="openAlertNote(item)">备注</button>
                <button v-if="item.status === 'open'" class="btn-ghost btn-sm" @click="resolveAlert(item)">标记恢复</button>
                <button class="btn-ghost btn-sm" @click="goAlertTarget(item.key)">查看相关</button>
              </td>
            </tr>
            <tr v-if="!alertRows.length">
              <td colspan="6" class="empty-cell">暂无告警记录</td>
            </tr>
          </tbody>
          </table>
        </div>
      </section>

      <section ref="usersSection" class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('users')">
          <span>用户列表</span>
          <div class="panel-actions" @click.stop>
            <el-input v-model="userKeyword" placeholder="搜索用户/手机号/邮箱" clearable style="width: 260px;" @change="loadUsers" />
            <button class="btn-ghost btn-sm" type="button" @click="togglePanel('users')">{{ openPanels.users ? '收起' : '展开' }}</button>
          </div>
        </div>
        <div v-show="openPanels.users" class="table-scroll">
          <table class="admin-table">
          <thead>
            <tr>
              <th>用户</th>
              <th>手机号</th>
              <th>角色</th>
              <th>积分</th>
              <th>注册时间</th>
              <th>最近登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in userRows" :key="item.id">
              <td>
                <strong>{{ item.full_name || item.username }}</strong>
                <div class="muted">{{ item.email || '—' }}</div>
              </td>
              <td>{{ item.phone || '—' }}</td>
              <td>{{ roleLabel(item) }}</td>
              <td>{{ item.credit_balance }}</td>
              <td>{{ fmtDate(item.created_at) }}</td>
              <td>{{ fmtDate(item.last_login) }}</td>
              <td class="action-cell">
                <button
                  v-if="!item.is_superuser"
                  class="btn-ghost btn-sm"
                  @click="toggleUserStatus(item)"
                >
                  {{ item.is_active ? '禁用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
          </table>
        </div>
      </section>

      <section ref="failedTasksSection" class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('failedTasks')">
          <span>最近失败任务</span>
          <button class="btn-ghost btn-sm" type="button">{{ openPanels.failedTasks ? '收起' : '展开' }}</button>
        </div>
        <div v-show="openPanels.failedTasks" class="table-scroll">
          <table class="admin-table">
          <thead>
            <tr>
              <th>任务</th>
              <th>状态</th>
              <th>错误</th>
              <th>更新时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in failedTasks" :key="item.id">
              <td>
                <strong>{{ item.title }}</strong>
                <div class="muted">{{ item.id }}</div>
              </td>
              <td><el-tag type="danger" size="small">{{ item.status }}</el-tag></td>
              <td class="error-cell">{{ item.error_message || '—' }}</td>
              <td>{{ fmtDate(item.updated_at) }}</td>
            </tr>
            <tr v-if="!failedTasks.length">
              <td colspan="4" class="empty-cell">最近没有失败任务</td>
            </tr>
          </tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-main panel-collapsible">
        <div class="panel-title panel-title-clickable" @click="togglePanel('audit')">
          <div>
            <span>敏感操作记录</span>
            <span class="muted title-note">角色变更、积分赠送、封禁、定价调整、告警处理都会进入这里</span>
          </div>
          <button class="btn-ghost btn-sm" type="button">{{ openPanels.audit ? '收起' : '展开' }}</button>
        </div>
        <div v-show="openPanels.audit" class="table-scroll">
          <table class="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者</th>
              <th>动作</th>
              <th>目标</th>
              <th>来源</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in auditRows" :key="item.id" :class="{ 'audit-risk-row': auditRiskLevel(item) === 'critical' }">
              <td>{{ fmtDate(item.occurred_at) }}</td>
              <td>{{ item.actor_user_id || '系统' }}</td>
              <td>
                <el-tag :type="auditRiskLevel(item) === 'critical' ? 'danger' : 'info'" size="small">
                  {{ actionLabel(item.action) }}
                </el-tag>
              </td>
              <td>{{ item.target_type || '—' }} {{ item.target_id || '' }}</td>
              <td>
                <div>{{ item.metadata?.ip || '—' }}</div>
                <div class="muted ua-cell">{{ item.metadata?.user_agent || '—' }}</div>
              </td>
              <td>
                <strong>{{ item.summary || '—' }}</strong>
                <div v-if="item.detail" class="muted">{{ item.detail }}</div>
              </td>
            </tr>
            <tr v-if="!auditRows.length">
              <td colspan="6" class="empty-cell">暂无管理员操作记录</td>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  getAdminAuditLogs,
  getAdminUsers,
  getAdmins,
  getFailedTasks,
  getMonitoringAlerts,
  getMonitoringOverview,
  getMonitoringSnapshots,
  setAdminByPhone,
  updateAdminUserStatus,
  updateMonitoringAlert,
} from '@/api/admin'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const alertsSection = ref(null)
const failedTasksSection = ref(null)
const usersSection = ref(null)
const phone = ref('')
const roleDraft = ref('admin')
const userKeyword = ref('')
const overview = reactive({ overall: null, signals: {}, content_pipeline: {}, tasks: {}, users: {} })
const admins = ref([])
const snapshots = ref([])
const alertRows = ref([])
const userRows = ref([])
const failedTasks = ref([])
const auditRows = ref([])
const openPanels = reactive({
  roles: true,
  history: false,
  alerts: true,
  users: true,
  failedTasks: false,
  audit: true,
})

const sensitiveActions = new Set([
  'admin.role.update',
  'credits.gift',
  'user.status.update',
  'llm_pricing.create',
  'llm_pricing.update',
])

const pipeline = computed(() => overview.content_pipeline || {})
const tasks = computed(() => overview.tasks || {})
const users = computed(() => overview.users || {})
const currentAlerts = computed(() => overview.current_alerts || [])
const securityAlerts = computed(() => {
  const items = []
  const criticalAlerts = alertRows.value
    .filter(item => item.status === 'open' && item.level === 'critical')
    .slice(0, 3)
  for (const item of criticalAlerts) {
    items.push({
      key: `alert-${item.id}`,
      title: item.title,
      message: item.message,
      level: 'critical',
      levelLabel: '系统告警',
      time: fmtDate(item.last_triggered_at),
    })
  }

  const recentSensitive = auditRows.value
    .filter(item => sensitiveActions.has(item.action))
    .slice(0, 6)
  for (const item of recentSensitive) {
    items.push({
      key: `audit-${item.id}`,
      title: actionLabel(item.action),
      message: item.summary || item.detail || '敏感后台操作',
      level: auditRiskLevel(item),
      levelLabel: auditRiskLevel(item) === 'critical' ? '高风险操作' : '敏感操作',
      time: fmtDate(item.occurred_at),
    })
  }
  return items.slice(0, 8)
})
const signalLabels = {
  data_freshness: '数据新鲜度',
  preprocess_backlog: '预处理积压',
  task_failures: '任务失败',
  cluster_output: '信息簇产出',
}

async function loadAll() {
  loading.value = true
  try {
    const [monitorResp, adminResp, snapshotResp, alertResp, userResp, failedResp, auditResp] = await Promise.allSettled([
      getMonitoringOverview(),
      getAdmins(),
      getMonitoringSnapshots(24),
      getMonitoringAlerts({ status: 'all', limit: 30 }),
      getAdminUsers({ limit: 30, keyword: userKeyword.value || undefined }),
      getFailedTasks(30),
      getAdminAuditLogs(50),
    ])
    Object.assign(overview, settledData(monitorResp) || {})
    admins.value = settledData(adminResp)?.items || []
    snapshots.value = settledData(snapshotResp)?.items || []
    alertRows.value = settledData(alertResp)?.items || []
    userRows.value = settledData(userResp)?.items || []
    failedTasks.value = settledData(failedResp)?.items || []
    auditRows.value = settledData(auditResp)?.items || []
  } finally {
    loading.value = false
  }
}

function settledData(result) {
  return result.status === 'fulfilled' ? result.value.data : null
}

function togglePanel(key) {
  openPanels[key] = !openPanels[key]
}

function actionLabel(action) {
  const map = {
    'admin.grant': '设置管理员',
    'admin.revoke': '取消管理员',
    'admin.role.update': '后台角色变更',
    'credits.gift': '赠送积分',
    'user.status.update': '用户状态变更',
    'llm_pricing.create': '新增模型单价',
    'llm_pricing.update': '修改模型单价',
    'monitoring_alert.update': '处理告警',
  }
  return map[action] || action
}

function auditRiskLevel(item) {
  if (['admin.role.update', 'credits.gift', 'user.status.update', 'llm_pricing.update'].includes(item.action)) {
    return 'critical'
  }
  return sensitiveActions.has(item.action) ? 'warn' : 'info'
}

function roleLabel(item) {
  if (item.is_superuser) return '最高管理员'
  const map = {
    admin: '管理员',
    ops: '运营',
    support: '客服',
    finance: '财务',
    auditor: '审计',
    user: '普通用户',
  }
  return map[item.role] || item.role || '普通用户'
}

async function loadUsers() {
  const resp = await getAdminUsers({ limit: 30, keyword: userKeyword.value || undefined })
  userRows.value = resp.data?.items || []
}

async function grantRole() {
  saving.value = true
  try {
    await setAdminByPhone(phone.value.trim(), roleDraft.value)
    ElMessage.success('后台角色已更新')
    phone.value = ''
    roleDraft.value = 'admin'
    await loadAll()
  } finally {
    saving.value = false
  }
}

async function toggleUserStatus(item) {
  const nextActive = !item.is_active
  const actionText = nextActive ? '启用' : '禁用'
  const { value } = await ElMessageBox.prompt(`请输入${actionText}原因`, `${actionText}用户：${item.full_name || item.username}`, {
    confirmButtonText: actionText,
    cancelButtonText: '取消',
    inputType: 'textarea',
    type: nextActive ? 'info' : 'warning',
  })
  await updateAdminUserStatus(item.id, { is_active: nextActive, reason: value || '' })
  ElMessage.success(`用户已${actionText}`)
  await loadAll()
}

async function openAlertNote(item) {
  const { value } = await ElMessageBox.prompt('处理备注', item.title, {
    confirmButtonText: '保存',
    cancelButtonText: '取消',
    inputValue: item.note || '',
    inputType: 'textarea',
  })
  await updateMonitoringAlert(item.id, { note: value, resolve: false })
  ElMessage.success('备注已保存')
  await loadAll()
}

async function resolveAlert(item) {
  await ElMessageBox.confirm('确认把这条告警标记为已恢复？如果下一轮监测仍然触发，它会重新打开。', item.title, {
    confirmButtonText: '标记恢复',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await updateMonitoringAlert(item.id, { note: item.note || '', resolve: true })
  ElMessage.success('告警已标记恢复')
  await loadAll()
}

function scrollToSection(sectionRef) {
  sectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function goAlertTarget(key) {
  if (key.includes('tasks.')) {
    scrollToSection(failedTasksSection)
  } else if (key.includes('users.')) {
    scrollToSection(usersSection)
  } else if (key.includes('data_freshness')) {
    router.push('/tools/gzh-test')
  } else {
    scrollToSection(alertsSection)
  }
}

function fmtDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16)
  } catch {
    return value
  }
}

onMounted(loadAll)
</script>

<style scoped>
.admin-page { max-width: 1180px; margin: 0 auto; padding: 24px 12px 80px; }
.admin-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.kicker { color: var(--clay-deep); font-size: 13px; font-weight: 700; letter-spacing: .06em; }
h1 { margin: 4px 0 0; font-family: var(--serif); font-size: 34px; color: var(--ink); }
.admin-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.panel { background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); padding: 18px; }
.panel-main { grid-column: 1 / -1; }
.panel-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; font-weight: 700; color: var(--ink); }
.panel-collapsible { padding-bottom: 14px; }
.panel-collapsible .panel-title { margin-bottom: 0; }
.panel-body { margin-top: 14px; }
.panel-title-clickable { cursor: pointer; gap: 12px; }
.panel-title-clickable:hover { color: var(--clay-deep); }
.title-note { margin-left: 10px; font-weight: 400; }
.panel-actions { display: flex; align-items: center; gap: 10px; }
.signal-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.signal { background: var(--ivory); border: 1px solid var(--line); border-radius: var(--r-sm); padding: 14px; }
.signal-name, .muted { font-size: 12px; color: var(--ink-4); }
.signal-value { margin-top: 6px; font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--ink); }
.signal-msg { margin-top: 4px; font-size: 13px; color: var(--ink-3); }
.signal-msg.warn { color: #b7791f; }
.signal-msg.critical { color: #c0392b; }
.alert-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.alert-card { border: 1px solid var(--line); border-radius: var(--r-sm); padding: 12px 14px; background: var(--ivory); }
.alert-card.warn { border-color: #e3b665; background: #fff8e8; }
.alert-card.critical { border-color: #dfa29a; background: #fff0ef; }
.alert-title { font-weight: 700; color: var(--ink); }
.alert-message { margin-top: 4px; color: var(--ink-3); font-size: 13px; line-height: 1.5; }
.alert-actions { margin-top: 10px; }
.alert-empty { margin-top: 14px; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--r-sm); color: var(--ink-3); background: var(--ivory); }
.metric { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--line); color: var(--ink-3); }
.metric strong { color: var(--ink); font-size: 20px; font-variant-numeric: tabular-nums; }
.security-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.security-card { border: 1px solid var(--line); border-radius: var(--r-sm); padding: 12px 14px; background: var(--ivory); }
.security-card.warn { border-color: #e3b665; background: #fff8e8; }
.security-card.critical { border-color: #dfa29a; background: #fff0ef; }
.security-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--ink); }
.security-desc { margin-top: 6px; color: var(--ink-3); font-size: 13px; line-height: 1.5; }
.security-meta { margin-top: 8px; color: var(--ink-4); font-size: 12px; }
.grant-row { display: grid; grid-template-columns: minmax(220px, 1fr) 180px auto; gap: 10px; margin-bottom: 14px; }
.table-scroll { margin-top: 14px; max-height: 420px; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--paper); }
.table-scroll.compact-scroll { max-height: 300px; }
.table-scroll .admin-table th { position: sticky; top: 0; z-index: 1; }
.admin-table { width: 100%; min-width: 760px; border-collapse: collapse; }
.admin-table th, .admin-table td { text-align: left; padding: 11px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
.admin-table th { font-size: 12px; color: var(--ink-4); font-weight: 700; background: var(--ivory); }
.audit-risk-row td { background: rgba(176, 73, 58, 0.04); }
.empty-cell { text-align: center !important; color: var(--ink-4); padding: 24px 10px !important; }
.error-cell { max-width: 520px; color: #9b2c2c; font-size: 13px; line-height: 1.5; }
.note-cell { max-width: 220px; color: var(--ink-3); font-size: 13px; line-height: 1.5; }
.ua-cell { max-width: 260px; overflow-wrap: anywhere; }
.action-cell { display: flex; gap: 6px; flex-wrap: wrap; }
@media (max-width: 900px) {
  .admin-grid, .signal-grid, .alert-strip, .security-grid { grid-template-columns: 1fr; }
  .grant-row { grid-template-columns: 1fr; }
  .panel-title-clickable, .panel-actions { align-items: stretch; }
  .panel-title-clickable { flex-direction: column; }
  .panel-actions { width: 100%; flex-direction: column; }
  .panel-actions .el-input { width: 100% !important; }
  .title-note { display: block; margin: 4px 0 0; }
  .table-scroll { max-height: 360px; }
}
</style>
