<template>
  <div class="wechat-to-xhs">
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">公众号转小红书</h1>
      <p class="text-sm text-ink-3 mt-1">将公众号文章内容转换为小红书风格文案，或一键长文排版发布</p>
    </header>

    <!-- ===== 输入区域 ===== -->
    <div v-if="step === 'input'" class="card p-6 mb-6">
      <div class="flex gap-4 mb-6">
        <button class="mode-btn" :class="{ 'mode-btn-active': mode === 'paste' }" @click="mode = 'paste'">
          <el-icon><Document /></el-icon>
          <span>粘贴内容</span>
        </button>
        <button class="mode-btn" :class="{ 'mode-btn-active': mode === 'link' }" @click="mode = 'link'">
          <el-icon><Link /></el-icon>
          <span>公众号链接</span>
        </button>
      </div>

      <!-- 粘贴内容模式 -->
      <div v-if="mode === 'paste'">
        <div class="mb-4">
          <label class="label">原文标题（可选）</label>
          <el-input v-model="originalTitle" placeholder="输入公众号文章原标题" />
        </div>
        <div class="mb-4">
          <label class="label">文章内容</label>
          <el-input v-model="content" type="textarea" placeholder="请粘贴公众号文章正文内容..." :autosize="{ minRows: 8, maxRows: 20 }" resize="none" />
        </div>
        <div class="flex items-center justify-between">
          <span class="text-sm text-ink-3">{{ content.length }} 字</span>
          <el-button type="primary" size="large" @click="convertContent" :loading="loading" :disabled="content.length < 10">
            转换为小红书文案
          </el-button>
        </div>
      </div>

      <!-- 链接模式 -->
      <div v-if="mode === 'link'">
        <div class="mb-4">
          <label class="label">公众号文章链接</label>
          <el-input v-model="linkUrl" placeholder="粘贴 mp.weixin.qq.com 的文章链接" clearable />
        </div>
        <div class="flex justify-end gap-3">
          <el-button size="large" @click="extractPreview" :loading="extracting" :disabled="!isValidLink">
            提取图文预览
          </el-button>
          <el-button type="primary" size="large" @click="convertLink" :loading="loading" :disabled="!isValidLink">
            直接转换文案
          </el-button>
        </div>
      </div>
    </div>

    <!-- ===== 提取预览 ===== -->
    <div v-if="step === 'preview'" class="preview-area">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-h4 font-serif text-ink">{{ previewData.title || '文章预览' }}</h2>
          <p v-if="previewData.author" class="text-sm text-ink-3 mt-1">来源：{{ previewData.author }}</p>
        </div>
        <el-button text @click="backToInput">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
      </div>

      <!-- 图文混排预览 -->
      <div class="card p-6 mb-6">
        <div class="article-preview">
          <template v-for="(block, i) in previewData.blocks" :key="i">
            <p v-if="block.type === 'text'" class="article-text">{{ block.content }}</p>
            <div v-else-if="block.type === 'image'" class="article-image-wrap">
              <img
                :src="previewImgSrc(block)"
                :alt="block.alt || '文章配图'"
                class="article-image"
                loading="lazy"
                @error="onImageError($event)"
              />
            </div>
          </template>
        </div>
        <div class="mt-4 flex items-center justify-between text-sm text-ink-3">
          <span>共 {{ previewData.blocks.filter(b => b.type === 'text').length }} 段文字，{{ previewData.image_count || 0 }} 张图片</span>
          <div v-if="previewData.tags && previewData.tags.length" class="flex flex-wrap gap-1">
            <span v-for="tag in previewData.tags" :key="tag" class="tag-item">#{{ tag }}</span>
          </div>
        </div>
      </div>

      <!-- 操作选择 -->
      <div class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">选择操作</h3>
        <div class="flex gap-4">
          <div class="action-card" @click="convertFromPreview">
            <div class="action-icon">
              <el-icon :size="28"><Switch /></el-icon>
            </div>
            <div>
              <h4 class="text-base font-semibold text-ink">转换小红书文案</h4>
              <p class="text-sm text-ink-3 mt-1">AI 改写为小红书风格短文案</p>
            </div>
          </div>
          <div class="action-card" @click="startPluginPublish">
            <div class="action-icon action-icon-primary">
              <el-icon :size="28"><Promotion /></el-icon>
            </div>
            <div>
              <h4 class="text-base font-semibold text-ink">
                插件发布
                <span v-if="extReady" class="badge-clay" style="margin-left:6px;">插件已就绪</span>
                <span v-else class="text-xs text-ink-4" style="margin-left:6px;">未检测到插件</span>
              </h4>
              <p class="text-sm text-ink-3 mt-1">用你自己浏览器里登录的小红书发布（推荐）</p>
            </div>
          </div>
          <div class="action-card" @click="startPublishFlow">
            <div class="action-icon">
              <el-icon :size="28"><Promotion /></el-icon>
            </div>
            <div>
              <h4 class="text-base font-semibold text-ink">本机 Chrome 发布</h4>
              <p class="text-sm text-ink-3 mt-1">在运行后端的机器上弹出 Chrome 自动排版（原方式）</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 长文发布流程 ===== -->
    <div v-if="step === 'publish'" class="publish-area">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-h4 font-serif text-ink">长文排版发布</h2>
        <el-button text @click="backToPreview">
          <el-icon><ArrowLeft /></el-icon>
          返回预览
        </el-button>
      </div>

      <!-- 发布步骤 -->
      <el-steps :active="publishStep" align-center class="mb-6">
        <el-step title="填写内容" />
        <el-step title="选择模板" />
        <el-step title="预览确认" />
        <el-step title="发布" />
      </el-steps>

      <!-- Step 0: 填写中 -->
      <div v-if="publishStep === 0 && publishStatus !== 'need_login'" class="card p-6 mb-6 text-center py-12">
        <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
        <template v-if="publishVia === 'ext'">
          <p class="text-ink-3 mt-3">{{ publishProgress || '正在通过插件填写长文…' }}</p>
          <p class="text-xs text-ink-4 mt-1">请勿关闭新打开的小红书标签页</p>
        </template>
        <template v-else>
          <p class="text-ink-3 mt-3">正在启动 Chrome 并填写长文内容...</p>
          <p class="text-xs text-ink-4 mt-1">请勿关闭弹出的 Chrome 窗口</p>
        </template>
      </div>

      <!-- 需要登录 -->
      <div v-if="publishStep === 0 && publishStatus === 'need_login'" class="card p-6 mb-6">
        <div class="flex items-center gap-3 mb-4">
          <el-icon :size="24" style="color: var(--sand);"><Warning /></el-icon>
          <h3 class="text-base font-semibold text-ink">需要登录小红书</h3>
        </div>
        <p class="text-sm text-ink-2 mb-4">请在弹出的 Chrome 窗口中扫码登录小红书，登录成功后点击下方按钮继续。</p>
        <el-button type="primary" @click="retryPublish" :loading="publishLoading">
          登录完成，继续发布
        </el-button>
      </div>

      <!-- Step 1: 选择模板 -->
      <div v-if="publishStep === 1" class="card p-6 mb-6">
        <h3 class="text-h4 font-sans text-ink mb-4">选择排版模板</h3>
        <p class="text-sm text-ink-3 mb-4">请在 Chrome 窗口中预览效果，然后选择一个模板：</p>
        <div class="template-grid">
          <div
            v-for="name in templates"
            :key="name"
            class="template-option"
            :class="{ 'template-option-active': selectedTemplate === name }"
            @click="selectedTemplate = name"
          >
            {{ name }}
          </div>
        </div>
        <div class="flex justify-end mt-4">
          <el-button type="primary" @click="confirmTemplate" :loading="publishLoading" :disabled="!selectedTemplate">
            使用此模板
          </el-button>
        </div>
      </div>

      <!-- Step 2: 预览确认 -->
      <div v-if="publishStep === 2" class="card p-6 mb-6">
        <div v-if="publishLoading" class="text-center py-8">
          <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
          <p class="text-ink-3 mt-3">正在应用模板并进入发布页...</p>
        </div>
        <div v-else>
          <h3 class="text-h4 font-sans text-ink mb-3">请在浏览器中预览确认</h3>
          <p v-if="publishVia === 'ext'" class="text-sm text-ink-2 mb-4">
            已在小红书标签页填好内容并排版。请<strong>切换到那个标签页</strong>检查无误后，
            在小红书页面里点「发布」。发布完成后点下方按钮。
          </p>
          <p v-else class="text-sm text-ink-2 mb-4">已在 Chrome 中打开发布页，请检查内容和排版效果。确认无误后点击发布。</p>
          <div class="flex justify-center gap-4">
            <el-button @click="backToPreview">取消</el-button>
            <el-button type="primary" @click="doPublish" :loading="publishLoading">
              {{ publishVia === 'ext' ? '我已在小红书完成发布' : '确认发布' }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- Step 3: 发布结果 -->
      <div v-if="publishStep === 3" class="card p-6 mb-6 text-center py-8">
        <el-icon :size="48" style="color: var(--clay);"><CircleCheckFilled /></el-icon>
        <h3 class="text-lg font-semibold text-ink mt-4">发布成功！</h3>
        <p class="text-sm text-ink-3 mt-2">文章已发布到小红书</p>
        <el-button class="mt-4" @click="resetAll">发布新内容</el-button>
      </div>
    </div>

    <!-- ===== 错误提示 ===== -->
    <div v-if="error" class="card p-6 mb-6 error-card">
      <div class="flex items-center gap-3">
        <el-icon :size="24" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
        <div>
          <h3 class="text-base font-semibold text-ink">操作失败</h3>
          <p class="text-sm text-ink-3 mt-1">{{ error }}</p>
        </div>
      </div>
      <div class="mt-4">
        <el-button @click="error = ''">关闭</el-button>
      </div>
    </div>

    <!-- ===== 加载状态 ===== -->
    <div v-if="loading && step === 'input'" class="card p-6 mb-6 text-center py-12">
      <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <p class="text-ink-3 mt-3">正在生成小红书文案...</p>
    </div>

    <div v-if="extracting" class="card p-6 mb-6 text-center py-12">
      <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <p class="text-ink-3 mt-3">正在提取文章图文内容...</p>
    </div>

    <!-- ===== 文案转换结果 ===== -->
    <div v-if="result && !loading && step !== 'publish'" class="result-area">
      <div class="flex items-center justify-between mb-4">
        <div v-if="result.type" class="badge-primary">{{ result.type }}</div>
        <el-button v-if="step === 'preview'" text @click="result = null">
          <el-icon><ArrowLeft /></el-icon>
          返回预览
        </el-button>
      </div>

      <div v-if="result.title" class="card p-6 mb-4 title-card">
        <div class="flex items-center gap-2 mb-3"><span class="badge-clay">主标题</span></div>
        <p class="text-xl font-bold text-ink text-center py-2">{{ result.title }}</p>
      </div>

      <div v-if="result.alt_titles && result.alt_titles.length" class="card p-6 mb-4">
        <h3 class="text-h4 font-sans text-ink mb-3">备用标题</h3>
        <div class="space-y-2">
          <div v-for="(title, i) in result.alt_titles" :key="i" class="alt-title-item">
            <span class="text-ink-4 mr-2">{{ i + 1 }}.</span>
            <span class="text-ink">{{ title }}</span>
          </div>
        </div>
      </div>

      <div v-if="result.content" class="card p-6 mb-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-h4 font-sans text-ink">正文</h3>
          <el-button text size="small" @click="copyContent">
            <el-icon><CopyDocument /></el-icon>
            复制
          </el-button>
        </div>
        <div class="content-box whitespace-pre-wrap text-ink-2 leading-relaxed">{{ result.content }}</div>
        <div class="mt-3 text-sm text-ink-3 text-right">{{ result.content.length }} 字</div>
      </div>

      <div v-if="result.tags && result.tags.length" class="card p-6 mb-4">
        <h3 class="text-h4 font-sans text-ink mb-3">推荐标签</h3>
        <div class="flex flex-wrap gap-2">
          <span v-for="(tag, i) in result.tags" :key="i" class="tag-item">#{{ tag }}</span>
        </div>
      </div>

      <div v-if="result.original_title || result.original_author" class="card p-6 mb-4">
        <h3 class="text-h4 font-sans text-ink mb-3">原文信息</h3>
        <div class="space-y-2 text-sm">
          <p v-if="result.original_title" class="text-ink-2"><span class="text-ink-3">原标题：</span>{{ result.original_title }}</p>
          <p v-if="result.original_author" class="text-ink-2"><span class="text-ink-3">来源：</span>{{ result.original_author }}</p>
        </div>
      </div>

      <div class="bottom-actions">
        <el-button @click="resetAll">重新转换</el-button>
        <el-button type="primary" @click="copyAll">复制全部内容</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document, Link, CircleCloseFilled, Loading, CopyDocument,
  Switch, Promotion, ArrowLeft, Warning, CircleCheckFilled
} from '@element-plus/icons-vue'
import { post, get } from '@/api/api'
import generationRecordApi from '@/api/generationRecord'

