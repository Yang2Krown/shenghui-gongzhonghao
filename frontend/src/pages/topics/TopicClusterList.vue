<template>
  <div class="topic-cluster-list">
    <!-- 页面标题和操作栏 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="font-serif text-ink" style="font-size: 30px; font-weight: 500; line-height: 1.2;">话题库</h1>
        <p class="mt-1" style="color: #6B6862; font-size: 14px;">信息聚合后的原始话题，点击可查看衍生的候选选题</p>
      </div>
      <div class="flex space-x-3">
        <el-button :loading="mining" @click="triggerMining" style="background: #CC785C; color: #fff; border: none; border-radius: 10px;">
          挖掘选题
        </el-button>
        <el-button @click="showFilters = !showFilters" style="background: transparent; color: #1F1F1E; border: 1px solid #E4DDCE; border-radius: 10px;">
          筛选
        </el-button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <el-collapse-transition>
      <div v-show="showFilters" class="mb-6" style="background: #FAF9F5; border: 1px solid #E4DDCE; border-radius: 16px; padding: 24px;">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="block mb-1" style="color: #3A3935; font-size: 13px; font-weight: 500;">信息类型</label>
            <el-select v-model="filters.info_type" placeholder="选择类型" clearable class="w-full">
              <el-option label="资讯型" value="资讯型" />
              <el-option label="实操案例型" value="实操案例型" />
              <el-option label="观点分享型" value="观点分享型" />
              <el-option label="教程型" value="教程型" />
            </el-select>
          </div>
          <div>
            <label class="block mb-1" style="color: #3A3935; font-size: 13px; font-weight: 500;">方向</label>
            <el-select v-model="filters.direction" placeholder="选择方向" clearable class="w-full">
              <el-option v-for="d in directions" :key="d" :label="d" :value="d" />
            </el-select>
          </div>
          <div>
            <label class="block mb-1" style="color: #3A3935; font-size: 13px; font-weight: 500;">时效</label>
            <el-select v-model="filters.freshness" placeholder="选择时效" clearable class="w-full">
              <el-option label="24h 内" value="24h" />
              <el-option label="7 天内" value="7d" />
              <el-option label="30 天内" value="30d" />
              <el-option label="已过期" value="expired" />
            </el-select>
          </div>
          <div>
            <label class="block mb-1" style="color: #3A3935; font-size: 13px; font-weight: 500;">关键词</label>
            <el-input v-model="filters.keyword" placeholder="搜索话题标题" clearable />
          </div>
        </div>
        <div class="flex justify-end mt-4 space-x-2">
          <el-button @click="resetFilters" style="border-radius: 10px;">重置</el-button>
          <el-button @click="applyFilters" style="background: #CC785C; color: #fff; border: none; border-radius: 10px;">应用筛选</el-button>
        </div>
      </div>
    </el-collapse-transition>

    <!-- 快速类型筛选 chips（默认推荐"工具实操"两类） -->
    <div class="mb-5 flex flex-wrap items-center gap-2">
      <span style="color: #6B6862; font-size: 13px; margin-right: 4px;">公众号创作推荐：</span>
      <button
        v-for="opt in quickTypeOptions"
        :key="opt.value"
        @click="quickFilterByType(opt.value)"
        :class="['type-chip', filters.info_type === opt.value && 'type-chip-active', opt.highlight && 'type-chip-highlight']"
      >
        {{ opt.label }}
        <span v-if="opt.tip" class="chip-tip">{{ opt.tip }}</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32" style="color: #CC785C;"><Loading /></el-icon>
      <span class="ml-2" style="color: #6B6862;">加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="clusters.length === 0" class="text-center py-20">
      <el-icon :size="64" style="color: #E4DDCE;"><Folder /></el-icon>
      <h3 class="mt-4" style="color: #3A3935; font-size: 18px; font-weight: 600;">暂无话题</h3>
      <p class="mt-1" style="color: #6B6862; font-size: 14px;">需要先通过抓取和预处理生成话题</p>
    </div>

    <!-- 话题列表 -->
    <div v-else class="space-y-4">
      <div
        v-for="cluster in clusters"
        :key="cluster.id"
        :class="['cluster-card', cluster.info_type === '资讯型' && 'cluster-card-news']"
        @click="goToDetail(cluster.id)"
      >
        <div class="p-6">
          <!-- 标题行 -->
          <div class="flex items-start justify-between mb-2">
            <div class="flex-1">
              <!-- 中文标题（如果有翻译就用中文，否则直接显示原文） -->
              <h3 class="font-serif" style="font-size: 20px; font-weight: 500; color: #1F1F1E; line-height: 1.4;">
                {{ cluster.core_title_zh || cluster.core_title }}
              </h3>
              <!-- 英文原标题（仅在有翻译时小字灰色展示） -->
              <p v-if="cluster.core_title_zh && cluster.core_title_zh !== cluster.core_title"
                 class="mt-1" style="font-size: 12px; color: #9A968D; line-height: 1.4;">
                {{ cluster.core_title }}
              </p>
            </div>
            <div class="ml-4 flex-shrink-0 flex items-center space-x-2">
              <span v-if="cluster.mined" class="tag-mined">已挖掘</span>
              <span v-else class="tag-unmined">待挖掘</span>
            </div>
          </div>

          <!-- 摘要：中文优先，英文回退 -->
          <p v-if="cluster.summary_zh || cluster.summary" class="mb-3"
             style="color: #6B6862; font-size: 14px; line-height: 1.7; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
            {{ cluster.summary_zh || cluster.summary }}
          </p>

          <!-- 标签行 -->
          <div class="flex flex-wrap gap-2 mb-3">
            <span v-if="cluster.info_type"
                  :class="['tag-type', cluster.info_type === '教程型' && 'tag-type-recommend',
                                       cluster.info_type === '实操案例型' && 'tag-type-recommend']">
              {{ cluster.info_type }}
              <span v-if="cluster.info_type === '教程型' || cluster.info_type === '实操案例型'">✨</span>
            </span>
            <span v-if="cluster.direction" class="tag-direction">{{ cluster.direction }}</span>
            <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
            <span v-if="cluster.low_fan_hit" class="tag-hot">🔥 低粉爆款</span>
          </div>

          <!-- 底部信息行 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-4" style="font-size: 13px; color: #6B6862;">
              <!-- 创作价值（加权后）+ 原始热度 -->
              <span class="flex items-center space-x-1">
                <span style="color: #CC785C; font-weight: 600;">{{ cluster.display_score?.toFixed(1) || '-' }}</span>
                <span>价值</span>
                <span style="color: #C8C2B6; margin: 0 4px;">·</span>
                <span style="color: #9A968D;">热度 {{ cluster.heat_score?.toFixed(1) || '-' }}</span>
              </span>
              <!-- 候选数 -->
              <span v-if="cluster.candidate_count > 0" class="flex items-center space-x-1">
                <span style="color: #3F5C52; font-weight: 600;">{{ cluster.candidate_count }}</span>
                <span>个选题</span>
              </span>
              <!-- 来源数 -->
              <span class="flex items-center space-x-1">
                <span>{{ cluster.source_count || cluster.source_urls?.length || 0 }}</span>
                <span>篇原文</span>
              </span>
            </div>

            <!-- 原文链接 -->
            <div v-if="cluster.source_urls?.length > 0" class="flex items-center space-x-2">
              <a
                v-for="(url, idx) in cluster.source_urls.slice(0, 3)"
                :key="idx"
                :href="url"
                target="_blank"
                rel="noopener noreferrer"
                class="source-link"
                @click.stop
              >
                来源 {{ idx + 1 }}
              </a>
              <span v-if="cluster.source_urls.length > 3" style="color: #9A968D; font-size: 12px;">
                +{{ cluster.source_urls.length - 3 }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="clusters.length > 0" class="flex justify-center mt-8">
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Folder } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const showFilters = ref(false)
const mining = ref(false)
const clusters = ref([])

