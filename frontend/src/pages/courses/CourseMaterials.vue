<template>
  <div class="cm-page">
    <!-- Mobile topbar -->
    <div class="cm-topbar">
      <button class="cm-menu-btn" @click="sidebarOpen = !sidebarOpen">目录</button>
      <span class="cm-topbar-title">{{ displayData?.title || '加载中…' }}</span>
    </div>

    <div class="cm-layout">
      <!-- Sidebar: chapter list -->
      <aside class="cm-sidebar" :class="{ open: sidebarOpen }">
        <div class="cm-brand">
          <div class="cm-brand-title">AI垂类公众号实战营</div>
          <div class="cm-brand-sub">从选题到商业变现 · 完整讲义</div>
        </div>
        <nav class="cm-nav">
          <a
            v-for="(ch, idx) in chapters"
            :key="ch.id"
            class="cm-nav-item"
            :class="{ active: ch.id === currentId }"
            @click="selectChapter(ch)"
          >
            <span class="cm-nav-num">{{ String(idx).padStart(2, '0') }}</span>
            <span class="cm-nav-text">
              <span class="cm-nav-name">{{ getNavName(ch, idx) }}</span>
              <span class="cm-nav-sub">{{ getNavSub(ch, idx) }}</span>
            </span>
            <span v-if="isAdmin && !isPreviewing && !editPreviewData" class="cm-nav-actions" @click.stop>
              <button class="cm-nav-btn" title="上移" :disabled="idx === 0" @click="moveChapter(ch, -1)">↑</button>
              <button class="cm-nav-btn" title="下移" :disabled="idx === chapters.length - 1" @click="moveChapter(ch, 1)">↓</button>
              <button class="cm-nav-btn cm-nav-del" title="删除" @click="confirmDelete(ch)">×</button>
            </span>
          </a>
        </nav>
        <button v-if="isAdmin && !isPreviewing && !editPreviewData" class="cm-add-btn" @click="openCreateDrawer">+ 新增章节</button>
      </aside>

      <!-- Main content -->
      <div class="cm-main">
        <div v-if="loading" class="cm-loading">加载中…</div>
        <div v-else-if="!displayData" class="cm-empty">请从左侧选择一个章节</div>
        <article v-else class="cm-content">
          <!-- 编辑预览指示条 -->
          <div v-if="editPreviewData" class="cm-preview-banner">
            <span class="cm-preview-tag">编辑预览</span>
            <span class="cm-preview-hint">以下是编辑后未保存的效果</span>
          </div>
          <div class="cm-ch-head">
            <div class="cm-ch-kicker">{{ displayData.kicker }}</div>
            <h1>{{ displayData.title }}</h1>
            <div class="cm-ch-actions">
              <!-- 编辑预览：取消 + 确认更新 -->
              <template v-if="editPreviewData">
                <button class="cm-edit-btn" @click="cancelPreview">取消</button>
                <button class="cm-edit-btn cm-btn-confirm" :disabled="saving" @click="confirmUpdate">
                  {{ saving ? '保存中…' : '确认更新' }}
                </button>
              </template>
              <!-- 正常状态：预览切换 + 编辑 -->
              <template v-else>
                <button v-if="isAdmin" class="cm-edit-btn" @click="isPreviewing = !isPreviewing">
                  {{ isPreviewing ? '退出预览' : '预览' }}
                </button>
                <button v-if="isAdmin && !isPreviewing" class="cm-edit-btn" @click="openEditDrawer">编辑此章</button>
              </template>
            </div>
          </div>
          <div class="cm-prose" v-html="displayData.content_html"></div>

          <!-- Prev / Next（编辑预览时隐藏） -->
          <div v-if="!editPreviewData" class="cm-pager">
            <button class="cm-pager-btn" :disabled="!prevChapter" @click="selectChapter(prevChapter)">
              <span v-if="prevChapter">← {{ prevChapter.title }}</span>
            </button>
            <button class="cm-pager-btn next" :disabled="!nextChapter" @click="selectChapter(nextChapter)">
              <span v-if="nextChapter">{{ nextChapter.title }} →</span>
            </button>
          </div>
        </article>
      </div>
    </div>

    <!-- Scrim for mobile sidebar -->
    <div class="cm-scrim" :class="{ show: sidebarOpen }" @click="sidebarOpen = false"></div>

    <!-- Edit / Create Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="editingChapter ? '编辑章节' : '新增章节'"
      size="55%"
      :destroy-on-close="true"
      @closed="onDrawerClosed"
    >
      <div class="cm-edit-form">
        <div class="cm-form-row">
          <label class="cm-form-label">章节标签</label>
          <el-input v-model="form.kicker" placeholder="如：第 1 章 / 附录 / 课程总览" />
        </div>
        <div class="cm-form-row">
          <label class="cm-form-label">标题</label>
          <el-input v-model="form.title" placeholder="章节标题" />
        </div>
        <div class="cm-form-row">
          <label class="cm-form-label">侧边栏名称</label>
          <el-input v-model="form.subtitle" placeholder="如：认知篇 / 定位篇 / 附录" />
        </div>
        <div class="cm-form-row">
          <label class="cm-form-label">正文内容</label>
          <div v-if="drawerVisible" class="cm-editor-wrap">
            <Toolbar class="cm-toolbar" :editor="editorRef" :defaultConfig="toolbarConfig" mode="default" />
            <Editor
              class="cm-editor"
              v-model="form.content_html"
              :defaultConfig="editorConfig"
              mode="default"
              @onCreated="handleEditorCreated"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <div class="cm-drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button @click="enterPreview">预览</el-button>
          <el-button type="primary" :loading="saving" @click="saveChapter">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import '@wangeditor/editor/dist/css/style.css'
