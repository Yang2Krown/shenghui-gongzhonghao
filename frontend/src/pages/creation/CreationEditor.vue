<template>
  <div class="creation-workspace">
    <!-- 顶部：选题信息 + 操作 -->
    <header class="workspace-header mb-6">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <el-button text @click="router.push('/creation')" class="text-ink-3">
              <el-icon><ArrowLeft /></el-icon>
              返回创作列表
            </el-button>
          </div>
          <h1 class="text-h2 font-serif text-ink">
            {{ topicTitle || '新建创作' }}
          </h1>
          <div class="flex items-center gap-2 mt-1">
            <span v-if="topicDirection" class="badge-info">{{ topicDirection }}</span>
            <span class="text-sm text-ink-3">
              {{ isEditing ? '编辑创作' : '从选题开始创作' }}
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <el-button @click="saveDraft" :loading="saving">
            <el-icon><Document /></el-icon>
            保存草稿
          </el-button>
          <!-- 发布按钮暂时隐藏 -->
        </div>
      </div>
    </header>

    <!-- 创作进度概览 -->
    <div class="workflow-steps mb-6">
      <button
        v-for="(step, i) in steps"
        :key="step.key"
        type="button"
        class="workflow-step"
        :class="{
          'is-current': isCurrentWorkflowStep(step.key),
          'is-done': step.status === 'completed',
          'is-running': step.status === 'generating',
          'is-failed': step.status === 'failed',
          'is-disabled': !canOpenStep(step.key),
        }"
        :disabled="!canOpenStep(step.key)"
        @click="openStep(step.key)"
      >
        <span class="step-indicator">
          <el-icon v-if="step.status === 'completed'" :size="15"><Check /></el-icon>
          <span v-else>{{ i + 1 }}</span>
        </span>
        <span class="step-copy">
          <span class="step-label">{{ step.label }}</span>
          <span class="step-meta">{{ getStepMeta(step) }}</span>
        </span>
        <el-icon v-if="i < steps.length - 1" class="step-arrow"><ArrowRight /></el-icon>
      </button>
    </div>

    <!-- 内容区：Tab header 隐藏，顶部四步是唯一导航 -->
    <el-tabs v-model="activeTab" class="workspace-tabs">
      <!-- Tab 1: 大纲 -->
      <el-tab-pane name="outline">
        <template #label>
          <span class="tab-label-wrapper">
            <span>大纲管理</span>
            <span class="tab-status-dot" :class="getStatusClass('outline')"></span>
          </span>
        </template>
        <OutlinePanel
          :candidate-id="candidateId"
          :outline-id="currentOutlineId"
          :active-workflow-step="activeWorkflowStep"
          @pipeline-status="onPipelineStatus"
          @complete="onOutlineComplete"
          @next-step="goWorkflowStep('title')"
        />
        <!-- 大纲数据由本步骤生成，后续步骤直接复用 currentOutlineData -->
      </el-tab-pane>

      <!-- Tab 2: 标题 -->
      <el-tab-pane name="title" :disabled="outlineStatus !== 'completed'">
        <template #label>
          <span class="tab-label-wrapper">
            <span>标题生成</span>
            <span class="tab-status-dot" :class="getStatusClass('title')"></span>
          </span>
        </template>
        <TitlePanel
          :candidate-id="candidateId"
          :outline-data="currentOutlineData"
          @complete="onTitleComplete"
          @next-step="goWorkflowStep('content')"
        />
      </el-tab-pane>

      <!-- Tab 3: 正文 -->
      <el-tab-pane name="content" :disabled="titleStatus !== 'completed'">
        <template #label>
          <span class="tab-label-wrapper">
            <span>正文生成</span>
            <span class="tab-status-dot" :class="getStatusClass('content')"></span>
          </span>
        </template>
        <ContentPanel
          :candidate-id="candidateId"
          :outline-data="currentOutlineData"
          :title-data="selectedTitle"
          :initial-content="finalContent"
          @complete="onContentComplete"
          @save-draft="onSaveDraft"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Document, Check } from '@element-plus/icons-vue'
import { useCreationStore } from '@/stores/creation'
import OutlinePanel from '@/components/creation/OutlinePanel.vue'
import TitlePanel from '@/components/creation/TitlePanel.vue'
import ContentPanel from '@/components/creation/ContentPanel.vue'
import outlineApi from '@/api/outline'
import generationRecordApi from '@/api/generationRecord'
import { get } from '@/api/api'

const route = useRoute()
const router = useRouter()
const creationStore = useCreationStore()

// 从 URL 获取选题信息
const candidateId = computed(() => route.query.candidate_id || null)
const clusterId = computed(() => route.query.cluster_id || null)
const topicTitle = computed(() => route.query.topic_title || '')
const topicDirection = computed(() => route.query.topic_direction || '')
const isEditing = computed(() => !!route.params.id)

