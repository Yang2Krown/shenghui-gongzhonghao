<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><Document /></el-icon>
        创作工具 · 正文生成
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        把大纲写成<span class="text-clay">有人味</span>的正文
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        提供信息源，AI 会自动生成有节奏、去 AI 味的完整正文，可直接复制发布。
      </p>
    </div>

    <!-- 信息源 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">信息源</div>
            <div class="text-xs text-ink-4">支持文件 / 链接 / 文本</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div class="seg" style="margin-bottom: 16px;">
          <button :class="['seg-btn', { 'seg-btn-active': inputMode === 'file' }]" @click="inputMode = 'file'">文件</button>
          <button :class="['seg-btn', { 'seg-btn-active': inputMode === 'link' }]" @click="inputMode = 'link'">链接</button>
          <button :class="['seg-btn', { 'seg-btn-active': inputMode === 'text' }]" @click="inputMode = 'text'">文本</button>
        </div>

        <div class="tab-grid">
          <div v-show="inputMode === 'file'">
            <FileUploadZone v-model="fileName" policy="reference" :uploading="fileUploading"
              :meta-text="fileText ? `${fileText.length} 字` : ''"
              :preview-text="fileText ? fileText.slice(0, 200) + '…' : ''"
              title="点击或拖拽上传 PDF / Word / TXT / MD / 图片"
              @select="onFileSelect" @remove="removeFile" />
          </div>

          <div v-show="inputMode === 'link'">
            <div v-if="linkExtracting" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
              <span class="text-sm text-ink-3">正在提取链接内容…</span>
            </div>
            <div v-else-if="linkTitle" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                  <el-icon class="text-clay"><Link /></el-icon> {{ linkTitle }}
                  <span v-if="linkPlatform" class="text-xs text-ink-4" style="padding: 2px 8px; background: var(--line); border-radius: 12px;">{{ linkPlatform }}</span>
                </span>
                <button @click="removeLink()" class="btn-text text-sm">移除</button>
              </div>
            </div>
            <div v-else style="position: relative;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex: 1; position: relative;">
                  <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
                  <el-input v-model="linkUrl" placeholder="粘贴文章链接（公众号 / 小红书 / 知乎 / 抖音 等）"
                    style="padding-left: 38px;" />
                </div>
                <button @click="handleLinkExtract()" :disabled="!linkUrl || linkExtracting"
                  style="padding: 8px 16px; background: var(--clay); color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;"
                  :style="{ opacity: (!linkUrl || linkExtracting) ? 0.5 : 1 }">
                  确认
                </button>
              </div>
            </div>
          </div>

          <div v-show="inputMode === 'text'">
            <el-input v-model="outlineText" type="textarea" :rows="5"
              placeholder="粘贴或输入文章大纲，每行一个要点……" style="resize: none;" />
          </div>
        </div>
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
          placeholder="例如：篇幅 1500 字左右，多用短句和具体场景，结尾留一个开放式问题……" />
      </div>
    </div>

    <button class="cta-bar" :disabled="!canGenerate || submitting" @click="handleGenerate">
        <template v-if="submitting">
          <el-icon class="spin"><Loading /></el-icon> 正在生成…
        </template>
        <template v-else>生成正文 <CreditHint :cost="10" /></template>
    </button>
    <p v-if="!canGenerate" class="text-xs text-ink-4" style="text-align: center; margin-top: 10px;">先填入内容即可开始</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Edit, Loading, Link } from '@element-plus/icons-vue'
import api, { uploadFile, extractLinkContent } from '@/api/api'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'
import FileUploadZone from '@/components/upload/FileUploadZone.vue'

const creditStore = useCreditStore()

const router = useRouter()
const submitting = ref(false)

const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const inputMode = ref('file')
const outlineText = ref('')
const fileName = ref('')
const fileText = ref('')
const fileUploading = ref(false)
const linkUrl = ref('')
const linkExtracting = ref(false)
const linkTitle = ref('')
const linkContent = ref('')
const linkPlatform = ref('')
const preference = ref('')

const canGenerate = computed(() => {
  const hasContent = fileName.value ? !!fileText.value : outlineText.value.trim().length > 4
  return hasContent && !submitting.value
})

// 获取当前输入的文本内容
const getSourceText = () => {
  if (inputMode.value === 'link' && linkTitle.value) {
    const parts = []
    if (linkTitle.value) parts.push(`标题：${linkTitle.value}`)
    if (linkContent.value) parts.push(linkContent.value)
    return parts.join('\n')
  }
  if (inputMode.value === 'file') return fileText.value
  return outlineText.value
}

const onFileSelect = async (file) => {
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

const removeFile = () => { fileName.value = ''; fileText.value = '' }

const handleLinkExtract = async () => {
  const url = (linkUrl.value || '').trim()
  if (!url) return
  linkExtracting.value = true
  try {
    const res = await extractLinkContent(url)
    const data = res.data || res
    linkTitle.value = data.title || '未知标题'
    linkContent.value = data.content || ''
    linkPlatform.value = data.platform || '网页'
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '链接提取失败')
    linkTitle.value = ''; linkContent.value = ''; linkPlatform.value = ''
  } finally {
    linkExtracting.value = false
  }
}

const removeLink = () => {
  linkUrl.value = ''; linkTitle.value = ''; linkContent.value = ''; linkPlatform.value = ''
}

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip : chip
  }
}

const handleGenerate = async () => {
  const sourceText = getSourceText()
  if (!sourceText || sourceText.trim().length < 5) {
    ElMessage.warning('请输入至少 5 个字的内容')
    return
  }

  submitting.value = true
  try {
    // 构造信息源
    const sources = []
    if (inputMode.value === 'link' && linkTitle.value) {
      sources.push({ type: 'text', content: sourceText, url: linkUrl.value.trim() })
    } else if (inputMode.value === 'file') {
      sources.push({ type: 'text', content: fileText.value })
    } else {
      sources.push({ type: 'text', content: outlineText.value })
    }

    // 创建候选选题
    const res = await api.post('/topic-candidates/create-adhoc', {
      sources,
      preference: preference.value,
    }, { timeout: 10000 })

    const data = res?.data || res
    const candidateId = data?.data?.candidate_id || data?.candidate_id
    if (!candidateId) {
      ElMessage.error('未能创建选题')
      submitting.value = false
      return
    }

    // 将大纲文本存入 sessionStorage，供编辑器读取
    sessionStorage.setItem('creation_body_outline_text', sourceText)

    // 跳转到编辑器，自动开始正文生成
    router.push({
      path: '/creation/new',
      query: {
        candidate_id: candidateId,
        topic_title: data?.data?.title || data?.title || sourceText.slice(0, 30),
        auto_generate_content: 'true',
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
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.dropzone-active { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.cta-bar { position: relative; width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.type-chip { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--paper); color: #6B6862; border: 1px solid var(--line); cursor: pointer; transition: all 0.15s; }
.type-chip:hover { background: #F0EDE3; color: var(--ink); }
.type-chip-active { background: var(--clay); color: #fff; border-color: var(--clay); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
