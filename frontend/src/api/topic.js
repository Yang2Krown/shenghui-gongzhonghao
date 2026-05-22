import { get, post, del } from './api'

// 获取选题列表
export const getTopics = (params = {}) => {
  return get('/topics', params)
}

// 获取选题详情
export const getTopicById = (id) => {
  return get(`/topics/${id}`)
}

// 收藏选题
export const collectTopic = (topicId) => {
  return post('/topics/collect', { topic_id: topicId })
}

// 取消收藏
export const uncollectTopic = (collectionId) => {
  return del(`/topics/collect/${collectionId}`)
}

// 获取收藏的选题列表
export const getCollectedTopics = (params = {}) => {
  return get('/topics/collected', params)
}

// 刷新选题
export const refreshTopics = () => {
  return post('/topics/refresh')
}

// 获取热门选题
export const getHotTopics = (limit = 10) => {
  return get('/topics/hot', { limit })
}

// 获取推荐选题
export const getRecommendedTopics = (limit = 10) => {
  return get('/topics/recommended', { limit })
}