<template>
  <div class="generation-history">
    <!-- 页面标题和操作栏 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-h2 font-serif text-ink">生成记录</h1>
        <p class="text-ink-3 mt-1">查看所有 AI 生成历史，点击可恢复到对应页面继续创作</p>
      </div>
      <el-button @click="fetchRecords" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 类型筛选 -->
    <div class="flex gap-2 mb-4 flex-wrap">
      <el-button
        v-for="t in typeOptions"
        :key="t.value"
        :type="currentType === t.value ? 'primary' : ''"
        size="small"
        round
        @click="currentType = t.value; fetchRecords()"
      >
        {{ t.label }}
      </el-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">暂无生成记录</h3>
      <p class="text-ink-3 mt-1">使用各功能生成内容后，记录会自动出现在这里</p>
    </div>

    <!-- 记录列表 -->
    <div v-else class="space-y-3">
      <div
        v-for="record in records"
        :key="record.id"
        class="record-card"
        @click="navigateToRecord(record)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <!-- 类型标签 -->
            <span :class="['type-badge', `type-${record.type}`]">
              {{ typeLabel(record.type) }}
            </span>
            <!-- 状态指示器 -->
            <span :class="['status-dot', `status-${record.status}`]"></span>
            <!-- 标题 -->
            <span class="text-ink font-medium truncate flex-1">
              {{ record.display_title || '未命名' }}
            </span>
          </div>
          <div class="flex items-center gap-4 flex-shrink-0">
            <span class="text-ink-3 text-sm">{{ formatTime(record.created_at) }}</span>
            <el-button size="small" type="primary" plain @click.stop="navigateToRecord(record)">
              <el-icon><Right /></el-icon>
              继续创作
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-6">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchRecords"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Loading, Document, Right } from '@element-plus/icons-vue'
import generationRecordApi from '@/api/generationRecord'

const router = useRouter()

const loading = ref(false)
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const currentType = ref('')

const typeOptions = [
  { value: '', label: '全部' },
  { value: 'angle_inspection', label: '角度体检' },
  { value: 'outline_generate', label: '大纲生成' },
  { value: 'outline_reevaluate', label: '大纲重评' },
  { value: 'title_generate', label: '标题生成' },
  { value: 'title_reevaluate', label: '标题重评' },
  { value: 'content_generate', label: '正文生成' },
  { value: 'content_reevaluate', label: '正文重评' },
  { value: 'munger_generate', label: '芒格标题' },
  { value: 'munger_score', label: '标题评分' },
  { value: 'xhs_convert', label: '转小红书' },
]

const typeLabels = {
  angle_inspection: '角度体检',
  outline_generate: '大纲生成',
  outline_reevaluate: '大纲重评',
  title_generate: '标题生成',
  title_reevaluate: '标题重评',
  content_generate: '正文生成',
  content_reevaluate: '正文重评',
  munger_generate: '芒格标题',
  munger_score: '标题评分',
  xhs_convert: '转小红书',
}

const typeLabel = (type) => typeLabels[type] || type

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

const navigateToRecord = (record) => {
  const ctx = record.resume_context
  if (!ctx || !ctx.route) {
    ElMessage.warning('此记录无法跳转')
    return
  }
  router.push({
    path: ctx.route,
    query: { ...ctx.query, record_id: record.id },
  })
}

onMounted(fetchRecords)
</script>

<style scoped>
.generation-history {
  max-width: 960px;
  margin: 0 auto;
}

.record-card {
  padding: 16px 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.record-card:hover {
  border-color: var(--clay);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.type-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  background: #f0ede8;
  color: var(--ink-2);
}

.type-badge.type-outline_generate,
.type-badge.type-outline_reevaluate {
  background: #e8f0ea;
  color: #2d6a4f;
}

.type-badge.type-title_generate,
.type-badge.type-title_reevaluate {
  background: #e8ecf0;
  color: #2d4a6f;
}

.type-badge.type-content_generate,
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
  display: inline-block;
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
</style>
