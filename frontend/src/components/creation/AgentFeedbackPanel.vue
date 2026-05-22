<template>
  <div class="agent-feedback-panel">
    <!-- 标题区 -->
    <div class="panel-header">
      <h3 class="text-h4 font-sans text-ink">Agent 反馈</h3>
      <p class="text-xs text-ink-3 mt-1">{{ subtitle || '四个 Agent 的评审结果与改进建议' }}</p>
    </div>

    <!-- 空状态 -->
    <div v-if="!agents || agents.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="20" stroke="var(--line)" stroke-width="2" stroke-dasharray="4 4"/>
          <path d="M18 24h12M24 18v12" stroke="var(--ink-4)" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <p class="text-sm text-ink-3">尚无 Agent 反馈数据</p>
    </div>

    <!-- 流水线时间轴 -->
    <div v-else class="pipeline">
      <div
        v-for="(agent, i) in agents"
        :key="agent.id || agent.key || i"
        class="pipeline-step"
        :class="{ 'is-expanded': isExpanded(agent, i) }"
      >
        <!-- 时间轴连接线 -->
        <div class="timeline-track">
          <div class="timeline-dot" :class="`dot-${(agent.code || 'x').toLowerCase()}`">
            <span class="dot-letter">{{ agent.code || 'X' }}</span>
          </div>
          <div v-if="i < agents.length - 1" class="timeline-line"></div>
        </div>

        <!-- Agent 卡片 -->
        <div class="agent-card" :class="`card-${(agent.code || 'x').toLowerCase()}`">
          <!-- 卡片头部（可点击折叠） -->
          <div class="card-header" @click="toggle(agent, i)">
            <div class="header-left">
              <span class="agent-name">{{ agent.name }}</span>
              <span v-if="agent.role" class="agent-role">{{ agent.role }}</span>
            </div>
            <div class="header-right">
              <!-- 分数徽章 -->
              <span v-if="typeof agent.score === 'number'" class="score-badge" :class="scoreColorClass(agent.score, agent.scoreMax)">
                {{ formatScore(agent.score) }}
                <span class="score-max">/{{ agent.scoreMax || 10 }}</span>
              </span>
              <!-- 判定标签 -->
              <span v-if="agent.verdict" class="verdict-chip" :class="agent.verdictPassed ? 'verdict-pass' : 'verdict-fail'">
                <span class="verdict-dot"></span>
                {{ agent.verdict }}
              </span>
              <!-- 展开箭头 -->
              <svg class="expand-arrow" :class="{ 'is-rotated': isExpanded(agent, i) }" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>

          <!-- 卡片内容（可折叠） -->
          <transition name="card-body">
            <div v-show="isExpanded(agent, i)" class="card-body">
              <!-- 综述 -->
              <div v-if="agent.summary" class="section summary-section">
                <p class="summary-text">{{ agent.summary }}</p>
              </div>

              <!-- 维度评分明细 -->
              <div v-if="agent.dimensions && agent.dimensions.length" class="section dimensions-section">
                <div class="section-title">评分维度</div>

                <!-- 雷达图 -->
                <div class="radar-container">
                  <svg :viewBox="`0 0 ${svgSize} ${svgSize}`" class="radar-svg">
                    <!-- 背景网格（同心多边形） -->
                    <polygon
                      v-for="level in gridLevels"
                      :key="'g-' + level"
                      :points="gridPolygon(level)"
                      class="radar-grid-line"
                    />
                    <!-- 轴线 -->
                    <line
                      v-for="(pt, idx) in axisPoints"
                      :key="'ax-' + idx"
                      :x1="center" :y1="center"
                      :x2="pt.x" :y2="pt.y"
                      class="radar-axis-line"
                    />
                    <!-- 刻度标签 (2/4/6/8/10) -->
                    <text
                      v-for="level in gridLevels"
                      :key="'t-' + level"
                      :x="center + 4"
                      :y="center - radarRadius * (level / 10) + 4"
                      class="radar-grid-label"
                    >{{ level }}</text>
                    <!-- 数据多边形 -->
                    <polygon
                      :points="dataPolygon"
                      class="radar-data-area"
                    />
                    <!-- 数据点 + 分数气泡 -->
                    <g v-for="(pt, idx) in dataPoints" :key="'dp-' + idx">
                      <circle
                        :cx="pt.x" :cy="pt.y" r="4"
                        class="radar-data-dot"
                      />
                      <rect
                        :x="scoreBubble(agent.dimensions[idx]).x - 16"
                        :y="scoreBubble(agent.dimensions[idx]).y - 9"
                        width="32" height="18" rx="9"
                        class="score-bubble-bg"
                      />
                      <text
                        :x="scoreBubble(agent.dimensions[idx]).x"
                        :y="scoreBubble(agent.dimensions[idx]).y + 4"
                        class="score-bubble-text"
                      >{{ formatScore(agent.dimensions[idx].score) }}</text>
                    </g>
                    <!-- 维度标签 -->
                    <text
                      v-for="(d, idx) in agent.dimensions"
                      :key="'lbl-' + idx"
                      :x="labelPoint(idx).x"
                      :y="labelPoint(idx).y"
                      :text-anchor="labelAnchor(idx)"
                      :dominant-baseline="labelBaseline(idx)"
                      class="radar-dim-label"
                    >{{ shortLabel(d.label) }}</text>
                  </svg>
                </div>
              </div>

              <!-- 三档建议 -->
              <div v-if="agent.priorities" class="section priorities-section">
                <div v-if="agent.priorities.high && agent.priorities.high.length" class="priority-group priority-high">
                  <div class="priority-header">
                    <span class="priority-icon">!</span>
                    <span class="priority-label">高优先级</span>
                  </div>
                  <ul>
                    <li v-for="(s, i) in agent.priorities.high" :key="`h-${i}`">{{ s }}</li>
                  </ul>
                </div>
                <div v-if="agent.priorities.medium && agent.priorities.medium.length" class="priority-group priority-medium">
                  <div class="priority-header">
                    <span class="priority-icon">~</span>
                    <span class="priority-label">中优先级</span>
                  </div>
                  <ul>
                    <li v-for="(s, i) in agent.priorities.medium" :key="`m-${i}`">{{ s }}</li>
                  </ul>
                </div>
                <div v-if="agent.priorities.low && agent.priorities.low.length" class="priority-group priority-low">
                  <div class="priority-header">
                    <span class="priority-icon">-</span>
                    <span class="priority-label">低优先级</span>
                  </div>
                  <ul>
                    <li v-for="(s, i) in agent.priorities.low" :key="`l-${i}`">{{ s }}</li>
                  </ul>
                </div>
              </div>

              <!-- 改进建议 -->
              <div v-if="agent.suggestions && agent.suggestions.length" class="section suggestions-section">
                <div class="section-title">改进建议</div>
                <ul class="suggestion-list">
                  <li v-for="(s, i) in agent.suggestions" :key="i">{{ s }}</li>
                </ul>
              </div>

              <!-- 问题列表 -->
              <div v-if="agent.issues && agent.issues.length" class="section issues-section">
                <div class="section-title">问题点</div>
                <div class="issue-list">
                  <div v-for="(p, i) in agent.issues" :key="i" class="issue-item">
                    <span v-if="p.location" class="issue-loc">{{ p.location }}</span>
                    <span class="issue-text">{{ typeof p === 'string' ? p : (p.text || p.description || p.reason) }}</span>
                  </div>
                </div>
              </div>

              <!-- 自定义插槽 -->
              <slot :name="agent.slot || `agent-${(agent.code || '').toLowerCase()}`" :agent="agent" />
            </div>
          </transition>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  subtitle: { type: String, default: '' },
  defaultExpand: { type: Boolean, default: true },
})

