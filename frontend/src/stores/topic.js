import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getTopics, getTopicById, collectTopic as collectTopicApi, uncollectTopic as uncollectTopicApi, refreshTopics as refreshTopicsApi } from '@/api/topic'
import { ElMessage } from 'element-plus'

export const useTopicStore = defineStore('topic', () => {
  // 状态
  const topics = ref([])
  const currentTopic = ref(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const totalTopics = ref(0)
  const filters = ref({
    platform: '',
    category: '',
    keyword: '',
    sort_by: 'published_at',
    sort_order: 'desc'
  })

  // 计算属性
  const hasTopics = computed(() => topics.value.length > 0)
  const collectedTopics = computed(() => topics.value.filter(t => t.is_collected))

  // 获取选题列表
  const fetchTopics = async (params = {}) => {
    loading.value = true
    try {
      const queryParams = {
        ...filters.value,
        ...params
      }
      
      const response = await getTopics(queryParams)
      const { items, total } = response.data
      
      topics.value = items || []
      totalTopics.value = total || 0
      
      return { items, total }
    } catch (error) {
      ElMessage.error('获取选题列表失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 获取选题详情
  const fetchTopicById = async (id) => {
    loading.value = true
    try {
      const response = await getTopicById(id)
      currentTopic.value = response.data
      return response.data
    } catch (error) {
      ElMessage.error('获取选题详情失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 收藏选题
  const collectTopic = async (topicId) => {
    try {
      await collectTopicApi(topicId)
      
      // 更新本地状态
      const topic = topics.value.find(t => t.id === topicId)
      if (topic) {
        topic.is_collected = true
      }
      
      if (currentTopic.value?.id === topicId) {
        currentTopic.value.is_collected = true
      }
      
      return true
    } catch (error) {
      ElMessage.error('收藏失败')
      throw error
    }
  }

  // 取消收藏
  const uncollectTopic = async (topicId) => {
    try {
      await uncollectTopicApi(topicId)
      
      // 更新本地状态
      const topic = topics.value.find(t => t.id === topicId)
      if (topic) {
        topic.is_collected = false
      }
      
      if (currentTopic.value?.id === topicId) {
        currentTopic.value.is_collected = false
      }
      
      return true
    } catch (error) {
      ElMessage.error('取消收藏失败')
      throw error
    }
  }

  // 刷新选题
  const refreshTopics = async () => {
    refreshing.value = true
    try {
      await refreshTopicsApi()
      await fetchTopics()
      return true
    } catch (error) {
      ElMessage.error('刷新选题失败')
      throw error
    } finally {
      refreshing.value = false
    }
  }

  // 设置筛选条件
  const setFilters = (newFilters) => {
    filters.value = { ...filters.value, ...newFilters }
  }

  // 重置筛选条件
  const resetFilters = () => {
    filters.value = {
      platform: '',
      category: '',
      keyword: '',
      sort_by: 'published_at',
      sort_order: 'desc'
    }
  }

  // 清空当前选题
  const clearCurrentTopic = () => {
    currentTopic.value = null
  }

  return {
    // 状态
    topics,
    currentTopic,
    loading,
    refreshing,
    totalTopics,
    filters,
    
    // 计算属性
    hasTopics,
    collectedTopics,
    
    // 方法
    fetchTopics,
    fetchTopicById,
    collectTopic,
    uncollectTopic,
    refreshTopics,
    setFilters,
    resetFilters,
    clearCurrentTopic
  }
})