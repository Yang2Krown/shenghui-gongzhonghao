<template>
  <div class="wechat-editor-page">
    <!-- Hero -->
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><EditPen /></el-icon>
        创作工具 · 公众号编辑器
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        排版你的<span class="text-clay">公众号文章</span>
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        粘贴或编辑正文，用工具栏排版，一键发布到公众号草稿箱。
      </p>
      <!-- 自动填充的标题 -->
      <div v-if="articleTitle" class="auto-title-bar">
        <span class="auto-title-label">文章标题</span>
        <span class="auto-title-text">{{ articleTitle }}</span>
        <button class="auto-title-edit" @click="showPublishDialog = true">编辑</button>
      </div>
    </div>

    <!-- 富文本编辑器 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <WechatRichEditor
        ref="editorRef"
        v-model="editorHtml"
        placeholder="在这里编辑文章正文……&#10;&#10;支持工具栏排版、一键排版、快捷样式按钮。"
      />
    </div>

    <!-- 底部操作栏 -->
    <div class="bottom-actions" style="display: flex; align-items: center; gap: 12px;">
      <button class="btn-ghost btn-uniform" @click="copyHtml">
        <el-icon :size="15"><CopyDocument /></el-icon> 复制 HTML
      </button>
      <button class="btn-ghost btn-uniform" @click="copyPlainText">
        <el-icon :size="15"><CopyDocument /></el-icon> 复制纯文本
      </button>
      <div style="flex: 1;"></div>
      <button class="btn-ghost btn-uniform btn-format" @click="oneClickFormat">
        <el-icon :size="15"><MagicStick /></el-icon> 一键排版
      </button>
      <button class="btn-ghost btn-uniform btn-publish" @click="openPublishDialog">
        <el-icon><Promotion /></el-icon>
        发布到公众号草稿箱
      </button>
    </div>

    <!-- 发布弹窗（精简版：封面 + 确认） -->
    <el-dialog
      v-model="showPublishDialog"
      title="发布到公众号草稿箱"
      width="520px"
      :close-on-click-modal="false"
    >
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <!-- 标题 -->
        <el-input
          v-model="articleTitle"
          placeholder="文章标题（必填，不超过 64 字）"
          maxlength="64"
          show-word-limit
        />

        <!-- 校验提示 -->
        <div v-if="!wechatConfigured" class="card" style="padding: 14px 18px; border-color: var(--crimson);">
          <p class="text-sm" style="color: var(--crimson); margin-bottom: 8px;">
            未配置公众号账号，请先到「个人信息」页面添加公众号。
          </p>
          <button class="btn-ghost btn-sm" @click="router.push('/profile')">去配置</button>
        </div>

        <!-- 封面图 -->
        <div class="cover-section">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-size: 14px; font-weight: 600; color: var(--ink);">封面图</div>
              <div style="font-size: 12px; color: var(--ink-4);">公众号草稿必须带封面图</div>
            </div>
            <div style="display: flex; gap: 8px;">
              <label class="cover-btn cover-btn-upload">
                <el-icon><Upload /></el-icon> 上传
                <input type="file" accept="image/*" style="display:none" @change="handleCoverUpload" />
              </label>
              <button class="cover-btn cover-btn-ai" @click="handleGenerateCover" :disabled="generatingCover">
                <el-icon v-if="generatingCover" class="spin"><Loading /></el-icon>
                <el-icon v-else><MagicStick /></el-icon>
                {{ generatingCover ? '生成中...' : 'AI 封面' }}
              </button>
            </div>
          </div>
          <div v-if="coverPreview" style="position: relative; margin-top: 10px; border-radius: 8px; overflow: hidden; border: 1px solid var(--line);">
            <img :src="coverPreview" style="width: 100%; aspect-ratio: 21/9; object-fit: cover; display: block;" />
            <button @click="removeCover" style="position: absolute; top: 6px; right: 6px; width: 24px; height: 24px; border-radius: 50%; border: none; background: rgba(0,0,0,.5); color: #fff; cursor: pointer; font-size: 14px;">×</button>
          </div>
          <div v-if="coverError" style="color: var(--crimson); font-size: 12px; margin-top: 6px;">{{ coverError }}</div>
        </div>

        <!-- 摘要 -->
        <el-input v-model="digest" type="textarea" :rows="2" placeholder="文章摘要（选填，不填自动截取）" maxlength="120" show-word-limit />

        <!-- 操作 -->
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
          <button class="btn-ghost" @click="showPublishDialog = false">取消</button>
          <button
            class="cta-bar"
            style="width: auto; padding: 12px 28px;"
            :disabled="!canPublish || publishing"
            @click="handlePublish"
          >
            <el-icon v-if="publishing" class="spin"><Loading /></el-icon>
            <el-icon v-else><Promotion /></el-icon>
            {{ publishing ? '发布中...' : '确认发布' }}
          </button>
        </div>

        <p v-if="publishResult" :style="{ color: publishResult.success ? '#52c41a' : 'var(--crimson)', fontSize: '13px' }">
          {{ publishResult.message }}
        </p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { EditPen, Promotion, CopyDocument, Upload, Loading, MagicStick } from '@element-plus/icons-vue'
