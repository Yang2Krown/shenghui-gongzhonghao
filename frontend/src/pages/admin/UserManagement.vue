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
      <el-table-column label="会员" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_member ? 'success' : 'info'" size="small" effect="plain">
            {{ row.is_member ? '会员' : '非会员' }}
          </el-tag>
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
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            :type="row.is_member ? 'warning' : 'success'"
            @click="toggleMembership(row)"
            :disabled="row.is_superuser"
          >
            {{ row.is_member ? '取消会员' : '设为会员' }}
          </el-button>
          <el-button
            size="small"
            :type="row.is_active ? 'danger' : 'primary'"
            @click="toggleStatus(row)"
            :disabled="row.is_superuser"
            plain
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

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
import { getAdminUsers, updateAdminUserMembership, updateAdminUserStatus } from '@/api/admin'

const users = ref([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

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

const toggleMembership = async (row) => {
  const action = row.is_member ? '取消会员' : '设为会员'
  try {
    await ElMessageBox.confirm(
      `确定要${action}「${row.username}」吗？`,
      '确认',
      { type: 'warning' }
    )
    await updateAdminUserMembership(row.id, { is_member: !row.is_member })
    ElMessage.success(`${action}成功`)
    fetchUsers()
  } catch {
    // 用户取消或请求失败
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
