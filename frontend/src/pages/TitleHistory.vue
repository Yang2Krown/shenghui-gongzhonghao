<template>
  <div class="title-history-page">
    <div class="page-header">
      <h1>标题生成历史</h1>
      <p class="subtitle">查看历史生成的标题记录</p>
    </div>

    <div class="content-section">
      <div v-if="loading" class="loading">加载中...</div>
      
      <div v-else-if="history.length === 0" class="empty-state">
        <p>暂无历史记录</p>
        <router-link to="/title-generation" class="btn-primary">去生成标题</router-link>
      </div>

      <div v-else class="history-list">
        <div v-for="record in history" :key="record.id" class="history-item">
          <div class="history-header">
            <span class="topic-title">{{ record.topicTitle }}</span>
            <span class="create-time">{{ formatDate(record.createdAt) }}</span>
          </div>
          <div class="history-body">
            <div class="selected-title">
              <span class="label">选用标题：</span>
              <span class="value">{{ record.selectedTitle || '未选择' }}</span>
            </div>
            <div class="candidates-count">
              <span class="label">候选数量：</span>
              <span class="value">{{ record.candidatesCount }}个</span>
            </div>
          </div>
          <div class="history-actions">
            <button class="btn-text" @click="viewDetail(record.id)">查看详情</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const loading = ref(true)
const history = ref([])

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const fetchHistory = async () => {
  try {
    const response = await axios.get('/api/v1/title-generation/history')
    history.value = response.data
  } catch (error) {
    console.error('获取历史记录失败:', error)
  } finally {
    loading.value = false
  }
}

const viewDetail = (id) => {
  // TODO: 实现查看详情功能
  alert(`查看记录 ${id} 的详情`)
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.title-history-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 32px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.content-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.loading {
  text-align: center;
  padding: 40px;
  color: #888;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-state p {
  color: #888;
  font-size: 16px;
  margin-bottom: 20px;
}

.btn-primary {
  background: #1890ff;
  color: #fff;
  border: none;
  padding: 12px 32px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #40a9ff;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-item {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  transition: box-shadow 0.2s;
}

.history-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.topic-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.create-time {
  font-size: 12px;
  color: #888;
}

.history-body {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}

.selected-title,
.candidates-count {
  font-size: 14px;
  color: #666;
}

.selected-title .label,
.candidates-count .label {
  color: #999;
}

.selected-title .value {
  color: #333;
  font-weight: 500;
}

.history-actions {
  text-align: right;
}

.btn-text {
  background: none;
  border: none;
  color: #1890ff;
  font-size: 14px;
  cursor: pointer;
  padding: 0;
}

.btn-text:hover {
  color: #40a9ff;
  text-decoration: underline;
}
</style>
