<template>
  <div class="meeting-detail-page">
    <div v-if="loading" class="loading-state"><el-icon class="is-loading" :size="26"><Loading /></el-icon><span>加载会议详情…</span></div>
    <template v-else-if="meeting">
      <header class="detail-hero">
        <div class="hero-copy">
          <el-button text class="back-button" @click="router.push('/meetings')">← 返回会议方法论</el-button>
          <h1>{{ meeting.title }}</h1>
          <div class="detail-meta">
            <span>{{ formatDate(meeting.meeting_at) }}</span>
            <el-tag size="small" :type="meetingStatusType(meeting.status)">{{ meetingStatusLabel(meeting.status) }}</el-tag>
            <el-tag v-if="synthesis?.is_manually_edited" size="small" type="success" effect="plain">已人工修订</el-tag>
          </div>
        </div>
        <div class="detail-actions">
          <el-button v-if="meeting.status === 'failed' || meeting.status === 'ready'" type="warning" :loading="retrying" @click="retryExtraction">
            {{ meeting.status === 'failed' ? '重试整理' : '重新整理' }}
          </el-button>
          <el-button v-if="meeting.status === 'extracting'" disabled>整理中…</el-button>
        </div>
      </header>

      <div v-if="meeting.status === 'extracting'" class="state-banner state-banner-running">
        <el-icon class="is-loading"><Loading /></el-icon>
        <div><strong>正在整理会议方法论</strong><span>任务在后台运行，页面会自动刷新；不会因为刷新页面而重复提交。</span></div>
      </div>
      <div v-else-if="meeting.status === 'failed'" class="state-banner state-banner-failed">
        <el-icon><WarningFilled /></el-icon>
        <div><strong>本次方法论整理失败</strong><span>原文仍然保留，可以重试；如果上一轮已有人工修订，重试不会覆盖人工内容。</span></div>
      </div>

      <section class="summary-panel">
        <div class="summary-panel-head">
          <span class="section-eyebrow">本次会议真正留下的是</span>
          <el-button v-if="synthesis" type="primary" plain @click="openSynthesisEditor">编辑沉淀</el-button>
        </div>
        <p v-if="synthesis?.summary" class="summary-text">{{ synthesis.summary }}</p>
        <el-empty v-else-if="meeting.status === 'ready'" :image-size="52" description="这次还没有生成沉淀，请重新整理" />
        <p v-else class="muted">整理完成后，这里会显示会议最重要的结论。</p>
        <div v-if="synthesis" class="summary-meta">
          <span>{{ synthesis.checklist?.length || 0 }} 项动笔前对齐清单</span>
          <span>{{ synthesis.methodology?.length || 0 }} 条方法论依据</span>
        </div>
      </section>

      <template v-if="synthesis">
        <section class="content-panel primary-section checklist-section">
          <div class="section-heading">
            <div>
              <span class="section-eyebrow">START HERE</span>
              <h2>动笔前对齐清单</h2>
              <p>每篇文章开始前，先和团队把这几件事对齐。</p>
            </div>
            <span class="section-count">{{ synthesis.checklist?.length || 0 }} 项</span>
          </div>
          <div v-if="synthesis.checklist?.length" class="checklist-list">
            <article v-for="(item, index) in synthesis.checklist" :key="`${item.item}-${index}`" class="checklist-item">
              <div class="checklist-item-head">
                <span class="check-mark">{{ String(index + 1).padStart(2, '0') }}</span>
                <div><h3>{{ item.item }}</h3><span class="checklist-label">动笔前对齐</span></div>
              </div>
              <div class="checklist-fields">
                <div><strong>具体检查</strong><p>{{ item.description || '围绕这一项确认文章的切入和表达是否成立。' }}</p></div>
                <div><strong>使用时机</strong><p>{{ item.when_to_use || '每篇文章动笔前' }}</p></div>
              </div>
            </article>
          </div>
          <el-empty v-else :image-size="48" description="暂无对齐清单" />
        </section>

        <section class="content-panel secondary-section methodology-section">
          <div class="section-heading section-heading-compact">
            <div>
              <span class="section-eyebrow">WHY IT WORKS</span>
              <h2>方法论详解</h2>
              <p>把清单背后的判断、原因、场景和会议依据完整保留下来。</p>
            </div>
          </div>
          <div v-if="synthesis.methodology?.length" class="methodology-list">
            <article v-for="(item, index) in synthesis.methodology" :key="`${item.title}-${index}`" class="methodology-item">
              <div class="method-number">{{ String(index + 1).padStart(2, '0') }}</div>
              <div class="method-body">
                <span class="method-label">判断规则</span>
                <h3>{{ item.title }}</h3>
                <p class="rule-text">{{ item.rule }}</p>
                <div class="method-fields">
                  <div v-if="item.rationale"><strong>为什么</strong><p>{{ item.rationale }}</p></div>
                  <div v-if="item.example"><strong>例子 / 场景</strong><p>{{ item.example }}</p></div>
                  <div v-if="item.evidence" class="evidence-field"><strong>会议依据</strong><p>{{ item.evidence }}</p></div>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-else :image-size="48" description="暂无方法论依据" />
        </section>
      </template>
      <el-empty v-else-if="meeting.status === 'ready'" :image-size="64" description="还没有生成方法论沉淀" />
      <div v-else class="waiting-copy">方法论整理完成后会显示在这里。</div>

      <section class="source-section">
        <details>
          <summary class="source-summary">
            <span><strong>原始会议纪要</strong><small>需要核对时再展开</small></span>
            <span class="source-count">{{ (meeting.raw_text || '').length }} 字</span>
          </summary>
          <div class="raw-text">{{ meeting.raw_text }}</div>
        </details>
      </section>
    </template>
    <el-empty v-else description="会议不存在或无权访问" />

    <el-dialog v-model="editVisible" title="编辑会议方法论沉淀" width="900px" align-center destroy-on-close>
      <el-tabs v-model="editorTab" class="editor-tabs">
        <el-tab-pane label="摘要" name="summary">
          <el-input v-model="editorForm.summary" type="textarea" :autosize="{ minRows: 5, maxRows: 12 }" maxlength="4000" show-word-limit placeholder="用 1-3 句话说明这次会议最重要的结论" />
        </el-tab-pane>
        <el-tab-pane label="方法论" name="methodology">
          <div class="editor-list">
            <div v-for="(item, index) in editorForm.methodology" :key="index" class="editor-item">
              <div class="editor-item-head"><strong>方法 {{ index + 1 }}</strong><el-button text type="danger" @click="removeEditorItem('methodology', index)">删除</el-button></div>
              <el-input v-model="item.title" placeholder="方法论名称" class="editor-input" />
              <el-input v-model="item.rule" type="textarea" :rows="2" placeholder="可复用的判断规则" class="editor-input" />
              <div class="editor-two-col"><el-input v-model="item.rationale" type="textarea" :rows="2" placeholder="为什么这样做" /><el-input v-model="item.example" type="textarea" :rows="2" placeholder="会议中的例子或适用场景" /></div>
              <el-input v-model="item.evidence" type="textarea" :rows="2" placeholder="会议依据（可选）" />
            </div>
          </div>
          <el-button plain @click="addEditorItem('methodology')">+ 添加方法论</el-button>
        </el-tab-pane>
        <el-tab-pane label="对齐清单" name="checklist">
          <div class="editor-list">
            <div v-for="(item, index) in editorForm.checklist" :key="index" class="editor-item">
              <div class="editor-item-head"><strong>清单 {{ index + 1 }}</strong><el-button text type="danger" @click="removeEditorItem('checklist', index)">删除</el-button></div>
              <el-input v-model="item.item" placeholder="动笔前要对齐的事项" class="editor-input" />
              <el-input v-model="item.description" type="textarea" :rows="2" placeholder="具体要检查什么" class="editor-input" />
              <el-input v-model="item.when_to_use" placeholder="什么时候使用（可选）" />
            </div>
          </div>
          <el-button plain @click="addEditorItem('checklist')">+ 添加清单项</el-button>
        </el-tab-pane>
      </el-tabs>
      <template #footer><el-button @click="editVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveSynthesis">保存人工修订</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import { extractMeeting, getMeeting, updateMeetingSynthesis } from '@/api/meetings'
