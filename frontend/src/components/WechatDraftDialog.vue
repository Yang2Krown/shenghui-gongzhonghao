<template>
  <el-dialog
    v-model="visible"
    title="发布到公众号草稿箱"
    width="520px"
    :close-on-click-modal="false"
    :close-on-press-escape="!publishing"
    @close="handleClose"
  >
    <!-- 步骤1：填写公众号信息 + 封面 -->
    <div v-if="step === 'form'" class="publish-step" style="align-items: stretch;">
      <div class="step-header" style="justify-content: center;">
        <span class="step-num">1</span>
        <span>填写公众号凭证</span>
      </div>
      <p style="color: var(--ink-3); margin: 8px 0 16px; font-size: 13px; text-align: center;">
        填写公众号的 AppID 和 AppSecret，用于发布草稿
      </p>

      <el-form label-position="top" style="width: 100%;">
        <el-form-item label="文章标题（必填，不超过 64 字）">
          <el-input v-model="publishTitle" placeholder="请输入标题" maxlength="64" show-word-limit />
          <div v-if="!publishTitle" style="color: var(--ink-4); font-size: 12px; margin-top: 4px;">
            不填将从正文自动截取前 30 字
          </div>
        </el-form-item>
        <el-form-item label="公众号账号">
          <el-select v-model="selectedAccountId" placeholder="选择公众号账号" style="width: 100%;" @change="onAccountChange">
            <el-option
              v-for="acc in accountOptions"
              :key="acc.id"
              :label="acc.account_name + (acc.is_default ? ' (默认)' : '')"
              :value="acc.id"
            />
          </el-select>
          <div v-if="accountOptions.length === 0" style="color: #E6A23C; font-size: 12px; margin-top: 4px;">
            暂无公众号账号，请先到「个人信息」页面添加
          </div>
        </el-form-item>
        <el-form-item label="作者（可选）">
          <el-input v-model="form.author" placeholder="文章作者名，不填则留空" maxlength="32" />
        </el-form-item>
        <el-form-item label="摘要（可选）">
          <el-input v-model="form.digest" type="textarea" :rows="2" placeholder="文章摘要，不填则自动截取" maxlength="120" show-word-limit />
        </el-form-item>
      </el-form>

      <!-- 封面图区域 -->
      <div class="cover-section">
        <div class="cover-label">封面图</div>
        <div class="cover-hint">公众号草稿必须带封面图（横向长方形比例）</div>

        <!-- 封面预览 -->
        <div v-if="coverPreview" class="cover-preview">
          <img :src="coverPreview" alt="封面预览" />
          <button class="cover-remove" @click="removeCover" title="移除封面">×</button>
        </div>

        <!-- 封面操作按钮 -->
        <div class="cover-actions">
          <label class="cover-btn cover-btn-upload">
            <el-icon><Upload /></el-icon>
            上传封面
            <input type="file" accept="image/*" style="display:none" @change="handleCoverUpload" />
          </label>
          <!-- AI 生成封面：暂时隐藏，保留代码以便日后恢复
          <button class="cover-btn cover-btn-ai" @click="handleGenerateCover" :disabled="generatingCover">
            <el-icon v-if="generatingCover" class="spin"><Loading /></el-icon>
            <el-icon v-else><MagicStick /></el-icon>
            {{ generatingCover ? 'AI 生成中...' : 'AI 生成封面' }}
          </button>
          -->
          <button class="cover-btn cover-btn-bing" @click="toggleBingPicker" :disabled="bingLoading">
            <el-icon v-if="bingLoading" class="spin"><Loading /></el-icon>
            <el-icon v-else><Picture /></el-icon>
            {{ bingLoading ? '加载中...' : 'Bing 每日一图' }}
          </button>
        </div>

        <!-- Bing 每日一图选择器 -->
        <div v-if="bingPickerOpen" class="bing-picker">
          <div v-if="bingError" class="bing-error">{{ bingError }}</div>
          <div v-else-if="bingImages.length" class="bing-grid">
            <div
              v-for="img in bingImages"
              :key="img.url"
              class="bing-item"
              :class="{ active: coverPreview === img.url }"
              :title="img.title"
              @click="selectBingImage(img)"
            >
              <img :src="img.url" :alt="img.title" loading="lazy" />
              <span class="bing-date">{{ img.date }}</span>
            </div>
          </div>
          <div v-else class="bing-empty">暂无图片</div>
        </div>

        <div v-if="coverError" style="color: #ff4d4f; font-size: 12px; margin-top: 6px;">{{ coverError }}</div>
      </div>

      <div class="form-actions">
        <button class="btn-secondary" @click="testConnection" :disabled="testing || !selectedAccountId">
          <el-icon v-if="testing" class="spin"><Loading /></el-icon>
          <el-icon v-else><Connection /></el-icon>
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <button class="btn-primary" @click="handlePublish" :disabled="publishing || !selectedAccountId">
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
  Loading, Promotion, CircleCheckFilled, CircleCloseFilled,
  Connection, Upload, MagicStick, Picture
} from '@element-plus/icons-vue'
import { get, post, createWechatDraft, testWechatConnection, generateWechatCover, getBingImages } from '@/api/api'

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

