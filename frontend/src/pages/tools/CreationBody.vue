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
        给定一份大纲，AI 会生成有节奏、去 AI 味的完整正文，可直接复制发布。
      </p>
    </div>

    <!-- 大纲输入 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">大纲</div>
            <div class="text-xs text-ink-4">粘贴文字或上传文件</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div class="seg" style="margin-bottom: 16px;">
          <button :class="['seg-btn', { 'seg-btn-active': !fileName }]" @click="removeFile()">
            文字输入
          </button>
          <button :class="['seg-btn', { 'seg-btn-active': !!fileName }]" @click="$refs.bodyFileInput?.click()">
            上传文件
          </button>
        </div>
        <el-input v-if="!fileName" v-model="outline" type="textarea" :rows="8"
          placeholder="粘贴或输入文章大纲，每行一个要点……" />
        <div v-else>
          <div v-if="fileUploading" style="display: flex; align-items: center; justify-content: center; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
            <el-icon class="spin" style="margin-right: 8px;"><Loading /></el-icon>
            <span class="text-sm text-ink-3">正在提取文件内容…</span>
          </div>
          <div v-else style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                <el-icon class="text-clay"><Document /></el-icon> {{ fileName }}
                <span v-if="fileText" class="text-xs text-ink-4">· {{ fileText.length }} 字</span>
              </span>
              <button @click="removeFile()" class="btn-text text-sm">移除</button>
            </div>
            <div v-if="fileText" class="text-xs text-ink-4" style="margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5;">
              {{ fileText.slice(0, 200) }}…
            </div>
          </div>
        </div>
        <div v-if="!fileName" class="dropzone" :class="{ 'dropzone-active': dragOver }"
          @click="$refs.bodyFileInput?.click()"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop="handleFileDrop"
          style="margin-top: 12px;">
          <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
          <div class="text-sm font-medium">或拖拽上传 PDF / Word / TXT / MD</div>
        </div>
        <input ref="bodyFileInput" type="file" accept=".pdf,.docx,.txt,.md" style="display:none"
          @change="handleFileUpload" />
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

    <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate">
      <template v-if="progress.isRunning.value">
        <el-icon class="spin"><Loading /></el-icon> 正在撰写正文…
      </template>
      <template v-else>生成正文</template>
    </button>
    <p v-if="!canGenerate" class="text-xs text-ink-4" style="text-align: center; margin-top: 10px;">先填入大纲即可开始</p>

    <!-- Agent 进度 -->
    <div v-if="progress.isRunning.value" style="margin-top: 24px;" class="fade-in">
      <AgentStatusBar
        v-for="(step, idx) in progress.steps.value"
        :key="idx"
        :agent-name="step.agent"
        :action="step.action"
        :avatar="step.avatar"
        :is-active="idx === progress.currentStepIndex.value"
        :show-progress="idx === progress.currentStepIndex.value"
        :percent="idx === progress.currentStepIndex.value ? progress.stepPercent.value : (idx < progress.currentStepIndex.value ? 100 : 0)"
        class="mb-2"
      />
    </div>

    <div v-if="progress.error.value" class="card" style="margin-top: 16px; padding: 16px; border-color: var(--crimson);">
      <p class="text-sm" style="color: var(--crimson);">{{ progress.error.value }}</p>
    </div>

    <!-- 结果 -->
    <div v-if="result && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
      <PipelineStepper current="body" />
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">生成正文</h2>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 重新生成
        </button>
      </div>
      <div class="card" style="padding: 32px;">
        <!-- 统计栏 -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 18px; border-bottom: 1px solid var(--line);">
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span class="badge badge-success">{{ result.final_word_count || result.final_text?.replace(/\s/g, '').length || 0 }} 字</span>
            <span class="badge badge-warning">已去 AI 味</span>
            <span v-if="result.rewrite_count" class="badge badge-info">改写 {{ result.rewrite_count }} 处</span>
            <span v-if="result.diagnosis?.total_score" class="badge badge-clay">
              评分 {{ result.diagnosis.total_score.toFixed(1) }}
            </span>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn-text btn-sm" @click="copyText(result.final_text || '')">
              <el-icon :size="15"><CopyDocument /></el-icon> 复制正文
            </button>
            <button class="btn-clay btn-sm" @click="goToTitle">
              生成标题 <el-icon :size="14"><ArrowRight /></el-icon>
            </button>
          </div>
        </div>

        <!-- 诊断摘要 -->
        <div v-if="result.diagnosis" style="margin-bottom: 20px; padding: 16px; background: var(--bone); border-radius: var(--r-md);">
          <div class="text-xs text-ink-4 font-semibold" style="margin-bottom: 8px; letter-spacing: .05em;">诊断报告</div>
          <div class="text-sm text-ink-2" style="margin-bottom: 6px;">{{ result.diagnosis.recommended_action }}</div>
          <div v-if="result.diagnosis.medium_priority?.length" class="text-xs text-ink-4">
            建议优化：{{ result.diagnosis.medium_priority.join('、') }}
          </div>
        </div>

        <!-- 正文 -->
        <article style="font-family: var(--serif); font-size: 17px; line-height: 1.95; color: var(--ink-2); white-space: pre-wrap;">
          {{ result.final_text }}
        </article>

        <!-- 金句 -->
        <div v-if="result.gold_sentences?.length" style="margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--line);">
          <div class="text-xs text-ink-4 font-semibold" style="margin-bottom: 10px; letter-spacing: .05em;">金句摘要</div>
          <div v-for="gs in result.gold_sentences" :key="gs.sentence_id"
            style="padding: 10px 14px; margin-bottom: 8px; background: var(--clay-tint); border-radius: var(--r-sm); border-left: 3px solid var(--clay);">
            <div class="text-sm font-serif" style="color: var(--ink); font-style: italic;">"{{ gs.content }}"</div>
            <div class="text-xs text-ink-4" style="margin-top: 4px;">{{ gs.sentence_type }} · {{ gs.location }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Edit, Loading, Refresh, CopyDocument, ArrowRight, Check, Upload } from '@element-plus/icons-vue'