const expandedSet = ref(new Set())

function agentKey(agent, i) {
  return String(agent.id || agent.key || i)
}

function isExpanded(agent, i) {
  return expandedSet.value.has(agentKey(agent, i))
}

function toggle(agent, i) {
  const k = agentKey(agent, i)
  const s = new Set(expandedSet.value)
  if (s.has(k)) s.delete(k)
  else s.add(k)
  expandedSet.value = s
}

watch(
  () => props.agents,
  () => {
    if (props.defaultExpand) {
      expandedSet.value = new Set(
        (props.agents || []).map((a, i) => agentKey(a, i))
      )
    }
  },
  { immediate: true }
)

function formatScore(s) {
  if (s === null || s === undefined || Number.isNaN(Number(s))) return '-'
  const n = Number(s)
  return Number.isInteger(n) ? n.toString() : n.toFixed(1)
}

function formatWeight(w) {
  if (!w && w !== 0) return ''
  const n = Number(w)
  if (n <= 1) return `${(n * 100).toFixed(0)}%`
  return `${n.toFixed(0)}%`
}

function scoreColorClass(s, max = 10) {
  if (s === null || s === undefined) return 'score-na'
  const ratio = Number(s) / (max || 10)
  if (ratio >= 0.8) return 'score-good'
  if (ratio >= 0.6) return 'score-ok'
  return 'score-bad'
}

