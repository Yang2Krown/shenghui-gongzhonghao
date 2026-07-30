<template>
  <div class="creation-workspace">
    <!-- 顶部：选题信息 + 操作 -->
    <header class="workspace-header mb-6">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <el-button text @click="router.push('/content-info')" class="text-ink-3">
              <el-icon><ArrowLeft /></el-icon>
              返回选题列表
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
          <el-button
            v-if="canPublish"
            type="primary"
            :loading="publishing"
            :disabled="saving"
            @click="publishCreation"
          >
            <el-icon><Promotion /></el-icon>
            发布到公众号
          </el-button>
        </div>
      </div>
    </header>

    <!-- 创作进度概览 -->
    <div class="workflow-steps mb-6" :style="{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }">
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

    <!-- 内容区：通过 activeTab 直接切换 -->
    <div class="workspace-content">
      <OutlinePanel
        v-if="activeTab === 'outline'"
        :candidate-id="candidateId"
        :outline-id="currentOutlineId"
        :active-workflow-step="activeWorkflowStep"
        :auto-generate="autoGenerateOutline"
        @pipeline-status="onPipelineStatus"
        @complete="onOutlineComplete"
        @next-step="goWorkflowStep('content')"
      />
      <ContentPanel
        v-if="activeTab === 'content'"
        :candidate-id="candidateId"
        :outline-data="currentOutlineData"
        :title-data="selectedTitle"
        :initial-content="finalContent"
        :auto-generate="autoGenerateContent"
        :outline-text="outlineTextFromQuery"
        :topic-title="topicTitle"
        @complete="onContentComplete"
        @next-step="goWorkflowStep('title')"
        @save-draft="onSaveDraft"
      />
      <TitlePanel
        v-if="activeTab === 'title'"
        :candidate-id="candidateId"
        :outline-data="currentOutlineData"
        :content-data="contentDataForTitle"
        :initial-titles="selectedTitle"
        :step-status="titleStatus"
        :auto-generate="autoGenerateTitle"
        @complete="onTitleComplete"
      />
    </div>

    <!-- 标题确认后操作选择弹窗 -->
    <PublishChoiceDialog
      v-model="showPublishChoice"
      :title="selectedTitle?.title || ''"
      @save-draft="handleSaveDraftAfterTitle"
      @publish="handlePublishAfterTitle"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Document, Check, Promotion } from '@element-plus/icons-vue'
import { useCreationStore } from '@/stores/creation'
import OutlinePanel from '@/components/creation/OutlinePanel.vue'
import TitlePanel from '@/components/creation/TitlePanel.vue'
import ContentPanel from '@/components/creation/ContentPanel.vue'
import PublishChoiceDialog from '@/components/PublishChoiceDialog.vue'
import outlineApi from '@/api/outline'
import generationRecordApi from '@/api/generationRecord'
import { get } from '@/api/api'
import { publishToWechatEditor } from '@/utils/publishToEditor'

const route = useRoute()
const router = useRouter()
const creationStore = useCreationStore()

// 从 URL 获取选题信息
const candidateId = computed(() => route.query.candidate_id || null)
const clusterId = computed(() => route.query.cluster_id || null)
const topicTitle = computed(() => route.query.topic_title || '')
const topicDirection = computed(() => route.query.topic_direction || '')
const isEditing = computed(() => !!route.params.id)
const autoGenerateOutlineFromQuery = computed(() => route.query.auto_generate === 'true')
const autoGenerateContentFromQuery = computed(() => route.query.auto_generate_content === 'true')
const autoGenerateTitleFromQuery = computed(() => route.query.auto_generate_title === 'true')
const outlineEntryCandidateId = ref('')
const contentEntryOutlineText = ref('')
const titleEntrySourceText = ref('')

if (route.query.auto_generate === 'true') {
  outlineEntryCandidateId.value = sessionStorage.getItem('creation_outline_auto_candidate_id') || ''
  if (outlineEntryCandidateId.value) {
    sessionStorage.removeItem('creation_outline_auto_candidate_id')
  }
}

