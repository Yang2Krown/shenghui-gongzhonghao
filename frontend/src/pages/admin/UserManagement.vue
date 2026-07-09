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
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
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
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminUsers, updateAdminUserProductAccess, updateAdminUserStatus } from '@/api/admin'
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
  practical_camp: '实战营'
}
const productOptions = Object.entries(productLabels).map(([value, label]) => ({ value, label }))

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
  return new Date(iso).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

onMounted(() => {
  fetchUsers()
})
</script>
