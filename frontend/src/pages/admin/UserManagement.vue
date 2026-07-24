<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6">用户管理</h1>

    <!-- 搜索栏 -->
    <div class="flex items-center gap-3 mb-6">
      <el-input
        v-model="keyword"
        placeholder="搜索用户名/手机号/邮箱"
        class="w-80"
        clearable
        @keyup.enter="fetchUsers"
        @clear="fetchUsers"
      />
      <el-button type="primary" @click="fetchUsers">查询</el-button>
      <el-button @click="keyword = ''; fetchUsers()">重置</el-button>
    </div>

    <!-- 用户表格 -->
    <el-table :data="users" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="email" label="邮箱" width="180">
        <template #default="{ row }">
          <span>{{ row.email || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_superuser ? 'danger' : 'info'" size="small">
            {{ row.is_superuser ? '超管' : row.role }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="已购产品" min-width="220">
        <template #default="{ row }">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="product in row.product_access || []"
              :key="product"
              type="success"
              size="small"
              effect="plain"
            >
              {{ productLabels[product] || product }}
            </el-tag>
            <el-tag v-if="!(row.product_access || []).length" type="info" size="small" effect="plain">
              免费版
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="credit_balance" label="积分" width="80" />
      <el-table-column label="注册时间" width="160">
        <template #default="{ row }">
          <span class="text-sm text-slate-500">{{ formatDate(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="440" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            @click="openDiagnosticsDialog(row)"
          >
            排障
          </el-button>
          <el-button
            size="small"
            @click="openRecordsDialog(row)"
          >
            使用记录
          </el-button>
          <el-button
            size="small"
            type="warning"
            plain
            @click="openCreditDialog(row)"
            :disabled="!userStore.isSuperAdmin"
          >
            改积分
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="openProductDialog(row)"
            :disabled="!userStore.isSuperAdmin || row.is_superuser"
          >
            产品权益
          </el-button>
          <el-button
            size="small"
            :type="row.is_active ? 'danger' : 'primary'"
            @click="toggleStatus(row)"
            :disabled="!userStore.isSuperAdmin || row.is_superuser"
            plain
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="productDialogVisible" title="设置产品权益" width="420px">
      <div v-if="editingUser" class="space-y-4">
        <div class="text-sm text-slate-500">
          用户：{{ editingUser.username }} / {{ editingUser.phone || '-' }}
        </div>
        <el-checkbox-group v-model="editingProducts">
          <div v-for="product in productOptions" :key="product.value" class="mb-2">
            <el-checkbox :label="product.value">{{ product.label }}</el-checkbox>
          </div>
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button @click="productDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingProducts" @click="saveProductAccess">保存</el-button>
      </template>
    </el-dialog>

    <!-- 调整积分 -->
    <el-dialog v-model="creditDialogVisible" title="调整用户积分" width="440px">
      <div v-if="creditUser" class="space-y-4">
        <div class="text-sm text-slate-500">
          用户：{{ creditUser.username }} · 当前余额
          <strong class="text-slate-700">{{ creditUser.credit_balance || 0 }}</strong> 积分
        </div>
        <el-radio-group v-model="creditMode">
          <el-radio-button label="add">增加</el-radio-button>
          <el-radio-button label="deduct">扣减</el-radio-button>
          <el-radio-button label="set">设为</el-radio-button>
        </el-radio-group>
        <el-input-number
          v-model="creditAmount"
          :min="creditMode === 'set' ? 0 : 1"
          :step="10"
          class="w-full"
        />
        <div class="text-sm text-slate-500">调整后余额约为 {{ creditPreview }} 积分</div>
        <el-input
          v-model="creditReason"
          type="textarea"
          :rows="3"
          maxlength="500"
          show-word-limit
          placeholder="请填写调整原因（必填，会记入操作审计）"
        />
      </div>
      <template #footer>
        <el-button @click="creditDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="savingCredit"
          :disabled="!creditReason.trim()"
          @click="saveCreditAdjust"
        >
          确认调整
        </el-button>
      </template>
    </el-dialog>

    <!-- 积分使用记录 -->
    <el-dialog v-model="recordsDialogVisible" title="积分使用记录" width="760px">
      <div v-loading="recordsLoading">
        <div v-if="recordsAccount" class="flex flex-wrap gap-6 mb-4 text-sm text-slate-600">
          <div>当前余额：<strong>{{ recordsAccount.balance }}</strong></div>
          <div>累计消耗：<strong>{{ recordsAccount.total_consumed }}</strong></div>
          <div>累计购买：<strong>{{ recordsAccount.total_purchased }}</strong></div>
          <div>累计赠送：<strong>{{ recordsAccount.total_gifted }}</strong></div>
        </div>
        <el-table :data="recordsList" stripe max-height="420" style="width: 100%">
          <el-table-column label="时间" width="160">
            <template #default="{ row }">
              <span class="text-sm text-slate-500">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="creditTypeTag(row.type)" size="small">{{ creditTypeLabel(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变动" width="90">
            <template #default="{ row }">
              <span :class="row.amount >= 0 ? 'text-green-600' : 'text-red-600'">
                {{ row.amount >= 0 ? '+' : '' }}{{ row.amount }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="balance_after" label="变动后" width="90" />
          <el-table-column label="操作 / 说明" min-width="220">
            <template #default="{ row }">
              <div class="text-sm">{{ operationLabel(row.operation) }}</div>
              <div v-if="row.description" class="text-xs text-slate-400">{{ row.description }}</div>
            </template>
          </el-table-column>
          <template #empty>暂无积分流水</template>
        </el-table>
      </div>
    </el-dialog>

    <!-- 排障 -->
    <el-dialog v-model="diagDialogVisible" title="用户排障" width="900px" top="6vh">
      <div v-loading="diagLoading">
        <div v-if="diagUser" class="mb-3 text-sm text-slate-600">
          用户：<strong>{{ diagUser.username }}</strong> · {{ diagUser.phone || '-' }}
          <span class="text-slate-400">（展示最近 {{ diagData.summary?.limit || 30 }} 条）</span>
        </div>
        <div v-if="diagData.summary" class="flex flex-wrap gap-2 mb-4">
          <el-tag type="info" size="small">生成记录 {{ diagData.summary.generation_total }}</el-tag>
          <el-tag :type="diagData.summary.generation_failed ? 'danger' : 'success'" size="small">
            生成失败 {{ diagData.summary.generation_failed }}
          </el-tag>
          <el-tag :type="diagData.summary.llm_errors ? 'danger' : 'success'" size="small">
            LLM 错误 {{ diagData.summary.llm_errors }}
          </el-tag>
          <el-tag :type="diagData.summary.api_errors ? 'danger' : 'success'" size="small">
            接口错误 {{ diagData.summary.api_errors }}
          </el-tag>
        </div>

        <el-tabs v-model="diagTab">
          <el-tab-pane label="生成记录" name="gen">
            <el-table :data="diagData.generation_records || []" stripe max-height="440" style="width: 100%"
              :row-class-name="({ row }) => (row.status === 'failed' ? 'diag-failed-row' : '')">
              <el-table-column label="时间" width="150">
                <template #default="{ row }"><span class="text-sm text-slate-500">{{ formatDate(row.created_at) }}</span></template>
              </el-table-column>
              <el-table-column label="类型" width="130">
                <template #default="{ row }">{{ operationLabel(row.type) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="genStatusTag(row.status)" size="small">{{ genStatusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="标题 / 失败原因" min-width="300">
                <template #default="{ row }">
                  <div class="text-sm">{{ row.display_title || '-' }}</div>
                  <div v-if="row.error" class="text-xs text-red-600 whitespace-pre-wrap break-all">{{ row.error }}</div>
                </template>
              </el-table-column>
              <el-table-column label="run_id" width="120">
                <template #default="{ row }"><span class="text-xs text-slate-400 break-all">{{ row.run_id }}</span></template>
              </el-table-column>
              <template #empty>该用户暂无生成记录</template>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="LLM 调用错误" name="llm">
            <el-table :data="diagData.llm_errors || []" stripe max-height="440" style="width: 100%">
              <el-table-column label="时间" width="150">
                <template #default="{ row }"><span class="text-sm text-slate-500">{{ formatDate(row.created_at) }}</span></template>
              </el-table-column>
              <el-table-column label="操作" width="130">
                <template #default="{ row }">{{ operationLabel(row.operation) }}</template>
              </el-table-column>
              <el-table-column label="模型" width="160">
                <template #default="{ row }"><span class="text-xs">{{ row.provider }} / {{ row.model }}</span></template>
              </el-table-column>
              <el-table-column label="错误信息" min-width="280">
                <template #default="{ row }">
                  <div class="text-xs text-red-600 whitespace-pre-wrap break-all">{{ row.error_message || row.finish_reason || '-' }}</div>
                </template>
              </el-table-column>
              <template #empty>该用户近期没有失败的 LLM 调用</template>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="接口错误" name="api">
            <el-table :data="diagData.api_errors || []" stripe max-height="440" style="width: 100%">
              <el-table-column label="时间" width="150">
                <template #default="{ row }"><span class="text-sm text-slate-500">{{ formatDate(row.created_at) }}</span></template>
              </el-table-column>
              <el-table-column label="状态码" width="90">
                <template #default="{ row }"><el-tag type="danger" size="small">{{ row.status_code }}</el-tag></template>
              </el-table-column>
              <el-table-column label="接口" min-width="320">
                <template #default="{ row }"><span class="text-xs break-all">{{ row.method }} {{ row.path }}</span></template>
              </el-table-column>
              <el-table-column label="耗时" width="100">
                <template #default="{ row }">{{ Math.round(row.duration_ms) }} ms</template>
              </el-table-column>
              <template #empty>该用户近期没有接口错误</template>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <!-- 分页 -->
    <div class="flex justify-center mt-6">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchUsers"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adjustUserCredits,
  getAdminUsers,
  getUserCredits,
  getUserDiagnostics,
  updateAdminUserProductAccess,
  updateAdminUserStatus,
} from '@/api/admin'
import { useUserStore } from '@/stores/user'

const users = ref([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const userStore = useUserStore()
const productDialogVisible = ref(false)
const editingUser = ref(null)
const editingProducts = ref([])
const savingProducts = ref(false)
const productLabels = {
  creation_tool: '创作工具',
  potential_commercial: '潜在商单',
  practical_camp: '实战营',
  xhs_topic: '小红书选题'
}
const productOptions = Object.entries(productLabels).map(([value, label]) => ({ value, label }))

// 调整积分
const creditDialogVisible = ref(false)
const creditUser = ref(null)
const creditMode = ref('add')
const creditAmount = ref(10)
const creditReason = ref('')
const savingCredit = ref(false)

// 使用记录
const recordsDialogVisible = ref(false)
const recordsLoading = ref(false)
const recordsAccount = ref(null)
const recordsList = ref([])

// 排障
const diagDialogVisible = ref(false)
const diagLoading = ref(false)
const diagUser = ref(null)
const diagData = ref({})
const diagTab = ref('gen')

const genStatusMeta = {
  completed: { label: '成功', tag: 'success' },
  failed: { label: '失败', tag: 'danger' },
  pending: { label: '进行中', tag: 'info' },
}
const genStatusLabel = (s) => genStatusMeta[s]?.label || s || '-'
const genStatusTag = (s) => genStatusMeta[s]?.tag || 'info'

const creditTypeMeta = {
  purchase: { label: '购买', tag: 'success' },
  gift: { label: '赠送', tag: 'success' },
  consume: { label: '消耗', tag: 'info' },
  refund: { label: '退款', tag: 'warning' },
  expire: { label: '过期清零', tag: 'danger' },
  adjust: { label: '人工调整', tag: 'warning' },
}
const operationLabels = {
  topic_mining: '选题挖掘',
  outline_generation: '大纲生成',
  content_generation: '正文生成',
  content_polish: '文案润色',
  title_generation: '标题生成',
  content_continuation: '正文续写',
  title_scoring: '标题评分',
  content_transform: '内容转写',
  content_imitate: '内容仿写',
  practical_research: '实操调研',
  admin_adjust: '管理员调整',
}

const creditPreview = computed(() => {
  const base = creditUser.value?.credit_balance || 0
  const amount = Number(creditAmount.value) || 0
  if (creditMode.value === 'set') return Math.max(amount, 0)
  if (creditMode.value === 'deduct') return Math.max(base - amount, 0)
  return base + amount
})

const creditTypeLabel = (type) => creditTypeMeta[type]?.label || type || '-'
const creditTypeTag = (type) => creditTypeMeta[type]?.tag || 'info'
const operationLabel = (op) => (op ? operationLabels[op] || op : '-')

const openCreditDialog = (row) => {
  creditUser.value = row
  creditMode.value = 'add'
  creditAmount.value = 10
  creditReason.value = ''
  creditDialogVisible.value = true
}

const saveCreditAdjust = async () => {
  const reason = creditReason.value.trim()
  if (!reason) {
    ElMessage.warning('请填写调整原因')
    return
  }
  const amount = Number(creditAmount.value) || 0
  if (creditMode.value !== 'set' && amount <= 0) {
    ElMessage.warning('调整数量必须大于 0')
    return
  }
  const payload = creditMode.value === 'set'
    ? { mode: 'set', amount, reason }
    : { mode: 'delta', amount: creditMode.value === 'deduct' ? -amount : amount, reason }

  savingCredit.value = true
  try {
    const res = await adjustUserCredits(creditUser.value.id, payload)
    ElMessage.success(`积分已调整，当前余额 ${res.data?.balance ?? '-'}`)
    creditDialogVisible.value = false
    fetchUsers()
  } catch {
    // handled by interceptor
  } finally {
    savingCredit.value = false
  }
}

const openRecordsDialog = async (row) => {
  recordsDialogVisible.value = true
  recordsLoading.value = true
  recordsAccount.value = null
  recordsList.value = []
  try {
    const res = await getUserCredits(row.id, { limit: 100 })
    recordsAccount.value = res.data?.account || null
    recordsList.value = res.data?.transactions || []
  } catch {
    // handled by interceptor
  } finally {
    recordsLoading.value = false
  }
}

const openDiagnosticsDialog = async (row) => {
  diagDialogVisible.value = true
  diagLoading.value = true
  diagUser.value = row
  diagData.value = {}
  diagTab.value = 'gen'
  try {
    const res = await getUserDiagnostics(row.id, { limit: 30 })
    diagData.value = res.data || {}
  } catch {
    // handled by interceptor
  } finally {
    diagLoading.value = false
  }
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await getAdminUsers({
      keyword: keyword.value || undefined,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    users.value = res.data.items
    total.value = res.data.total
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

const openProductDialog = (row) => {
  editingUser.value = row
  editingProducts.value = [...(row.product_access || [])]
  productDialogVisible.value = true
}

const saveProductAccess = async () => {
  if (!editingUser.value) return
  savingProducts.value = true
  try {
    await updateAdminUserProductAccess(editingUser.value.id, {
      product_access: editingProducts.value
    })
    ElMessage.success('产品权益已更新')
    productDialogVisible.value = false
    fetchUsers()
  } catch {
    // handled by interceptor
  } finally {
    savingProducts.value = false
  }
}

const toggleStatus = async (row) => {
  const action = row.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确定要${action}用户「${row.username}」吗？`,
      '确认',
      { type: 'warning' }
    )
    await updateAdminUserStatus(row.id, { is_active: !row.is_active })
    ElMessage.success(`${action}成功`)
    fetchUsers()
  } catch {
    // 用户取消或请求失败
  }
}

const formatDate = (iso) => {
  if (!iso) return '-'
  // 后端用户时间是无时区的北京时间；显式补上 +08:00，避免按浏览器本地时区误解析。
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso)
  const date = new Date(hasTimezone ? iso : `${iso}+08:00`)
  return date.toLocaleString('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'Asia/Shanghai'
  })
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
:deep(.diag-failed-row) {
  background: #fef2f2;
}
</style>