const route = useRoute()

// 状态
const step = ref('input') // input | preview | publish
const mode = ref('paste')
const content = ref('')
const originalTitle = ref('')
const linkUrl = ref('')
const loading = ref(false)
const extracting = ref(false)
const error = ref('')
const result = ref(null)

// 预览数据
const previewData = ref({ title: '', author: '', blocks: [], tags: [], image_count: 0, text_content: '' })

// 发布状态
const publishStep = ref(0) // 0=填写 1=模板 2=确认 3=完成
const publishStatus = ref('')
const publishLoading = ref(false)
const templates = ref([])
const selectedTemplate = ref('')

// 插件发布相关
const publishVia = ref('local') // 'local' | 'ext'
const extReady = ref(false)     // 是否检测到发布插件
const publishProgress = ref('') // 插件流程进度文案

const postToExt = (type, payload) => {
  window.postMessage({ __gzhXhs: true, dir: 'to-ext', type, payload }, '*')
}

// 监听插件(bridge)发来的消息
const onExtMessage = (e) => {
  const m = e.data
  if (!m || m.__gzhXhs !== true || m.dir !== 'to-page') return
  if (m.type === 'ready' || m.type === 'pong') { extReady.value = true; return } // 插件已安装就绪
  if (publishVia.value !== 'ext') return // 只在插件发布流程里处理后续消息
  if (m.type === 'progress') {
    publishProgress.value = m.detail || m.step || ''
  } else if (m.type === 'templates') {
    templates.value = m.templates || []
    publishStep.value = 1
    publishLoading.value = false
  } else if (m.type === 'prepared') {
    publishStep.value = 2
    publishLoading.value = false
  } else if (m.type === 'error') {
    error.value = m.error || '插件发布出错'
    publishLoading.value = false
  }
}