function scoreBarClass(s, max = 10) {
  if (s === null || s === undefined) return 'bar-na'
  const ratio = Number(s) / (max || 10)
  if (ratio >= 0.8) return 'bar-good'
  if (ratio >= 0.6) return 'bar-ok'
  return 'bar-bad'
}

function barWidth(s, max = 10) {
  if (s === null || s === undefined) return '0%'
  return `${Math.min(100, (Number(s) / (max || 10)) * 100)}%`
}

// ── 雷达图 ──
const svgSize = 320
const radarRadius = 105
const center = svgSize / 2
const gridLevels = [2, 4, 6, 8, 10]

// 多边形顶点（n 边形，从正上方顺时针）
function polygonPoints(n, radius) {
  const pts = []
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2
    pts.push({
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle),
    })
  }
  return pts
}

// 背景网格多边形点串
function gridPolygon(level) {
  const n = currentDimCount.value
  if (!n) return ''
  const r = radarRadius * (level / 10)
  return polygonPoints(n, r).map(p => `${p.x},${p.y}`).join(' ')
}

// 轴线端点
const axisPoints = computed(() => {
  const n = currentDimCount.value
  if (!n) return []
  return polygonPoints(n, radarRadius)
})

// 当前 Agent D 的维度数
const currentDimCount = computed(() => {
  // 从 agents 中找有 dimensions 的那个
  const agent = (props.agents || []).find(a => a.dimensions && a.dimensions.length)
  return agent ? agent.dimensions.length : 0
})

// 数据点坐标
const dataPoints = computed(() => {
  const agent = (props.agents || []).find(a => a.dimensions && a.dimensions.length)
  if (!agent) return []
  const n = agent.dimensions.length
  return agent.dimensions.map((d, i) => {
    const ratio = Math.min(1, (Number(d.score) || 0) / (d.max || 10))
    const r = radarRadius * ratio
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2
    return { x: center + r * Math.cos(angle), y: center + r * Math.sin(angle) }
  })
})

// 数据多边形点串
const dataPolygon = computed(() => {
  return dataPoints.value.map(p => `${p.x},${p.y}`).join(' ')
})

// 标签位置（比轴线端点再远一点）
function labelPoint(idx) {
  const n = currentDimCount.value
  if (!n) return { x: 0, y: 0 }
  const r = radarRadius + 40
  const angle = (Math.PI * 2 * idx) / n - Math.PI / 2
  return { x: center + r * Math.cos(angle), y: center + r * Math.sin(angle) }
}

// 分数气泡位置（在数据点外侧偏移，避免遮挡）
function scoreBubble(dim) {
  if (!dim) return { x: 0, y: 0 }
  const agent = (props.agents || []).find(a => a.dimensions && a.dimensions.length)
  if (!agent) return { x: 0, y: 0 }
  const idx = agent.dimensions.indexOf(dim)
  const n = agent.dimensions.length
  if (idx < 0 || !n) return { x: 0, y: 0 }
  const ratio = Math.min(1, (Number(dim.score) || 0) / (dim.max || 10))
  const r = radarRadius * ratio + 18
  const angle = (Math.PI * 2 * idx) / n - Math.PI / 2
  return { x: center + r * Math.cos(angle), y: center + r * Math.sin(angle) }
}

function labelAnchor(idx) {
  const n = currentDimCount.value
  if (!n) return 'middle'
  const angle = (Math.PI * 2 * idx) / n - Math.PI / 2
  const cos = Math.cos(angle)
  if (Math.abs(cos) < 0.15) return 'middle'
  return cos > 0 ? 'start' : 'end'
}