if (route.query.auto_generate_content === 'true') {
  contentEntryOutlineText.value = sessionStorage.getItem('creation_body_outline_text') || ''
  if (contentEntryOutlineText.value) {
    sessionStorage.removeItem('creation_body_outline_text')
  }
}

if (route.query.auto_generate_title === 'true') {
  titleEntrySourceText.value = sessionStorage.getItem('creation_title_content_text') || ''
  if (titleEntrySourceText.value) {
    sessionStorage.removeItem('creation_title_content_text')
  }
}

const hasFreshOutlineEntry = computed(() => {
  return autoGenerateOutlineFromQuery.value
    && !!candidateId.value
    && outlineEntryCandidateId.value === String(candidateId.value)
})
const hasStaleOutlineEntry = computed(() => autoGenerateOutlineFromQuery.value && !hasFreshOutlineEntry.value)
const autoGenerateOutline = computed(() => hasFreshOutlineEntry.value)
const hasFreshContentEntry = computed(() => autoGenerateContentFromQuery.value && !!contentEntryOutlineText.value)
const hasStaleContentEntry = computed(() => autoGenerateContentFromQuery.value && !contentEntryOutlineText.value)
const hasFreshTitleEntry = computed(() => autoGenerateTitleFromQuery.value && !!titleEntrySourceText.value)
const hasStaleTitleEntry = computed(() => autoGenerateTitleFromQuery.value && !titleEntrySourceText.value)

// 从 sessionStorage 读取正文生成入口传来的大纲文本
const outlineTextFromQuery = computed(() => {
  return hasFreshContentEntry.value ? contentEntryOutlineText.value : ''
})

// 从 sessionStorage 读取标题生成入口传来的正文文本
const contentTextForTitle = computed(() => {
  return hasFreshTitleEntry.value ? titleEntrySourceText.value : ''
})

// 状态：根据 query 参数决定初始步骤
const initialStep = hasFreshTitleEntry.value ? 'title' : (hasFreshContentEntry.value ? 'content' : 'outline')
const activeTab = ref(initialStep)
const activeWorkflowStep = ref(initialStep)
const autoGenerateContent = ref(hasFreshContentEntry.value)
const autoGenerateTitle = ref(hasFreshTitleEntry.value)
const saving = ref(false)
const publishing = ref(false)
const showPublishChoice = ref(false)
const currentOutlineId = ref(null)
const currentOutlineData = ref(null)
const selectedTitle = ref(null)
const finalContent = ref(null)
// 持久化输入文本（从任意入口进入时保存，发布时作为兜底）
const sourceText = ref('')

// 标题生成入口：将文本包装为 contentData 格式
const contentDataForTitle = computed(() => {
  if (autoGenerateTitleFromQuery.value && contentTextForTitle.value) {
    return { final_text: contentTextForTitle.value }
  }
  return finalContent.value
})

// 未保存状态追踪
const isDirty = ref(false)

// 创作步骤状态
const outlineStatus = ref('idle')
const contentStatus = ref('idle')
const titleStatus = ref('idle')

// 顶部“发布到公众号”按钮只在标题和正文都准备好后显示。
// 实际上传仍复用下方的公众号编辑器流程：先保存本地创作，再排版、选择公众号账号并上传草稿箱。
const publishTitle = computed(() => (
  selectedTitle.value?.title?.trim()
  || creationStore.currentCreation?.title?.trim()
  || topicTitle.value.trim()
  || ''
))
const publishText = computed(() => (
  finalContent.value?.final_text?.trim()
  || finalContent.value?.content?.trim()
  || ''
))
const canPublish = computed(() => (
  contentStatus.value === 'completed'
  && !!publishTitle.value
  && !!publishText.value
))

const steps = computed(() => {
  if (hasFreshTitleEntry.value) {
    // 从标题生成入口进来，只显示标题
    return [
      { key: 'title', label: '标题', status: titleStatus.value },
    ]
  }
  if (hasFreshContentEntry.value) {
    // 从正文生成入口进来，跳过大纲，只显示正文和标题
    return [
      { key: 'content', label: '正文', status: contentStatus.value },
      { key: 'title', label: '标题', status: titleStatus.value },
    ]
  }
  return [
    { key: 'outline', label: '大纲', status: outlineStatus.value },
    { key: 'content', label: '正文', status: contentStatus.value },
    { key: 'title', label: '标题', status: titleStatus.value },
  ]
})

