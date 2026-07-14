<template>
  <div class="creation-draft">
    <!-- 顶部：返回 + 操作 -->
    <header class="draft-header mb-6">
      <div class="draft-header-main">
        <div class="draft-header-copy">
          <el-button text @click="router.push('/creation-history')" class="draft-header-back text-ink-3">
            <el-icon><ArrowLeft /></el-icon>
            返回草稿箱
          </el-button>
          <div v-if="titleViewMode === 'preview'" class="draft-title-display mt-2">
            {{ editableTitle || creation.title || '无标题' }}
          </div>
          <div v-else class="title-edit-view mt-2">
            <div class="title-edit-row">
              <el-input
                v-model="editableTitle"
                class="title-edit-input"
                maxlength="500"
                placeholder="请输入文章标题"
              />
              <el-dropdown v-if="titleOptions.length" trigger="click" @command="selectTitleVersion">
                <button type="button" class="title-picker-button" aria-label="选择历史标题">
                  <el-icon><ArrowDown /></el-icon>
                </button>
                <template #dropdown>
                  <el-dropdown-menu class="title-version-menu">
                    <el-dropdown-item
                      v-for="(option, index) in titleOptions"
                      :key="`title-${option.record_id || 'current'}-${index}`"
                      :command="option.value"
                    >
                      <span class="select-option-title">{{ option.value }}</span>
                      <small v-if="option.is_current">当前版本</small>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <div class="flex items-center gap-3 mt-2">
            <span :class="['c-status', `c-status-${creation.status || 'draft'}`]">
              {{ getStatusName(creation.status) }}
            </span>
            <span class="text-sm text-ink-3">
              {{ creation.word_count || 0 }} 字 · 更新于 {{ formatDate(creation.updated_at) }}
            </span>
          </div>
        </div>
        <div class="draft-header-actions">
          <div class="title-view-toolbar">
            <div class="view-toggle">
              <button class="toggle-btn" :class="{ active: titleViewMode === 'edit' }" @click="titleViewMode = 'edit'">编辑</button>
              <button class="toggle-btn" :class="{ active: titleViewMode === 'preview' }" @click="titleViewMode = 'preview'">预览</button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- 源选题：在弹窗中展示，避免离开当前草稿 -->
    <div v-if="creation.candidate_id || creation.cluster_id || creation.topic_title" class="traceback-bar mb-5">
      <div class="traceback-copy">
        <span class="traceback-label">来源选题</span>
        <span class="traceback-title">{{ sourceTopic?.candidate?.title || creation.topic_title || '正在查找源选题…' }}</span>
      </div>
      <el-button size="small" plain :loading="sourceLoading" @click="openSourceTopic">
        <el-icon><Connection /></el-icon>
        查看源话题
      </el-button>
    </div>

    <!-- 主体：左右分栏 -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-2 text-ink-3">加载中...</span>
    </div>

    <div v-else-if="!creation.id" class="text-center py-20">
      <el-icon :size="64" class="text-ink-4"><Document /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4">创作不存在</h3>
      <el-button type="primary" class="mt-4" @click="router.push('/creation-history')">返回草稿箱</el-button>
    </div>

    <div v-else class="draft-content">
      <!-- 正文编辑区 -->
      <div class="draft-main-column">
        <div class="card p-5 mb-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-h4 font-sans text-ink">文章正文</h3>
            <div class="flex items-center gap-2">
              <div class="view-toggle">
                <button class="toggle-btn" :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
                <button class="toggle-btn" :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
              </div>
              <el-button link size="small" @click="copyText">
                <el-icon><DocumentCopy /></el-icon> 复制
              </el-button>
            </div>
          </div>

          <el-input
            v-if="viewMode === 'edit'"
            v-model="editableText"
            type="textarea"
            :autosize="{ minRows: 18, maxRows: 60 }"
            class="content-edit"
            resize="vertical"
          />
          <div v-else class="content-preview prose" v-html="renderedHtml" />
        </div>
      </div>
    </div>

    <!-- 固定底部操作栏 -->
    <div v-if="creation.id" class="draft-bottom-bar">
      <div class="bottom-bar-inner">
        <el-button @click="saveDraft" :loading="saving">
          <el-icon><Document /></el-icon>
          保存草稿
        </el-button>
        <el-button type="primary" @click="showWechatDraft = true">
          <el-icon><Promotion /></el-icon>
          发布到公众号草稿箱
        </el-button>
      </div>
    </div>

    <!-- 公众号草稿箱弹窗 -->
    <WechatDraftDialog
      v-model="showWechatDraft"
      :title="editableTitle || creation.title || ''"
      :content="editableText"
      :content-html="editableText"
      @success="handleWechatDraftSuccess"
    />

    <!-- 源话题详情 -->
    <el-dialog
      v-model="showSourceTopic"
      title="源话题"
      width="760px"
      class="source-topic-dialog"
      modal-class="source-topic-modal-overlay"
      :lock-scroll="false"
    >
      <div v-if="sourceLoading" class="source-loading">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span>正在查找源话题…</span>
      </div>
      <div v-else-if="sourceTopic" class="source-topic-content">
        <div class="source-topic-tags">
          <span v-if="sourceTopic.cluster?.info_type" class="source-topic-tag">{{ sourceTopic.cluster.info_type }}</span>
          <span v-if="sourceTopic.cluster?.freshness" class="source-topic-tag">{{ getFreshnessName(sourceTopic.cluster.freshness) }}</span>
        </div>
        <h3>{{ sourceTopic.cluster?.core_title_zh || sourceTopic.cluster?.latest_title || sourceTopic.candidate?.title || '源话题' }}</h3>
        <p v-if="sourceTopic.candidate?.title && sourceTopic.candidate.title !== sourceTopic.cluster?.core_title_zh" class="source-candidate-title">
          选题角度：{{ sourceTopic.candidate.title }}
        </p>
        <p class="source-topic-summary">{{ sourceTopic.cluster?.summary_zh || sourceTopic.cluster?.summary || sourceTopic.candidate?.summary || '暂无摘要' }}</p>
        <div v-if="sourceLinks.length" class="source-topic-links">
          <div class="source-topic-links-header">
            <div>
              <div class="source-topic-links-title">原文来源</div>
              <div class="source-topic-links-count">共 {{ sourceLinks.length }} 条相关报道</div>
            </div>
          </div>
          <div class="source-link-list">
            <a
              v-for="(source, index) in sourceLinks"
              :key="`${source.url}-${index}`"
              :href="source.url"
              target="_blank"
              rel="noopener noreferrer"
              class="source-link-item"
            >
              <span class="source-link-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="source-link-copy">
                <span class="source-link-title">{{ source.title }}</span>
                <span class="source-link-host">{{ sourceHost(source.url) }}</span>
              </span>
              <span class="source-link-open" aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂时找不到源话题" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowDown, Document, DocumentCopy, Connection, Loading, Promotion } from '@element-plus/icons-vue'
