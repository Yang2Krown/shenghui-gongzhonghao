<template>
  <div class="fuz" :data-policy="policy">
    <!-- 已选文件态 -->
    <div v-if="modelValue" class="fuz-file">
      <div class="fuz-file-row">
        <span class="fuz-file-name">
          <el-icon class="fuz-ico"><Document /></el-icon>
          <span class="fuz-name-text">{{ modelValue }}</span>
          <span v-if="metaText" class="fuz-meta">· {{ metaText }}</span>
        </span>
        <button type="button" class="fuz-remove" :disabled="uploading" @click="onRemove">移除</button>
      </div>
      <div v-if="previewText" class="fuz-preview">{{ previewText }}</div>
    </div>

    <!-- 解析中态 -->
    <div v-else-if="uploading" class="fuz-loading">
      <el-icon class="is-loading fuz-spin"><Loading /></el-icon>
      <span class="fuz-loading-text">{{ uploadingText }}</span>
    </div>

    <!-- 空态:可点/可拖/可键盘 -->
    <label
      v-else
      class="fuz-drop"
      :class="{ 'fuz-drop-active': dragOver }"
      role="button"
      tabindex="0"
      :aria-label="ariaLabel"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop.prevent="onDrop"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
    >
      <el-icon :size="22" class="fuz-up-ico"><Upload /></el-icon>
      <div class="fuz-up-title">{{ title }}</div>
      <div class="fuz-up-hint">{{ currentPolicy.hint }}</div>
      <input
        ref="inputEl"
        type="file"
        :accept="currentPolicy.accept"
        tabindex="-1"
        style="display:none"
        @change="onPick"
      />
    </label>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Loading, Upload } from '@element-plus/icons-vue'
import { UPLOAD_POLICIES, validateUploadFile } from '@/utils/uploadPolicy'

const props = defineProps({
  /** 当前文件名(空串 = 未选)。配合 @update:modelValue 用 v-model。 */
  modelValue: { type: String, default: '' },
  /** uploadPolicy.js 里的策略名:brief / reference / style / document / cover */
  policy: { type: String, default: 'reference' },
  /** 是否正在上传/解析(显示加载态) */
  uploading: { type: Boolean, default: false },
  /** 已选文件的补充信息,如「1234 字」 */
  metaText: { type: String, default: '' },
  /** 已选文件的内容预览 */
  previewText: { type: String, default: '' },
  /** 上传区标题 */
  title: { type: String, default: '点击或拖拽上传' },
  /** 解析中的提示文案 */
  uploadingText: { type: String, default: '正在提取文件内容…' },
})

const emit = defineEmits(['update:modelValue', 'select', 'remove', 'error'])

const dragOver = ref(false)
const inputEl = ref(null)

const currentPolicy = computed(() => UPLOAD_POLICIES[props.policy] || UPLOAD_POLICIES.reference)
const ariaLabel = computed(() => `${props.title},${currentPolicy.value.hint}`)

const openPicker = (e) => {
  const root = e?.currentTarget
  const input = inputEl.value || root?.querySelector('input[type="file"]')
  input?.click()
}

// 统一入口:无论点击选择还是拖拽,都先客户端校验,通过才 emit
const accept = (file) => {
  if (!file) return
  const err = validateUploadFile(file, props.policy)
  if (err) {
    ElMessage.error(err)
    emit('error', err)
    return
  }
  emit('update:modelValue', file.name)
  emit('select', file)
}

const onPick = (e) => {
  accept(e.target.files?.[0])
  // 关键:清空 input.value,保证「移除后重选同一文件」能再次触发 change。
  e.target.value = ''
}

const onDrop = (e) => {
  dragOver.value = false
  accept(e.dataTransfer?.files?.[0])
}

const onRemove = () => {
  if (inputEl.value) inputEl.value.value = ''
  emit('update:modelValue', '')
  emit('remove')
}
</script>

<style scoped>
.fuz { width: 100%; }
.fuz-drop {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; width: 100%; min-height: 104px; box-sizing: border-box;
  border: 1px dashed var(--line); border-radius: var(--r-lg, 12px);
  background: var(--paper); padding: 22px; text-align: center; cursor: pointer;
  transition: all .15s; color: var(--ink-3);
}
.fuz-drop:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.fuz-drop-active { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.fuz-drop:focus-visible {
  outline: 2px solid var(--clay); outline-offset: 3px;
  border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep);
}
.fuz-up-ico { margin: 0 auto; }
.fuz-up-title { font-size: 13px; font-weight: 600; }
.fuz-up-hint { font-size: 12px; color: var(--ink-4, #9a958c); }

.fuz-file { padding: 11px 14px; background: var(--bone, #f4f1ea); border-radius: var(--r-md, 10px); }
.fuz-file-row { display: flex; align-items: center; justify-content: space-between; }
.fuz-file-name { display: flex; align-items: center; gap: 9px; font-size: 13px; color: var(--ink-2); min-width: 0; }
.fuz-ico { color: var(--clay); flex-shrink: 0; }
.fuz-name-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fuz-meta { font-size: 12px; color: var(--ink-4, #9a958c); flex-shrink: 0; }
.fuz-remove { background: none; border: none; cursor: pointer; font-size: 13px; color: var(--ink-3); font-family: inherit; padding: 4px; flex-shrink: 0; }
.fuz-remove:hover { color: var(--ink); }
.fuz-remove:disabled { opacity: .5; cursor: not-allowed; }
.fuz-preview { font-size: 12px; color: var(--ink-4, #9a958c); margin-top: 8px; max-height: 60px; overflow: hidden; line-height: 1.5; }

.fuz-loading {
  display: flex; align-items: center; justify-content: center;
  padding: 11px 14px; background: var(--bone, #f4f1ea); border-radius: var(--r-md, 10px);
}
.fuz-spin { margin-right: 8px; }
.fuz-loading-text { font-size: 13px; color: var(--ink-3); }
.is-loading { animation: fuz-rotate 1s linear infinite; }
@keyframes fuz-rotate { to { transform: rotate(360deg); } }
</style>
