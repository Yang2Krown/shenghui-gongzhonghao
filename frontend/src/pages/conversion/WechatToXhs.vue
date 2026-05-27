<template>
  <div class="wechat-to-xhs">
    <!-- 页头 -->
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">公众号转小红书</h1>
      <p class="text-sm text-ink-3 mt-1">将公众号文章内容一键转换为小红书风格文案</p>
    </header>

    <!-- 输入区域 -->
    <div class="card p-6 mb-6">
      <!-- 模式切换 -->
      <div class="flex gap-4 mb-6">
        <button
          class="mode-btn"
          :class="{ 'mode-btn-active': mode === 'paste' }"
          @click="mode = 'paste'"
        >
          <el-icon><Document /></el-icon>
          <span>粘贴内容</span>
        </button>
        <button
          class="mode-btn"
          :class="{ 'mode-btn-active': mode === 'link' }"
          @click="mode = 'link'"
        >
          <el-icon><Link /></el-icon>
          <span>公众号链接</span>
        </button>
      </div>

      <!-- 粘贴内容模式 -->
      <div v-if="mode === 'paste'">
        <div class="mb-4">
          <label class="label">原文标题（可选）</label>
          <el-input
            v-model="originalTitle"
            placeholder="输入公众号文章原标题"
          />
        </div>
        <div class="mb-4">
          <label class="label">文章内容</label>
          <el-input
            v-model="content"
            type="textarea"
            placeholder="请粘贴公众号文章正文内容..."
            :autosize="{ minRows: 8, maxRows: 20 }"
            resize="none"
          />
        </div>
        <div class="flex items-center justify-between">
          <span class="text-sm text-ink-3">{{ content.length }} 字</span>
          <el-button
            type="primary"
            size="large"
            @click="convertContent"
            :loading="loading"
            :disabled="content.length < 10"
          >
            转换为小红书文案
          </el-button>
        </div>
      </div>

      <!-- 链接模式 -->
      <div v-if="mode === 'link'">
        <div class="mb-4">
          <label class="label">公众号文章链接</label>
          <el-input
            v-model="linkUrl"
            placeholder="粘贴 mp.weixin.qq.com 的文章链接"
            clearable
          />
        </div>
        <div class="flex justify-end">
          <el-button
            type="primary"
            size="large"
            @click="convertLink"
            :loading="loading"
            :disabled="!linkUrl || !linkUrl.includes('weixin')"
          >
            提取并转换
          </el-button>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="card p-6 mb-6 error-card">
      <div class="flex items-center gap-3">
        <el-icon :size="24" style="color: var(--crimson);"><CircleCloseFilled /></el-icon>
        <div>
          <h3 class="text-base font-semibold text-ink">转换失败</h3>
          <p class="text-sm text-ink-3 mt-1">{{ error }}</p>
        </div>
      </div>
      <div class="mt-4">
        <el-button @click="error = ''">关闭</el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="card p-6 mb-6 text-center py-12">
      <el-icon class="is-loading" :size="32" style="color: var(--clay);"><Loading /></el-icon>
      <p class="text-ink-3 mt-3">正在生成小红书文案...</p>
    </div>

    <!-- 结果展示 -->
    <div v-if="result && !loading" class="result-area">
      <!-- 内容类型 -->
      <div v-if="result.type" class="mb-4">
        <span class="badge-primary">{{ result.type }}</span>
      </div>

      <!-- 主标题 -->
      <div v-if="result.title" class="card p-6 mb-4 title-card">
        <div class="flex items-center gap-2 mb-3">
          <span class="badge-clay">主标题</span>
        </div>
        <p class="text-xl font-bold text-ink text-center py-2">{{ result.title }}</p>
      </div>

      <!-- 备用标题 -->
      <div v-if="result.alt_titles && result.alt_titles.length" class="card p-6 mb-4">
        <h3 class="text-h4 font-sans text-ink mb-3">备用标题</h3>
        <div class="space-y-2">
          <div v-for="(title, i) in result.alt_titles" :key="i" class="alt-title-item">
            <span class="text-ink-4 mr-2">{{ i + 1 }}.</span>
            <span class="text-ink">{{ title }}</span>
          </div>
        </div>
      </div>

      <!-- 正文 -->
      <div v-if="result.content" class="card p-6 mb-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-h4 font-sans text-ink">正文</h3>
          <el-button
            text
            size="small"
            @click="copyContent"
          >
            <el-icon><CopyDocument /></el-icon>
            复制
          </el-button>
        </div>
        <div class="content-box whitespace-pre-wrap text-ink-2 leading-relaxed">{{ result.content }}</div>
        <div class="mt-3 text-sm text-ink-3 text-right">
          {{ result.content.length }} 字
        </div>
      </div>

      <!-- 标签 -->
      <div v-if="result.tags && result.tags.length" class="card p-6 mb-4">
        <h3 class="text-h4 font-sans text-ink mb-3">推荐标签</h3>
        <div class="flex flex-wrap gap-2">
          <span v-for="(tag, i) in result.tags" :key="i" class="tag-item">
            #{{ tag }}
          </span>
        </div>
      </div>

      <!-- 原文信息 -->
      <div v-if="result.original_title || result.original_author" class="card p-6 mb-4">
        <h3 class="text-h4 font-sans text-ink mb-3">原文信息</h3>
        <div class="space-y-2 text-sm">
          <p v-if="result.original_title" class="text-ink-2">
            <span class="text-ink-3">原标题：</span>{{ result.original_title }}
          </p>
          <p v-if="result.original_author" class="text-ink-2">
            <span class="text-ink-3">来源：</span>{{ result.original_author }}
          </p>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="bottom-actions">
        <el-button @click="reset">重新转换</el-button>
        <el-button type="primary" @click="copyAll">复制全部内容</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Link, CircleCloseFilled, Loading, CopyDocument } from '@element-plus/icons-vue'
