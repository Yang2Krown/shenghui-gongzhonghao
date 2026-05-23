<template>
  <div class="title-generation-page">
    <div class="page-header">
      <h1>标题生成</h1>
      <p class="subtitle">基于4 Agent协作流程的智能标题生成系统</p>
    </div>

    <div class="content-section">
      <!-- 输入区域 -->
      <div class="input-section">
        <h2>输入信息</h2>
        <div class="form-group">
          <label>选题标题</label>
          <input v-model="form.topicTitle" type="text" placeholder="请输入选题标题" />
        </div>
        <div class="form-group">
          <label>选题方向</label>
          <select v-model="form.direction">
            <option value="">请选择方向</option>
            <option value="实践型">实践型</option>
            <option value="解决问题型">解决问题型</option>
            <option value="教程型">教程型</option>
            <option value="观点型">观点型</option>
            <option value="整活型">整活型</option>
            <option value="资讯型">资讯型</option>
          </select>
        </div>
        <div class="form-group">
          <label>大纲内容</label>
          <textarea v-model="form.outline" placeholder="请输入大纲内容" rows="6"></textarea>
        </div>
        <button class="btn-primary" @click="generateTitles" :disabled="loading">
          {{ loading ? '生成中...' : '生成标题' }}
        </button>
      </div>

      <!-- 结果展示区域 -->
      <div v-if="result" class="result-section">
        <h2>推荐标题</h2>
        <div class="title-cards">
          <div v-for="(title, index) in result.top3" :key="index" class="title-card">
            <div class="title-rank">TOP {{ index + 1 }}</div>
            <div class="title-text">{{ title.title }}</div>
            <div class="title-meta">
              <span class="score">综合评分: {{ title.score.toFixed(1) }}</span>
              <span class="method">套路: {{ title.method }}</span>
            </div>
            <div class="title-reason">{{ title.reason }}</div>
          </div>
        </div>

        <!-- 详细信息 -->
        <div class="detail-section">
          <h3>生成详情</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="label">候选总数</span>
              <span class="value">{{ result.totalCandidates }}</span>
            </div>
            <div class="detail-item">
              <span class="label">覆盖套路</span>
              <span class="value">{{ result.methodsUsed }}种</span>
            </div>
            <div class="detail-item">
              <span class="label">一票否决</span>
              <span class="value">{{ result.rejectedCount }}个</span>
            </div>
            <div class="detail-item">
              <span class="label">重生次数</span>
              <span class="value">{{ result.retryCount }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史记录入口 -->
      <div class="history-link">
        <router-link to="/title-history" class="btn-secondary">查看历史记录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import axios from 'axios'

const loading = ref(false)
const result = ref(null)

const form = reactive({
  topicTitle: '',
  direction: '',
  outline: ''
})

const generateTitles = async () => {
  if (!form.topicTitle || !form.direction || !form.outline) {
    alert('请填写完整信息')
    return
  }

  loading.value = true
  try {
    const response = await axios.post('/api/v1/title-generation/generate', {
      topic: {
        title: form.topicTitle,
        direction: form.direction,
        outline: form.outline
      }
    })
    result.value = response.data
  } catch (error) {
    console.error('生成失败:', error)
    alert('生成失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.title-generation-page {
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
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.input-section {
  background: var(--paper);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.input-section h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 20px 0;
  color: #333;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #555;
  margin-bottom: 8px;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24,144,255,0.1);
}

.btn-primary {
  background: #1890ff;
  color: var(--paper);
  border: none;
  padding: 12px 32px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 8px;
}

.btn-primary:hover:not(:disabled) {
  background: #40a9ff;
}

.btn-primary:disabled {
  background: #d9d9d9;
  cursor: not-allowed;
}

.result-section {
  background: var(--paper);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.result-section h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 20px 0;
  color: #333;
}

.title-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.title-card {
  background-color: var(--ivory); background-image: radial-gradient(circle at 15% 20%, rgba(204,120,92,.08), transparent 45%), radial-gradient(circle at 85% 80%, rgba(63,92,82,.06), transparent 50%);
  border-radius: 12px;
  padding: 20px;
  color: var(--paper);
}

.title-rank {
  font-size: 12px;
  font-weight: 600;
  background: rgba(255,255,255,0.2);
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  margin-bottom: 12px;
}

.title-text {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 12px;
}

.title-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.title-reason {
  font-size: 13px;
  opacity: 0.8;
  line-height: 1.5;
}

.detail-section {
  border-top: 1px solid #f0f0f0;
  padding-top: 20px;
}

.detail-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
  color: #333;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.detail-item {
  text-align: center;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.detail-item .label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.detail-item .value {
  font-size: 24px;
  font-weight: 600;
  color: #1890ff;
}

.history-link {
  text-align: center;
  margin-top: 16px;
}

.btn-secondary {
  background: var(--paper);
  color: #1890ff;
  border: 1px solid #1890ff;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  text-decoration: none;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #f0f8ff;
}
</style>