const directions = ['大模型', 'Coding Agent', 'AI视频', 'AI绘画', 'AI音频', '效率工具', '观点型', '实践型', '教程型', '解决问题型', '资讯型', '整活型']

const filters = reactive({
  info_type: '',
  direction: '',
  freshness: '',
  keyword: '',
  sort_by: 'display_score',   // 默认按"公众号创作价值"加权排序（教程/实操优先）
  sort_order: 'desc',
})

// 顶部快速分类 chips
const quickTypeOptions = [
  { value: '', label: '全部' },
  { value: '教程型', label: '教程型', highlight: true, tip: '✨ 推荐' },
  { value: '实操案例型', label: '实操案例', highlight: true, tip: '✨ 推荐' },
  { value: '观点分享型', label: '观点分享' },
  { value: '资讯型', label: '资讯型' },
]

const quickFilterByType = (typeValue) => {
  filters.info_type = typeValue
  pagination.page = 1
  syncToQuery()
  loadClusters()
}

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// 从 URL query 还原状态（首次进入 / 浏览器后退时）
const restoreFromQuery = () => {
  const q = route.query
  filters.info_type   = q.info_type   ?? ''
  filters.direction   = q.direction   ?? ''
  filters.freshness   = q.freshness   ?? ''
  filters.keyword     = q.keyword     ?? ''
  filters.sort_by     = q.sort_by     ?? 'display_score'
  filters.sort_order  = q.sort_order  ?? 'desc'
  pagination.page     = Number(q.page) || 1
  pagination.pageSize = Number(q.page_size) || 20
}