// 状态
const activeTab = ref('outline')
const activeWorkflowStep = ref('angle')
const saving = ref(false)
const publishing = ref(false)
const currentOutlineId = ref(null)
const currentOutlineData = ref(null)
const selectedTitle = ref(null)
const finalContent = ref(null)

// 未保存状态追踪
const isDirty = ref(false)

// 创作步骤状态
const angleStatus = ref('idle')
const outlineStatus = ref('idle')
const titleStatus = ref('idle')
const contentStatus = ref('idle')

const steps = computed(() => [
  { key: 'angle', label: '创作角度体检', status: angleStatus.value },
  { key: 'outline', label: '大纲', status: outlineStatus.value },
  { key: 'title', label: '标题', status: titleStatus.value },
  { key: 'content', label: '正文', status: contentStatus.value },
])

const stepToTab = {
  angle: 'outline',
  outline: 'outline',
  title: 'title',
  content: 'content',
}

const canOpenStep = (key) => {
  if (key === 'angle') return true
  if (key === 'outline') return angleStatus.value === 'completed'
  if (key === 'title') return outlineStatus.value === 'completed'
  if (key === 'content') return titleStatus.value === 'completed'
  return false
}

const openStep = (key) => {
  if (!canOpenStep(key)) return
  goWorkflowStep(key)
}

const isCurrentWorkflowStep = (key) => {
  return activeWorkflowStep.value === key
}

const getStepMeta = (step) => {
  const text = {
    idle: '待开始',
    generating: '进行中',
    completed: '已完成',
    failed: '需重试',
  }
  return text[step.status] || '待开始'
}

// ── 从历史记录恢复创作状态 ──
const restoreFromHistory = async (recordId) => {
  try {
    // 1. 获取点击的那条记录
    const recordRes = await generationRecordApi.get(recordId)
    const record = recordRes.data

    const cid = record.candidate_id
    if (!cid) {
      ElMessage.warning('此记录未关联选题，无法恢复完整创作状态')
      return
    }

    // 2. 加载选题信息（用于顶部显示 + 传给子面板）
    try {
      const candidateRes = await get(`/topic-candidates/${cid}`)
      const cand = candidateRes.data?.data || candidateRes.data || candidateRes
      // 写入 URL query（不触发导航，仅更新显示用的 computed）
      router.replace({
        path: route.path,
        query: {
          ...route.query,
          candidate_id: cid,
          topic_title: cand.title || '',
          topic_direction: cand.direction || '',
        },
      })
    } catch (e) {
      console.warn('加载选题信息失败:', e)
    }

    // 3. 获取该选题下所有已完成的记录（每种 type 最新一条）
    const allRes = await generationRecordApi.byCandidate(cid)
    const records = allRes.data || []

    // 按 type 索引
    const byType = {}
    for (const r of records) {
      byType[r.type] = r
    }

    // 4. 恢复大纲（最关键 —— 后续步骤都依赖大纲数据）
    const outlineRecord = byType['outline_generate'] || byType['outline_reevaluate']
    if (outlineRecord && outlineRecord.output_snapshot) {
      const snap = outlineRecord.output_snapshot
      // output_snapshot 里可能包含 outline_id 或 id
      const oid = snap.id || snap.outline_id
      if (oid) {
        currentOutlineId.value = oid
        // 通过 API 加载完整大纲数据（含 sections、inspection 等）
        try {
          const outlineRes = await outlineApi.getOutline(oid)
          currentOutlineData.value = outlineRes.data || outlineRes
        } catch {
          // 如果 API 加载失败，尝试用快照数据
          currentOutlineData.value = { ...snap, id: oid }
        }
      } else {
        // 没有 outline_id，直接用快照
        currentOutlineData.value = snap
      }
      angleStatus.value = 'completed'
      outlineStatus.value = 'completed'
    }

    // 5. 恢复标题
    const titleRecord = byType['title_generate']
    if (titleRecord && titleRecord.output_snapshot) {
      const snap = titleRecord.output_snapshot
      const recs = snap.recommendations || []
      if (recs.length > 0) {
        selectedTitle.value = { title: recs[0].title, ...recs[0] }
      }
      titleStatus.value = 'completed'
    }

    // 6. 恢复正文
    const contentRecord = byType['content_generate']
    if (contentRecord && contentRecord.output_snapshot) {
      const snap = contentRecord.output_snapshot
      // content_generate 的 output_snapshot 只存了摘要信息
      // 如果有 final_text 就用，否则标记 completed 但不填内容
      if (snap.final_text) {
        finalContent.value = snap
      }
      contentStatus.value = 'completed'
    }

    // 7. 跳到对应步骤（根据点击的记录类型决定）
    const typeToStep = {
      angle_inspection: 'angle',
      outline_generate: 'outline',
      outline_reevaluate: 'outline',
      title_generate: 'title',
      title_reevaluate: 'title',
      content_generate: 'content',
      content_reevaluate: 'content',
    }
    const targetStep = typeToStep[record.type] || 'outline'
    goWorkflowStep(targetStep)

    ElMessage.success('已从历史记录恢复创作状态')
  } catch (e) {
    console.error('从历史记录恢复失败:', e)
    ElMessage.error('恢复创作状态失败')
  }
}

