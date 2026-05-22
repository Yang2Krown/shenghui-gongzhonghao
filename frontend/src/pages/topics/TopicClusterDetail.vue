<template>
  <div class="topic-cluster-detail">
    <!-- 返回按钮 -->
    <div class="mb-4">
      <el-button text @click="router.push('/topic-clusters')" style="color: #6B6862;">
        &larr; 返回话题库
      </el-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32" style="color: #CC785C;"><Loading /></el-icon>
      <span class="ml-2" style="color: #6B6862;">加载中...</span>
    </div>

    <template v-else-if="cluster">
      <!-- 话题详情卡片 -->
      <div class="detail-card mb-6">
        <div class="p-6">
          <!-- 标题：中文主显 + 英文原标题灰色小字 -->
          <h1 class="font-serif mb-1" style="font-size: 28px; font-weight: 500; color: #1F1F1E; line-height: 1.3;">
            {{ cluster.core_title_zh || cluster.core_title }}
          </h1>
          <p v-if="cluster.core_title_zh && cluster.core_title_zh !== cluster.core_title"
             class="mb-3" style="font-size: 13px; color: #9A968D; line-height: 1.5;">
            {{ cluster.core_title }}
          </p>
          <div v-else class="mb-3"></div>

          <!-- 标签行 -->
          <div class="flex flex-wrap gap-2 mb-4">
            <span v-if="cluster.info_type" class="tag-type">{{ cluster.info_type }}</span>
            <span v-if="cluster.direction" class="tag-direction">{{ cluster.direction }}</span>
            <span v-if="cluster.freshness" class="tag-freshness">{{ formatFreshness(cluster.freshness) }}</span>
            <span v-if="cluster.low_fan_hit" class="tag-hot">低粉爆款</span>
          </div>

          <!-- 摘要：中文优先 + 英文原文小字回退 -->
          <p v-if="cluster.summary_zh || cluster.summary" class="mb-1"
             style="color: #3A3935; font-size: 15px; line-height: 1.7;">
            {{ cluster.summary_zh || cluster.summary }}
          </p>
          <p v-if="cluster.summary_zh && cluster.summary && cluster.summary_zh !== cluster.summary"
             class="mb-4" style="color: #9A968D; font-size: 12px; line-height: 1.6; font-style: italic;">
            {{ cluster.summary }}
          </p>

          <!-- 要素 -->
          <div v-if="cluster.elements && Object.keys(cluster.elements).length > 0" class="mb-4">
            <h4 style="color: #3A3935; font-size: 14px; font-weight: 600; margin-bottom: 8px;">信息要素</h4>
            <div class="flex flex-wrap gap-2">
              <span v-for="(val, key) in cluster.elements" :key="key" class="element-tag">
                {{ key }}: {{ val }}
              </span>
            </div>
          </div>

          <!-- 底部信息 -->
          <div class="flex items-center justify-between pt-4" style="border-top: 1px solid #E4DDCE;">
            <div class="flex items-center space-x-4" style="font-size: 13px; color: #6B6862;">
              <span>热度: <strong style="color: #CC785C;">{{ cluster.heat_score?.toFixed(1) || '-' }}</strong></span>
              <span>{{ cluster.candidates?.length || 0 }} 个候选选题</span>
              <span>{{ cluster.source_urls?.length || 0 }} 篇原文</span>
            </div>
            <span class="text-xs" style="color: #9A968D;">
              {{ cluster.created_at ? new Date(cluster.created_at).toLocaleDateString() : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 原文来源区域：卡片化 -->
      <div v-if="cluster.raw_infos?.length > 0 || cluster.source_urls?.length > 0" class="source-section mb-6">
        <h3 class="font-serif mb-3" style="font-size: 18px; font-weight: 500; color: #1F1F1E;">
          原文来源
          <span style="color: #6B6862; font-size: 14px; font-weight: 400;">
            ({{ cluster.raw_infos?.length || cluster.source_urls?.length }})
          </span>
        </h3>

        <!-- 新版：完整原文卡片 -->
        <div v-if="cluster.raw_infos?.length > 0" class="space-y-3">
          <a
            v-for="raw in cluster.raw_infos"
            :key="raw.id"
            :href="raw.url"
            target="_blank"
            rel="noopener noreferrer"
            class="source-card"
          >
            <div class="source-card-body">
              <div class="source-card-header">
                <span class="source-card-platform">{{ raw.source_name }}</span>
                <span v-if="raw.published_at" class="source-card-time">
                  {{ formatRelativeTime(raw.published_at) }}
                </span>
              </div>
              <div class="source-card-title">{{ raw.title }}</div>
              <div v-if="raw.summary" class="source-card-summary">{{ raw.summary }}</div>
              <div class="source-card-footer">
                <span v-if="raw.author" class="source-card-author">{{ raw.author }}</span>
                <span class="source-card-link">阅读原文 &rarr;</span>
              </div>
            </div>
          </a>
        </div>

        <!-- 兼容：raw_infos 缺失时仍用旧的 URL 列表 -->
        <div v-else class="space-y-2">
          <a
            v-for="(url, idx) in cluster.source_urls"
            :key="idx"
            :href="url"
            target="_blank"
            rel="noopener noreferrer"
            class="source-item"
          >
            <span class="source-index">{{ idx + 1 }}</span>
            <span class="source-url">{{ url }}</span>
            <span class="source-arrow">&rarr;</span>
          </a>
        </div>
      </div>

      <!-- 候选选题列表 -->
      <div>
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-serif" style="font-size: 18px; font-weight: 500; color: #1F1F1E;">
            候选选题
            <span style="color: #6B6862; font-size: 14px; font-weight: 400;">({{ cluster.candidates?.length || 0 }})</span>
          </h3>
        </div>

        <div v-if="!cluster.candidates || cluster.candidates.length === 0" class="text-center py-12" style="background: #FAF9F5; border: 1px solid #E4DDCE; border-radius: 16px;">
          <p style="color: #6B6862;">该话题尚未挖掘候选选题</p>
          <el-button
            class="mt-3"
            :loading="mining"
            @click="triggerMining"
            style="background: #CC785C; color: #fff; border: none; border-radius: 10px;"
          >
            立即挖掘
          </el-button>
        </div>

        <div v-else class="space-y-4">
          <div
            v-for="candidate in cluster.candidates"
            :key="candidate.id"
            class="candidate-card"
            @click="expandedId = expandedId === candidate.id ? null : candidate.id"
          >
            <div class="p-5">
              <div class="flex items-start justify-between">
                <!-- 左侧内容 -->
                <div class="flex-1">
                  <!-- 标题和判定 -->
                  <div class="flex items-center gap-2 mb-2">
                    <span class="verdict-badge" :class="getVerdictClass(candidate.verdict)">
                      {{ getVerdictIcon(candidate.verdict) }}
                    </span>
                    <h4 style="font-size: 16px; font-weight: 600; color: #1F1F1E;">
                      {{ candidate.title }}
                    </h4>
                    <span v-if="candidate.persona_divergence_flag" style="color: #C49B5C;" title="Persona 分歧度高">
                      !
                    </span>
                  </div>

                  <!-- 标签行 -->
                  <div class="flex flex-wrap gap-2 mb-2">
                    <span v-if="candidate.direction" class="tag-direction-sm">{{ candidate.direction }}</span>
                    <span v-if="candidate.routine" class="tag-routine">{{ candidate.routine }}</span>
                    <span
                      v-for="dim in (candidate.dimension_combo || []).slice(0, 2)"
                      :key="dim"
                      class="tag-dim"
                    >
                      {{ dim }}
                    </span>
                  </div>

                  <!-- 价值承诺 -->
                  <p style="color: #6B6862; font-size: 14px; margin-bottom: 8px;">{{ candidate.value_promise }}</p>

                  <!-- Persona 评议摘要 -->
                  <div class="flex gap-4" style="font-size: 12px; color: #9A968D;">
                    <span v-for="pr in (candidate.persona_reviews || []).slice(0, 4)" :key="pr.persona">
                      {{ pr.persona }}: <strong style="color: #3A3935;">{{ pr.score }}</strong>
                    </span>
                  </div>
                </div>

                <!-- 右侧评分 -->
                <div class="ml-4 text-right flex-shrink-0">
                  <div class="font-serif" :style="{ color: getScoreColor(candidate.weighted_score), fontSize: '32px', fontWeight: 500, lineHeight: 1.1 }">
                    {{ candidate.weighted_score?.toFixed(1) || '-' }}
                  </div>
                  <div style="font-size: 12px; color: #6B6862; margin-top: 4px;">加权总分</div>
                  <div v-if="!candidate.veto_passed" class="mt-2">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; background: #B85450; color: #fff;">一票否决</span>
                  </div>
                </div>
              </div>

              <!-- 展开的评分明细 -->
              <div v-if="expandedId === candidate.id && candidate.score" class="mt-4 pt-4" style="border-top: 1px solid #E4DDCE;">
                <div class="grid grid-cols-3 md:grid-cols-6 gap-4 mb-3">
                  <div v-for="(label, key) in dimensionLabels" :key="key" class="text-center">
                    <div style="font-size: 12px; color: #6B6862;">{{ label }}</div>
                    <div style="font-size: 18px; font-weight: 600; color: #1F1F1E;">{{ candidate.score[key]?.toFixed(1) || '-' }}</div>
                  </div>
                </div>
                <div v-if="candidate.score.evidence" style="font-size: 12px; color: #9A968D;">
                  <div v-for="(ev, key) in candidate.score.evidence" :key="key" class="mb-1">
                    <strong>{{ dimensionLabels[key] }}:</strong> {{ ev }}
                  </div>
                </div>

                <!-- 角切入说明 -->
                <div v-if="candidate.angle_note" class="mt-3 p-3" style="background: #F5E2D5; border-radius: 10px;">
                  <span style="font-size: 12px; font-weight: 600; color: #A85A40;">切入说明: </span>
                  <span style="font-size: 13px; color: #3A3935;">{{ candidate.angle_note }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 404 -->
    <div v-else class="text-center py-20">
      <h3 style="color: #3A3935; font-size: 18px;">话题不存在</h3>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { get, post } from '@/api/api'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const mining = ref(false)
const cluster = ref(null)
const expandedId = ref(null)

const dimensionLabels = {
  pain_point: '痛点直击',
  value_density: '价值密度',
  propagation: '传播触发',
  differentiation: '差异化',
  freshness: '新鲜度',
  audience_fit: '受众适配',
}

onMounted(() => {
  loadCluster()
})

const loadCluster = async () => {
  loading.value = true
  try {
    const res = await get(`/topic-clusters/${route.params.id}`)
    cluster.value = res.data
  } catch (error) {
    if (error.response?.status === 404) {
      cluster.value = null
    } else {
      ElMessage.error('加载话题详情失败')
    }
  } finally {
    loading.value = false
  }
}

const triggerMining = async () => {
  if (!cluster.value?.id) return
  mining.value = true
  try {
    // 挖掘需顺序调用 Agent A + Agent B 两次 LLM，耗时较长，单独放宽超时到 180s
    const res = await post('/topic-candidates/mine', { cluster_id: cluster.value.id }, { timeout: 180000 })
    const data = res?.data || {}
    if (data.skipped) {
      ElMessage.info('该话题已经挖掘过')
    } else {
      ElMessage.success(`挖掘完成，生成 ${data.total_candidates ?? '?'} 个候选`)
    }
    await loadCluster()
  } catch (error) {
    // axios 错误：从 response.data.detail 拿 FastAPI 抛出的具体错误
    const detail = error?.response?.data?.detail || error?.message || '挖掘失败'
    ElMessage.error(`挖掘失败: ${detail}`)
    console.error('[triggerMining]', error)
  } finally {
    mining.value = false
  }
}

const formatFreshness = (val) => {
  const map = { '24h': '24h 内', '7d': '7 天内', '30d': '30 天内', 'expired': '已过期' }
  return map[val] || val
}

const formatRelativeTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return '刚刚'
  if (h < 24) return `${h} 小时前`
  const days = Math.floor(h / 24)
  if (days < 30) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}

const getVerdictIcon = (verdict) => {
  const icons = { selected: 'S', backup: 'B', rejected: 'R', vetoed: 'V' }
  return icons[verdict] || '?'
}

const getVerdictClass = (verdict) => {
  const classes = {
    selected: 'verdict-selected',
    backup: 'verdict-backup',
    rejected: 'verdict-rejected',
    vetoed: 'verdict-vetoed',
  }
  return classes[verdict] || ''
}

const getScoreColor = (score) => {
  if (!score) return '#6B6862'
  if (score >= 7) return '#5C8A5C'
  if (score >= 5) return '#C49B5C'
  return '#B85450'
}
</script>

<style scoped>
.detail-card {
  background: #FAF9F5;
  border: 1px solid #E4DDCE;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}

.source-section {
  background: #FAF9F5;
  border: 1px solid #E4DDCE;
  border-radius: 16px;
  padding: 24px;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid #E4DDCE;
  border-radius: 10px;
  text-decoration: none;
  transition: all 0.15s;
}
.source-item:hover {
  border-color: #CC785C;
  background: #F5E2D5;
}

.source-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #CC785C;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.source-url {
  flex: 1;
  font-size: 13px;
  color: #3A3935;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-arrow {
  color: #CC785C;
  font-size: 16px;
  flex-shrink: 0;
}

/* 新版原文卡片 */
.source-card {
  display: block;
  background: #fff;
  border: 1px solid #E4DDCE;
  border-radius: 12px;
  text-decoration: none;
  transition: all 0.2s cubic-bezier(.32, .72, 0, 1);
  overflow: hidden;
}
.source-card:hover {
  border-color: #CC785C;
  box-shadow: 0 4px 12px rgba(204, 120, 92, 0.10);
  transform: translateY(-1px);
}
.source-card-body {
  padding: 14px 16px;
}
.source-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.source-card-platform {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  background: #F5E2D5;
  color: #A85A40;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid #E9B79E;
}
.source-card-time {
  font-size: 12px;
  color: #9A968D;
}
.source-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1F1F1E;
  line-height: 1.45;
  margin-bottom: 6px;
}
.source-card-summary {
  font-size: 13px;
  color: #6B6862;
  line-height: 1.6;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 8px;
}
.source-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.source-card-author {
  color: #9A968D;
}
.source-card-link {
  color: #CC785C;
  font-weight: 500;
}

.candidate-card {
  background: #FAF9F5;
  border: 1px solid #E4DDCE;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.24s cubic-bezier(.32, .72, 0, 1);
  box-shadow: 0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
}
.candidate-card:hover {
  box-shadow: 0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  transform: translateY(-2px);
}

.verdict-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.verdict-selected {
  background: #5C8A5C;
  color: #fff;
}
.verdict-backup {
  background: #C49B5C;
  color: #fff;
}
.verdict-rejected {
  background: #B85450;
  color: #fff;
}
.verdict-vetoed {
  background: #EFEAE0;
  color: #6B6862;
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

.tag-direction {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #C9D4CD;
  color: #3F5C52;
}

.tag-direction-sm {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
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

.tag-routine {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: #EFEAE0;
  color: #3A3935;
  border: 1px solid #E4DDCE;
}

.tag-dim {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: #ECDCBF;
  color: #C49B5C;
}

.element-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  background: #EFEAE0;
  color: #3A3935;
  border: 1px solid #E4DDCE;
}
</style>
