<template>
  <div class="tool-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ config.title }}</h1>
        <p class="page-desc">{{ config.desc }}</p>
      </div>
    </div>

    <!-- 转换方向示意 -->
    <div class="direction-card card">
      <div class="platform-chip">
        <span class="platform-dot" :style="{ background: config.from.color }">{{ config.from.dot }}</span>
        {{ config.from.label }}
      </div>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/></svg>
      <div class="platform-chip">
        <span class="platform-dot" :style="{ background: config.to.color }">{{ config.to.dot }}</span>
        {{ config.to.label }}
      </div>
      <span style="margin-left: auto; font-size: 13px; color: var(--ink-4);">保留核心信息，转换语言风格与排版</span>
    </div>

    <!-- 输入 -->
    <div class="card input-card">
      <div class="section-title"><h3>{{ config.inputLabel }}</h3></div>
      <div style="display: flex; gap: 10px; margin-bottom: 16px;">
        <button v-for="m in config.modes" :key="m.key" @click="mode = m.key"
          :class="['chip', mode === m.key && 'chip-active']" style="padding: 8px 16px;">
          {{ m.label }}
        </button>
      </div>
      <div v-if="mode === 'link'" style="position: relative;">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--ink-4)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; left: 14px; top: 14px;"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>
        <input class="input-field" style="padding-left: 40px;" :placeholder="config.linkPlaceholder" v-model="value" />
      </div>
      <textarea v-else class="textarea-field" rows="9" :placeholder="config.textPlaceholder" v-model="value"></textarea>
      <hr class="divider" />
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-clay btn-lg" :disabled="!canSubmit || loading" @click="run">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.8L18.5 9 13.8 10.8 12 15.5 10.2 10.8 5.5 9l4.7-1.2L12 3z"/></svg>
          {{ config.cta }}
        </button>
      </div>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card loading-card">
      <Loading :text="config.loadingText" />
    </div>

    <!-- 结果 -->
    <div v-if="result && !loading" class="animate-fade-in">
      <div v-if="result.title" class="card result-title-card">
        <span class="badge badge-clay" style="margin-bottom: 10px;">标题</span>
        <p class="result-title">{{ result.title }}</p>
      </div>

      <div class="card result-body-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <div class="section-title" style="margin-bottom: 0;"><h3>正文</h3></div>
          <CopyBtn :text="result.body" label="复制正文" />
        </div>
        <div class="result-body">{{ result.body }}</div>
      </div>

      <div v-if="result.tags" class="card result-tags-card">
        <div class="section-title"><h3>推荐标签</h3></div>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
          <span v-for="t in result.tags" :key="t" class="tag-chip">#{{ t }}</span>
        </div>
      </div>

      <div style="display: flex; justify-content: center; gap: 12px;">
        <CopyBtn :text="fullText" label="复制全部" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { post } from '@/api/api'
import CopyBtn from '@/components/shared/CopyBtn.vue'
import Loading from '@/components/shared/Loading.vue'

const props = defineProps({
  config: { type: Object, required: true },
})

const loading = ref(false)
const mode = ref(props.config.modes[0]?.key || 'link')
const value = ref('')
const result = ref(null)

const canSubmit = computed(() => {
  if (mode.value === 'link') return /\w/.test(value.value)
  return value.value.trim().length > 6
})

const fullText = computed(() => {
  if (!result.value) return ''
  const parts = []
  if (result.value.title) parts.push(result.value.title)
  parts.push(result.value.body)
  if (result.value.tags) parts.push(result.value.tags.map(t => '#' + t).join(' '))
  return parts.join('\n\n')
})

const run = async () => {
  loading.value = true
  result.value = null
  try {
    const payload = { mode: mode.value }
    if (mode.value === 'link') payload.url = value.value
    else payload.content = value.value
    const res = await post(props.config.apiEndpoint, payload)
    result.value = res.data
  } catch (e) {
    // 模拟数据
    result.value = props.config.mockResult
  }
  loading.value = false
}
</script>

<style scoped>
.tool-page { max-width: 820px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 30px; line-height: 1.2; font-weight: 500; font-family: var(--serif); color: var(--ink); margin: 0; }
.page-desc { font-size: 14px; color: var(--ink-3); margin-top: 6px; }

.direction-card {
  padding: 16px 24px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px 6px 6px;
  background: var(--bone);
  border-radius: var(--r-pill);
  font-weight: 600;
  font-size: 14px;
  color: var(--ink-2);
}

.platform-dot {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.input-card { padding: 24px; margin-bottom: 20px; }
.section-title { display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; }
.section-title h3 { font-size: 16px; font-weight: 600; color: var(--ink); margin: 0; }

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  border-radius: var(--r-pill);
  padding: 6px 13px;
  font-size: 13px;
  font-weight: 500;
  background: var(--paper);
  color: var(--ink-2);
  border: 1px solid var(--line);
  transition: all 0.15s;
}

.chip:hover { border-color: var(--clay-soft); color: var(--ink); }
.chip-active { background: var(--ink); color: var(--paper); border-color: var(--ink); }

.input-field {
  width: 100%;
  font-family: inherit;
  font-size: 15px;
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 11px 14px;
  outline: none;
  transition: all 0.15s;
}

.input-field:focus {
  border-color: var(--clay);
  box-shadow: 0 0 0 3px rgba(204,120,92,0.12);
}

.textarea-field {
  width: 100%;
  font-family: inherit;
  font-size: 15px;
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 14px;
  outline: none;
  transition: all 0.15s;
  line-height: 1.6;
  resize: none;
}

.textarea-field:focus {
  border-color: var(--clay);
  box-shadow: 0 0 0 3px rgba(204,120,92,0.12);
}

.divider { height: 1px; background: var(--line); border: 0; margin: 20px 0; }
.loading-card { padding: 8px; margin-bottom: 20px; }

.result-title-card {
  padding: 22px;
  margin-bottom: 14px;
  border-color: var(--clay-soft);
  box-shadow: var(--sh-clay);
}

.result-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  margin: 8px 0 0;
}

.result-body-card { padding: 24px; margin-bottom: 14px; }

.result-body {
  white-space: pre-wrap;
  font-size: 15px;
  line-height: 1.85;
  color: var(--ink-2);
  background: var(--bone);
  border-radius: var(--r-md);
  padding: 18px;
}

.result-tags-card { padding: 24px; margin-bottom: 14px; }

.tag-chip {
  padding: 5px 13px;
  background: var(--sand-soft);
  color: #8a6d33;
  border-radius: var(--r-pill);
  font-size: 13px;
  font-weight: 500;
}

.animate-fade-in { animation: fadeIn 0.28s cubic-bezier(0.32, 0.72, 0, 1); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