const stepToTab = {
  outline: 'outline',
  content: 'content',
  title: 'title',
}

const canOpenStep = (key) => {
  if (key === 'outline') return true
  if (key === 'content') return outlineStatus.value === 'completed' || hasFreshContentEntry.value
  if (key === 'title') return contentStatus.value === 'completed' || hasFreshTitleEntry.value
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
      outlineStatus.value = 'completed'
    }

    // 5. 恢复正文
    const contentRecord = byType['content_generate']
    if (contentRecord && contentRecord.output_snapshot) {
      const snap = contentRecord.output_snapshot
      if (snap.final_text) {
        finalContent.value = snap
      }
      contentStatus.value = 'completed'
    }

    // 6. 恢复标题
    const titleRecord = byType['title_generate']
    if (titleRecord && titleRecord.output_snapshot) {
      const snap = titleRecord.output_snapshot
      const recs = snap.recommendations || []
      if (recs.length > 0) {
        selectedTitle.value = { title: recs[0].title, ...recs[0] }
      }
      titleStatus.value = 'completed'
    }

    // 7. 跳到对应步骤（根据点击的记录类型决定）
    const typeToStep = {
      outline_generate: 'outline',
      outline_reevaluate: 'outline',
      content_generate: 'content',
      content_reevaluate: 'content',
      title_generate: 'title',
      title_reevaluate: 'title',
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
onMounted(async () =>  {
  if (hasStaleOutlineEntry.value) {
    router.replace({ name: 'CreationOutline' })
    return
  }
  if (hasStaleContentEntry.value) {
    router.replace({ name: 'CreationBody' })
    return
  }
  if (hasStaleTitleEntry.value) {
    router.replace({ name: 'CreationTitle' })
    return
  }

  // 捕获任意入口传入的输入文本（在 computed 清除 sessionStorage 之前）
  sourceText.value =
    titleEntrySourceText.value ||
    contentEntryOutlineText.value ||
    ''

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

const onPipelineStatus = ({ outline }) => {
  if (outline) outlineStatus.value = outline
  if (outline === 'generating') goWorkflowStep('outline')
}

// 大纲完成回调
const onOutlineComplete = (outlineData) => {
  isDirty.value = true
  outlineStatus.value = 'completed'
  goWorkflowStep('outline')
  const oid = outlineData?.id ?? outlineData?.outline_id ?? null
  currentOutlineId.value = oid
  currentOutlineData.value = outlineData ? { ...outlineData, id: oid } : null
  ElMessage.success('大纲生成完成，可切换到正文生成')
}

// 正文完成回调
const onContentComplete = (contentData) => {
  isDirty.value = true
  contentStatus.value = 'completed'
  finalContent.value = contentData || null
  // 不在这里调 goWorkflowStep —— 由 @next-step 事件统一处理导航
  ElMessage.success('正文生成完成，可切换到标题生成')
}

// 标题完成回调
const onTitleComplete = (titleData) => {
  isDirty.value = true
  titleStatus.value = 'completed'
  selectedTitle.value = titleData
  // 从 TitlePanel 接收输入原文（如果有），作为发布时的兜底
  if (titleData?._sourceText && !sourceText.value) {
    sourceText.value = titleData._sourceText
  }
  showPublishChoice.value = true
}
// 标题确认后 → 保存草稿
const handleSaveDraftAfterTitle = async () => {
  await saveDraft()
}

// 标题确认后 → 保存本地创作并进入公众号编辑器，最终上传到公众号草稿箱
const handlePublishAfterTitle = async () => {
  // 先保存草稿，确保数据不丢
  const savedCreation = await saveDraft(false)
  // 将正文和标题写入 sessionStorage，公众号编辑器 onMounted 时读取
  // fallback 链：finalContent → creationStore → outlineText → sourceText → 空
  let finalText = finalContent.value?.final_text || finalContent.value?.content || ''
  let titleText = selectedTitle.value?.title || ''

  // 如果 finalContent 为空，尝试从 creationStore 恢复
  if (!finalText) {
    try {
      const saved = creationStore.currentCreation
      if (saved?.content) {
        try {
          const parsed = JSON.parse(saved.content)
          if (parsed?.final_text) finalText = parsed.final_text
        } catch {
          finalText = saved.content
        }
      }
      if (!titleText && saved?.title) titleText = saved.title
    } catch { /* ignore */ }
  }

  // 如果仍然为空，尝试从大纲 sections 序列化
  if (!finalText && currentOutlineData.value) {
    const outline = currentOutlineData.value
    if (Array.isArray(outline.sections)) {
      // 把结构化 sections 转成纯文本
      const parts = []
      for (const s of outline.sections) {
        if (s.title) parts.push(`## ${s.title}`)
        if (s.description) parts.push(s.description)
        if (s.core_points?.length) parts.push(s.core_points.join('\n'))
      }
      finalText = parts.join('\n\n')
    } else if (outline.full_text) {
      finalText = outline.full_text
    }
  }

  // 最终兜底：用初始化时捕获的输入文本
  if (!finalText && sourceText.value) {
    finalText = sourceText.value
  }

  if (!finalText) {
    ElMessage.warning('正文内容为空，编辑器将只显示标题。请先完成正文生成或在编辑器中手动输入。')
  }
  // 发布到公众号编辑器（内含 LLM 智能换行 + loading 动画）
  await publishToWechatEditor(router, finalText, titleText, savedCreation?.id || route.params.id || null)
}

// 从 ContentPanel 触发保存草稿（携带当前编辑内容）
const onSaveDraft = async (contentData) => {
  if (contentData) {
    finalContent.value = contentData
  }
  await saveDraft()
}

// 保存草稿
const saveDraft = async (openDraft = true) => {
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
      // 编辑已有创作时保留其发布状态；新建创作默认是未发布草稿。
      status: isEditing.value && creationStore.currentCreation?.status === 'published'
        ? 'published'
        : 'draft',
    }

    const savedCreation = isEditing.value
      ? await creationStore.updateCreation(route.params.id, data)
      : await creationStore.createCreation(data)

    isDirty.value = false
    ElMessage.success('草稿已保存')

    // 保存草稿后直接进入统一的草稿详情页；发布流程则保留当前工作台。
    if (openDraft && savedCreation?.id) {
      await router.push(`/creation/${savedCreation.id}`)
    }

    return savedCreation
  } catch (e) {
    console.error('保存失败:', e)
    throw e
  } finally {
    saving.value = false
  }
}

// 发布
const publishCreation = async () => {
  if (publishing.value) return

  if (contentStatus.value !== 'completed') {
    ElMessage.warning('请先完成正文生成')
    return
  }

  if (!publishTitle.value) {
    ElMessage.warning('请先确认文章标题')
    return
  }

  if (!publishText.value) {
    ElMessage.warning('正文内容为空，请先完成正文生成')
    return
  }

  publishing.value = true
  try {
    // 复用已有的保存、智能排版、公众号编辑器和草稿箱上传流程。
    await handlePublishAfterTitle()
  } catch (e) {
    console.error('发布失败:', e)
    ElMessage.error(e?.response?.data?.detail || '进入发布流程失败，请重试')
  } finally {
    publishing.value = false
  }
}

const getStatusClass = (key) => {
  const statusMap = {
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
  // 只在步骤未完成时自动触发生成；已完成的步骤直接展示结果
  if (key === 'content') {
    autoGenerateContent.value = contentStatus.value !== 'completed'
    autoGenerateTitle.value = false
  } else if (key === 'title') {
    autoGenerateTitle.value = titleStatus.value !== 'completed'
    autoGenerateContent.value = false
  } else {
    autoGenerateContent.value = false
    autoGenerateTitle.value = false
  }
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
.creation-workspace {
  padding-bottom: 73px;
}

.workflow-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