// 封面图状态
const coverPreview = ref('')
const coverBase64 = ref('')
const coverFile = ref(null)
const generatingCover = ref(false)
const coverError = ref('')

// Bing 每日一图状态
const bingPickerOpen = ref(false)
const bingLoading = ref(false)
const bingImages = ref([])
const bingError = ref('')

// 表单数据 — 从 API 加载已保存的账号
const STORAGE_KEY = 'wechat_draft_credentials'
const accountOptions = ref([])
const selectedAccountId = ref(null)

const loadAccounts = async () => {
  try {
    const res = await get('/wechat-accounts')
    accountOptions.value = res.data || []
    // 自动选中默认账号
    if (accountOptions.value.length > 0 && !selectedAccountId.value) {
      const defaultAcc = accountOptions.value.find(a => a.is_default) || accountOptions.value[0]
      selectedAccountId.value = defaultAcc.id
      if (!form.value.author && defaultAcc.author) form.value.author = defaultAcc.author
    }
  } catch { /* ignore */ }
}

const onAccountChange = (accId) => {
  const acc = accountOptions.value.find(a => a.id === accId)
  if (acc && acc.author && !form.value.author) {
    form.value.author = acc.author
  }
}

const loadSavedCredentials = () => {
  return { author: '', digest: props.digest || '' }
}

const form = ref(loadSavedCredentials())

// 标题：可编辑，初始值从 props 传入
const publishTitle = ref('')

// 监听 v-model 变化
watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    step.value = 'form'
    errorMsg.value = ''
    testResult.value = null
    coverError.value = ''
    bingPickerOpen.value = false
    publishTitle.value = props.title || ''
    // 加载账号列表
    loadAccounts()
    // 如果有外部传入的封面图，显示预览
    if (props.coverImageUrl) {
      coverPreview.value = props.coverImageUrl
      coverBase64.value = ''
      coverFile.value = null
    } else {
      coverPreview.value = ''
      coverBase64.value = ''
      coverFile.value = null
    }
    if (props.author && !form.value.author) form.value.author = props.author
    if (props.digest && !form.value.digest) form.value.digest = props.digest
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

// 保存凭证（已改为数据库持久化，这里只保留兼容）
const saveCredentials = () => {
  // 凭证已通过账号管理持久化到数据库，无需再存 localStorage
}

// ========== 封面图操作 ==========

const handleCoverUpload = (e) => {
  const file = e.target.files?.[0]
  if (!file) return

  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('封面图不能超过 5MB')
    return
  }

  coverFile.value = file
  coverError.value = ''

  const reader = new FileReader()
  reader.onload = (ev) => {
    coverPreview.value = ev.target.result
    // 转为 base64（去掉 data:image/xxx;base64, 前缀）
    coverBase64.value = ev.target.result
  }
  reader.readAsDataURL(file)
}

const removeCover = () => {
  coverPreview.value = ''
  coverBase64.value = ''
  coverFile.value = null
  coverError.value = ''
}

const handleGenerateCover = async () => {
  if (!props.title && !props.content) {
    ElMessage.warning('请先填写文章标题或正文')
    return
  }
  generatingCover.value = true
  coverError.value = ''
  try {
    const res = await generateWechatCover(props.title || '', props.content || '', '')
    const data = res.data || res
    if (data.url) {
      coverPreview.value = data.url
      coverBase64.value = ''  // AI 生成的是远程 URL，不转 base64
      coverFile.value = null
      ElMessage.success('封面生成成功')
    }
  } catch (e) {
    coverError.value = e?.response?.data?.detail || '封面生成失败，请重试'
  } finally {
    generatingCover.value = false
  }
}

// ========== Bing 每日一图 ==========