import WechatDraftDialog from '@/components/WechatDraftDialog.vue'
import { useCreationStore } from '@/stores/creation'
import { getCreationAdjustmentOptions, markCreationPublished } from '@/api/creation'
import { get } from '@/api/api'

const route = useRoute()
const router = useRouter()
const creationStore = useCreationStore()

// 状态
const loading = ref(false)
const saving = ref(false)
const creation = ref({})
const editableTitle = ref('')
const editableText = ref('')
const viewMode = ref('preview')
const titleViewMode = ref('preview')
const showWechatDraft = ref(false)
const titleOptions = ref([])
const sourceTopic = ref(null)
const sourceLoading = ref(false)
const showSourceTopic = ref(false)

// 加载创作数据
onMounted(async () => {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    const data = await creationStore.fetchCreationById(id)
    creation.value = data || {}
    editableTitle.value = data?.title || ''
    // 尝试解析 JSON 内容（包含 agent 数据），否则按纯文本
    const raw = data?.content || ''
    let text = raw
    if (raw && raw !== 'null') {
      try {
        const parsed = JSON.parse(raw)
        if (typeof parsed === 'object' && parsed && parsed.final_text) {
          text = parsed.final_text
          // 将生成快照中的辅助字段合并到本地，保存时继续保留旧数据
          creation.value = { ...creation.value, ...parsed }
        }
      } catch {}
    }
    editableText.value = text
    await loadAdjustmentOptions()
  } catch (e) {
    console.error('加载创作失败:', e)
  } finally {
    loading.value = false
  }
})

const loadAdjustmentOptions = async () => {
  if (!creation.value.id) return
  try {
    const res = await getCreationAdjustmentOptions(creation.value.id)
    const data = res.data || res
    titleOptions.value = data.titles || []
    if (data.creation?.title) editableTitle.value = data.creation.title
  } catch (e) {
    console.warn('加载历史标题和正文版本失败:', e)
  }
}

