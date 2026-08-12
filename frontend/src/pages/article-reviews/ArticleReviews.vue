<template>
  <div class="reviews-page">
    <header class="reviews-hero">
      <div>
        <span class="eyebrow">TEAM REVIEW WORKSPACE · PHASE 1C</span>
        <h1>文章复盘</h1>
        <p>把改前稿和改后稿放在一起，看清哪里改了、为什么改，再把确认过的经验沉淀下来。</p>
      </div>
      <el-button type="primary" size="large" @click="createVisible = true">
        <el-icon><Plus /></el-icon> 新建文章复盘
      </el-button>
    </header>

    <div class="workspace-grid">
      <aside class="review-list-panel">
        <div class="list-panel-head">
          <div>
            <span class="eyebrow">REVIEW LOG</span>
            <h2>复盘记录</h2>
          </div>
          <el-button text :loading="listLoading" @click="loadReviews">刷新</el-button>
        </div>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索主题或文件名"
          @keyup.enter="loadReviews"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="status-filter">
          <button
            v-for="item in statusFilters"
            :key="item.value"
            type="button"
            :class="{ active: filters.status === item.value }"
            @click="filters.status = item.value; loadReviews()"
          >
            {{ item.label }}
          </button>
        </div>
        <div v-loading="listLoading" class="review-list">
          <button
            v-for="item in reviews"
            :key="item.id"
            type="button"
            class="review-list-item"
            :class="{ selected: selectedReview?.id === item.id }"
            @click="selectReview(item.id)"
          >
            <div class="review-list-item-top">
              <strong>{{ item.title }}</strong>
              <el-tag size="small" :type="statusType(item.status)">{{ statusLabel(item.status) }}</el-tag>
            </div>
            <span class="review-list-files">{{ item.before?.filename }} → {{ item.after?.filename }}</span>
            <div class="review-list-meta">
              <span>{{ item.stats?.major_group_count || 0 }} 处重点修改</span>
              <span>{{ formatDate(item.created_at) }}</span>
            </div>
          </button>
          <el-empty v-if="!listLoading && !reviews.length" :image-size="58" description="还没有文章复盘" />
        </div>
      </aside>

      <main v-if="selectedReview" class="review-detail-panel">
        <header class="detail-head">
          <div>
            <button type="button" class="back-link" @click="clearSelectedReview">← 返回复盘记录</button>
            <h2>{{ selectedReview.title }}</h2>
            <div class="detail-meta">
              <span>{{ selectedReview.before?.filename }} → {{ selectedReview.after?.filename }}</span>
              <span>创建于 {{ formatDate(selectedReview.created_at) }}</span>
              <el-tag size="small" :type="statusType(selectedReview.status)">{{ statusLabel(selectedReview.status) }}</el-tag>
            </div>
          </div>
          <div class="detail-actions">
            <el-button v-if="retryableStage" :loading="analyzing" @click="retryStage">
              {{ retryableStageLabel }}
            </el-button>
            <el-button v-if="selectedReview.ai_analysis" type="primary" plain @click="openAnalysisEditor">人工修订总结</el-button>
          </div>
        </header>

        <div v-if="waitingForSemanticConfirmation" class="state-banner waiting">
          <el-icon><WarningFilled /></el-icon>
          <div><strong>语义分段已生成，等待团队确认</strong><span>可以先编辑、合并或拆分语义块；确认后才会计算重大修改并启动 AI 复盘。</span></div>
          <el-button type="primary" size="small" :loading="confirmingBlocks" @click="confirmSemanticBlocks">确认分段并继续</el-button>
        </div>
        <div v-else-if="selectedReview.status === 'processing'" class="state-banner running">
          <el-icon class="is-loading"><Loading /></el-icon>
          <div><strong>{{ progressMessage }}</strong><span>当前阶段：{{ stageLabel(progressState?.stage || currentStage) }} · 文件正在后台解析和比对，页面会实时更新，不需要一直等待上传请求。</span></div>
        </div>
        <div v-else-if="selectedReview.status === 'analyzing'" class="state-banner running">
          <el-icon class="is-loading"><Loading /></el-icon>
          <div><strong>{{ progressMessage }}</strong><span>当前阶段：{{ stageLabel(progressState?.stage || currentStage) }} · 文本改动已经识别完成，AI 分析在后台运行，页面会实时更新。</span></div>
        </div>
        <div v-else-if="selectedReview.status === 'failed'" class="state-banner failed">
          <el-icon><WarningFilled /></el-icon>
          <div><strong>AI 分析没有完成</strong><span>{{ selectedReview.analysis_error || '原文和重点改动仍然保留，可以修复后重试。' }}</span></div>
        </div>

        <section class="stats-grid">
          <div class="stat-card stat-highlight"><span>重点修改</span><strong>{{ selectedReview.stats?.major_group_count || 0 }}</strong><small>建议优先复盘</small></div>
          <div class="stat-card"><span>全部改动块</span><strong>{{ selectedReview.stats?.total_groups || 0 }}</strong><small>按段落 / 行聚合</small></div>
          <div class="stat-card"><span>改前字数</span><strong>{{ selectedReview.before?.char_count || 0 }}</strong><small>{{ selectedReview.before?.truncated ? '已截断' : '完整解析' }}</small></div>
          <div class="stat-card"><span>改后字数</span><strong>{{ selectedReview.after?.char_count || 0 }}</strong><small>{{ selectedReview.after?.truncated ? '已截断' : '完整解析' }}</small></div>
        </section>

        <section v-if="workflowStages.length" class="content-section stage-section">
          <div class="section-heading">
            <div><span class="eyebrow">WORKFLOW STATUS</span><h3>复盘阶段</h3><p>每个阶段都保存到本次运行记录，刷新或断线后可以从当前阶段继续。</p></div>
            <span class="section-count">{{ currentStageLabel }}</span>
          </div>
          <div class="stage-list">
            <div v-for="stage in workflowStages" :key="stage.stage_key" class="stage-item" :class="`stage-${stage.status}`">
              <span class="stage-dot">{{ stage.status === 'succeeded' ? '✓' : stage.stage_order }}</span>
              <div><strong>{{ stage.label }}</strong><small>{{ stageMessage(stage) }}</small></div>
              <el-tag size="small" :type="stageType(stage.status)">{{ stageStatusLabel(stage.status) }}</el-tag>
            </div>
          </div>
        </section>

        <section v-if="semanticBlocks.length" class="content-section semantic-section">
          <div class="section-heading">
            <div><span class="eyebrow">00 · CONFIRM THE MEANING</span><h3>语义分段确认</h3><p>短句换行会尽量合并为同一语义块；你可以在对齐前人工修订边界。</p></div>
            <div class="section-actions">
              <el-button size="small" plain @click="semanticEditMode = !semanticEditMode">{{ semanticEditMode ? '完成编辑' : '编辑分段' }}</el-button>
              <el-button size="small" type="primary" :loading="confirmingBlocks" @click="confirmSemanticBlocks">确认并重新对齐</el-button>
            </div>
          </div>
          <div class="semantic-columns">
            <div v-for="side in ['before', 'after']" :key="side" class="semantic-column">
              <div class="semantic-column-head"><strong>{{ side === 'before' ? '改前语义块' : '改后语义块' }}</strong><span>{{ semanticDraft[side].length }} 块</span></div>
              <div v-for="(block, index) in semanticDraft[side]" :key="block.stable_id || `${side}-${index}`" class="semantic-block">
                <div class="semantic-block-head"><span>{{ String(index + 1).padStart(2, '0') }}</span><small>{{ block.source_line_start ? `原文第 ${block.source_line_start}-${block.source_line_end || block.source_line_start} 行` : '人工语义块' }}</small></div>
                <el-input v-if="semanticEditMode" v-model="block.text" type="textarea" :autosize="{ minRows: 2, maxRows: 8 }" />
                <p v-else>{{ block.text }}</p>
                <div v-if="semanticEditMode" class="semantic-block-actions">
                  <el-button text size="small" :disabled="index === 0" @click="mergeSemanticBlock(side, index)">合并上一块</el-button>
                  <el-button text size="small" @click="splitSemanticBlock(side, index)">拆分</el-button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="content-section change-section">
          <div class="section-heading">
            <div><span class="eyebrow">01 · SHOW THE CHANGE</span><h3>先看真正改大的地方</h3><p>高影响修改会置顶，人工评论直接挂在对应改动块下。</p></div>
            <span class="section-count">{{ selectedReview.change_groups?.length || 0 }} 个改动块</span>
          </div>
          <div v-if="selectedReview.status === 'processing'" class="processing-empty">
            <el-empty :image-size="58" description="正在解析文件并识别改动，请稍候" />
          </div>
          <div v-else-if="orderedGroups.length" class="change-list">
            <article v-for="group in orderedGroups" :key="group.id" class="change-card" :class="`impact-${group.impact}`">
              <div class="change-card-head">
                <div class="change-label"><span class="change-index">{{ group.id.replace('change-', '') }}</span><el-tag size="small" :type="impactType(group.impact)">{{ impactLabel(group.impact) }}</el-tag><span>{{ changeKindLabel(group.kind || group.change_type) }}</span><el-tag v-if="group.human_label" size="small" effect="plain">{{ humanLabel(group.human_label) }}</el-tag></div>
                <span class="change-ratio">变化度 {{ Math.round((group.change_ratio || 0) * 100) }}%</span>
              </div>
              <p class="change-reason"><strong>判定依据：</strong>{{ group.significance_reason || '算法识别到语义内容变化' }}</p>
              <div class="diff-columns">
                <div class="diff-block before"><span>改前</span><p>{{ group.before || '（删除）' }}</p></div>
                <div class="diff-arrow">→</div>
                <div class="diff-block after"><span>改后</span><p>{{ group.after || '（新增）' }}</p></div>
              </div>
              <div class="change-review-actions">
                <span>这处判断：</span>
                <el-button-group>
                  <el-button size="small" :type="group.human_label === 'important' ? 'primary' : ''" @click="reviewChange(group, 'important')">重要</el-button>
                  <el-button size="small" :type="group.human_label === 'unimportant' ? 'info' : ''" @click="reviewChange(group, 'unimportant')">不重要</el-button>
                  <el-button size="small" :type="group.human_label === 'false_positive' ? 'warning' : ''" @click="reviewChange(group, 'false_positive')">误判</el-button>
                  <el-button size="small" :type="group.human_label === 'needs_review' ? 'danger' : ''" @click="reviewChange(group, 'needs_review')">待确认</el-button>
                </el-button-group>
              </div>
              <div class="comment-area">
                <div v-if="commentsFor(group.id).length" class="comment-list">
                  <div v-for="comment in commentsFor(group.id)" :key="comment.id" class="comment-item">
                    <div><strong>{{ comment.author?.full_name || comment.author?.username || '团队成员' }}</strong><small>{{ formatDate(comment.created_at) }}</small></div>
                    <p>{{ comment.body }}</p>
                  </div>
                </div>
                <div class="comment-compose">
                  <el-input v-model="commentDrafts[group.id]" maxlength="5000" placeholder="写下你对这个修改的判断、疑问或可复用经验" @keyup.ctrl.enter="addComment(group)">
                    <template #append><el-button :loading="commenting[group.id]" @click="addComment(group)">评论</el-button></template>
                  </el-input>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-else :image-size="58" description="改前稿和改后稿没有检测到文本变化" />
        </section>

        <section v-if="reorderEvents.length" class="content-section reorder-section">
          <div class="section-heading"><div><span class="eyebrow">01B · ORDER MATTERS</span><h3>顺序变化</h3><p>内容本身基本保留，但位置变化可能影响读者理解路径或论证节奏。</p></div><span class="section-count">{{ reorderEvents.length }} 处</span></div>
          <div class="reorder-list"><article v-for="event in reorderEvents" :key="event.id" class="reorder-item"><el-tag size="small" effect="plain">重排</el-tag><div><strong>{{ event.summary }}</strong><p>改前第 {{ event.before_block_ids?.join('、') || '—' }} 块 → 改后第 {{ event.after_block_ids?.join('、') || '—' }} 块</p></div></article></div>
        </section>

        <section class="content-section analysis-section">
          <div class="section-heading">
            <div><span class="eyebrow">02 · UNDERSTAND WHY</span><h3>AI 差异分析</h3><p>AI 只对真实改动做解释；不确定的原因会保留为“需要人工确认”。</p></div>
            <el-button v-if="methodologyCandidates.length && hasConfirmedMethodology" type="primary" @click="openPromote()">沉淀为方法论</el-button>
          </div>
          <div v-if="selectedReview.ai_analysis?.summary" class="ai-summary">{{ selectedReview.ai_analysis.summary }}</div>
          <el-empty v-else-if="selectedReview.status === 'reviewing'" :image-size="50" description="AI 没有生成摘要，可以人工修订或直接依据改动沉淀" />
          <div v-if="selectedReview.ai_analysis?.key_changes?.length" class="analysis-change-list">
            <article v-for="item in selectedReview.ai_analysis.key_changes" :key="`${item.group_id}-${item.what_changed}`" class="analysis-change-item">
              <div class="analysis-change-title"><el-tag size="small" effect="plain">{{ item.group_id }}</el-tag><strong>{{ item.what_changed }}</strong><span>置信度 {{ Math.round((item.confidence || 0) * 100) }}%</span></div>
              <div class="analysis-fields"><div><span>可能原因</span><p>{{ item.likely_reason || '需要人工确认' }}</p></div><div><span>可能效果</span><p>{{ item.effect || '待团队观察' }}</p></div></div>
            </article>
          </div>
        </section>

        <section v-if="methodologyCandidates.length" class="content-section methodology-section">
          <div class="section-heading"><div><span class="eyebrow">03 · KEEP THE LESSON</span><h3>候选方法论</h3><p>先由 AI 提炼，再由团队评论和修订，确认后才进入经验库。</p></div></div>
          <div class="methodology-list">
            <article v-for="(item, index) in methodologyCandidates" :key="`${item.title}-${index}`" class="methodology-card">
              <div class="method-number">{{ String(index + 1).padStart(2, '0') }}</div>
              <div class="method-body"><h4>{{ item.title }}</h4><p class="rule">{{ item.rule }}</p><div class="method-fields"><div v-if="item.rationale"><span>为什么</span><p>{{ item.rationale }}</p></div><div v-if="item.example"><span>本次例子</span><p>{{ item.example }}</p></div></div><small v-if="item.evidence_group_ids?.length">证据：{{ item.evidence_group_ids.join('、') }}</small></div>
              <div class="method-actions"><el-tag v-if="item.status" size="small" effect="plain">{{ candidateStatusLabel(item.status) }}</el-tag><el-button v-if="item.status !== 'confirmed' && item.status !== 'promoted'" type="primary" plain size="small" @click="confirmMethodology(item, 'confirmed')">确认</el-button><el-button v-if="item.status !== 'rejected' && item.status !== 'promoted'" text type="danger" size="small" @click="confirmMethodology(item, 'rejected')">驳回</el-button><el-button v-if="!item.status || ['confirmed', 'promoted'].includes(item.status)" type="primary" plain size="small" @click="openPromote(item)">沉淀</el-button></div>
            </article>
          </div>
        </section>

        <section class="source-section">
          <details>
            <summary><span><strong>查看原文全文</strong><small>需要核对上下文时展开</small></span><span>{{ selectedReview.before?.char_count + selectedReview.after?.char_count }} 字</span></summary>
            <div class="source-columns"><div><b>改前稿</b><pre>{{ selectedReview.before_text || '当前接口未返回全文' }}</pre></div><div><b>改后稿</b><pre>{{ selectedReview.after_text || '当前接口未返回全文' }}</pre></div></div>
          </details>
        </section>
      </main>

      <main v-else class="empty-detail-panel">
        <div><span class="empty-mark">↗</span><h2>从一场文章复盘开始</h2><p>上传改前稿和改后稿，系统会先把“大改动”找出来，再交给团队一起判断。</p><el-button type="primary" @click="createVisible = true">上传两份文章</el-button></div>
      </main>
    </div>

    <el-dialog v-model="createVisible" title="新建文章复盘" width="620px" align-center destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="复盘主题（可选）"><el-input v-model="createForm.title" maxlength="200" placeholder="例如：春季活动文章 · 开头重写复盘" /></el-form-item>
        <div class="upload-pair">
          <label class="upload-box"><span>改前文章</span><strong>{{ beforeFile?.name || '选择 PDF / Word / TXT / MD' }}</strong><input type="file" accept=".pdf,.docx,.txt,.md,.markdown" @change="pickFile('before', $event)" /></label>
          <label class="upload-box"><span>改后文章</span><strong>{{ afterFile?.name || '选择 PDF / Word / TXT / MD' }}</strong><input type="file" accept=".pdf,.docx,.txt,.md,.markdown" @change="pickFile('after', $event)" /></label>
        </div>
      </el-form>
      <p class="dialog-tip">支持文字版 PDF、DOCX、TXT、MD，单个文件不超过 20MB；改前和改后两份文件合计不超过 40MB（请求含 multipart 开销预留 45MB）。上传后会先解析并生成语义分段；扫描件或加密文件需要先转成可复制文本。</p>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="creating" @click="submitCreate">创建并分析</el-button></template>
    </el-dialog>

    <el-dialog v-model="analysisEditVisible" title="人工修订 AI 复盘" width="820px" align-center destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="复盘摘要"><el-input v-model="analysisForm.summary" type="textarea" :autosize="{ minRows: 4, maxRows: 9 }" maxlength="4000" show-word-limit /></el-form-item>
        <div class="editor-list"><div v-for="(item, index) in analysisForm.methodology_candidates" :key="index" class="editor-item"><div class="editor-item-head"><strong>方法论 {{ index + 1 }}</strong><el-button text type="danger" @click="analysisForm.methodology_candidates.splice(index, 1)">删除</el-button></div><el-input v-model="item.title" class="editor-input" placeholder="方法论名称" /><el-input v-model="item.rule" class="editor-input" type="textarea" :rows="2" placeholder="可复用的判断规则" /><div class="editor-two-col"><el-input v-model="item.rationale" type="textarea" :rows="2" placeholder="为什么" /><el-input v-model="item.example" type="textarea" :rows="2" placeholder="本次例子" /></div></div></div>
        <el-button plain @click="analysisForm.methodology_candidates.push({ title: '', rule: '', rationale: '', example: '', evidence_group_ids: [] })">+ 添加方法论</el-button>
      </el-form>
      <template #footer><el-button @click="analysisEditVisible = false">取消</el-button><el-button type="primary" :loading="savingAnalysis" @click="saveAnalysis">保存人工修订</el-button></template>
    </el-dialog>

    <el-dialog v-model="promoteVisible" title="沉淀到经验库" width="680px" align-center destroy-on-close>
      <p class="promote-intro">这一步会把当前复盘中的改动证据、AI 总结和人工评论保存成一张可检索的经验卡片。</p>
      <el-form label-position="top">
        <el-form-item label="经验标题"><el-input v-model="promoteForm.title" maxlength="200" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="promoteForm.category" maxlength="50" placeholder="例如：开头、文章结构、表达与呈现" /></el-form-item>
        <el-form-item label="关联重点改动"><el-checkbox-group v-model="promoteForm.groupIds" class="group-checkboxes"><el-checkbox v-for="group in selectedReview?.change_groups || []" :key="group.id" :label="group.id">{{ group.id }} · {{ impactLabel(group.impact) }}</el-checkbox></el-checkbox-group></el-form-item>
        <el-form-item label="人工确认后的经验正文（可选）"><el-input v-model="promoteForm.content" type="textarea" :autosize="{ minRows: 6, maxRows: 14 }" maxlength="50000" placeholder="留空则由系统自动整理 AI 总结、改动证据和评论" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="promoteVisible = false">取消</el-button><el-button type="primary" :loading="promoting" @click="submitPromote">确认沉淀</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Plus, Search, WarningFilled } from '@element-plus/icons-vue'
