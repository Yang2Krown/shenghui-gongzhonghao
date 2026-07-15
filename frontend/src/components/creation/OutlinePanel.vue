<template>
  <div class="outline-panel">
    <!-- Agent 状态提示 -->
    <div v-if="generating" class="mb-6">
      <AgentStatusBar
        v-for="(step, i) in agentSteps"
        :key="i"
        :agent-name="step.agent"
        :action="step.action"
        :avatar="step.avatar"
        :is-active="i === currentStepIndex"
        :show-progress="i === currentStepIndex"
        :percent="i === currentStepIndex ? stepPercent : (i < currentStepIndex ? 100 : 0)"
        :no-transition="progress.noStepTransition.value"
        class="mb-2"
      />
    </div>

    <!-- 空状态：直接生成大纲 -->
    <div v-if="status === 'idle'" class="text-center py-16">
      <div class="mb-4">
        <el-icon :size="48" style="color: var(--line);"><Document /></el-icon>
      </div>
      <h3 class="text-h4 font-sans text-ink mb-2">生成文章大纲</h3>
      <p class="text-ink-3 mb-6">基于选题信息，AI 将生成「引入 → 正文 → 总结」三段式、可直接落笔的大纲</p>
      <div class="flex items-center justify-center gap-2 mb-6">
        <span class="text-sm text-ink-3">目标总字数</span>
        <el-input-number v-model="targetWords" :min="500" :max="8000" :step="100" :controls="false" style="width: 120px;" />
        <span class="text-xs text-ink-4">字（可后续逐节微调）</span>
      </div>
      <el-button type="primary" size="large" @click="generateOutline" :loading="generating">
        生成大纲 <CreditHint :cost="3" />
      </el-button>
    </div>

    <!-- 生成中 -->
    <div v-if="status === 'generating'" class="text-center py-8">
      <p class="text-ink-3">大纲生成中，请稍候...</p>
    </div>

    <!-- 失败 -->
    <div v-if="status === 'failed'" class="text-center py-16">
      <el-icon :size="48" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
      <h3 class="text-h4 font-sans text-ink mt-4 mb-2">生成失败</h3>
      <p class="text-ink-3 mb-6">{{ errorMessage }}</p>
      <el-button @click="generateOutline()">重试</el-button>
    </div>

    <!-- 完成：左右分栏 -->
    <div v-if="showOutlineResult" class="outline-result-split">
      <!-- 左侧：大纲内容 -->
      <div class="result-left">
        <div class="card p-5 mb-4">
          <div class="flex items-center justify-between mb-3 gap-3">
            <h3 class="text-h3 font-sans text-ink flex-1 min-w-0 break-words">{{ outline.title }}</h3>
            <div class="flex items-center gap-3 flex-shrink-0">
              <span :class="outline.passed === 'passed' ? 'badge-success' : 'badge-warning'">
                {{ outline.passed === 'passed' ? '通过' : '未通过' }}
              </span>
              <span class="text-2xl font-bold" :class="getScoreColor(outline.total_score)">
                {{ outline.total_score?.toFixed(1) || '-' }}
              </span>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <div class="flex flex-wrap gap-4 text-sm text-ink-3">
              <span v-if="outline.direction">{{ outline.direction }}</span>
              <span v-if="outline.routine">{{ outline.routine }}</span>
              <span>{{ outline.section_count }} 节</span>
              <span>{{ outline.total_words }} 字</span>
            </div>
            <!-- 视图切换 -->
            <div class="flex items-center gap-2">
              <el-button size="small" @click="copyAllOutline">
                <el-icon class="mr-1"><DocumentCopy /></el-icon>复制全部
              </el-button>
              <div class="view-toggle">
                <button
                  class="toggle-btn"
                  :class="{ active: viewMode === 'edit' }"
                  @click="viewMode = 'edit'"
                >编辑</button>
                <button
                  class="toggle-btn"
                  :class="{ active: viewMode === 'preview' }"
                  @click="viewMode = 'preview'"
                >预览</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 3 个候选大纲切换（Agent A 生成，B 默认选中） -->
        <div v-if="outline.candidates?.length > 1" class="candidate-chips">
          <div class="text-xs text-ink-4 mb-2">选择大纲方案</div>
          <div class="flex gap-3">
            <button
              v-for="c in outline.candidates"
              :key="c.candidate_number"
              class="candidate-card"
              :class="{ active: selectedCandidate === c.candidate_number }"
              @click="switchCandidate(c)"
            >
              <div class="flex items-baseline justify-between mb-1">
                <span class="candidate-number">#{{ c.candidate_number }}</span>
                <span class="candidate-hook">{{ c.hook_type }}</span>
              </div>
              <p class="text-xs text-ink-3 leading-relaxed line-clamp-2">
                {{ c.skeleton_feature }}
              </p>
              <div class="text-xs text-ink-4 mt-1">{{ c.total_words }} 字 · {{ c.sections?.length }} 节</div>
            </button>
          </div>
        </div>

        <!-- 编辑模式：一整个文本框，文字 + 字数一起改 -->
        <div v-if="viewMode === 'edit'" class="section-card">
          <p class="text-xs text-ink-4 mb-2">
            用「引入 / 正文 / 总结」分段；每个小节首行写「小标题（300字）」，下面写这节要写什么。改字数直接改括号里的数字。
          </p>
          <el-input
            v-model="editText"
            type="textarea"
            class="outline-editor"
            :autosize="{ minRows: 16, maxRows: 40 }"
            resize="none"
            placeholder="引入&#10;小标题（300字）&#10;这一节要写什么…&#10;&#10;正文&#10;小标题（500字）&#10;这一节要写什么…&#10;&#10;总结&#10;小标题（300字）&#10;怎么收尾升华…"
          />
          <p class="text-xs text-ink-4 mt-2">当前合计约 {{ editTextWordSum }} 字</p>
        </div>

        <!-- 预览模式：最多三块（引入 / 正文 / 总结） -->
        <div v-else class="space-y-4">
          <div
            v-for="part in previewParts"
            :key="part.key"
            class="preview-part"
          >
            <div class="preview-part-head">
              <span class="preview-part-name">{{ part.label }}</span>
              <span class="text-xs text-ink-4">{{ part.words }} 字</span>
            </div>
            <div class="preview-part-body">
              <div
                v-for="(section, idx) in part.sections"
                :key="idx"
                class="preview-sub"
              >
                <div class="flex items-baseline justify-between gap-3">
                  <h4 class="text-base font-semibold text-ink">{{ section.title || '未命名小节' }}</h4>
                  <span class="text-xs text-ink-4 flex-shrink-0">{{ section.word_count || 0 }} 字</span>
                </div>
                <p class="text-sm text-ink-2 mt-1 leading-relaxed">
                  {{ section.description || (section.core_points || []).join('；') || '（无说明）' }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 保存按钮（仅编辑模式） -->
        <div v-if="viewMode === 'edit'" class="mt-6 flex justify-center">
          <el-button type="primary" @click="saveOutline" :loading="saving">
            <el-icon><Document /></el-icon>
            保存编辑
          </el-button>
        </div>
      </div>

      <!-- 右侧：Agent 反馈 -->
      <div class="result-right">
        <AgentFeedbackPanel
          :agents="agentFeedback"
          subtitle="大纲流水线：A 起稿 → B 评审 → C 挑刺 → D 自检"
        />
      </div>
    </div>

    <!-- 固定底部操作栏 -->
    <div v-if="showOutlineResult" class="outline-bottom-bar">
      <div class="bottom-bar-inner">
        <el-button @click="generateOutline" :loading="generating">
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
        <el-button :loading="reevaluating" @click="reevaluateOutline">
          <el-icon><Aim /></el-icon>
          重新评估
        </el-button>
        <el-button type="primary" @click="goNextStep">
          下一步
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, CircleCloseFilled, DocumentCopy, Refresh, ArrowRight, Aim } from '@element-plus/icons-vue'
import AgentStatusBar from './AgentStatusBar.vue'
import AgentFeedbackPanel from './AgentFeedbackPanel.vue'
import outlineApi from '@/api/outline'
import { useAgentProgress } from '@/composables/useAgentProgress'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'

