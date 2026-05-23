<template>
  <div class="style-page">
    <!-- Hero Section -->
    <div class="style-hero-wrap">
      <template v-if="profile">
        <!-- Top meta -->
        <div class="style-meta-bar">
          <span class="style-meta-item">基于 <b>{{ profile.sourceCount }}</b> 篇素材</span>
          <span class="style-meta-dot">·</span>
          <span class="style-meta-item"><b>{{ (profile.totalWords || 0).toLocaleString() }}</b> 字</span>
          <span class="style-meta-dot">·</span>
          <span class="style-meta-item">最后训练 <b>{{ formatTime(profile.trainedAt) }}</b></span>
          <button class="btn-retrain" @click="handleTrain" :disabled="training">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            {{ training ? '训练中…' : '重新训练' }}
          </button>
        </div>

        <!-- Signature -->
        <div class="style-signature-block" v-if="profile.signature">
          <div class="style-signature-text">{{ profile.signature }}</div>
        </div>

        <!-- Radar + Traits -->
        <div class="style-analysis-grid">
          <div class="style-radar-card">
            <div class="analysis-label">— STYLE RADAR · 6维度雷达</div>
            <RadarChart :radar="profile.radar" />
            <div v-if="profile.radar" class="radar-scores">
              <div v-for="key in RADAR_KEYS" :key="key" class="radar-score-row">
                <span class="rs-label">{{ key }}</span>
                <span class="rs-val">{{ (profile.radar[key] ?? 0).toFixed(1) }} <span class="rs-max">/ 10</span></span>
              </div>
            </div>
          </div>

          <div class="style-traits-card">
            <div class="analysis-label">— STYLE TRAITS · 风格特征标签</div>
            <div class="traits-cloud">
              <span
                v-for="(trait, i) in (profile.traits || [])"
                :key="i"
                :class="['trait-tag', { primary: trait.primary }]"
              >
                {{ trait.text }}
              </span>
            </div>
          </div>
        </div>

      </template>

      <template v-else>
        <div class="style-empty-hero">
          <div class="empty-hero-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path d="M12 2L13.5 8.5L20 10L13.5 11.5L12 18L10.5 11.5L4 10L10.5 8.5L12 2Z"/>
            </svg>
          </div>
          <h3>还没有训练过风格</h3>
          <p>上传 5-10 篇你的代表作品，AI 会提取你的写作风格特征</p>
          <div v-if="training" class="training-spinner">
            <div class="spinner"></div>
            <span>AI 正在分析你的写作风格…</span>
          </div>
          <button
            v-else
            class="btn-start-train"
            @click="handleTrain"
            :disabled="sources.length === 0"
          >
            {{ sources.length === 0 ? '先在下方添加素材' : `开始训练（${sources.length} 篇素材）` }}
          </button>
        </div>
      </template>

      <div v-if="training && profile" class="training-overlay">
        <div class="spinner"></div>
        <span>AI 正在重新分析你的写作风格…</span>
      </div>
    </div>

    <!-- Sources Section -->
    <div class="style-sources-wrap">
      <div class="sources-header">
        <div class="sources-header-left">
          <h3 class="sources-title">训练素材库</h3>
          <span class="sources-count">{{ sources.length }} 篇 · {{ totalWords.toLocaleString() }} 字</span>
        </div>
        <button class="btn-add-source" @click="showAdd = true">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          添加素材
        </button>
      </div>

      <div v-if="loading" class="sources-loading">加载中…</div>

      <div v-else-if="sources.length === 0" class="sources-empty">
        <div class="empty-icon-wrap">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <p class="empty-title">还没有素材</p>
        <p class="empty-desc">建议添加 5–10 篇你自己写的代表作品，AI 抽取风格更准确</p>
      </div>

      <div v-else class="sources-list">
        <div v-for="s in sources" :key="s.id" class="source-card">
          <div :class="['source-type-badge', `type-${s.contentType}`]">
            {{ typeIcon(s.contentType) }}
          </div>
          <div class="source-body">
            <div class="source-title">{{ s.title || '未命名素材' }}</div>
            <div class="source-preview">{{ s.preview }}</div>
          </div>
          <div class="source-meta">
            <span class="source-words">{{ (s.wordCount || 0).toLocaleString() }} 字</span>
            <button class="source-del" @click="handleDelete(s.id)" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6M14 11v6"/>
                <path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Source Modal -->
    <AddSourceModal
      v-if="showAdd"
      @done="handleAddDone"
      @close="showAdd = false"
    />

    <!-- Preview Modal -->
    <PreviewModal
      v-if="showPreview"
      :profile="profile"
      @close="showPreview = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getStyleProfile,
  addStyleSource,
  deleteStyleSource,
  trainStyle,
  previewStyle,
  uploadStyleSourceFile,
} from '@/api/style'
import RadarChart from '@/components/style/RadarChart.vue'
import AddSourceModal from '@/components/style/AddSourceModal.vue'
import PreviewModal from '@/components/style/PreviewModal.vue'

