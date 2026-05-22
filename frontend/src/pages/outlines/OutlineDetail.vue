<template>
  <div class="outline-detail">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center">
        <el-button @click="goBack" class="mr-4">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div>
          <h1 class="text-h2 font-serif text-ink">{{ outline.title }}</h1>
          <p class="text-ink-3 mt-1">大纲详情</p>
        </div>
      </div>
      <div class="flex items-center space-x-4">
        <span class="status-badge" :class="getStatusClass(outline.passed)">
          {{ getStatusIcon(outline.passed) }}
          {{ getStatusText(outline.passed) }}
        </span>
        <div class="text-3xl font-bold" :class="getScoreColor(outline.total_score)">
          {{ outline.total_score?.toFixed(1) || '0.0' }}
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <!-- 大纲内容 -->
    <div v-else-if="outline.id" class="space-y-6">
      <!-- 基本信息卡片 -->
      <div class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">基本信息</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div class="text-sm text-ink-3">方向</div>
            <div class="text-ink font-medium">{{ outline.direction || '-' }}</div>
          </div>
          <div>
            <div class="text-sm text-ink-3">套路</div>
            <div class="text-ink font-medium">{{ outline.routine || '-' }}</div>
          </div>
          <div>
            <div class="text-sm text-ink-3">节数</div>
            <div class="text-ink font-medium">{{ outline.section_count }} 节</div>
          </div>
          <div>
            <div class="text-sm text-ink-3">总字数</div>
            <div class="text-ink font-medium">{{ outline.total_words }} 字</div>
          </div>
        </div>
      </div>

      <!-- 大纲内容卡片 -->
      <div class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">大纲内容</h3>
        <div class="space-y-4">
          <div
            v-for="section in outline.sections"
            :key="section.section_number"
            class="section-card"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-sm font-bold text-ink-2">节{{ section.section_number }}</span>
                  <h4 class="text-lg font-semibold text-ink">{{ section.title }}</h4>
                </div>
                
                <!-- 核心信息点 -->
                <div v-if="section.core_points && section.core_points.length > 0" class="mb-3">
                  <div class="text-sm text-ink-3 mb-1">核心信息点：</div>
                  <ul class="list-disc list-inside space-y-1">
                    <li v-for="(point, index) in section.core_points" :key="index" class="text-ink text-sm">
                      {{ point }}
                    </li>
                  </ul>
                </div>

                <!-- 备注 -->
                <div v-if="section.notes" class="text-sm text-ink-3 italic">
                  备注：{{ section.notes }}
                </div>
              </div>

              <div class="ml-4 flex flex-col items-end">
                <!-- 字数 -->
                <div class="text-sm text-ink-3">
                  {{ section.word_count }} 字
                </div>

                <!-- 传播标签 -->
                <div v-if="section.propagation_tags && section.propagation_tags.length > 0" class="mt-2">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="tag in section.propagation_tags"
                      :key="tag"
                      class="tag"
                    >
                      {{ tag }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 生成过程卡片 -->
      <div v-if="outline.generation_process && Object.keys(outline.generation_process).length > 0" class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">生成过程</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div class="text-sm text-ink-3">尝试次数</div>
            <div class="text-ink font-medium">{{ outline.generation_process.attempts }} 次</div>
          </div>
          <div>
            <div class="text-sm text-ink-3">选中候选</div>
            <div class="text-ink font-medium">候选 {{ outline.generation_process.selected_candidate }}</div>
          </div>
          <div>
            <div class="text-sm text-ink-3">问题节数</div>
            <div class="text-ink font-medium">{{ outline.generation_process.problem_sections_count }} 节</div>
          </div>
          <div>
            <div class="text-sm text-ink-3">创建时间</div>
            <div class="text-ink font-medium">{{ formatDate(outline.created_at) }}</div>
          </div>
        </div>
        
        <!-- 评审理由 -->
        <div v-if="outline.generation_process.review_reason" class="mt-4">
          <div class="text-sm text-ink-3 mb-1">评审理由：</div>
          <div class="text-ink bg-ivory p-3 rounded">{{ outline.generation_process.review_reason }}</div>
        </div>
        
        <!-- 读者反馈 -->
        <div v-if="outline.generation_process.criticism" class="mt-4">
          <div class="text-sm text-ink-3 mb-1">读者反馈：</div>
          <div class="text-ink bg-ivory p-3 rounded">{{ outline.generation_process.criticism }}</div>
        </div>
      </div>

      <!-- 自检评分明细卡片 -->
      <div v-if="outline.inspection_score && Object.keys(outline.inspection_score).length > 0" class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">自检评分明细</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div v-for="(score, dimension) in outline.inspection_score" :key="dimension" class="score-card">
            <div class="flex items-center justify-between mb-2">
              <div class="text-sm font-medium text-ink">{{ getDimensionName(dimension) }}</div>
              <div class="text-lg font-bold" :class="getScoreColor(score.score)">
                {{ score.score }}
              </div>
            </div>
            <div class="text-xs text-ink-3">{{ score.evidence }}</div>
          </div>
        </div>
      </div>

      <!-- 候选大纲卡片 -->
      <div v-if="outline.candidates && outline.candidates.length > 0" class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">候选大纲</h3>
        <el-tabs v-model="activeCandidate">
          <el-tab-pane
            v-for="candidate in outline.candidates"
            :key="candidate.candidate_number"
            :label="`候选 ${candidate.candidate_number}`"
            :name="candidate.candidate_number"
          >
            <div class="space-y-4">
              <div class="flex items-center gap-4">
                <div>
                  <div class="text-sm text-ink-3">开头钩子类型</div>
                  <div class="text-ink font-medium">{{ candidate.hook_type }}</div>
                </div>
                <div>
                  <div class="text-sm text-ink-3">总字数</div>
                  <div class="text-ink font-medium">{{ candidate.total_words }} 字</div>
                </div>
              </div>
              
              <div>
                <div class="text-sm text-ink-3 mb-1">骨架特点：</div>
                <div class="text-ink bg-ivory p-3 rounded">{{ candidate.skeleton_feature }}</div>
              </div>

              <div v-if="candidate.sections && candidate.sections.length > 0">
                <div class="text-sm text-ink-3 mb-2">大纲内容：</div>
                <div class="space-y-2">
                  <div
                    v-for="section in candidate.sections"
                    :key="section.section_number"
                    class="bg-ivory p-3 rounded"
                  >
                    <div class="font-medium text-ink">
                      节{{ section.section_number }}: {{ section.title }}
                    </div>
                    <div class="text-sm text-ink-3 mt-1">
                      {{ section.core_points?.join(' | ') || '-' }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 评审记录卡片 -->
      <div v-if="outline.review" class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">评审记录</h3>
        <div class="space-y-4">
          <div>
            <div class="text-sm text-ink-3 mb-1">选中候选：</div>
            <div class="text-ink font-medium">候选 {{ outline.review.selected_candidate }}</div>
          </div>
          <div>
            <div class="text-sm text-ink-3 mb-1">评审理由：</div>
            <div class="text-ink bg-ivory p-3 rounded">{{ outline.review.review_reason }}</div>
          </div>
        </div>
      </div>

      <!-- 读者挑刺记录卡片 -->
      <div v-if="outline.criticism" class="card p-6">
        <h3 class="text-h4 font-sans text-ink mb-4">读者挑刺记录</h3>
        <div class="space-y-4">
          <div>
            <div class="text-sm text-ink-3 mb-1">整体感受：</div>
            <div class="text-ink bg-ivory p-3 rounded">{{ outline.criticism.overall_feeling }}</div>
          </div>
          
          <div v-if="outline.criticism.problem_sections && outline.criticism.problem_sections.length > 0">
            <div class="text-sm text-ink-3 mb-2">问题节：</div>
            <div class="space-y-2">
              <div
                v-for="problem in outline.criticism.problem_sections"
                :key="problem.section_number"
                class="bg-red-50 p-3 rounded border-l-4 border-red-400"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-bold text-red-600">节{{ problem.section_number }}</span>
                  <span class="text-sm text-red-500">{{ problem.problem_type }}</span>
                </div>
                <div class="text-sm text-ink">{{ problem.feedback }}</div>
                <div class="text-sm text-ink-3 mt-1">建议：{{ problem.suggestion }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">大纲不存在</h3>
      <p class="text-ink-3 mt-1">请检查大纲ID是否正确</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Loading, Document } from '@element-plus/icons-vue'
import outlineApi from '@/api/outline'

const router = useRouter()
const route = useRoute()

// 状态
const loading = ref(false)
const outline = ref({})
const activeCandidate = ref(1)

// 获取大纲详情
const fetchOutline = async () => {
  const outlineId = route.params.id
  if (!outlineId) {
    ElMessage.error('缺少大纲ID')
    return
  }

  loading.value = true
  try {
    const response = await outlineApi.getOutline(outlineId)
    outline.value = response.data
  } catch (error) {
    ElMessage.error('获取大纲详情失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 返回列表
const goBack = () => {
  router.push('/outlines')
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

// 获取状态文本
const getStatusText = (passed) => {
  switch (passed) {
    case 'passed': return '通过'
    case 'failed': return '未通过'
    default: return '待处理'
  }
}

// 获取分数颜色
const getScoreColor = (score) => {
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-yellow-600'
  return 'text-red-600'
}

// 获取维度名称
const getDimensionName = (dimension) => {
  const names = {
    hook: '开头钩子强度',
    value_ladder: '价值阶梯递进',
    rhythm: '节奏感',
    title_scan: '小标题扫读友好度',
    trigger: '传播触发点完整度',
    length: '长度与节数匹配'
  }
  return names[dimension] || dimension
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 初始化
onMounted(() => {
  fetchOutline()
})
</script>

<style scoped>
.section-card {
  @apply bg-ivory p-4 rounded-lg;
}

.tag {
  @apply text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded;
}

.score-card {
  @apply bg-ivory p-4 rounded-lg;
}

.status-badge {
  @apply px-3 py-1 rounded-full text-sm font-medium;
}

.status-passed {
  @apply bg-green-100 text-green-700;
}

.status-failed {
  @apply bg-red-100 text-red-700;
}

.status-pending {
  @apply bg-yellow-100 text-yellow-700;
}
</style>