// 加载已有创作数据
onMounted(async () => {
  // 优先：从历史记录恢复
  const recordId = route.query.record_id
  if (recordId) {
    await restoreFromHistory(recordId)
    return
  }

  // 原有逻辑：编辑模式加载草稿
  if (isEditing.value) {
    try {
      await creationStore.fetchCreationById(route.params.id)
      const creation = creationStore.currentCreation
      if (creation) {
        // 恢复标题
        if (creation.title) {
          selectedTitle.value = { title: creation.title }
        }
        // 恢复大纲
        if (creation.outline_id) {
          currentOutlineId.value = creation.outline_id
          angleStatus.value = 'completed'
          outlineStatus.value = creation.outline_status || 'completed'
          try {
            const outlineRes = await outlineApi.getOutline(creation.outline_id)
            currentOutlineData.value = outlineRes.data || outlineRes
            goWorkflowStep('outline')
          } catch (err) {
            console.error('加载大纲数据失败:', err)
          }
        }
        if (creation.title_status === 'completed') {
          titleStatus.value = 'completed'
        }
        // 恢复正文（兼容 JSON 存储与纯文本）
        const contentRaw = creation.content
        if (contentRaw && contentRaw !== 'null') {
          let contentData = { final_text: contentRaw }
          try {
            const parsed = JSON.parse(contentRaw)
            if (parsed && typeof parsed === 'object' && parsed.final_text) {
              contentData = parsed
            }
          } catch {}
          finalContent.value = { ...contentData, final_word_count: creation.word_count }
          contentStatus.value = creation.content_status || 'completed'
        }
      }
    } catch (e) {
      console.error('加载创作失败:', e)
    }
  }
})

const onPipelineStatus = ({ angle, outline }) => {
  if (angle) angleStatus.value = angle
  if (outline) outlineStatus.value = outline
  if (angle === 'generating') goWorkflowStep('angle')
  if (outline === 'generating') goWorkflowStep('outline')
}

// 大纲完成回调（留在当前 tab，不自动跳转）
const onOutlineComplete = (outlineData) => {
  isDirty.value = true
  angleStatus.value = 'completed'
  outlineStatus.value = 'completed'
  goWorkflowStep('outline')
  // 大纲流水线 SSE 返回的字段是 outline_id；获取详情接口返回的是 id —— 两边兼容
  const oid = outlineData?.id ?? outlineData?.outline_id ?? null
  currentOutlineId.value = oid
  currentOutlineData.value = outlineData ? { ...outlineData, id: oid } : null
  ElMessage.success('大纲生成完成，可切换到标题生成')
}

// 标题完成回调
const onTitleComplete = (titleData) => {
  isDirty.value = true
  titleStatus.value = 'completed'
  selectedTitle.value = titleData
  goWorkflowStep('title')
}

// 正文完成回调
const onContentComplete = (contentData) => {
  isDirty.value = true
  contentStatus.value = 'completed'
  finalContent.value = contentData || null
  goWorkflowStep('content')
  ElMessage.success('创作流程完成！')
}

// 从 ContentPanel 触发保存草稿（携带当前编辑内容）
const onSaveDraft = (contentData) => {
  if (contentData) {
    finalContent.value = contentData
  }
  saveDraft()
}

