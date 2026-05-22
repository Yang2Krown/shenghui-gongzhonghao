<template>
  <div class="content-generation-page">
    <div class="page-header">
      <h1>正文生成</h1>
      <p class="subtitle">4 Agent 协作：正文创作 → 金句催化 → 去 AI 味 → 整合自检</p>
    </div>

    <div class="content-section">
      <!-- 输入区域 -->
      <div class="input-section">
        <h2>输入信息</h2>

        <div class="form-row">
          <div class="form-group">
            <label>选题标题</label>
            <input v-model="form.topicTitle" type="text" placeholder="最终选定的标题" />
          </div>
          <div class="form-group">
            <label>内容方向</label>
            <input v-model="form.topicDirection" type="text" placeholder="如：实践型、观点型" />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>套路</label>
            <input v-model="form.topicRoutine" type="text" placeholder="如：1.1.1 深度解读型" />
          </div>
          <div class="form-group">
            <label>价值承诺</label>
            <input v-model="form.valuePromise" type="text" placeholder="一句话价值承诺" />
          </div>
        </div>

        <!-- 大纲节 -->
        <div class="form-group">
          <label>大纲节 <button class="btn-add" @click="addSection">+ 添加节</button></label>
          <div v-for="(sec, idx) in form.sections" :key="idx" class="section-card">
            <div class="section-header">
              <span class="section-num">第{{ sec.section_number }}节</span>
              <button class="btn-remove" @click="removeSection(idx)">删除</button>
            </div>
            <div class="form-row">
              <div class="form-group flex-2">
                <input v-model="sec.subtitle" type="text" placeholder="小标题" />
              </div>
              <div class="form-group flex-1">
                <select v-model="sec.spread_role">
                  <option value="">传播角色</option>
                  <option value="钩子">钩子</option>
                  <option value="铺垫">铺垫</option>
                  <option value="高潮">高潮</option>
                  <option value="升华">升华</option>
                  <option value="收尾">收尾</option>
                </select>
              </div>
              <div class="form-group flex-1">
                <input v-model.number="sec.word_estimate" type="number" placeholder="字数" />
              </div>
            </div>
            <textarea v-model="sec.core_points_text" placeholder="核心信息点（每行一个）" rows="2"></textarea>
          </div>
        </div>

        <!-- 风格参数 -->
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="showStyle" /> 风格参数（可选）
          </label>
          <div v-if="showStyle" class="style-section">
            <div class="form-group">
              <input v-model="form.styleParams.tone" type="text" placeholder="语气描述，如：第一人称、带点自嘲" />
            </div>
            <div class="form-row">
              <div class="form-group flex-1">
                <input v-model="form.styleParams.bannedWordsText" type="text" placeholder="禁用词（逗号分隔）" />
              </div>
              <div class="form-group flex-1">
                <input v-model="form.styleParams.preferredWordsText" type="text" placeholder="偏好用词（逗号分隔）" />
              </div>
            </div>
          </div>
        </div>

        <button class="btn-primary" @click="generateContent" :disabled="loading">
          {{ loading ? '生成中...（约30-60秒）' : '生成正文' }}
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-section">
        <div class="loading-steps">
          <div v-for="(step, idx) in steps" :key="idx" class="step" :class="{ active: idx === currentStep, done: idx < currentStep }">
            <span class="step-icon">{{ idx < currentStep ? '✓' : idx === currentStep ? '⏳' : '○' }}</span>
            <span class="step-text">{{ step }}</span>
          </div>
        </div>
      </div>

      <!-- 结果展示区域 -->
      <div v-if="result" class="result-section">
        <!-- 诊断报告 -->
        <div class="diagnosis-bar">
          <div class="score-circle" :class="scoreClass">
            <span class="score-num">{{ result.diagnosis.total_score.toFixed(1) }}</span>
            <span class="score-label">总分</span>
          </div>
          <div class="score-action">
            <span class="action-label">建议：</span>
            <span class="action-value" :class="actionClass">{{ result.diagnosis.recommended_action }}</span>
          </div>
          <div class="score-stats">
            <span>字数: {{ result.final_word_count }}</span>
            <span>金句: {{ result.gold_sentences.length }}个</span>
            <span>改写: {{ result.rewrite_count }}处</span>
          </div>
        </div>

        <!-- 8 维度雷达 -->
        <div class="dimensions-section">
          <h3>8 维度评分</h3>
          <div class="dimensions-grid">
            <div v-for="(dim, key) in result.diagnosis.dimensions" :key="key" class="dim-item">
              <div class="dim-header">
                <span class="dim-name">{{ dimNameMap[key] || key }}</span>
                <span class="dim-score" :class="dimScoreClass(dim.score)">{{ dim.score }}</span>
              </div>
              <div class="dim-bar">
                <div class="dim-bar-fill" :style="{ width: (dim.score * 10) + '%' }"></div>
              </div>
              <div class="dim-eval">{{ dim.evaluation }}</div>
            </div>
          </div>
        </div>

        <!-- 金句清单 -->
        <div class="gold-section">
          <h3>金句清单</h3>
          <div class="gold-cards">
            <div v-for="g in result.gold_sentences" :key="g.sentence_id" class="gold-card">
              <span class="gold-type">{{ g.sentence_type }}</span>
              <p class="gold-content">"{{ g.content }}"</p>
              <span class="gold-loc">{{ g.location }}</span>
            </div>
          </div>
        </div>

        <!-- 正文预览 -->
        <div class="article-section">
          <h3>
            正文预览
            <button class="btn-copy" @click="copyText">复制全文</button>
          </h3>
          <div class="article-content" v-html="renderMarkdown(result.final_text)"></div>
        </div>

        <!-- 改进建议 -->
        <div v-if="result.diagnosis.medium_priority.length || result.diagnosis.high_priority.length" class="suggestions-section">
          <h3>改进建议</h3>
          <div v-if="result.diagnosis.high_priority.length" class="suggestion-group high">
            <h4>高优先级</h4>
            <ul><li v-for="(s, i) in result.diagnosis.high_priority" :key="i">{{ s }}</li></ul>
          </div>
          <div v-if="result.diagnosis.medium_priority.length" class="suggestion-group medium">
            <h4>中优先级</h4>
            <ul><li v-for="(s, i) in result.diagnosis.medium_priority" :key="i">{{ s }}</li></ul>
          </div>
          <div v-if="result.diagnosis.low_priority.length" class="suggestion-group low">
            <h4>低优先级</h4>
            <ul><li v-for="(s, i) in result.diagnosis.low_priority" :key="i">{{ s }}</li></ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'

