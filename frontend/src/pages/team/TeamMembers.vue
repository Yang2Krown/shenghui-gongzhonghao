<template>
  <div class="team-page">
    <div class="team-head">
      <div>
        <div class="kicker">TEAM</div>
        <h1>团队管理</h1>
        <p class="team-sub">员工默认拥有全部产品权限；与管理员唯一的区别是看不到「后台管理」</p>
      </div>
      <el-button v-if="userStore.isAdmin" type="primary" @click="openAddDialog">
        + 添加员工
      </el-button>
    </div>

    <div class="team-grid">
      <div class="card member-card">
        <div class="card-head">
          <div>
            <h3>团队成员</h3>
            <span class="muted">{{ members.length }} 人</span>
          </div>
          <el-input
            v-model="keyword"
            placeholder="搜索姓名 / 用户名 / 手机号"
            clearable
            style="width: 240px"
            @input="loadMembers"
          />
        </div>
        <el-table :data="members" v-loading="loading" class="member-table">
          <el-table-column label="成员" min-width="200">
            <template #default="{ row }">
              <div class="member-cell">
                <el-avatar :size="30" :src="row.avatar_url || ''">
                  {{ (row.full_name || row.username || '?').charAt(0).toUpperCase() }}
                </el-avatar>
                <div>
                  <div class="member-name">{{ row.full_name || row.username }}</div>
                  <div class="member-uname">@{{ row.username }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="角色" width="110">
            <template #default="{ row }">
              <el-tag :type="roleTagType(row)" size="small">{{ roleLabel(row) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="部门 / 岗位" min-width="150">
            <template #default="{ row }">
              <span class="muted">{{ row.department || '—' }} / {{ row.position || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                {{ row.is_active ? '在职' : '已禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="入职" width="110">
            <template #default="{ row }">
              <span class="muted">{{ fmtDate(row.joined_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="userStore.isAdmin" label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <template v-if="row.role === 'employee' && !row.is_superuser">
                <el-button text size="small" @click="openEditDialog(row)">编辑</el-button>
                <el-button text type="danger" size="small" @click="removeEmployee(row)">移除员工</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="side-col">
        <div class="card note-card">
          <h3>角色说明</h3>
          <div class="note-item">
            <b>员工</b>
            <span>默认拥有全部产品权限（创作工具 / 潜在商单 / 实战营 / 小红书选题），但看不到「后台管理」。</span>
          </div>
          <div class="note-item">
            <b>用户</b>
            <span>权益保持不变，仅可使用已开通产品，不进入团队模块。</span>
          </div>
          <div class="note-item">
            <b>管理员</b>
            <span>可在「添加员工」里直接给任意用户赋予员工角色。</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加员工（管理员直接赋予角色） -->
    <el-dialog v-model="addVisible" title="添加员工" width="560px" align-center class="team-dialog" :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="restoreDialogScroll">
      <p class="dialog-tip">搜索用户并直接赋予「员工」角色，无需邀请码；员工自动获得全部产品权限。</p>
      <div class="candidate-search">
        <el-input
          v-model="searchKeyword"
          placeholder="输入手机号 / 用户名 / 姓名"
          clearable
          @keyup.enter="searchCandidates"
          @clear="candidates = []"
        >
          <template #append>
            <el-button @click="searchCandidates">搜索</el-button>
          </template>
        </el-input>
      </div>
      <div v-if="searching" class="empty-note">搜索中…</div>
      <div v-else-if="candidates.length === 0 && searched" class="empty-note">未找到匹配用户，请确认对方已用手机号登录过系统。</div>
      <div v-else class="candidate-list">
        <div v-for="u in candidates" :key="u.user_id" class="candidate-row">
          <div class="member-cell">
            <el-avatar :size="30">{{ (u.full_name || u.username || '?').charAt(0).toUpperCase() }}</el-avatar>
            <div>
              <div class="member-name">{{ u.full_name || u.username }}</div>
              <div class="member-uname">@{{ u.username }} · {{ u.phone_masked || '—' }}</div>
            </div>
          </div>
          <el-tag v-if="u.role === 'employee'" type="success" size="small">已是员工</el-tag>
          <el-button
            v-else-if="!u.is_superuser"
            type="primary"
            size="small"
            :loading="assigningUserId === u.user_id"
            @click="assignEmployee(u)"
          >
            设为员工
          </el-button>
          <el-tag v-else size="small">最高管理员</el-tag>
        </div>
      </div>
    </el-dialog>

    <!-- 编辑员工档案 -->
    <el-dialog v-model="editVisible" title="编辑员工档案" width="480px" align-center class="team-dialog" :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="restoreDialogScroll">
      <el-form :model="editForm" label-position="top">
        <el-form-item label="部门">
          <el-input v-model="editForm.department" placeholder="如：内容组 / 商务组 / 技术组" />
        </el-form-item>
        <el-form-item label="岗位">
          <el-input v-model="editForm.position" placeholder="如：编辑 / 运营" />
        </el-form-item>
        <el-form-item label="工号">
          <el-input v-model="editForm.employee_no" placeholder="选填" />
        </el-form-item>
        <el-form-item label="入职日期">
          <el-date-picker v-model="editForm.joined_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="在职" value="active" />
            <el-option label="已离职" value="left" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveMember">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import {
  listTeamMembers,
  searchTeamCandidates,
  updateMemberRole,
  updateTeamMember
} from '@/api/team'
import { useDialogScrollPosition } from '@/utils/dialogScrollPosition'

const userStore = useUserStore()
const { rememberDialogScroll, restoreDialogScroll } = useDialogScrollPosition()

const members = ref([])
const loading = ref(false)
const keyword = ref('')

const addVisible = ref(false)
const searchKeyword = ref('')
const candidates = ref([])
const searched = ref(false)
const searching = ref(false)
const assigningUserId = ref(null)

const editVisible = ref(false)
const editForm = ref({ user_id: null, department: '', position: '', employee_no: '', joined_at: '', status: 'active' })
const saving = ref(false)

const roleLabel = (row) => {
  if (row.is_superuser) return '最高管理员'
  const map = { admin: '管理员', employee: '员工', user: '普通用户' }
  return map[row.role] || row.role || '普通用户'
}

const roleTagType = (row) => {
  if (row.is_superuser) return 'danger'
  if (row.role === 'admin') return 'warning'
  if (row.role === 'employee') return 'success'
  return 'info'
}

const fmtDate = (v) => (v ? String(v).slice(0, 10) : '—')

const loadMembers = async () => {
  loading.value = true
  try {
    const resp = await listTeamMembers({ keyword: keyword.value || undefined })
    members.value = resp.data?.items || []
  } finally {
    loading.value = false
  }
}

const openAddDialog = () => {
  addVisible.value = true
  searchKeyword.value = ''
  candidates.value = []
  searched.value = false
}

const searchCandidates = async () => {
  const kw = searchKeyword.value.trim()
  if (!kw) {
    ElMessage.warning('请输入手机号 / 用户名 / 姓名')
    return
  }
  searching.value = true
  searched.value = true
  try {
    const resp = await searchTeamCandidates(kw)
    candidates.value = resp.data?.items || []
  } finally {
    searching.value = false
  }
}

const assignEmployee = async (u) => {
  assigningUserId.value = u.user_id
  try {
    await updateMemberRole(u.user_id, 'employee')
    ElMessage.success(`已将 ${u.full_name || u.username} 设为员工`)
    u.role = 'employee'
    await loadMembers()
  } finally {
    assigningUserId.value = null
  }
}

const removeEmployee = async (row) => {
  try {
    await ElMessageBox.confirm(
      `移除后 ${row.full_name || row.username} 将失去员工身份（产品权限回到个人已开通状态），确定继续？`,
      '移除员工',
      { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消', lockScroll: false }
    )
  } catch {
    return
  }
  await updateMemberRole(row.user_id, 'user')
  ElMessage.success('已移除员工身份')
  await loadMembers()
}

const openEditDialog = (row) => {
  editForm.value = {
    user_id: row.user_id,
    department: row.department || '',
    position: row.position || '',
    employee_no: row.employee_no || '',
    joined_at: row.joined_at || '',
    status: row.employee_status || 'active'
  }
  editVisible.value = true
}

const saveMember = async () => {
  saving.value = true
  try {
    await updateTeamMember(editForm.value.user_id, {
      department: editForm.value.department || undefined,
      position: editForm.value.position || undefined,
      employee_no: editForm.value.employee_no || undefined,
      joined_at: editForm.value.joined_at || undefined,
      status: editForm.value.status
    })
    ElMessage.success('员工档案已更新')
    editVisible.value = false
    await loadMembers()
  } finally {
    saving.value = false
  }
}

onMounted(loadMembers)
</script>

<style scoped>
.team-page {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  color: var(--ink);
}
.team-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
}
.kicker {
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--clay-deep, #a85a40);
  font-weight: 700;
}
.team-head h1 {
  font-family: var(--serif, 'Songti SC', serif);
  font-size: 30px;
  margin: 4px 0 6px;
}
.team-sub {
  color: var(--ink-3, #6b6862);
  font-size: 13.5px;
  margin: 0;
}
.team-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 14px;
  align-items: start;
}
.card {
  background: var(--paper, #faf9f5);
  border: 1px solid var(--line, #e4ddce);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31, 31, 30, 0.04);
  overflow: hidden;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--line, #e4ddce);
}
.card-head h3 {
  font-size: 16px;
  margin: 0;
}
.muted {
  color: var(--ink-4, #9a968d);
  font-size: 12px;
}
.member-table {
  width: 100%;
}
.member-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.member-name {
  font-weight: 650;
  font-size: 13.5px;
}
.member-uname {
  font-size: 11px;
  color: var(--ink-4, #9a968d);
}
.side-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.note-card {
  padding: 18px;
}
.note-card h3 {
  margin: 0 0 12px;
  font-size: 15px;
}
.note-item {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
  color: var(--ink-3, #6b6862);
  padding: 10px 0;
  border-bottom: 1px dashed var(--line, #e4ddce);
}
.note-item:last-child {
  border-bottom: 0;
}
.note-item b {
  color: var(--ink-2, #3a3935);
  flex-shrink: 0;
}
.dialog-tip {
  color: var(--ink-3, #6b6862);
  font-size: 13px;
  margin: 0 0 14px;
}
.candidate-search {
  margin-bottom: 12px;
}
.candidate-list {
  display: flex;
  flex-direction: column;
  max-height: 320px;
  overflow-y: auto;
}
.candidate-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px dashed var(--line, #e4ddce);
}
.candidate-row:last-child {
  border-bottom: 0;
}
.empty-note {
  color: var(--ink-4, #9a968d);
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
@media (max-width: 1000px) {
  .team-grid {
    grid-template-columns: 1fr;
  }
}
</style>
