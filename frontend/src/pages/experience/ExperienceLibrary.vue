<template>
  <div class="experience-page">
    <header class="experience-hero">
      <div>
        <div class="eyebrow">TEAM MEMORY · PHASE 1C</div>
        <h1>经验库</h1>
        <p>把会议方法论、文章复盘和实际修改整理成团队以后可以直接复用的判断。原始材料先进入待确认，确认后才成为正式经验。</p>
      </div>
      <div class="hero-actions">
        <el-button size="large" :loading="overlapLoading" @click="scanOverlaps">
          <el-icon><Connection /></el-icon> 查找重合
        </el-button>
        <el-button type="primary" size="large" @click="openCreateDialog">
          <el-icon><Plus /></el-icon> 新增经验
        </el-button>
      </div>
    </header>

    <section class="library-tabs">
      <el-button-group>
        <el-button :type="filters.status === 'confirmed' ? 'primary' : 'default'" @click="switchStatus('confirmed')">正式经验</el-button>
        <el-button :type="filters.status === 'pending' ? 'primary' : 'default'" @click="switchStatus('pending')">待确认</el-button>
      </el-button-group>
      <span class="tab-note">{{ filters.status === 'pending' ? '这里是刚处理出的候选，确认后才会进入正式经验库。' : '这里只展示已经确认、可以被团队复用的经验。' }}</span>
    </section>

    <section class="search-card">
      <el-input v-model="filters.q" clearable class="search-input" placeholder="搜索经验标题、正文或分类" @keyup.enter="loadCards">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filters.category" clearable filterable allow-create placeholder="分类" class="category-select" @change="loadCards">
        <el-option v-for="category in categories" :key="category" :label="category" :value="category" />
      </el-select>
      <el-select v-model="filters.source_type" clearable placeholder="来源" class="source-select" @change="loadCards">
        <el-option v-for="source in sourceTypes" :key="source.value" :label="source.label" :value="source.value" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="loadCards">搜索</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </section>

    <div class="result-note">
      <span>{{ total }} 条经验</span>
      <span v-if="searchMode === 'semantic'">当前使用语义检索</span>
      <span v-else-if="searchMode === 'keyword_fallback'">Embedding 不可用，当前使用关键词降级</span>
      <span v-else>按创建时间倒序</span>
    </div>

    <section v-loading="loading" class="card-list">
      <article v-for="card in cards" :key="card.id" class="experience-card" tabindex="0" @click="openDetail(card)" @keyup.enter="openDetail(card)">
        <div class="card-head">
          <div>
            <div class="card-kicker">
              <el-tag size="small" effect="plain">{{ sourceTypeLabel(card.source_type) }}</el-tag>
              <el-tag v-if="card.status === 'pending'" size="small" type="warning">待确认</el-tag>
              <span v-if="card.category">{{ card.category }}</span>
              <span v-if="card.match_method && searchMode !== 'recent'">{{ matchMethodLabel(card.match_method) }}</span>
            </div>
            <h2>{{ card.title }}</h2>
          </div>
          <span class="card-date">{{ formatDate(card.created_at) }}</span>
        </div>
        <p class="card-content">{{ card.content }}</p>
        <div v-if="card.source_meta?.meeting_title || card.source_meta?.filename" class="source-context">
          来源：{{ card.source_meta.meeting_title || card.source_meta.filename }}
        </div>
        <div class="card-foot">
          <span class="creator">{{ card.created_by_user?.full_name || card.created_by_user?.username || '团队成员' }}</span>
          <span v-if="card.similarity !== null && card.similarity !== undefined" class="similarity">相似度 {{ Math.round(card.similarity * 100) }}%</span>
          <span class="embedding-state" :class="`embedding-${card.embedding_status}`">{{ embeddingStatusLabel(card.embedding_status) }}</span>
          <el-button text type="primary" size="small" @click.stop="openDetail(card)">查看完整经验 <el-icon><ArrowRight /></el-icon></el-button>
          <el-button v-if="card.status === 'pending'" text type="success" size="small" @click.stop="confirmCard(card)">确认沉淀</el-button>
          <el-button v-if="card.source_type === 'review_feedback' && card.version_pair?.review_id" text type="primary" size="small" @click.stop="openReviewSource(card)">查看文章复盘 <el-icon><ArrowRight /></el-icon></el-button>
          <el-button v-else-if="card.source_type === 'meeting_methodology' && card.source_meta?.meeting_id" text type="primary" size="small" @click.stop="openMeetingSource(card)">查看会议 <el-icon><ArrowRight /></el-icon></el-button>
          <el-button v-else-if="card.creation_id && card.version_pair && card.source_accessible" text type="primary" size="small" @click.stop="openSource(card)">查看来源版本 <el-icon><ArrowRight /></el-icon></el-button>
          <span v-else-if="card.creation_id && card.version_pair" class="source-locked">来源文章当前不可访问</span>
        </div>
      </article>
      <el-empty v-if="!loading && !cards.length" :image-size="70" :description="filters.status === 'pending' ? '还没有待确认经验，先从会议或文章复盘里生成一条吧' : '还没有正式经验，先新增一条或上传一份 PDF/Word 吧'" />
    </section>

    <div class="pagination-wrap">
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" layout="total, prev, pager, next" :total="total" @current-change="loadCards" />
    </div>

    <el-dialog v-model="createVisible" title="新增经验" width="700px" align-center destroy-on-close :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="restoreDialogScroll">
      <div class="upload-intro">
        <div><strong>支持上传 PDF / Word</strong><span>上传内容会先保存到“待确认”，你可以改标题、正文和分类，再确认进入正式经验库。</span></div>
        <input ref="fileInput" type="file" accept=".pdf,.docx,.txt,.md,.markdown" hidden @change="handleFileChange">
        <el-button plain :loading="uploading" @click="fileInput?.click()"><el-icon><Upload /></el-icon> 上传并解析</el-button>
      </div>
      <div v-if="uploadMessage" class="upload-message" :class="{ 'is-error': uploadFailed }">{{ uploadMessage }}</div>
      <el-form :model="form" label-position="top">
        <el-form-item label="经验标题" required><el-input v-model="form.title" maxlength="200" show-word-limit placeholder="例如：开头要让读者先看见具体冲突" /></el-form-item>
        <el-form-item label="经验正文" required><el-input v-model="form.content" type="textarea" :rows="12" maxlength="50000" show-word-limit placeholder="写下可复用的判断、做法和依据；也可以先上传文件解析" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="form.category" maxlength="50" placeholder="例如：开头、结构、案例、表达" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveCard">{{ form.uploaded ? '保存到待确认' : '保存正式经验' }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailVisible" width="780px" align-center destroy-on-close class="experience-detail-dialog" :lock-scroll="false" @open="rememberDialogScroll" @opened="restoreDialogScroll" @closed="onDetailClosed">
      <template #header>
        <div class="detail-dialog-head">
          <div>
            <div class="card-kicker"><el-tag v-if="detailCard" size="small" effect="plain">{{ sourceTypeLabel(detailCard.source_type) }}</el-tag><el-tag v-if="detailCard?.status === 'pending'" size="small" type="warning">待确认</el-tag><span v-if="detailCard?.category">{{ detailCard.category }}</span></div>
            <h2>{{ detailCard?.title || '经验详情' }}</h2>
          </div>
          <el-button v-if="detailCard?.status === 'pending' && !detailEditing" text type="primary" @click="startDetailEdit">编辑</el-button>
        </div>
      </template>
      <div v-if="detailLoading" class="detail-loading"><el-icon class="is-loading"><Loading /></el-icon>正在加载完整经验…</div>
      <template v-else-if="detailCard">
        <div v-if="detailEditing" class="detail-edit-form">
          <el-form label-position="top">
            <el-form-item label="经验标题"><el-input v-model="detailForm.title" maxlength="200" show-word-limit /></el-form-item>
            <el-form-item label="经验正文"><el-input v-model="detailForm.content" type="textarea" :rows="14" maxlength="50000" show-word-limit /></el-form-item>
            <el-form-item label="分类"><el-input v-model="detailForm.category" maxlength="50" /></el-form-item>
          </el-form>
        </div>
        <div v-else class="detail-content">
          <div class="detail-body markdown-body" v-html="renderExperienceMarkdown(detailCard.content)"></div>
          <div v-if="detailCard.source_meta?.meeting_title || detailCard.source_meta?.filename" class="detail-source"><strong>来源</strong><span>{{ detailCard.source_meta.meeting_title || detailCard.source_meta.filename }}</span></div>
          <div v-if="detailCard.source_type === 'review_feedback' && detailCard.version_pair?.before_filename" class="detail-source"><strong>复盘文件</strong><span>{{ detailCard.version_pair.before_filename }} → {{ detailCard.version_pair.after_filename }}</span></div>
          <div class="detail-meta-row"><span>创建于 {{ formatDate(detailCard.created_at) }}</span><span>{{ detailCard.created_by_user?.full_name || detailCard.created_by_user?.username || '团队成员' }}</span><span>{{ embeddingStatusLabel(detailCard.embedding_status) }}</span></div>
        </div>
        <div v-if="detailCard.status === 'confirmed'" class="similar-section">
          <div class="similar-head">
            <strong>相似经验</strong>
            <span v-if="!similarLoading">{{ similarCards.length ? '可勾选合并' : '没有发现高度相似的经验' }}</span>
          </div>
          <div v-if="similarLoading" class="similar-loading"><el-icon class="is-loading"><Loading /></el-icon> 正在查找相似经验…</div>
          <div v-else-if="similarCards.length" class="similar-list">
            <div v-for="similar in similarCards" :key="similar.id" class="similar-item">
              <div class="similar-item-main">
                <strong>{{ similar.title }}</strong>
                <span class="similarity-tag">相似度 {{ Math.round((similar.similarity || 0) * 100) }}%</span>
                <p>{{ similar.content }}</p>
              </div>
              <el-button text type="primary" size="small" @click="mergeWithSimilar(similar)">合并</el-button>
            </div>
          </div>
        </div>
      </template>
      <template #footer>
        <template v-if="detailEditing">
          <el-button @click="detailEditing = false">取消</el-button><el-button type="primary" :loading="detailSaving" @click="saveDetail">保存修改</el-button>
        </template>
        <template v-else-if="detailCard?.status === 'pending'">
          <el-button type="danger" plain :loading="detailSaving" @click="rejectCard(detailCard)">退回</el-button><el-button type="primary" :loading="detailSaving" @click="confirmCard(detailCard)">确认沉淀</el-button>
        </template>
        <el-button v-else @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="overlapVisible" title="查找重合经验" width="860px" align-center destroy-on-close class="overlap-dialog" :lock-scroll="false">
      <div v-loading="overlapLoading" class="overlap-body">
        <p class="overlap-hint">按语义相似度扫描正式经验，把重合度高的归为一组。这里只做提示，不会自动合并或删除。</p>
        <el-empty v-if="!overlapLoading && !overlapGroups.length" :image-size="60" description="没有发现明显重合的经验" />
        <div v-for="(group, gIndex) in overlapGroups" :key="gIndex" class="overlap-group">
          <div class="overlap-group-head">
            <strong>重合组 {{ gIndex + 1 }}</strong>
            <span class="similarity-tag">{{ Math.round(group.max_similarity * 100) }}% 最高相似度</span>
            <el-button type="primary" plain size="small" @click="openMergeDialog(group.cards.map((c) => c.id))">合并这组</el-button>
          </div>
          <div class="overlap-card-list">
            <div v-for="card in group.cards" :key="card.id" class="overlap-card">
              <strong>{{ card.title }}</strong>
              <span v-if="card.category">{{ card.category }}</span>
              <p>{{ card.content_preview }}<template v-if="card.content && card.content.length > 120">…</template></p>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="overlapVisible = false">关闭</el-button>
        <el-button type="primary" :loading="overlapLoading" @click="scanOverlaps">重新扫描</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="mergeVisible" title="合并经验" width="860px" align-center destroy-on-close class="merge-dialog" :lock-scroll="false">
      <div v-if="mergePreviewing" class="merge-loading"><el-icon class="is-loading" :size="22"><Loading /></el-icon><span>正在生成智能合并稿…</span></div>
      <template v-else>
        <p class="merge-hint">以下 {{ mergeSources.length }} 条经验将合并为一条正式经验，合并后原记录会标记为「已合并」并从正式库隐藏，不会被删除。</p>
        <div class="merge-sources">
          <div v-for="(card, index) in mergeSources" :key="card.id" class="merge-source">
            <span class="merge-source-index">{{ index + 1 }}</span>
            <div class="merge-source-body">
              <strong>{{ card.title }}</strong>
              <span v-if="card.category">{{ card.category }} · {{ sourceTypeLabel(card.source_type) }}</span>
              <p>{{ card.content }}</p>
            </div>
          </div>
        </div>
        <el-divider content-position="left">合并后的经验（可编辑）</el-divider>
        <el-form label-position="top">
          <el-form-item label="经验标题" required><el-input v-model="mergeForm.title" maxlength="200" show-word-limit /></el-form-item>
          <el-form-item label="分类"><el-input v-model="mergeForm.category" maxlength="50" placeholder="例如：开头、结构、案例" /></el-form-item>
          <el-form-item label="经验正文" required><el-input v-model="mergeForm.content" type="textarea" :rows="10" maxlength="50000" show-word-limit /></el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="mergeVisible = false">取消</el-button>
        <el-button :loading="mergePreviewing" @click="generateMergePreview">重新生成</el-button>
        <el-button type="primary" :loading="mergeSaving" :disabled="mergePreviewing || !mergeSources.length" @click="confirmMerge">确认合并</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Connection, Loading, Plus, Search, Upload } from '@element-plus/icons-vue'
