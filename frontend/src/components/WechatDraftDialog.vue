<template>
  <el-dialog
    v-model="visible"
    title="发布到公众号草稿箱"
    width="480px"
    :close-on-click-modal="false"
    :close-on-press-escape="!publishing"
    @close="handleClose"
  >
    <!-- 步骤1：填写公众号信息 -->
    <div v-if="step === 'form'" class="publish-step">
      <div class="step-header">
        <span class="step-num">1</span>
        <span>填写公众号凭证</span>
      </div>
      <p style="color: var(--ink-3); margin: 8px 0 16px; font-size: 13px;">
        填写公众号的 AppID 和 AppSecret，用于发布草稿
      </p>
      <el-form label-position="top" style="width: 100%;">
        <el-form-item label="AppID">
          <el-input v-model="form.appid" placeholder="公众号 AppID" />
        </el-form-item>
        <el-form-item label="AppSecret">
          <el-input v-model="form.app_secret" placeholder="公众号 AppSecret" show-password />
        </el-form-item>
        <el-form-item label="作者（可选）">
          <el-input v-model="form.author" placeholder="文章作者名，不填则留空" maxlength="32" />
        </el-form-item>
        <el-form-item label="摘要（可选）">
          <el-input v-model="form.digest" type="textarea" :rows="2" placeholder="文章摘要，不填则自动截取" maxlength="120" show-word-limit />
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <button class="btn-secondary" @click="testConnection" :disabled="testing || !form.appid || !form.app_secret">
          <el-icon v-if="testing" class="spin"><Loading /></el-icon>
          <el-icon v-else><Connection /></el-icon>
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <button class="btn-primary" @click="handlePublish" :disabled="publishing || !form.appid || !form.app_secret">
          <el-icon v-if="publishing" class="spin"><Loading /></el-icon>
          <el-icon v-else><Promotion /></el-icon>
          {{ publishing ? '发布中...' : '发布到草稿箱' }}
        </button>
      </div>

      <p v-if="testResult" :class="['test-result', testResult.success ? 'test-success' : 'test-fail']">
        {{ testResult.message }}
      </p>
    </div>

    <!-- 发布中 -->
    <div v-else-if="step === 'publishing'" class="publish-step">
      <el-icon class="spin" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <p style="font-size: 15px; margin-top: 12px;">正在发布到草稿箱...</p>
      <p style="color: var(--ink-3); font-size: 13px;">获取凭证 → 上传封面 → 创建草稿</p>
    </div>

    <!-- 发布成功 -->
    <div v-else-if="step === 'success'" class="publish-step">
      <el-icon :size="48" style="color: #52c41a; margin-bottom: 16px;"><CircleCheckFilled /></el-icon>
      <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">发布成功！</p>
      <p style="color: var(--ink-3); margin-bottom: 8px;">文章已保存到公众号草稿箱</p>
      <p v-if="resultMediaId" style="color: var(--ink-4); font-size: 12px; font-family: monospace;">
        media_id: {{ resultMediaId }}
      </p>
      <button class="btn-primary" style="margin-top: 20px;" @click="handleClose">
        完成
      </button>
    </div>

    <!-- 发布失败 -->
    <div v-else-if="step === 'error'" class="publish-step">
      <el-icon :size="48" style="color: #ff4d4f; margin-bottom: 16px;"><CircleCloseFilled /></el-icon>
      <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">发布失败</p>
      <p style="color: var(--ink-3); margin-bottom: 16px;">{{ errorMsg }}</p>
      <div style="display: flex; gap: 12px; justify-content: center;">
        <button class="btn-secondary" @click="handleRetry">重试</button>
        <button class="btn-primary" @click="handleClose">关闭</button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Loading, Promotion, CircleCheckFilled, CircleCloseFilled, Connection
} from '@element-plus/icons-vue'
import { createWechatDraft, testWechatConnection } from '@/api/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  content: { type: String, default: '' },
  contentHtml: { type: String, default: '' },
  author: { type: String, default: '' },
  digest: { type: String, default: '' },
  coverImageUrl: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = ref(false)