function labelBaseline(idx) {
  const n = currentDimCount.value
  if (!n) return 'auto'
  const angle = (Math.PI * 2 * idx) / n - Math.PI / 2
  const sin = Math.sin(angle)
  if (sin < -0.5) return 'auto'
  if (sin > 0.5) return 'hanging'
  return 'central'
}

function shortLabel(label) {
  // 截短过长的标签（雷达图空间有限）
  if (!label) return ''
  return label.length > 8 ? label.slice(0, 7) + '…' : label
}
</script>

<style scoped>
.agent-feedback-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  margin-bottom: 20px;
}

/* ── 空状态 ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  gap: 12px;
}

.empty-icon {
  opacity: 0.4;
}

/* ── 流水线 ── */
.pipeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.pipeline-step {
  display: flex;
  gap: 16px;
  position: relative;
}

/* ── 时间轴轨道 ── */
.timeline-track {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 36px;
}

.timeline-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
  box-shadow: 0 0 0 4px var(--paper);
}

.dot-letter {
  font-size: 13px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.02em;
}

.dot-a {
  background: linear-gradient(135deg, var(--clay), var(--clay-deep));
  box-shadow: 0 2px 8px rgba(204, 120, 92, 0.3), 0 0 0 4px var(--paper);
}

.dot-b {
  background: linear-gradient(135deg, var(--pine), #2a4538);
  box-shadow: 0 2px 8px rgba(63, 92, 82, 0.3), 0 0 0 4px var(--paper);
}

.dot-c {
  background: linear-gradient(135deg, var(--sand), #a07a3a);
  box-shadow: 0 2px 8px rgba(196, 155, 92, 0.3), 0 0 0 4px var(--paper);
}

.dot-d {
  background: linear-gradient(135deg, var(--leaf), #3d6b3d);
  box-shadow: 0 2px 8px rgba(92, 138, 92, 0.3), 0 0 0 4px var(--paper);
}

.dot-x {
  background: var(--ink-4);
  box-shadow: 0 0 0 4px var(--paper);
}

.timeline-line {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: var(--line);
  margin: 4px 0;
}

/* ── Agent 卡片 ── */
.agent-card {
  flex: 1;
  min-width: 0;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  margin-bottom: 16px;
  overflow: hidden;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.agent-card:hover {
  box-shadow: var(--sh-2);
}

.agent-card.is-expanded {
  box-shadow: var(--sh-2);
}

.card-a { border-left: 3px solid var(--clay); }
.card-b { border-left: 3px solid var(--pine); }
.card-c { border-left: 3px solid var(--sand); }
.card-d { border-left: 3px solid var(--leaf); }

/* ── 卡片头部 ── */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  user-select: none;
  gap: 12px;
  transition: background 0.15s;
}

.card-header:hover {
  background: var(--ivory);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.agent-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.3;
}

.agent-role {
  font-size: 12px;
  color: var(--ink-3);
  line-height: 1.3;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* ── 分数徽章 ── */
.score-badge {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  padding: 4px 10px;
  border-radius: var(--r-pill);
}

.score-badge .score-max {
  font-size: 11px;
  font-weight: 500;
  opacity: 0.6;
}

.score-good {
  color: var(--leaf);
  background: rgba(92, 138, 92, 0.08);
}

.score-ok {
  color: var(--sand);
  background: rgba(196, 155, 92, 0.08);
}

.score-bad {
  color: var(--crimson);
  background: rgba(184, 84, 80, 0.08);
}

.score-na {
  color: var(--ink-4);
  background: var(--bone);
}

/* ── 判定标签 ── */
.verdict-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: var(--r-pill);
}

.verdict-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.verdict-pass {
  background: rgba(92, 138, 92, 0.1);
  color: var(--leaf);
}

.verdict-pass .verdict-dot {
  background: var(--leaf);
  box-shadow: 0 0 6px rgba(92, 138, 92, 0.4);
}

.verdict-fail {
  background: rgba(184, 84, 80, 0.1);
  color: var(--crimson);
}

.verdict-fail .verdict-dot {
  background: var(--crimson);
  box-shadow: 0 0 6px rgba(184, 84, 80, 0.4);
}

/* ── 展开箭头 ── */
.expand-arrow {
  color: var(--ink-4);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.expand-arrow.is-rotated {
  transform: rotate(180deg);
}

/* ── 卡片内容 ── */
.card-body {
  padding: 0 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 折叠动画 */
.card-body-enter-active,
.card-body-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.card-body-enter-from,
.card-body-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* ── 内容区块 ── */
.section {
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-3);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 10px;
}

/* ── 综述 ── */
.summary-section {
  padding-top: 0;
  border-top: none;
}

.summary-text {
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.7;
  padding: 10px 14px;
  background: var(--ivory);
  border-radius: var(--r-md);
  border-left: 3px solid var(--line);
  margin: 0;
}

/* ── 雷达图 ── */
.radar-container {
  display: flex;
  justify-content: center;
  padding: 4px 0 8px;
}

.radar-svg {
  width: 100%;
  max-width: 340px;
  aspect-ratio: 1;
}

.radar-grid-line {
  fill: none;
  stroke: var(--line);
  stroke-width: 1;
}

.radar-axis-line {
  stroke: var(--line);
  stroke-width: 0.8;
  stroke-dasharray: 3 3;
}

.radar-grid-label {
  font-size: 9px;
  fill: var(--ink-4);
  font-variant-numeric: tabular-nums;
}

.radar-data-area {
  fill: var(--leaf);
  fill-opacity: 0.15;
  stroke: var(--leaf);
  stroke-width: 2;
  stroke-linejoin: round;
  transition: all 0.4s ease;
}

.radar-data-dot {
  fill: var(--leaf);
  stroke: var(--paper);
  stroke-width: 2;
  transition: all 0.4s ease;
}

.radar-dim-label {
  font-size: 12px;
  font-weight: 600;
  fill: var(--ink-2);
}

.score-bubble-bg {
  fill: var(--paper);
  stroke: var(--line);
  stroke-width: 1;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.06));
}

.score-bubble-text {
  font-size: 10px;
  font-weight: 700;
  fill: var(--ink);
  text-anchor: middle;
  font-variant-numeric: tabular-nums;
}

/* ── 三档建议 ── */
.priorities-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.priority-group {
  border-radius: var(--r-md);
  overflow: hidden;
}

.priority-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.03em;
}

.priority-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}

