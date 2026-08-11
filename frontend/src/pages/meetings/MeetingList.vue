<template>
  <div class="meetings-page">
    <header class="meeting-hero">
      <div>
        <div class="kicker">MEETING KNOWLEDGE · PHASE 1B</div>
        <h1>会议方法论</h1>
        <p>把会议纪要沉淀为动笔前可以直接使用的判断规则和对齐清单。</p>
      </div>
      <el-button type="primary" size="large" @click="createVisible = true">
        <el-icon><Plus /></el-icon> 新建会议
      </el-button>
    </header>

    <section class="filter-card">
      <el-input
        v-model="filters.keyword"
        clearable
        placeholder="搜索会议主题或纪要"
        class="keyword-input"
        @keyup.enter="refresh"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filters.status" clearable placeholder="整理状态" class="status-select">
        <el-option label="整理中" value="extracting" />
        <el-option label="已完成" value="ready" />
        <el-option label="整理失败" value="failed" />
      </el-select>
      <el-date-picker
        v-model="filters.dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        class="date-range"
      />
      <el-button type="primary" @click="refresh">筛选</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </section>

    <section class="card meeting-list-card">
      <div class="section-head">
        <div>
          <h2>会议记录</h2>
          <span class="muted">选择一场会议，查看它沉淀出的写作方法</span>
        </div>
        <el-button text :loading="loading" @click="refresh">刷新</el-button>
      </div>

      <el-table :data="meetings" v-loading="loading" class="meeting-table" @row-click="openMeeting">
        <el-table-column label="会议" min-width="280">
          <template #default="{ row }">
            <div class="meeting-title-cell">
              <strong>{{ row.title }}</strong>
              <span>{{ formatDate(row.meeting_at) }} · {{ row.created_by_user?.full_name || row.created_by_user?.username || '团队成员' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="整理状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="meetingStatusType(row.status)">{{ meetingStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="沉淀摘要" min-width="420">
          <template #default="{ row }">
            <p v-if="row.synthesis_summary" class="summary-preview">{{ shorten(row.synthesis_summary) }}</p>
            <span v-else class="empty-preview">整理完成后显示方法论摘要</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click.stop="openMeeting(row)">查看沉淀 <el-icon><ArrowRight /></el-icon></el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !meetings.length" description="还没有会议记录，先粘贴一份纪要吧" />
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          layout="total, prev, pager, next"
          :total="pagination.total"
          @current-change="loadMeetings"
        />
      </div>
    </section>

    <section class="card knowledge-summary-card">
      <div class="summary-section-head">
        <div>
          <div class="kicker">METHOD INDEX</div>
          <h2>方法论汇总</h2>
          <p>相似原则会合并成一条主方法，同时保留每次会议的来源，点击分类即可查阅。</p>
        </div>
        <div class="summary-counts">
          <strong>{{ summary.total_items || 0 }}</strong>
          <span>条沉淀</span>
          <small>{{ summary.total_methodology || 0 }} 条主规则 · {{ summary.total_checklist || 0 }} 条主清单</small>
        </div>
      </div>
      <div v-if="summary.categories?.length" class="category-grid">
        <button v-for="(category, index) in summary.categories" :key="category.key" type="button" class="category-card" @click="openCategory(category)">
          <div class="category-card-top">
            <span class="category-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="category-count">{{ category.item_count }} 条沉淀</span>
          </div>
          <h3>{{ category.title }}</h3>
          <p>{{ category.description }}</p>
          <div class="category-preview">
            <span v-for="title in category.preview_titles" :key="title">{{ title }}</span>
          </div>
          <span class="category-link">进入分类查阅 <el-icon><ArrowRight /></el-icon></span>
        </button>
      </div>
      <el-empty v-else :image-size="56" description="整理完成后，这里会出现方法论分类" />
    </section>

    <teleport to="body">
      <transition name="category-modal">
        <div v-if="categoryVisible && selectedCategory" class="category-modal-mask" @click.self="closeCategory">
          <section
            class="category-modal-card"
            role="dialog"
            aria-modal="true"
            tabindex="-1"
            :aria-label="`${selectedCategory.title}分类详情`"
            @keydown.esc="closeCategory"
          >
            <header class="category-modal-head">
              <div>
                <span class="category-modal-kicker">分类查阅</span>
                <h2>{{ selectedCategory.title }}</h2>
                <p>{{ selectedCategory.description }}</p>
              </div>
              <button type="button" class="category-modal-close" aria-label="关闭" @click="closeCategory">×</button>
            </header>
            <div class="category-modal-meta">
              <span>{{ selectedCategory.item_count }} 条沉淀</span>
              <span>来自 {{ selectedCategory.meeting_count }} 场会议</span>
            </div>
            <div class="category-modal-body">
              <div class="category-detail-list">
                <article v-for="(item, index) in selectedCategory.items" :key="`${item.meeting_id}-${item.type}-${index}`" class="category-detail-card">
                  <div class="detail-card-meta">
                    <span>{{ item.type === 'methodology' ? '方法论' : '对齐清单' }}</span>
                    <small>{{ item.source_count > 1 ? `${item.source_count} 次提到 · ${item.meeting_count} 场会议` : item.meeting_title }}</small>
                  </div>
                  <h3>{{ item.title }}</h3>
                  <p class="detail-rule">{{ item.rule }}</p>
                  <div class="detail-fields">
                    <div v-if="item.rationale"><strong>为什么</strong><p>{{ item.rationale }}</p></div>
                    <div v-if="item.example"><strong>例子 / 场景</strong><p>{{ item.example }}</p></div>
                    <div v-if="item.when_to_use"><strong>使用时机</strong><p>{{ item.when_to_use }}</p></div>
                    <div v-if="item.evidence"><strong>会议依据</strong><p>{{ item.evidence }}</p></div>
                  </div>
                  <div v-if="item.source_count > 1 && item.sources?.length" class="detail-sources">
                    <strong>出现于</strong>
                    <button v-for="source in item.sources" :key="`${source.meeting_id}-${source.meeting_at}`" type="button" @click.stop="openMeetingById(source.meeting_id)">
                      <span>{{ source.meeting_title }}</span>
                      <small>{{ formatDate(source.meeting_at) }}</small>
                    </button>
                  </div>
                  <button type="button" class="source-link" @click="openMeetingById(item.meeting_id)">查看完整会议 →</button>
                </article>
              </div>
            </div>
          </section>
        </div>
      </transition>
    </teleport>

    <el-dialog v-model="createVisible" title="新建会议" width="620px" align-center destroy-on-close>
      <el-form :model="form" label-position="top">
        <el-form-item label="会议主题" required>
          <el-input v-model="form.title" maxlength="200" show-word-limit placeholder="例如：内容组周会 · Seedance 2.5 评测复盘" />
        </el-form-item>
        <el-form-item label="会议时间" required>
          <el-date-picker v-model="form.meeting_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="会议纪要全文" required>
          <el-input
            v-model="form.raw_text"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 24 }"
            maxlength="200000"
            show-word-limit
            placeholder="粘贴完整会议纪要。系统会整理出可复用的方法论和动笔前对齐清单。"
          />
        </el-form-item>
      </el-form>
      <div class="dialog-tip">创建后后台整理，不会阻塞页面；完成后可以人工修订方法论和对齐清单。</div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建并整理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Plus, Search } from '@element-plus/icons-vue'
