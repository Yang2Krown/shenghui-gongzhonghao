<template>
  <div class="versions-page">
    <header class="versions-hero">
      <div>
        <el-button text class="back-button" @click="router.push(`/creation/${route.params.id}`)">
          <el-icon><ArrowLeft /></el-icon> 返回文章
        </el-button>
        <div class="eyebrow">ARTICLE HISTORY · PHASE 1C</div>
        <h1>{{ creationTitle || '文章版本' }}</h1>
        <p>只在你明确点击“保存版本”时留下快照；自动保存和发布流程保持不变。</p>
      </div>
      <el-button type="primary" size="large" @click="saveDialogVisible = true">
        <el-icon><Plus /></el-icon> 保存版本
      </el-button>
    </header>

    <section class="toolbar-card">
      <div>
        <span class="toolbar-label">版本时间线</span>
        <span class="toolbar-meta">{{ versions.length }} 个显式快照</span>
      </div>
      <div class="toolbar-actions">
        <el-select v-model="versionTypeFilter" clearable placeholder="全部类型" size="default" @change="loadVersions">
          <el-option v-for="item in versionTypes" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button :loading="loading" @click="loadVersions">刷新</el-button>
      </div>
    </section>

    <section v-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>正在加载版本时间线…</span>
    </section>
    <el-empty v-else-if="!versions.length" description="还没有显式版本，先保存一个会前版或手动版吧" />
    <section v-else class="timeline-card">
      <el-timeline>
        <el-timeline-item
          v-for="version in versions"
          :key="version.id"
          :timestamp="formatDate(version.created_at)"
          placement="top"
          :type="version.id === selectedAfterId ? 'primary' : undefined"
        >
          <article class="version-item" :class="{ 'is-selected': version.id === selectedAfterId }">
            <div class="version-item-head">
              <div>
                <div class="version-kicker">
                  <span class="version-number">v{{ version.version_no }}</span>
                  <el-tag size="small" effect="plain">{{ versionTypeLabel(version.version_type) }}</el-tag>
                  <span v-if="version.semantic_summary_status" class="summary-state" :class="`summary-${version.semantic_summary_status}`">
                    {{ summaryStatusLabel(version.semantic_summary_status) }}
                  </span>
                </div>
                <h2>{{ version.title }}</h2>
              </div>
              <div class="version-actions">
                <el-button text size="small" @click="openDetail(version)">查看内容</el-button>
                <el-button text size="small" @click="setBefore(version)">设为前版</el-button>
                <el-button text size="small" type="primary" @click="setAfter(version)">设为后版</el-button>
              </div>
            </div>
            <div class="version-meta">
              <span>{{ version.word_count || 0 }} 字</span>
              <span>{{ version.created_by_user?.full_name || version.created_by_user?.username || '团队成员' }}</span>
              <span v-if="version.note">备注：{{ version.note }}</span>
              <span v-if="version.suggestion">建议：{{ shorten(version.suggestion.content) }}</span>
            </div>
          </article>
        </el-timeline-item>
      </el-timeline>
    </section>

    <section v-if="versions.length > 1" class="compare-card">
      <div>
        <span class="eyebrow">COMPARE</span>
        <h2>选择两个版本查看修改</h2>
        <p>前版是修改前内容，后版是修改后内容。文本 diff 不依赖 LLM，始终可用。</p>
      </div>
      <div class="compare-controls">
        <el-select v-model="selectedBeforeId" placeholder="选择前版" clearable>
          <el-option v-for="version in versions" :key="`before-${version.id}`" :label="versionOptionLabel(version)" :value="version.id" />
        </el-select>
        <span class="arrow">→</span>
        <el-select v-model="selectedAfterId" placeholder="选择后版" clearable>
          <el-option v-for="version in versions" :key="`after-${version.id}`" :label="versionOptionLabel(version)" :value="version.id" />
        </el-select>
        <el-button type="primary" :disabled="!canCompare" :loading="diffLoading" @click="openDiff">查看 diff</el-button>
      </div>
    </section>

    <el-dialog v-model="saveDialogVisible" title="保存文章版本" width="560px" align-center destroy-on-close :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="restoreDialogScroll">
      <el-form :model="saveForm" label-position="top">
        <el-form-item label="版本类型" required>
          <el-select v-model="saveForm.version_type" style="width: 100%">
            <el-option v-for="item in versionTypes" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联会议建议">
          <el-select v-model="saveForm.suggestion_id" clearable filterable style="width: 100%" placeholder="可选：选择已关联当前文章的会议建议">
            <el-option v-for="suggestion in suggestions" :key="suggestion.id" :label="`#${suggestion.id} ${suggestion.content}`" :value="suggestion.id" />
          </el-select>
          <small class="form-help">只有已关联到当前文章的建议会出现在这里。</small>
        </el-form-item>
        <el-form-item label="版本备注">
          <el-input v-model="saveForm.note" type="textarea" :rows="3" maxlength="5000" show-word-limit placeholder="例如：会前版，保留原始开头和案例段落" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="saveForm.save_as_experience">同时沉淀为经验卡片</el-checkbox>
        </el-form-item>
        <template v-if="saveForm.save_as_experience">
          <el-form-item label="经验标题">
            <el-input v-model="saveForm.experience_title" maxlength="200" placeholder="留空则自动生成" />
          </el-form-item>
          <el-form-item label="经验分类">
            <el-input v-model="saveForm.experience_category" maxlength="50" placeholder="例如：开头、结构、案例、表达" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveVersion">确认保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="版本内容" width="820px" align-center destroy-on-close :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="restoreDialogScroll">
      <div v-if="detailVersion" class="version-detail">
        <div class="detail-summary">
          <strong>v{{ detailVersion.version_no }} · {{ versionTypeLabel(detailVersion.version_type) }}</strong>
          <span>{{ detailVersion.word_count || 0 }} 字 · {{ formatDate(detailVersion.created_at) }}</span>
        </div>
        <p v-if="detailVersion.note" class="detail-note">备注：{{ detailVersion.note }}</p>
        <pre class="version-text">{{ detailVersion.content_text || '' }}</pre>
      </div>
    </el-dialog>

    <el-dialog v-model="diffVisible" title="版本对比" width="980px" align-center destroy-on-close :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="restoreDialogScroll">
      <div v-if="diffData" class="diff-dialog">
        <div class="diff-header">
          <div>
            <strong>v{{ diffData.before_version_no }} → v{{ diffData.after_version_no }}</strong>
            <span>{{ diffData.before_word_count }} 字 → {{ diffData.after_word_count }} 字</span>
          </div>
          <div class="diff-counts"><span class="added-count">+{{ diffData.added_count }}</span><span class="removed-count">-{{ diffData.removed_count }}</span></div>
        </div>
        <div class="diff-legend"><span class="legend-added">新增</span><span class="legend-removed">删除</span><span class="legend-unchanged">未变化</span><span class="diff-ready">文本 diff 可用</span></div>
        <div class="diff-lines">
          <div v-for="(line, index) in diffData.lines" :key="`${index}-${line.kind}`" :class="['diff-line', `diff-line-${line.kind}`]"><span class="line-mark">{{ line.kind === 'added' ? '+' : line.kind === 'removed' ? '-' : ' ' }}</span><span>{{ line.text || ' ' }}</span></div>
        </div>
        <section class="semantic-panel">
          <div class="semantic-head"><div><span class="eyebrow">SEMANTIC SUMMARY</span><h3>为什么这样改</h3></div><div class="semantic-actions"><el-tag v-if="semanticStatus === 'succeeded'" type="success" effect="plain">已完成</el-tag><el-tag v-else-if="semanticStatus === 'failed'" type="danger" effect="plain">生成失败</el-tag><el-tag v-else-if="semanticStatus" type="warning" effect="plain">生成中</el-tag><el-button v-if="semanticStatus === 'failed'" size="small" type="warning" @click="triggerSummary(true)">重试</el-button><el-button v-else-if="!semanticStatus" size="small" type="primary" @click="triggerSummary(false)">生成语义摘要</el-button></div></div>
          <div v-if="semanticStatus === 'running' || semanticStatus === 'queued'" class="semantic-running"><el-icon class="is-loading"><Loading /></el-icon> 语义摘要正在后台生成，文本 diff 不受影响。</div>
          <div v-else-if="semanticStatus === 'failed'" class="semantic-failed">LLM 没有返回可解析的摘要。{{ diffData.semantic_summary?.error || '' }}<span v-if="diffData.semantic_summary?.raw_output">原始输出已保留，可重试。</span></div>
          <div v-else-if="diffData.semantic_summary?.summary" class="semantic-result"><p>{{ diffData.semantic_summary.summary }}</p><div v-for="(change, index) in diffData.semantic_summary.changes || []" :key="index" class="semantic-change"><strong>{{ change.position || '修改点' }}</strong><span>{{ change.before || '（无）' }} → {{ change.after || '（无）' }}</span><small>原因：{{ change.reason || '未在输入中明确' }}</small></div><p v-if="diffData.semantic_summary.suggestion_match" class="suggestion-match">关联建议：{{ diffData.semantic_summary.suggestion_match }}</p></div>
          <el-empty v-else :image-size="42" description="尚未生成语义摘要" />
        </section>
      </div>
      <el-empty v-else description="暂无对比数据" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Loading, Plus } from '@element-plus/icons-vue'
