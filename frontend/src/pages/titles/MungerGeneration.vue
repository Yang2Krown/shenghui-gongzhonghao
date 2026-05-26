<template>
  <div class="title-munger-page">
    <div class="page-header">
      <h1>芒格版标题生成</h1>
      <p class="subtitle">基于芒格多Agent协作方案的智能标题生成系统（≤20字 · 回环机制）</p>
    </div>

    <div class="workflow-banner">
      <div class="flow-step" v-for="(step, i) in workflowSteps" :key="i"
           :class="{ active: currentStep === i, done: currentStep > i }">
        <div class="step-num">{{ i + 1 }}</div>
        <div class="step-info">
          <div class="step-name">{{ step.name }}</div>
          <div class="step-action">{{ step.action }}</div>
        </div>
        <div v-if="i < workflowSteps.length - 1" class="step-arrow">→</div>
      </div>
    </div>

    <div class="content-section">
      <div class="input-section">
        <h2>输入文章内容</h2>
        <div class="form-group">
          <label>文章全文 / 内容摘要</label>
          <textarea v-model="content" placeholder="请输入文章全文或详细内容摘要..." rows="10"></textarea>
        </div>
        <button class="btn-primary" @click="generate" :disabled="loading">
          {{ loading ? '生成中...' : '生成标题' }}
        </button>
      </div>

      <!-- 报错 -->
      <div v-if="error" class="error-section">
        <p class="error-text">{{ error }}</p>
      </div>

      <!-- 定位语 -->
      <div v-if="result && result.positioning" class="positioning-section">
        <h2>定位语</h2>
        <div class="positioning-box">{{ result.positioning }}</div>
      </div>

      <!-- 维度候选标题 -->
      <div v-if="result && result.allTitles && result.allTitles.length" class="titles-section">
        <h2>三维度候选标题（共 {{ result.allTitles.length }} 条）</h2>
        <div class="dimension-grid">
          <div v-for="dim in dimensionGroups" :key="dim.name" class="dimension-card">
            <h3>{{ dim.name }}</h3>
            <div v-for="(t, i) in dim.titles" :key="i" class="candidate-title">
              <span class="title-text">{{ t.title }}</span>
              <span class="title-note">{{ t.dimension }}</span>
            </div>
            <div v-if="!dim.titles.length" class="empty-text">无候选</div>
          </div>
        </div>
      </div>

      <!-- Top 5 增强标题 -->
      <div v-if="result && result.top5 && result.top5.length" class="top5-section">
        <h2>Top 5 增强标题</h2>
        <div class="top5-list">
          <div v-for="(t, i) in result.top5" :key="i" class="top5-item">
            <span class="top5-rank">TOP {{ i + 1 }}</span>
            <span class="top5-title">{{ t.title }}</span>
            <span class="top5-tags">
              <span class="tag dim-tag">{{ t.dimension }}</span>
              <span v-if="t.enhancement" class="tag enhance-tag">{{ t.enhancement }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- 审判结果 -->
      <div v-if="result && result.verdicts && result.verdicts.length" class="verdict-section">
        <h2>审判结果</h2>
        <div class="verdict-list">
          <div v-for="(v, i) in result.verdicts" :key="i" class="verdict-item"
               :class="verdictClass(v.finalVerdict)">
            <div class="verdict-header">
              <span class="verdict-title">{{ v.title }}</span>
              <span class="verdict-badge" :class="verdictClass(v.finalVerdict)">{{ v.finalVerdict }}</span>
            </div>
            <div class="verdict-details">
              <span>拇指：{{ v.thumb }}</span>
              <span>字数：{{ v.wordCount }}字</span>
            </div>
            <div v-if="v.redline" class="verdict-redline">红线：{{ v.redline }}</div>
          </div>
        </div>
      </div>

      <!-- 最终推荐 -->
      <div v-if="result && result.finalPick" class="final-section">
        <h2>🏆 最终推荐标题</h2>
        <div class="final-pick">{{ result.finalPick }}</div>
      </div>

      <!-- 元信息 -->
      <div v-if="result" class="meta-section">
        <div class="meta-grid">
          <div class="meta-item">
            <span class="label">状态</span>
            <span class="value" :class="result.success ? 'success' : 'fail'">
              {{ result.success ? '通过' : '未通过' }}
            </span>
          </div>
          <div class="meta-item">
            <span class="label">迭代轮数</span>
            <span class="value">{{ result.loopCount }}</span>
          </div>
          <div class="meta-item">
            <span class="label">耗时</span>
            <span class="value">{{ result.durationSeconds.toFixed(1) }}s</span>
          </div>
        </div>
        <div v-if="result.failureReasons && result.failureReasons.length" class="failure-reasons">
          <h4>失败原因</h4>
          <p v-for="(r, i) in result.failureReasons" :key="i" class="reason-text">{{ r }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { post } from '@/api/api'

const content = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const currentStep = ref(-1)

const workflowSteps = [
  { name: '策划 Agent', action: '定位语提取' },
  { name: '三维度生成', action: '缺口/锚点/冲突' },
  { name: '增强 Agent', action: '芒格倾向叠加' },
  { name: '审判 Agent', action: '拇指测试+红线' },
]

const dimensionGroups = computed(() => {
  if (!result.value || !result.value.allTitles) return []
  const groups = { '信息缺口': [], '社会位置': [], '认知冲突': [] }
  for (const t of result.value.allTitles) {
    if (groups[t.dimension]) groups[t.dimension].push(t)
  }
  return Object.entries(groups).map(([name, titles]) => ({ name, titles }))
})

const verdictClass = (verdict) => {
  if (verdict === '发布') return 'pass'
  if (verdict === '备选') return 'backup'
  return 'reject'
}

const generate = async () => {
  if (!content.value || content.value.length < 10) {
    error.value = '请输入文章内容（至少10个字符）'
    return
  }

  loading.value = true
  error.value = ''
  result.value = null
  currentStep.value = 0

  try {
    const res = await post('/title-munger/munger-generate', { content: content.value }, { timeout: 180000 })
    const data = res.data || res
    result.value = {
      success: data.success,
      positioning: data.positioning,
      allTitles: data.all_titles || [],
      top5: data.top5 || [],
      verdicts: (data.verdicts || []).map(v => ({
        title: v.title,
        thumb: v.thumb,
        redline: v.redline,
        wordCount: v.word_count,
        finalVerdict: v.final_verdict,
      })),
      finalPick: data.final_pick,
      loopCount: data.loop_count,
      durationSeconds: data.duration_seconds,
      failureReasons: data.failure_reasons || [],
    }
    currentStep.value = 4
  } catch (e) {
    console.error('生成失败:', e)
    error.value = e.response?.data?.detail || e.message || '生成失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.title-munger-page { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 28px; font-weight: 600; color: #1a1a1a; margin: 0 0 8px 0; }
.subtitle { color: #666; font-size: 14px; margin: 0; }

.workflow-banner { display: flex; align-items: center; background: var(--paper); border-radius: 12px; padding: 16px 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); gap: 8px; overflow-x: auto; }
.flow-step { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.flow-step .step-num { width: 28px; height: 28px; border-radius: 50%; background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; color: #999; }
.flow-step.active .step-num { background: #1890ff; color: #fff; }
.flow-step.done .step-num { background: #52c41a; color: #fff; }
.step-info { display: flex; flex-direction: column; }
.step-name { font-size: 13px; font-weight: 500; color: #333; }
.step-action { font-size: 11px; color: #999; }
.step-arrow { color: #ddd; font-size: 16px; margin: 0 4px; }

.content-section { display: flex; flex-direction: column; gap: 24px; }
.input-section, .positioning-section, .titles-section, .top5-section, .verdict-section, .final-section, .meta-section { background: var(--paper); border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 14px; font-weight: 500; color: #555; margin-bottom: 8px; }
.form-group textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; resize: vertical; }
.form-group textarea:focus { outline: none; border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.1); }

.error-section { background: #fff2f0; border: 1px solid #ffccc7; border-radius: 8px; padding: 16px; }
.error-text { color: #ff4d4f; margin: 0; }

h2 { font-size: 18px; font-weight: 600; margin: 0 0 16px 0; color: #333; }
h3 { font-size: 15px; font-weight: 500; margin: 0 0 12px 0; color: #555; }
h4 { font-size: 14px; font-weight: 500; margin: 0 0 8px 0; color: #555; }

.positioning-box { background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px; padding: 16px; font-size: 16px; line-height: 1.6; color: #ad8b00; }

.btn-primary { background: #1890ff; color: #fff; border: none; padding: 12px 32px; border-radius: 8px; font-size: 16px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.btn-primary:hover:not(:disabled) { background: #40a9ff; }
.btn-primary:disabled { background: #d9d9d9; cursor: not-allowed; }

.dimension-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.dimension-card { background: #fafafa; border-radius: 8px; padding: 16px; border: 1px solid #f0f0f0; }
.candidate-title { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.candidate-title:last-child { border-bottom: none; }
.title-text { display: block; font-size: 15px; font-weight: 500; color: #333; }
.title-note { display: inline-block; margin-top: 4px; font-size: 12px; color: #999; background: #f0f0f0; padding: 2px 8px; border-radius: 4px; }
.empty-text { color: #ccc; font-size: 13px; text-align: center; padding: 12px; }

.top5-list { display: flex; flex-direction: column; gap: 12px; }
.top5-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 8px; }
.top5-rank { font-size: 12px; font-weight: 600; color: #52c41a; background: #f6ffed; padding: 2px 8px; border-radius: 4px; border: 1px solid #b7eb8f; }
.top5-title { flex: 1; font-size: 16px; font-weight: 500; color: #333; }
.top5-tags { display: flex; gap: 6px; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
.dim-tag { background: #e6f7ff; color: #1890ff; }
.enhance-tag { background: #fff7e6; color: #fa8c16; }

.verdict-list { display: flex; flex-direction: column; gap: 12px; }
.verdict-item { padding: 16px; border-radius: 8px; border: 1px solid #f0f0f0; background: #fafafa; }
.verdict-item.pass { background: #f6ffed; border-color: #b7eb8f; }
.verdict-item.backup { background: #fffbe6; border-color: #ffe58f; }
.verdict-item.reject { background: #fff2f0; border-color: #ffccc7; }
.verdict-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.verdict-title { font-size: 16px; font-weight: 500; color: #333; }
.verdict-badge { font-size: 12px; padding: 2px 10px; border-radius: 4px; font-weight: 500; }
.verdict-badge.pass { background: #b7eb8f; color: #135200; }
.verdict-badge.backup { background: #ffe58f; color: #ad8b00; }
.verdict-badge.reject { background: #ffccc7; color: #a8071a; }
.verdict-details { display: flex; gap: 16px; font-size: 13px; color: #888; }
.verdict-redline { margin-top: 4px; font-size: 13px; color: #ff4d4f; }

.final-pick { font-size: 24px; font-weight: 700; color: #1890ff; text-align: center; padding: 20px; }

.meta-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
.meta-item { text-align: center; padding: 12px; background: #f5f5f5; border-radius: 8px; }
.meta-item .label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.meta-item .value { font-size: 20px; font-weight: 600; }
.meta-item .value.success { color: #52c41a; }
.meta-item .value.fail { color: #ff4d4f; }

.failure-reasons { background: #fff2f0; border-radius: 8px; padding: 16px; }
.reason-text { color: #ff4d4f; font-size: 13px; margin: 4px 0; }
</style>