import WechatRichEditor from '@/components/ui/WechatRichEditor.vue'
import { get, createWechatDraft, generateWechatCover } from '@/api/api'

const router = useRouter()

const articleTitle = ref('')
const editorHtml = ref('')
const editorRef = ref(null)

// 发布相关
const showPublishDialog = ref(false)
const openPublishDialog = () => {
  // 自动从编辑器内容提取标题（如果用户还没填）
  if (!articleTitle.value && editorRef.value) {
    const autoTitle = editorRef.value.extractTitle()
    if (autoTitle) articleTitle.value = autoTitle
  }
  showPublishDialog.value = true
}
const publishing = ref(false)
const publishResult = ref(null)
const digest = ref('')
const coverPreview = ref('')
const coverBase64 = ref('')
const coverFile = ref(null)
const generatingCover = ref(false)
const coverError = ref('')

// 从 API 加载公众号账号配置
const defaultAccountId = ref(null)
const wechatConfigured = ref(false)

const loadWechatAccount = async () => {
  try {
    const res = await get('/wechat-accounts')
    const accounts = res.data || []
    const defaultAcc = accounts.find(a => a.is_default) || accounts[0]
    if (defaultAcc) {
      defaultAccountId.value = defaultAcc.id
      wechatConfigured.value = true
    } else {
      wechatConfigured.value = false
    }
  } catch { wechatConfigured.value = false }
}

const canPublish = computed(() => {
  return wechatConfigured.value && articleTitle.value.trim() && editorHtml.value.trim()
})

// 从 sessionStorage 读取传入的内容（如果从其他页面跳转过来）
onMounted(() => {
  loadWechatAccount()
  const savedContent = sessionStorage.getItem('wechat_editor_content')
  const savedTitle = sessionStorage.getItem('wechat_editor_title')
  console.log('[WechatEditor] onMounted', {
    hasContent: !!savedContent,
    contentLength: savedContent?.length || 0,
    contentPreview: (savedContent || '').slice(0, 100),
    savedTitle,
  })
  if (savedContent) {
    editorHtml.value = savedContent
    sessionStorage.removeItem('wechat_editor_content')
    // wangEditor v-model 不一定触发内容更新，用 setHtml 强制设置
    nextTick(() => {
      if (editorRef.value?.setHtml) {
        editorRef.value.setHtml(savedContent)
      }
    })
  }
  if (savedTitle) {
    articleTitle.value = savedTitle
    sessionStorage.removeItem('wechat_editor_title')
  }
})