import {
  diffContentVersions,
  getContentVersion,
  listContentVersions,
  saveContentVersion,
  summarizeContentVersions,
} from '@/api/contentVersions'
import { getCreationById } from '@/api/creation'
import { formatDateTimeMinute } from '@/utils/dateTime'
import { useDialogScrollPosition } from '@/utils/dialogScrollPosition'

const route = useRoute()
const router = useRouter()
const { rememberDialogScroll, restoreDialogScroll } = useDialogScrollPosition()
const creationTitle = ref('')
const versions = ref([])
const suggestions = ref([])
const loading = ref(false)
const saving = ref(false)
const diffLoading = ref(false)
const versionTypeFilter = ref('')
const selectedBeforeId = ref(null)
const selectedAfterId = ref(null)
const saveDialogVisible = ref(false)
const detailVisible = ref(false)
const detailVersion = ref(null)
const diffVisible = ref(false)
const diffData = ref(null)
let pollTimer = null

const saveForm = reactive({
  version_type: 'manual',
  suggestion_id: null,
  note: '',
  save_as_experience: false,
  experience_title: '',
  experience_category: '',
})

const versionTypes = [
  { value: 'before_meeting', label: '会前版' },
  { value: 'after_meeting', label: '会后版' },
  { value: 'before_review', label: '审稿前' },
  { value: 'final', label: '终稿' },
  { value: 'manual', label: '手动保存' },
]