const loading = ref(false)
const result = ref(null)
const showStyle = ref(false)
const currentStep = ref(-1)

const steps = ['Agent A 正文创作', 'Agent B 金句催化', 'Agent C 去AI味改写', 'Agent D 整合自检']

const dimNameMap = {
  title_fulfillment: '标题兑现',
  outline_alignment: '大纲对应',
  word_compliance: '字数合规',
  style_consistency: '风格统一',
  deai_thoroughness: '去AI味',
  gold_sentence_completeness: '金句完整',
  opening_quality: '开头质量',
  ending_quality: '结尾升华'
}

const form = reactive({
  topicTitle: '',
  topicDirection: '',
  topicRoutine: '',
  valuePromise: '',
  sections: [
    { section_number: 1, subtitle: '', core_points_text: '', spread_role: '钩子', word_estimate: 500 },
    { section_number: 2, subtitle: '', core_points_text: '', spread_role: '铺垫', word_estimate: 500 },
    { section_number: 3, subtitle: '', core_points_text: '', spread_role: '高潮', word_estimate: 500 },
    { section_number: 4, subtitle: '', core_points_text: '', spread_role: '升华', word_estimate: 500 },
    { section_number: 5, subtitle: '', core_points_text: '', spread_role: '收尾', word_estimate: 400 }
  ],
  styleParams: {
    tone: '',
    bannedWordsText: '',
    preferredWordsText: ''
  }
})

