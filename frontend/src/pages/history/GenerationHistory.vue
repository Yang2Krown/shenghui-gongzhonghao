<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <!-- 页面标题 -->
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><Clock /></el-icon>
        创作历史
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        你的<span class="text-clay">创作足迹</span>
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        所有生成记录，可随时查看与复用
      </p>
    </div>

    <!-- 类型筛选 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div style="padding: 16px 22px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <span class="text-sm text-ink-4" style="flex-shrink: 0;">分类：</span>
        <button
          v-for="c in categories"
          :key="c.value"
          :class="['type-chip', { 'type-chip-active': currentCat === c.value }]"
          @click="currentCat = c.value; currentPage = 1; fetchRecords()"
        >
          {{ c.label }}
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" style="text-align: center; padding: 80px 0;">
      <el-icon :size="30" class="spin text-clay" style="margin: 0 auto;"><Loading /></el-icon>
      <p class="text-sm text-ink-3" style="margin-top: 14px;">加载中…</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="card" style="text-align: center; padding: 80px 22px;">
      <el-icon :size="48" class="text-ink-4"><Document /></el-icon>
      <h3 class="font-sans text-ink" style="font-size: 18px; font-weight: 600; margin-top: 16px;">暂无生成记录</h3>
      <p class="text-sm text-ink-3" style="margin-top: 8px;">使用各功能生成内容后，记录会自动出现在这里</p>
    </div>

    <!-- 记录列表 -->
    <div v-else style="display: flex; flex-direction: column; gap: 12px;">
      <div
        v-for="record in records"
        :key="record.id"
        class="card record-card"
        @click="navigateToRecord(record)"
      >
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;">
          <div style="display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0;">
            <!-- 类型标签 -->
            <span :class="['type-badge', `cat-${typeCat(record.type)}`]">
              {{ typeLabel(record.type) }}
            </span>
            <!-- 状态指示器 -->
            <span :class="['status-dot', `status-${record.status}`]"></span>
            <!-- 标题 -->
            <span class="text-ink font-serif" style="font-weight: 500; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">
              {{ record.display_title || '未命名' }}
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 14px; flex-shrink: 0;">
            <!-- 积分消耗 -->
            <span :class="['credit-tag', typeCredits(record.type) > 0 ? 'credit-tag-cost' : 'credit-tag-free']">
              {{ typeCredits(record.type) > 0 ? `-${typeCredits(record.type)} 积分` : '免费' }}
            </span>
            <span class="text-sm text-ink-4 font-serif">{{ formatTime(record.created_at) }}</span>
            <button class="btn-action" @click.stop="navigateToRecord(record)">
              查看详情
              <el-icon :size="14"><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" style="display: flex; justify-content: center; margin-top: 24px;">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchRecords"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="showDetail"
      title="记录详情"
      width="680px"
      :close-on-click-modal="true"
      class="detail-dialog"
    >
      <div v-if="detailLoading" style="text-align: center; padding: 40px 0;">
        <el-icon class="spin" :size="24"><Loading /></el-icon>
        <p class="text-sm text-ink-3" style="margin-top: 10px;">加载中…</p>
      </div>
      <div v-else-if="detailRecord" class="detail-content">
        <!-- 头部信息 -->
        <div class="detail-header">
          <span :class="['type-badge', `cat-${typeCat(detailRecord.type)}`]">
            {{ typeLabel(detailRecord.type) }}
          </span>
          <span :class="['status-dot', `status-${detailRecord.status}`]"></span>
          <span :class="['credit-tag', typeCredits(detailRecord.type) > 0 ? 'credit-tag-cost' : 'credit-tag-free']">
            {{ typeCredits(detailRecord.type) > 0 ? `消耗 ${typeCredits(detailRecord.type)} 积分` : '免费' }}
          </span>
          <span class="text-sm text-ink-4 font-serif">{{ formatTime(detailRecord.created_at) }}</span>
        </div>

        <!-- 标题 -->
        <h2 class="font-serif detail-title">{{ detailRecord.display_title || '未命名' }}</h2>

        <!-- 内容 -->
        <div class="detail-body font-serif">
          <div v-if="detailBlocks.length === 0" class="detail-text text-ink-4" style="text-align: center; padding: 40px 0;">
            暂无输出内容
          </div>
          <div v-for="block in detailBlocks" :key="block.key" class="detail-section">
            <div class="detail-label">{{ block.label }}</div>

            <!-- 长文本 / Markdown -->
            <div v-if="block.kind === 'markdown'" class="markdown-body" v-html="renderMarkdown(block.value)"></div>

            <!-- 短文本 -->
            <div v-else-if="block.kind === 'text'" class="detail-text">{{ block.value }}</div>

            <!-- 标签 -->
            <div v-else-if="block.kind === 'tags'" class="detail-tags">
              <span v-for="(tag, i) in block.value" :key="i" class="detail-tag">#{{ tag }}</span>
            </div>

            <!-- 字符串列表 -->
            <ul v-else-if="block.kind === 'list'" class="detail-list">
              <li v-for="(item, i) in block.value" :key="i">{{ item }}</li>
            </ul>

            <!-- 对象数组（如推荐标题） -->
            <div v-else-if="block.kind === 'objects'" class="detail-titles">
              <div v-for="(pairs, i) in block.value" :key="i" class="title-item">
                <div v-for="p in pairs" :key="p.label" class="pair-row">
                  <span class="pair-label">{{ p.label }}</span>
                  <span class="pair-value">{{ p.value }}</span>
                </div>
              </div>
            </div>

            <!-- 键值对象 -->
            <div v-else-if="block.kind === 'pairs'" class="title-item">
              <div v-for="p in block.value" :key="p.label" class="pair-row">
                <span class="pair-label">{{ p.label }}</span>
                <span class="pair-value">{{ p.value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Clock, Loading, Document, ArrowRight } from '@element-plus/icons-vue'
import { marked } from 'marked'
import generationRecordApi from '@/api/generationRecord'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderMarkdown = (text) => {
  if (!text) return ''
  return marked.parse(text)
}

const router = useRouter()

const loading = ref(false)
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const currentCat = ref('')

// 详情弹窗
const showDetail = ref(false)
const detailLoading = ref(false)
const detailRecord = ref(null)

// 类型元数据：标签、分类、积分消耗
// credits 镜像后端 credit_config.py 的 base_credits；仅计费操作 > 0，
// 重评/对比/独立工具等为免费功能。
// ponytail: 静态镜像后端定价，定价若改为动态再由接口返回
const TYPE_META = {
  outline_generate:         { label: '大纲生成', cat: 'outline', credits: 3 },
  outline_reevaluate:       { label: '大纲重评', cat: 'outline', credits: 0 },
  angle_inspection:         { label: '角度体检', cat: 'outline', credits: 0 },
  title_generate:           { label: '标题生成', cat: 'title', credits: 3 },
  standalone_title:         { label: '独立标题', cat: 'title', credits: 0 },
  multi_model_title:        { label: '多模型标题', cat: 'title', credits: 0 },
  munger_generate:          { label: '芒格标题', cat: 'title', credits: 0 },
  munger_score:             { label: '标题评分', cat: 'title', credits: 0 },
  title_reevaluate:         { label: '标题重评', cat: 'title', credits: 0 },
  content_generate:         { label: '正文生成', cat: 'content', credits: 10 },
  content_polish:           { label: '文案润色', cat: 'content', credits: 8 },
  content_continuation:     { label: '正文续写', cat: 'content', credits: 1 },
  content_reevaluate:       { label: '正文重评', cat: 'content', credits: 0 },
  multi_model_polish:       { label: '多模型润色', cat: 'content', credits: 0 },
  multi_model_continuation: { label: '多模型续写', cat: 'content', credits: 0 },
  content_transform:        { label: '内容转写', cat: 'convert', credits: 2 },
  content_imitate:          { label: '内容仿写', cat: 'convert', credits: 3 },
  xhs_convert:              { label: '转小红书', cat: 'convert', credits: 0 },
}

const categories = [
  { value: '', label: '全部' },
  { value: 'outline', label: '选题大纲' },
  { value: 'title', label: '标题' },
  { value: 'content', label: '正文' },
  { value: 'convert', label: '转换' },
]

const typeLabel = (type) => TYPE_META[type]?.label || '其他'
const typeCat = (type) => TYPE_META[type]?.cat || 'other'
const typeCredits = (type) => TYPE_META[type]?.credits ?? 0

// ===== 详情可读化渲染 =====
const KEY_LABELS = {
  final_text: '正文内容', content: '正文', body: '正文', article: '正文',
  text: '内容', title: '标题', titles: '标题', recommendations: '推荐标题',
  gold_sentences: '金句', tags: '标签', outline: '大纲', summary: '摘要',
  sections: '段落', score: '评分', final_score: '评分', scores: '评分',
  method: '手法', word_count: '字数', reason: '理由', hook: '开头钩子',
  keywords: '关键词', angle: '切入角度', suggestions: '建议', comment: '点评',
  source_title: '原标题', source_content: '原文', candidates: '候选',
}
const HIDDEN_KEYS = new Set(['error', 'run_id', 'task_id', 'raw', 'prompt', 'model', 'provider', 'id', 'created_at'])
const LONG_TEXT_KEYS = new Set(['final_text', 'content', 'body', 'article', 'text', 'outline', 'summary'])

const labelOf = (k) => KEY_LABELS[k] || k

const toPairs = (obj) =>
  Object.entries(obj)
    .filter(([k, v]) => !HIDDEN_KEYS.has(k) && v != null && v !== '')
    .map(([k, v]) => ({
      label: labelOf(k),
      value: Array.isArray(v) ? v.join('、') : typeof v === 'object' ? JSON.stringify(v) : String(v),
    }))

const buildBlocks = (snapshot) => {
  const blocks = []
  for (const [k, v] of Object.entries(snapshot || {})) {
    if (HIDDEN_KEYS.has(k) || v == null || v === '') continue
    const label = labelOf(k)
    if (typeof v === 'string') {
      blocks.push({ key: k, label, kind: LONG_TEXT_KEYS.has(k) || v.length > 80 ? 'markdown' : 'text', value: v })
    } else if (typeof v === 'number' || typeof v === 'boolean') {
      blocks.push({ key: k, label, kind: 'text', value: String(v) })
    } else if (Array.isArray(v)) {
      if (v.length === 0) continue
      if (k === 'tags') blocks.push({ key: k, label, kind: 'tags', value: v })
      else if (typeof v[0] === 'object' && v[0] !== null) blocks.push({ key: k, label, kind: 'objects', value: v.map(toPairs) })
      else blocks.push({ key: k, label, kind: 'list', value: v.map(String) })
    } else if (typeof v === 'object') {
      const pairs = toPairs(v)
      if (pairs.length) blocks.push({ key: k, label, kind: 'pairs', value: pairs })
    }
  }
  return blocks
}

const detailBlocks = computed(() => {
  const r = detailRecord.value
  if (!r) return []
  const out = r.output_snapshot && Object.keys(r.output_snapshot).length ? r.output_snapshot : null
  const src = out || r.input_snapshot || {}
  return buildBlocks(src)
})

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize }
    if (currentCat.value) {
      params.type = Object.entries(TYPE_META)
        .filter(([, m]) => m.cat === currentCat.value)
        .map(([t]) => t)
        .join(',')
    }
    const res = await generationRecordApi.list(params)
    records.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    ElMessage.error('加载生成记录失败')
  } finally {
    loading.value = false
  }
}