const versionTypeLabel = (value) => versionTypes.find((item) => item.value === value)?.label || value || '手动保存'
const summaryStatusLabel = (value) => ({ queued: '摘要排队中', running: '摘要生成中', succeeded: '语义摘要已完成', failed: '摘要失败' }[value] || value)
const formatDate = formatDateTimeMinute
const shorten = (value, length = 70) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  return text.length > length ? `${text.slice(0, length)}…` : text
}
const versionOptionLabel = (version) => `v${version.version_no} · ${versionTypeLabel(version.version_type)} · ${formatDate(version.created_at)}`
const canCompare = computed(() => selectedBeforeId.value && selectedAfterId.value && selectedBeforeId.value !== selectedAfterId.value)
const semanticStatus = computed(() => diffData.value?.semantic_summary?.status || null)

const loadVersions = async () => {
  loading.value = true
  try {
    const response = await listContentVersions(route.params.id, versionTypeFilter.value ? { version_type: versionTypeFilter.value } : {})
    const data = response.data || {}
    versions.value = data.items || []
    suggestions.value = data.suggestions || []
    creationTitle.value = versions.value[0]?.title || creationTitle.value
    if (!selectedAfterId.value && versions.value.length) selectedAfterId.value = versions.value[0].id
    if (!selectedBeforeId.value && versions.value.length > 1) selectedBeforeId.value = versions.value[1].id
    if (selectedBeforeId.value && !versions.value.some((item) => item.id === selectedBeforeId.value)) selectedBeforeId.value = versions.value[1]?.id || null
    if (selectedAfterId.value && !versions.value.some((item) => item.id === selectedAfterId.value)) selectedAfterId.value = versions.value[0]?.id || null
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '版本列表加载失败')
  } finally {
    loading.value = false
  }
}

const saveVersion = async () => {
  saving.value = true
  try {
    const response = await saveContentVersion(route.params.id, {
      version_type: saveForm.version_type,
      note: saveForm.note || null,
      suggestion_id: saveForm.suggestion_id || null,
      save_as_experience: saveForm.save_as_experience,
      experience_title: saveForm.experience_title || null,
      experience_category: saveForm.experience_category || null,
    })
    const data = response.data || {}
    saveDialogVisible.value = false
    selectedAfterId.value = data.version?.id || selectedAfterId.value
    ElMessage.success(data.experience?.status === 'created' ? '版本已保存，经验卡片已生成' : '版本已保存')
    Object.assign(saveForm, { version_type: 'manual', suggestion_id: null, note: '', save_as_experience: false, experience_title: '', experience_category: '' })
    await loadVersions()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '版本保存失败')
  } finally {
    saving.value = false
  }
}

