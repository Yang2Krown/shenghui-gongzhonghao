<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><Switch /></el-icon>
        内容仿写 · 转写
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        一篇内容，<span class="text-clay">换个平台</span>重新表达
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        把一篇内容从一个平台的语言风格，转写成另一个平台的风格与排版。在下方切换转换方向。
      </p>
    </div>

    <!-- 转换方向 -->
    <div class="card soft-panel" style="padding: 0; overflow: visible; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Switch /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">转换方向</div>
            <div class="text-xs text-ink-4">选择源平台与目标平台</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap;">
          <!-- 源平台 -->
          <div style="flex: 1; min-width: 168px;">
            <div class="text-xs text-ink-4 uppercase font-semibold" style="margin-bottom: 9px; letter-spacing: .08em;">从（源平台）</div>
            <div class="platform-select" @click="showFromMenu = !showFromMenu">
              <span class="platform-dot" :style="{ background: platforms[from].color }">{{ platforms[from].dot }}</span>
              <span style="flex: 1; text-align: left; font-weight: 600;">{{ platforms[from].label }}</span>
              <el-icon :size="16" class="text-ink-4"><ArrowRight /></el-icon>
            </div>
            <div v-if="showFromMenu" class="platform-menu slide-up">
              <div @click="showFromMenu = false" style="position: fixed; inset: 0; z-index: 40;"></div>
              <div style="position: absolute; top: calc(100% + 6px); left: 0; right: 0; z-index: 41; background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); box-shadow: var(--sh-3); padding: 6px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
                <button v-for="pid in sourcePlatforms" :key="pid"
                  @click="pickFrom(pid)"
                  :class="['platform-option', { 'platform-option--active': pid === from }]">
                  <span class="platform-dot" :style="{ background: platforms[pid].color }">{{ platforms[pid].dot }}</span>
                  <span style="flex: 1; text-align: left;">{{ platforms[pid].label }}</span>
                  <el-icon v-if="pid === from" :size="15" class="text-clay"><Check /></el-icon>
                </button>
              </div>
            </div>
          </div>

          <!-- 互换按钮 -->
          <button @click="swapPlatforms" class="swap-btn"
            @mouseenter="$event.target.style.borderColor = 'var(--clay)'; $event.target.style.background = 'var(--clay-tint)'"
            @mouseleave="$event.target.style.borderColor = 'var(--line)'; $event.target.style.background = 'var(--paper)'">
            <el-icon :size="18"><Switch /></el-icon>
          </button>

          <!-- 目标平台 -->
          <div style="flex: 1; min-width: 168px;">
            <div class="text-xs text-ink-4 uppercase font-semibold" style="margin-bottom: 9px; letter-spacing: .08em;">转换成（目标平台）</div>
            <div class="platform-select" @click="showToMenu = !showToMenu">
              <span class="platform-dot" :style="{ background: platforms[to].color }">{{ platforms[to].dot }}</span>
              <span style="flex: 1; text-align: left; font-weight: 600;">{{ platforms[to].label }}</span>
              <el-icon :size="16" class="text-ink-4"><ArrowRight /></el-icon>
            </div>
            <div v-if="showToMenu" class="platform-menu slide-up">
              <div @click="showToMenu = false" style="position: fixed; inset: 0; z-index: 40;"></div>
              <div style="position: absolute; top: calc(100% + 6px); left: 0; right: 0; z-index: 41; background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); box-shadow: var(--sh-3); padding: 6px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
                <button v-for="pid in targetPlatforms.filter(t => t !== from)" :key="pid"
                  @click="pickTo(pid)"
                  :class="['platform-option', { 'platform-option--active': pid === to }]">
                  <span class="platform-dot" :style="{ background: platforms[pid].color }">{{ platforms[pid].dot }}</span>
                  <span style="flex: 1; text-align: left;">{{ platforms[pid].label }}</span>
                  <el-icon v-if="pid === to" :size="15" class="text-clay"><Check /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 方向回显 -->
        <div style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--line);">
          <span class="badge badge-clay" style="font-size: 13px; padding: 5px 12px;">
            <span class="platform-dot" :style="{ background: platforms[from].color, width: '16px', height: '16px', fontSize: '9px' }">{{ platforms[from].dot }}</span>
            {{ platforms[from].label }}
          </span>
          <el-icon :size="18" class="text-clay"><ArrowRight /></el-icon>
          <span class="badge badge-clay" style="font-size: 13px; padding: 5px 12px;">
            <span class="platform-dot" :style="{ background: platforms[to].color, width: '16px', height: '16px', fontSize: '9px' }">{{ platforms[to].dot }}</span>
            {{ platforms[to].label }}
          </span>
        </div>
      </div>
    </div>

    <!-- 原文输入 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">{{ platforms[from].label }}原文</div>
            <div class="text-xs text-ink-4">粘贴链接或正文内容</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div class="seg" style="margin-bottom: 16px;">
          <button @click="inputMode = 'file'" :class="['seg-btn', { 'seg-btn-active': inputMode === 'file' }]">文件</button>
          <button @click="inputMode = 'link'" :class="['seg-btn', { 'seg-btn-active': inputMode === 'link' }]">链接</button>
          <button @click="inputMode = 'text'" :class="['seg-btn', { 'seg-btn-active': inputMode === 'text' }]">文本</button>
        </div>

        <div class="tab-grid">
          <div v-show="inputMode === 'file'">
            <div v-if="fileUploading" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取文件内容…</span>
            </div>
            <div v-else-if="fileName" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Document /></el-icon> {{ fileName }}
                  <span v-if="fileText" class="text-xs text-ink-4">· {{ fileText.length }} 字</span>
                </span>
                <button @click="removeFile" class="btn-text text-sm">移除</button>
              </div>
              <div v-if="fileText" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ fileText.slice(0, 200) }}…
              </div>
            </div>
            <div v-else class="dropzone" :class="{ 'dropzone-active': dragOver }"
              @click="$refs.fileInput?.click()"
              @dragover.prevent="dragOver = true"
              @dragleave="dragOver = false"
              @drop="handleFileDrop">
              <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
              <div class="text-sm font-medium">点击或拖拽上传 PDF / Word / TXT / MD</div>
            </div>
            <input ref="fileInput" type="file" accept=".pdf,.docx,.txt,.md" style="display:none"
              @change="handleFileUpload" />
          </div>

          <div v-show="inputMode === 'link'">
            <div v-if="linkExtracting" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取内容…</span>
            </div>
            <div v-else-if="linkTitle" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
                  <el-icon class="text-clay"><Link /></el-icon>
                  <span class="text-sm font-semibold text-ink" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ linkTitle }}</span>
                  <span v-if="linkPlatform" class="text-xs text-ink-4" style="padding: 2px 8px; background: var(--line); border-radius: 12px; flex-shrink: 0;">{{ linkPlatform }}</span>
                </div>
                <button @click="removeLink" class="btn-text text-sm" style="flex-shrink: 0; margin-left: 8px;">移除</button>
              </div>
              <div v-if="linkContent" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
                {{ linkContent.slice(0, 200) }}…
              </div>
            </div>
            <div v-else>
              <div style="display: flex; gap: 8px;">
                <el-input v-model="linkUrl"
                  :placeholder="`粘贴${platforms[from].label}原文链接`" style="flex: 1;" />
                <button @click="handleLinkExtract" :disabled="!linkUrl || linkExtracting"
                  class="btn-extract" :style="{ opacity: (!linkUrl || linkExtracting) ? 0.5 : 1 }">
                  确认提取
                </button>
              </div>
            </div>
          </div>

          <div v-show="inputMode === 'text'">
            <el-input v-model="inputValue" type="textarea" :rows="5"
              :placeholder="`粘贴${platforms[from].label}原文内容……`" style="resize: none;" />
          </div>
        </div>
      </div>
    </div>

    <!-- 额外要求 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">额外要求 <span class="text-xs text-ink-4" style="font-weight: 400;">选填</span></div>
            <div class="text-xs text-ink-4">补充转写时的额外要求</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px;">
          <button v-for="chip in rewriteChips" :key="chip" @click="toggleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：标题更有网感，正文分段短一些，结尾加一句互动引导……" />
      </div>
    </div>

    <button class="cta-bar" :disabled="!canGenerate || generating" @click="handleGenerate">
      <template v-if="generating">
        <el-icon class="spin"><Loading /></el-icon> 正在转写…
      </template>
      <template v-else>转写为{{ platforms[to].label }}</template>
    </button>

    <div v-if="generating" style="margin-top: 24px;" class="fade-in">
      <div style="text-align: center; padding: 56px 0;">
        <el-icon :size="30" class="spin text-clay" style="margin: 0 auto;"><Loading /></el-icon>
        <p class="text-sm text-ink-3" style="margin-top: 14px;">正在转写为{{ platforms[to].label }}风格…</p>
      </div>
    </div>

    <div v-if="result && !generating" class="fade-in" style="margin-top: 32px;">
      <RewriteResult :result="result" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Switch, Document, Edit, Loading, ArrowRight, Check, Link, Upload } from '@element-plus/icons-vue'
