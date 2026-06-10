<template>
  <el-dialog
    v-model="visible"
    title=""
    width="440px"
    :close-on-click-modal="false"
    :close-on-press-escape="true"
    @close="handleClose"
    class="publish-choice-dialog"
  >
    <div class="choice-body">
      <div class="choice-icon">
        <el-icon :size="36" style="color: var(--clay);"><CircleCheckFilled /></el-icon>
      </div>
      <h3 class="choice-title">标题已确认</h3>
      <p class="choice-subtitle">「{{ title }}」</p>
      <p class="choice-hint">请选择下一步操作</p>

      <div class="choice-actions">
        <button class="choice-btn choice-btn-save" @click="handleSaveDraft">
          <el-icon :size="20"><Document /></el-icon>
          <div class="choice-btn-text">
            <span class="choice-btn-label">保存草稿</span>
            <span class="choice-btn-desc">保存到我的创作列表</span>
          </div>
        </button>
        <button class="choice-btn choice-btn-publish" @click="handlePublish">
          <el-icon :size="20"><Promotion /></el-icon>
          <div class="choice-btn-text">
            <span class="choice-btn-label">一键发布到公众号</span>
            <span class="choice-btn-desc">排版后上传草稿箱</span>
          </div>
        </button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { CircleCheckFilled, Document, Promotion } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'save-draft', 'publish'])

const visible = ref(false)

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

const handleSaveDraft = () => {
  visible.value = false
  emit('save-draft')
}

const handlePublish = () => {
  visible.value = false
  emit('publish')
}

const handleClose = () => {
  visible.value = false
  emit('update:modelValue', false)
}
</script>

<style scoped>
.choice-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0 4px;
}

.choice-icon {
  margin-bottom: 12px;
}

.choice-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
  margin: 0 0 6px;
}

.choice-subtitle {
  font-size: 14px;
  color: var(--ink-3);
  margin: 0 0 4px;
  max-width: 360px;
  text-align: center;
  line-height: 1.5;
  word-break: break-all;
}

.choice-hint {
  font-size: 13px;
  color: var(--ink-4);
  margin: 0 0 24px;
}

.choice-actions {
  display: flex;
  gap: 12px;
  width: 100%;
}

.choice-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: var(--r-lg);
  border: 1.5px solid var(--line);
  background: var(--paper);
  cursor: pointer;
  transition: all 0.18s ease;
  text-align: left;
  font-family: inherit;
}

.choice-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.choice-btn-save {
  color: var(--ink-2);
}

.choice-btn-save:hover {
  border-color: var(--clay-soft);
  background: var(--ivory);
}

.choice-btn-publish {
  color: var(--clay-deep);
  border-color: var(--clay-soft);
  background: linear-gradient(135deg, var(--clay-tint) 0%, var(--paper) 100%);
}

.choice-btn-publish:hover {
  border-color: var(--clay);
  background: linear-gradient(135deg, var(--clay-tint) 0%, var(--ivory) 100%);
  box-shadow: 0 6px 20px rgba(204, 120, 92, 0.15);
}

.choice-btn-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.choice-btn-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
}

.choice-btn-desc {
  font-size: 12px;
  color: var(--ink-4);
  white-space: nowrap;
}
</style>
