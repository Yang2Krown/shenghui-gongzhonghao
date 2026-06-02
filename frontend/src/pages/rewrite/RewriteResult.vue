<template>
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
      <h2 class="font-serif text-ink" style="font-size: 22px; font-weight: 600;">生成结果</h2>
    </div>

    <!-- 标题 -->
    <div v-if="result.title" class="card" style="padding: 22px; margin-bottom: 14px; border-color: var(--clay-soft); box-shadow: var(--sh-clay);">
      <span class="badge badge-clay" style="margin-bottom: 10px;">标题</span>
      <p class="font-serif text-ink" style="font-size: 20px; font-weight: 700; margin-top: 8px; line-height: 1.4;">{{ result.title }}</p>
    </div>

    <!-- 正文 -->
    <div class="card" style="padding: 24px; margin-bottom: 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h4 class="text-sm font-semibold text-ink">正文</h4>
        <button class="btn-text btn-sm" @click="copyText(result.body)">
          <el-icon :size="15"><CopyDocument /></el-icon> 复制正文
        </button>
      </div>
      <div style="white-space: pre-wrap; font-size: 15px; line-height: 1.85; color: var(--ink-2); background: var(--bone); border-radius: var(--r-md); padding: 18px;">
        {{ result.body }}
      </div>
    </div>

    <!-- 标签 -->
    <div v-if="result.tags?.length" class="card" style="padding: 24px; margin-bottom: 14px;">
      <h4 class="text-sm font-semibold text-ink" style="margin-bottom: 12px;">推荐标签</h4>
      <div style="display: flex; flex-wrap: wrap; gap: 8px;">
        <span v-for="tag in result.tags" :key="tag"
          style="padding: 5px 13px; background: var(--sand-soft); color: #8a6d33; border-radius: var(--r-pill); font-size: 13px; font-weight: 500;">
          #{{ tag }}
        </span>
      </div>
    </div>

    <!-- 复制全部 -->
    <div style="display: flex; justify-content: center;">
      <button class="btn-text btn-sm" @click="copyAll">
        <el-icon :size="15"><CopyDocument /></el-icon> 复制全部
      </button>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { CopyDocument } from '@element-plus/icons-vue'

const props = defineProps({
  result: { type: Object, required: true }
})

const copyText = (text) => {
  navigator.clipboard?.writeText(text).catch(() => {})
  ElMessage.success('已复制')
}

const copyAll = () => {
  const full = (props.result.title ? props.result.title + '\n\n' : '') +
    props.result.body +
    (props.result.tags ? '\n\n' + props.result.tags.map(t => '#' + t).join(' ') : '')
  copyText(full)
}
</script>
