<template>
  <div class="topic-list">
    <!-- 页面标题和操作栏 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-h2 font-serif text-ink">每日选题</h1>
        <p class="text-ink-3 mt-1">发现AI领域热点内容，获取创作灵感</p>
      </div>
      <div class="flex space-x-3">
        <el-button @click="refreshTopics" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
          刷新选题
        </el-button>
        <el-button type="primary" @click="showFilters = !showFilters">
          <el-icon><Filter /></el-icon>
          筛选
        </el-button>
      </div>
    </div>
    
    <!-- 筛选面板 -->
    <el-collapse-transition>
      <div v-show="showFilters" class="card p-4 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="label">平台筛选</label>
            <el-select v-model="filters.platform" placeholder="选择平台" clearable class="w-full">
              <el-option label="36氪" value="36kr" />
              <el-option label="量子位" value="qbitai" />
              <el-option label="机器之心" value="jiqizhixin" />
              <el-option label="IT之家" value="ithome" />
              <el-option label="虎嗅" value="huxiu" />
              <el-option label="TopHub" value="tophub" />
            </el-select>
          </div>
          
          <div>
            <label class="label">分类筛选</label>
            <el-select v-model="filters.category" placeholder="选择分类" clearable class="w-full">
              <el-option label="AI" value="AI" />
              <el-option label="机器学习" value="机器学习" />
              <el-option label="自然语言处理" value="自然语言处理" />
              <el-option label="计算机视觉" value="计算机视觉" />
              <el-option label="科技" value="科技" />
            </el-select>
          </div>
          
          <div>
            <label class="label">关键词搜索</label>
            <el-input v-model="filters.keyword" placeholder="输入关键词" clearable />
          </div>
          
          <div>
            <label class="label">排序方式</label>
            <el-select v-model="filters.sort_by" class="w-full">
              <el-option label="按发布时间" value="published_at" />
              <el-option label="按热度" value="heat_score" />
              <el-option label="按阅读量" value="read_count" />
            </el-select>
          </div>
        </div>
        
        <div class="flex justify-end mt-4">
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="primary" @click="applyFilters">应用筛选</el-button>
        </div>
      </div>
    </el-collapse-transition>
    
    <!-- 选题列表 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>
    
    <div v-else-if="topics.length === 0" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">暂无选题</h3>
      <p class="text-ink-3 mt-1">点击刷新按钮获取最新选题</p>
      <el-button type="primary" class="mt-4" @click="refreshTopics">
        刷新选题
      </el-button>
    </div>
    
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="topic in topics"
        :key="topic.id"
        class="card-hover cursor-pointer"
        @click="viewTopic(topic)"
      >
        <!-- 选题图片 -->
        <div v-if="topic.image_url" class="h-48 overflow-hidden">
          <img
            :src="topic.image_url"
            :alt="topic.title"
            class="w-full h-full object-cover"
          />
        </div>
        
        <!-- 选题内容 -->
        <div class="p-4">
          <!-- 平台标签 -->
          <div class="flex items-center justify-between mb-2">
            <span class="badge-info">
              {{ getPlatformName(topic.source_platform) }}
            </span>
            <div class="flex items-center space-x-2">
              <span class="text-sm text-ink-3">
                <el-icon><View /></el-icon>
                {{ topic.read_count || 0 }}
              </span>
              <span class="text-sm text-ink-3">
                <el-icon><Star /></el-icon>
                {{ topic.like_count || 0 }}
              </span>
            </div>
          </div>
          
          <!-- 选题标题 -->
          <h3 class="text-lg font-semibold text-ink mb-2 line-clamp-2">
            {{ topic.title }}
          </h3>
          
          <!-- 选题摘要 -->
          <p class="text-ink-3 text-sm mb-4 line-clamp-3">
            {{ topic.content_summary || '暂无摘要' }}
          </p>
          
          <!-- 关键词 -->
          <div class="flex flex-wrap gap-1 mb-4">
            <span
              v-for="keyword in (topic.keywords || []).slice(0, 3)"
              :key="keyword"
              class="badge-primary text-xs"
            >
              {{ keyword }}
            </span>
          </div>
          
          <!-- 底部信息 -->
          <div class="flex items-center justify-between">
            <span class="text-sm text-ink-3">
              {{ formatDate(topic.published_at) }}
            </span>
            
            <div class="flex space-x-2">
              <el-button
                size="small"
                :type="topic.is_collected ? 'warning' : 'default'"
                @click.stop="toggleCollect(topic)"
              >
                <el-icon><Star /></el-icon>
                {{ topic.is_collected ? '已收藏' : '收藏' }}
              </el-button>
              
              <el-button
                size="small"
                type="primary"
                @click.stop="createCreation(topic)"
              >
                <el-icon><Edit /></el-icon>
                创作
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 分页 -->
    <div v-if="topics.length > 0" class="flex justify-center mt-8">
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
import { useTopicStore } from '@/stores/topic'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Filter,
  Loading,
  Document,
  View,
  Star,
  Edit
} from '@element-plus/icons-vue'