const openDetail = async (version) => {
  detailVersion.value = version
  detailVisible.value = true
  try {
    const response = await getContentVersion(route.params.id, version.id)
    detailVersion.value = response.data || version
  } catch {
    // 列表已经有基础信息时仍允许用户查看。
  }
}

const setBefore = (version) => {
  selectedBeforeId.value = version.id
  if (selectedAfterId.value === version.id) selectedAfterId.value = versions.value.find((item) => item.id !== version.id)?.id || null
}

const setAfter = (version) => {
  selectedAfterId.value = version.id
  if (selectedBeforeId.value === version.id) selectedBeforeId.value = versions.value.find((item) => item.id !== version.id)?.id || null
}

const stopPolling = () => {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = null
}

const pollSemanticSummary = () => {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    if (document.hidden || !diffData.value) return
    try {
      const response = await diffContentVersions(route.params.id, diffData.value.before_version_id, diffData.value.after_version_id)
      diffData.value = response.data || diffData.value
      if (!['queued', 'running'].includes(semanticStatus.value)) stopPolling()
    } catch {
      // 临时网络错误不终止后台任务，下一轮继续查询。
    }
  }, 2500)
}

const openDiff = async () => {
  if (!canCompare.value) return
  diffLoading.value = true
  try {
    const response = await diffContentVersions(route.params.id, selectedBeforeId.value, selectedAfterId.value)
    diffData.value = response.data || null
    diffVisible.value = true
    if (['queued', 'running'].includes(semanticStatus.value)) pollSemanticSummary()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '版本 diff 加载失败')
  } finally {
    diffLoading.value = false
  }
}

const triggerSummary = async (retry) => {
  if (!diffData.value) return
  try {
    const response = await summarizeContentVersions(
      route.params.id,
      diffData.value.before_version_id,
      diffData.value.after_version_id,
      retry,
    )
    const task = response.data?.task
    diffData.value.semantic_summary = task || diffData.value.semantic_summary
    ElMessage.success(task?.status === 'failed' ? '语义摘要提交失败，可稍后重试' : '语义摘要任务已提交')
    if (task?.status === 'queued' || task?.status === 'running') pollSemanticSummary()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '语义摘要任务提交失败')
  }
}