import api from '@/api/api'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isAdmin = computed(() => userStore.isAdmin)

// ── Data ──────────────────────────────────────────────────────
const chapters = ref([])       // 列表（不含 content_html）
const detail = ref(null)       // 当前章节详情（含 content_html）
const currentId = ref(null)    // 当前选中的章节 ID
const loading = ref(false)

// ── 章节短名称 + 副标题（侧边栏用，硬编码） ──────────────────
const NAV_ITEMS = [
  { name: '课程总览', sub: '开始这里' },
  { name: '认知篇', sub: '为什么是 AI 垂类公众号' },
  { name: '定位篇', sub: '账号定位与用户画像' },
  { name: '机制篇', sub: '推荐机制与爆款心理学' },
  { name: '选题篇 · 上', sub: '信息源与热点挖掘' },
  { name: '选题篇 · 下', sub: '爆款选题方法论' },
  { name: '标题篇', sub: '让大脑刹车的标题' },
  { name: '创作篇', sub: '文章创作全流程' },
  { name: '加热篇', sub: '花小钱撬动大流量' },
  { name: '变现篇', sub: '商单获取与商稿写作' },
  { name: '复盘篇', sub: '数据复盘与持续增长' },
  { name: '附录', sub: 'SOP 清单与工具包' },
]
function getNavName(ch, idx) {
  return NAV_ITEMS[idx]?.name || ch.subtitle || ch.title
}
function getNavSub(ch, idx) {
  return NAV_ITEMS[idx]?.sub || ''
}

// ── Sidebar (mobile) ──────────────────────────────────────────
const sidebarOpen = ref(false)

// ── Drawer / Editor ───────────────────────────────────────────
const drawerVisible = ref(false)
const editingChapter = ref(null)  // null = 新建, object = 编辑
const saving = ref(false)
const form = ref({
  kicker: '',
  title: '',
  subtitle: '',
  content_html: '',
})
const editorRef = shallowRef(null)

// ── 主页面预览（纯视角切换，隐藏管理员控件） ────────────────
const isPreviewing = ref(false)

// ── 编辑预览（编辑后未保存的内容预览） ──────────────────────
const editPreviewData = ref(null)        // 编辑后未保存的预览数据
const editPreviewChapter = ref(null)     // 预览时保存 editingChapter 引用

// 显示数据：编辑预览时用 editPreviewData，否则用 detail
const displayData = computed(() => {
  if (editPreviewData.value) return editPreviewData.value
  return detail.value
})