import { validateArticleReviewFiles, validateUploadFile } from '@/utils/uploadPolicy'
import {
  addArticleReviewComment,
  analyzeArticleReview,
  confirmArticleReviewMethodology,
  createArticleReview,
  getArticleReview,
  listArticleReviews,
  promoteArticleReview,
  retryArticleReviewStage,
  reviewArticleReviewChange,
  streamArticleReview,
  updateArticleReviewSemanticBlocks,
  updateArticleReviewAnalysis,
} from '@/api/articleReviews'

const route = useRoute()
const reviews = ref([])
const selectedReview = ref(null)
const listLoading = ref(false)
const detailLoading = ref(false)
const creating = ref(false)
const analyzing = ref(false)
const confirmingBlocks = ref(false)
const semanticEditMode = ref(false)
const commenting = reactive({})
const createVisible = ref(false)
const analysisEditVisible = ref(false)
const savingAnalysis = ref(false)
const promoteVisible = ref(false)
const promoting = ref(false)
const beforeFile = ref(null)
const afterFile = ref(null)
const pollTimer = ref(null)
const streamAbortController = ref(null)
const progressReconnectTimer = ref(null)
const progressState = ref(null)
const semanticDraft = reactive({ before: [], after: [] })
const filters = reactive({ keyword: '', status: '' })
const createForm = reactive({ title: '' })
const commentDrafts = reactive({})
const analysisForm = reactive({ summary: '', methodology_candidates: [] })
const promoteForm = reactive({ title: '', category: '文章复盘', content: '', groupIds: [] })