import { createMeeting, getMeetingSummary, listMeetings } from '@/api/meetings'
import { meetingStatusLabel, meetingStatusType } from './meetingUi'

const router = useRouter()
const meetings = ref([])
const loading = ref(false)
const creating = ref(false)
const createVisible = ref(false)
const filters = reactive({ keyword: '', status: '', dateRange: [] })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const summary = ref({ total_items: 0, total_methodology: 0, total_checklist: 0, categories: [] })
const categoryVisible = ref(false)
const selectedCategory = ref(null)
const categoryScrollY = ref(0)
let categoryPreviousOverflow = ''
let categoryPreviousPaddingRight = ''
let categoryPreviousBodyOverflow = ''
let categoryPreviousBodyPaddingRight = ''
let refreshTimer = null

const form = reactive({ title: '', meeting_at: '', raw_text: '' })

const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }).slice(0, 16) : '—'
const shorten = (value) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  return text.length > 96 ? `${text.slice(0, 96)}…` : text
}

const listParams = () => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize,
    keyword: filters.keyword.trim() || undefined,
    status: filters.status || undefined,
  }
  if (filters.dateRange?.length === 2) {
    params.start_at = `${filters.dateRange[0]}T00:00:00`
    params.end_at = `${filters.dateRange[1]}T23:59:59`
  }
  return params
}