import { extractLinkContent, uploadFile, transformContent } from '@/api/api'
import RewriteResult from './RewriteResult.vue'

const platforms = {
  wechat: { id: 'wechat', label: '公众号', dot: '公', color: '#07C160' },
  xhs: { id: 'xhs', label: '小红书', dot: '书', color: '#FF2442' },
  douyin: { id: 'douyin', label: '抖音', dot: '抖', color: '#000000' },
  zhihu: { id: 'zhihu', label: '知乎', dot: '知', color: '#0084FF' },
}
const sourcePlatforms = ['wechat', 'xhs', 'douyin', 'zhihu']
const targetPlatforms = ['wechat', 'xhs']
const rewriteChips = ['更口语', '更精简', '更有网感', '加 emoji', '去 AI 味', '保留原意']

const from = ref('wechat')
const to = ref('xhs')
const showFromMenu = ref(false)
const showToMenu = ref(false)
const inputMode = ref('file')
const inputValue = ref('')
const preference = ref('')
const generating = ref(false)
const result = ref(null)

// 文件上传相关
const fileName = ref('')
const fileText = ref('')
const fileUploading = ref(false)
const dragOver = ref(false)

// 链接提取相关
const linkUrl = ref('')
const linkExtracting = ref(false)
const linkTitle = ref('')
const linkContent = ref('')
const linkPlatform = ref('')
const linkAuthor = ref('')