import {
  confirmExperienceCard,
  confirmExperienceMerge,
  createExperienceCard,
  createExperienceDraft,
  getExperienceCard,
  getSimilarExperiences,
  listExperienceCards,
  parseExperienceUpload,
  previewExperienceMerge,
  rejectExperienceCard,
  scanExperienceOverlaps,
  updateExperienceCard,
} from '@/api/experience'
import { renderExperienceMarkdown } from '@/utils/experienceMarkdown'
import { formatDateTimeMinute } from '@/utils/dateTime'
import { useDialogScrollPosition } from '@/utils/dialogScrollPosition'

const router = useRouter()
const { rememberDialogScroll, restoreDialogScroll } = useDialogScrollPosition()
const cards = ref([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const searchMode = ref('recent')
const createVisible = ref(false)
const fileInput = ref(null)
const uploadMessage = ref('')
const uploadFailed = ref(false)
const categories = ref([])
const filters = reactive({ q: '', category: '', source_type: '', status: 'confirmed' })
const pagination = reactive({ page: 1, pageSize: 12 })
const form = reactive({ title: '', content: '', category: '', uploaded: false, source_meta: null })
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailSaving = ref(false)
const detailEditing = ref(false)
const detailCard = ref(null)
const detailForm = reactive({ title: '', content: '', category: '' })
const similarCards = ref([])
const similarLoading = ref(false)
const overlapVisible = ref(false)
const overlapLoading = ref(false)
const overlapGroups = ref([])
const mergeVisible = ref(false)
const mergePreviewing = ref(false)
const mergeSaving = ref(false)
const mergeSources = ref([])
const mergeForm = reactive({ title: '', content: '', category: '' })

const sourceTypes = [
  { value: 'meeting_methodology', label: '会议方法论' },
  { value: 'review_feedback', label: '文章复盘' },
  { value: 'meeting_diff', label: '文章版本' },
  { value: 'uploaded', label: '上传材料' },
  { value: 'manual', label: '手动新增' },
]

const sourceTypeLabel = (value) => ({ meeting_methodology: '会议方法论', meeting_diff: '文章版本', review_feedback: '文章复盘', uploaded: '上传材料', manual: '手动新增' }[value] || value || '经验')
const matchMethodLabel = (value) => ({ semantic: '语义命中', 'semantic+keyword': '语义 + 关键词', keyword_fallback: '关键词降级' }[value] || value)
const embeddingStatusLabel = (value) => ({ waiting: '确认后生成 Embedding', pending: 'Embedding 生成中', ready: '已向量化', failed: 'Embedding 不可用' }[value] || '待处理')
const formatDate = formatDateTimeMinute

const loadCards = async () => {
  loading.value = true
  try {
    const response = await listExperienceCards({ q: filters.q || undefined, category: filters.category || undefined, source_type: filters.source_type || undefined, status: filters.status, page: pagination.page, page_size: pagination.pageSize })
    const data = response.data || {}
    cards.value = data.items || []
    total.value = data.total || 0
    searchMode.value = data.search_mode || 'recent'
    const foundCategories = cards.value.map((card) => card.category).filter(Boolean)
    categories.value = [...new Set([...categories.value, ...foundCategories])]
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验库加载失败')
  } finally {
    loading.value = false
  }
}

const switchStatus = (value) => {
  filters.status = value
  pagination.page = 1
  loadCards()
}

const resetFilters = () => {
  filters.q = ''
  filters.category = ''
  filters.source_type = ''
  pagination.page = 1
  loadCards()
}

const openCreateDialog = () => {
  Object.assign(form, { title: '', content: '', category: '', uploaded: false, source_meta: null })
  uploadMessage.value = ''
  uploadFailed.value = false
  createVisible.value = true
}

const handleFileChange = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  uploadMessage.value = `正在解析 ${file.name}…`
  uploadFailed.value = false
  try {
    const response = await parseExperienceUpload(file)
    const data = response.data || {}
    form.content = data.text || ''
    form.uploaded = true
    form.source_meta = { filename: data.filename || file.name, parse_mode: data.parse_mode || 'pdf_or_docx' }
    if (!form.title) form.title = file.name.replace(/\.(pdf|docx|txt|md|markdown)$/i, '')
    uploadMessage.value = data.truncated ? `解析成功，内容超过上限，已截取前 ${data.char_count} 字。` : `解析成功，共 ${data.char_count} 字；请检查后再保存。`
  } catch (error) {
    uploadFailed.value = true
    uploadMessage.value = error?.response?.data?.detail || '文件解析失败，请换用未加密的文字版 PDF/Word'
  } finally {
    uploading.value = false
  }
}

const saveCard = async () => {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('请填写经验标题和正文')
    return
  }
  saving.value = true
  try {
    if (form.uploaded) {
      await createExperienceDraft({ title: form.title.trim(), content: form.content.trim(), category: form.category.trim() || null, source_type: 'uploaded', source_meta: form.source_meta })
      ElMessage.success('材料已进入待确认，确认后会出现在正式经验库')
      filters.status = 'pending'
    } else {
      await createExperienceCard({ title: form.title.trim(), content: form.content.trim(), category: form.category.trim() || null, source_type: 'manual' })
      ElMessage.success('经验卡片已保存，Embedding 将在后台生成')
      filters.status = 'confirmed'
    }
    createVisible.value = false
    pagination.page = 1
    await loadCards()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验保存失败')
  } finally {
    saving.value = false
  }
}