// ── 一键排版 ──
const oneClickFormat = () => {
  if (!editorRef.value) return
  const editor = editorRef.value.getEditor()
  if (!editor) return

  const html = editor.getHtml() || ''
  if (!html.trim()) {
    ElMessage.warning('编辑器内容为空')
    return
  }

  const doc = new DOMParser().parseFromString(html, 'text/html')
  const body = doc.body

  // 1. 清理标点符号
  const cleanPunc = (text) => {
    text = text.replace(/[\u201c\u201d]/g, '')   // ""
    text = text.replace(/[\u2018\u2019]/g, '')   // ''
    text = text.replace(/[《》]/g, '')             // 《》
    text = text.replace(/——/g, '，')              // ——→，
    // 多个 …… 只保留第一个
    let count = 0
    text = text.replace(/……/g, () => { count++; return count === 1 ? '……' : '。' })
    return text
  }

  // 遍历所有段落块
  const blocks = body.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, blockquote')
  blocks.forEach(block => {
    // 清理标点
    const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT)
    while (walker.nextNode()) {
      walker.currentNode.textContent = cleanPunc(walker.currentNode.textContent)
    }

    const tag = block.tagName.toLowerCase()
    const text = (block.textContent || '').trim()

    // 2. 判断是否是段落大标题（h1/h2 或者之前设过的标题样式）
    const isHeading = tag === 'h1' || tag === 'h2'
    const existingStyle = block.getAttribute('style') || ''
    const isStyledHeading = /font-size:\s*20px/.test(existingStyle) && /font-weight:\s*(bold|700)/.test(existingStyle)

    if (isHeading || isStyledHeading) {
      // 3. 段落大标题：20px 加粗 黑底白字 inline
      block.style.display = 'inline'
      block.style.fontSize = '20px'
      block.style.fontWeight = 'bold'
      block.style.color = '#ffffff'
      block.style.backgroundColor = '#000000'
      block.style.lineHeight = '1.75'
      block.style.padding = '2px 6px'
      block.style.marginBottom = '24px'
      block.style.textAlign = 'left'
    } else if (tag !== 'li' && tag !== 'blockquote') {
      // 5. 正常段落：16px 两端对齐，段前0 段后24
      block.style.fontSize = '16px'
      block.style.lineHeight = '24px'
      block.style.textAlign = 'justify'
      block.style.marginTop = '0'
      block.style.marginBottom = '24px'
      block.style.color = '#333333'
      block.style.fontWeight = 'normal'
      block.style.backgroundColor = ''
      block.style.display = ''
      block.style.padding = ''
    }
  })

  // 4. 红色重点段落检查：红色文字必须单独成段
  body.querySelectorAll('p').forEach(p => {
    const hasRed = p.querySelector('[style*="color: rgb(192, 57, 43)"], [style*="color:#c0392b"], [style*="color: #c0392b"], [style*="color: red"]')
    if (hasRed) {
      // 确保整段都是红色重点，而不是混排
      // 如果段落里有非红色文字，把整段标红加粗
      const allText = p.textContent.trim()
      if (allText) {
        p.style.color = '#c0392b'
        p.style.fontWeight = 'bold'
      }
    }
  })

  // 回写到编辑器
  editor.setHtml(body.innerHTML)
  ElMessage.success('排版完成')
}

// 复制
const copyHtml = () => {
  navigator.clipboard?.writeText(editorHtml.value).catch(() => {})
  ElMessage.success('HTML 已复制')
}
const copyPlainText = () => {
  const div = document.createElement('div')
  div.innerHTML = editorHtml.value || ''
  navigator.clipboard?.writeText(div.textContent || '').catch(() => {})
  ElMessage.success('纯文本已复制')
}

// 封面图
const handleCoverUpload = (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) { ElMessage.error('封面图不能超过 5MB'); return }
  coverFile.value = file
  coverError.value = ''
  const reader = new FileReader()
  reader.onload = (ev) => {
    coverPreview.value = ev.target.result
    coverBase64.value = ev.target.result
  }
  reader.readAsDataURL(file)
}
const removeCover = () => {
  coverPreview.value = ''
  coverBase64.value = ''
  coverFile.value = null
}
const handleGenerateCover = async () => {
  if (!articleTitle.value && !editorHtml.value) {
    ElMessage.warning('请先填写标题或正文')
    return
  }
  generatingCover.value = true
  coverError.value = ''
  try {
    const div = document.createElement('div')
    div.innerHTML = editorHtml.value || ''
    const plainText = (div.textContent || '').slice(0, 500)
    const res = await generateWechatCover(articleTitle.value, plainText, '')
    const data = res.data || res
    if (data.url) {
      coverPreview.value = data.url
      coverBase64.value = ''
      ElMessage.success('封面生成成功')
    }
  } catch (e) {
    coverError.value = e?.response?.data?.detail || '封面生成失败'
  } finally {
    generatingCover.value = false
  }
}