const creditStore = useCreditStore()

const props = defineProps({
  candidateId: { type: [Number, String], default: null },
  outlineId: { type: [Number, String], default: null },
  activeWorkflowStep: { type: String, default: 'angle' },
  autoGenerate: { type: Boolean, default: false },
})

const emit = defineEmits(['complete', 'next-step', 'pipeline-status'])

// 状态
const status = ref('idle') // idle | generating | completed | failed
const generating = ref(false)
const viewMode = ref('preview') // edit | preview
const outline = ref(null)
const targetWords = ref(2500)   // 生成大纲前的目标总字数
const editText = ref('')        // 编辑态：整段大纲文本（文字+字数）
const selectedCandidate = ref(1) // 当前选中的候选编号（1/2/3，B 推荐默认选中）

const PART_LABELS = { intro: '引入', body: '正文', conclusion: '总结' }
const PART_ORDER = ['intro', 'body', 'conclusion']

// sections（结构化）→ 编辑文本
const serializeSections = (sections) => {
  if (!Array.isArray(sections)) return ''
  const blocks = []
  for (const key of PART_ORDER) {
    const inPart = sections.filter((s) => (s.part || 'body') === key)
    if (!inPart.length) continue
    const lines = [PART_LABELS[key]]
    for (const s of inPart) {
      const desc = s.description || (s.core_points || []).join('；')
      lines.push(`${s.title || ''}（${s.word_count || 0}字）`)
      if (desc) lines.push(desc)
      lines.push('')
    }
    blocks.push(lines.join('\n').trimEnd())
  }
  return blocks.join('\n\n')
}