// 保存草稿
const saveDraft = async () => {
  saving.value = true
  try {
    const finalTitle = selectedTitle.value?.title || topicTitle.value || '未命名创作'
    const finalText = finalContent.value?.final_text || ''
    const plain = finalText.replace(/[#*`>_~\-]/g, '').trim()
    const summary = plain.slice(0, 120)
    const tags = []
    if (topicDirection.value) tags.push(topicDirection.value)

    const data = {
      title: finalTitle,
      content: finalContent.value ? JSON.stringify(finalContent.value) : null,
      summary: summary || null,
      tags,
      word_count: finalContent.value?.final_word_count || finalText.length || 0,
      topic_title: topicTitle.value || null,
      topic_direction: topicDirection.value || null,
      topic_id: null,
      candidate_id: candidateId.value ? Number(candidateId.value) : null,
      outline_id: currentOutlineId.value,
      outline_status: outlineStatus.value,
      title_status: titleStatus.value,
      content_status: contentStatus.value,
      status: 'draft',
    }

    if (isEditing.value) {
      await creationStore.updateCreation(route.params.id, data)
    } else {
      const creation = await creationStore.createCreation(data)
      // 替换 URL 为编辑模式
      router.replace(`/creation/editor/${creation.id}`)
    }
    isDirty.value = false
    ElMessage.success('草稿已保存')
  } catch (e) {
    console.error('保存失败:', e)
  } finally {
    saving.value = false
  }
}

// 发布
const publishCreation = async () => {
  if (contentStatus.value !== 'completed') {
    ElMessage.warning('请先完成正文生成')
    return
  }
  publishing.value = true
  try {
    // TODO: 实现发布逻辑
    ElMessage.success('发布成功')
    router.push('/creation')
  } catch (e) {
    console.error('发布失败:', e)
  } finally {
    publishing.value = false
  }
}

const getStatusClass = (key) => {
  const statusMap = {
    angle: angleStatus.value,
    outline: outlineStatus.value,
    title: titleStatus.value,
    content: contentStatus.value,
  }
  const s = statusMap[key]
  if (s === 'completed') return 'dot-done'
  if (s === 'generating') return 'dot-active'
  if (s === 'failed') return 'dot-failed'
  return 'dot-pending'
}

const goWorkflowStep = (key) => {
  activeWorkflowStep.value = key
  activeTab.value = stepToTab[key] || 'outline'
}

// ── 离开提示 ──
onBeforeRouteLeave(async (to, from, next) => {
  if (!isDirty.value) return next()
  try {
    await ElMessageBox.confirm(
      '当前页面有未保存的生成内容，离开后将丢失。建议先保存草稿。',
      '确认离开',
      {
        confirmButtonText: '仍然离开',
        cancelButtonText: '留在此页',
        type: 'warning',
      }
    )
    next()
  } catch {
    next(false)
  }
})

const handleBeforeUnload = (e) => {
  if (isDirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.workspace-tabs :deep(.el-tabs__header) {
  display: none;
}

.workspace-tabs :deep(.el-tabs__content) {
  overflow: visible;
}

.creation-workspace {
  padding-bottom: 73px;
}

.workflow-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 10px 28px rgba(31, 31, 30, 0.06);
  overflow: hidden;
}

.workflow-step {
  position: relative;
  min-width: 0;
  height: 88px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 24px;
  border: 0;
  background: transparent;
  color: var(--ink-3);
  text-align: left;
  transition: background 0.18s ease, color 0.18s ease;
}

.workflow-step + .workflow-step {
  border-left: 1px solid var(--line);
}

.workflow-step:not(.is-disabled) {
  cursor: pointer;
}

.workflow-step:not(.is-disabled):hover {
  background: var(--ivory);
}

.workflow-step.is-current {
  background: var(--clay-tint);
  color: var(--ink);
}

.workflow-step.is-current::after {
  content: '';
  position: absolute;
  left: 24px;
  right: 24px;
  bottom: 0;
  height: 3px;
  border-radius: 999px 999px 0 0;
  background: var(--clay);
}

.workflow-step.is-disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.step-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.step-label {
  font-size: 17px;
  font-weight: 600;
  line-height: 1.2;
  color: currentColor;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-meta {
  font-size: 12px;
  color: var(--ink-3);
}

.workflow-step.is-current .step-meta,
.workflow-step.is-running .step-meta {
  color: var(--clay-deep);
}

.step-arrow {
  margin-left: auto;
  color: var(--ink-4);
  flex-shrink: 0;
}

.step-indicator {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
  background: var(--bone);
  color: var(--ink-3);
  border: 1px solid var(--line);
}

.workflow-step.is-done .step-indicator {
  background: var(--leaf);
  border-color: var(--leaf);
  color: var(--paper);
}

.workflow-step.is-running .step-indicator {
  background: var(--clay);
  border-color: var(--clay);
  color: var(--paper);
  animation: pulse 1.5s ease-in-out infinite;
}

.workflow-step.is-failed .step-indicator {
  background: var(--crimson);
  border-color: var(--crimson);
  color: var(--paper);
}

@media (max-width: 960px) {
  .workflow-steps {
    grid-template-columns: 1fr 1fr;
  }

  .workflow-step {
    height: 76px;
  }

  .workflow-step + .workflow-step {
    border-left: 0;
  }

  .workflow-step:nth-child(2n) {
    border-left: 1px solid var(--line);
  }

  .workflow-step:nth-child(n + 3) {
    border-top: 1px solid var(--line);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