const selectTitleVersion = (title) => {
  if (!title) return
  editableTitle.value = title
}

const sourceLinks = computed(() => {
  const cluster = sourceTopic.value?.cluster
  const rawInfos = cluster?.raw_infos || []
  if (rawInfos.length) {
    return rawInfos
      .filter((item) => /^https?:\/\//i.test(item?.url || ''))
      .map((item) => ({ title: item.title || item.url, url: item.url }))
  }
  return (cluster?.source_urls || [])
    .filter((url) => /^https?:\/\//i.test(url || ''))
    .map((url) => ({ title: url, url }))
})

const sourceHost = (url) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url || '原文链接'
  }
}

const getFreshnessName = (freshness) => {
  const map = { earlier: '较早', latest: '最新', recent: '近期', ongoing: '持续' }
  return map[freshness] || freshness
}

const openSourceTopic = async () => {
  showSourceTopic.value = true
  if (sourceTopic.value || (!creation.value.candidate_id && !creation.value.cluster_id)) return

  sourceLoading.value = true
  try {
    let candidate = null
    if (creation.value.candidate_id) {
      const candidateRes = await get(`/topic-candidates/${creation.value.candidate_id}`)
      candidate = candidateRes.data || candidateRes
    }
    const clusterId = candidate?.info_cluster_id || candidate?.cluster?.id || creation.value.cluster_id
    let cluster = candidate?.cluster || null

    if (clusterId) {
      const clusterRes = await get(`/topic-clusters/${clusterId}`)
      cluster = clusterRes.data || clusterRes
      creation.value.cluster_id = clusterId
    }

    sourceTopic.value = { candidate, cluster }
  } catch (e) {
    console.error('查找源话题失败:', e)
    ElMessage.warning('暂时找不到源话题，请稍后重试')
  } finally {
    sourceLoading.value = false
  }
}

