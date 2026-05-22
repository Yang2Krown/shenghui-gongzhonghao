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

    <!-- 筛选和排序 -->
    <div class="card p-4 mb-6">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex-1 min-w-[200px]">
          <el-input
            v-model="searchQuery"
            placeholder="搜索创作标题或内容..."
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <div>
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="handleFilter">
            <el-option label="全部" value="" />
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </div>
        
        <div>
          <el-select v-model="sortBy" placeholder="排序方式" @change="handleSort">
            <el-option label="最近更新" value="updated_at" />
            <el-option label="创建时间" value="created_at" />
            <el-option label="标题" value="title" />
          </el-select>
        </div>
        
        <div>
          <el-button-group>
            <el-button :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'">
              <el-icon><Grid /></el-icon>
            </el-button>
            <el-button :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'">
              <el-icon><List /></el-icon>
            </el-button>
          </el-button-group>
        </div>
      </div>
    </div>

    <!-- 创作列表 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <div v-else-if="filteredCreations.length === 0" class="text-center py-20">
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
        v-for="creation in filteredCreations"
        :key="creation.id"
        class="card-hover cursor-pointer"
        @click="editCreation(creation)"
      >
        <div class="p-4">
          <!-- 状态标签 -->
          <div class="flex items-center justify-between mb-3">
            <span :class="getStatusBadgeClass(creation.status)">
              {{ getStatusName(creation.status) }}
            </span>
            <span class="text-sm text-gray-500">
              {{ formatDate(creation.updated_at) }}
            </span>
          </div>
          
          <!-- 标题 -->
          <h3 class="text-lg font-semibold text-ink mb-2 line-clamp-2">
            {{ creation.title || '无标题' }}
          </h3>
          
          <!-- 摘要 -->
          <p class="text-ink-3 text-sm mb-4 line-clamp-3">
            {{ getExcerpt(creation.content) || '暂无内容' }}
          </p>
          
          <!-- 创作进度 -->
          <div class="creation-progress mb-3">
            <span class="progress-step" :class="getProgressClass(creation.outline_status)">
              <span class="step-dot"></span>
              大纲
            </span>
            <span class="progress-arrow">→</span>
            <span class="progress-step" :class="getProgressClass(creation.title_status)">
              <span class="step-dot"></span>
              标题
            </span>
            <span class="progress-arrow">→</span>
            <span class="progress-step" :class="getProgressClass(creation.content_status)">
              <span class="step-dot"></span>
              正文
            </span>
          </div>

          <!-- 标签 -->
          <div class="flex flex-wrap gap-1 mb-3">
            <span v-if="creation.topic_direction" class="badge-info text-xs">
              {{ creation.topic_direction }}
            </span>
            <span
              v-for="tag in (creation.tags || []).slice(0, 2)"
              :key="tag"
              class="badge-primary text-xs"
            >
              {{ tag }}
            </span>
          </div>
          
          <!-- 底部操作 -->
          <div class="flex items-center justify-between pt-3 border-t border-line">
            <span class="text-sm text-ink-3">
              {{ creation.word_count || 0 }} 字
            </span>
            
            <div class="flex space-x-2">
              <el-button
                size="small"
                type="danger"
                plain
                @click.stop="deleteCreation(creation)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
              
              <el-button
                size="small"
                type="primary"
                @click.stop="editCreation(creation)"
              >
                <el-icon><Edit /></el-icon>
                继续创作
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 列表视图 -->
    <div v-else class="card overflow-hidden">
      <el-table :data="filteredCreations" style="width: 100%">
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
            <el-button size="small" type="primary" @click="editCreation(row)">
              编辑
            </el-button>
            <el-button size="small" type="danger" plain @click="deleteCreation(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div v-if="filteredCreations.length > 0" class="flex justify-center mt-8">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[12, 24, 36, 48]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCreationStore } from '@/stores/creation'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Plus,
  Search,
  Grid,
  List,
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
const searchQuery = ref('')
const statusFilter = ref('')
const sortBy = ref('updated_at')

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 12,
  total: 0
})

// 计算属性
const creations = computed(() => creationStore.creations)

const filteredCreations = computed(() => {
  let filtered = [...creations.value]
  
  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(creation => 
      (creation.title && creation.title.toLowerCase().includes(query)) ||
      (creation.content && creation.content.toLowerCase().includes(query))
    )
  }
  
  // 状态过滤
  if (statusFilter.value) {
    filtered = filtered.filter(creation => creation.status === statusFilter.value)
  }
  
  // 排序
  filtered.sort((a, b) => {
    if (sortBy.value === 'title') {
      return (a.title || '').localeCompare(b.title || '')
    }
    const dateA = new Date(a[sortBy.value] || a.created_at)
    const dateB = new Date(b[sortBy.value] || b.created_at)
    return dateB - dateA
  })
  
  return filtered
})

// 生命周期
onMounted(() => {
  fetchCreations()
})

// 获取创作列表
const fetchCreations = async () => {
  loading.value = true
  
  try {
    await creationStore.fetchCreations({
      page: pagination.page,
      page_size: pagination.pageSize
    })
    
    pagination.total = creationStore.totalCreations
  } catch (error) {
    console.error('Fetch creations error:', error)
  } finally {
    loading.value = false
  }
}

// 创建新创作
const createNewCreation = () => {
  router.push('/creation/new')
}

// 编辑创作
const editCreation = (creation) => {
  router.push(`/creation/${creation.id}`)
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

// 搜索处理
const handleSearch = () => {
  pagination.page = 1
}

// 筛选处理
const handleFilter = () => {
  pagination.page = 1
}

// 排序处理
const handleSort = () => {
  pagination.page = 1
}

// 分页处理
const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.page = 1
  fetchCreations()
}

const handleCurrentChange = (val) => {
  pagination.page = val
  fetchCreations()
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
  // 移除HTML标签
  const text = content.replace(/<[^>]*>/g, '')
  return text.substring(0, 100) + (text.length > 100 ? '...' : '')
}

const getProgressClass = (status) => {
  if (status === 'completed') return 'step-done'
  if (status === 'generating') return 'step-active'
  if (status === 'failed') return 'step-failed'
  return 'step-pending'
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

.creation-progress {
  display: flex;
  align-items: center;
  gap: 6px;
}

.progress-step {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}

.step-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.step-done .step-dot {
  background: var(--leaf);
}

.step-done {
  color: var(--leaf);
}

.step-active .step-dot {
  background: var(--clay);
  animation: pulse 1.5s ease-in-out infinite;
}

.step-active {
  color: var(--clay);
}

.step-failed .step-dot {
  background: var(--crimson);
}

.step-failed {
  color: var(--crimson);
}

.step-pending .step-dot {
  background: var(--line);
}

.step-pending {
  color: var(--ink-4);
}

.progress-arrow {
  color: var(--ink-4);
  font-size: 10px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>