const isValidLink = computed(() => linkUrl.value && linkUrl.value.includes('weixin'))

// 从历史记录恢复
onMounted(async () => {
  window.addEventListener('message', onExtMessage)
  // 主动探测插件是否就绪（bridge 注入后也会主动推 ready）
  postToExt('ping')

  const recordId = route.query.record_id
  if (recordId) {
    try {
      const res = await generationRecordApi.get(recordId)
      const record = res.data
      if (record.output_snapshot && record.status === 'completed') {
        result.value = record.output_snapshot
        ElMessage.success('已从历史记录恢复转换结果')
      }
    } catch (e) {
      console.warn('恢复历史记录失败:', e)
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('message', onExtMessage)
})

// ===== 粘贴内容转换 =====
const convertContent = async () => {
  if (content.value.length < 10) return ElMessage.warning('请输入至少10个字符的内容')
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await post('/wechat-to-xhs/convert-content', {
      content: content.value,
      original_title: originalTitle.value || null
    }, { timeout: 120000 })
    result.value = res.data || res
    ElMessage.success('转换成功')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '转换失败，请重试'
  } finally {
    loading.value = false
  }
}

// ===== 链接直接转换 =====
const convertLink = async () => {
  if (!isValidLink.value) return ElMessage.warning('请输入有效的公众号链接')
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await post('/wechat-to-xhs/convert-link', { url: linkUrl.value }, { timeout: 120000 })
    result.value = res.data || res
    ElMessage.success('提取并转换成功')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '提取失败，请检查链接是否有效'
  } finally {
    loading.value = false
  }
}