// 保存草稿（存为 JSON，保留 agent 数据）
const saveDraft = async () => {
  if (!creation.value.id) return
  saving.value = true
  try {
    // 重建完整内容对象：保留 agent 数据，更新编辑后的文本
    const contentObj = {
      final_text: editableText.value,
      final_word_count: editableText.value.length,
      style_anchor: creation.value.style_anchor,
      gold_sentences: creation.value.gold_sentences,
      rewrite_table: creation.value.rewrite_table,
      factual_summary: creation.value.factual_summary,
      factual_corrections: creation.value.factual_corrections,
      section_count: creation.value.section_count,
      rewrite_count: creation.value.rewrite_count,
    }
    const plain = editableText.value.replace(/[#*`>_~\-]/g, '').trim()
    const summary = plain.slice(0, 120)
    await creationStore.updateCreation(creation.value.id, {
      title: editableTitle.value.trim(),
      content: JSON.stringify(contentObj),
      summary: summary || null,
      word_count: editableText.value.length,
    })
    // 同步本地状态
    creation.value.content = JSON.stringify(contentObj)
    creation.value.title = editableTitle.value.trim()
    creation.value.final_text = contentObj.final_text
    creation.value.word_count = editableText.value.length
  } catch (e) {
    console.error('保存失败:', e)
  } finally {
    saving.value = false
  }
}

// 复制正文
const copyText = async () => {
  try {
    await navigator.clipboard.writeText(editableText.value)
    ElMessage.success('正文已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

const handleWechatDraftSuccess = async () => {
  if (!creation.value.id) return
  try {
    const res = await markCreationPublished(creation.value.id, 'wechat_draft')
    creation.value = res.data || res
    ElMessage.success('创作历史已标记为已发布')
  } catch (e) {
    console.error('同步创作发布状态失败:', e)
    ElMessage.warning('文章已上传草稿箱，但创作历史状态同步失败，请稍后刷新重试')
  }
}

// 正文渲染
const renderedHtml = computed(() => {
  const txt = editableText.value || ''
  return txt
    .split(/\n\n+/)
    .map((para) => {
      const trimmed = para.trim()
      if (!trimmed) return ''
      if (trimmed.startsWith('### ')) return `<h3>${escapeHtml(trimmed.slice(4))}</h3>`
      if (trimmed.startsWith('## ')) return `<h2>${escapeHtml(trimmed.slice(3))}</h2>`
      if (trimmed.startsWith('# ')) return `<h2>${escapeHtml(trimmed.slice(2))}</h2>`
      return `<p>${escapeHtml(trimmed).replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
})

// 允许保留的安全 HTML 标签（后端可能直接输出）
const SAFE_TAGS = 'strong|em|b|i|u|s|sup|sub|br'
const SAFE_TAG_RE = new RegExp(`<(${SAFE_TAGS})(\\s[^>]*)?>`, 'gi')
const SAFE_CLOSE_RE = new RegExp(`</(${SAFE_TAGS})>`, 'gi')

function escapeHtml(s) {
  const placeholders = []
  let i = 0
  const protected_ = s
    .replace(SAFE_TAG_RE, (m) => { placeholders.push(m); return `\x00PH${i++}\x00` })
    .replace(SAFE_CLOSE_RE, (m) => { placeholders.push(m); return `\x00PH${i++}\x00` })
  const escaped = protected_
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  return escaped.replace(/\x00PH(\d+)\x00/g, (_, idx) => placeholders[+idx])
}

// 工具函数
const getStatusName = (status) => {
  const map = { draft: '草稿', published: '已发布', archived: '已归档' }
  return map[status] || status
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diff = Math.abs(now - date)
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
  if (days === 1) return '今天'
  if (days === 2) return '昨天'
  if (days <= 7) return `${days - 1}天前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.creation-draft {
  width: min(100%, 980px);
  margin: 0 auto;
  padding: 0 28px 110px;
  box-sizing: border-box;
}

.draft-header {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

.draft-header-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  width: 100%;
}

.draft-header-copy {
  flex: 1;
  min-width: 0;
}

.draft-header-back {
  margin-left: -8px;
}

.draft-header-actions {
  flex-shrink: 0;
  padding-top: 44px;
}

/* 溯源栏 */
.traceback-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--paper);
  border-radius: var(--r-md);
  border: 1px solid var(--line);
  box-shadow: 0 5px 16px rgba(71, 54, 39, 0.045);
}

.traceback-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-3);
  flex-shrink: 0;
}

.traceback-copy {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.traceback-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink);
  font-family: var(--font-serif, inherit);
}

.draft-main-column {
  min-width: 0;
}

.content-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.draft-title-display {
  max-width: 100%;
  overflow-wrap: anywhere;
  color: var(--ink);
  font-family: var(--font-serif, Georgia, serif);
  font-size: clamp(22px, 2.1vw, 27px);
  font-weight: 500;
  letter-spacing: -0.025em;
  line-height: 1.25;
}

.title-edit-view {
  width: 100%;
}

.title-edit-row {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 6px;
}

.title-edit-input {
  flex: 1;
  min-width: 0;
}

.title-edit-input :deep(.el-input__inner) {
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  box-shadow: none;
  color: var(--ink);
  font-family: var(--font-serif, Georgia, serif);
  font-size: clamp(22px, 2.1vw, 27px);
  font-weight: 500;
  letter-spacing: -0.025em;
  line-height: 1.25;
}

.title-edit-input :deep(.el-input__wrapper) {
  min-height: 46px;
  padding: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: 0 1px 0 var(--line);
}

.title-edit-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 2px 0 var(--clay);
}

.title-view-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.title-picker-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  flex-shrink: 0;
}

.title-picker-button:hover {
  color: var(--clay-deep);
}

:deep(.title-version-menu) {
  min-width: 420px;
}

:deep(.title-version-menu .el-dropdown-menu__item) {
  max-width: 520px;
  padding-top: 10px;
  padding-bottom: 10px;
  font-size: 15px;
  line-height: 1.5;
}

.select-option-title {
  display: inline-block;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  white-space: nowrap;
}

.select-option-title + small {
  float: right;
  margin-left: 12px;
  color: var(--ink-4);
  font-size: 11px;
}

.source-topic-content h3 {
  margin: 12px 0 8px;
  color: var(--ink);
  font-family: var(--font-serif, inherit);
  font-size: 24px;
  line-height: 1.4;
}

:global(.source-topic-modal-overlay) {
  box-sizing: border-box;
  padding: 0;
}

:global(.source-topic-modal-overlay .el-overlay-dialog) {
  display: flex;
  align-items: center;
  justify-content: center;
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 248px;
  width: auto;
  height: auto;
  max-height: none;
  overflow: auto;
}

:global(.source-topic-modal-overlay .el-dialog) {
  max-width: 100%;
  margin: 0 !important;
}

:deep(.source-topic-dialog .el-dialog) {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: var(--paper);
  box-shadow: 0 24px 60px rgba(42, 38, 32, 0.16);
}

:deep(.source-topic-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 18px 24px 4px;
}

:deep(.source-topic-dialog .el-dialog__title) {
  color: var(--ink);
  font-family: var(--font-serif, Georgia, serif);
  font-size: 24px;
  font-weight: 500;
}

:deep(.source-topic-dialog .el-dialog__headerbtn) {
  top: 22px;
  right: 24px;
}

:deep(.source-topic-dialog .el-dialog__body) {
  padding: 8px 24px 18px;
}

.source-topic-content {
  padding-top: 4px;
}

.source-topic-tags {
  display: flex;
  gap: 6px;
}

.source-topic-tag {
  padding: 3px 8px;
  border-radius: var(--r-pill);
  background: var(--bone);
  color: var(--ink-3);
  font-size: 11px;
  letter-spacing: 0.02em;
}

.source-candidate-title,
.source-topic-summary {
  color: var(--ink-3);
  line-height: 1.7;
}

.source-topic-links {
  margin-top: 22px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--ivory);
}

.source-topic-links-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.source-topic-links-title {
  color: var(--ink);
  font-size: 16px;
  font-weight: 600;
}

.source-topic-links-count {
  margin-top: 3px;
  color: var(--ink-4);
  font-size: 12px;
}

.source-link-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 238px;
  padding: 2px 6px 2px 0;
  overflow-y: auto;
  scrollbar-color: var(--clay-soft) transparent;
  scrollbar-width: thin;
}