const RADAR_KEYS = ['语气温度', '专业密度', '句式节奏', '情绪强度', '修辞偏好', '结构习惯']

// State
const loading = ref(true)
const training = ref(false)
const profile = ref(null)
const sources = ref([])
const showAdd = ref(false)
const showPreview = ref(false)

const totalWords = computed(() =>
  sources.value.reduce((sum, s) => sum + (s.wordCount || 0), 0)
)

// Load profile
const loadProfile = async () => {
  loading.value = true
  try {
    const res = await getStyleProfile()
    const data = res.data || res
    profile.value = data.profile
    sources.value = data.sources || []
  } catch (e) {
    console.warn('load profile failed:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadProfile()
})

// Train
const handleTrain = async () => {
  if (sources.value.length === 0) {
    ElMessage.warning('请先添加至少一篇素材')
    return
  }
  training.value = true
  try {
    const res = await trainStyle()
    const result = res.data || res
    profile.value = { ...result, trainedAt: new Date().toISOString() }
    ElMessage.success('训练完成')
  } catch (e) {
    const detail = e?.response?.data?.detail || e?.message || '未知错误'
    ElMessage.error('训练失败: ' + detail)
  } finally {
    training.value = false
  }
}

// Add source
const handleAddDone = (source) => {
  // source 可能是 axios Response 也可能是数据本身
  const s = source?.data || source
  if (s && s.id) {
    sources.value.unshift(s)
  }
  showAdd.value = false
  // 兜底：从后端重新拉一次，保证数据一致
  loadProfile()
}

// Delete source
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确认删除这篇素材？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteStyleSource(id)
    sources.value = sources.value.filter(s => s.id !== id)
    ElMessage.success('删除成功')
  } catch (e) {
    if (e === 'cancel') return
    console.error('删除素材失败:', e)
    const detail = e?.response?.data?.detail || e?.message || '未知错误'
    ElMessage.error(`删除失败：${detail}`)
  }
}

// Helpers
const typeIcon = (type) => {
  const icons = { xhs: '小', gzh: '公', link: '🔗', file: '📄' }
  return icons[type] || '文'
}

const formatTime = (iso) => {
  if (!iso) return ''
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + 'Z'
  const diff = Date.now() - new Date(normalized).getTime()
  if (diff < 0) return '刚刚'
  const m = Math.floor(diff / 60000)
  const h = Math.floor(diff / 3600000)
  const d = Math.floor(diff / 86400000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  if (h < 24) return `${h} 小时前`
  return `${d} 天前`
}
</script>

<style scoped>
.style-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
}