// 发布
const handlePublish = async () => {
  if (!wechatConfigured.value || !defaultAccountId.value) {
    ElMessage.warning('请先到「个人信息」配置公众号账号')
    return
  }
  publishing.value = true
  publishResult.value = null
  try {
    const params = {
      title: articleTitle.value.trim(),
      content: editorRef.value ? editorRef.value.getWechatHtml() : editorHtml.value,
      account_id: defaultAccountId.value,
      digest: digest.value || '',
    }
    if (coverBase64.value) params.cover_image_base64 = coverBase64.value
    else if (coverPreview.value) params.cover_image_url = coverPreview.value

    const res = await createWechatDraft(params)
    const data = res.data || res
    if (data.success) {
      publishResult.value = { success: true, message: `发布成功！media_id: ${data.media_id || ''}` }
      ElMessage.success('已发布到公众号草稿箱')
    } else {
      publishResult.value = { success: false, message: data.message || '发布失败' }
    }
  } catch (e) {
    publishResult.value = { success: false, message: e?.response?.data?.detail || '发布失败' }
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped>
.wechat-editor-page {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px - 64px);  /* 减去 topbar 60px 和 padding 64px */
  overflow: hidden;
}

.wechat-editor-page .tool-hero {
  flex-shrink: 0;
}

.wechat-editor-page .card {
  flex: 1;
  min-height: 0;  /* 关键：让 flex 子元素可以收缩到比内容小 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 让编辑器填满 card 的剩余空间 */
.wechat-editor-page .card :deep(.wechat-editor-wrap) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.wechat-editor-page .card :deep(.wechat-editor-content) {
  flex: 1;
  min-height: 0 !important;
  max-height: none !important;
  overflow-y: auto;
}

.wechat-editor-page .card :deep(.w-e-text-container [data-slate-editor]) {
  min-height: 100% !important;
}

.wechat-editor-page .bottom-actions {
  flex-shrink: 0;
  padding-top: 8px;
  padding-bottom: 8px;
}

.tool-hero { position: relative; margin-bottom: 16px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }

/* 自动标题栏 */
.auto-title-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding: 10px 14px;
  background: var(--ivory);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
}
.auto-title-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--clay-deep);
  background: var(--clay-tint);
  border: 1px solid var(--clay-soft);
  padding: 2px 8px;
  border-radius: var(--r-pill);
  flex-shrink: 0;
}
.auto-title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.auto-title-edit {
  flex-shrink: 0;
  padding: 4px 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--paper);
  color: var(--ink-3);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.14s;
}
.auto-title-edit:hover {
  border-color: var(--clay-soft);
  color: var(--clay-deep);
}

.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }

.btn-ghost { display: inline-flex; align-items: center; gap: 5px; padding: 10px 18px; border: 1px solid var(--line); background: var(--paper); color: var(--ink-2); font-family: inherit; font-size: 13px; font-weight: 500; cursor: pointer; border-radius: var(--r-md); transition: all .14s; }
.btn-ghost:hover { border-color: var(--clay-soft); color: var(--clay-deep); }
.btn-sm { padding: 5px 10px; font-size: 12px; }

.btn-uniform {
  padding: 12px 20px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  border-color: var(--clay-soft) !important;
  color: var(--ink-2) !important;
}
.btn-uniform:hover { border-color: var(--clay) !important; color: var(--clay-deep) !important; }
.btn-format { border-color: var(--clay) !important; color: var(--clay-deep) !important; }
.btn-publish {
  background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%) !important;
  color: #fff !important;
  border: none !important;
  box-shadow: 0 4px 12px rgba(204,120,92,.25);
}
.btn-publish:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(204,120,92,.35); }

.cover-section { padding: 16px; background: var(--bone); border-radius: var(--r-md); }
.cover-btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 8px 14px; border-radius: var(--r-md); font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.cover-btn-upload { border: 1.5px dashed var(--line); background: var(--paper); color: var(--ink-2); }
.cover-btn-upload:hover { border-color: var(--clay-soft); background: var(--clay-tint); }
.cover-btn-ai { border: 1.5px solid var(--clay); background: var(--clay); color: #fff; }
.cover-btn-ai:hover:not([disabled]) { background: var(--clay-deep); }
.cover-btn-ai[disabled] { opacity: 0.5; cursor: not-allowed; }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
