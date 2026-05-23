<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-sheet preview-sheet" @click.stop>
      <div class="modal-top">
        <div>
          <h3>风格预览</h3>
          <p class="preview-subtitle">AI 正在用你的风格写作：<b>{{ profile?.signature }}</b></p>
        </div>
        <button class="modal-close-btn" @click="$emit('close')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="preview-topic-bar">
        <span class="preview-topic-label">主题：</span>
        <div class="preview-chips">
          <button
            v-for="t in PREVIEW_TOPICS"
            :key="t"
            :class="['pchip', { active: topic === t && !custom }]"
            @click="selectTopic(t)"
          >
            {{ t }}
          </button>
        </div>
        <input
          class="preview-custom-input"
          placeholder="自定义主题…"
          v-model="custom"
          @keydown.enter="custom.trim() && generate(custom.trim())"
        />
        <button class="btn-regen" @click="generate(effectiveTopic)" :disabled="loading">
          {{ loading ? '…' : '换一个' }}
        </button>
      </div>

      <div class="preview-body">
        <div v-if="loading" class="preview-loading">
          <div class="spinner"></div>
          <span>AI 正在用你的风格写作…</span>
        </div>
        <div v-else class="preview-content" v-html="renderedResult"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { previewStyle } from '@/api/style'
import { marked } from 'marked'

const props = defineProps({
  profile: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['close'])

const PREVIEW_TOPICS = ['重疾险避坑', '医疗险怎么选', '给父母配保险', '年金险和储蓄险', '百万医疗险']

const topic = ref(PREVIEW_TOPICS[0])
const custom = ref('')
const result = ref('')
const loading = ref(false)

const effectiveTopic = computed(() => custom.value.trim() || topic.value)

const renderedResult = computed(() => {
  if (!result.value) return ''
  return marked(result.value)
})

const selectTopic = (t) => {
  topic.value = t
  custom.value = ''
  generate(t)
}

const generate = async (t) => {
  loading.value = true
  result.value = ''
  try {
    const res = await previewStyle(t || topic.value)
    result.value = res.content || ''
  } catch (e) {
    result.value = '生成失败: ' + e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  generate(topic.value)
})
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.modal-sheet {
  background: white;
  border-radius: 16px;
  width: 100%;
  max-width: 640px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
}

.preview-sheet {
  max-width: 700px;
}

.modal-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.modal-top h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink, #333);
}

.preview-subtitle {
  font-size: 13px;
  color: var(--ink-3, #666);
  margin-top: 4px;
}

.modal-close-btn {
  background: none;
  border: none;
  color: var(--ink-4, #999);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.modal-close-btn:hover {
  color: var(--ink, #333);
  background: var(--bone, #f5f5f5);
}

.preview-topic-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.preview-topic-label {
  font-size: 13px;
  color: var(--ink-3, #666);
}

.preview-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pchip {
  padding: 6px 12px;
  background: var(--bone, #f5f5f5);
  border: 1px solid transparent;
  border-radius: 16px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.pchip:hover {
  background: var(--clay-tint, #fdf0ec);
}

.pchip.active {
  background: var(--clay-tint, #fdf0ec);
  border-color: var(--clay, #cc785c);
  color: var(--clay, #cc785c);
}

.preview-custom-input {
  flex: 1;
  min-width: 120px;
  padding: 6px 12px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}

.preview-custom-input:focus {
  border-color: var(--clay, #cc785c);
}

.btn-regen {
  padding: 6px 16px;
  background: var(--bone, #f5f5f5);
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-regen:hover:not(:disabled) {
  background: var(--clay-tint, #fdf0ec);
  border-color: var(--clay, #cc785c);
  color: var(--clay, #cc785c);
}

.btn-regen:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.preview-body {
  min-height: 200px;
}

.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px;
  color: var(--clay, #cc785c);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--line, #e5e5e5);
  border-top-color: var(--clay, #cc785c);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.preview-content {
  padding: 20px;
  background: var(--bone, #fafafa);
  border-radius: 12px;
  line-height: 1.8;
  color: var(--ink, #333);
  font-size: 15px;
}

.preview-content :deep(p) {
  margin-bottom: 12px;
}

.preview-content :deep(p:last-child) {
  margin-bottom: 0;
}

.preview-content :deep(strong) {
  color: var(--clay, #cc785c);
}

.preview-content :deep(ul),
.preview-content :deep(ol) {
  padding-left: 20px;
  margin-bottom: 12px;
}

.preview-content :deep(li) {
  margin-bottom: 4px;
}
</style>