const navigateToRecord = async (record) => {
  showDetail.value = true
  detailLoading.value = true
  detailRecord.value = null

  try {
    const res = await generationRecordApi.get(record.id)
    detailRecord.value = res.data || res
  } catch (e) {
    ElMessage.error('获取记录详情失败')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

onMounted(fetchRecords)
</script>

<style scoped>
.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }

.card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  transition: all 0.2s ease;
}

.record-card {
  cursor: pointer;
  padding: 20px 24px;
}

.record-card:hover {
  border-color: var(--clay);
  box-shadow: 0 2px 8px rgba(204, 120, 92, 0.08);
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  background: var(--paper);
  color: #6B6862;
  border: 1px solid var(--line);
  cursor: pointer;
  transition: all 0.15s;
}

.type-chip:hover {
  background: #F0EDE3;
  color: var(--ink);
}

.type-chip-active {
  background: var(--clay);
  color: #fff;
  border-color: var(--clay);
}

.type-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  background: var(--bone);
  color: var(--ink-2);
}

/* 按分类着色 */
.type-badge.cat-outline {
  background: #e8f0ea;
  color: #2d6a4f;
}

.type-badge.cat-title {
  background: #e8ecf0;
  color: #2d4a6f;
}

.type-badge.cat-content {
  background: #f0e8ee;
  color: #6a2d5f;
}

