<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><ChatDotSquare /></el-icon>
        创作工具 · 标题生成
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        写一个让人<span class="text-clay">忍不住点开</span>的标题
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        给定正文 —— 可以是文字、链接或文档，AI 会生成多个候选标题并按吸引力打分。
      </p>
    </div>

    <!-- 正文来源 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">正文来源</div>
            <div class="text-xs text-ink-4">支持文字 / 链接 / 文档</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div class="seg" style="margin-bottom: 16px;">
          <button v-for="m in inputModes" :key="m.key" @click="mode = m.key"
            :class="['seg-btn', { 'seg-btn-active': mode === m.key }]">
            {{ m.label }}
          </button>
        </div>
        <el-input v-if="mode === 'text'" v-model="value" type="textarea" :rows="8"
          placeholder="粘贴文章正文……" />
        <div v-else-if="mode === 'link'" style="position: relative;">
          <el-icon :size="17" style="position: absolute; left: 14px; top: 14px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
          <el-input v-model="value" placeholder="粘贴文章链接" style="padding-left: 40px;" />
        </div>
        <div v-else>
          <div v-if="fileName" style="display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
            <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
              <el-icon class="text-clay"><Document /></el-icon> {{ fileName }}
            </span>
            <button @click="fileName = ''" class="btn-text text-sm">移除</button>
          </div>
          <div v-else class="dropzone" @click="$refs.fileInput?.click()">
            <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
            <div class="text-sm font-medium">点击上传 PDF / Word / TXT</div>
          </div>
          <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.txt" class="hidden"
            @change="(e) => fileName = e.target.files?.[0]?.name || ''" />
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
          placeholder="例如：风格克制不标题党，控制在 20 字内，突出反差感……" />
      </div>
    </div>

    <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate">
      <template v-if="progress.isRunning.value">
        <el-icon class="spin"><Loading /></el-icon> 正在打磨标题…
      </template>
      <template v-else>生成标题</template>
    </button>

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
      <PipelineStepper current="title" />
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">推荐标题</h2>
          <span class="text-sm text-ink-4">按综合评分排序</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <!-- Top 推荐 -->
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div v-for="(rec, index) in result.recommendations" :key="rec.rank || index"
          class="card lift slide-up" :style="{ padding: '18px 22px', display: 'flex', alignItems: 'center', gap: '18px', animationDelay: `${index * 50}ms` }">
          <div style="flex-shrink: 0; text-align: center; width: 54px;">
            <div class="font-serif" :style="{ fontSize: '26px', fontWeight: 600, color: (rec.final_score || rec.score) >= 7 ? 'var(--clay)' : 'var(--ink-3)', lineHeight: 1 }">
              {{ (rec.final_score || rec.score || 0).toFixed(1) }}
            </div>
            <div class="text-xs text-ink-4" style="margin-top: 3px;">综合分</div>
          </div>
          <div style="width: 1px; align-self: stretch; background: var(--line);"></div>
          <div style="flex: 1;">
            <h3 class="font-serif text-ink" style="font-size: 18px; line-height: 1.4; font-weight: 600;">{{ rec.title }}</h3>
            <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
              <span v-if="rec.method" class="badge badge-clay">{{ rec.method }}</span>
              <span v-if="rec.b_score" class="badge badge-info">评审 {{ rec.b_score.toFixed(1) }}</span>
              <span v-if="rec.c_click_willingness" class="badge badge-success">点击意愿 {{ rec.c_click_willingness.toFixed(1) }}</span>
            </div>
            <p v-if="rec.reason" class="text-xs text-ink-4" style="margin-top: 6px;">{{ rec.reason }}</p>
          </div>
          <button class="btn-text btn-sm" @click="copyText(rec.title)">
            <el-icon :size="15"><CopyDocument /></el-icon> 复制
          </button>
        </div>
      </div>

      <!-- 全部候选（可展开） -->
      <details v-if="result.candidates?.length" style="margin-top: 20px;">
        <summary class="text-sm text-ink-4 font-semibold cursor-pointer" style="padding: 8px 0; letter-spacing: .03em;">
          查看全部 {{ result.candidates.length }} 个候选标题
        </summary>
        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px;">
          <div v-for="c in result.candidates" :key="c.id"
            style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid var(--line); border-radius: var(--r-md);"
            :style="{ opacity: c.is_eliminated ? 0.45 : 1 }">
            <span class="font-serif text-sm" :style="{ color: c.is_eliminated ? 'var(--ink-4)' : 'var(--clay)', fontWeight: 600, width: '36px', textAlign: 'center' }">
              {{ c.final_score?.toFixed(1) || '-' }}
            </span>
            <span style="flex: 1;" class="text-sm" :style="{ textDecoration: c.is_eliminated ? 'line-through' : 'none', color: c.is_eliminated ? 'var(--ink-4)' : 'var(--ink)' }">
              {{ c.title }}
            </span>
            <span v-if="c.method" class="text-xs text-ink-4">{{ c.method }}</span>
            <span v-if="c.is_eliminated" class="text-xs" style="color: var(--crimson);">已淘汰</span>
            <button v-else class="btn-text btn-sm" @click="copyText(c.title)" style="padding: 2px 6px;">
              <el-icon :size="13"><CopyDocument /></el-icon>
            </button>
          </div>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotSquare, Document, Link, Upload, Edit, Loading, Refresh, CopyDocument, Check } from '@element-plus/icons-vue'
import PipelineStepper from '@/components/creation/PipelineStepper.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api from '@/api/api'

const progress = useAgentProgress()

const inputModes = [
  { key: 'text', label: '文字' },
  { key: 'link', label: '链接' },
  { key: 'file', label: '文档' },
]
const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const mode = ref('text')
const value = ref('')
const fileName = ref('')
const preference = ref('')
const result = ref(null)

const canGenerate = computed(() => {
  const hasContent = mode.value === 'file' ? !!fileName.value : value.value.trim().length > 10
  return hasContent && !progress.isRunning.value
})

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip : chip
  }
}

watch(() => progress.result.value, (data) => {
  if (data?.recommendations) {
    result.value = data
  }
})

const handleGenerate = async () => {
  result.value = null
  progress.stop()

  const content = value.value.trim()
  if (!content || content.length < 10) {
    ElMessage.warning('请输入至少 10 个字符的正文内容')
    return
  }

  try {
    const res = await api.post('/standalone-title/generate', {
      content: content,
    }, { timeout: 10000 })

    const runId = res?.run_id || res?.data?.run_id
    if (!runId) {
      ElMessage.error('未能获取任务 ID')
      return
    }

    progress.start(`/api/v1/standalone-title/stream/${runId}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
  }
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
.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
.slide-up { animation: slideUp .3s cubic-bezier(.32,.72,0,1) both; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.lift { transition: transform .2s cubic-bezier(.32,.72,0,1), box-shadow .2s, border-color .2s; }
.lift:hover { transform: translateY(-3px); box-shadow: var(--sh-3); border-color: var(--clay-soft); }
</style>