import { post } from '@/api/api'

const mode = ref('paste')
const content = ref('')
const originalTitle = ref('')
const linkUrl = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const convertContent = async () => {
  if (content.value.length < 10) {
    ElMessage.warning('请输入至少10个字符的内容')
    return
  }

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

const convertLink = async () => {
  if (!linkUrl.value || !linkUrl.value.includes('weixin')) {
    ElMessage.warning('请输入有效的公众号链接')
    return
  }

  loading.value = true
  error.value = ''
  result.value = null

  try {
    const res = await post('/wechat-to-xhs/convert-link', {
      url: linkUrl.value
    }, { timeout: 120000 })
    result.value = res.data || res
    ElMessage.success('提取并转换成功')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '提取失败，请检查链接是否有效'
  } finally {
    loading.value = false
  }
}

const copyContent = async () => {
  if (!result.value?.content) return
  try {
    await navigator.clipboard.writeText(result.value.content)
    ElMessage.success('正文已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

const copyAll = async () => {
  if (!result.value) return

  let text = ''
  if (result.value.title) {
    text += `【主标题】\n${result.value.title}\n\n`
  }
  if (result.value.alt_titles?.length) {
    text += `【备用标题】\n${result.value.alt_titles.map((t, i) => `${i + 1}. ${t}`).join('\n')}\n\n`
  }
  if (result.value.content) {
    text += `【正文】\n${result.value.content}\n\n`
  }
  if (result.value.tags?.length) {
    text += `【标签】\n${result.value.tags.map(t => `#${t}`).join(' ')}`
  }

  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('全部内容已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

const reset = () => {
  result.value = null
  error.value = ''
  content.value = ''
  originalTitle.value = ''
  linkUrl.value = ''
}

onBeforeRouteLeave(async (to, from, next) => {
  if (!result.value) return next()
  try {
    await ElMessageBox.confirm(
      '离开后当前转换结果将丢失，确定离开吗？',
      '确认离开',
      { confirmButtonText: '仍然离开', cancelButtonText: '留在此页', type: 'warning' }
    )
    next()
  } catch { next(false) }
})

const handleBeforeUnload = (e) => {
  if (result.value) { e.preventDefault(); e.returnValue = '' }
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

.mode-btn:hover {
  border-color: var(--clay-soft);
  color: var(--ink);
}

.mode-btn-active {
  background: var(--clay);
  border-color: var(--clay);
  color: var(--paper);
}

.mode-btn-active:hover {
  background: var(--clay-deep);
  border-color: var(--clay-deep);
  color: var(--paper);
}

/* 错误卡片 */
.error-card {
  border: 1px solid var(--crimson);
  background: rgba(184, 84, 80, 0.04);
}

/* 标题卡片 */
.title-card {
  border-color: var(--clay-soft);
  box-shadow: var(--sh-clay);
}

/* 备用标题 */
.alt-title-item {
  padding: 8px 12px;
  background: var(--bone);
  border-radius: var(--r-sm);
}

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

/* 底部操作 */
.bottom-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* 标签样式 */
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
</style>
