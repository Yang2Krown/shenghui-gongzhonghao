<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-sheet" @click.stop>
      <div class="modal-top">
        <h3>添加训练素材</h3>
        <button class="modal-close-btn" @click="$emit('close')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="modal-tabs">
        <button :class="['mtab', { active: tab === 'text' }]" @click="tab = 'text'">粘贴文字</button>
        <button :class="['mtab', { active: tab === 'file' }]" @click="tab = 'file'">
          上传文件
          <span class="mtab-badge">PDF/DOCX/图片</span>
        </button>
      </div>

      <!-- 标题只在粘贴文字时显示 -->
      <div v-if="tab === 'text'" class="modal-field">
        <label>标题（选填）</label>
        <input
          class="modal-input"
          v-model="title"
          placeholder="例如：我的一篇代表作品"
        />
      </div>

      <!-- Text Tab -->
      <div v-if="tab === 'text'" class="modal-field">
        <label>
          粘贴你写过的内容
          <span class="field-hint">越完整越好，至少 200 字</span>
        </label>
        <textarea
          class="modal-textarea"
          v-model="text"
          :rows="8"
          placeholder="粘贴你写过的内容，至少 200 字效果更好"
        />
        <div class="word-hint">{{ text.length }} 字</div>
      </div>

      <!-- File Tab -->
      <div v-if="tab === 'file'" class="modal-field">
        <label>
          上传文件
          <span class="field-hint">支持 PDF / DOCX 格式</span>
        </label>
        <div v-if="!file" class="file-drop-zone">
          <div class="file-drop-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <p class="file-drop-text">拖拽文件到此处，或 <span class="file-drop-browse">点击选择文件</span></p>
          <p class="file-drop-hint">PDF / DOCX / 图片，建议单文件 20MB 以内</p>
          <input
            type="file"
            accept=".pdf,.docx,.png,.jpg,.jpeg,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg,image/webp"
            class="file-input-hidden"
            @change="handleFileDrop"
          />
        </div>
        <div v-else class="file-selected-card">
          <div class="file-selected-icon">
            {{ file.name.toLowerCase().endsWith('.pdf') ? '📕' : file.name.toLowerCase().match(/\.(png|jpg|jpeg|webp)$/) ? '🖼️' : '📘' }}
          </div>
          <div class="file-selected-info">
            <div class="file-selected-name">{{ file.name }}</div>
            <div class="file-selected-size">{{ (file.size / 1024 / 1024).toFixed(1) }} MB</div>
          </div>
          <button class="file-remove-btn" @click="file = null" title="移除文件">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="error" class="modal-error">{{ error }}</div>

      <div class="modal-footer">
        <button class="btn-ghost" @click="$emit('close')">取消</button>
        <button class="btn-solid" :disabled="!canSubmit" @click="handleSubmit">
          <template v-if="loading">
            <span v-if="tab === 'file'">正在解析文件…</span>
            <span v-else>处理中…</span>
          </template>
          <template v-else>添加到素材库</template>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { addStyleSource, uploadStyleSourceFile } from '@/api/style'

const emit = defineEmits(['done', 'close'])

const tab = ref('text')
const title = ref('')
const text = ref('')
const file = ref(null)
const loading = ref(false)
const error = ref('')

const canSubmit = computed(() => {
  if (loading.value) return false
  if (tab.value === 'text' && text.value.trim()) return true
  if (tab.value === 'file' && file.value) return true
  return false
})

const handleFileDrop = (e) => {
  const f = e.target?.files?.[0]
  if (!f) return
  const name = f.name.toLowerCase()
  const validExts = ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.webp']
  const isValid = validExts.some(ext => name.endsWith(ext))
  if (!isValid) {
    error.value = '支持 PDF、DOCX、PNG、JPG 格式'
    return
  }
  file.value = f
  error.value = ''
}

const handleSubmit = async () => {
  loading.value = true
  error.value = ''
  try {
    let source
    if (tab.value === 'file' && file.value) {
      source = await uploadStyleSourceFile(file.value, title.value)
    } else {
      source = await addStyleSource({ content_type: 'text', title: title.value, raw_text: text.value })
    }
    emit('done', source)
  } catch (e) {
    error.value = e.message || '添加失败'
  } finally {
    loading.value = false
  }
}
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
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
}

.modal-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.modal-top h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink, #333);
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

.modal-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.mtab {
  flex: 1;
  padding: 10px;
  background: var(--bone, #f5f5f5);
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.mtab.active {
  background: var(--clay-tint, #fdf0ec);
  border-color: var(--clay, #cc785c);
  color: var(--clay, #cc785c);
}

.mtab-badge {
  display: block;
  font-size: 10px;
  color: var(--ink-4, #999);
  margin-top: 2px;
}

.modal-field {
  margin-bottom: 16px;
}

.modal-field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink, #333);
  margin-bottom: 8px;
}

.field-hint {
  font-weight: 400;
  color: var(--ink-4, #999);
  font-size: 12px;
}

.modal-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.modal-input:focus {
  border-color: var(--clay, #cc785c);
}

.modal-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 8px;
  font-size: 14px;
  resize: vertical;
  outline: none;
  font-family: inherit;
  transition: border-color 0.2s;
}

.modal-textarea:focus {
  border-color: var(--clay, #cc785c);
}

.word-hint {
  text-align: right;
  font-size: 12px;
  color: var(--ink-4, #999);
  margin-top: 4px;
}

.file-drop-zone {
  border: 2px dashed var(--line, #e5e5e5);
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.file-drop-zone:hover {
  border-color: var(--clay, #cc785c);
  background: var(--clay-tint, #fdf0ec);
}

.file-input-hidden {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.file-drop-icon {
  color: var(--ink-4, #999);
  margin-bottom: 12px;
}

.file-drop-text {
  font-size: 14px;
  color: var(--ink-3, #666);
}

.file-drop-browse {
  color: var(--clay, #cc785c);
  text-decoration: underline;
}

.file-drop-hint {
  font-size: 12px;
  color: var(--ink-4, #999);
  margin-top: 8px;
}

.file-selected-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bone, #f5f5f5);
  border-radius: 8px;
}

.file-selected-icon {
  font-size: 24px;
}

.file-selected-info {
  flex: 1;
}

.file-selected-name {
  font-size: 14px;
  color: var(--ink, #333);
}

.file-selected-size {
  font-size: 12px;
  color: var(--ink-4, #999);
}

.file-remove-btn {
  background: none;
  border: none;
  color: var(--ink-4, #999);
  cursor: pointer;
  padding: 4px;
}

.file-remove-btn:hover {
  color: #e74c3c;
}

.modal-error {
  padding: 10px 12px;
  background: #fef0f0;
  border-radius: 8px;
  font-size: 13px;
  color: #e74c3c;
  margin-bottom: 16px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

.btn-ghost {
  padding: 10px 20px;
  background: none;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  color: var(--ink-2, #555);
}

.btn-ghost:hover {
  background: var(--bone, #f5f5f5);
}

.btn-solid {
  padding: 10px 20px;
  background: var(--clay, #cc785c);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}

.btn-solid:hover:not(:disabled) {
  background: var(--clay-dark, #b5654a);
}

.btn-solid:disabled {
  background: var(--ink-4, #999);
  cursor: not-allowed;
}
</style>