// ===== 提取图文预览 =====
const extractPreview = async () => {
  if (!isValidLink.value) return ElMessage.warning('请输入有效的公众号链接')
  extracting.value = true
  error.value = ''
  try {
    const res = await post('/wechat-to-xhs/extract-link-preview', { url: linkUrl.value }, { timeout: 60000 })
    previewData.value = res.data || res
    step.value = 'preview'
    ElMessage.success('图文提取成功')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '提取失败'
  } finally {
    extracting.value = false
  }
}

// ===== 从预览转换文案 =====
const convertFromPreview = async () => {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await post('/wechat-to-xhs/convert-content', {
      content: previewData.value.text_content,
      original_title: previewData.value.title || null
    }, { timeout: 120000 })
    result.value = {
      ...(res.data || res),
      original_title: previewData.value.title,
      original_author: previewData.value.author,
    }
    ElMessage.success('转换成功')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '转换失败'
  } finally {
    loading.value = false
  }
}

// ===== 插件发布流程 =====
const startPluginPublish = () => {
  if (!extReady.value) {
    error.value = '未检测到发布插件。请先安装插件（见 xhs-extension/README）并刷新页面。'
    return
  }
  publishVia.value = 'ext'
  step.value = 'publish'
  publishStep.value = 0
  publishStatus.value = ''
  publishLoading.value = true
  publishProgress.value = '正在把内容发送给插件…'
  error.value = ''
  templates.value = []
  selectedTemplate.value = ''

  // 插件用公网图片 url（OSS），不用 local_path；插件后台会 fetch 下来再上传
  const blocks = (previewData.value.blocks || []).map(b => ({
    type: b.type,
    content: b.content || undefined,
    url: b.url || undefined,
    alt: b.alt || undefined,
  }))
  let desc = previewData.value.text_content || ''
  if (desc.length > 800) desc = desc.slice(0, 800)

  postToExt('publish', {
    title: previewData.value.title || '无标题',
    description: desc,
    blocks,
  })
}