.priority-high {
  background: rgba(184, 84, 80, 0.04);
  border: 1px solid rgba(184, 84, 80, 0.15);
}

.priority-high .priority-header { color: var(--crimson); }
.priority-high .priority-icon { background: var(--crimson); }

.priority-medium {
  background: rgba(196, 155, 92, 0.04);
  border: 1px solid rgba(196, 155, 92, 0.15);
}

.priority-medium .priority-header { color: var(--sand); }
.priority-medium .priority-icon { background: var(--sand); }

.priority-low {
  background: rgba(92, 138, 92, 0.04);
  border: 1px solid rgba(92, 138, 92, 0.15);
}

.priority-low .priority-header { color: var(--leaf); }
.priority-low .priority-icon { background: var(--leaf); }

.priority-group ul {
  margin: 0;
  padding: 0 12px 10px 40px;
  font-size: 13px;
  color: var(--ink-2);
}

.priority-group li {
  list-style: disc;
  margin-bottom: 5px;
  line-height: 1.5;
}

/* ── 改进建议 ── */
.suggestion-list {
  margin: 0;
  padding: 0 0 0 20px;
  font-size: 13px;
  color: var(--ink-2);
}

.suggestion-list li {
  list-style: disc;
  margin-bottom: 5px;
  line-height: 1.5;
}

/* ── 问题列表 ── */
.issue-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.issue-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 10px;
  background: var(--ivory);
  border-radius: var(--r-sm);
  font-size: 13px;
  line-height: 1.5;
}

.issue-loc {
  font-size: 11px;
  color: var(--ink-3);
  font-family: var(--font-mono, monospace);
  background: var(--bone);
  padding: 1px 6px;
  border-radius: var(--r-xs);
  flex-shrink: 0;
  white-space: nowrap;
}

.issue-text {
  color: var(--ink-2);
}
</style>
