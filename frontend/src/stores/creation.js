import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCreations, getCreationById, createCreation as createCreationApi, updateCreation as updateCreationApi, deleteCreation as deleteCreationApi, generateContent as generateContentApi, optimizeContent as optimizeContentApi } from '@/api/creation'
import { ElMessage } from 'element-plus'

export const useCreationStore = defineStore('creation', () => {
  // 状态
  const creations = ref([])
  const currentCreation = ref(null)
  const loading = ref(false)
  const generating = ref(false)
  const optimizing = ref(false)
  const totalCreations = ref(0)

  // 计算属性
  const hasCreations = computed(() => creations.value.length > 0)
  const draftCreations = computed(() => creations.value.filter(c => c.status === 'draft'))
  const publishedCreations = computed(() => creations.value.filter(c => c.status === 'published'))

  // 获取创作列表
  const fetchCreations = async (params = {}) => {
    loading.value = true
    try {
      const response = await getCreations(params)
      const { items, total } = response.data
      
      creations.value = items || []
      totalCreations.value = total || 0
      
      return { items, total }
    } catch (error) {
      ElMessage.error('获取创作列表失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 获取创作详情
  const fetchCreationById = async (id) => {
    loading.value = true
    try {
      const response = await getCreationById(id)
      currentCreation.value = response.data
      return response.data
    } catch (error) {
      ElMessage.error('获取创作详情失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 创建创作
  const createCreation = async (creationData) => {
    loading.value = true
    try {
      const response = await createCreationApi(creationData)
      const newCreation = response.data
      
      // 添加到列表
      creations.value.unshift(newCreation)
      totalCreations.value += 1
      
      ElMessage.success('创作创建成功')
      return newCreation
    } catch (error) {
      ElMessage.error('创建创作失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 更新创作
  const updateCreation = async (id, creationData) => {
    loading.value = true
    try {
      const response = await updateCreationApi(id, creationData)
      const updatedCreation = response.data
      
      // 更新列表
      const index = creations.value.findIndex(c => c.id === id)
      if (index !== -1) {
        creations.value[index] = updatedCreation
      }
      
      // 更新当前创作
      if (currentCreation.value?.id === id) {
        currentCreation.value = updatedCreation
      }
      
      ElMessage.success('创作更新成功')
      return updatedCreation
    } catch (error) {
      ElMessage.error('更新创作失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 删除创作
  const deleteCreation = async (id) => {
    try {
      await deleteCreationApi(id)
      
      // 从列表移除
      creations.value = creations.value.filter(c => c.id !== id)
      totalCreations.value -= 1
      
      // 清空当前创作
      if (currentCreation.value?.id === id) {
        currentCreation.value = null
      }
      
      ElMessage.success('创作删除成功')
      return true
    } catch (error) {
      ElMessage.error('删除创作失败')
      throw error
    }
  }

  // AI生成内容
  const generateContent = async (params) => {
    generating.value = true
    try {
      const response = await generateContentApi(params)
      return response.data
    } catch (error) {
      ElMessage.error('AI生成内容失败')
      throw error
    } finally {
      generating.value = false
    }
  }

  // AI优化内容
  const optimizeContent = async (params) => {
    optimizing.value = true
    try {
      const response = await optimizeContentApi(params)
      return response.data
    } catch (error) {
      ElMessage.error('AI优化内容失败')
      throw error
    } finally {
      optimizing.value = false
    }
  }

  // 清空当前创作
  const clearCurrentCreation = () => {
    currentCreation.value = null
  }

  return {
    // 状态
    creations,
    currentCreation,
    loading,
    generating,
    optimizing,
    totalCreations,
    
    // 计算属性
    hasCreations,
    draftCreations,
    publishedCreations,
    
    // 方法
    fetchCreations,
    fetchCreationById,
    createCreation,
    updateCreation,
    deleteCreation,
    generateContent,
    optimizeContent,
    clearCurrentCreation
  }
})