/* Hero Section */
.style-hero-wrap {
  position: relative;
  background: linear-gradient(135deg, #faf8f5 0%, #f5f0eb 100%);
  border: 1px solid var(--clay-soft, #E9B79E);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(31,31,30,.04);
}

.style-hero-wrap::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--clay, #cc785c), var(--leaf, #7a9e7e));
}

/* Meta Bar */
.style-meta-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.style-version-badge {
  background: var(--clay, #cc785c);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.style-meta-item {
  font-size: 13px;
  color: var(--ink-3, #666);
}

.style-meta-item b {
  color: var(--ink, #333);
  font-weight: 600;
}

.style-meta-dot {
  color: var(--ink-4, #999);
}

.btn-retrain {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  background: white;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-retrain:hover:not(:disabled) {
  border-color: var(--clay, #cc785c);
  color: var(--clay, #cc785c);
}

.btn-retrain:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Signature Block */
.style-signature-block {
  text-align: center;
  margin: 32px 0;
}

.style-signature-label {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--ink-4, #999);
  margin-bottom: 12px;
}

.style-signature-text {
  font-size: 28px;
  font-weight: 300;
  color: var(--ink, #333);
  line-height: 1.4;
  font-style: italic;
}

.style-signature-sub {
  font-size: 12px;
  color: var(--ink-4, #999);
  margin-top: 12px;
}

/* Analysis Grid */
.style-analysis-grid {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  margin: 32px 0;
}

.analysis-label {
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--ink-4, #999);
  margin-bottom: 16px;
}

/* Radar Card */
.style-radar-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.radar-scores {
  margin-top: 16px;
  text-align: left;
}

.radar-score-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--line, #f0f0f0);
  font-size: 13px;
}

.radar-score-row:last-child {
  border-bottom: none;
}

.rs-label {
  color: var(--ink-2, #555);
}

.rs-val {
  font-weight: 600;
  color: var(--ink, #333);
}

.rs-max {
  font-weight: 400;
  color: var(--ink-4, #999);
  font-size: 11px;
}

/* Traits Card */
.style-traits-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.traits-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.trait-tag {
  display: inline-block;
  padding: 6px 12px;
  background: var(--bone, #f5f5f5);
  border-radius: 16px;
  font-size: 13px;
  color: var(--ink-2, #555);
}

.trait-tag.primary {
  background: var(--clay-tint, #fdf0ec);
  color: var(--clay, #cc785c);
  font-weight: 500;
}

/* Preview CTA */
.btn-preview-style {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 14px;
  background: white;
  border: 1px dashed var(--clay, #cc785c);
  border-radius: 12px;
  color: var(--clay, #cc785c);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-preview-style:hover {
  background: var(--clay-tint, #fdf0ec);
}

/* Empty Hero */
.style-empty-hero {
  text-align: center;
  padding: 48px 24px;
}

.empty-hero-icon {
  color: var(--ink-4, #999);
  margin-bottom: 16px;
}

.style-empty-hero h3 {
  font-size: 18px;
  color: var(--ink, #333);
  margin-bottom: 8px;
}

.style-empty-hero p {
  color: var(--ink-3, #666);
  margin-bottom: 24px;
}

.btn-start-train {
  background: var(--clay, #cc785c);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 12px 24px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-start-train:hover:not(:disabled) {
  background: var(--clay-dark, #b5654a);
}

.btn-start-train:disabled {
  background: var(--ink-4, #999);
  cursor: not-allowed;
}

.training-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--clay, #cc785c);
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--line, #e5e5e5);
  border-top-color: var(--clay, #cc785c);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Training Overlay */
.training-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-radius: 16px;
  color: var(--clay, #cc785c);
}

/* Sources Section */
.style-sources-wrap {
  background: linear-gradient(135deg, #faf8f5 0%, #f5f0eb 100%);
  border: 1px solid var(--clay-soft, #E9B79E);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(31,31,30,.04);
}

.sources-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.sources-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sources-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink, #333);
}

.sources-count {
  font-size: 13px;
  color: var(--ink-3, #666);
}

.btn-add-source {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--clay, #cc785c);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-add-source:hover {
  background: var(--clay-dark, #b5654a);
}

/* Sources Empty */
.sources-loading,
.sources-empty {
  text-align: center;
  padding: 48px 24px;
  color: var(--ink-3, #666);
}

.empty-icon-wrap {
  color: var(--ink-4, #999);
  margin-bottom: 12px;
}

.empty-title {
  font-size: 16px;
  color: var(--ink, #333);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  color: var(--ink-3, #666);
}

/* Source Card */
.sources-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--line, #f0f0f0);
  border-radius: 10px;
  transition: all 0.2s;
}

.source-card:hover {
  border-color: var(--clay-light, #e8d5cf);
  background: var(--bone, #fafafa);
}

.source-type-badge {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.source-type-badge.type-xhs {
  background: #fff0f0;
  color: #ff2442;
}

.source-type-badge.type-gzh {
  background: #f0fff5;
  color: #07c160;
}

.source-type-badge.type-link {
  background: #f0f5ff;
  color: var(--leaf, #7a9e7e);
}

.source-type-badge.type-file {
  background: #f5f5f5;
  color: var(--ink-3, #666);
}

.source-body {
  flex: 1;
  min-width: 0;
}

.source-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink, #333);
  margin-bottom: 4px;
}

.source-preview {
  font-size: 12px;
  color: var(--ink-3, #666);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.source-words {
  font-size: 12px;
  color: var(--ink-4, #999);
}

.source-del {
  background: none;
  border: none;
  color: var(--ink-4, #999);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.source-del:hover {
  color: #e74c3c;
  background: #fef0f0;
}

/* Responsive */
@media (max-width: 768px) {
  .style-analysis-grid {
    grid-template-columns: 1fr;
  }

  .style-meta-bar {
    flex-wrap: wrap;
  }

  .btn-retrain {
    margin-left: 0;
    margin-top: 8px;
  }
}
</style>