const toolbarConfig = {
  toolbarKeys: [
    'headerSelect', '|',
    'bold', 'italic', 'underline', 'through', '|',
    'color', 'bgColor', '|',
    'bulletedList', 'numberedList', 'todo', '|',
    'insertLink', 'insertTable', 'blockquote', 'divider', '|',
    'justifyLeft', 'justifyCenter', 'justifyRight', '|',
    'undo', 'redo',
  ],
  excludeKeys: ['group-video', 'insertVideo', 'uploadVideo', 'group-image', 'uploadImage'],
}

const editorConfig = {
  placeholder: '编辑章节正文…',
  scroll: false,
  MENU_CONF: {
    insertTable: { maxRows: 10, maxCols: 8 },
  },
}

function handleEditorCreated(editor) {
  editorRef.value = editor
}

// ── Computed: prev / next ─────────────────────────────────────
const prevChapter = computed(() => {
  if (!detail.value || !chapters.value.length) return null
  const idx = chapters.value.findIndex(ch => ch.id === currentId.value)
  if (idx <= 0) return null
  return chapters.value[idx - 1]
})

const nextChapter = computed(() => {
  if (!detail.value || !chapters.value.length) return null
  const idx = chapters.value.findIndex(ch => ch.id === currentId.value)
  if (idx < 0 || idx >= chapters.value.length - 1) return null
  return chapters.value[idx + 1]
})

// ── Actions ───────────────────────────────────────────────────
async function fetchChapters() {
  const res = await api.get('/courses/chapters')
  chapters.value = res.data?.chapters || res.chapters || []
}

async function fetchDetail(id) {
  if (!id) return
  loading.value = true
  try {
    const res = await api.get(`/courses/chapters/${id}`)
    detail.value = res.data?.data || res.data || res
  } catch (e) {
    ElMessage.error('获取章节详情失败')
  } finally {
    loading.value = false
  }
}

async function selectChapter(ch) {
  currentId.value = ch.id
  await fetchDetail(ch.id)
  router.replace({ query: { ...route.query, chapter: ch.id } })
  sidebarOpen.value = false
  // scroll to top
  const main = document.querySelector('.cm-main')
  if (main) main.scrollTop = 0
}

// ── Admin: Create / Edit ──────────────────────────────────────
function openCreateDrawer() {
  editingChapter.value = null
  form.value = { kicker: '', title: '', subtitle: '', content_html: '' }
  drawerVisible.value = true
}

function openEditDrawer() {
  if (!detail.value) return
  editingChapter.value = detail.value
  form.value = {
    kicker: detail.value.kicker || '',
    title: detail.value.title || '',
    subtitle: detail.value.subtitle || '',
    content_html: detail.value.content_html || '',
  }
  drawerVisible.value = true
}

function onDrawerClosed() {
  editorRef.value = null
  editingChapter.value = null
}

// 编辑预览：从抽屉进入，关闭抽屉并在主页面显示编辑后的内容
function enterPreview() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请先填写标题')
    return
  }
  editPreviewData.value = { ...form.value }
  editPreviewChapter.value = editingChapter.value
  drawerVisible.value = false
  const main = document.querySelector('.cm-main')
  if (main) main.scrollTop = 0
}

// 确认更新：保存到数据库
async function confirmUpdate() {
  if (!editPreviewData.value?.title?.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  saving.value = true
  try {
    if (editPreviewChapter.value) {
      await api.put(`/courses/chapters/${editPreviewChapter.value.id}`, {
        title: editPreviewData.value.title,
        subtitle: editPreviewData.value.subtitle,
        kicker: editPreviewData.value.kicker,
        content_html: editPreviewData.value.content_html,
      })
      ElMessage.success('章节已更新')
    } else {
      const res = await api.post('/courses/chapters', {
        title: editPreviewData.value.title,
        subtitle: editPreviewData.value.subtitle,
        kicker: editPreviewData.value.kicker,
        content_html: editPreviewData.value.content_html,
      })
      const newCh = res.data?.data || res.data || res
      if (newCh?.id) currentId.value = newCh.id
      ElMessage.success('章节已创建')
    }
    editPreviewData.value = null
    editPreviewChapter.value = null
    await fetchChapters()
    if (currentId.value) await fetchDetail(currentId.value)
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message || ''))
  } finally {
    saving.value = false
  }
}

