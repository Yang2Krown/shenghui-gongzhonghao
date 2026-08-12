<template>
  <div class="experience-page">
    <header class="experience-hero">
      <div>
        <div class="eyebrow">TEAM MEMORY · PHASE 1C</div>
        <h1>经验库</h1>
        <p>把真实的文章修改、会议建议和复盘反馈留成可检索的经验。来源版本始终保留，语义检索不可用时自动降级为关键词匹配。</p>
      </div>
      <el-button type="primary" size="large" @click="openCreateDialog">
        <el-icon><Plus /></el-icon> 新增经验
      </el-button>
    </header>

    <section class="search-card">
      <el-input v-model="filters.q" clearable class="search-input" placeholder="搜索经验标题、正文或分类" @keyup.enter="loadCards">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filters.category" clearable filterable allow-create placeholder="分类" class="category-select" @change="loadCards">
        <el-option v-for="category in categories" :key="category" :label="category" :value="category" />
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
      <article v-for="card in cards" :key="card.id" class="experience-card">
        <div class="card-head">
          <div>
            <div class="card-kicker"><el-tag size="small" effect="plain">{{ sourceTypeLabel(card.source_type) }}</el-tag><span v-if="card.category">{{ card.category }}</span><span v-if="card.match_method && searchMode !== 'recent'">{{ matchMethodLabel(card.match_method) }}</span></div>
            <h2>{{ card.title }}</h2>
          </div>
          <span class="card-date">{{ formatDate(card.created_at) }}</span>
        </div>
        <p class="card-content">{{ card.content }}</p>
        <div class="card-foot">
          <span class="creator">{{ card.created_by_user?.full_name || card.created_by_user?.username || '团队成员' }}</span>
          <span v-if="card.similarity !== null && card.similarity !== undefined" class="similarity">相似度 {{ Math.round(card.similarity * 100) }}%</span>
          <span class="embedding-state" :class="`embedding-${card.embedding_status}`">{{ embeddingStatusLabel(card.embedding_status) }}</span>
          <el-button v-if="card.source_type === 'review_feedback' && card.version_pair?.review_id" text type="primary" size="small" @click="openReviewSource(card)">查看文章复盘 <el-icon><ArrowRight /></el-icon></el-button>
          <el-button v-else-if="card.creation_id && card.version_pair && card.source_accessible" text type="primary" size="small" @click="openSource(card)">查看来源版本 <el-icon><ArrowRight /></el-icon></el-button>
          <span v-else-if="card.creation_id && card.version_pair" class="source-locked">来源文章当前不可访问</span>
        </div>
      </article>
      <el-empty v-if="!loading && !cards.length" :image-size="70" description="还没有匹配的经验，先新增一条或上传一份 PDF/Word 吧" />
    </section>

    <div class="pagination-wrap">
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" layout="total, prev, pager, next" :total="total" @current-change="loadCards" />
    </div>

    <el-dialog v-model="createVisible" title="新增经验" width="700px" align-center destroy-on-close>
      <div class="upload-intro">
        <div><strong>支持上传 PDF / Word</strong><span>文件只用于解析文字，解析后先填入下面表单，确认后才会保存经验卡片。</span></div>
        <input ref="fileInput" type="file" accept=".pdf,.docx,.txt,.md,.markdown" hidden @change="handleFileChange">
        <el-button plain :loading="uploading" @click="fileInput?.click()"><el-icon><Upload /></el-icon> 上传并解析</el-button>
      </div>
      <div v-if="uploadMessage" class="upload-message" :class="{ 'is-error': uploadFailed }">{{ uploadMessage }}</div>
      <el-form :model="form" label-position="top">
        <el-form-item label="经验标题" required><el-input v-model="form.title" maxlength="200" show-word-limit placeholder="例如：开头要让读者先看见具体冲突" /></el-form-item>
        <el-form-item label="经验正文" required><el-input v-model="form.content" type="textarea" :rows="12" maxlength="50000" show-word-limit placeholder="写下可复用的判断、做法和依据；也可以先上传文件解析" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="form.category" maxlength="50" placeholder="例如：开头、结构、案例、表达" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveCard">保存经验</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Plus, Search, Upload } from '@element-plus/icons-vue'
import { createExperienceCard, listExperienceCards, parseExperienceUpload } from '@/api/experience'

const router = useRouter()
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
const filters = reactive({ q: '', category: '' })
const pagination = reactive({ page: 1, pageSize: 12 })
const form = reactive({ title: '', content: '', category: '' })

