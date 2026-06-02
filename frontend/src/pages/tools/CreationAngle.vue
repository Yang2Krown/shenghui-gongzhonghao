<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <!-- Hero -->
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><EditPen /></el-icon>
        创作工具 · 创作角度
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        找到那个<span class="text-clay">没人写过</span>的角度
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        投喂任意信息源 —— 文字、PDF 或链接，可以一次给多个。AI 会替你拆出几个陌生化、有张力的切入口。
      </p>
    </div>

    <!-- 信息源面板 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div class="flex items-center" style="gap: 11px;">
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
            <button v-if="sources.length > 1" @click="removeSource(index)" class="btn-text text-ink-4" style="padding: 4px;">
              <el-icon :size="15"><Delete /></el-icon>
            </button>
          </div>

          <el-input v-if="source.kind === 'text'" v-model="source.text" type="textarea" :rows="4"
            placeholder="粘贴或输入文字内容，如新闻、笔记、观点、数据……" />

          <div v-else-if="source.kind === 'link'" style="position: relative;">
            <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
            <el-input v-model="source.url" placeholder="粘贴文章链接（公众号 / 小红书 / 知乎 / 抖音 等）"
              style="padding-left: 38px;" />
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
              <div class="text-xs text-ink-4" style="margin-top: 2px;">支持拖拽，单文件不超过 20MB</div>
            </div>
            <input :ref="`fileInput${index}`" type="file" accept=".pdf,.doc,.docx,.txt" class="hidden"
              @change="(e) => source.fileName = e.target.files?.[0]?.name || ''" />
          </div>
        </div>
        <button @click="addSource" class="btn-ghost" style="border-style: dashed; margin-top: 8px;">
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
          <button v-for="chip in styleChips" :key="chip" @click="toggleStyleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：写给一线从业者，语气克制但有锋芒，多用具体案例，避免空泛的大词……" />
      </div>
    </div>

    <!-- 生成按钮 -->
    <button class="cta-bar" :disabled="!canGenerate || progress.isRunning.value" @click="handleGenerate">
      <template v-if="progress.isRunning.value">
        <el-icon class="spin"><Loading /></el-icon> 正在发掘角度…
      </template>
      <template v-else>生成创作角度</template>
    </button>
    <p v-if="!canGenerate" class="text-xs text-ink-4" style="text-align: center; margin-top: 10px;">
      至少填写一个信息源即可开始
    </p>

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
    <div v-if="results && !progress.isRunning.value" class="fade-in" style="margin-top: 32px;">
      <PipelineStepper current="angle" />

      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px;">
          <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">推荐角度</h2>
          <span class="text-sm text-ink-4">为你找到 {{ results.length }} 个切入口</span>
        </div>
        <button class="btn-ghost btn-sm" @click="handleGenerate">
          <el-icon :size="15"><Refresh /></el-icon> 换一批
        </button>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div v-for="(angle, index) in results" :key="angle.id || index"
          class="card lift slide-up"
          :style="{ animationDelay: `${index * 70}ms` }"
          style="padding: 22px; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 9px;">
              <span class="font-serif text-clay" style="font-size: 22px; font-weight: 600; line-height: 1;">
                {{ String(index + 1).padStart(2, '0') }}
              </span>
              <span class="badge badge-clay">{{ angle.routine || angle.direction }}</span>
            </div>
            <span class="badge" :class="angle.verdict === 'selected' ? 'badge-success' : angle.verdict === 'backup' ? 'badge-warning' : 'badge-info'">
              {{ angle.verdict === 'selected' ? '推荐' : angle.verdict === 'backup' ? '备选' : angle.verdict }}
            </span>
          </div>
          <h3 class="font-serif text-ink" style="font-size: 19px; line-height: 1.4; font-weight: 600;">{{ angle.title }}</h3>
          <p class="text-sm text-ink-3" style="margin-top: 9px; flex: 1;">{{ angle.summary || angle.value_promise }}</p>
          <div v-if="angle.angle_note" class="text-xs text-ink-4" style="margin-top: 8px; padding: 8px 10px; background: var(--bone); border-radius: var(--r-sm);">
            切入：{{ angle.angle_note }}
          </div>
          <div style="margin-top: 16px; display: flex; gap: 8px; padding-top: 14px; border-top: 1px solid var(--line);">
            <button class="btn-dark btn-sm" @click="goToOutline(angle.title)">
              用此角度写大纲 <el-icon :size="14"><ArrowRight /></el-icon>
            </button>
            <button class="btn-text btn-sm" @click="copyText(angle.title)">
              <el-icon :size="15"><CopyDocument /></el-icon> 复制
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  EditPen, Document, Delete, Plus, Upload, Link,
  Edit, Loading, Refresh, ArrowRight, CopyDocument, Check
} from '@element-plus/icons-vue'
import PipelineStepper from '@/components/creation/PipelineStepper.vue'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import api from '@/api/api'

const router = useRouter()
const progress = useAgentProgress()

const sourceKinds = [
  { key: 'text', label: '文字' },
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
]

const styleChips = ['理性克制', '犀利观点', '亲切口语', '故事化', '干货清单', '反共识']

const sources = ref([{ kind: 'text', text: '', url: '', fileName: '' }])
const preference = ref('')
const results = ref(null)

const filledCount = computed(() =>
  sources.value.filter(s => s.text || s.url || s.fileName).length
)

const canGenerate = computed(() => filledCount.value > 0 && !progress.isRunning.value)

const addSource = () => {
  sources.value.push({ kind: 'text', text: '', url: '', fileName: '' })
}

const removeSource = (index) => {
  sources.value.splice(index, 1)
}

const toggleStyleChip = (chip) => {
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
  if (data?.angles) {
    results.value = data.angles
  }
})

const handleGenerate = async () => {
  results.value = null
  progress.stop()

  // 构造信息源
  const apiSources = sources.value
    .filter(s => s.text || s.url || s.fileName)
    .map(s => {
      if (s.kind === 'text') return { type: 'text', content: s.text }
      if (s.kind === 'link') return { type: 'link', content: s.url }
      if (s.kind === 'file') return { type: 'file', content: s.fileName || '' }
      return { type: 'text', content: '' }
    })

  try {
    // 1. 调用后端获取 run_id
    const res = await api.post('/topic-candidates/mine-adhoc', {
      sources: apiSources,
      preference: preference.value,
    }, { timeout: 10000 })

    const runId = res?.run_id || res?.data?.run_id
    if (!runId) {
      ElMessage.error('未能获取任务 ID')
      return
    }

    // 2. 连接 SSE 流
    progress.start(`/api/v1/topic-candidates/stream/${runId}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err.message || '请求失败')
  }
}

const goToOutline = (angle) => {
  router.push({ path: '/creation/outline', query: { angle } })
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
.tool-hero .kicker {
  display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700;
  letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint);
  border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px;
}
.soft-panel { background: radial-gradient(120% 80% at 100% 0%, rgba(204,120,92,.06) 0%, transparent 55%), var(--paper); }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.src-card {
  position: relative; border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--paper);
  padding: 16px 18px 16px 20px; overflow: hidden; transition: border-color .18s, box-shadow .18s;
}
.src-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: linear-gradient(var(--clay-soft), var(--clay)); opacity: .55;
}
.src-card:focus-within { border-color: var(--clay-soft); box-shadow: var(--sh-2); }
.src-card:focus-within::before { opacity: 1; }
.src-number { width: 26px; height: 26px; border-radius: 8px; background: var(--clay); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; font-family: var(--serif); }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.cta-bar {
  width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px;
  background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s;
}
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
