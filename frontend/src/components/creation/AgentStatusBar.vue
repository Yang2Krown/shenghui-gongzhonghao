<template>
  <div class="agent-status-bar">
    <div class="agent-avatar" :class="{ active: isActive }">
      {{ agentLabel }}
    </div>
    <div class="agent-info">
      <div class="agent-name">{{ agentName }}</div>
      <div class="agent-action">
        {{ action }}
        <span class="typing-cursor" v-if="isActive">▌</span>
      </div>
    </div>
    <div class="progress-wrapper" v-if="showProgress">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: percent + '%' }"></div>
      </div>
      <span class="progress-text">{{ percent.toFixed(2) }}%</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  agentName: { type: String, required: true },
  action: { type: String, default: '' },
  isActive: { type: Boolean, default: false },
  percent: { type: Number, default: 0 },
  showProgress: { type: Boolean, default: false },
})

const agentLabel = computed(() => {
  const name = props.agentName
  if (name.includes('A')) return 'A'
  if (name.includes('B')) return 'B'
  if (name.includes('C')) return 'C'
  if (name.includes('D')) return 'D'
  if (name.includes('Reader') || name.includes('reader')) return 'R'
  return name.charAt(0).toUpperCase()
})
</script>

<style scoped>
.agent-status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  margin-bottom: 16px;
}

.agent-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--clay-tint);
  color: var(--clay-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
  transition: all 0.3s;
}

.agent-avatar.active {
  background: var(--clay);
  color: #fff;
  box-shadow: 0 0 0 3px rgba(204, 120, 92, 0.2);
  animation: pulse-ring 2s ease-in-out infinite;
}

.agent-info {
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 2px;
}

.agent-action {
  font-size: 12px;
  color: var(--ink-3);
  line-height: 1.4;
}

.typing-cursor {
  color: var(--clay);
  animation: blink 1s step-end infinite;
}

.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.progress-track {
  width: 80px;
  height: 4px;
  background: var(--bone);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--clay-deep), var(--clay));
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--clay);
  min-width: 32px;
  text-align: right;
}

@keyframes pulse-ring {
  0%, 100% {
    box-shadow: 0 0 0 3px rgba(204, 120, 92, 0.2);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(204, 120, 92, 0.1);
  }
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