// 把当前状态写进 URL query（不刷新页面）
const syncToQuery = () => {
  const q = {}
  if (pagination.page !== 1)            q.page = pagination.page
  if (pagination.pageSize !== 20)       q.page_size = pagination.pageSize
  if (filters.sort_by !== 'display_score') q.sort_by = filters.sort_by
  if (filters.sort_order !== 'desc')    q.sort_order = filters.sort_order
  if (filters.info_type)                q.info_type = filters.info_type
  if (filters.direction)                q.direction = filters.direction
  if (filters.freshness)                q.freshness = filters.freshness
  if (filters.keyword)                  q.keyword = filters.keyword
  router.replace({ query: q })
}

onMounted(() => {
  restoreFromQuery()
  loadClusters()
})

// 浏览器后退/前进时，URL query 变化要重新载入
watch(() => route.query, () => {
  // 仅当当前路由是列表本身时响应（避免详情页跳回时触发两次）
  if (route.name === 'TopicClusters' || route.name === 'Home') {
    restoreFromQuery()
    loadClusters()
  }
})

const loadClusters = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    }
    if (filters.info_type) params.info_type = filters.info_type
    if (filters.direction) params.direction = filters.direction
    if (filters.freshness) params.freshness = filters.freshness
    if (filters.keyword) params.keyword = filters.keyword

    const res = await get('/topic-clusters', params)
    clusters.value = res.data.items
    pagination.total = res.data.total
  } catch (error) {
    ElMessage.error('加载话题库失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const goToDetail = (id) => {
  router.push(`/topic-clusters/${id}`)
}

const triggerMining = async () => {
  mining.value = true
  try {
    // 批量挖掘可能处理多个簇，耗时更长，放宽超时到 180s
    const res = await post('/topic-candidates/mine', { limit: 3 }, { timeout: 180000 })
    const data = res.data || res
    if (data.total_candidates > 0) {
      ElMessage.success(`挖掘完成，新增 ${data.total_candidates} 个候选选题`)
    } else {
      ElMessage.info(data.message || '没有未挖掘的话题')
    }
    await loadClusters()
  } catch (error) {
    ElMessage.error('挖掘任务失败')
  } finally {
    mining.value = false
  }
}

const applyFilters = () => {
  pagination.page = 1
  syncToQuery()
  loadClusters()
}

const resetFilters = () => {
  filters.info_type = ''
  filters.direction = ''
  filters.freshness = ''
  filters.keyword = ''
  pagination.page = 1
  syncToQuery()
  loadClusters()
}

const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.page = 1
  syncToQuery()
  loadClusters()
}

const handleCurrentChange = (val) => {
  pagination.page = val
  syncToQuery()
  loadClusters()
}

const formatFreshness = (val) => {
  const map = { '24h': '24h 内', '7d': '7 天内', '30d': '30 天内', 'expired': '已过期' }
  return map[val] || val
}
</script>

<style scoped>
.cluster-card {
  background: #FAF9F5;
  border: 1px solid #E4DDCE;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.24s cubic-bezier(.32, .72, 0, 1);
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}
.cluster-card:hover {
  box-shadow: 0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  transform: translateY(-2px);
}

.tag-type {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #F5E2D5;
  color: #A85A40;
  border: 1px solid #E9B79E;
}

/* 资讯型卡片整体降级（透明度 + 边框淡化） */
.cluster-card-news {
  opacity: 0.75;
}
.cluster-card-news:hover {
  opacity: 1;
}

/* 教程 / 实操推荐徽标（绿色高亮） */
.tag-type-recommend {
  background: #DAF0DC !important;
  color: #2A6B3A !important;
  border-color: #A8D6B0 !important;
  font-weight: 600 !important;
}

/* 顶部 chip 筛选 */
.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  background: #FAF9F5;
  color: #6B6862;
  border: 1px solid #E4DDCE;
  cursor: pointer;
  transition: all 0.15s;
}
.type-chip:hover {
  background: #F0EDE3;
  color: #1F1F1E;
}
.type-chip-active {
  background: #1F1F1E;
  color: #fff;
  border-color: #1F1F1E;
}
.type-chip-highlight {
  border-color: #A8D6B0;
  background: #F4FBF6;
  color: #2A6B3A;
}
.type-chip-highlight.type-chip-active {
  background: #2A6B3A;
  color: #fff;
  border-color: #2A6B3A;
}
.chip-tip {
  font-size: 11px;
  opacity: 0.8;
}

.tag-direction {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #C9D4CD;
  color: #3F5C52;
}

.tag-freshness {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #ECDCBF;
  color: #C49B5C;
}

.tag-hot {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #B85450;
  color: #fff;
}

.tag-mined {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #5C8A5C;
  color: #fff;
}

.tag-unmined {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #EFEAE0;
  color: #6B6862;
  border: 1px solid #E4DDCE;
}

.source-link {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #CC785C;
  background: #F5E2D5;
  text-decoration: none;
  transition: background 0.15s;
}
.source-link:hover {
  background: #E9B79E;
}
</style>