const statusFilters = [
  { value: '', label: '全部' },
  { value: 'processing', label: '解析中' },
  { value: 'analyzing', label: '分析中' },
  { value: 'reviewing', label: '待复盘' },
  { value: 'failed', label: '需重试' },
]

const orderedGroups = computed(() => [...(selectedReview.value?.change_groups || [])].sort((left, right) => Number(right.is_major) - Number(left.is_major)))
const workflow = computed(() => selectedReview.value?.workflow || {})
const workflowStages = computed(() => workflow.value.run?.stages || [])
const semanticBlocks = computed(() => workflow.value.blocks || [])
const reorderEvents = computed(() => workflow.value.reorder_events || [])
const methodologyCandidates = computed(() => {
  const persisted = workflow.value.methodology_candidates || []
  return persisted.length ? persisted : (selectedReview.value?.ai_analysis?.methodology_candidates || [])
})
const hasConfirmedMethodology = computed(() => {
  const persisted = workflow.value.methodology_candidates || []
  return !persisted.length || persisted.some((item) => ['confirmed', 'promoted'].includes(item.status))
})
const currentStage = computed(() => workflow.value.run?.current_stage || null)
const currentStageLabel = computed(() => workflowStages.value.find((item) => item.stage_key === currentStage.value)?.label || '—')
const waitingForSemanticConfirmation = computed(() => workflowStages.value.some((item) => item.stage_key === 'semantic_segmentation' && item.status === 'awaiting_confirmation'))
const retryableStage = computed(() => {
  const failed = workflowStages.value.find((item) => item.status === 'failed' || item.status === 'invalidated')
  if (failed) return failed.stage_key
  if (selectedReview.value?.status === 'reviewing') return 'ai_review'
  return null
})
const retryableStageLabel = computed(() => retryableStage.value === 'ai_review' ? '重新分析' : retryableStage.value ? `重试${stageLabel(retryableStage.value)}` : '')

