<template>
  <div class="topic-candidate-list">
    <!-- 页面标题和操作栏 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-h2 font-serif text-ink">候选选题清单</h1>
        <p class="text-ink-3 mt-1">AI 挖掘的候选选题，含评分和判定</p>
      </div>
      <div class="flex space-x-3">
        <el-button type="success" :loading="mining" @click="triggerMining">
          <el-icon><MagicStick /></el-icon>
          挖掘选题
        </el-button>
        <el-button @click="showDailyList = true">
          <el-icon><Calendar /></el-icon>
          每日清单
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
            <label class="label">判定筛选</label>
            <el-select v-model="filters.verdict" placeholder="选择判定" clearable class="w-full">
              <el-option label="✅ 入选" value="selected" />
              <el-option label="⏳ 备选" value="backup" />
              <el-option label="❌ 淘汰" value="rejected" />
              <el-option label="🚫 否决" value="vetoed" />
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

    <!-- 候选选题列表 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <div v-else-if="candidates.length === 0" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">暂无候选选题</h3>
      <p class="text-ink-3 mt-1">需要先运行选题挖掘任务</p>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="candidate in candidates"
        :key="candidate.id"
        class="card-hover cursor-pointer"
        @click="viewCandidate(candidate)"
      >
        <div class="p-4">
          <div class="flex items-start justify-between">
            <!-- 左侧内容 -->
            <div class="flex-1">
              <!-- 标题和判定 -->
              <div class="flex items-center gap-2 mb-2">
                <span class="verdict-badge" :class="getVerdictClass(candidate.verdict)">
                  {{ getVerdictIcon(candidate.verdict) }}
                </span>
                <h3 class="text-lg font-semibold text-ink">
                  {{ candidate.title }}
                </h3>
                <span v-if="candidate.persona_divergence_flag" class="text-orange-500" title="Persona 分歧度高">
                  ⚠️
                </span>
              </div>

              <!-- 标签行 -->
              <div class="flex flex-wrap gap-2 mb-3">
                <span class="badge-info text-xs">{{ candidate.direction || '未分类' }}</span>
                <span class="badge-primary text-xs">{{ candidate.routine }}</span>
                <span
                  v-for="dim in (candidate.dimension_combo || []).slice(0, 2)"
                  :key="dim"
                  class="badge-secondary text-xs"
                >
                  {{ dim }}
                </span>
              </div>

              <!-- 价值承诺 -->
              <p class="text-ink-3 text-sm mb-3">{{ candidate.value_promise }}</p>

              <!-- Persona 评议摘要 -->
              <div class="flex gap-4 text-xs text-ink-4">
                <span v-for="pr in (candidate.persona_reviews || []).slice(0, 4)" :key="pr.persona">
                  {{ pr.persona }}: <span class="font-semibold">{{ pr.score }}</span>
                </span>
              </div>
            </div>

            <!-- 右侧评分 -->
            <div class="ml-4 text-right flex-shrink-0">
              <div class="text-3xl font-bold" :class="getScoreColor(candidate.weighted_score)">
                {{ candidate.weighted_score?.toFixed(1) || '-' }}
              </div>
              <div class="text-xs text-ink-3 mt-1">加权总分</div>

              <!-- 一票否决状态 -->
              <div v-if="!candidate.veto_passed" class="mt-2">
                <span class="badge-danger text-xs">一票否决</span>
              </div>

              <!-- 生成大纲按钮 -->
              <div class="mt-3">
                <el-button
                  type="primary"
                  size="small"
                  @click.stop="generateOutline(candidate)"
                  :loading="generatingOutlineId === candidate.id"
                >
                  <el-icon><Document /></el-icon>
                  生成大纲
                </el-button>
              </div>
            </div>
          </div>

          <!-- 评分明细（展开时显示） -->
          <div v-if="expandedId === candidate.id && candidate.score" class="mt-4 pt-4 border-t border-ink-1">
            <div class="grid grid-cols-3 md:grid-cols-6 gap-4">
              <div v-for="(dim, key) in dimensionLabels" :key="key" class="text-center">
                <div class="text-sm text-ink-3">{{ dim }}</div>
                <div class="text-lg font-semibold">{{ candidate.score[key]?.toFixed(1) || '-' }}</div>
              </div>
            </div>
            <div v-if="candidate.score.evidence" class="mt-3 text-xs text-ink-4">
              <div v-for="(ev, key) in candidate.score.evidence" :key="key" class="mb-1">
                <span class="font-semibold">{{ dimensionLabels[key] }}:</span> {{ ev }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="candidates.length > 0" class="flex justify-center mt-8">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 每日清单弹窗 -->
    <el-dialog v-model="showDailyList" title="每日选题清单" width="600px">
      <div class="mb-4">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="loadDailyList"
        />
      </div>

      <div v-if="dailyListLoading" class="text-center py-8">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>

      <div v-else-if="dailyList">
        <div class="mb-4">
          <span class="text-ink-3">共 {{ dailyList.items?.length || 0 }} 个选题</span>
          <span class="ml-4 text-ink-3">
            方向分布:
            <span v-for="(count, dir) in dailyList.direction_distribution" :key="dir" class="ml-2">
              {{ dir }}: {{ count }}
            </span>
          </span>
        </div>

        <div class="space-y-3">
          <div
            v-for="item in dailyList.items"
            :key="item.candidate_id"
            class="flex items-center gap-3 p-3 bg-ink-0 rounded"
          >
            <span class="text-lg font-bold text-ink-2 w-8">{{ item.rank }}</span>
            <div class="flex-1">
              <div class="font-semibold">{{ item.title }}</div>
              <div class="text-sm text-ink-3">{{ item.direction }} · {{ item.score?.toFixed(1) }}分</div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-8 text-ink-3">
        该日期暂无选题清单
      </div>

      <template #footer>
        <el-button @click="generateDailyList" :loading="generating">
          生成今日清单
        </el-button>
        <el-button @click="showDailyList = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 统计弹窗 -->
    <el-dialog v-model="showStats" title="候选选题统计" width="500px">
      <div v-if="statsLoading" class="text-center py-8">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>

      <div v-else-if="stats">
        <div class="grid grid-cols-2 gap-4 mb-6">
          <div class="text-center p-4 bg-ink-0 rounded">
            <div class="text-3xl font-bold text-ink">{{ stats.total }}</div>
            <div class="text-sm text-ink-3">总候选数</div>
          </div>
          <div class="text-center p-4 bg-green-50 rounded">
            <div class="text-3xl font-bold text-green-600">{{ stats.selected }}</div>
            <div class="text-sm text-ink-3">入选</div>
          </div>
          <div class="text-center p-4 bg-yellow-50 rounded">
            <div class="text-3xl font-bold text-yellow-600">{{ stats.backup }}</div>
            <div class="text-sm text-ink-3">备选</div>
          </div>
          <div class="text-center p-4 bg-red-50 rounded">
            <div class="text-3xl font-bold text-red-600">{{ stats.rejected + stats.vetoed }}</div>
            <div class="text-sm text-ink-3">淘汰/否决</div>
          </div>
        </div>

        <h4 class="font-semibold mb-3">按方向分布</h4>
        <div class="space-y-2">
          <div v-for="(count, dir) in stats.by_direction" :key="dir" class="flex items-center gap-2">
            <span class="w-24 text-sm text-ink-3">{{ dir }}</span>
            <div class="flex-1 bg-ink-1 rounded-full h-4">
              <div
                class="bg-primary-500 rounded-full h-4"
                :style="{ width: `${(count / stats.total) * 100}%` }"
              />
            </div>
            <span class="w-8 text-sm text-right">{{ count }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="showStats = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Calendar,
  DataAnalysis,
  Filter,
  Loading,
  Document,
  MagicStick,
} from '@element-plus/icons-vue'
import { get, post } from '@/api/api'

const router = useRouter()

// 状态
const loading = ref(false)
const showFilters = ref(false)
const showDailyList = ref(false)
const showStats = ref(false)
const expandedId = ref(null)

// 候选列表
const candidates = ref([])

// 挖掘状态
const mining = ref(false)

// 生成大纲状态
const generatingOutlineId = ref(null)

// 筛选
const filters = reactive({
  verdict: '',
  direction: '',
  min_score: null,
  keyword: '',
  sort_by: 'weighted_score',
  sort_order: 'desc',
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// 方向列表
const directions = ['大模型', 'Coding Agent', 'AI视频', 'AI绘画', 'AI音频', '效率工具', '观点型', '实践型', '教程型', '解决问题型', '资讯型', '整活型']

// 维度标签
const dimensionLabels = {
  pain_point: '痛点直击',
  value_density: '价值密度',
  propagation: '传播触发',
  differentiation: '差异化',
  freshness: '新鲜度',
  audience_fit: '受众适配',
}

// 每日清单
const selectedDate = ref(new Date().toISOString().split('T')[0])
const dailyList = ref(null)
const dailyListLoading = ref(false)
const generating = ref(false)

// 统计
const stats = ref(null)
const statsLoading = ref(false)

// 生命周期
onMounted(() => {
  loadCandidates()
})

// 加载候选列表
const loadCandidates = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    }
    if (filters.verdict) params.verdict = filters.verdict
    if (filters.direction) params.direction = filters.direction
    if (filters.min_score !== null && filters.min_score !== undefined) params.min_score = filters.min_score
    if (filters.keyword) params.keyword = filters.keyword

    const res = await get('/topic-candidates', params)
    candidates.value = res.data.items
    pagination.total = res.data.total
  } catch (error) {
    ElMessage.error('加载候选选题失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 查看详情（展开评分明细）
const viewCandidate = (candidate) => {
  expandedId.value = expandedId.value === candidate.id ? null : candidate.id
}

// 生成大纲
const generateOutline = async (candidate) => {
  generatingOutlineId.value = candidate.id
  try {
    const res = await post('/outlines/generate', {
      candidate_id: candidate.id
    })
    ElMessage.success('大纲生成成功')
    // 跳转到大纲详情页
    router.push(`/outlines/${res.data.outline_id}`)
  } catch (error) {
    ElMessage.error('大纲生成失败')
    console.error(error)
  } finally {
    generatingOutlineId.value = null
  }
}

// 加载每日清单
const loadDailyList = async () => {
  dailyListLoading.value = true
  try {
    const res = await get(`/topic-candidates/daily-list/${selectedDate.value}`)
    dailyList.value = res.data
  } catch (error) {
    if (error.response?.status === 404) {
      dailyList.value = null
    } else {
      ElMessage.error('加载每日清单失败')
    }
  } finally {
    dailyListLoading.value = false
  }
}

// 生成每日清单
const generateDailyList = async () => {
  generating.value = true
  try {
    const res = await post('/topic-candidates/daily-list/generate', { target_date: selectedDate.value })
    ElMessage.success('每日清单生成成功')
    await loadDailyList()
  } catch (error) {
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
  }
}

// 触发挖掘
const triggerMining = async () => {
  mining.value = true
  try {
    // 批量挖掘可能处理多个簇，耗时更长，放宽超时到 180s
    const res = await post('/topic-candidates/mine', { limit: 3 }, { timeout: 180000 })
    const data = res.data || res
    if (data.total_candidates > 0) {
      ElMessage.success(`挖掘完成，新增 ${data.total_candidates} 个候选选题`)
    } else {
      ElMessage.info(data.message || '没有未挖掘的信息源')
    }
    await loadCandidates()
  } catch (error) {
    ElMessage.error('挖掘任务失败')
  } finally {
    mining.value = false
  }
}

// 加载统计
const loadStats = async () => {
  statsLoading.value = true
  try {
    const res = await get('/topic-candidates/stats/overview')
    stats.value = res.data
  } catch (error) {
    ElMessage.error('加载统计失败')
  } finally {
    statsLoading.value = false
  }
}

// 应用筛选
const applyFilters = () => {
  pagination.page = 1
  loadCandidates()
}

// 重置筛选
const resetFilters = () => {
  filters.verdict = ''
  filters.direction = ''
  filters.min_score = null
  filters.keyword = ''
  pagination.page = 1
  loadCandidates()
}

// 分页
const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.page = 1
  loadCandidates()
}

const handleCurrentChange = (val) => {
  pagination.page = val
  loadCandidates()
}

// 工具函数
const getVerdictIcon = (verdict) => {
  const icons = { selected: '✅', backup: '⏳', rejected: '❌', vetoed: '🚫' }
  return icons[verdict] || '?'
}

const getVerdictClass = (verdict) => {
  const classes = {
    selected: 'bg-green-100 text-green-700',
    backup: 'bg-yellow-100 text-yellow-700',
    rejected: 'bg-red-100 text-red-700',
    vetoed: 'bg-bone text-ink-2',
  }
  return classes[verdict] || ''
}

const getScoreColor = (score) => {
  if (!score) return 'text-ink-3'
  if (score >= 7) return 'text-green-600'
  if (score >= 5) return 'text-yellow-600'
  return 'text-red-600'
}

// 监听弹窗打开
import { watch } from 'vue'
watch(showStats, (val) => {
  if (val && !stats.value) loadStats()
})
watch(showDailyList, (val) => {
  if (val) loadDailyList()
})
</script>

<style scoped>
.verdict-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  font-size: 14px;
}
</style>
