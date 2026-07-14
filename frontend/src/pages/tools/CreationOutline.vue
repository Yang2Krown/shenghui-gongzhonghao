<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><Document /></el-icon>
        创作工具 · 大纲生成
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        把信息搭成<span class="text-clay">立得住</span>的结构
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        给定一个或多个信息源，AI 会为你生成一份层次清晰、可直接落笔的文章大纲。
      </p>
    </div>

    <!-- 信息源面板 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">信息源</div>
            <div class="text-xs text-ink-4">支持文字 / PDF / 链接，可添加多个</div>
          </div>
        </div>
        <span class="badge badge-clay" style="font-size: 12px; padding: 4px 11px;">
          已填 {{ filledCount }} / {{ sources.length }}
        </span>
      </div>
      <div style="padding: 22px;">
        <div v-for="(source, index) in sources" :key="index" class="src-card slide-up">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 13px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="src-number">{{ index + 1 }}</span>
              <div class="seg">
                <button v-for="kind in sourceKinds" :key="kind.key"
                  @click="source.kind = kind.key"
                  :class="['seg-btn', { 'seg-btn-active': source.kind === kind.key }]">
                  {{ kind.label }}
                </button>
              </div>
            </div>
            <button v-if="sources.length > 1" @click="sources.splice(index, 1)" class="btn-text text-ink-4" style="padding: 4px;">
              <el-icon :size="15"><Delete /></el-icon>
            </button>
          </div>
          <el-input v-if="source.kind === 'text'" v-model="source.text" type="textarea" :rows="4"
            placeholder="粘贴或输入文字内容，如新闻、笔记、观点、数据……" />
          <div v-else-if="source.kind === 'link'">
            <!-- 链接加载中 -->
            <div v-if="source.linkExtracting" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取链接内容…</span>
            </div>
            <!-- 链接已提取 -->
            <div v-else-if="source.linkTitle" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Link /></el-icon> {{ source.linkTitle }}
                  <span v-if="source.linkPlatform" class="text-xs text-ink-4" style="padding: 2px 8px; background: var(--line); border-radius: 12px;">{{ source.linkPlatform }}</span>
                </span>
                <button @click="removeLink(source)" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="source.linkContent" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ source.linkContent.slice(0, 200) }}…
              </div>
            </div>
            <!-- 链接输入框 -->
            <div v-else style="position: relative;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex: 1; position: relative;">
                  <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
                  <el-input v-model="source.url" placeholder="粘贴文章链接（公众号 / 小红书 / 知乎 / 抖音 等）"
                    style="padding-left: 38px;" />
                </div>
                <button @click="handleLinkExtract(source)" :disabled="!source.url || source.linkExtracting"
                  style="padding: 8px 16px; background: var(--clay); color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;"
                  :style="{ opacity: (!source.url || source.linkExtracting) ? 0.5 : 1 }">
                  确认
                </button>
              </div>
            </div>
          </div>
          <div v-else-if="source.kind === 'file'">
            <div v-if="source.fileUploading" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取文件内容…</span>
            </div>
            <div v-else-if="source.fileName" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Document /></el-icon> {{ source.fileName }}
                  <span v-if="source.fileText" class="text-xs text-ink-4">· {{ source.fileText.length }} 字</span>
                </span>
                <button @click="removeFile(source)" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="source.fileText" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ source.fileText.slice(0, 200) }}…
              </div>
            </div>
            <div v-else class="dropzone" :class="{ 'dropzone-active': source.dragOver }"
              @click="triggerFileInput(index)"
              @dragover.prevent="source.dragOver = true"
              @dragleave="source.dragOver = false"
              @drop="handleFileDrop(source, $event)">
              <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
              <div class="text-sm font-medium">点击或拖拽上传 PDF / Word / TXT / MD</div>
            </div>
            <input :ref="(el) => setFileInputRef(el, index)" type="file" accept=".pdf,.docx,.txt,.md" style="display:none"
              @change="(e) => handleFileUpload(source, e)" />
          </div>
        </div>
        <button @click="sources.push({ kind: 'file', text: '', url: '', fileName: '', fileText: '', fileUploading: false, dragOver: false })" class="btn-ghost" style="border-style: dashed; margin-top: 8px;">
          <el-icon :size="16"><Plus /></el-icon> 添加信息源
        </button>
      </div>
    </div>

    <!-- 创作偏好 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">创作偏好 <span class="text-xs text-ink-4" style="font-weight: 400;">选填</span></div>
            <div class="text-xs text-ink-4">补充风格、语气、受众或任何额外要求</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px;">
          <button v-for="chip in styleChips" :key="chip" @click="toggleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：篇幅 1500 字左右，多用短句和具体场景……" />
      </div>
    </div>

    <!-- 生成按钮 -->
    <button class="cta-bar" :disabled="!canGenerate || submitting" @click="handleGenerate">
        <template v-if="submitting">
          <el-icon class="spin"><Loading /></el-icon> 正在创建选题…
        </template>
        <template v-else>生成大纲 <CreditHint :cost="3" /></template>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Document, Delete, Plus, Upload, Link, Edit,
  Loading
} from '@element-plus/icons-vue'
import api, { uploadFile, extractLinkContent } from '@/api/api'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'