const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16) : '—'
const statusLabel = (value) => ({ processing: '解析中', analyzing: '分析中', reviewing: '待复盘', failed: '分析失败' }[value] || value || '未知')
const statusType = (value) => ({ processing: 'warning', analyzing: 'warning', reviewing: 'success', failed: 'danger' }[value] || 'info')
const impactLabel = (value) => ({ high: '重点修改', medium: '中等修改', low: '轻微修改' }[value] || '修改')
const impactType = (value) => ({ high: 'danger', medium: 'warning', low: 'info' }[value] || 'info')
const changeKindLabel = (value) => ({ replace: '替换', insert: '新增', delete: '删除', rewrite: '整段重写', structural_change: '结构变化', addition: '新增', deletion: '删除', reorder: '顺序调整', minor_edit: '轻微措辞', uncertain: '待确认' }[value] || '修改')
const humanLabel = (value) => ({ important: '人工确认重要', unimportant: '人工确认不重要', false_positive: '人工标记误判', needs_review: '人工标记待确认' }[value] || value)
const stageLabel = (value) => ({ parse: '解析', semantic_segmentation: '分段', semantic_alignment: '对齐', ai_review: 'AI 分析', methodology: '方法论' }[value] || value)
const stageStatusLabel = (value) => ({ queued: '排队中', running: '执行中', succeeded: '已完成', awaiting_confirmation: '待确认', blocked: '等待上游', invalidated: '需重算', failed: '失败', waiting: '等待' }[value] || value || '未开始')
const stageType = (value) => ({ succeeded: 'success', failed: 'danger', running: 'warning', awaiting_confirmation: 'warning', invalidated: 'danger', blocked: 'info' }[value] || 'info')
const stageMessage = (stage) => stage.message || (stage.status === 'succeeded' ? '已完成' : stage.status === 'blocked' ? '等待上游阶段' : '尚未开始')
const candidateStatusLabel = (value) => ({ candidate: '待确认', confirmed: '已确认', rejected: '已驳回', promoted: '已沉淀' }[value] || value)
const progressMessage = computed(() => progressState.value?.action || (selectedReview.value?.status === 'processing' ? '正在准备解析文件…' : '正在分析改动背后的原因和效果…'))

const syncWorkflowDraft = (value) => {
  const blocks = value || {}
  semanticDraft.before = JSON.parse(JSON.stringify((blocks.blocks || []).filter((item) => item.side === 'before')))
  semanticDraft.after = JSON.parse(JSON.stringify((blocks.blocks || []).filter((item) => item.side === 'after')))
}

const applyReviewResponse = (value) => {
  const previous = selectedReview.value
  const review = value?.review || value
  if (!review) return
  if (value?.run) review.workflow = { run: value.run, blocks: value.blocks || [], changes: value.changes || [], reorder_events: value.reorder_events || [], methodology_candidates: value.methodology_candidates || [], experience_sources: value.experience_sources || [] }
  if (!review.workflow && previous?.id === review.id && previous.workflow) review.workflow = previous.workflow
  selectedReview.value = review
  if (review.workflow) syncWorkflowDraft(review.workflow)
}