// ===== 长文发布流程（本机 Chrome / CDP） =====
const startPublishFlow = async () => {
  publishVia.value = 'local'
  step.value = 'publish'
  publishStep.value = 0
  publishStatus.value = ''
  publishLoading.value = true
  error.value = ''

  try {
    const blocks = (previewData.value.blocks || []).map(b => ({
      type: b.type,
      content: b.content || undefined,
      url: b.url || undefined,
      local_path: b.local_path || undefined,
      alt: b.alt || undefined,
    }))
    // 一键排版前会逐张上传图片到小红书，图多时较慢，超时放宽到 5 分钟
    const res = await post('/xhs-publish/start-long-article', {
      title: previewData.value.title || '无标题',
      content: previewData.value.text_content,
      blocks: blocks.length > 0 ? blocks : undefined,
    }, { timeout: 300000 })

    const data = res.data || res
    if (data.status === 'need_login') {
      publishStatus.value = 'need_login'
      publishLoading.value = false
      return
    }
    templates.value = data.templates || []
    publishStep.value = 1
    publishLoading.value = false
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '启动发布失败'
    publishLoading.value = false
  }
}

const retryPublish = () => {
  publishStatus.value = ''
  startPublishFlow()
}

const confirmTemplate = async () => {
  if (!selectedTemplate.value) return

  // 插件流程：把模板名发给插件，等待 'prepared' 消息
  if (publishVia.value === 'ext') {
    publishLoading.value = true
    publishProgress.value = '应用模板中…'
    error.value = ''
    postToExt('selectTemplate', { name: selectedTemplate.value })
    return
  }

  publishLoading.value = true
  error.value = ''
  try {
    // 选模板时会同步上传所有图片到小红书 CDN，6 张图可能需要 1 分钟以上，超时放宽到 3 分钟
    await post('/xhs-publish/select-template', { name: selectedTemplate.value }, { timeout: 180000 })
    publishStep.value = 2

    // 自动点击下一步
    let desc = previewData.value.text_content || ''
    if (desc.length > 800) {
      desc = desc.slice(0, 800)
    }
    await post('/xhs-publish/click-next-step', { content: desc }, { timeout: 60000 })
    publishLoading.value = false
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '模板选择失败'
    publishLoading.value = false
  }
}

const doPublish = async () => {
  // 插件流程 v1 不自动点发布，用户已在小红书页面手动发布，这里只标记完成
  if (publishVia.value === 'ext') {
    publishStep.value = 3
    ElMessage.success('已完成')
    return
  }

  publishLoading.value = true
  error.value = ''
  try {
    await post('/xhs-publish/click-publish', {}, { timeout: 30000 })
    publishStep.value = 3
    ElMessage.success('发布成功！')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '发布失败'
  } finally {
    publishLoading.value = false
  }
}

// ===== 导航 =====
const backToInput = () => {
  step.value = 'input'
  result.value = null
}

const backToPreview = () => {
  step.value = 'preview'
  publishStep.value = 0
  publishStatus.value = ''
  publishVia.value = 'local'
  publishProgress.value = ''
  result.value = null
}

const resetAll = () => {
  step.value = 'input'
  result.value = null
  error.value = ''
  content.value = ''
  originalTitle.value = ''
  linkUrl.value = ''
  previewData.value = { title: '', author: '', blocks: [], tags: [], image_count: 0, text_content: '' }
  publishStep.value = 0
  publishStatus.value = ''
  publishVia.value = 'local'
  publishProgress.value = ''
  templates.value = []
  selectedTemplate.value = ''
}

// 预览图地址：优先用公网 url（OSS，生产/本地都能显示）；
// 微信原图有防盗链不能直接加载，这种才退回本地代理路径 local_path
const previewImgSrc = (block) => {
  const url = block.url || ''
  if (url && !/weixin|qq\.com/i.test(url)) return url
  return block.local_path || url
}