import PipelineStepper from '@/components/creation/PipelineStepper.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api, { uploadFile } from '@/api/api'

const route = useRoute()
const router = useRouter()
const progress = useAgentProgress()

const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const outline = ref(route.query.outline || '')
const fileName = ref('')
const fileText = ref('')
const fileUploading = ref(false)
const preference = ref('')
const result = ref(null)

const canGenerate = computed(() => {
  const hasContent = fileName.value ? !!fileText.value : outline.value.trim().length > 4
  return hasContent && !progress.isRunning.value
})

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

const dragOver = ref(false)

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

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip : chip
  }
}

watch(() => progress.result.value, (data) => {
  if (data?.final_text) {
    result.value = data
  }
})

const handleGenerate = async () => {
  result.value = null
  progress.stop()

  const outlineContent = fileName.value ? fileText.value : outline.value

  try {
    const res = await api.post('/content-generation/generate-adhoc', {
      outline_text: outlineContent,
      title: outlineContent.split('\n')[0]?.slice(0, 80) || '未命名文章',
      preference: preference.value,
    }, { timeout: 10000 })

    const runId = res?.run_id || res?.data?.run_id
    if (!runId) {
      ElMessage.error('未能获取任务 ID')
      return
    }

    progress.start(`/api/v1/content-generation/stream/${runId}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
  }
}

const goToTitle = () => {
  router.push({ path: '/creation/title', query: { body: (result.value?.final_text || '').slice(0, 500) } })
}

const copyText = (text) => {
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制')
}

onUnmounted(() => {
  progress.stop()
})
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
.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.type-chip { display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--paper); color: #6B6862; border: 1px solid var(--line); cursor: pointer; transition: all 0.15s; }
.type-chip:hover { background: #F0EDE3; color: var(--ink); }
.type-chip-active { background: var(--clay); color: #fff; border-color: var(--clay); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