const loadReviews = async ({ selectFirst = true, silent = false } = {}) => {
  listLoading.value = true
  try {
    const response = await listArticleReviews({ page: 1, page_size: 50, keyword: filters.keyword.trim() || undefined, status: filters.status || undefined })
    const data = response.data || {}
    reviews.value = data.items || []
    if (selectedReview.value && reviews.value.some((item) => item.id === selectedReview.value.id)) {
      return
    }
    if (selectedReview.value) {
      selectedReview.value = null
      stopProgressStream()
      stopPolling()
    }
    if (selectFirst && !selectedReview.value && reviews.value.length) await selectReview(reviews.value[0].id)
  } catch {
    if (!silent) ElMessage.error('加载文章复盘失败')
  } finally {
    listLoading.value = false
  }
}

const selectReview = async (id) => {
  stopProgressStream()
  stopPolling()
  progressState.value = null
  detailLoading.value = true
  try {
    const response = await getArticleReview(id)
    applyReviewResponse(response.data)
    startProgressTracking()
  } catch {
    ElMessage.error('加载复盘详情失败')
  } finally {
    detailLoading.value = false
  }
}

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const stopProgressStream = () => {
  if (streamAbortController.value) {
    streamAbortController.value.abort()
    streamAbortController.value = null
  }
  if (progressReconnectTimer.value) {
    clearTimeout(progressReconnectTimer.value)
    progressReconnectTimer.value = null
  }
}

const clearSelectedReview = () => {
  stopProgressStream()
  stopPolling()
  progressState.value = null
  selectedReview.value = null
}

const startPolling = () => {
  stopPolling()
  if (!['processing', 'analyzing'].includes(selectedReview.value?.status) || waitingForSemanticConfirmation.value) return
  pollTimer.value = setInterval(async () => {
    if (!selectedReview.value) return
    try {
      const response = await getArticleReview(selectedReview.value.id)
      applyReviewResponse(response.data)
      if (!['processing', 'analyzing'].includes(selectedReview.value.status)) {
        progressState.value = null
        stopPolling()
        await loadReviews()
      }
    } catch {
      // 后台任务期间的单次网络抖动不打断轮询。
    }
  }, 3000)
}

const startProgressTracking = () => {
  stopProgressStream()
  stopPolling()
  progressState.value = null
  if (!['processing', 'analyzing'].includes(selectedReview.value?.status)) return

  const reviewId = selectedReview.value.id
  const runId = selectedReview.value.progress?.run_id
  if (!runId) {
    startPolling()
    return
  }

  let lastEventId = 0
  let reconnectCount = 0
  const connect = async () => {
    if (selectedReview.value?.id !== reviewId) return
    const controller = new AbortController()
    streamAbortController.value = controller
    try {
      const result = await streamArticleReview(reviewId, (payload, eventId) => {
        lastEventId = Number(eventId || lastEventId) || lastEventId
        if (selectedReview.value?.id === reviewId && payload?.progress) {
          progressState.value = payload.progress
        }
      }, { signal: controller.signal, lastEventId })
      lastEventId = Number(result?.lastEventId || lastEventId) || lastEventId
      if (controller.signal.aborted || selectedReview.value?.id !== reviewId) return
      const response = await getArticleReview(reviewId)
      if (selectedReview.value?.id !== reviewId) return
      applyReviewResponse(response.data)
      progressState.value = null
      if (['processing', 'analyzing'].includes(selectedReview.value.status) && !waitingForSemanticConfirmation.value) startPolling()
      else if (!waitingForSemanticConfirmation.value) await loadReviews()
    } catch {
      if (controller.signal.aborted || selectedReview.value?.id !== reviewId) return
      if (reconnectCount < 3) {
        reconnectCount += 1
        progressReconnectTimer.value = setTimeout(() => {
          progressReconnectTimer.value = null
          connect()
        }, Math.min(4_000, 500 * (2 ** (reconnectCount - 1))))
      } else {
        startPolling()
      }
    } finally {
      if (streamAbortController.value === controller) streamAbortController.value = null
    }
  }
  connect()
}

const pickFile = (side, event) => {
  const file = event.target.files?.[0] || null
  const error = validateUploadFile(file, 'articleReview')
  if (error) {
    ElMessage.error(error)
    event.target.value = ''
    return
  }
  const nextBefore = side === 'before' ? file : beforeFile.value
  const nextAfter = side === 'after' ? file : afterFile.value
  const pairError = validateArticleReviewFiles(nextBefore, nextAfter)
  if (pairError) {
    ElMessage.error(pairError)
    event.target.value = ''
    return
  }
  if (side === 'before') beforeFile.value = file
  else afterFile.value = file
}

const resetCreateForm = () => {
  createForm.title = ''
  beforeFile.value = null
  afterFile.value = null
}

const submitCreate = async () => {
  if (!beforeFile.value || !afterFile.value) {
    ElMessage.warning('请同时选择改前文章和改后文章')
    return
  }
  creating.value = true
  try {
    const response = await createArticleReview(beforeFile.value, afterFile.value, createForm.title)
    ElMessage.success('复盘已创建，正在分析改动')
    createVisible.value = false
    resetCreateForm()
    const createdReview = response.data?.review || null
    // POST 已在后端提交记录并投递任务；先进入这个已确认存在的详情，
    // 再静默刷新列表，避免列表请求失败覆盖刚创建的详情状态。
    if (createdReview?.id) await selectReview(createdReview.id)
    await loadReviews({ selectFirst: false, silent: true })
  } catch {
    ElMessage.error('创建文章复盘失败，请检查文件后重试')
  } finally {
    creating.value = false
  }
}

const commentsFor = (groupId) => {
  const change = (workflow.value.changes || []).find((item) => item.stable_id === groupId || item.id === groupId)
  return (selectedReview.value?.comments || []).filter((comment) => (
    comment.change_group_id === groupId || (change && comment.change_id === change.id)
  ))
}

const mergeSemanticBlock = (side, index) => {
  if (index <= 0) return
  const items = semanticDraft[side]
  items[index - 1].text = `${items[index - 1].text}\n${items[index].text}`.trim()
  items[index - 1].end_offset = items[index].end_offset || items[index - 1].end_offset
  items.splice(index, 1)
}

const splitSemanticBlock = (side, index) => {
  const items = semanticDraft[side]
  const current = items[index]
  const parts = String(current.text || '').split(/(?<=[。！？!?；;])\s*|\n+/).map((item) => item.trim()).filter(Boolean)
  if (parts.length < 2) {
    ElMessage.info('这块内容暂时没有明确的句子边界')
    return
  }
  items.splice(index, 1, ...parts.map((text, offset) => ({ ...current, stable_id: `${current.stable_id || side}-${index + offset + 1}`, text, user_edited: true })))
}