// 编辑文本 → sections（结构化）
const WORD_RE = /[（(]\s*(\d+)\s*字?\s*[）)]\s*$/
const parseEditText = (text) => {
  const sections = []
  let curPart = 'body'
  let cur = null
  let n = 0
  const flush = () => {
    if (cur) {
      cur.description = cur._desc.join(' ').trim()
      delete cur._desc
      sections.push(cur)
      cur = null
    }
  }
  for (const raw of (text || '').split('\n')) {
    const line = raw.trim()
    if (!line) continue
    if (line === '引入') { flush(); curPart = 'intro'; continue }
    if (line === '正文') { flush(); curPart = 'body'; continue }
    if (line === '总结') { flush(); curPart = 'conclusion'; continue }
    const m = line.match(WORD_RE)
    if (m) {
      flush()
      n += 1
      cur = {
        section_number: n,
        part: curPart,
        title: line.replace(WORD_RE, '').trim(),
        word_count: parseInt(m[1], 10) || 0,
        description: '',
        core_points: [],
        propagation_tags: [],
        notes: null,
        _desc: [],
      }
    } else if (cur) {
      cur._desc.push(line)
    } else {
      // 段头后、首个带字数行之前的描述行：当作无标题小节
      n += 1
      cur = { section_number: n, part: curPart, title: '', word_count: 0, description: '', core_points: [], propagation_tags: [], notes: null, _desc: [line] }
    }
  }
  flush()
  return sections
}

// 编辑态合计字数（从文本里所有（N字）求和）
const editTextWordSum = computed(() => {
  let sum = 0
  for (const raw of (editText.value || '').split('\n')) {
    const m = raw.trim().match(WORD_RE)
    if (m) sum += parseInt(m[1], 10) || 0
  }
  return sum
})

// 预览：按 intro/body/conclusion 分三块
const previewParts = computed(() => {
  const secs = outline.value?.sections || []
  return PART_ORDER
    .map((key) => {
      const list = secs.filter((s) => (s.part || 'body') === key)
      return {
        key,
        label: PART_LABELS[key],
        sections: list,
        words: list.reduce((a, s) => a + (s.word_count || 0), 0),
      }
    })
    .filter((p) => p.sections.length)
})

