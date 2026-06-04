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
        <span class="text-sm text-ink-4" style="flex-shrink: 0;">筛选：</span>
        <button
          v-for="t in typeOptions"
          :key="t.value"
          :class="['type-chip', { 'type-chip-active': currentType === t.value }]"
          @click="currentType = t.value; fetchRecords()"
        >
          {{ t.label }}
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
            <span :class="['type-badge', `type-${record.type}`]">
              {{ typeLabel(record.type) }}
            </span>
            <!-- 状态指示器 -->
            <span :class="['status-dot', `status-${record.status}`]"></span>
            <!-- 标题 -->
            <span class="text-ink font-serif" style="font-weight: 500; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">
              {{ record.display_title || '未命名' }}
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 16px; flex-shrink: 0;">
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
          <span :class="['type-badge', `type-${detailRecord.type}`]">
            {{ typeLabel(detailRecord.type) }}
          </span>
          <span :class="['status-dot', `status-${detailRecord.status}`]"></span>
          <span class="text-sm text-ink-4 font-serif">{{ formatTime(detailRecord.created_at) }}</span>
        </div>

        <!-- 标题 -->
        <h2 class="font-serif detail-title">{{ detailRecord.display_title || '未命名' }}</h2>

        <!-- 内容 -->
        <div class="detail-body font-serif">
          <!-- 有输出内容 -->
          <template v-if="detailRecord.output_snapshot && Object.keys(detailRecord.output_snapshot).length > 0">
            <!-- 标题生成结果 -->
            <template v-if="detailRecord.type === 'title_generate'">
              <div v-if="detailRecord.output_snapshot.recommendations && detailRecord.output_snapshot.recommendations.length" class="detail-section">
                <div class="detail-label">推荐标题</div>
                <div class="detail-titles">
                  <div v-for="(item, i) in detailRecord.output_snapshot.recommendations" :key="i" class="title-item">
                    <div class="title-content">{{ item.title }}</div>
                    <div class="title-meta">
                      <span v-if="item.method" class="title-method">{{ item.method }}</span>
                      <span v-if="item.final_score" class="title-score">{{ item.final_score.toFixed(1) }}分</span>
                      <span v-if="item.word_count" class="title-words">{{ item.word_count }}字</span>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="detail-text">{{ JSON.stringify(detailRecord.output_snapshot, null, 2) }}</div>
            </template>

            <!-- 正文生成结果 -->
            <template v-else-if="detailRecord.type === 'content_generate'">
              <div v-if="detailRecord.output_snapshot.final_text" class="detail-section">
                <div class="detail-label">生成的正文</div>
                <div class="markdown-body" v-html="renderMarkdown(detailRecord.output_snapshot.final_text)"></div>
              </div>
              <div v-else-if="detailRecord.output_snapshot.gold_sentences" class="detail-section">
                <div class="detail-label">金句</div>
                <div class="detail-text">{{ JSON.stringify(detailRecord.output_snapshot.gold_sentences, null, 2) }}</div>
              </div>
              <div v-else class="detail-text">{{ JSON.stringify(detailRecord.output_snapshot, null, 2) }}</div>
            </template>

            <!-- 转写/仿写结果 -->
            <template v-else-if="detailRecord.type === 'content_transform' || detailRecord.type === 'content_imitate'">
              <div v-if="detailRecord.output_snapshot.title" class="detail-section">
                <div class="detail-label">标题</div>
                <div class="detail-text">{{ detailRecord.output_snapshot.title }}</div>
              </div>
              <div v-if="detailRecord.output_snapshot.content" class="detail-section">
                <div class="detail-label">正文</div>
                <div class="markdown-body" v-html="renderMarkdown(detailRecord.output_snapshot.content)"></div>
              </div>
              <div v-if="detailRecord.output_snapshot.tags && detailRecord.output_snapshot.tags.length" class="detail-section">
                <div class="detail-label">标签</div>
                <div class="detail-tags">
                  <span v-for="tag in detailRecord.output_snapshot.tags" :key="tag" class="detail-tag">#{{ tag }}</span>
                </div>
              </div>
            </template>

            <!-- 其他类型 -->
            <template v-else>
              <div class="detail-text">{{ JSON.stringify(detailRecord.output_snapshot, null, 2) }}</div>
            </template>
          </template>

          <!-- 无输出内容，显示输入信息 -->
          <template v-else>
            <div v-if="detailRecord.input_snapshot && Object.keys(detailRecord.input_snapshot).length > 0" class="detail-section">
              <div class="detail-label">输入信息</div>
              <div class="detail-text">{{ JSON.stringify(detailRecord.input_snapshot, null, 2) }}</div>
            </div>
            <div v-else class="detail-text text-ink-4" style="text-align: center; padding: 40px 0;">
              暂无输出内容
            </div>
          </template>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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
const currentType = ref('')

// 详情弹窗
const showDetail = ref(false)
const detailLoading = ref(false)
const detailRecord = ref(null)

const typeOptions = [
  { value: '', label: '全部' },
  { value: 'title_generate', label: '标题生成' },
  { value: 'content_generate', label: '正文生成' },
  { value: 'content_transform', label: '内容转写' },
  { value: 'content_imitate', label: '内容仿写' },
]

const typeLabels = {
  title_generate: '标题生成',
  content_generate: '正文生成',
  content_transform: '内容转写',
  content_imitate: '内容仿写',
  // 旧数据兼容
  outline_generate: '大纲生成',
  outline_reevaluate: '大纲重评',
  title_reevaluate: '标题重评',
  content_reevaluate: '正文重评',
  munger_generate: '芒格标题',
  munger_score: '标题评分',
  xhs_convert: '转小红书',
  angle_inspection: '角度体检',
}

const typeLabel = (type) => typeLabels[type] || '其他'

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
    if (currentType.value) params.type = currentType.value
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

.type-badge.type-title_generate {
  background: #e8ecf0;
  color: #2d4a6f;
}

.type-badge.type-content_generate {
  background: #f0e8ee;
  color: #6a2d5f;
}

.type-badge.type-content_transform {
  background: #fff3e8;
  color: #8a5a2d;
}

.type-badge.type-content_imitate {
  background: #e8f8f0;
  color: #2d6a4f;
}

/* 旧数据类型标签 */
.type-badge.type-outline_generate,
.type-badge.type-outline_reevaluate {
  background: #e8f0ea;
  color: #2d6a4f;
}

.type-badge.type-title_reevaluate {
  background: #e8ecf0;
  color: #2d4a6f;
}

.type-badge.type-content_reevaluate {
  background: #f0e8ee;
  color: #6a2d5f;
}

.type-badge.type-munger_generate,
.type-badge.type-munger_score {
  background: #f0ece8;
  color: #6a4a2d;
}

.type-badge.type-xhs_convert {
  background: #ffe8e8;
  color: #c43e3e;
}

.type-badge.type-angle_inspection {
  background: #e8f0f0;
  color: #2d5f6a;
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