const confirmSemanticBlocks = async () => {
  if (!selectedReview.value || !semanticDraft.before.length || !semanticDraft.after.length) return
  confirmingBlocks.value = true
  try {
    const blocks = [
      ...semanticDraft.before.map((item, index) => ({ ...item, side: 'before', ordinal: index + 1 })),
      ...semanticDraft.after.map((item, index) => ({ ...item, side: 'after', ordinal: index + 1 })),
    ]
    const response = await updateArticleReviewSemanticBlocks(selectedReview.value.id, { blocks, lock: true })
    applyReviewResponse(response.data)
    semanticEditMode.value = false
    ElMessage.success('语义块已确认，正在计算语义级差异')
    startProgressTracking()
  } catch {
    ElMessage.error('语义块确认失败，请稍后重试')
  } finally {
    confirmingBlocks.value = false
  }
}

const reviewChange = async (group, label) => {
  const change = (workflow.value.changes || []).find((item) => item.stable_id === group.id || item.id === group.id)
  if (!change) {
    ElMessage.warning('当前改动还没有保存为可确认的语义变化')
    return
  }
  try {
    const response = await reviewArticleReviewChange(selectedReview.value.id, change.id, { human_label: label })
    applyReviewResponse(response.data)
    const persistedChange = (workflow.value.changes || []).find((item) => item.id === change.id)
    if (persistedChange) persistedChange.human_label = label
    ElMessage.success('人工判断已保存')
  } catch {
    ElMessage.error('人工判断保存失败')
  }
}

const retryStage = async () => {
  if (!selectedReview.value || !retryableStage.value) return
  analyzing.value = true
  try {
    const response = await retryArticleReviewStage(selectedReview.value.id, retryableStage.value)
    applyReviewResponse(response.data)
    const refreshed = await getArticleReview(selectedReview.value.id)
    applyReviewResponse(refreshed.data)
    ElMessage.success('阶段任务已重新提交')
    startProgressTracking()
  } catch {
    ElMessage.error('阶段任务提交失败')
  } finally {
    analyzing.value = false
  }
}

const confirmMethodology = async (candidate, status) => {
  try {
    const response = await confirmArticleReviewMethodology(selectedReview.value.id, candidate.id, { status })
    applyReviewResponse(response.data)
    ElMessage.success(status === 'confirmed' ? '方法论候选已确认' : '方法论候选已驳回')
  } catch {
    ElMessage.error('方法论确认失败')
  }
}

const addComment = async (group) => {
  const body = String(commentDrafts[group.id] || '').trim()
  if (!body || !selectedReview.value) return
  commenting[group.id] = true
  try {
    const change = (workflow.value.changes || []).find((item) => item.stable_id === group.id || item.id === group.id)
    const response = await addArticleReviewComment(selectedReview.value.id, {
      change_group_id: group.id,
      change_id: change?.id,
      body,
    })
    selectedReview.value.comments = [...(selectedReview.value.comments || []), response.data.comment]
    commentDrafts[group.id] = ''
    ElMessage.success('评论已保存')
  } catch {
    ElMessage.error('评论保存失败')
  } finally {
    commenting[group.id] = false
  }
}

const retryAnalysis = async () => {
  if (!selectedReview.value) return
  analyzing.value = true
  try {
    const response = await analyzeArticleReview(selectedReview.value.id)
    applyReviewResponse(response.data)
    ElMessage.success('AI 分析任务已提交')
    startProgressTracking()
  } catch {
    ElMessage.error('AI 分析任务提交失败')
  } finally {
    analyzing.value = false
  }
}

const openAnalysisEditor = () => {
  const analysis = selectedReview.value?.ai_analysis || {}
  analysisForm.summary = analysis.summary || ''
  analysisForm.methodology_candidates = JSON.parse(JSON.stringify(analysis.methodology_candidates || []))
  analysisEditVisible.value = true
}

const saveAnalysis = async () => {
  if (!selectedReview.value) return
  savingAnalysis.value = true
  try {
    const response = await updateArticleReviewAnalysis(selectedReview.value.id, {
      summary: analysisForm.summary.trim() || null,
      methodology_candidates: analysisForm.methodology_candidates.filter((item) => String(item.rule || '').trim()).map((item) => ({ ...item, title: String(item.title || '').trim(), rule: String(item.rule || '').trim() })),
    })
    applyReviewResponse(response.data)
    analysisEditVisible.value = false
    ElMessage.success('人工修订已保存')
  } catch {
    ElMessage.error('人工修订保存失败')
  } finally {
    savingAnalysis.value = false
  }
}

const openPromote = (candidate = null) => {
  const groupIds = candidate?.evidence_group_ids?.length
    ? candidate.evidence_group_ids
    : (selectedReview.value?.change_groups || []).filter((group) => group.is_major).map((group) => group.id)
  promoteForm.title = candidate?.title || ''
  promoteForm.category = '文章复盘'
  promoteForm.content = candidate ? `${candidate.title || '方法论'}\n\n${candidate.rule || ''}\n\n为什么：${candidate.rationale || '未说明'}\n\n本次例子：${candidate.example || '未说明'}` : ''
  promoteForm.groupIds = [...groupIds]
  promoteVisible.value = true
}

const submitPromote = async () => {
  if (!selectedReview.value) return
  promoting.value = true
  try {
    const response = await promoteArticleReview(selectedReview.value.id, {
      title: promoteForm.title.trim() || null,
      category: promoteForm.category.trim() || null,
      content: promoteForm.content.trim() || null,
      change_group_ids: promoteForm.groupIds,
    })
    selectedReview.value.promoted_card_ids = [...new Set([...(selectedReview.value.promoted_card_ids || []), response.data.card.id])]
    promoteVisible.value = false
    ElMessage.success('已沉淀到经验库')
  } catch {
    ElMessage.error('经验沉淀失败')
  } finally {
    promoting.value = false
  }
}

onMounted(async () => {
  await loadReviews()
  const reviewId = Number(route.query.review_id)
  if (reviewId > 0) await selectReview(reviewId)
})
onBeforeUnmount(() => {
  stopProgressStream()
  stopPolling()
})
</script>