// 把编辑文本解析回 outline.sections（用于预览/保存前同步）
const syncEditToSections = () => {
  if (!outline.value) return
  const parsed = parseEditText(editText.value)
  if (parsed.length) {
    outline.value.sections = parsed
    outline.value.section_count = parsed.length
    outline.value.total_words = parsed.reduce((a, s) => a + (s.word_count || 0), 0)
  }
}

// 切换候选大纲（选中即采用，用原始版）
const switchCandidate = (c) => {
  selectedCandidate.value = c.candidate_number
  // 把选中候选的 sections 写入 outline.sections，作为编辑/预览的当前版本
  outline.value.sections = c.sections
  outline.value.section_count = c.sections.length
  outline.value.total_words = c.sections.reduce((a, s) => a + (s.word_count || 0), 0)
  // 重新序列化编辑文本
  editText.value = serializeSections(c.sections)
}
const errorMessage = ref('')
const saving = ref(false)
const reevaluating = ref(false)
const generationPhase = ref('outline')

// Agent 进度（轮询驱动）
const progress = useAgentProgress()
const agentSteps = progress.steps
const currentStepIndex = progress.currentStepIndex
const stepPercent = progress.stepPercent

// 监听完成结果
watch(() => progress.result.value, (newResult) => {
  if (newResult) {
    outline.value = JSON.parse(JSON.stringify(newResult))
    const bPick = newResult.selected_candidate || 1
    selectedCandidate.value = bPick
    // 默认用 B 选中的那个候选版本，统一展示体验
    if (newResult.candidates?.length) {
      const picked = newResult.candidates.find(c => c.candidate_number === bPick) || newResult.candidates[0]
      outline.value.sections = picked.sections
      outline.value.section_count = picked.sections.length
      outline.value.total_words = picked.sections.reduce((a, s) => a + (s.word_count || 0), 0)
    }
    editText.value = serializeSections(outline.value.sections)
    status.value = 'completed'
    emit('pipeline-status', { outline: 'completed' })
    emit('complete', newResult)
    ElMessage.success('大纲生成完成')
    generating.value = false
    // 刷新积分余额
    creditStore.fetchBalance()
  }
})

// 监听任务错误
watch(() => progress.error.value, (newError) => {
  if (newError) {
    status.value = 'failed'
    errorMessage.value = newError
    generating.value = false
    emit('pipeline-status', { outline: 'failed' })
    ElMessage.error('大纲生成失败')
  }
})

watch(currentStepIndex, (idx) => {
  if (idx < 0) return
  emit('pipeline-status', {
    outline: 'generating',
  })
})

// 加载已有大纲
onMounted(async () => {
  if (props.outlineId) {
    try {
      const res = await outlineApi.getOutline(props.outlineId)
      outline.value = JSON.parse(JSON.stringify(res.data))
      const bPick = outline.value.selected_candidate || 1
      selectedCandidate.value = bPick
      if (outline.value.candidates?.length) {
        const picked = outline.value.candidates.find(c => c.candidate_number === bPick) || outline.value.candidates[0]
        outline.value.sections = picked.sections
        outline.value.section_count = picked.sections.length
        outline.value.total_words = picked.sections.reduce((a, s) => a + (s.word_count || 0), 0)
      }
      editText.value = serializeSections(outline.value.sections)
      status.value = 'completed'
      emit('pipeline-status', { outline: 'completed' })
    } catch (e) {
      console.error('加载大纲失败:', e)
    }
  } else if (props.autoGenerate && props.candidateId && status.value === 'idle') {
    // 从大纲生成页跳转过来，自动开始生成
    generateOutline()
  }
})

onUnmounted(() => {
  progress.stop()
  reevaluateProgress.stop()
})

