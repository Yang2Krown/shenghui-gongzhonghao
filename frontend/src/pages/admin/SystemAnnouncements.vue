<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <div><h1 class="text-2xl font-bold">系统公告</h1><p class="text-sm text-slate-500 mt-1">发布后，已登录用户将在登录时看到弹窗；选择“不再提示”后不再展示。</p></div>
      <el-button type="primary" @click="openCreate">发布公告</el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="content" label="内容" min-width="280" show-overflow-tooltip />
      <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="statusType(row)">{{ statusText(row) }}</el-tag></template></el-table-column>
      <el-table-column label="到期时间" width="180"><template #default="{ row }">{{ formatDate(row.expires_at) }}</template></el-table-column>
      <el-table-column label="发布时间" width="180"><template #default="{ row }">{{ formatDate(row.published_at) }}</template></el-table-column>
      <el-table-column label="操作" width="180" fixed="right"><template #default="{ row }"><el-button size="small" @click="openEdit(row)">编辑</el-button><el-button v-if="row.is_published" size="small" type="danger" plain @click="stop(row)">停止提示</el-button></template></el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑系统公告' : '发布系统公告'" width="560px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top"><el-form-item label="标题" required><el-input v-model="form.title" maxlength="120" show-word-limit /></el-form-item><el-form-item label="公告内容" required><el-input v-model="form.content" type="textarea" :rows="6" maxlength="10000" show-word-limit /></el-form-item><el-form-item label="提示到期时间" required><el-date-picker v-model="form.expires_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" style="width: 100%" /></el-form-item></el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">{{ editing ? '保存' : '立即发布' }}</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createSystemAnnouncement, getSystemAnnouncements, updateSystemAnnouncement } from '@/api/admin'

const items = ref([]); const loading = ref(false); const dialogVisible = ref(false); const saving = ref(false); const editing = ref(null)
const form = ref({ title: '', content: '', expires_at: '' })
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' }) : '-'
const isExpired = (row) => new Date(row.expires_at) <= new Date()
const statusText = (row) => !row.is_published ? '已停止' : isExpired(row) ? '已过期' : '提示中'
const statusType = (row) => !row.is_published ? 'info' : isExpired(row) ? 'warning' : 'success'
const fetchItems = async () => { loading.value = true; try { items.value = (await getSystemAnnouncements()).data.items || [] } finally { loading.value = false } }
const openCreate = () => { editing.value = null; form.value = { title: '', content: '', expires_at: '' }; dialogVisible.value = true }
const openEdit = (row) => { editing.value = row; form.value = { title: row.title, content: row.content, expires_at: row.expires_at?.slice(0, 19) || '' }; dialogVisible.value = true }
const save = async () => { if (!form.value.title.trim() || !form.value.content.trim() || !form.value.expires_at) return ElMessage.warning('请完整填写公告内容和到期时间'); saving.value = true; try { if (editing.value) await updateSystemAnnouncement(editing.value.id, form.value); else await createSystemAnnouncement(form.value); ElMessage.success(editing.value ? '公告已更新' : '公告已发布'); dialogVisible.value = false; fetchItems() } finally { saving.value = false } }
const stop = async (row) => { try { await ElMessageBox.confirm(`停止后用户将不再看到「${row.title}」，确定继续吗？`, '停止公告', { type: 'warning' }); await updateSystemAnnouncement(row.id, { is_published: false }); ElMessage.success('已停止提示'); fetchItems() } catch {} }
onMounted(fetchItems)
</script>