.type-badge.cat-convert {
  background: #fff3e8;
  color: #8a5a2d;
}

/* 积分消耗标签 */
.credit-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.credit-tag-cost {
  background: rgba(192, 57, 43, 0.08);
  color: #c0392b;
}

.credit-tag-free {
  background: var(--bone);
  color: var(--ink-4);
}

.status-dot {
  display: inline-flex;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.status-completed {
  background: #52c41a;
}

.status-dot.status-pending {
  background: #faad14;
}

.status-dot.status-failed {
  background: #ff4d4f;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--r-sm);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-3);
  background: transparent;
  border: 1px solid var(--line);
  cursor: pointer;
  transition: all 0.15s;
}

.btn-action:hover {
  color: var(--clay-deep);
  border-color: var(--clay);
  background: var(--clay-tint);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 详情弹窗样式 */
.detail-content {
  padding: 0;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.detail-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
  margin: 0 0 20px 0;
}

.detail-body {
  max-height: 500px;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-4);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.detail-text {
  font-size: 15px;
  line-height: 1.7;
  color: var(--ink-2);
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-titles {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.title-item {
  padding: 12px 16px;
  background: var(--bone);
  border-radius: var(--r-md);
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink);
}

.title-content {
  font-weight: 500;
  margin-bottom: 6px;
}

.detail-list {
  margin: 0;
  padding-left: 20px;
  font-size: 15px;
  line-height: 1.7;
  color: var(--ink-2);
}

.detail-list li {
  margin-bottom: 6px;
}

.pair-row {
  display: flex;
  gap: 10px;
  font-size: 14px;
  line-height: 1.6;
  padding: 3px 0;
}

.pair-row + .pair-row {
  border-top: 1px dashed var(--line);
}

.pair-label {
  flex-shrink: 0;
  min-width: 64px;
  color: var(--ink-4);
  font-weight: 600;
}

.pair-value {
  color: var(--ink-2);
  word-break: break-word;
}

.title-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--ink-4);
}

.title-method {
  background: var(--clay-tint);
  color: var(--clay-deep);
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.title-score {
  color: var(--clay-deep);
  font-weight: 600;
}

.title-words {
  color: var(--ink-3);
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-tag {
  padding: 4px 12px;
  background: var(--clay-tint);
  color: var(--clay-deep);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

/* Markdown 渲染样式 */
.markdown-body {
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink-2);
  word-break: break-word;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  font-weight: 600;
  margin: 20px 0 12px 0;
  color: var(--ink);
}

.markdown-body h1 { font-size: 20px; }
.markdown-body h2 { font-size: 18px; }
.markdown-body h3 { font-size: 16px; }

.markdown-body p {
  margin: 0 0 12px 0;
}

.markdown-body ul,
.markdown-body ol {
  margin: 0 0 12px 0;
  padding-left: 24px;
}

.markdown-body li {
  margin-bottom: 6px;
}

.markdown-body blockquote {
  border-left: 3px solid var(--clay);
  padding-left: 16px;
  margin: 16px 0;
  color: var(--ink-3);
  font-style: italic;
}

.markdown-body code {
  background: var(--bone);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.markdown-body pre {
  background: var(--bone);
  padding: 16px;
  border-radius: var(--r-md);
  overflow-x: auto;
  margin: 16px 0;
}

.markdown-body pre code {
  background: none;
  padding: 0;
}

.markdown-body strong {
  font-weight: 600;
  color: var(--ink);
}

.markdown-body em {
  font-style: italic;
}

.markdown-body a {
  color: var(--clay-deep);
  text-decoration: underline;
}

.markdown-body hr {
  border: none;
  border-top: 1px solid var(--line);
  margin: 20px 0;
}
</style>

<style>
/* 弹窗全局样式覆盖 */
.detail-dialog .el-dialog__header {
  border-bottom: 1px solid var(--line);
  padding: 16px 24px;
  margin: 0;
}

.detail-dialog .el-dialog__title {
  font-family: serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
}

.detail-dialog .el-dialog__body {
  padding: 24px;
}

.detail-dialog .el-dialog__footer {
  border-top: 1px solid var(--line);
  padding: 12px 24px;
}
</style>