const sourceTypeLabel = (value) => ({ meeting_diff: '文章版本', review_feedback: '文章复盘', manual: '手动新增' }[value] || value || '经验')
const matchMethodLabel = (value) => ({ semantic: '语义命中', 'semantic+keyword': '语义 + 关键词', keyword_fallback: '关键词降级' }[value] || value)
const embeddingStatusLabel = (value) => ({ pending: 'Embedding 生成中', ready: '已向量化', failed: 'Embedding 不可用' }[value] || '待处理')
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16) : '—'

const loadCards = async () => {
  loading.value = true
  try {
    const response = await listExperienceCards({ q: filters.q || undefined, category: filters.category || undefined, page: pagination.page, page_size: pagination.pageSize })
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

const resetFilters = () => {
  filters.q = ''
  filters.category = ''
  pagination.page = 1
  loadCards()
}

const openCreateDialog = () => {
  Object.assign(form, { title: '', content: '', category: '' })
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
    await createExperienceCard({ title: form.title.trim(), content: form.content.trim(), category: form.category.trim() || null, source_type: 'manual' })
    ElMessage.success('经验卡片已保存，Embedding 将在后台生成')
    createVisible.value = false
    pagination.page = 1
    await loadCards()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '经验保存失败')
  } finally {
    saving.value = false
  }
}

const openSource = (card) => {
  router.push({ path: `/creation/${card.creation_id}/versions`, query: { before: card.version_pair.before || undefined, after: card.version_pair.after || undefined } })
}

const openReviewSource = (card) => {
  router.push({ path: '/article-reviews', query: { review_id: card.version_pair.review_id } })
}

onMounted(loadCards)
</script>

<style scoped>
.experience-page { max-width: 1120px; margin: 0 auto; padding-bottom: 56px; color: var(--ink); }
.experience-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }.eyebrow { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .14em; }.experience-hero h1 { margin: 8px 0; font: 500 34px/1.3 var(--serif, serif); }.experience-hero p { max-width: 720px; margin: 0; color: var(--ink-3); font-size: 13px; line-height: 1.75; }
.search-card { display: flex; gap: 10px; align-items: center; padding: 16px 18px; margin-bottom: 17px; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); }.search-input { max-width: 560px; }.category-select { width: 180px; }.result-note { display: flex; gap: 18px; flex-wrap: wrap; margin: 0 2px 12px; color: var(--ink-3); font-size: 12px; }.card-list { min-height: 300px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px; padding: 0; background: transparent; }.experience-card { display: flex; min-height: 245px; flex-direction: column; padding: 20px; border: 1px solid #eadfcd; border-radius: var(--r-lg); background: #fffdf9; box-shadow: 0 8px 24px rgba(72,57,43,.05); }.card-head { display: flex; justify-content: space-between; gap: 12px; }.card-kicker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--ink-3); font-size: 11px; }.experience-card h2 { margin: 10px 0 0; font-size: 19px; line-height: 1.45; }.card-date { flex-shrink: 0; color: var(--ink-4); font-size: 11px; }.card-content { flex: 1; display: -webkit-box; overflow: hidden; margin: 15px 0; color: var(--ink-2); font-size: 13px; line-height: 1.75; white-space: pre-wrap; -webkit-box-orient: vertical; -webkit-line-clamp: 7; }.card-foot { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; padding-top: 12px; border-top: 1px solid var(--line); color: var(--ink-3); font-size: 11px; }.similarity { color: var(--clay-deep); }.embedding-ready { color: var(--leaf-deep); }.embedding-failed { color: var(--crimson); }.embedding-pending { color: var(--clay-deep); }.source-locked { color: var(--ink-4); }.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 22px; }.upload-intro { display: flex; align-items: center; justify-content: space-between; gap: 15px; padding: 13px 15px; margin-bottom: 18px; border: 1px dashed var(--clay-soft); border-radius: var(--r-md); background: #fff9f0; }.upload-intro strong, .upload-intro span { display: block; }.upload-intro strong { color: var(--clay-deep); font-size: 13px; }.upload-intro span { margin-top: 4px; color: var(--ink-3); font-size: 12px; line-height: 1.5; }.upload-message { margin: -6px 0 16px; color: var(--leaf-deep); font-size: 12px; }.upload-message.is-error { color: var(--crimson); }
@media (max-width: 800px) { .experience-hero, .search-card { align-items: stretch; flex-direction: column; }.search-input, .category-select { width: 100%; max-width: none; }.card-list { grid-template-columns: 1fr; }.upload-intro { align-items: stretch; flex-direction: column; } }
</style>