const openDetail = async (card) => {
  detailCard.value = card
  detailForm.title = card.title || ''
  detailForm.content = card.content || ''
  detailForm.category = card.category || ''
  detailEditing.value = false
  detailVisible.value = true
  detailLoading.value = true
  similarCards.value = []
  try {
    const [response] = await Promise.all([
      getExperienceCard(card.id),
      card.status === 'confirmed' ? loadSimilarCards(card.id) : Promise.resolve(),
    ])
    const loaded = response.data?.card || response.data || null
    if (loaded) {
      detailCard.value = loaded
      detailForm.title = loaded.title || ''
      detailForm.content = loaded.content || ''
      detailForm.category = loaded.category || ''
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

const onDetailClosed = () => {
  similarCards.value = []
  restoreDialogScroll()
}

const startDetailEdit = () => {
  detailEditing.value = true
}

const saveDetail = async () => {
  if (!detailCard.value || !detailForm.title.trim() || !detailForm.content.trim()) {
    ElMessage.warning('标题和正文不能为空')
    return
  }
  detailSaving.value = true
  try {
    const response = await updateExperienceCard(detailCard.value.id, {
      title: detailForm.title.trim(),
      content: detailForm.content.trim(),
      category: detailForm.category.trim() || null,
    })
    detailCard.value = response.data?.card || detailCard.value
    detailEditing.value = false
    ElMessage.success('待确认经验已更新')
    await loadCards()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验更新失败')
  } finally {
    detailSaving.value = false
  }
}

const confirmCard = async (card) => {
  detailSaving.value = true
  try {
    const response = await confirmExperienceCard(card.id)
    const confirmed = response.data?.card || null
    ElMessage.success('经验已确认并进入正式经验库')
    if (detailCard.value?.id === card.id) {
      detailCard.value = confirmed || { ...detailCard.value, status: 'confirmed' }
      detailEditing.value = false
    }
    filters.status = 'pending'
    await loadCards()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验确认失败')
  } finally {
    detailSaving.value = false
  }
}

const rejectCard = async (card) => {
  detailSaving.value = true
  try {
    await rejectExperienceCard(card.id)
    ElMessage.success('经验已退回')
    detailVisible.value = false
    await loadCards()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验退回失败')
  } finally {
    detailSaving.value = false
  }
}

const openSource = (card) => {
  router.push({ path: `/creation/${card.creation_id}/versions`, query: { before: card.version_pair.before || undefined, after: card.version_pair.after || undefined } })
}

const openReviewSource = (card) => {
  router.push({ path: '/article-reviews', query: { review_id: card.version_pair.review_id } })
}

const openMeetingSource = (card) => {
  if (card.source_meta?.meeting_id) router.push(`/meetings/${card.source_meta.meeting_id}`)
}

const loadSimilarCards = async (cardId) => {
  similarLoading.value = true
  similarCards.value = []
  try {
    const response = await getSimilarExperiences(cardId)
    similarCards.value = response.data?.items || []
  } catch (error) {
    similarCards.value = []
  } finally {
    similarLoading.value = false
  }
}

const scanOverlaps = async () => {
  overlapVisible.value = true
  overlapLoading.value = true
  overlapGroups.value = []
  try {
    const response = await scanExperienceOverlaps()
    overlapGroups.value = response.data?.groups || []
    if (!overlapGroups.value.length) ElMessage.info('没有发现明显重合的正式经验')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '重合扫描失败，请稍后重试')
  } finally {
    overlapLoading.value = false
  }
}

const openMergeDialog = async (sourceIds) => {
  const ids = [...new Set(sourceIds.filter(Boolean))]
  if (ids.length < 2) {
    ElMessage.warning('请至少选择两条经验再合并')
    return
  }
  mergeVisible.value = true
  mergeSources.value = []
  Object.assign(mergeForm, { title: '', content: '', category: '' })
  overlapVisible.value = false
  try {
    const responses = await Promise.all(ids.map((id) => getExperienceCard(id)))
    mergeSources.value = responses.map((res) => res.data?.card).filter(Boolean)
    if (!mergeSources.value.length) {
      ElMessage.error('经验加载失败')
      mergeVisible.value = false
      return
    }
    await generateMergePreview()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验加载失败')
    mergeVisible.value = false
  }
}

const generateMergePreview = async () => {
  if (!mergeSources.value.length || mergePreviewing.value) return
  mergePreviewing.value = true
  try {
    const response = await previewExperienceMerge(mergeSources.value.map((card) => card.id))
    const preview = response.data || {}
    mergeForm.title = preview.title || mergeForm.title
    mergeForm.content = preview.content || mergeForm.content
    mergeForm.category = preview.category || mergeForm.category
    if (!mergeForm.category) {
      const categories = mergeSources.value.map((card) => card.category).filter(Boolean)
      mergeForm.category = categories[0] || ''
    }
    ElMessage.success('已生成智能合并稿，请检查后确认')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '智能合并生成失败，可手动编辑')
    if (!mergeForm.title) mergeForm.title = mergeSources.value[0]?.title || ''
    if (!mergeForm.content) {
      mergeForm.content = mergeSources.value.map((card, i) => `【经验 ${i + 1}】${card.title}\n${card.content}`).join('\n\n---\n\n')
    }
  } finally {
    mergePreviewing.value = false
  }
}

const confirmMerge = async () => {
  if (!mergeForm.title.trim() || !mergeForm.content.trim()) {
    ElMessage.warning('标题和正文不能为空')
    return
  }
  mergeSaving.value = true
  try {
    await confirmExperienceMerge({
      source_ids: mergeSources.value.map((card) => card.id),
      title: mergeForm.title.trim(),
      content: mergeForm.content.trim(),
      category: mergeForm.category.trim() || null,
    })
    ElMessage.success('经验已合并，其余来源已标记为已合并')
    mergeVisible.value = false
    detailVisible.value = false
    pagination.page = 1
    await loadCards()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '合并失败，请稍后重试')
  } finally {
    mergeSaving.value = false
  }
}