// 取消预览：丢弃编辑内容，回到原始
function cancelPreview() {
  editPreviewData.value = null
  editPreviewChapter.value = null
}

async function saveChapter() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请输入章节标题')
    return
  }
  saving.value = true
  try {
    if (editingChapter.value) {
      // 更新
      await api.put(`/courses/chapters/${editingChapter.value.id}`, {
        title: form.value.title,
        subtitle: form.value.subtitle,
        kicker: form.value.kicker,
        content_html: form.value.content_html,
      })
      ElMessage.success('章节已更新')
    } else {
      // 新建
      const res = await api.post('/courses/chapters', {
        title: form.value.title,
        subtitle: form.value.subtitle,
        kicker: form.value.kicker,
        content_html: form.value.content_html,
      })
      const newCh = res.data?.data || res.data || res
      if (newCh?.id) {
        currentId.value = newCh.id
      }
      ElMessage.success('章节已创建')
    }
    drawerVisible.value = false
    await fetchChapters()
    if (currentId.value) await fetchDetail(currentId.value)
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

// ── Admin: Delete ─────────────────────────────────────────────
async function confirmDelete(ch) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${ch.title}」？此操作不可撤销。`,
      '删除章节',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await api.delete(`/courses/chapters/${ch.id}`)
    ElMessage.success('已删除')
    await fetchChapters()
    if (currentId.value === ch.id) {
      currentId.value = chapters.value[0]?.id || null
      if (currentId.value) await fetchDetail(currentId.value)
      else detail.value = null
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// ── Admin: Reorder ────────────────────────────────────────────
async function moveChapter(ch, direction) {
  const idx = chapters.value.findIndex(c => c.id === ch.id)
  const targetIdx = idx + direction
  if (targetIdx < 0 || targetIdx >= chapters.value.length) return

  const items = chapters.value.map((c, i) => ({ id: c.id, sort_order: i }))
  // Swap sort_order of the two items
  const tmp = items[idx].sort_order
  items[idx].sort_order = items[targetIdx].sort_order
  items[targetIdx].sort_order = tmp

  try {
    await api.put('/courses/chapters/reorder', { items })
  } catch (e) {
    console.error('排序失败:', e)
    ElMessage.error('排序失败：' + (e.response?.status || '') + ' ' + (e.response?.data?.detail || e.message || ''))
    return
  }
  await fetchChapters()
  if (currentId.value) await fetchDetail(currentId.value)
}

// ── Lifecycle ─────────────────────────────────────────────────
onBeforeUnmount(() => {
  if (editorRef.value) {
    editorRef.value.destroy()
    editorRef.value = null
  }
})

// ── Init ──────────────────────────────────────────────────────
;(async () => {
  await fetchChapters()
  // 从 URL query 读初始章节
  const qCh = route.query.chapter
  if (qCh) {
    const target = chapters.value.find(ch => ch.id === Number(qCh))
    if (target) {
      await selectChapter(target)
      return
    }
  }
  // 默认选第一章
  if (chapters.value.length) {
    await selectChapter(chapters.value[0])
  }
})()
</script>

<style scoped>
.cm-page {
  height: 100%;
  position: relative;
}

/* ── Mobile topbar ─────────────────────────────────────────── */
.cm-topbar {
  display: none;
  align-items: center;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--ivory);
  border-bottom: 1px solid var(--line);
  padding: 10px 16px;
}
.cm-menu-btn {
  font-size: 13px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  padding: 6px 12px;
  cursor: pointer;
  color: var(--ink);
}
.cm-topbar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Layout ────────────────────────────────────────────────── */
.cm-layout {
  display: flex;
  gap: 0;
  min-height: calc(100vh - 92px);
}

/* ── Sidebar ───────────────────────────────────────────────── */
.cm-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--paper);
  border-right: 1px solid var(--line);
  position: sticky;
  top: 92px;
  height: calc(100vh - 92px);
  overflow-y: auto;
  padding: 20px 12px 32px;
}
.cm-brand {
  padding: 0 10px 16px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 12px;
}
.cm-brand-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
}
.cm-brand-sub {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 2px;
}
.cm-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cm-nav-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: background 0.12s;
  position: relative;
}
.cm-nav-item:hover {
  background: var(--ivory);
}
.cm-nav-item.active {
  background: var(--clay-tint);
}
.cm-nav-item.active .cm-nav-name {
  color: var(--clay);
  font-weight: 600;
}
.cm-nav-num {
  font-size: 11px;
  color: var(--ink-4);
  font-variant-numeric: tabular-nums;
  width: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}
.cm-nav-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.cm-nav-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.4;
}
.cm-nav-sub {
  font-size: 11px;
  color: var(--ink-4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cm-nav-actions {
  display: none;
  gap: 2px;
  flex-shrink: 0;
}
.cm-nav-item:hover .cm-nav-actions {
  display: flex;
}
.cm-nav-btn {
  font-size: 12px;
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--ink-3);
  border-radius: 3px;
  line-height: 1;
}
.cm-nav-btn:hover {
  background: var(--line);
  color: var(--ink);
}
.cm-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.cm-nav-del:hover {
  color: var(--crimson);
}
.cm-add-btn {
  width: 100%;
  margin-top: 12px;
  padding: 8px;
  font-size: 13px;
  border: 1px dashed var(--clay-soft);
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--clay);
  cursor: pointer;
  transition: background 0.12s;
}
.cm-add-btn:hover {
  background: var(--clay-tint);
}

/* ── Main content ──────────────────────────────────────────── */
.cm-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}
.cm-loading,
.cm-empty {
  padding: 80px 20px;
  text-align: center;
  color: var(--ink-4);
  font-size: 14px;
}
.cm-content {
  max-width: 760px;
  margin: 0 auto;
  padding: 40px 40px 72px;
}

/* ── Chapter head ──────────────────────────────────────────── */
.cm-ch-head {
  position: relative;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
}
.cm-ch-kicker {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--clay);
  margin-bottom: 8px;
}
.cm-ch-head h1 {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', ui-serif, Georgia, serif;
  font-size: clamp(24px, 3.2vw, 34px);
  font-weight: 500;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.35;
  margin: 0;
}
.cm-edit-btn {
  font-size: 13px;
  padding: 5px 14px;
  border: 1px solid var(--clay-soft);
  border-radius: var(--r-sm);
  background: var(--paper);
  color: var(--clay);
  cursor: pointer;
  transition: all 0.12s;
  white-space: nowrap;
}
.cm-edit-btn:hover {
  background: var(--clay-tint);
  border-color: var(--clay);
}

/* ── Prose content (rendered HTML) ─────────────────────────── */
.cm-prose {
  font-size: 15px;
  line-height: 1.85;
  color: var(--ink-2);
  text-align: justify;
}
.cm-prose :deep(h2) {
  font-size: 20px;
  font-weight: 600;
  color: var(--ink);
  margin: 36px 0 12px;
  letter-spacing: -0.01em;
}
.cm-prose :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin: 24px 0 8px;
}
.cm-prose :deep(p) {
  margin: 0 0 14px;
}
.cm-prose :deep(ul) {
  list-style-type: disc;
  margin: 0 0 16px;
  padding-left: 22px;
}
.cm-prose :deep(ol) {
  list-style-type: decimal;
  margin: 0 0 16px;
  padding-left: 22px;
}
.cm-prose :deep(li) {
  margin-bottom: 6px;
}
.cm-prose :deep(li > ul),
.cm-prose :deep(li > ol) {
  margin-top: 6px;
  margin-bottom: 0;
}
.cm-prose :deep(strong) {
  color: var(--ink);
  font-weight: 600;
}
.cm-prose :deep(a) {
  color: var(--clay);
  text-decoration: none;
}
.cm-prose :deep(a:hover) {
  text-decoration: underline;
}
.cm-prose :deep(blockquote) {
  background: var(--paper);
  border: 1px solid var(--line);
  border-left: 3px solid var(--clay);
  border-radius: var(--r-sm);
  padding: 14px 18px;
  margin: 0 0 16px;
  color: var(--ink-2);
}
.cm-prose :deep(blockquote p) {
  margin-bottom: 6px;
}
.cm-prose :deep(blockquote p:last-child) {
  margin-bottom: 0;
}
.cm-prose :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 6px 0 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  overflow: hidden;
  font-size: 14px;
}
.cm-prose :deep(th) {
  text-align: left;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-4);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  background: var(--bone);
}
.cm-prose :deep(td) {
  padding: 9px 12px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.cm-prose :deep(tr:last-child td) {
  border-bottom: none;
}
.cm-prose :deep(input[type="checkbox"]) {
  accent-color: var(--clay);
  margin-right: 6px;
}
.cm-prose :deep(.task-list) {
  list-style: none;
  padding-left: 0;
}
.cm-prose :deep(.citation) {
  font-style: normal;
  color: var(--clay);
}

/* ── Pager ─────────────────────────────────────────────────── */
.cm-pager {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 48px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
}
.cm-pager-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  padding: 8px 16px;
  cursor: pointer;
  transition: all 0.12s;
}
.cm-pager-btn:hover:not(:disabled) {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-1);
  color: var(--ink);
}
.cm-pager-btn:disabled {
  opacity: 0;
  pointer-events: none;
}
.cm-pager-btn.next {
  margin-left: auto;
}

/* ── Scrim (mobile) ────────────────────────────────────────── */
.cm-scrim {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(31, 31, 30, 0.25);
  z-index: 20;
}
.cm-scrim.show {
  display: block;
}

/* ── Edit drawer ───────────────────────────────────────────── */
.cm-edit-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 20px;
}
.cm-form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cm-form-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2);
}
.cm-editor-wrap {
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  overflow: hidden;
}
.cm-toolbar {
  border-bottom: 1px solid var(--line) !important;
}
.cm-editor {
  height: 500px;
  overflow-y: auto;
}
.cm-editor :deep(.w-e-text-container) {
  height: 500px !important;
  background: var(--paper);
}
.cm-editor :deep(.w-e-text p),
.cm-editor :deep(.w-e-text li),
.cm-editor :deep(.w-e-text td),
.cm-editor :deep(.w-e-text blockquote) {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink-2);
}
.cm-editor :deep(.w-e-text h1),
.cm-editor :deep(.w-e-text h2),
.cm-editor :deep(.w-e-text h3),
.cm-editor :deep(.w-e-text h4),
.cm-editor :deep(.w-e-text h5) {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', ui-serif, Georgia, serif;
  color: var(--ink);
}
.cm-editor :deep(.w-e-text a) {
  color: var(--clay);
}
.cm-drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ── 章节操作按钮容器 ──────────────────────────────────────── */
.cm-ch-actions {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  gap: 8px;
}

/* ── 编辑预览横条 ──────────────────────────────────────────── */
.cm-preview-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin-bottom: 20px;
  background: var(--clay-tint);
  border: 1px solid var(--clay-soft);
  border-radius: var(--r-sm);
}
.cm-preview-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--clay);
  background: var(--paper);
  padding: 2px 8px;
  border-radius: var(--r-pill);
}
.cm-preview-hint {
  font-size: 13px;
  color: var(--ink-3);
}
.cm-btn-confirm {
  background: var(--clay) !important;
  color: #fff !important;
  border-color: var(--clay) !important;
}
.cm-btn-confirm:hover {
  background: var(--clay-deep) !important;
  border-color: var(--clay-deep) !important;
}
.cm-btn-confirm:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ── Responsive ────────────────────────────────────────────── */
@media (max-width: 860px) {
  .cm-topbar {
    display: flex;
  }
  .cm-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 30;
    transform: translateX(-100%);
    transition: transform 0.22s ease;
    width: 280px;
    height: 100vh;
    box-shadow: var(--sh-2);
  }
  .cm-sidebar.open {
    transform: none;
  }
  .cm-content {
    padding: 24px 16px 56px;
  }
}
</style>