const canGenerate = computed(() => {
  if (inputMode.value === 'link') {
    return linkTitle.value && linkContent.value
  }
  if (inputMode.value === 'file') {
    return !!fileText.value
  }
  return inputValue.value.trim().length > 3
})

const pickFrom = (pid) => { from.value = pid; if (pid === to.value) to.value = targetPlatforms.find(t => t !== pid); showFromMenu.value = false }
const pickTo = (pid) => { to.value = pid; if (pid === from.value) from.value = sourcePlatforms.find(s => s !== pid); showToMenu.value = false }
const swapPlatforms = () => {
  if (targetPlatforms.includes(from.value) && sourcePlatforms.includes(to.value)) {
    const tmp = from.value; from.value = to.value; to.value = tmp
  } else {
    to.value = targetPlatforms.find(t => t !== from.value)
  }
}

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip : chip
  }
}

const handleLinkExtract = async () => {
  const url = linkUrl.value.trim()
  if (!url) return
  linkExtracting.value = true
  try {
    const res = await extractLinkContent(url)
    const data = res.data || res
    linkTitle.value = data.title || '未知标题'
    linkContent.value = data.content || ''
    linkPlatform.value = data.platform || '网页'
    linkAuthor.value = data.author || ''
  } catch (e) {
    ElMessage.error('链接提取失败，请检查链接或使用文字模式')
    linkTitle.value = ''
    linkContent.value = ''
    linkPlatform.value = ''
  } finally {
    linkExtracting.value = false
  }
}