// 生成大纲
const generateOutline = async () => {
  if (!props.candidateId) {
    ElMessage.warning('缺少选题候选 ID')
    return
  }

  status.value = 'generating'
  generating.value = true
  errorMessage.value = ''
  emit('pipeline-status', { outline: 'generating' })

  try {
    const res = await outlineApi.generateOutline({
      candidate_id: props.candidateId,
      target_words: targetWords.value || undefined,
    })

    const runId = res.data.run_id
    if (runId) {
      progress.start(runId)
    }
  } catch (error) {
    status.value = 'failed'
    errorMessage.value = error?.response?.data?.detail || error?.message || '生成失败，请重试'
    generating.value = false
    emit('pipeline-status', { outline: 'failed' })
    ElMessage.error('大纲生成失败')
  }
}

const getScoreColor = (score) => {
  if (!score) return 'text-ink-3'
  if (score >= 8) return 'text-leaf'
  if (score >= 6) return 'text-sand'
  return 'text-crimson'
}

const showOutlineResult = computed(() =>
  props.activeWorkflowStep !== 'angle'
  && status.value === 'completed'
  && !!outline.value
)

const copyAllOutline = async () => {
  if (!outline.value) return
  const lines = [outline.value.title || '', '']
  let lastPart = null
  outline.value.sections?.forEach((s, i) => {
    const part = s.part || 'body'
    if (part !== lastPart) { lines.push(`【${PART_LABELS[part] || '正文'}】`); lastPart = part }
    lines.push(`${s.title || ''}（${s.word_count || 0}字）`)
    const desc = s.description || (s.core_points || []).join('；')
    if (desc) lines.push(`  ${desc}`)
    lines.push('')
  })
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    ElMessage.success('已复制完整大纲')
  } catch {
    ElMessage.error('复制失败')
  }
}

