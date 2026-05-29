<template>
  <div class="multi-source">
    <div v-for="(s, i) in sources" :key="i" class="source-card animate-slide-up">
      <div class="source-header">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="source-num">{{ i + 1 }}</span>
          <div style="display: flex; gap: 6px;">
            <button v-for="k in kinds" :key="k.key" @click="updateKind(i, k.key)"
              :class="['chip', s.kind === k.key && 'chip-active']" style="padding: 4px 11px;">
              {{ k.label }}
            </button>
          </div>
        </div>
        <button v-if="sources.length > 1" class="btn btn-text btn-sm" style="color: var(--ink-4);" @click="remove(i)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>
        </button>
      </div>

      <textarea v-if="s.kind === 'text'" class="textarea-field" rows="4"
        placeholder="粘贴或输入文字内容，如新闻、笔记、观点、数据……"
        :value="s.text" @input="update(i, { text: $event.target.value })" />

      <div v-else-if="s.kind === 'link'" style="position: relative;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-4)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; left: 13px; top: 13px;"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>
        <input class="input-field" style="padding-left: 38px;" placeholder="粘贴文章链接（公众号 / 小红书 / 知乎 / 抖音 等）"
          :value="s.url" @input="update(i, { url: $event.target.value })" />
      </div>

      <div v-else>
        <input :ref="el => fileRefs[i] = el" type="file" accept=".pdf,.doc,.docx,.txt" hidden
          @change="handleFile(i, $event)" />
        <div v-if="s.fileName" class="file-display">
          <span style="display: flex; align-items: center; gap: 9px; font-size: 14px; color: var(--ink-2);">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v5h5M6 3h8l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M8 13h8M8 17h6"/></svg>
            {{ s.fileName }}
          </span>
          <button class="btn btn-text btn-sm" @click="update(i, { fileName: '' })">移除</button>
        </div>
        <div v-else class="dropzone" @click="fileRefs[i]?.click()">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="margin: 0 auto 6px; display: block;"><path d="M12 16V4M7 9l5-5 5 5M5 18v2a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2"/></svg>
          <div style="font-size: 14px; font-weight: 500;">点击上传 PDF / Word / TXT</div>
          <div style="font-size: 12px; color: var(--ink-4); margin-top: 2px;">支持拖拽，单文件不超过 20MB</div>
        </div>
      </div>
    </div>

    <button class="btn btn-ghost" style="border-style: dashed; align-self: flex-start;" @click="add">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
      添加信息源
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  sources: { type: Array, default: () => [{ kind: 'text', text: '', url: '', fileName: '' }] }
})

const emit = defineEmits(['update'])

const fileRefs = ref({})

const kinds = [
  { key: 'text', label: '文字' },
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
]

const update = (i, patch) => {
  const next = props.sources.map((s, idx) => idx === i ? { ...s, ...patch } : s)
  emit('update', next)
}

const updateKind = (i, kind) => {
  update(i, { kind, text: '', url: '', fileName: '' })
}

const remove = (i) => {
  emit('update', props.sources.filter((_, idx) => idx !== i))
}

const add = () => {
  emit('update', [...props.sources, { kind: 'text', text: '', url: '', fileName: '' }])
}

const handleFile = (i, e) => {
  update(i, { fileName: e.target.files?.[0]?.name || '' })
}
</script>

<style scoped>
.multi-source {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-card {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--paper);
  padding: 14px;
}

.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
}

.source-num {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--clay-tint);
  color: var(--clay-deep);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

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

.chip:hover {
  border-color: var(--clay-soft);
  color: var(--ink);
}

.chip-active {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}

.textarea-field {
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
  line-height: 1.6;
  resize: none;
}

.textarea-field:focus {
  border-color: var(--clay);
  box-shadow: 0 0 0 3px rgba(204,120,92,0.12);
}

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

.file-display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 14px;
  background: var(--bone);
  border-radius: var(--r-md);
}

.dropzone {
  border: 1px dashed var(--line);
  border-radius: var(--r-lg);
  background: var(--paper);
  padding: 22px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--ink-3);
}

.dropzone:hover {
  border-color: var(--clay);
  background: var(--clay-tint);
  color: var(--clay-deep);
}

.animate-slide-up {
  animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1) both;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