const step = ref('form')
const errorMsg = ref('')
const publishing = ref(false)
const testing = ref(false)
const testResult = ref(null)
const resultMediaId = ref('')

// 表单数据 — 从 localStorage 读取上次填写的凭证
const STORAGE_KEY = 'wechat_draft_credentials'
const loadSavedCredentials = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return {
      appid: saved.appid || '',
      app_secret: saved.app_secret || '',
      author: saved.author || props.author || '',
      digest: saved.digest || props.digest || '',
    }
  } catch {
    return { appid: '', app_secret: '', author: props.author || '', digest: props.digest || '' }
  }
}

const form = ref(loadSavedCredentials())

// 监听 v-model 变化
watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    step.value = 'form'
    errorMsg.value = ''
    testResult.value = null
    // 每次打开时同步外部 props 到表单（但凭证保留 localStorage 的）
    if (props.author && !form.value.author) form.value.author = props.author
    if (props.digest && !form.value.digest) form.value.digest = props.digest
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

// 保存凭证到 localStorage
const saveCredentials = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      appid: form.value.appid,
      app_secret: form.value.app_secret,
      author: form.value.author,
      digest: form.value.digest,
    }))
  } catch { /* ignore */ }
}

const testConnection = async () => {
  testing.value = true
  testResult.value = null
  try {
    const res = await testWechatConnection(form.value.appid, form.value.app_secret)
    const data = res.data || res
    testResult.value = data
    if (data.success) {
      ElMessage.success('连接成功')
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: e?.response?.data?.detail || '连接测试失败'
    }
  } finally {
    testing.value = false
  }
}

const handlePublish = async () => {
  if (!form.value.appid || !form.value.app_secret) {
    ElMessage.warning('请填写 AppID 和 AppSecret')
    return
  }

  saveCredentials()
  step.value = 'publishing'
  publishing.value = true

  try {
    // 确定正文内容：优先用 HTML，否则将纯文本包装为 HTML
    let content = props.contentHtml || ''
    if (!content && props.content) {
      // 纯文本 → 基础 HTML（按段落拆分）
      content = props.content
        .split(/\n{2,}/)
        .filter(p => p.trim())
        .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
        .join('')
    }

    const res = await createWechatDraft({
      title: props.title,
      content: content,
      author: form.value.author || '',
      digest: form.value.digest || '',
      appid: form.value.appid,
      app_secret: form.value.app_secret,
      cover_image_url: props.coverImageUrl || '',
    })
    const data = res.data || res

    if (data.success) {
      resultMediaId.value = data.media_id || ''
      step.value = 'success'
      emit('success', data)
    } else {
      errorMsg.value = data.message || '发布失败'
      step.value = 'error'
    }
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || e?.message || '发布失败，请重试'
    step.value = 'error'
  } finally {
    publishing.value = false
  }
}

const handleRetry = () => {
  step.value = 'form'
  errorMsg.value = ''
  testResult.value = null
}

const handleClose = () => {
  visible.value = false
  emit('update:modelValue', false)
  step.value = 'form'
  errorMsg.value = ''
  testResult.value = null
  resultMediaId.value = ''
}
</script>

<style scoped>
.publish-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
  text-align: center;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--clay);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
}

.test-result {
  margin-top: 12px;
  font-size: 13px;
  padding: 8px 14px;
  border-radius: var(--r-md);
}

.test-success {
  color: #389e0d;
  background: #f6ffed;
}

.test-fail {
  color: #cf1322;
  background: #fff1f0;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border: none;
  border-radius: var(--r-md);
  background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%);
  color: #fff;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-primary:hover:not([disabled]) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(204, 120, 92, 0.3);
}

.btn-primary[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border: 1.5px solid var(--line);
  border-radius: var(--r-md);
  background: var(--paper);
  color: var(--ink-2);
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-secondary:hover:not([disabled]) {
  border-color: var(--clay-soft);
  background: var(--clay-tint);
}

.btn-secondary[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