const addSection = () => {
  const num = form.sections.length + 1
  form.sections.push({ section_number: num, subtitle: '', core_points_text: '', spread_role: '', word_estimate: 500 })
}

const removeSection = (idx) => {
  form.sections.splice(idx, 1)
  form.sections.forEach((s, i) => { s.section_number = i + 1 })
}

const scoreClass = computed(() => {
  if (!result.value) return ''
  const s = result.value.diagnosis.total_score
  if (s >= 8) return 'score-good'
  if (s >= 6) return 'score-ok'
  return 'score-bad'
})

const actionClass = computed(() => {
  if (!result.value) return ''
  const a = result.value.diagnosis.recommended_action
  if (a.includes('接受')) return 'action-good'
  if (a.includes('局部')) return 'action-ok'
  return 'action-bad'
})

const dimScoreClass = (score) => {
  if (score >= 8) return 'dim-good'
  if (score >= 6) return 'dim-ok'
  return 'dim-bad'
}

const renderMarkdown = (text) => {
  if (!text) return ''
  return text
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

const copyText = () => {
  if (result.value?.final_text) {
    navigator.clipboard.writeText(result.value.final_text)
    alert('已复制到剪贴板')
  }
}

const generateContent = async () => {
  if (!form.topicTitle) {
    alert('请填写选题标题')
    return
  }
  if (form.sections.length === 0 || !form.sections[0].subtitle) {
    alert('请至少填写一节大纲')
    return
  }

  loading.value = true
  result.value = null
  currentStep.value = 0

  // 模拟步骤进度
  const stepTimer = setInterval(() => {
    if (currentStep.value < 3) currentStep.value++
  }, 8000)

  try {
    const sections = form.sections.map(s => ({
      section_number: s.section_number,
      subtitle: s.subtitle,
      core_points: s.core_points_text ? s.core_points_text.split('\n').filter(Boolean) : [],
      spread_role: s.spread_role || null,
      word_estimate: s.word_estimate || 500
    }))

    const styleParams = showStyle.value ? {
      tone: form.styleParams.tone || null,
      banned_words: form.styleParams.bannedWordsText ? form.styleParams.bannedWordsText.split(',').map(s => s.trim()).filter(Boolean) : [],
      preferred_words: form.styleParams.preferredWordsText ? form.styleParams.preferredWordsText.split(',').map(s => s.trim()).filter(Boolean) : []
    } : null

    const response = await axios.post('/api/v1/content-generation/generate/sync', {
      topic_title: form.topicTitle,
      topic_direction: form.topicDirection || null,
      topic_routine: form.topicRoutine || null,
      value_promise: form.valuePromise || null,
      sections,
      style_params: styleParams
    })

    result.value = response.data.data
    currentStep.value = 4
  } catch (error) {
    console.error('生成失败:', error)
    alert('生成失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    clearInterval(stepTimer)
    loading.value = false
  }
}
</script>

<style scoped>
.content-generation-page {
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
  gap: 24px;
}

/* 输入区 */
.input-section {
  background: #fff;
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

.form-row {
  display: flex;
  gap: 16px;
}

.form-group {
  margin-bottom: 16px;
  flex: 1;
}

.form-group.flex-2 { flex: 2; }
.form-group.flex-1 { flex: 1; }

.form-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #555;
  margin-bottom: 8px;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24,144,255,0.1);
}

.section-card {
  background: #f9f9fb;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-num {
  font-weight: 600;
  color: #1890ff;
  font-size: 14px;
}

.btn-add {
  background: #f0f8ff;
  color: #1890ff;
  border: 1px dashed #1890ff;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.btn-remove {
  background: none;
  border: none;
  color: #ff4d4f;
  cursor: pointer;
  font-size: 12px;
}

.style-section {
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 16px;
  margin-top: 8px;
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

/* 加载状态 */
.loading-section {
  background: #fff;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.loading-steps {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.step {
  flex: 1;
  text-align: center;
  padding: 16px;
  border-radius: 8px;
  background: #f5f5f5;
  transition: all 0.3s;
}

.step.active {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

.step.done {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.step-icon {
  display: block;
  font-size: 20px;
  margin-bottom: 8px;
}

.step-text {
  font-size: 13px;
  color: #666;
}

.step.active .step-text {
  color: #1890ff;
  font-weight: 500;
}

/* 结果区 */
.result-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.diagnosis-bar {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  display: flex;
  align-items: center;
  gap: 32px;
}

.score-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.score-good { background: linear-gradient(135deg, #52c41a, #73d13d); }
.score-ok { background: linear-gradient(135deg, #faad14, #ffc53d); }
.score-bad { background: linear-gradient(135deg, #ff4d4f, #ff7875); }

.score-num { font-size: 24px; font-weight: 700; }
.score-label { font-size: 11px; opacity: 0.9; }

.score-action {
  font-size: 16px;
}

.action-label { color: #888; }
.action-good { color: #52c41a; font-weight: 600; }
.action-ok { color: #faad14; font-weight: 600; }
.action-bad { color: #ff4d4f; font-weight: 600; }

.score-stats {
  margin-left: auto;
  display: flex;
  gap: 24px;
  color: #888;
  font-size: 14px;
}

/* 维度 */
.dimensions-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.dimensions-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 20px 0;
}

.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.dim-item {
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
}

.dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.dim-name { font-size: 13px; color: #555; }
.dim-score { font-size: 18px; font-weight: 700; }
.dim-good { color: #52c41a; }
.dim-ok { color: #faad14; }
.dim-bad { color: #ff4d4f; }

.dim-bar {
  height: 4px;
  background: #eee;
  border-radius: 2px;
  margin-bottom: 8px;
}

.dim-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: #1890ff;
  transition: width 0.5s;
}

.dim-eval {
  font-size: 12px;
  color: #888;
  line-height: 1.4;
}

/* 金句 */
.gold-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.gold-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.gold-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.gold-card {
  background: linear-gradient(135deg, #fff7e6, #fffbe6);
  border: 1px solid #ffe58f;
  border-radius: 10px;
  padding: 16px;
}

.gold-type {
  font-size: 11px;
  color: #d48806;
  background: #fff7e6;
  border: 1px solid #ffe58f;
  padding: 2px 8px;
  border-radius: 4px;
}

.gold-content {
  font-size: 15px;
  font-weight: 500;
  color: #333;
  line-height: 1.6;
  margin: 12px 0 8px 0;
}

.gold-loc {
  font-size: 12px;
  color: #999;
}

/* 正文 */
.article-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.article-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-copy {
  background: #f0f8ff;
  color: #1890ff;
  border: 1px solid #1890ff;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.article-content {
  font-size: 15px;
  line-height: 1.8;
  color: #333;
  max-height: 600px;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.article-content :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  margin: 24px 0 12px 0;
  color: #1a1a1a;
}

.article-content :deep(strong) {
  color: #1890ff;
}

/* 建议 */
.suggestions-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.suggestions-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.suggestion-group {
  margin-bottom: 16px;
}

.suggestion-group h4 {
  font-size: 14px;
  margin: 0 0 8px 0;
}

.suggestion-group.high h4 { color: #ff4d4f; }
.suggestion-group.medium h4 { color: #faad14; }
.suggestion-group.low h4 { color: #888; }

.suggestion-group ul {
  margin: 0;
  padding-left: 20px;
}

.suggestion-group li {
  font-size: 13px;
  color: #555;
  line-height: 1.8;
}
</style>
