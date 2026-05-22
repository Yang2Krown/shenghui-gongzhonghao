<template>
  <div class="topic-detail">
    <!-- 返回按钮 -->
    <div class="mb-6">
      <el-button @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回选题列表
      </el-button>
    </div>
    
    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>
    
    <!-- 选题详情 -->
    <div v-else-if="topic" class="max-w-4xl mx-auto">
      <!-- 头部信息 -->
      <div class="card p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <span class="badge-info">
            {{ getPlatformName(topic.source_platform) }}
          </span>
          
          <div class="flex items-center space-x-4">
            <span class="text-sm text-ink-3">
              <el-icon><View /></el-icon>
              {{ topic.read_count || 0 }} 阅读
            </span>
            <span class="text-sm text-ink-3">
              <el-icon><Star /></el-icon>
              {{ topic.like_count || 0 }} 点赞
            </span>
            <span class="text-sm text-ink-3">
              <el-icon><ChatDotRound /></el-icon>
              {{ topic.comment_count || 0 }} 评论
            </span>
          </div>
        </div>
        
        <h1 class="text-3xl font-bold text-ink mb-4">
          {{ topic.title }}
        </h1>
        
        <div class="flex items-center space-x-4 text-sm text-ink-3 mb-6">
          <span v-if="topic.author">
            <el-icon><User /></el-icon>
            {{ topic.author }}
          </span>
          <span>
            <el-icon><Calendar /></el-icon>
            {{ formatDate(topic.published_at) }}
          </span>
          <span>
            <el-icon><Link /></el-icon>
            <a :href="topic.source_url" target="_blank" class="text-clay-deep hover:underline">
              查看原文
            </a>
          </span>
        </div>
        
        <!-- 关键词 -->
        <div v-if="topic.keywords && topic.keywords.length > 0" class="flex flex-wrap gap-2 mb-6">
          <span
            v-for="keyword in topic.keywords"
            :key="keyword"
            class="badge-primary"
          >
            {{ keyword }}
          </span>
        </div>
        
        <!-- 操作按钮 -->
        <div class="flex space-x-3">
          <el-button
            :type="topic.is_collected ? 'warning' : 'primary'"
            @click="toggleCollect"
          >
            <el-icon><Star /></el-icon>
            {{ topic.is_collected ? '取消收藏' : '收藏选题' }}
          </el-button>
          
          <el-button type="primary" @click="createCreation">
            <el-icon><Edit /></el-icon>
            基于此选题创作
          </el-button>
          
          <el-button @click="copyLink">
            <el-icon><CopyDocument /></el-icon>
            复制链接
          </el-button>
        </div>
      </div>
      
      <!-- 内容摘要 -->
      <div class="card p-6 mb-6">
        <h2 class="text-xl font-semibold text-ink mb-4">内容摘要</h2>
        <div class="prose max-w-none">
          <p class="text-ink-2 leading-relaxed">
            {{ topic.content_summary || '暂无摘要' }}
          </p>
        </div>
      </div>
      
      <!-- 热度分析 -->
      <div class="card p-6 mb-6">
        <h2 class="text-xl font-semibold text-ink mb-4">热度分析</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="text-center">
            <div class="text-3xl font-bold text-clay">
              {{ topic.heat_score || 0 }}
            </div>
            <div class="text-sm text-ink-3 mt-1">热度分数</div>
            <div class="w-full bg-bone rounded-full h-2 mt-2">
              <div
                class="bg-clay h-2 rounded-full"
                :style="{ width: `${Math.min(100, (topic.heat_score || 0))}%` }"
              ></div>
            </div>
          </div>
          
          <div class="text-center">
            <div class="text-3xl font-bold text-leaf">
              {{ topic.read_count || 0 }}
            </div>
            <div class="text-sm text-ink-3 mt-1">阅读量</div>
          </div>
          
          <div class="text-center">
            <div class="text-3xl font-bold text-sand">
              {{ topic.like_count || 0 }}
            </div>
            <div class="text-sm text-ink-3 mt-1">点赞数</div>
          </div>
        </div>
      </div>
      
      <!-- 相关选题 -->
      <div class="card p-6">
        <h2 class="text-xl font-semibold text-ink mb-4">相关选题</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="relatedTopic in relatedTopics"
            :key="relatedTopic.id"
            class="flex items-start space-x-3 p-3 rounded-lg hover:bg-bone cursor-pointer"
            @click="viewTopic(relatedTopic)"
          >
            <div class="flex-shrink-0 w-10 h-10 bg-clay-tint rounded-lg flex items-center justify-center">
              <span class="text-clay font-semibold text-sm">
                {{ relatedTopic.title.charAt(0) }}
              </span>
            </div>
            <div class="flex-1 min-w-0">
              <h4 class="text-sm font-medium text-ink line-clamp-2">
                {{ relatedTopic.title }}
              </h4>
              <p class="text-xs text-ink-3 mt-1">
                {{ getPlatformName(relatedTopic.source_platform) }} · {{ formatDate(relatedTopic.published_at) }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 未找到选题 -->
    <div v-else class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-lg font-medium text-ink mt-4">选题不存在</h3>
      <p class="text-ink-3 mt-1">该选题可能已被删除或不存在</p>
      <el-button type="primary" class="mt-4" @click="$router.push('/topics')">
        返回选题列表
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTopicStore } from '@/stores/topic'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  Loading,
  View,
  Star,
  ChatDotRound,
  User,
  Calendar,
  Link,
  Edit,
  CopyDocument,
  Document
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const topicStore = useTopicStore()
const userStore = useUserStore()