const creditStore = useCreditStore()

const route = useRoute()
const router = useRouter()
const submitting = ref(false)

const sourceKinds = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]
const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const sources = ref([{
  kind: 'file',
  text: route.query.angle || '',
  url: '',
  fileName: '',
  fileText: '',
  fileUploading: false,
  dragOver: false,
  linkExtracting: false,
  linkTitle: '',
  linkContent: '',
  linkPlatform: '',
  linkAuthor: '',
}])
const fileInputs = reactive({})
const preference = ref('')

const filledCount = computed(() => sources.value.filter(s => s.text || s.url || s.fileText).length)
const canGenerate = computed(() => filledCount.value > 0 && !submitting.value)

const handleFileUpload = async (source, event) => {
  const file = event.target.files?.[0]
  if (!file) return

  source.fileName = file.name
  source.fileUploading = true
  source.fileText = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    source.fileText = data.text || ''
    if (!source.fileText) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      source.fileName = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    source.fileName = ''
  } finally {
    source.fileUploading = false
  }
}

const removeFile = (source) => {
  source.fileName = ''
  source.fileText = ''
}

const handleLinkExtract = async (source) => {
  const url = (source.url || '').trim()
  if (!url) return

  source.linkExtracting = true
  try {
    const res = await extractLinkContent(url)
    const data = res.data || res
    source.linkTitle = data.title || '未知标题'
    source.linkContent = data.content || ''
    source.linkPlatform = data.platform || '网页'
    source.linkAuthor = data.author || ''
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '链接提取失败')
    source.linkTitle = ''
    source.linkContent = ''
    source.linkPlatform = ''
  } finally {
    source.linkExtracting = false
  }
}

const removeLink = (source) => {
  source.url = ''
  source.linkTitle = ''
  source.linkContent = ''
  source.linkPlatform = ''
  source.linkAuthor = ''
}

const setFileInputRef = (el, index) => {
  if (el) fileInputs[index] = el
}

const triggerFileInput = (index) => {
  const input = fileInputs[index]
  if (input) {
    input.value = ''
    input.click()
  }
}

const handleFileDrop = async (source, event) => {
  event.preventDefault()
  source.dragOver = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return

  source.fileName = file.name
  source.fileUploading = true
  source.fileText = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    source.fileText = data.text || ''
    if (!source.fileText) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      source.fileName = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    source.fileName = ''
  } finally {
    source.fileUploading = false
  }
}

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value
      ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip
      : chip
  }
}

const handleGenerate = async () => {
  submitting.value = true

  const apiSources = sources.value
    .filter(s => s.text || s.url || s.fileText)
    .map(s => {
      if (s.kind === 'text') return { type: 'text', content: s.text }
      if (s.kind === 'link') {
        if (s.linkTitle) {
          const parts = []
          if (s.linkTitle) parts.push(`标题：${s.linkTitle}`)
          if (s.linkAuthor) parts.push(`作者：${s.linkAuthor}`)
          if (s.linkContent) parts.push(s.linkContent)
          return { type: 'text', content: parts.join('\n'), url: s.url }
        }
        return { type: 'link', content: s.url }
      }
      if (s.kind === 'file') return { type: 'text', content: s.fileText || '' }
      return { type: 'text', content: '' }
    })

  try {
    // 同步创建候选选题，拿到 candidate_id 后跳转到创作页自动生成大纲
    const res = await api.post('/topic-candidates/create-adhoc', {
      sources: apiSources,
      preference: preference.value,
    }, { timeout: 10000 })

    const data = res?.data || res
    const candidateId = data?.candidate_id
    if (!candidateId) {
      ElMessage.error('未能创建选题')
      return
    }

    sessionStorage.setItem('creation_outline_auto_candidate_id', String(candidateId))

    router.push({
      path: '/creation/new',
      query: {
        candidate_id: candidateId,
        topic_title: data?.title || '',
        auto_generate: 'true',
      }
    })
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
    submitting.value = false
  }
}
</script>

<style scoped>
.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }
.soft-panel { background: radial-gradient(120% 80% at 100% 0%, rgba(204,120,92,.06) 0%, transparent 55%), var(--paper); }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.src-card { position: relative; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 16px 18px 16px 20px; overflow: hidden; transition: border-color .18s, box-shadow .18s; margin-bottom: 12px; }
.src-card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: linear-gradient(var(--clay-soft), var(--clay)); opacity: .55; }
.src-card:focus-within { border-color: var(--clay-soft); box-shadow: var(--sh-2); }
.src-card:focus-within::before { opacity: 1; }
.src-number { width: 26px; height: 26px; border-radius: 8px; background: var(--clay); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; font-family: var(--serif); }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.cta-bar { position: relative; width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.dropzone-active { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.type-chip { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--paper); color: #6B6862; border: 1px solid var(--line); cursor: pointer; transition: all 0.15s; }
.type-chip:hover { background: #F0EDE3; color: var(--ink); }
.type-chip-active { background: var(--clay); color: #fff; border-color: var(--clay); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
.slide-up { animation: slideUp .3s cubic-bezier(.32,.72,0,1) both; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