const loadMeetings = async () => {
  loading.value = true
  try {
    const response = await listMeetings(listParams())
    const data = response.data || {}
    meetings.value = data.items || []
    pagination.total = data.total || 0
  } catch {
    ElMessage.error('加载会议列表失败')
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    const response = await getMeetingSummary()
    summary.value = response.data || summary.value
  } catch {
    // 汇总失败不阻塞会议列表。
  }
}

const refresh = async () => {
  pagination.page = 1
  await Promise.all([loadMeetings(), loadSummary()])
}

const resetFilters = () => {
  filters.keyword = ''
  filters.status = ''
  filters.dateRange = []
  refresh()
}

const openMeeting = (row) => router.push(`/meetings/${row.id}`)
const openMeetingById = (meetingId) => {
  closeCategory()
  router.push(`/meetings/${meetingId}`)
}
const openCategory = (category) => {
  selectedCategory.value = category
  categoryVisible.value = true
}
const currentScrollY = () => window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0
const restoreCategoryScroll = () => {
  const scrollY = categoryScrollY.value
  window.requestAnimationFrame(() => {
    window.scrollTo({ left: 0, top: scrollY, behavior: 'auto' })
    document.documentElement.scrollTop = scrollY
    document.body.scrollTop = scrollY
  })
}
const lockCategoryScroll = () => {
  const docEl = document.documentElement
  const body = document.body
  categoryScrollY.value = currentScrollY()
  categoryPreviousOverflow = docEl.style.overflow
  categoryPreviousPaddingRight = docEl.style.paddingRight
  categoryPreviousBodyOverflow = body.style.overflow
  categoryPreviousBodyPaddingRight = body.style.paddingRight
  const scrollbarWidth = window.innerWidth - docEl.clientWidth
  if (scrollbarWidth > 0) docEl.style.paddingRight = `${scrollbarWidth}px`
  docEl.style.overflow = 'hidden'
  body.style.overflow = 'hidden'
  restoreCategoryScroll()
}
const unlockCategoryScroll = () => {
  const docEl = document.documentElement
  const body = document.body
  docEl.style.overflow = categoryPreviousOverflow
  docEl.style.paddingRight = categoryPreviousPaddingRight
  body.style.overflow = categoryPreviousBodyOverflow
  body.style.paddingRight = categoryPreviousBodyPaddingRight
  restoreCategoryScroll()
}
const closeCategory = () => {
  categoryVisible.value = false
}
watch(categoryVisible, (visible) => {
  if (visible) lockCategoryScroll()
  else unlockCategoryScroll()
})