const toggleBingPicker = async () => {
  if (bingPickerOpen.value) {
    bingPickerOpen.value = false
    return
  }
  bingPickerOpen.value = true
  // 已加载过则不重复请求
  if (bingImages.value.length) return
  bingLoading.value = true
  bingError.value = ''
  try {
    const res = await getBingImages(7)
    const data = res.data || res
    bingImages.value = data.images || []
    if (!bingImages.value.length) {
      bingError.value = '暂无每日一图'
    }
  } catch (e) {
    bingError.value = e?.response?.data?.detail || '获取每日一图失败，请重试'
  } finally {
    bingLoading.value = false
  }
}

const selectBingImage = (img) => {
  coverPreview.value = img.url
  coverBase64.value = ''   // 远程 URL，发布时走 cover_image_url 分支
  coverFile.value = null
  coverError.value = ''
  bingPickerOpen.value = false
}

// ========== 连接测试 ==========

const testConnection = async () => {
  testing.value = true
  testResult.value = null
  try {
    const res = await post('/wechat-accounts/' + selectedAccountId.value + '/test')
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

// ========== 发布 ==========

const handlePublish = async () => {
  if (!selectedAccountId.value) {
    ElMessage.warning('请选择公众号账号')
    return
  }

  saveCredentials()
  step.value = 'publishing'
  publishing.value = true

  try {
    // 确定正文内容 —— 优先 HTML，兜底纯文本由后端 ensure_html 转换
    let content = props.contentHtml || props.content || ''

    // 标题校验：微信限制 64 字符，超长则阻止发布
    let title = (publishTitle.value || '').replace(/[\n\r\t]+/g, ' ').trim()
    if (title.length > 64) {
      errorMsg.value = `标题超过微信限制（${title.length}/64 字符），请精简后重试`
      step.value = 'error'
      publishing.value = false
      return
    }

    // 构建请求参数
    const params = {
      title: title,
      content: content,
      author: form.value.author || '',
      digest: form.value.digest || '',
      account_id: selectedAccountId.value,
    }

    // 封面图：优先 base64（本地上传），其次 URL（AI 生成/外部链接）
    if (coverBase64.value) {
      params.cover_image_base64 = coverBase64.value
    } else if (coverPreview.value) {
      params.cover_image_url = coverPreview.value
    }

    const res = await createWechatDraft(params)
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

/* 封面图区域 */
.cover-section {
  width: 100%;
  margin-top: 16px;
  padding: 16px;
  background: var(--bone);
  border-radius: var(--r-md);
}

.cover-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.cover-hint {
  font-size: 12px;
  color: var(--ink-4);
  margin-bottom: 12px;
}

.cover-preview {
  position: relative;
  width: 100%;
  aspect-ratio: 21 / 9;
  border-radius: var(--r-md);
  overflow: hidden;
  margin-bottom: 12px;
  border: 1.5px solid var(--line);
}

.cover-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-remove {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 16px;
  line-height: 24px;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s;
}

.cover-remove:hover {
  background: rgba(0, 0, 0, 0.75);
}

.cover-actions {
  display: flex;
  gap: 10px;
}

.cover-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: var(--r-md);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.cover-btn-upload {
  border: 1.5px dashed var(--line);
  background: var(--paper);
  color: var(--ink-2);
}

.cover-btn-upload:hover {
  border-color: var(--clay-soft);
  background: var(--clay-tint);
}

.cover-btn-ai {
  border: 1.5px solid #7c3aed;
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  color: #fff;
}

.cover-btn-ai:hover:not([disabled]) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

.cover-btn-ai[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

.cover-btn-bing {
  border: 1.5px solid #2563eb;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
}

.cover-btn-bing:hover:not([disabled]) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.cover-btn-bing[disabled] {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Bing 每日一图选择器 */
.bing-picker {
  margin-top: 12px;
}

.bing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.bing-item {
  position: relative;
  aspect-ratio: 16 / 9;
  border-radius: var(--r-sm, 8px);
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.15s;
}

.bing-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.bing-item:hover {
  border-color: var(--clay-soft);
}

.bing-item.active {
  border-color: var(--clay);
}

.bing-date {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 2px 4px;
  font-size: 10px;
  color: #fff;
  background: rgba(0, 0, 0, 0.45);
  text-align: center;
}

.bing-error,
.bing-empty {
  font-size: 13px;
  color: var(--ink-4);
  text-align: center;
  padding: 16px 0;
}

.bing-error {
  color: #ff4d4f;
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