const router = useRouter()
const topicStore = useTopicStore()
const userStore = useUserStore()

// 状态
const loading = ref(false)
const refreshing = ref(false)
const showFilters = ref(false)

// 筛选条件
const filters = reactive({
  platform: '',
  category: '',
  keyword: '',
  sort_by: 'published_at',
  sort_order: 'desc'
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 12,
  total: 0
})

// 计算属性
const topics = computed(() => topicStore.topics)

// 生命周期
onMounted(() => {
  loadTopics()
})

// 加载选题列表
const loadTopics = async () => {
  loading.value = true
  
  try {
    await topicStore.fetchTopics({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    })
    
    pagination.total = topicStore.totalTopics
  } catch (error) {
    ElMessage.error('加载选题失败')
    console.error('Load topics error:', error)
  } finally {
    loading.value = false
  }
}

// 刷新选题
const refreshTopics = async () => {
  refreshing.value = true
  
  try {
    await topicStore.refreshTopics()
    ElMessage.success('选题刷新成功')
    await loadTopics()
  } catch (error) {
    ElMessage.error('选题刷新失败')
    console.error('Refresh topics error:', error)
  } finally {
    refreshing.value = false
  }
}

// 查看选题详情
const viewTopic = (topic) => {
  router.push(`/topics/${topic.id}`)
}

// 收藏/取消收藏
const toggleCollect = async (topic) => {
  if (!userStore.isAuthenticated) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return
  }
  
  try {
    if (topic.is_collected) {
      await topicStore.uncollectTopic(topic.id)
      topic.is_collected = false
      ElMessage.success('取消收藏成功')
    } else {
      await topicStore.collectTopic(topic.id)
      topic.is_collected = true
      ElMessage.success('收藏成功')
    }
  } catch (error) {
    ElMessage.error('操作失败')
    console.error('Toggle collect error:', error)
  }
}

// 创建创作
const createCreation = (topic) => {
  if (!userStore.isAuthenticated) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return
  }
  
  router.push({
    path: '/creation/new',
    query: {
      topic_id: topic.id,
      topic_title: topic.title,
      topic_summary: topic.content_summary
    }
  })
}

// 应用筛选
const applyFilters = () => {
  pagination.page = 1
  loadTopics()
}

// 重置筛选
const resetFilters = () => {
  filters.platform = ''
  filters.category = ''
  filters.keyword = ''
  filters.sort_by = 'published_at'
  filters.sort_order = 'desc'
  pagination.page = 1
  loadTopics()
}

// 分页处理
const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.page = 1
  loadTopics()
}

const handleCurrentChange = (val) => {
  pagination.page = val
  loadTopics()
}

// 工具函数
const getPlatformName = (platform) => {
  const platformNames = {
    '36kr': '36氪',
    'qbitai': '量子位',
    'jiqizhixin': '机器之心',
    'ithome': 'IT之家',
    'huxiu': '虎嗅',
    'tophub': 'TopHub'
  }
  return platformNames[platform] || platform
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
</style>