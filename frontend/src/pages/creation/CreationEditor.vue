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
    <div class="card p-4 mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <div
            v-for="(step, i) in steps"
            :key="step.key"
            class="flex items-center gap-2"
          >
            <div
              class="step-indicator"
              :class="{
                'step-done': step.status === 'completed',
                'step-active': step.status === 'generating',
                'step-pending': step.status === 'idle' || step.status === 'failed',
              }"
            >
              <el-icon v-if="step.status === 'completed'" :size="14"><Check /></el-icon>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <span class="text-sm" :class="step.status === 'completed' ? 'text-ink font-medium' : 'text-ink-3'">
              {{ step.label }}
            </span>
            <el-icon v-if="i < steps.length - 1" class="text-ink-4 mx-1"><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 页签 -->
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
          @complete="onOutlineComplete"
          @next-step="activeTab = 'title'"
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
          @next-step="activeTab = 'content'"
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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight, Document, Check } from '@element-plus/icons-vue'
import { useCreationStore } from '@/stores/creation'
import OutlinePanel from '@/components/creation/OutlinePanel.vue'
import TitlePanel from '@/components/creation/TitlePanel.vue'
import ContentPanel from '@/components/creation/ContentPanel.vue'
import outlineApi from '@/api/outline'

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
const saving = ref(false)
const publishing = ref(false)
const currentOutlineId = ref(null)
const currentOutlineData = ref(null)
const selectedTitle = ref(null)
const finalContent = ref(null)

// 创作步骤状态
const outlineStatus = ref('idle')
const titleStatus = ref('idle')
const contentStatus = ref('idle')

const steps = computed(() => [
  { key: 'outline', label: '大纲', status: outlineStatus.value },
  { key: 'title', label: '标题', status: titleStatus.value },
  { key: 'content', label: '正文', status: contentStatus.value },
])

// 加载已有创作数据
onMounted(async () => {
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

// 大纲完成回调（留在当前 tab，不自动跳转）
const onOutlineComplete = (outlineData) => {
  outlineStatus.value = 'completed'
  // 大纲流水线 SSE 返回的字段是 outline_id；获取详情接口返回的是 id —— 两边兼容
  const oid = outlineData?.id ?? outlineData?.outline_id ?? null
  currentOutlineId.value = oid
  currentOutlineData.value = outlineData ? { ...outlineData, id: oid } : null
  ElMessage.success('大纲生成完成，可切换到标题生成')
}

// 标题完成回调
const onTitleComplete = (titleData) => {
  titleStatus.value = 'completed'
  selectedTitle.value = titleData
}

// 正文完成回调
const onContentComplete = (contentData) => {
  contentStatus.value = 'completed'
  finalContent.value = contentData || null
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
</script>

<style scoped>
.workspace-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
}

.creation-workspace {
  padding-bottom: 73px;
}

.workspace-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  padding: 0 20px;
  height: 44px;
  line-height: 44px;
}

.tab-label-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tab-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-done {
  background: var(--leaf);
}

.dot-active {
  background: var(--clay);
  animation: pulse 1.5s ease-in-out infinite;
}

.dot-failed {
  background: var(--crimson);
}

.dot-pending {
  background: var(--line);
}

.step-indicator {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-done {
  background: var(--leaf);
  color: var(--paper);
}

.step-active {
  background: var(--clay);
  color: var(--paper);
  animation: pulse 1.5s ease-in-out infinite;
}

.step-pending {
  background: var(--bone);
  color: var(--ink-3);
  border: 1px solid var(--line);
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