const copySection = async (section) => {
  const lines = [`${section.section_number}. ${section.title}`]
  section.core_points?.forEach((p) => lines.push(`  · ${p}`))
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    ElMessage.success('已复制本节')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 编辑 → 预览 切换时，把编辑文本解析回结构化 sections
watch(viewMode, (mode, prev) => {
  if (prev === 'edit' && mode === 'preview') {
    syncEditToSections()
  } else if (mode === 'edit' && outline.value) {
    // 进入编辑态时，用最新结构重新序列化（避免预览端改动丢失）
    editText.value = serializeSections(outline.value.sections)
  }
})

// 保存编辑后的大纲
const saveOutline = async () => {
  if (!outline.value?.id) return
  syncEditToSections()
  saving.value = true
  try {
    await outlineApi.updateOutline(outline.value.id, {
      title: outline.value.title,
      sections: outline.value.sections,
    })
    ElMessage.success('大纲已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// 下一步
const goNextStep = () => {
  emit('next-step')
}

// 重新评估大纲（只跑 B→C→D）
const reevaluateProgress = useAgentProgress()
const reevaluateOutline = async () => {
  if (!outline.value?.id) return
  reevaluating.value = true
  try {
    const res = await outlineApi.reevaluateOutline(outline.value.id)
    const runId = res.data.run_id
    if (runId) {
      // 用新的进度轮询获取重新评估结果
      reevaluateProgress.start(runId)
    }
  } catch (e) {
    reevaluating.value = false
    ElMessage.error('重新评估请求失败')
  }
}

// 监听重新评估结果
watch(() => reevaluateProgress.result.value, (newResult) => {
  if (newResult) {
    outline.value = JSON.parse(JSON.stringify(newResult))
    editText.value = serializeSections(outline.value.sections)
    emit('complete', newResult)
    ElMessage.success('重新评估完成')
    reevaluating.value = false
  }
})

watch(() => reevaluateProgress.error.value, (newError) => {
  if (newError) {
    ElMessage.error(`重新评估失败: ${newError}`)
    reevaluating.value = false
  }
})

// ── Agent 反馈数据组装 ────────────────────────────
const D_DIM_LABELS = {
  hook: { label: '开头钩子强度', weight: 20 },
  value_ladder: { label: '价值阶梯递进', weight: 20 },
  rhythm: { label: '节奏感', weight: 15 },
  title_scan: { label: '小标题扫读友好度', weight: 15 },
  trigger: { label: '传播触发点完整度', weight: 20 },
  length: { label: '长度与节数匹配', weight: 10 },
}

const agentFeedback = computed(() => {
  const o = outline.value
  if (!o) return []

  const gp = o.generation_process || {}
  const insp = o.inspection_score || {}
  const reviewObj = o.review || {}
  const criticismObj = o.criticism || {}
  const inspectionObj = o.inspection || {}
  // Agent A
  const agentA = {
    id: 'A',
    code: 'A',
    name: '顾清和 · 大纲创作员',
    role: '生成 3 个大纲候选骨架',
    avatar: '/agents/outline-a.png',
    summary: gp.selected_candidate
      ? `共生成 ${gp.attempts || 1} 轮候选；最终选用候选 #${gp.selected_candidate}。`
      : `共尝试 ${gp.attempts || 1} 轮。`,
  }
  if (o.candidates && o.candidates.length) {
    agentA.issues = o.candidates.map((c) => ({
      location: `候选 #${c.candidate_number} · ${c.hook_type || ''}`,
      text: `${c.skeleton_feature || ''} · ${c.total_words || 0} 字 · ${c.sections?.length || 0} 节`,
    }))
  }

  // Agent B 评审
  const agentB = {
    id: 'B',
    code: 'B',
    name: '陆言之 · 大纲评审员',
    role: '从候选骨架里挑选最佳并补传播标签',
    avatar: '/agents/outline-b.png',
    summary: gp.review_reason || reviewObj.review_reason || '',
  }
  if (reviewObj.selected_candidate) {
    agentB.summary = `选中候选 #${reviewObj.selected_candidate}。${reviewObj.review_reason || ''}`
  }

  // Agent C 挑刺
  const agentC = {
    id: 'C',
    code: 'C',
    name: '刁亦凡 · 大纲挑刺员',
    role: '模拟读者立场指出大纲不顺畅之处',
    avatar: '/agents/outline-c.png',
    summary: criticismObj.overall_feeling || gp.criticism || '',
  }
  const problemSections =
    criticismObj.problem_sections || gp.problem_sections || []
  if (Array.isArray(problemSections) && problemSections.length) {
    agentC.issues = problemSections.map((p) => ({
      location:
        typeof p === 'object'
          ? `第 ${p.section_number || '?'} 节${p.problem_type ? ` · ${p.problem_type}` : ''}${p.title ? ` · ${p.title}` : ''}`
          : '',
      text:
        typeof p === 'object'
          ? [
              p.feedback || p.problem || p.reason || p.description,
              p.suggestion ? `建议：${p.suggestion}` : '',
            ].filter(Boolean).join(' ')
          : String(p),
    }))
  }

  // Agent D 6 维度自检
  const agentD = {
    id: 'D',
    code: 'D',
    name: '简行舟 · 大纲自检员',
    role: '6 维度评分 + 通过/打回判定',
    avatar: '/agents/outline-d.png',
    score: o.total_score ?? inspectionObj.total_score,
    verdict: (o.passed || inspectionObj.verdict) === 'passed' ? '通过' : '未通过',
    verdictPassed: (o.passed || inspectionObj.verdict) === 'passed',
  }
  const dims = []
  Object.entries(D_DIM_LABELS).forEach(([key, conf]) => {
    const dim = insp[key]
    const direct = inspectionObj[`${key}_score`]
    if (dim) {
      dims.push({
        key,
        label: conf.label,
        weight: conf.weight,
        score: dim.score ?? dim.total ?? dim,
        evaluation: dim.evaluation || dim.reason || '',
        suggestions: dim.suggestions || [],
      })
    } else if (typeof direct === 'number') {
      dims.push({ key, label: conf.label, weight: conf.weight, score: direct })
    }
  })
  if (dims.length) agentD.dimensions = dims

  const deductions = inspectionObj.deduction_reasons || []
  if (Array.isArray(deductions) && deductions.length) {
    agentD.issues = deductions.map((d) =>
      typeof d === 'object'
        ? { location: d.dimension || '', text: d.reason || JSON.stringify(d) }
        : { text: String(d) }
    )
  }

  return [agentA, agentB, agentC, agentD]
})
</script>

<style scoped>
/* ── 布局 ─────────────────────────────────────────── */
.outline-result-split {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
}
@media (max-width: 1100px) {
  .outline-result-split { grid-template-columns: 1fr; }
}
.result-left,
.result-right { min-width: 0; }

/* ── 空状态按钮 ───────────────────────────────────── */
.outline-panel :deep(.el-button--large) {
  padding: 12px 32px;
  border-radius: var(--r-md);
  font-size: 15px;
  font-weight: 600;
}

/* ── 字数输入 ─────────────────────────────────────── */
.outline-panel :deep(.el-input-number) {
  --el-input-number-step-button-border-color: var(--line);
}
.outline-panel :deep(.el-input-number .el-input-number__decrease),
.outline-panel :deep(.el-input-number .el-input-number__increase) {
  background: var(--bone);
  border-color: var(--line);
  color: var(--ink-2);
}
.outline-panel :deep(.el-input-number .el-input-number__decrease:hover),
.outline-panel :deep(.el-input-number .el-input-number__increase:hover) {
  color: var(--clay);
}

/* ── 视图切换（pill toggle） ─────────────────────── */
.view-toggle {
  display: inline-flex;
  background: var(--bone);
  border-radius: var(--r-pill);
  padding: 3px;
  flex-shrink: 0;
}
.toggle-btn {
  padding: 4px 14px;
  border: none;
  background: transparent;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3);
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1.4;
}
.toggle-btn.active {
  background: var(--paper);
  color: var(--ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* ── 候选方案切换卡片 ────────────────────────────── */
.candidate-chips {
  margin-bottom: 16px;
}
.candidate-chips .flex.gap-3 {
  gap: 12px;
}

.candidate-card {
  flex: 1;
  min-width: 0;
  text-align: left;
  padding: 14px 16px;
  border: 1.5px solid var(--line);
  border-radius: var(--r-lg);
  background: var(--paper);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(.32, .72, 0, 1);
}
.candidate-card:hover {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-2);
  transform: translateY(-1px);
}
.candidate-card.active {
  border-color: var(--clay);
  background: var(--clay-tint);
  box-shadow: var(--sh-clay);
}
.candidate-card.active:hover {
  box-shadow: 0 10px 28px rgba(204, 120, 92, 0.22);
}

.candidate-number {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}
.candidate-card.active .candidate-number {
  color: var(--clay-deep);
}

.candidate-hook {
  font-size: 11px;
  font-weight: 600;
  color: var(--clay-deep);
  background: var(--bone);
  padding: 2px 8px;
  border-radius: var(--r-pill);
}
.candidate-card.active .candidate-hook {
  background: rgba(204, 120, 92, 0.15);
  color: var(--clay-deep);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── 编辑模式：section-card ──────────────────────── */
.section-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-1);
  padding: 16px 20px;
}

.outline-editor :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink);
  font-family: inherit;
}

/* ── 预览模式：三块（引入/正文/总结） ─────────── */
.preview-part {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-1);
  overflow: hidden;
}
.preview-part-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: var(--bone);
  border-bottom: 1px solid var(--line);
}
.preview-part-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--clay-deep);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.preview-part-body {
  padding: 8px 20px;
}
.preview-sub {
  padding: 12px 0;
}
.preview-sub + .preview-sub {
  border-top: 1px dashed var(--line);
}

/* ── 底部操作栏 ──────────────────────────────────── */
.outline-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 248px;
  right: 0;
  z-index: 100;
  background: var(--paper);
  border-top: 1px solid var(--line);
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);
  height: 65px;
  display: flex;
  align-items: center;
}
.bottom-bar-inner {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px;
  width: 100%;
}

/* ── 通用 badge ──────────────────────────────────── */
.badge-success {
  background: rgba(92, 138, 92, 0.10);
  color: var(--leaf);
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
}
.badge-warning {
  background: var(--sand-soft);
  color: var(--sand);
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
}
</style>