const resetForm = () => {
  form.title = ''
  form.raw_text = ''
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  form.meeting_at = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:00`
}

const submitCreate = async () => {
  if (!form.title.trim() || !form.meeting_at || !form.raw_text.trim()) {
    ElMessage.warning('请填写会议主题、时间和纪要全文')
    return
  }
  creating.value = true
  try {
    const response = await createMeeting({ ...form, title: form.title.trim(), raw_text: form.raw_text.trim() })
    const meeting = response.data?.meeting
    createVisible.value = false
    resetForm()
    ElMessage.success('会议已创建，正在整理方法论')
    await loadMeetings()
    if (meeting?.id) router.push(`/meetings/${meeting.id}`)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  resetForm()
  refresh()
  refreshTimer = window.setInterval(() => {
    if (!document.hidden && meetings.value.some(item => item.status === 'extracting')) {
      loadMeetings()
      loadSummary()
    }
  }, 5000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (categoryVisible.value) unlockCategoryScroll()
})
</script>

<style scoped>
.meetings-page { max-width: 1240px; margin: 0 auto; color: var(--ink); }
.meeting-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.kicker { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .14em; }
.meeting-hero h1 { margin: 6px 0 7px; font: 500 32px/1.2 var(--serif, serif); }
.meeting-hero p { margin: 0; color: var(--ink-3); font-size: 14px; }
.filter-card { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 14px; margin-bottom: 16px; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--bone); }
.keyword-input { max-width: 320px; }
.status-select { width: 150px; }
.date-range { width: 270px; }
.card { border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); }
.meeting-list-card { padding: 20px; }
.knowledge-summary-card { margin-top: 18px; padding: 24px; background: #fffdf9; }
.summary-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.summary-section-head h2 { margin: 6px 0 5px; font-size: 22px; }
.summary-section-head p { margin: 0; color: var(--ink-3); font-size: 13px; line-height: 1.6; }
.summary-counts { display: grid; grid-template-columns: auto auto; align-items: baseline; column-gap: 7px; min-width: 145px; padding: 12px 15px; border: 1px solid #eadfcd; border-radius: var(--r-md); background: #f8f1e5; }
.summary-counts strong { color: var(--clay-deep); font-size: 27px; line-height: 1; }
.summary-counts span { color: var(--ink-2); font-size: 12px; }
.summary-counts small { grid-column: 1 / -1; margin-top: 6px; color: var(--ink-3); font-size: 11px; }
.category-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.category-card { display: flex; min-height: 218px; flex-direction: column; align-items: flex-start; padding: 18px; border: 1px solid #e8ddca; border-radius: var(--r-md); background: #f8f3eb; color: var(--ink); text-align: left; cursor: pointer; transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease; }
.category-card:hover { border-color: var(--clay); box-shadow: 0 8px 20px rgba(83, 61, 42, .09); transform: translateY(-2px); }
.category-card-top { display: flex; width: 100%; align-items: center; justify-content: space-between; }
.category-index { color: var(--clay-deep); font-size: 13px; font-weight: 700; }
.category-count { color: var(--ink-3); font-size: 11px; }
.category-card h3 { margin: 20px 0 7px; font-size: 17px; }
.category-card > p { min-height: 42px; margin: 0; color: var(--ink-2); font-size: 12px; line-height: 1.65; }
.category-preview { display: flex; flex-direction: column; gap: 3px; margin-top: 13px; color: var(--ink-3); font-size: 11px; line-height: 1.5; }
.category-preview span { overflow: hidden; max-width: 100%; text-overflow: ellipsis; white-space: nowrap; }
.category-preview span::before { margin-right: 5px; color: var(--clay); content: '·'; }
.category-link { display: inline-flex; align-items: center; gap: 3px; margin-top: auto; padding-top: 14px; color: var(--clay-deep); font-size: 12px; font-weight: 600; }
.category-modal-mask { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 24px; background: rgba(31, 31, 30, .45); backdrop-filter: blur(3px); }
.category-modal-card { position: relative; display: flex; width: min(900px, 100%); max-height: min(760px, 88vh); flex-direction: column; overflow: hidden; border: 1px solid var(--line); border-radius: 16px; background: var(--paper); box-shadow: 0 24px 80px rgba(31, 31, 30, .28); outline: none; }
.category-modal-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 22px; padding: 26px 30px 18px; border-bottom: 1px solid var(--line); }
.category-modal-kicker { color: var(--clay-deep); font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.category-modal-head h2 { margin: 7px 0 6px; font: 500 27px/1.25 var(--serif, serif); }
.category-modal-head p { max-width: 660px; margin: 0; color: var(--ink-3); font-size: 13px; line-height: 1.65; }
.category-modal-close { flex: 0 0 auto; width: 32px; height: 32px; border: 0; border-radius: 50%; background: var(--bone); color: var(--ink-2); font-size: 20px; line-height: 1; cursor: pointer; transition: background .18s ease, color .18s ease; }
.category-modal-close:hover { background: var(--clay-tint); color: var(--clay-deep); }
.category-modal-meta { display: flex; gap: 18px; padding: 12px 30px; border-bottom: 1px solid #eee5d8; background: #f8f1e5; color: var(--ink-3); font-size: 12px; }
.category-modal-meta span + span { position: relative; padding-left: 18px; }
.category-modal-meta span + span::before { position: absolute; left: 0; color: var(--clay); content: '·'; }
.category-modal-body { min-height: 0; overflow-y: auto; padding: 22px 30px 30px; }
.category-detail-list { display: flex; flex-direction: column; gap: 13px; }
.category-detail-card { padding: 17px 18px; border: 1px solid #e8ddca; border-radius: var(--r-md); background: #fffdf9; }
.detail-card-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 9px; }
.detail-card-meta span { color: var(--clay-deep); font-size: 11px; font-weight: 700; }
.detail-card-meta small { overflow: hidden; color: var(--ink-3); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.category-detail-card h3 { margin: 0 0 8px; font-size: 16px; line-height: 1.5; }
.detail-rule { margin: 0; color: var(--ink); font-size: 14px; line-height: 1.75; }
.detail-fields { display: grid; gap: 9px; margin-top: 14px; }
.detail-fields > div { padding: 9px 11px; border-radius: var(--r-sm); background: #f8f3eb; }
.detail-fields strong { display: block; margin-bottom: 3px; color: var(--clay-deep); font-size: 11px; }
.detail-fields p { margin: 0; color: var(--ink-2); font-size: 12px; line-height: 1.65; }
.detail-sources { display: grid; gap: 7px; margin-top: 14px; padding-top: 13px; border-top: 1px solid #eee5d8; }
.detail-sources > strong { color: var(--clay-deep); font-size: 11px; }
.detail-sources button { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 10px; border: 1px solid #eadfcd; border-radius: var(--r-sm); background: #f8f3eb; color: var(--ink-2); text-align: left; cursor: pointer; transition: border-color .18s ease, background .18s ease; }
.detail-sources button:hover { border-color: var(--clay); background: var(--clay-tint); }
.detail-sources button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail-sources button small { flex: 0 0 auto; color: var(--ink-3); font-size: 11px; }
.source-link { display: inline-flex; padding: 12px 0 0; border: 0; background: transparent; color: var(--clay-deep); font-size: 12px; cursor: pointer; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-head h2 { margin: 0 0 5px; font-size: 18px; }
.muted { color: var(--ink-3); font-size: 12px; }
.meeting-title-cell { display: flex; flex-direction: column; gap: 5px; cursor: pointer; }
.meeting-title-cell strong { color: var(--ink); font-size: 14px; }
.meeting-title-cell span { color: var(--ink-3); font-size: 12px; }
.summary-preview { margin: 6px 0 0; color: var(--ink-3); font-size: 12px; line-height: 1.5; }
.empty-preview { display: inline-block; margin-top: 5px; color: var(--ink-4); font-size: 12px; }
.pagination-wrap { display: flex; justify-content: flex-end; padding-top: 18px; }
.dialog-tip { padding: 10px 12px; border-radius: var(--r-sm); background: var(--clay-tint); color: var(--ink-3); font-size: 12px; line-height: 1.6; }
.category-modal-enter-active, .category-modal-leave-active { transition: opacity .2s ease; }
.category-modal-enter-active .category-modal-card, .category-modal-leave-active .category-modal-card { transition: transform .22s ease, opacity .2s ease; }
.category-modal-enter-from, .category-modal-leave-to { opacity: 0; }
.category-modal-enter-from .category-modal-card, .category-modal-leave-to .category-modal-card { opacity: 0; transform: translateY(12px) scale(.985); }
@media (max-width: 900px) { .category-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 620px) {
  .meeting-hero { align-items: flex-start; flex-direction: column; }
  .keyword-input, .status-select, .date-range { max-width: none; width: 100%; }
  .filter-card .el-button { flex: 1; }
  .summary-section-head { flex-direction: column; }
  .summary-counts { width: 100%; }
  .category-grid { grid-template-columns: 1fr; }
  .category-modal-mask { padding: 12px; }
  .category-modal-card { max-height: calc(100vh - 24px); }
  .category-modal-head { gap: 12px; padding: 22px 20px 15px; }
  .category-modal-head h2 { font-size: 23px; }
  .category-modal-meta { padding: 11px 20px; }
  .category-modal-body { padding: 16px 20px 20px; }
}
</style>