const removeLink = () => {
  linkUrl.value = ''
  linkTitle.value = ''
  linkContent.value = ''
  linkPlatform.value = ''
  linkAuthor.value = ''
}

const handleFileUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  fileName.value = file.name
  fileUploading.value = true
  fileText.value = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    fileText.value = data.text || ''
    if (!fileText.value) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      fileName.value = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    fileName.value = ''
  } finally {
    fileUploading.value = false
  }
}

const removeFile = () => {
  fileName.value = ''
  fileText.value = ''
}

const handleFileDrop = async (event) => {
  event.preventDefault()
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return

  fileName.value = file.name
  fileUploading.value = true
  fileText.value = ''

  try {
    const res = await uploadFile(file)
    const data = res.data || res
    fileText.value = data.text || ''
    if (!fileText.value) {
      ElMessage.warning('文件内容提取为空，请检查文件')
      fileName.value = ''
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '文件上传失败')
    fileName.value = ''
  } finally {
    fileUploading.value = false
  }
}

const handleGenerate = async () => {
  generating.value = true
  result.value = null

  try {
    // 获取原文内容
    let content = ''
    let originalTitle = ''

    if (inputMode.value === 'link') {
      content = linkContent.value
      originalTitle = linkTitle.value
    } else if (inputMode.value === 'file') {
      content = fileText.value
    } else {
      content = inputValue.value
    }

    // 调用后端 API
    const res = await transformContent({
      content,
      source_platform: from.value,
      target_platform: to.value,
      original_title: originalTitle || undefined,
      extra_requirements: preference.value || undefined,
    })

    const data = res.data || res
    result.value = {
      title: data.title || '',
      body: data.content || '',
      tags: data.tags || [],
    }
  } catch (error) {
    console.error('转写失败:', error)
    ElMessage.error(error?.response?.data?.detail || '转写失败，请稍后重试')
  } finally {
    generating.value = false
  }
}
</script>

<style scoped>
.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }
.soft-panel { background: radial-gradient(120% 80% at 100% 0%, rgba(204,120,92,.06) 0%, transparent 55%), var(--paper); }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.platform-select { width: 100%; display: flex; align-items: center; gap: 10px; padding: 11px 14px; border-radius: var(--r-md); border: 1.5px solid var(--line); background: var(--paper); cursor: pointer; font-family: inherit; font-size: 15px; transition: all .15s; }
.platform-select:hover { border-color: var(--clay-soft); }
.platform-dot { width: 22px; height: 22px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #fff; flex-shrink: 0; }
.platform-option { display: flex; align-items: center; gap: 10px; padding: 9px 11px; border: none; background: transparent; cursor: pointer; border-radius: var(--r-sm); font-family: inherit; font-size: 14px; font-weight: 600; color: var(--ink-2); transition: background .12s; }
.platform-option:hover { background: var(--bone); }
.platform-option--active { background: var(--clay-tint); color: var(--clay-deep); }
.swap-btn { width: 42px; height: 42px; border-radius: 50%; border: 1px solid var(--line); background: var(--paper); display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; color: var(--clay); box-shadow: var(--sh-1); transition: all .15s; }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.dropzone-active { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.btn-extract { padding: 9px 18px; border: none; border-radius: var(--r-md); background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); color: #fff; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all .15s; }
.btn-extract:hover:not([disabled]) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(204,120,92,.3); }
.btn-extract[disabled] { cursor: not-allowed; }
.btn-text { border: none; background: transparent; color: var(--clay); font-family: inherit; font-weight: 600; cursor: pointer; padding: 2px 6px; border-radius: var(--r-sm); transition: background .12s; }
.btn-text:hover { background: var(--clay-tint); }
.type-chip { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--paper); color: #6B6862; border: 1px solid var(--line); cursor: pointer; transition: all 0.15s; }
.type-chip:hover { background: #F0EDE3; color: var(--ink); }
.type-chip-active { background: var(--clay); color: #fff; border-color: var(--clay); }
.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
.slide-up { animation: slideUp .3s cubic-bezier(.32,.72,0,1) both; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
