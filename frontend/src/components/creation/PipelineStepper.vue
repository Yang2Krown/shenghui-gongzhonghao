<template>
  <div class="card slide-up" style="padding: 14px 20px; margin-bottom: 16px; display: flex; align-items: center; gap: 16px;">
    <span class="text-xs text-ink-4 uppercase font-semibold" style="flex-shrink: 0; letter-spacing: .08em;">创作流程</span>
    <div style="display: flex; align-items: center; flex: 1; min-width: 0;">
      <template v-for="(step, index) in visibleSteps" :key="step.id">
        <button
          @click="step.clickable && goTo(step.id)"
          :class="['step-btn', { 'step-btn--done': step.done, 'step-btn--next': step.next, 'step-btn--clickable': step.clickable }]"
        >
          <span :class="['step-circle', { 'step-circle--done': step.done, 'step-circle--next': step.next }]">
            <el-icon v-if="step.done" :size="14"><Check /></el-icon>
            <template v-else>{{ step.globalIndex + 1 }}</template>
          </span>
          <span class="step-label-wrap">
            <span :class="['step-label', { 'step-label--done': step.done, 'step-label--next': step.next }]">
              {{ step.label }}
            </span>
            <span v-if="step.next" class="text-xs text-clay font-semibold">下一步 →</span>
          </span>
        </button>
        <span v-if="index < visibleSteps.length - 1"
          :class="['step-line', { 'step-line--done': step.done }]">
        </span>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Check } from '@element-plus/icons-vue'

const props = defineProps({
  current: { type: String, required: true }
})

const router = useRouter()

const PIPELINE = [
  { id: 'angle', label: '创作角度' },
  { id: 'outline', label: '大纲生成' },
  { id: 'body', label: '正文生成' },
  { id: 'title', label: '标题生成' },
]

const routeMap = {
  angle: '/creation/angle',
  outline: '/creation/outline',
  body: '/creation/body',
  title: '/creation/title',
}

const visibleSteps = computed(() => {
  const startIdx = PIPELINE.findIndex(p => p.id === props.current)
  if (startIdx < 0) return []
  const steps = PIPELINE.slice(startIdx)
  return steps.map((s, i) => ({
    ...s,
    globalIndex: startIdx + i,
    done: i === 0,
    next: i === 1,
    clickable: i > 0,
  }))
})

const goTo = (id) => {
  const path = routeMap[id]
  if (path) router.push(path)
}
</script>

<style scoped>
.step-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  padding: 4px 6px;
  border-radius: var(--r-md);
  cursor: default;
  flex-shrink: 0;
  font-family: inherit;
  transition: background .15s;
}
.step-btn--clickable {
  cursor: pointer;
}
.step-btn--clickable:hover {
  background: var(--bone);
}

.step-circle {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  font-family: var(--serif);
  background: var(--bone);
  color: var(--ink-4);
  border: 1.5px solid transparent;
}
.step-circle--done {
  background: var(--clay);
  color: #fff;
}
.step-circle--next {
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1.5px solid var(--clay);
}

.step-label-wrap {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  text-align: left;
}

.step-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-4);
}
.step-label--done {
  color: var(--ink-2);
}
.step-label--next {
  color: var(--clay-deep);
}

.step-line {
  flex: 1;
  height: 2px;
  min-width: 16px;
  margin: 0 4px;
  background: var(--line);
  border-radius: 2px;
}
.step-line--done {
  background: linear-gradient(90deg, var(--clay), var(--clay-soft));
}

.slide-up {
  animation: slideUp .3s cubic-bezier(.32,.72,0,1) both;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
