<template>
  <div class="title-scorer-page">
    <div class="page-header">
      <h1>芒格版标题评分</h1>
      <p class="subtitle">基于芒格多Agent协作方案，对标题进行多维度评分、诊断并生成改写建议</p>
    </div>

    <div class="content-section">
      <div class="input-section">
        <h2>输入信息</h2>
        <div class="form-group">
          <label>标题内容</label>
          <input v-model="title" type="text" placeholder="请输入需要评分的标题" />
        </div>
        <div class="form-group">
          <label>文章摘要（可选）</label>
          <textarea v-model="summary" placeholder="请输入文章摘要（如提供，能更精准地评估标题与内容的一致性）" rows="4"></textarea>
        </div>
        <button class="btn-primary" @click="score" :disabled="loading">
          {{ loading ? '评分中...' : '开始评分' }}
        </button>
      </div>

      <div v-if="error" class="error-section">
        <p class="error-text">{{ error }}</p>
      </div>

      <!-- 评分结果 -->
      <div v-if="result" class="result-section">
        <!-- 总分 -->
        <div class="total-score-section">
          <div class="score-main">
            <div class="score-circle" :class="gradeClass">
              <span class="score-value">{{ result.totalScore }}</span>
              <span class="score-unit">/100</span>
            </div>
            <div class="score-info">
              <span class="grade-badge" :class="gradeClass">{{ result.grade }}</span>
              <p class="grade-label">{{ result.gradeLabel }}</p>
            </div>
          </div>
        </div>

        <!-- 三维度评分 -->
        <div class="dimension-scores">
          <h3>三维度评分</h3>
          <div class="dimension-bar-grid">
            <div v-for="dim in dimScores" :key="dim.name" class="dimension-bar-item">
              <div class="dim-label">{{ dim.name }}</div>
              <div class="bar-wrapper">
                <div class="bar-bg">
                  <div class="bar-fill" :style="{ width: (dim.score / 10 * 100) + '%' }"
                       :class="scoreColor(dim.score)"></div>
                </div>
                <span class="bar-score">{{ dim.score.toFixed(1) }}/10</span>
              </div>
              <div class="dim-diagnosis">{{ dim.diagnosis }}</div>
            </div>
          </div>
        </div>

        <!-- 增强项评分 -->
        <div class="enhance-scores">
          <h3>增强项评分</h3>
          <div class="enhance-grid">
            <div v-for="item in enhanceItems" :key="item.name" class="enhance-item">
              <div class="enhance-label">{{ item.name }}</div>
              <div class="stars">
                <span v-for="n in 5" :key="n" class="star"
                      :class="{ filled: n <= item.score }">★</span>
                <span class="enhance-num">{{ item.score.toFixed(1) }}/5</span>
              </div>
            </div>
          </div>
          <div v-if="result.scores.enhanceOpportunities" class="enhance-opportunities">
            <p>{{ result.scores.enhanceOpportunities }}</p>
          </div>
        </div>

        <!-- 红线审查 -->
        <div class="redline-section">
          <h3>红线审查</h3>
          <div class="redline-grid">
            <div class="redline-item">
              <span class="rl-label">焦虑贩卖</span>
              <span class="rl-result" :class="result.redlines.r1 ? 'pass' : 'fail'">
                {{ result.redlines.r1 ? '✓ 通过' : '✗ 未通过' }}
              </span>
            </div>
            <div class="redline-item">
              <span class="rl-label">承诺兑现</span>
              <span class="rl-result" :class="result.redlines.r2 ? 'pass' : 'fail'">
                {{ result.redlines.r2 ? '✓ 通过' : (result.redlines.highRiskR2 ? '⚠ 高风险' : '✗ 未通过') }}
              </span>
            </div>
            <div class="redline-item">
              <span class="rl-label">操控词</span>
              <span class="rl-result" :class="result.redlines.r3 ? 'pass' : 'fail'">
                {{ result.redlines.r3 ? '✓ 通过' : '✗ 未通过' }}
              </span>
            </div>
            <div class="redline-item">
              <span class="rl-label">命名状态</span>
              <span class="rl-result" :class="result.redlines.r4NamedState ? 'bonus' : ''">
                {{ result.redlines.r4NamedState ? '✦ 命中' : '未命中' }}
              </span>
            </div>
            <div class="redline-item">
              <span class="rl-label">字数</span>
              <span class="rl-result" :class="result.redlines.charOk ? 'pass' : 'fail'">
                {{ result.redlines.charCount }}字 {{ result.redlines.charOk ? '✓' : '✗' }}
              </span>
            </div>
          </div>
          <div v-if="result.redlines.rawRedlines" class="redline-raw">
            <p>{{ result.redlines.rawRedlines }}</p>
          </div>
        </div>

        <!-- 诊断 -->
        <div v-if="result.diagnosis" class="diagnosis-section">
          <h3>综合诊断</h3>
          <div class="diagnosis-content">
            <template v-if="typeof result.diagnosis === 'string'">
              <p>{{ result.diagnosis }}</p>
            </template>
            <template v-else>
              <div v-for="(val, key) in result.diagnosis" :key="key" class="diag-item">
                <span class="diag-key">{{ key }}：</span>
                <span class="diag-val">{{ val }}</span>
              </div>
            </template>
          </div>
        </div>

        <!-- 结构分析 -->
        <div v-if="result.analysis && result.analysis.raw" class="analysis-section">
          <h3>结构分析</h3>
          <pre class="analysis-text">{{ result.analysis.raw }}</pre>
        </div>

        <!-- 改写建议 -->
        <div v-if="result.rewrites && result.rewrites.length" class="rewrite-section">
          <h3>改写建议</h3>
          <div class="rewrite-list">
            <div v-for="(rw, i) in result.rewrites" :key="i" class="rewrite-item">
              <div class="rewrite-header">
                <span class="rewrite-num">建议 {{ i + 1 }}</span>
                <span class="rewrite-title">{{ rw.title }}</span>
              </div>
              <div class="rewrite-detail">
                <span v-if="rw.fix" class="rewrite-fix">修复：{{ rw.fix }}</span>
                <span v-if="rw.keep" class="rewrite-keep">保留：{{ rw.keep }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 元信息 -->
        <div class="meta-section">
          <div class="meta-item">
            <span class="label">耗时</span>
            <span class="value">{{ result.durationSeconds.toFixed(1) }}s</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { post } from '@/api/api'

const title = ref('')
const summary = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const gradeClass = computed(() => {
  if (!result.value) return ''
  const g = result.value.grade
  if (g === 'S') return 'grade-s'
  if (g === 'A') return 'grade-a'
  if (g === 'B') return 'grade-b'
  if (g === 'C') return 'grade-c'
  return 'grade-d'
})

const dimScores = computed(() => {
  if (!result.value || !result.value.scores) return []
  const s = result.value.scores
  return [
    { name: '信息缺口', score: s.gap?.score || 0, diagnosis: s.gap?.diagnosis || '' },
    { name: '社会位置', score: s.anchor?.score || 0, diagnosis: s.anchor?.diagnosis || '' },
    { name: '认知冲突', score: s.conflict?.score || 0, diagnosis: s.conflict?.diagnosis || '' },
  ]
})

const enhanceItems = computed(() => {
  if (!result.value || !result.value.scores || !result.value.scores.enhancement) return []
  const e = result.value.scores.enhancement
  return [
    { name: '联想光环', score: e['联想光环'] || 0 },
    { name: '对比结构', score: e['对比结构'] || 0 },
    { name: '因果承诺', score: e['因果承诺'] || 0 },
  ]
})

const scoreColor = (score) => {
  if (score >= 7) return 'high'
  if (score >= 4) return 'mid'
  return 'low'
}

const score = async () => {
  if (!title.value) {
    error.value = '请输入标题内容'
    return
  }

  loading.value = true
  error.value = ''
  result.value = null

  try {
    const res = await post('/title-munger/munger-score', {
      title: title.value,
      summary: summary.value || undefined,
    }, { timeout: 120000 })

    const data = res.data || res
    result.value = {
      success: data.success,
      totalScore: data.total_score,
      grade: data.grade,
      gradeLabel: data.grade_label,
      analysis: data.analysis,
      scores: data.scores,
      redlines: data.redlines,
      diagnosis: data.diagnosis,
      rewrites: (data.rewrites || []).map(r => ({
        title: r.title,
        fix: r.fix,
        keep: r.keep,
      })),
      durationSeconds: data.duration_seconds,
      error: data.error,
    }
  } catch (e) {
    console.error('评分失败:', e)
    error.value = e.response?.data?.detail || e.message || '评分失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.title-scorer-page { padding: 24px; max-width: 1000px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 28px; font-weight: 600; color: #1a1a1a; margin: 0 0 8px 0; }
.subtitle { color: #666; font-size: 14px; margin: 0; }

.content-section { display: flex; flex-direction: column; gap: 24px; }
.input-section, .result-section, .dimension-scores, .enhance-scores, .redline-section, .diagnosis-section, .analysis-section, .rewrite-section { background: var(--paper); border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 14px; font-weight: 500; color: #555; margin-bottom: 8px; }
.form-group input, .form-group textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }
.form-group input:focus, .form-group textarea:focus { outline: none; border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.1); }
.form-group textarea { resize: vertical; }

.btn-primary { background: #1890ff; color: #fff; border: none; padding: 12px 32px; border-radius: 8px; font-size: 16px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
.btn-primary:hover:not(:disabled) { background: #40a9ff; }
.btn-primary:disabled { background: #d9d9d9; cursor: not-allowed; }

.error-section { background: #fff2f0; border: 1px solid #ffccc7; border-radius: 8px; padding: 16px; }
.error-text { color: #ff4d4f; margin: 0; }

h2 { font-size: 18px; font-weight: 600; margin: 0 0 16px 0; color: #333; }
h3 { font-size: 16px; font-weight: 600; margin: 0 0 16px 0; color: #333; }

.total-score-section { background: var(--paper); border-radius: 12px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.score-main { display: flex; align-items: center; gap: 32px; justify-content: center; }
.score-circle { width: 120px; height: 120px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #f5f5f5; }
.score-circle.grade-s { background: linear-gradient(135deg, #f5222d, #fa8c16); color: #fff; }
.score-circle.grade-a { background: linear-gradient(135deg, #52c41a, #73d13d); color: #fff; }
.score-circle.grade-b { background: linear-gradient(135deg, #1890ff, #40a9ff); color: #fff; }
.score-circle.grade-c { background: linear-gradient(135deg, #fa8c16, #ffc53d); color: #fff; }
.score-circle.grade-d { background: #d9d9d9; color: #999; }
.score-value { font-size: 36px; font-weight: 700; line-height: 1; }
.score-unit { font-size: 14px; opacity: 0.8; }
.score-info { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.grade-badge { font-size: 32px; font-weight: 800; }
.grade-badge.grade-s { color: #f5222d; }
.grade-badge.grade-a { color: #52c41a; }
.grade-badge.grade-b { color: #1890ff; }
.grade-badge.grade-c { color: #fa8c16; }
.grade-badge.grade-d { color: #999; }
.grade-label { font-size: 13px; color: #666; text-align: center; max-width: 240px; }

.dimension-bar-grid { display: flex; flex-direction: column; gap: 16px; }
.dimension-bar-item { }
.dim-label { font-size: 14px; font-weight: 500; color: #555; margin-bottom: 8px; }
.bar-wrapper { display: flex; align-items: center; gap: 12px; }
.bar-bg { flex: 1; height: 12px; background: #f0f0f0; border-radius: 6px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 6px; transition: width 0.5s; }
.bar-fill.high { background: #52c41a; }
.bar-fill.mid { background: #fa8c16; }
.bar-fill.low { background: #ff4d4f; }
.bar-score { font-size: 14px; font-weight: 600; color: #333; min-width: 50px; }
.dim-diagnosis { margin-top: 4px; font-size: 12px; color: #888; }

.enhance-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.enhance-item { padding: 16px; background: #fafafa; border-radius: 8px; text-align: center; }
.enhance-label { font-size: 14px; font-weight: 500; color: #555; margin-bottom: 8px; }
.stars { display: flex; align-items: center; justify-content: center; gap: 2px; }
.star { font-size: 18px; color: #ddd; }
.star.filled { color: #faad14; }
.enhance-num { margin-left: 8px; font-size: 13px; color: #888; }
.enhance-opportunities { margin-top: 12px; padding: 12px; background: #fffbe6; border-radius: 8px; font-size: 13px; color: #ad8b00; }

.redline-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.redline-item { display: flex; justify-content: space-between; padding: 10px 16px; background: #fafafa; border-radius: 8px; }
.rl-label { font-size: 13px; color: #555; }
.rl-result { font-size: 13px; font-weight: 500; }
.rl-result.pass { color: #52c41a; }
.rl-result.fail { color: #ff4d4f; }
.rl-result.bonus { color: #fa8c16; }
.redline-raw { margin-top: 12px; padding: 12px; background: #fafafa; border-radius: 8px; font-size: 13px; color: #888; white-space: pre-line; }

.diagnosis-content { padding: 16px; background: #fafafa; border-radius: 8px; font-size: 14px; line-height: 1.6; color: #333; }
.diag-item { margin-bottom: 8px; }
.diag-key { font-weight: 500; color: #555; }
.diag-val { color: #333; }

.analysis-text { background: #f5f5f5; border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; overflow-x: auto; color: #555; }

.rewrite-list { display: flex; flex-direction: column; gap: 12px; }
.rewrite-item { padding: 16px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 8px; }
.rewrite-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.rewrite-num { font-size: 12px; font-weight: 600; color: #52c41a; padding: 2px 8px; border-radius: 4px; border: 1px solid #b7eb8f; }
.rewrite-title { font-size: 16px; font-weight: 500; color: #333; }
.rewrite-detail { display: flex; gap: 16px; font-size: 13px; }
.rewrite-fix { color: #ff4d4f; }
.rewrite-keep { color: #1890ff; }

.meta-section { background: var(--paper); border-radius: 12px; padding: 16px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); display: flex; justify-content: center; }
.meta-item { text-align: center; }
.meta-item .label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.meta-item .value { font-size: 18px; font-weight: 600; color: #333; }

.result-section { display: flex; flex-direction: column; gap: 24px; }
</style>