import { meetingStatusLabel, meetingStatusType } from './meetingUi'

const route = useRoute()
const router = useRouter()
const meeting = ref(null)
const loading = ref(true)
const retrying = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const editorTab = ref('summary')
let pollTimer = null

const synthesis = computed(() => meeting.value?.synthesis || null)
const editorForm = reactive({
  summary: '',
  methodology: [],
  checklist: [],
})

const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16) : '—'
const trim = (value) => String(value || '').trim()
const valueOrNull = (value) => trim(value) || null

const loadMeeting = async () => {
  try {
    const response = await getMeeting(route.params.id)
    meeting.value = response.data || null
  } catch {
    meeting.value = null
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (meeting.value?.status === 'extracting') {
    pollTimer = window.setInterval(async () => {
      if (!document.hidden) {
        await loadMeeting()
        if (meeting.value?.status !== 'extracting') stopPolling()
      }
    }, 3000)
  }
}

const stopPolling = () => {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = null
}

const retryExtraction = async () => {
  retrying.value = true
  try {
    await extractMeeting(route.params.id)
    ElMessage.success('方法论整理任务已提交')
    await loadMeeting()
    startPolling()
  } finally {
    retrying.value = false
  }
}

const copyRows = (rows, fallback) => (Array.isArray(rows) && rows.length ? rows : [fallback()]).map((row) => ({ ...row }))

const openSynthesisEditor = () => {
  const current = synthesis.value || {}
  editorForm.summary = current.summary || ''
  editorForm.methodology = copyRows(current.methodology, () => ({ title: '', rule: '', rationale: '', example: '', evidence: '' }))
  editorForm.checklist = copyRows(current.checklist, () => ({ item: '', description: '', when_to_use: '' }))
  editorTab.value = 'summary'
  editVisible.value = true
}

const templates = {
  methodology: () => ({ title: '', rule: '', rationale: '', example: '', evidence: '' }),
  checklist: () => ({ item: '', description: '', when_to_use: '' }),
}

const addEditorItem = (section) => editorForm[section].push(templates[section]())
const removeEditorItem = (section, index) => editorForm[section].splice(index, 1)
const clean = (value) => Array.isArray(value) ? value.filter(Boolean) : []

const saveSynthesis = async () => {
  saving.value = true
  try {
    const payload = {
      summary: valueOrNull(editorForm.summary),
      methodology: clean(editorForm.methodology.map((item) => ({
        title: trim(item.title), rule: trim(item.rule), rationale: valueOrNull(item.rationale), example: valueOrNull(item.example), evidence: valueOrNull(item.evidence),
      })).filter((item) => item.rule)),
      checklist: clean(editorForm.checklist.map((item) => ({ item: trim(item.item), description: valueOrNull(item.description), when_to_use: valueOrNull(item.when_to_use) })).filter((item) => item.item)),
    }
    await updateMeetingSynthesis(route.params.id, payload)
    ElMessage.success('方法论沉淀已保存')
    editVisible.value = false
    await loadMeeting()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadMeeting()
  startPolling()
})

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.meeting-detail-page { max-width: 1080px; margin: 0 auto; padding-bottom: 48px; color: var(--ink); }
.loading-state { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 240px; color: var(--ink-3); }
.detail-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 32px; }
.hero-copy { min-width: 0; }
.back-button { padding-left: 0; color: var(--ink-3); }
.detail-hero h1 { max-width: 900px; margin: 20px 0 12px; font: 500 32px/1.3 var(--serif, serif); }
.detail-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; color: var(--ink-3); font-size: 13px; }
.detail-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 10px; }
.state-banner { display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px; border-radius: var(--r-md); margin-bottom: 16px; }
.state-banner strong, .state-banner span { display: block; }
.state-banner strong { margin-bottom: 3px; font-size: 13px; }
.state-banner span { color: var(--ink-3); font-size: 12px; }
.state-banner-running { background: var(--clay-tint); color: var(--clay-deep); }
.state-banner-failed { background: #f8eceb; color: var(--crimson); }
.summary-panel { margin-bottom: 42px; padding: 26px 30px 28px; border-left: 4px solid var(--clay); border-radius: 0 var(--r-md) var(--r-md) 0; background: var(--paper); box-shadow: 0 8px 24px rgba(72, 57, 43, .05); }
.summary-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 13px; }
.section-eyebrow { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .12em; }
.summary-text { max-width: 860px; margin: 0; color: var(--ink); font-size: 20px; line-height: 1.8; }
.summary-meta { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 18px; color: var(--ink-3); font-size: 12px; }
.summary-meta span::before { margin-right: 6px; color: var(--clay); content: '·'; }
.muted { color: var(--ink-3); font-size: 12px; }
.content-panel { padding: 28px 30px 30px; border: 1px solid #e8ddca; border-radius: var(--r-lg); background: #fffdf9; box-shadow: 0 8px 24px rgba(72, 57, 43, .05); }
.primary-section { margin-bottom: 26px; }
.secondary-section { margin-bottom: 30px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.section-heading h2 { margin: 6px 0 5px; font-size: 24px; font-weight: 600; }
.section-heading p { margin: 0; color: var(--ink-3); font-size: 13px; line-height: 1.6; }
.section-heading-compact h2 { font-size: 20px; }
.section-count { color: var(--clay-deep); font-size: 13px; font-weight: 700; white-space: nowrap; }
.checklist-list { display: flex; flex-direction: column; gap: 12px; }
.checklist-item { padding: 18px 20px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #f8f3eb; }
.checklist-item-head { display: flex; align-items: flex-start; gap: 14px; }
.check-mark { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 30px; flex: 0 0 36px; border-radius: var(--r-sm); background: var(--clay-deep); color: #fffaf3; font-size: 12px; font-weight: 700; }
.checklist-item-head h3 { margin: 0; color: var(--ink); font-size: 17px; font-weight: 600; line-height: 1.5; }
.checklist-label { display: inline-block; margin-top: 4px; color: var(--clay-deep); font-size: 11px; }
.checklist-fields { display: grid; grid-template-columns: 1.5fr 1fr; gap: 10px; margin: 16px 0 0 50px; }
.checklist-fields > div { padding: 11px 13px; border-radius: var(--r-sm); background: #fffdf9; }
.checklist-fields strong, .method-fields strong { display: block; margin-bottom: 4px; color: var(--clay-deep); font-size: 11px; }
.checklist-fields p, .method-fields p { margin: 0; color: var(--ink-2); font-size: 13px; line-height: 1.7; }
.methodology-list { display: flex; flex-direction: column; gap: 14px; }
.methodology-item { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 18px; padding: 22px; border: 1px solid #e8ddca; border-radius: var(--r-md); background: #f8f3eb; }
.method-number { color: var(--clay-deep); font-size: 14px; font-weight: 700; line-height: 1.7; }
.method-body h3 { margin: 4px 0 8px; color: var(--ink); font-size: 18px; line-height: 1.5; }
.method-label { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .05em; }
.rule-text { margin: 0; color: var(--ink); font-size: 15px; line-height: 1.8; }
.method-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }
.method-fields > div { padding: 11px 13px; border-radius: var(--r-sm); background: #fffdf9; }
.method-fields .evidence-field { grid-column: 1 / -1; background: #f5eee4; }
.waiting-copy { padding: 80px 20px; color: var(--ink-3); text-align: center; font-size: 13px; }
.source-section { margin-top: 10px; border: 1px solid #e8ddca; border-radius: var(--r-lg); background: #fffdf9; }
.source-section details { padding: 0 20px 20px; }
.source-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 4px; cursor: pointer; list-style: none; }
.source-summary::-webkit-details-marker { display: none; }
.source-summary strong, .source-summary small { display: block; }
.source-summary strong { color: var(--ink-2); font-size: 15px; }
.source-summary small { margin-top: 4px; color: var(--ink-3); font-size: 12px; }
.source-count { color: var(--ink-3); font-size: 12px; white-space: nowrap; }
.raw-text { max-height: 640px; overflow: auto; padding: 20px; border-radius: var(--r-md); background: var(--ivory); white-space: pre-wrap; color: var(--ink-2); font-size: 13px; line-height: 1.85; }
.editor-tabs { min-height: 430px; }
.editor-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 12px; max-height: 490px; overflow: auto; padding-right: 4px; }
.editor-item { padding: 13px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--ivory); }
.compact-editor-item { padding-bottom: 14px; }
.editor-item-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 9px; color: var(--ink-2); font-size: 13px; }
.editor-input { margin-bottom: 9px; }
.editor-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-bottom: 9px; }
@media (max-width: 620px) {
  .detail-hero { align-items: flex-start; flex-direction: column; }
  .detail-actions { width: 100%; }
  .detail-actions .el-button { flex: 1; }
  .summary-panel { padding: 22px 20px 24px; }
  .summary-text { font-size: 17px; }
  .content-panel { padding: 22px 18px 24px; }
  .section-heading h2 { font-size: 21px; }
  .checklist-fields, .method-fields { grid-template-columns: 1fr; margin-left: 0; }
  .method-fields .evidence-field { grid-column: auto; }
  .methodology-item { grid-template-columns: 32px minmax(0, 1fr); gap: 10px; padding: 17px 14px; }
  .editor-two-col { grid-template-columns: 1fr; }
}
</style>