const mergeWithSimilar = (card) => {
  if (!detailCard.value) return
  openMergeDialog([detailCard.value.id, card.id])
}

onMounted(loadCards)
</script>

<style scoped>
.experience-page { max-width: 1120px; margin: 0 auto; padding-bottom: 56px; color: var(--ink); }
.experience-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }.eyebrow { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .14em; }.experience-hero h1 { margin: 8px 0; font: 500 34px/1.3 var(--serif, serif); }.experience-hero p { max-width: 720px; margin: 0; color: var(--ink-3); font-size: 13px; line-height: 1.75; }
.library-tabs { display: flex; align-items: center; gap: 15px; margin-bottom: 13px; }.tab-note { color: var(--ink-3); font-size: 12px; line-height: 1.5; }.search-card { display: flex; gap: 10px; align-items: center; padding: 16px 18px; margin-bottom: 17px; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); }.search-input { max-width: 460px; }.category-select, .source-select { width: 170px; }.result-note { display: flex; gap: 18px; flex-wrap: wrap; margin: 0 2px 12px; color: var(--ink-3); font-size: 12px; }.card-list { min-height: 300px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px; padding: 0; background: transparent; }.experience-card { display: flex; min-height: 245px; flex-direction: column; padding: 20px; border: 1px solid #eadfcd; border-radius: var(--r-lg); background: #fffdf9; box-shadow: 0 8px 24px rgba(72,57,43,.05); cursor: pointer; transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease; }.experience-card:hover, .experience-card:focus-visible { border-color: var(--clay-soft); box-shadow: 0 12px 28px rgba(72,57,43,.1); outline: none; transform: translateY(-1px); }.card-head { display: flex; justify-content: space-between; gap: 12px; }.card-kicker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--ink-3); font-size: 11px; }.experience-card h2 { margin: 10px 0 0; font-size: 19px; line-height: 1.45; }.card-date { flex-shrink: 0; color: var(--ink-4); font-size: 11px; }.card-content { flex: 1; display: -webkit-box; overflow: hidden; margin: 15px 0 8px; color: var(--ink-2); font-size: 13px; line-height: 1.75; white-space: pre-wrap; -webkit-box-orient: vertical; -webkit-line-clamp: 7; }.source-context { overflow: hidden; color: var(--clay-deep); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.card-foot { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; padding-top: 12px; margin-top: 12px; border-top: 1px solid var(--line); color: var(--ink-3); font-size: 11px; }.similarity { color: var(--clay-deep); }.embedding-ready { color: var(--leaf-deep); }.embedding-failed { color: var(--crimson); }.embedding-pending { color: var(--clay-deep); }.embedding-waiting { color: var(--ink-3); }.source-locked { color: var(--ink-4); }.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 22px; }.upload-intro { display: flex; align-items: center; justify-content: space-between; gap: 15px; padding: 13px 15px; margin-bottom: 18px; border: 1px dashed var(--clay-soft); border-radius: var(--r-md); background: #fff9f0; }.upload-intro strong, .upload-intro span { display: block; }.upload-intro strong { color: var(--clay-deep); font-size: 13px; }.upload-intro span { margin-top: 4px; color: var(--ink-3); font-size: 12px; line-height: 1.5; }.upload-message { margin: -6px 0 16px; color: var(--leaf-deep); font-size: 12px; }.upload-message.is-error { color: var(--crimson); }.detail-dialog-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding-right: 16px; }.detail-dialog-head h2 { margin: 9px 0 0; color: var(--ink); font: 500 24px/1.4 var(--serif, serif); }.detail-loading { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 220px; color: var(--ink-3); }.detail-body { margin: 0; color: var(--ink); font-size: 15px; line-height: 1.9; white-space: pre-wrap; }.detail-source { display: flex; gap: 12px; margin-top: 20px; padding: 12px 14px; border-radius: var(--r-md); background: var(--ivory); color: var(--ink-2); font-size: 12px; line-height: 1.6; }.detail-source strong { flex: 0 0 auto; color: var(--clay-deep); }.detail-meta-row { display: flex; gap: 15px; flex-wrap: wrap; margin-top: 18px; color: var(--ink-3); font-size: 11px; }.detail-edit-form { padding: 2px 0 10px; }
.markdown-body { white-space: normal; }
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3), .markdown-body :deep(h4) { margin: 22px 0 9px; color: var(--ink); font-family: var(--serif, serif); line-height: 1.4; }
.markdown-body :deep(h1) { font-size: 24px; }
.markdown-body :deep(h2) { font-size: 21px; }
.markdown-body :deep(h3) { font-size: 18px; }
.markdown-body :deep(h4) { font-size: 16px; }
.markdown-body :deep(p) { margin: 0 0 13px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 0 0 14px; padding-left: 24px; }
.markdown-body :deep(li) { margin: 5px 0; }
.markdown-body :deep(blockquote) { padding: 8px 14px; margin: 14px 0; border-left: 3px solid var(--clay-soft); border-radius: 0 var(--r-sm) var(--r-sm) 0; background: #fff9f0; color: var(--ink-2); }
.markdown-body :deep(blockquote p) { margin-bottom: 0; }
.markdown-body :deep(strong) { color: var(--ink-2); font-weight: 750; }
.markdown-body :deep(em) { color: var(--clay-deep); }
.markdown-body :deep(code) { padding: 2px 5px; border-radius: 4px; background: #f4ede3; color: var(--crimson); font-family: var(--mono, monospace); font-size: .9em; }
.markdown-body :deep(pre) { overflow-x: auto; padding: 13px 15px; margin: 14px 0; border-radius: var(--r-md); background: #2e2a27; color: #fff8ef; line-height: 1.65; }
.markdown-body :deep(pre code) { padding: 0; background: transparent; color: inherit; }
.markdown-body :deep(a) { color: var(--clay-deep); text-decoration: underline; text-underline-offset: 3px; }
.markdown-body :deep(img) { display: block; max-width: 100%; height: auto; margin: 14px 0; border-radius: var(--r-md); }
.markdown-body :deep(hr) { margin: 18px 0; border: 0; border-top: 1px solid var(--line); }
.markdown-body :deep(table) { display: block; overflow-x: auto; width: 100%; margin: 14px 0; border-collapse: collapse; }
.markdown-body :deep(th), .markdown-body :deep(td) { min-width: 100px; padding: 8px 10px; border: 1px solid var(--line); text-align: left; vertical-align: top; }
.markdown-body :deep(th) { background: #fff9f0; color: var(--ink-2); }
.hero-actions { display: flex; gap: 10px; flex-shrink: 0; }
.similar-section { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--line); }
.similar-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }.similar-head strong { font-size: 14px; }.similar-head span { color: var(--ink-4); font-size: 11px; }
.similar-loading { display: flex; align-items: center; gap: 8px; padding: 12px; color: var(--ink-3); font-size: 12px; }
.similar-list { display: flex; flex-direction: column; gap: 8px; }
.similar-item { display: flex; align-items: flex-start; gap: 10px; padding: 11px 12px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #fffdf9; }
.similar-item-main { min-width: 0; flex: 1; }.similar-item-main strong { display: block; font-size: 13px; }.similar-item-main p { display: -webkit-box; overflow: hidden; margin: 5px 0 0; color: var(--ink-3); font-size: 11px; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.similarity-tag { display: inline-block; margin-left: 8px; padding: 1px 7px; border-radius: 999px; background: var(--clay-tint); color: var(--clay-deep); font-size: 10px; vertical-align: middle; }
.overlap-body { min-height: 220px; max-height: 62vh; overflow-y: auto; padding-right: 4px; }
.overlap-hint { margin: 0 0 16px; color: var(--ink-3); font-size: 12px; line-height: 1.7; }
.overlap-group { padding: 14px; margin-bottom: 14px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #fffdf9; }
.overlap-group-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }.overlap-group-head strong { font-size: 14px; }
.overlap-card-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 9px; }
.overlap-card { padding: 11px; border: 1px dashed #e3d5c2; border-radius: 8px; background: #fff; }.overlap-card strong { display: block; font-size: 13px; }.overlap-card span { display: block; margin-top: 3px; color: var(--ink-4); font-size: 10px; }.overlap-card p { display: -webkit-box; overflow: hidden; margin: 7px 0 0; color: var(--ink-3); font-size: 11px; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.merge-hint { margin: 0 0 16px; color: var(--ink-3); font-size: 12px; line-height: 1.7; }
.merge-sources { display: flex; flex-direction: column; gap: 10px; max-height: 260px; overflow-y: auto; margin-bottom: 4px; }
.merge-source { display: flex; gap: 10px; padding: 10px 12px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #fffdf9; }
.merge-source-index { display: grid; place-items: center; flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: var(--clay); color: #fff; font-size: 11px; font-weight: 700; }
.merge-source-body { min-width: 0; }.merge-source-body strong { display: block; font-size: 13px; }.merge-source-body span { display: block; margin-top: 2px; color: var(--ink-4); font-size: 10px; }.merge-source-body p { display: -webkit-box; overflow: hidden; margin: 6px 0 0; color: var(--ink-3); font-size: 11px; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.merge-loading { display: flex; flex-direction: column; align-items: center; gap: 12px; min-height: 260px; justify-content: center; color: var(--ink-3); font-size: 13px; }
@media (max-width: 800px) { .experience-hero, .library-tabs, .search-card { align-items: stretch; flex-direction: column; }.search-input, .category-select, .source-select { width: 100%; max-width: none; }.card-list { grid-template-columns: 1fr; }.upload-intro { align-items: stretch; flex-direction: column; }.tab-note { max-width: 100%; } .hero-actions { width: 100%; }.hero-actions .el-button { flex: 1; } }
</style>
