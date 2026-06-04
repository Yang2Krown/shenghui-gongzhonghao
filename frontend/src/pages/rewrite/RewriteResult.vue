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

    <!-- 操作按钮 -->
    <div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">
      <button class="btn-text btn-sm" @click="copyAll">
        <el-icon :size="15"><CopyDocument /></el-icon> 复制全部
      </button>
      <button v-if="showPublishBtn" class="btn-publish" @click="showPublishDialog = true">
        <el-icon :size="15"><Promotion /></el-icon> 发布到小红书
      </button>
      <button class="btn-wechat" @click="showWechatDraftDialog = true">
        <el-icon :size="15"><Promotion /></el-icon> 发布到公众号草稿箱
      </button>
    </div>

    <!-- 发布弹窗 -->
    <XhsPublishDialog
      v-model="showPublishDialog"
      :title="result.title"
      :content="result.body"
      :tags="result.tags"
      :blocks="blocks"
      @success="handlePublishSuccess"
    />

    <!-- 发布到公众号草稿箱弹窗 -->
    <WechatDraftDialog
      v-model="showWechatDraftDialog"
      :title="result.title"
      :content="result.body"
      :content-html="result.contentHtml || result.body"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Promotion } from '@element-plus/icons-vue'
import XhsPublishDialog from '@/components/XhsPublishDialog.vue'
import WechatDraftDialog from '@/components/WechatDraftDialog.vue'

const props = defineProps({
  result: { type: Object, required: true },
  // 是否显示发布按钮（默认当目标平台是小红书时显示）
  showPublishBtn: { type: Boolean, default: true },
  // 图文混排数据，用于发布到小红书
  blocks: { type: Array, default: () => [] }
})

const showPublishDialog = ref(false)
const showWechatDraftDialog = ref(false)

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

const handlePublishSuccess = () => {
  ElMessage.success('发布成功！')
}
</script>

<style scoped>
.btn-wechat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border: 1.5px solid #07c160;
  border-radius: var(--r-pill);
  background: linear-gradient(135deg, #07c160 0%, #06ae56 100%);
  color: #fff;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-wechat:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(7, 193, 96, 0.3);
}

.btn-publish {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border: 1.5px solid #FF2442;
  border-radius: var(--r-pill);
  background: linear-gradient(135deg, #FF2442 0%, #FF4D6A 100%);
  color: #fff;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-publish:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(255, 36, 66, 0.3);
}
</style>