const onImageError = (e) => {
  e.target.style.display = 'none'
}

// ===== 复制 =====
const copyContent = async () => {
  if (!result.value?.content) return
  try {
    await navigator.clipboard.writeText(result.value.content)
    ElMessage.success('正文已复制到剪贴板')
  } catch { ElMessage.error('复制失败') }
}

const copyAll = async () => {
  if (!result.value) return
  let text = ''
  if (result.value.title) text += `【主标题】\n${result.value.title}\n\n`
  if (result.value.alt_titles?.length) text += `【备用标题】\n${result.value.alt_titles.map((t, i) => `${i + 1}. ${t}`).join('\n')}\n\n`
  if (result.value.content) text += `【正文】\n${result.value.content}\n\n`
  if (result.value.tags?.length) text += `【标签】\n${result.value.tags.map(t => `#${t}`).join(' ')}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('全部内容已复制到剪贴板')
  } catch { ElMessage.error('复制失败') }
}

// ===== 离开提示 =====
onBeforeRouteLeave(async (to, from, next) => {
  if (!result.value && step.value === 'input') return next()
  try {
    await ElMessageBox.confirm('离开后当前内容将丢失，确定离开吗？', '确认离开', {
      confirmButtonText: '仍然离开', cancelButtonText: '留在此页', type: 'warning'
    })
    next()
  } catch { next(false) }
})

const handleBeforeUnload = (e) => {
  if (result.value || step.value !== 'input') { e.preventDefault(); e.returnValue = '' }
}
onMounted(() => window.addEventListener('beforeunload', handleBeforeUnload))
onUnmounted(() => window.removeEventListener('beforeunload', handleBeforeUnload))
</script>

<style scoped>
.wechat-to-xhs {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 80px;
}

/* 模式切换按钮 */
.mode-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn:hover { border-color: var(--clay-soft); color: var(--ink); }
.mode-btn-active { background: var(--clay); border-color: var(--clay); color: var(--paper); }
.mode-btn-active:hover { background: var(--clay-deep); border-color: var(--clay-deep); color: var(--paper); }

/* 错误卡片 */
.error-card { border: 1px solid var(--crimson); background: rgba(184, 84, 80, 0.04); }

/* 标题卡片 */
.title-card { border-color: var(--clay-soft); box-shadow: var(--sh-clay); }

/* 备用标题 */
.alt-title-item { padding: 8px 12px; background: var(--bone); border-radius: var(--r-sm); }

/* 内容框 */
.content-box {
  background: var(--bone);
  border-radius: var(--r-md);
  padding: 16px;
  font-size: 15px;
  line-height: 1.8;
}

/* 标签 */
.tag-item {
  display: inline-block;
  padding: 4px 12px;
  background: var(--sand-soft);
  color: var(--clay);
  border-radius: var(--r-pill);
  font-size: 13px;
  font-weight: 500;
}

.bottom-actions { display: flex; justify-content: center; gap: 12px; }

.badge-primary {
  display: inline-block;
  padding: 4px 12px;
  background: var(--clay);
  color: var(--paper);
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
}
.badge-clay {
  display: inline-block;
  padding: 4px 12px;
  background: var(--sand);
  color: var(--paper);
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 600;
}

/* ===== 图文预览 ===== */
.article-preview {
  max-height: 600px;
  overflow-y: auto;
  padding-right: 8px;
}
.article-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink-2);
  margin-bottom: 12px;
}
.article-image-wrap {
  margin: 16px 0;
  text-align: center;
}
.article-image {
  max-width: 100%;
  max-height: 400px;
  border-radius: var(--r-md);
  object-fit: contain;
  background: var(--bone);
}

/* ===== 操作卡片 ===== */
.action-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: all 0.2s;
}
.action-card:hover {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-1);
}
.action-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--r-md);
  background: var(--bone);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-3);
  flex-shrink: 0;
}
.action-icon-primary {
  background: var(--clay);
  color: var(--paper);
}

/* ===== 模板选择 ===== */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.template-option {
  padding: 12px 16px;
  border: 2px solid var(--line);
  border-radius: var(--r-md);
  text-align: center;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-2);
  transition: all 0.2s;
}
.template-option:hover { border-color: var(--clay-soft); color: var(--ink); }
.template-option-active {
  border-color: var(--clay);
  background: var(--clay);
  color: var(--paper);
}
</style>