.source-link-list::-webkit-scrollbar {
  width: 6px;
}

.source-link-list::-webkit-scrollbar-track {
  background: transparent;
}

.source-link-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: var(--clay-soft);
}

.source-link-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  min-height: 64px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--ivory);
  color: inherit;
  text-decoration: none;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.source-link-item:hover {
  background: var(--paper);
  border-color: var(--line);
}

.source-link-index {
  width: 24px;
  color: var(--ink-4);
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  flex-shrink: 0;
}

.source-link-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  gap: 3px;
}

.source-link-title {
  overflow: hidden;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link-host {
  overflow: hidden;
  color: var(--ink-4);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link-open {
  color: var(--clay-deep);
  font-size: 18px;
  line-height: 1;
  flex-shrink: 0;
}

.source-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 160px;
  color: var(--ink-3);
}

/* 正文编辑/预览 */
.content-edit :deep(.el-textarea__inner) {
  font-family: var(--font-serif, inherit);
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink);
  background: var(--paper);
}

.content-preview {
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink);
  min-height: 200px;
}

.content-preview :deep(h2) {
  font-size: 22px;
  font-weight: 600;
  margin: 24px 0 12px;
  color: var(--ink);
}

.content-preview :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  margin: 20px 0 10px;
  color: var(--ink);
}

.content-preview :deep(p) {
  margin-bottom: 14px;
}

/* 视图切换 */
.view-toggle {
  display: inline-flex;
  background: var(--bone);
  border-radius: var(--r-pill);
  padding: 3px;
  flex-shrink: 0;
}

.toggle-btn {
  padding: 4px 14px;
  border: none;
  background: transparent;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3);
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1.4;
}

.toggle-btn.active {
  background: var(--paper);
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* 状态徽标 */
.c-status {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.c-status-draft {
  background: var(--bone);
  color: #6B6862;
  border: 1px solid var(--line);
}

.c-status-published {
  background: #DAF0DC;
  color: #2A6B3A;
  border: 1px solid #A8D6B0;
}

.c-status-archived {
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
}

/* 固定底部操作栏 */
.draft-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 248px;
  right: 0;
  z-index: 100;
  background: var(--paper);
  border-top: 1px solid var(--line);
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);
  height: 65px;
  display: flex;
  align-items: center;
}

.draft-bottom-bar .bottom-bar-inner {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
  width: 100%;
}

@media (max-width: 720px) {
  :global(.source-topic-modal-overlay) {
    padding: 0;
  }

  :global(.source-topic-modal-overlay .el-overlay-dialog) {
    left: 0;
  }

  :deep(.source-topic-dialog .el-dialog__header) {
    padding-right: 18px;
    padding-left: 18px;
  }

  :deep(.source-topic-dialog .el-dialog__body) {
    padding-right: 18px;
    padding-left: 18px;
  }

  .creation-draft {
    padding-right: 16px;
    padding-left: 16px;
  }

  .draft-bottom-bar {
    left: 0;
  }
}
</style>
