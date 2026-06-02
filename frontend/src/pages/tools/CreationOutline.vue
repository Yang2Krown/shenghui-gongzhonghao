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
          <div v-else-if="source.kind === 'link'" style="position: relative;">
            <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
            <el-input v-model="source.url" placeholder="粘贴文章链接" style="padding-left: 38px;" />
          </div>
          <div v-else-if="source.kind === 'file'">
            <div v-if="source.fileName" style="display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
              <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                <el-icon class="text-clay"><Document /></el-icon> {{ source.fileName }}
              </span>
              <button @click="source.fileName = ''" class="btn-text text-sm">移除</button>
            </div>
            <div v-else class="dropzone" @click="$refs[`fileInput${index}`]?.click()">
              <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
              <div class="text-sm font-medium">点击上传 PDF / Word / TXT</div>
            </div>
            <input :ref="`fileInput${index}`" type="file" accept=".pdf,.doc,.docx,.txt" class="hidden"
              @change="(e) => source.fileName = e.target.files?.[0]?.name || ''" />
          </div>
        </div>
        <button @click="sources.push({ kind: 'text', text: '', url: '', fileName: '' })" class="btn-ghost" style="border-style: dashed; margin-top: 8px;">
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
    <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate">
      <template v-if="progress.isRunning.value">
        <el-icon class="spin"><Loading /></el-icon> 正在搭建结构…
      </template>
      <template v-else>生成大纲</template>
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

    <!-- 错误提示 -->
    <div v-if="progress.error.value" class="card" style="margin-top: 16px; padding: 16px; border-color: var(--crimson);">
      <p class="text-sm" style="color: var(--crimson);">{{ progress.error.value }}</p>
    </div>

    <!-- 结果 -->
    <div v-if="result && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
      <PipelineStepper current="outline" />
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">文章大纲</h2>
          <span class="text-sm text-ink-4">{{ result.sections.length }} 个章节</span>
          <span v-if="result.inspection" class="badge badge-clay" style="font-size: 11px;">
            评分 {{ result.inspection.total_score?.toFixed(1) }}
          </span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 重新生成
        </button>
      </div>
      <div class="card" style="padding: 30px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 18px;">
          <h2 class="text-ink font-serif" style="font-size: 22px; line-height: 1.35; font-weight: 500; flex: 1;">{{ result.title }}</h2>
          <button class="btn-clay btn-sm" style="flex-shrink: 0;" @click="goToBody">
            生成正文 <el-icon :size="14"><ArrowRight /></el-icon>
          </button>
        </div>
        <div style="display: flex; flex-direction: column; gap: 18px;">
          <div v-for="(section, index) in result.sections" :key="index" class="slide-up"
            :style="{ animationDelay: `${index * 60}ms`, display: 'flex', gap: '14px' }">
            <div style="flex-shrink: 0; width: 30px; height: 30px; border-radius: var(--r-sm); background: var(--clay); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; font-family: var(--serif);">
              {{ section.section_number || index + 1 }}
            </div>
            <div :style="{ flex: 1, paddingBottom: index < result.sections.length - 1 ? '18px' : '0', borderBottom: index < result.sections.length - 1 ? '1px solid var(--line)' : 'none' }">
              <h4 class="text-sm font-semibold text-ink">{{ section.title }}</h4>
              <ul style="margin: 8px 0 0; padding-left: 18px;">
                <li v-for="(point, j) in section.core_points" :key="j" class="text-sm text-ink-2" style="margin-bottom: 4px;">{{ point }}</li>
              </ul>
              <div v-if="section.propagation_tags?.length" style="margin-top: 6px; display: flex; gap: 4px; flex-wrap: wrap;">
                <span v-for="tag in section.propagation_tags" :key="tag" class="badge badge-info" style="font-size: 10px;">{{ tag }}</span>
              </div>
            </div>
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
import {
  Document, Delete, Plus, Upload, Link, Edit,
  Loading, Refresh, ArrowRight, Check
} from '@element-plus/icons-vue'
import PipelineStepper from '@/components/creation/PipelineStepper.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api from '@/api/api'

const route = useRoute()
const router = useRouter()
const progress = useAgentProgress()

const sourceKinds = [
  { key: 'text', label: '文字' },
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
]
const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const sources = ref([{ kind: 'text', text: route.query.angle || '', url: '', fileName: '' }])
const preference = ref('')
const result = ref(null)

const filledCount = computed(() => sources.value.filter(s => s.text || s.url || s.fileName).length)
const canGenerate = computed(() => filledCount.value > 0 && !progress.isRunning.value)

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value
      ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip
      : chip
  }
}

// 监听 SSE 结果
watch(() => progress.result.value, (data) => {
  if (data?.sections) {
    result.value = data
  }
})

const handleGenerate = async () => {
  result.value = null
  progress.stop()

  const apiSources = sources.value
    .filter(s => s.text || s.url || s.fileName)
    .map(s => {
      if (s.kind === 'text') return { type: 'text', content: s.text }
      if (s.kind === 'link') return { type: 'link', content: s.url }
      if (s.kind === 'file') return { type: 'file', content: s.fileName || '' }
      return { type: 'text', content: '' }
    })

  try {
    const res = await api.post('/outlines/generate-adhoc', {
      sources: apiSources,
      angle: route.query.angle || '',
      preference: preference.value,
    }, { timeout: 10000 })

    const runId = res?.run_id || res?.data?.run_id
    if (!runId) {
      ElMessage.error('未能获取任务 ID')
      return
    }

    progress.start(`/api/v1/outlines/stream/${runId}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
  }
}

const goToBody = () => {
  router.push({ path: '/creation/body', query: { outline: result.value?.title } })
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
.src-card { position: relative; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 16px 18px 16px 20px; overflow: hidden; transition: border-color .18s, box-shadow .18s; }
.src-card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: linear-gradient(var(--clay-soft), var(--clay)); opacity: .55; }
.src-card:focus-within { border-color: var(--clay-soft); box-shadow: var(--sh-2); }
.src-card:focus-within::before { opacity: 1; }
.src-number { width: 26px; height: 26px; border-radius: 8px; background: var(--clay); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; font-family: var(--serif); }
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
</style>