// 状态
const loading = ref(false)
const topic = ref(null)
const relatedTopics = ref([])

// 生命周期
onMounted(() => {
  loadTopic()
})

// 监听路由变化
watch(() => route.params.id, () => {
  loadTopic()
})

// 加载选题详情
const loadTopic = async () => {
  const topicId = route.params.id
  if (!topicId) return
  
  loading.value = true
  
  try {
    await topicStore.fetchTopic(topicId)
    topic.value = topicStore.currentTopic
    
    // 加载相关选题
    if (topic.value) {
      await loadRelatedTopics()
    }
  } catch (error) {
    ElMessage.error('加载选题详情失败')
    console.error('Load topic error:', error)
  } finally {
    loading.value = false
  }
}

// 加载相关选题
const loadRelatedTopics = async () => {
  try {
    // 这里应该调用API获取相关选题
    // 暂时使用模拟数据
    relatedTopics.value = [
      {
        id: 1,
        title: 'AI技术最新突破：多模态模型取得重大进展',
        source_platform: '36kr',
        published_at: new Date().toISOString()
      },
      {
        id: 2,
        title: '深度学习在自然语言处理中的应用前景',
        source_platform: 'jiqizhixin',
        published_at: new Date().toISOString()
      }
    ]
  } catch (error) {
    console.error('Load related topics error:', error)
  }
}

// 收藏/取消收藏
const toggleCollect = async () => {
  if (!userStore.isAuthenticated) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return
  }
  
  try {
    if (topic.value.is_collected) {
      await topicStore.uncollectTopic(topic.value.id)
      topic.value.is_collected = false
      ElMessage.success('取消收藏成功')
    } else {
      await topicStore.collectTopic(topic.value.id)
      topic.value.is_collected = true
      ElMessage.success('收藏成功')
    }
  } catch (error) {
    ElMessage.error('操作失败')
    console.error('Toggle collect error:', error)
  }
}

// 创建创作
const createCreation = () => {
  if (!userStore.isAuthenticated) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return
  }
  
  router.push({
    path: '/creation/new',
    query: {
      topic_id: topic.value.id,
      topic_title: topic.value.title,
      topic_summary: topic.value.content_summary
    }
  })
}

// 复制链接
const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(window.location.href)
    ElMessage.success('链接已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
    console.error('Copy link error:', error)
  }
}

// 查看其他选题
const viewTopic = (topic) => {
  router.push(`/topics/${topic.id}`)
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
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.prose {
  max-width: none;
}

.prose p {
  margin-bottom: 1rem;
  line-height: 1.75;
}
</style>