onMounted(async () => {
  const before = Number(route.query.before)
  const after = Number(route.query.after)
  if (Number.isInteger(before) && before > 0) selectedBeforeId.value = before
  if (Number.isInteger(after) && after > 0) selectedAfterId.value = after
  await loadVersions()
  if (!creationTitle.value) {
    try {
      const response = await getCreationById(route.params.id)
      creationTitle.value = response.data?.title || ''
    } catch {
      // 版本列表已经加载时，标题缺失不影响版本查看。
    }
  }
})
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.versions-page { max-width: 1120px; margin: 0 auto; padding-bottom: 56px; color: var(--ink); }
.versions-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
.back-button { padding-left: 0; color: var(--ink-3); }
.eyebrow { display: block; margin-top: 18px; color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .13em; }
.versions-hero h1 { margin: 8px 0 8px; font: 500 32px/1.3 var(--serif, serif); }
.versions-hero p, .compare-card p { margin: 0; color: var(--ink-3); font-size: 13px; line-height: 1.7; }
.toolbar-card, .compare-card { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 18px 22px; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); box-shadow: 0 8px 24px rgba(72,57,43,.05); }
.toolbar-card { margin-bottom: 20px; }
.toolbar-label { font-weight: 700; }
.toolbar-meta { margin-left: 10px; color: var(--ink-3); font-size: 12px; }
.toolbar-actions, .compare-controls, .version-actions, .version-kicker, .version-meta, .diff-header, .diff-legend, .semantic-head, .semantic-actions { display: flex; align-items: center; gap: 10px; }
.timeline-card { padding: 28px 30px 16px; border: 1px solid #eadfcd; border-radius: var(--r-lg); background: #fffdf9; }
.version-item { padding: 17px 18px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #fff; transition: border-color .18s ease, box-shadow .18s ease; }
.version-item.is-selected { border-color: var(--clay); box-shadow: 0 8px 20px rgba(181, 111, 67, .1); }
.version-item-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.version-kicker { flex-wrap: wrap; }
.version-number { color: var(--clay-deep); font-weight: 800; }
.version-item h2 { margin: 8px 0 0; font-size: 17px; font-weight: 600; }
.version-meta { flex-wrap: wrap; margin-top: 13px; color: var(--ink-3); font-size: 12px; }
.version-meta span + span::before { margin-right: 10px; color: var(--line-strong); content: '·'; }
.summary-state { font-size: 11px; }
.summary-succeeded { color: var(--leaf-deep); }.summary-failed { color: var(--crimson); }.summary-running, .summary-queued { color: var(--clay-deep); }
.compare-card { align-items: flex-end; margin-top: 22px; }
.compare-card h2 { margin: 6px 0 5px; font-size: 20px; }
.compare-controls { flex-wrap: wrap; justify-content: flex-end; }
.compare-controls .el-select { width: 190px; }.arrow { color: var(--clay-deep); font-weight: 800; }
.loading-state { display: flex; align-items: center; justify-content: center; min-height: 220px; gap: 10px; color: var(--ink-3); }
.form-help { display: block; margin-top: 5px; color: var(--ink-4); font-size: 12px; }
.version-detail .detail-summary { display: flex; justify-content: space-between; gap: 12px; color: var(--ink-3); font-size: 12px; }.version-detail .detail-summary strong { color: var(--ink); font-size: 15px; }
.detail-note { padding: 10px 12px; border-radius: var(--r-sm); background: var(--bone); color: var(--ink-3); font-size: 13px; }
.version-text { max-height: 58vh; overflow: auto; margin: 14px 0 0; padding: 18px; white-space: pre-wrap; word-break: break-word; border-radius: var(--r-md); background: #faf6ef; color: var(--ink); font: 14px/1.85 var(--sans, sans-serif); }
.diff-dialog { min-width: 0; }.diff-header { justify-content: space-between; padding-bottom: 14px; border-bottom: 1px solid var(--line); }.diff-header strong, .diff-header span { display: block; }.diff-header span { margin-top: 4px; color: var(--ink-3); font-size: 12px; }.diff-counts { display: flex; gap: 12px; font-weight: 800; }.added-count, .legend-added { color: #277b48; }.removed-count, .legend-removed { color: #b34d4d; }.legend-unchanged { color: var(--ink-4); }.diff-legend { flex-wrap: wrap; padding: 12px 0; color: var(--ink-3); font-size: 12px; }.diff-ready { margin-left: auto; color: var(--leaf-deep); }.diff-lines { max-height: 42vh; overflow: auto; border: 1px solid var(--line); border-radius: var(--r-md); background: #faf8f3; }.diff-line { display: grid; grid-template-columns: 28px minmax(0, 1fr); padding: 3px 12px; white-space: pre-wrap; word-break: break-word; font: 13px/1.65 ui-monospace, SFMono-Regular, Menlo, monospace; }.diff-line-added { background: #eaf6ed; color: #205e37; }.diff-line-removed { background: #fbeeee; color: #984343; text-decoration: line-through; }.diff-line-unchanged { color: #80786e; }.line-mark { color: var(--ink-4); text-align: center; }.semantic-panel { margin-top: 22px; padding: 18px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #fffdf9; }.semantic-head { justify-content: space-between; align-items: flex-start; }.semantic-head h3 { margin: 5px 0 0; font-size: 18px; }.semantic-running, .semantic-failed { margin-top: 14px; padding: 12px; border-radius: var(--r-sm); background: var(--bone); color: var(--ink-3); font-size: 13px; }.semantic-failed { background: #fbefef; color: var(--crimson); }.semantic-failed span { display: block; margin-top: 5px; color: var(--ink-3); }.semantic-result { margin-top: 14px; }.semantic-result > p { margin: 0 0 12px; line-height: 1.7; }.semantic-change { display: grid; gap: 4px; margin-top: 9px; padding: 10px 12px; border-left: 3px solid var(--clay); background: #faf6ef; }.semantic-change strong { color: var(--clay-deep); font-size: 12px; }.semantic-change span { line-height: 1.6; }.semantic-change small { color: var(--ink-3); }.suggestion-match { margin-top: 14px !important; color: var(--clay-deep); }
@media (max-width: 760px) { .versions-hero, .toolbar-card, .compare-card { align-items: stretch; flex-direction: column; }.toolbar-actions, .compare-controls { justify-content: stretch; }.compare-controls .el-select { width: 100%; }.compare-controls .el-button { width: 100%; }.diff-ready { margin-left: 0; }.version-item-head { flex-direction: column; }.version-actions { flex-wrap: wrap; } }
</style>
