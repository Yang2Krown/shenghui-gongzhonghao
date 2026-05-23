<template>
  <div class="creation-list">
    <!-- 页面标题和操作栏 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-h2 font-serif text-ink">我的创作</h1>
        <p class="text-ink-3 mt-1">管理您的所有创作内容</p>
      </div>
      <div class="flex space-x-3">
        <el-button @click="fetchCreations" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="createNewCreation">
          <el-icon><Plus /></el-icon>
          新建创作
        </el-button>
      </div>
    </div>


    <!-- 创作列表 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <div v-else-if="sortedCreations.length === 0" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">暂无创作</h3>
      <p class="text-ink-3 mt-1">点击"新建创作"开始您的第一篇内容</p>
      <el-button type="primary" class="mt-4" @click="createNewCreation">
        新建创作
      </el-button>
    </div>

    <!-- 网格视图 -->
    <div v-else-if="viewMode === 'grid'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="creation in sortedCreations"
        :key="creation.id"
        class="creation-card"
        @click="editCreation(creation)"
      >
        <div class="p-5">
          <!-- 顶部：状态 + 时间 -->
          <div class="flex items-center justify-between mb-3">
            <span :class="['c-status', `c-status-${creation.status || 'draft'}`]">
              {{ getStatusName(creation.status) }}
            </span>
            <span style="font-size: 12px; color: #9A968D;">
              {{ formatDate(creation.updated_at) }}
            </span>
          </div>

          <!-- 标题 -->
          <h3 class="font-serif" style="font-size: 18px; font-weight: 500; color: var(--ink); line-height: 1.4; margin-bottom: 8px;
                                        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
            {{ creation.title || '无标题' }}
          </h3>

          <!-- 摘要 / 正文片段 -->
          <p style="color: #6B6862; font-size: 13px; line-height: 1.7; margin-bottom: 14px;
                    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
            {{ creation.summary || getExcerpt(creation.content) || '暂无内容' }}
          </p>

          <!-- 标签：方向 + 自定义 tag -->
          <div class="flex flex-wrap gap-1.5 mb-3" v-if="creation.topic_direction || (creation.tags || []).length">
            <span v-if="creation.topic_direction" class="c-tag c-tag-direction">{{ creation.topic_direction }}</span>
            <span
              v-for="tag in (creation.tags || []).filter(t => t !== creation.topic_direction).slice(0, 3)"
              :key="tag"
              class="c-tag"
            >
              {{ tag }}
            </span>
          </div>

          <!-- 底部：字数 + 操作 -->
          <div class="flex items-center justify-between pt-3" style="border-top: 1px solid var(--line);">
            <span style="font-size: 12px; color: #9A968D;">
              {{ creation.word_count || 0 }} 字 · {{ formatTime(creation.created_at) }}
            </span>
            <div class="flex space-x-2">
              <el-button size="small" type="danger" plain @click.stop="deleteCreation(creation)">
                <el-icon><Delete /></el-icon>
              </el-button>
              <el-button size="small" @click.stop="continueCreation(creation)" style="background: var(--ink); color: var(--paper); border: none;">
                继续创作
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 列表视图 -->
    <div v-else class="card overflow-hidden">
      <el-table :data="sortedCreations" style="width: 100%">
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <div class="cursor-pointer" @click="editCreation(row)">
              <div class="font-medium text-ink">{{ row.title || '无标题' }}</div>
              <div class="text-sm text-ink-3 mt-1 line-clamp-1">
                {{ getExcerpt(row.content) || '暂无内容' }}
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <span :class="getStatusBadgeClass(row.status)">
              {{ getStatusName(row.status) }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="word_count" label="字数" width="80">
          <template #default="{ row }">
            {{ row.word_count || 0 }}
          </template>
        </el-table-column>
        
        <el-table-column prop="updated_at" label="更新时间" width="120">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editCreation(row)">
              查看
            </el-button>
            <el-button size="small" type="primary" @click="continueCreation(row)">
              继续创作
            </el-button>
            <el-button size="small" type="danger" plain @click="deleteCreation(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCreationStore } from '@/stores/creation'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Plus,
  Loading,
  Document,
  Delete,
  Edit
} from '@element-plus/icons-vue'

const router = useRouter()
const creationStore = useCreationStore()

// 状态
const loading = ref(false)
const viewMode = ref('grid')

// 计算属性
const creations = computed(() => creationStore.creations)

const sortedCreations = computed(() => {
  return [...creations.value].sort((a, b) => {
    const dateA = new Date(a.updated_at || a.created_at)
    const dateB = new Date(b.updated_at || b.created_at)
    return dateB - dateA
  })
})

// 生命周期
onMounted(() => {
  fetchCreations()
})

// 获取创作列表
const fetchCreations = async () => {
  loading.value = true

  try {
    await creationStore.fetchCreations({})
  } catch (error) {
    console.error('Fetch creations error:', error)
  } finally {
    loading.value = false
  }
}

// 创建新创作
const createNewCreation = () => {
  router.push('/topic-clusters')
}

// 查看草稿
const editCreation = (creation) => {
  router.push(`/creation/${creation.id}`)
}

// 继续创作（跳转到编辑器）
const continueCreation = (creation) => {
  router.push(`/creation/editor/${creation.id}`)
}

// 删除创作
const deleteCreation = async (creation) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除创作"${creation.title || '无标题'}"吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await creationStore.deleteCreation(creation.id)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete creation error:', error)
    }
  }
}

// 工具函数
const getStatusName = (status) => {
  const statusNames = {
    'draft': '草稿',
    'published': '已发布',
    'archived': '已归档'
  }
  return statusNames[status] || status
}

const getStatusBadgeClass = (status) => {
  const classes = {
    'draft': 'badge-warning',
    'published': 'badge-success',
    'archived': 'badge-info'
  }
  return classes[status] || 'badge-info'
}

const getExcerpt = (content) => {
  if (!content) return ''
  // 内容可能是 JSON（含 agent 数据），提取纯文本
  let text = content
  try {
    const parsed = JSON.parse(content)
    if (typeof parsed === 'object' && parsed.final_text) {
      text = parsed.final_text
    }
  } catch {}
  // 移除HTML标签
  text = text.replace(/<[^>]*>/g, '')
  return text.substring(0, 100) + (text.length > 100 ? '...' : '')
}

const formatDate = (dateString) => {
  if (!dateString) return ''

  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now - date)
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 1) {
    return '今天'
  } else if (diffDays === 2) {
    return '昨天'
  } else if (diffDays <= 7) {
    return `${diffDays - 1}天前`
  } else {
    return date.toLocaleDateString('zh-CN')
  }
}

const formatTime = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
</script>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 创作卡片（与话题库 cluster-card 同语言） */
.creation-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.24s cubic-bezier(.32, .72, 0, 1);
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}
.creation-card:hover {
  box-shadow: 0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  transform: translateY(-2px);
}

/* 状态徽标 */
.c-status {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}
.c-status-draft {
  background: var(--bone, #F0EDE3);
  color: #6B6862;
  border: 1px solid var(--line);
}
.c-status-published {
  background: #DAF0DC;
  color: #2A6B3A;
  border: 1px solid #A8D6B0;
}
.c-status-archived {
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}

/* tag chip */
.c-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}
.c-tag-direction {
  background: var(--pine-soft);
  color: var(--pine);
  border-color: var(--pine-soft);
}
</style>