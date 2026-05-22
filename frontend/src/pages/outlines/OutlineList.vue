<template>
  <div class="outline-list">
    <!-- 页面标题和操作栏 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-h2 font-serif text-ink">大纲管理</h1>
        <p class="text-ink-3 mt-1">AI 生成的大纲，含评审和自检评分</p>
      </div>
      <div class="flex space-x-3">
        <el-button type="success" :loading="generating" @click="showGenerateDialog = true">
          <el-icon><MagicStick /></el-icon>
          生成大纲
        </el-button>
        <el-button @click="showStats = true">
          <el-icon><DataAnalysis /></el-icon>
          统计
        </el-button>
        <el-button type="primary" @click="showFilters = !showFilters">
          <el-icon><Filter /></el-icon>
          筛选
        </el-button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <el-collapse-transition>
      <div v-show="showFilters" class="card p-4 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="label">状态筛选</label>
            <el-select v-model="filters.passed" placeholder="选择状态" clearable class="w-full">
              <el-option label="✅ 通过" value="passed" />
              <el-option label="❌ 未通过" value="failed" />
              <el-option label="⏳ 待处理" value="pending" />
            </el-select>
          </div>

          <div>
            <label class="label">方向筛选</label>
            <el-select v-model="filters.direction" placeholder="选择方向" clearable class="w-full">
              <el-option v-for="d in directions" :key="d" :label="d" :value="d" />
            </el-select>
          </div>

          <div>
            <label class="label">最低分数</label>
            <el-input-number v-model="filters.min_score" :min="0" :max="10" :step="0.5" class="w-full" />
          </div>

          <div>
            <label class="label">关键词搜索</label>
            <el-input v-model="filters.keyword" placeholder="输入关键词" clearable />
          </div>
        </div>

        <div class="flex justify-end mt-4">
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="primary" @click="applyFilters">应用筛选</el-button>
        </div>
      </div>
    </el-collapse-transition>

    <!-- 大纲列表 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <div v-else-if="outlines.length === 0" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">暂无大纲</h3>
      <p class="text-ink-3 mt-1">需要先生成大纲</p>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="outline in outlines"
        :key="outline.id"
        class="card-hover cursor-pointer"
        @click="viewOutline(outline)"
      >
        <div class="p-4">
          <div class="flex items-start justify-between">
            <!-- 左侧内容 -->
            <div class="flex-1">
              <!-- 标题和状态 -->
              <div class="flex items-center gap-2 mb-2">
                <span class="status-badge" :class="getStatusClass(outline.passed)">
                  {{ getStatusIcon(outline.passed) }}
                </span>
                <h3 class="text-lg font-semibold text-ink">
                  {{ outline.title }}
                </h3>
              </div>

              <!-- 元信息 -->
              <div class="flex flex-wrap gap-4 text-sm text-ink-3 mb-3">
                <span v-if="outline.direction" class="flex items-center">
                  <el-icon class="mr-1"><Compass /></el-icon>
                  {{ outline.direction }}
                </span>
                <span v-if="outline.routine" class="flex items-center">
                  <el-icon class="mr-1"><List /></el-icon>
                  {{ outline.routine }}
                </span>
                <span class="flex items-center">
                  <el-icon class="mr-1"><Document /></el-icon>
                  {{ outline.section_count }} 节
                </span>
                <span class="flex items-center">
                  <el-icon class="mr-1"><Edit /></el-icon>
                  {{ outline.total_words }} 字
                </span>
              </div>

              <!-- 大纲预览 -->
              <div v-if="outline.sections && outline.sections.length > 0" class="mt-3">
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="(section, index) in outline.sections.slice(0, 3)"
                    :key="index"
                    class="text-xs bg-ivory text-ink-2 px-2 py-1 rounded"
                  >
                    节{{ section.section_number }}: {{ section.title }}
                  </span>
                  <span v-if="outline.sections.length > 3" class="text-xs text-ink-3">
                    +{{ outline.sections.length - 3 }} 节
                  </span>
                </div>
              </div>
            </div>

            <!-- 右侧评分 -->
            <div class="ml-4 flex flex-col items-end">
              <div class="text-2xl font-bold" :class="getScoreColor(outline.total_score)">
                {{ outline.total_score.toFixed(1) }}
              </div>
              <div class="text-xs text-ink-3">自检评分</div>
              
              <!-- 生成信息 -->
              <div v-if="outline.generation_process" class="mt-2 text-xs text-ink-3">
                <div>尝试 {{ outline.generation_process.attempts }} 次</div>
                <div>{{ outline.created_at ? formatDate(outline.created_at) : '' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="flex justify-center mt-6">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="fetchOutlines"
        @size-change="fetchOutlines"
      />
    </div>

    <!-- 生成大纲对话框 -->
    <el-dialog v-model="showGenerateDialog" title="生成大纲" width="500px">
      <el-form :model="generateForm" label-width="100px">
        <el-form-item label="选题候选ID" required>
          <el-input v-model="generateForm.candidate_id" placeholder="输入选题候选ID" />
        </el-form-item>
        <el-form-item label="模型选择">
          <el-select v-model="generateForm.model" placeholder="选择模型" clearable class="w-full">
            <el-option label="默认模型" value="" />
            <el-option label="Claude 3 Sonnet" value="claude-3-sonnet" />
            <el-option label="Claude 3 Opus" value="claude-3-opus" />
            <el-option label="GPT-4" value="gpt-4" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="generateOutline">
          生成
        </el-button>
      </template>
    </el-dialog>

    <!-- 统计对话框 -->
    <el-dialog v-model="showStats" title="大纲统计" width="600px">
      <div v-if="stats" class="grid grid-cols-2 gap-4">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总大纲数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value text-green-600">{{ stats.passed }}</div>
          <div class="stat-label">通过</div>
        </div>
        <div class="stat-card">
          <div class="stat-value text-red-600">{{ stats.failed }}</div>
          <div class="stat-label">未通过</div>
        </div>
        <div class="stat-card">
          <div class="stat-value text-yellow-600">{{ stats.pending }}</div>
          <div class="stat-label">待处理</div>
        </div>
        <div class="stat-card col-span-2">
          <div class="stat-value">{{ stats.average_score }}</div>
          <div class="stat-label">平均分数</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showStats = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  MagicStick, DataAnalysis, Filter, Loading, Document,
  Compass, List, Edit
} from '@element-plus/icons-vue'
import outlineApi from '@/api/outline'

const router = useRouter()

// 状态
const loading = ref(false)
const generating = ref(false)
const outlines = ref([])
const stats = ref(null)

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 筛选
const showFilters = ref(false)
const filters = ref({
  passed: '',
  direction: '',
  min_score: null,
  keyword: ''
})

// 对话框
const showGenerateDialog = ref(false)
const showStats = ref(false)
const generateForm = ref({
  candidate_id: '',
  model: ''
})

// 方向列表
const directions = [
  '实践型',
  '解决问题型',
  '教程型',
  '观点型',
  '整活型',
  '资讯型'
]

// 获取大纲列表
const fetchOutlines = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ...filters.value
    }
    
    // 移除空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })
    
    const response = await outlineApi.getOutlines(params)
    outlines.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('获取大纲列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 获取统计信息
const fetchStats = async () => {
  try {
    const response = await outlineApi.getStats()
    stats.value = response.data
  } catch (error) {
    ElMessage.error('获取统计信息失败')
    console.error(error)
  }
}

// 生成大纲
const generateOutline = async () => {
  if (!generateForm.value.candidate_id) {
    ElMessage.warning('请输入选题候选ID')
    return
  }
  
  generating.value = true
  try {
    const response = await outlineApi.generateOutline(generateForm.value)
    ElMessage.success('大纲生成成功')
    showGenerateDialog.value = false
    generateForm.value = { candidate_id: '', model: '' }
    fetchOutlines()
  } catch (error) {
    ElMessage.error('大纲生成失败')
    console.error(error)
  } finally {
    generating.value = false
  }
}

// 查看大纲详情
const viewOutline = (outline) => {
  router.push(`/outlines/${outline.id}`)
}

// 重置筛选
const resetFilters = () => {
  filters.value = {
    passed: '',
    direction: '',
    min_score: null,
    keyword: ''
  }
  currentPage.value = 1
  fetchOutlines()
}

// 应用筛选
const applyFilters = () => {
  currentPage.value = 1
  fetchOutlines()
}

// 获取状态样式
const getStatusClass = (passed) => {
  switch (passed) {
    case 'passed': return 'status-passed'
    case 'failed': return 'status-failed'
    default: return 'status-pending'
  }
}

// 获取状态图标
const getStatusIcon = (passed) => {
  switch (passed) {
    case 'passed': return '✅'
    case 'failed': return '❌'
    default: return '⏳'
  }
}

// 获取分数颜色
const getScoreColor = (score) => {
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-yellow-600'
  return 'text-red-600'
}

// 格式化日期
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 初始化
onMounted(() => {
  fetchOutlines()
  fetchStats()
})
</script>

<style scoped>
.status-badge {
  @apply text-lg;
}

.status-passed {
  @apply text-green-600;
}

.status-failed {
  @apply text-red-600;
}

.status-pending {
  @apply text-yellow-600;
}

.stat-card {
  @apply p-4 bg-ivory rounded-lg text-center;
}

.stat-value {
  @apply text-2xl font-bold;
}

.stat-label {
  @apply text-sm text-ink-3 mt-1;
}
</style>