<style scoped>
.reviews-page { max-width: 1380px; margin: 0 auto; padding-bottom: 56px; color: var(--ink); }
.reviews-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 26px; }
.eyebrow { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .12em; }
.reviews-hero h1 { margin: 10px 0 8px; font: 500 34px/1.25 var(--serif, serif); }
.reviews-hero p { max-width: 720px; margin: 0; color: var(--ink-3); font-size: 14px; line-height: 1.7; }
.workspace-grid { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 22px; min-height: 680px; }
.review-list-panel, .review-detail-panel, .empty-detail-panel { border: 1px solid #e8ddca; border-radius: var(--r-lg); background: #fffdf9; box-shadow: 0 8px 24px rgba(72,57,43,.05); }
.review-list-panel { padding: 20px 14px; }
.list-panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin: 0 6px 16px; }
.list-panel-head h2 { margin: 6px 0 0; font-size: 20px; }
.status-filter { display: flex; gap: 5px; margin: 13px 2px 12px; }
.status-filter button { border: 0; border-radius: 99px; padding: 5px 9px; background: transparent; color: var(--ink-3); cursor: pointer; font-size: 12px; }
.status-filter button.active { background: var(--clay-tint); color: var(--clay-deep); font-weight: 700; }
.review-list { min-height: 420px; }
.review-list-item { display: block; width: 100%; margin-bottom: 7px; padding: 13px 12px; border: 1px solid transparent; border-radius: var(--r-md); background: transparent; color: var(--ink); cursor: pointer; text-align: left; transition: .2s ease; }
.review-list-item:hover { border-color: #e7d9c4; background: #fbf5ec; }
.review-list-item.selected { border-color: var(--clay); background: var(--clay-tint); }
.review-list-item-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.review-list-item-top strong { min-width: 0; overflow: hidden; font-size: 14px; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.review-list-files { display: block; margin-top: 8px; overflow: hidden; color: var(--ink-3); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.review-list-meta { display: flex; justify-content: space-between; gap: 8px; margin-top: 9px; color: var(--ink-4); font-size: 11px; }
.review-detail-panel { padding: 28px 30px 40px; }
.detail-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 22px; margin-bottom: 22px; }
.detail-head h2 { margin: 14px 0 10px; font: 500 28px/1.3 var(--serif, serif); }
.back-link { border: 0; padding: 0; background: none; color: var(--ink-3); cursor: pointer; font-size: 12px; }
.detail-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; color: var(--ink-3); font-size: 12px; }
.detail-actions { display: flex; flex: 0 0 auto; gap: 8px; }
.state-banner { display: flex; align-items: flex-start; gap: 11px; margin-bottom: 18px; padding: 13px 15px; border-radius: var(--r-md); }
.state-banner strong, .state-banner span { display: block; }.state-banner strong { margin-bottom: 3px; font-size: 13px; }.state-banner span { color: var(--ink-3); font-size: 12px; line-height: 1.6; }
.state-banner.running { background: var(--clay-tint); color: var(--clay-deep); }.state-banner.waiting { align-items: center; background: #f5f1e7; color: var(--ink-2); }.state-banner.waiting > div { flex: 1; }.state-banner.failed { background: #f8eceb; color: var(--crimson); }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 25px; }
.stat-card { padding: 16px; border: 1px solid #eee3d2; border-radius: var(--r-md); background: #fbf6ef; }.stat-card span, .stat-card small { display: block; color: var(--ink-3); font-size: 11px; }.stat-card strong { display: block; margin: 6px 0 2px; font-size: 25px; font-weight: 600; }.stat-highlight { border-color: #e9b2a6; background: #fff5f1; }.stat-highlight strong { color: var(--crimson); }
.content-section { margin-bottom: 24px; padding: 24px; border: 1px solid #e8ddca; border-radius: var(--r-lg); background: #fffdf9; }.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 18px; }.section-heading h3 { margin: 6px 0 5px; font-size: 22px; }.section-heading p { margin: 0; color: var(--ink-3); font-size: 12px; line-height: 1.6; }.section-count { color: var(--clay-deep); font-size: 12px; white-space: nowrap; }
.section-actions { display: flex; gap: 7px; flex-wrap: wrap; }.stage-list { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }.stage-item { display: flex; align-items: flex-start; gap: 8px; min-height: 75px; padding: 11px; border: 1px solid #eee3d2; border-radius: var(--r-sm); background: #fbf7f0; }.stage-item > div { min-width: 0; flex: 1; }.stage-item strong, .stage-item small { display: block; }.stage-item strong { font-size: 12px; }.stage-item small { margin-top: 5px; color: var(--ink-4); font-size: 10px; line-height: 1.45; }.stage-dot { display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; width: 21px; height: 21px; border-radius: 50%; background: #e8ddca; color: var(--ink-3); font-size: 10px; font-weight: 700; }.stage-succeeded .stage-dot { background: #dcebd6; color: #4f7646; }.stage-running .stage-dot, .stage-awaiting_confirmation .stage-dot { background: #f2dfb7; color: #9a6b1b; }.stage-failed .stage-dot, .stage-invalidated .stage-dot { background: #f2d8d3; color: var(--crimson); }
.semantic-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.semantic-column { min-width: 0; }.semantic-column-head { display: flex; justify-content: space-between; margin-bottom: 8px; color: var(--clay-deep); font-size: 12px; }.semantic-column-head span { color: var(--ink-4); }.semantic-block { margin-bottom: 8px; padding: 11px 12px; border: 1px solid #eee3d2; border-radius: var(--r-sm); background: #fbf7f0; }.semantic-block-head { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 7px; }.semantic-block-head span { color: var(--clay-deep); font-size: 11px; font-weight: 700; }.semantic-block-head small { color: var(--ink-4); font-size: 10px; }.semantic-block p { margin: 0; color: var(--ink-2); white-space: pre-wrap; font-size: 12px; line-height: 1.7; }.semantic-block-actions { display: flex; gap: 2px; margin-top: 5px; }.change-reason { margin: 0 0 11px; color: var(--ink-3); font-size: 12px; line-height: 1.6; }.change-reason strong { color: var(--clay-deep); }.change-review-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 12px; color: var(--ink-3); font-size: 11px; }.reorder-list { display: flex; flex-direction: column; gap: 8px; }.reorder-item { display: flex; align-items: flex-start; gap: 10px; padding: 12px; border: 1px solid #ead6a9; border-radius: var(--r-sm); background: #fffaf0; }.reorder-item strong { font-size: 13px; }.reorder-item p { margin: 5px 0 0; color: var(--ink-3); font-size: 11px; }.method-actions { display: flex; align-items: center; flex-direction: column; gap: 5px; }
.change-list { display: flex; flex-direction: column; gap: 13px; }.change-card { padding: 16px; border: 1px solid #e7dfd2; border-radius: var(--r-md); background: #fcfaf6; }.change-card.impact-high { border-color: #edb8ac; background: #fff8f4; }.change-card.impact-medium { border-color: #ead6a9; }.change-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }.change-label { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--ink-3); font-size: 12px; }.change-index { color: var(--clay-deep); font-weight: 700; }.change-ratio { color: var(--ink-4); font-size: 11px; }
.diff-columns { display: grid; grid-template-columns: minmax(0,1fr) 26px minmax(0,1fr); align-items: stretch; gap: 9px; }.diff-block { min-height: 90px; padding: 12px; border-radius: var(--r-sm); }.diff-block span { display: block; margin-bottom: 7px; font-size: 11px; font-weight: 700; }.diff-block p { margin: 0; white-space: pre-wrap; color: var(--ink-2); font-size: 13px; line-height: 1.75; }.diff-block.before { background: #f8e9e6; }.diff-block.before span { color: #a45247; }.diff-block.after { background: #edf5e9; }.diff-block.after span { color: #4f7646; }.diff-arrow { align-self: center; color: var(--ink-4); text-align: center; }
.comment-area { margin-top: 12px; }.comment-list { display: flex; flex-direction: column; gap: 7px; margin-bottom: 9px; }.comment-item { padding: 9px 11px; border-left: 3px solid var(--clay); border-radius: 0 var(--r-sm) var(--r-sm) 0; background: #f7f1e8; }.comment-item div { display: flex; gap: 8px; align-items: center; }.comment-item strong { font-size: 12px; }.comment-item small { color: var(--ink-4); font-size: 10px; }.comment-item p { margin: 5px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.6; }
.ai-summary { margin-bottom: 15px; padding: 16px 18px; border-left: 4px solid var(--clay); border-radius: 0 var(--r-md) var(--r-md) 0; background: var(--clay-tint); color: var(--ink); font-size: 16px; line-height: 1.8; }.analysis-change-list { display: flex; flex-direction: column; gap: 10px; }.analysis-change-item { padding: 14px; border: 1px solid #eee3d2; border-radius: var(--r-md); background: #fbf7f0; }.analysis-change-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }.analysis-change-title strong { font-size: 14px; }.analysis-change-title span { margin-left: auto; color: var(--ink-4); font-size: 11px; }.analysis-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-top: 12px; }.analysis-fields > div, .method-fields > div { padding: 10px 12px; border-radius: var(--r-sm); background: #fffdf9; }.analysis-fields span, .method-fields span { display: block; margin-bottom: 4px; color: var(--clay-deep); font-size: 11px; font-weight: 700; }.analysis-fields p, .method-fields p { margin: 0; color: var(--ink-2); font-size: 12px; line-height: 1.65; }
.methodology-list { display: flex; flex-direction: column; gap: 10px; }.methodology-card { display: grid; grid-template-columns: 35px minmax(0, 1fr) auto; gap: 13px; align-items: start; padding: 16px; border: 1px solid #e8ddca; border-radius: var(--r-md); background: #faf5ed; }.method-number { color: var(--clay-deep); font-size: 13px; font-weight: 700; }.method-body h4 { margin: 0 0 7px; font-size: 16px; }.method-body .rule { margin: 0; color: var(--ink); font-size: 13px; line-height: 1.7; }.method-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 11px; }.method-body small { display: block; margin-top: 10px; color: var(--ink-4); font-size: 10px; }
.source-section { margin-top: 4px; padding: 0 18px 18px; border: 1px solid #e8ddca; border-radius: var(--r-lg); background: #fffdf9; }.source-section summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 2px; cursor: pointer; list-style: none; color: var(--ink-3); font-size: 12px; }.source-section summary::-webkit-details-marker { display: none; }.source-section summary strong, .source-section summary small { display: block; }.source-section summary strong { color: var(--ink-2); font-size: 14px; }.source-section summary small { margin-top: 3px; font-size: 11px; }.source-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.source-columns b { display: block; margin: 0 0 6px; color: var(--clay-deep); font-size: 12px; }.source-columns pre { max-height: 500px; overflow: auto; margin: 0; padding: 14px; border-radius: var(--r-sm); background: var(--ivory); white-space: pre-wrap; color: var(--ink-2); font: 12px/1.8 var(--sans, sans-serif); }
.empty-detail-panel { display: flex; align-items: center; justify-content: center; min-height: 680px; padding: 40px; text-align: center; }.empty-detail-panel > div { max-width: 430px; }.empty-mark { display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; margin-bottom: 14px; border-radius: 50%; background: var(--clay-tint); color: var(--clay-deep); font-size: 25px; }.empty-detail-panel h2 { margin: 0 0 9px; font: 500 26px var(--serif, serif); }.empty-detail-panel p { margin: 0 0 20px; color: var(--ink-3); font-size: 13px; line-height: 1.7; }
.upload-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.upload-box { position: relative; display: flex; flex-direction: column; gap: 8px; min-height: 105px; padding: 17px; border: 1px dashed #d8c5a9; border-radius: var(--r-md); background: #fbf6ef; cursor: pointer; }.upload-box:hover { border-color: var(--clay); background: var(--clay-tint); }.upload-box span { color: var(--clay-deep); font-size: 11px; font-weight: 700; }.upload-box strong { color: var(--ink-2); font-size: 13px; line-height: 1.5; }.upload-box input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }.dialog-tip, .promote-intro { color: var(--ink-3); font-size: 12px; line-height: 1.65; }.editor-list { display: flex; flex-direction: column; gap: 11px; max-height: 430px; overflow: auto; margin-bottom: 12px; }.editor-item { padding: 13px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--ivory); }.editor-item-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 13px; }.editor-input { margin-bottom: 8px; }.editor-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.group-checkboxes { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
@media (max-width: 1050px) { .workspace-grid { grid-template-columns: 270px minmax(0, 1fr); }.review-detail-panel { padding: 24px 20px 34px; }.stats-grid { grid-template-columns: repeat(2, 1fr); }.stage-list { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .reviews-hero, .detail-head { align-items: flex-start; flex-direction: column; }.reviews-hero .el-button, .detail-actions { width: 100%; }.detail-actions .el-button { flex: 1; }.workspace-grid { display: block; }.review-list-panel { margin-bottom: 16px; }.review-list { min-height: auto; max-height: 310px; overflow: auto; }.empty-detail-panel { min-height: 360px; }.diff-columns, .source-columns, .analysis-fields, .method-fields, .upload-pair, .semantic-columns { grid-template-columns: 1fr; }.diff-arrow { transform: rotate(90deg); }.methodology-card { grid-template-columns: 30px minmax(0, 1fr); }.methodology-card .method-actions { grid-column: 2; align-items: flex-start; flex-direction: row; flex-wrap: wrap; }.content-section { padding: 18px 14px; }.section-heading { flex-direction: column; }.section-heading .el-button { width: 100%; }.stats-grid { gap: 7px; }.stat-card { padding: 12px; }.stat-card strong { font-size: 21px; }.editor-two-col { grid-template-columns: 1fr; }.stage-list { grid-template-columns: 1fr; }.state-banner.waiting { align-items: flex-start; flex-wrap: wrap; }.state-banner.waiting .el-button { margin-left: 29px; } }
</style>
