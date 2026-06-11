<template>
  <div class="wechat-editor-wrap">
    <!-- 工具栏 -->
    <Toolbar
      class="wechat-toolbar"
      :editor="editorRef"
      :defaultConfig="toolbarConfig"
      :mode="'default'"
    />
    <!-- 编辑区 -->
    <Editor
      class="wechat-editor-content"
      v-model="valueHtml"
      :defaultConfig="editorConfig"
      :mode="'default'"
      @onCreated="handleCreated"
      @onChange="handleChange"
    />
    <!-- 底部栏 -->
    <div class="wechat-editor-footer">
      <div class="footer-left">
        <span class="text-xs text-ink-4">{{ charCount }} 字</span>
        <span class="text-xs text-ink-4" style="margin-left: 8px;">{{ paragraphCount }} 段</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, onBeforeUnmount } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import '@wangeditor/editor/dist/css/style.css'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '开始写作……' },
})

const emit = defineEmits(['update:modelValue'])

const editorRef = shallowRef(null)
const valueHtml = ref(props.modelValue)
const charCount = ref(0)
const paragraphCount = ref(0)
const spacingBefore = ref('0')
const spacingAfter = ref('24px')
// 保存最后已知的段落路径（handleChange 时更新），用于 popup 弹出时 selection 已丢失的情况
let _lastKnownPath = 0

// ─── 注册自定义段前/段后距菜单 ───
import { Boot, SlateEditor, i18nAddResources } from '@wangeditor/editor'

// 从根源去掉"默认字号"/"默认字体"：覆盖 i18n 翻译
try {
  i18nAddResources('zh-CN', {
    fontSize: { title: '字号', default: '16px' },
    fontFamily: { title: '字体', default: '微软雅黑' },
  })
  i18nAddResources('en', {
    fontSize: { title: 'Font Size', default: '16px' },
    fontFamily: { title: 'Font Family', default: '微软雅黑' },
  })
} catch (e) { console.warn('i18n override:', e.message) }

// 从根源修改 headerSelect：把 H2 改成 二级标题
// wangEditor 不允许重新注册同名菜单，但可以拦截工厂函数
try {
  const _origReg = Boot.registerMenu
  Boot.registerMenu = function(conf, customConfig) {
    if (conf.key === 'headerSelect') {
      const origFactory = conf.factory
      conf.factory = function() {
        const menu = origFactory()
        const origGetOptions = menu.getOptions.bind(menu)
        menu.getOptions = (editor) => {
          const opts = origGetOptions(editor)
          return opts.map(opt => opt.value === 'header2' ? { ...opt, text: '二级标题' } : opt)
        }
        return menu
      }
    }
    return _origReg.call(this, conf, customConfig)
  }
} catch (e) { console.warn('headerSelect override:', e.message) }

const spacingOptions = ['0', '4px', '8px', '12px', '16px', '24px', '32px']

// 全局 Map：存储每段的间距（key=段落索引）
const _spacingMap = new Map()

// 从 Map 读取当前段落间距（overridePath 用于 popup 点击时 selection 已丢失的情况）
function _getSpacingFromMap(editor, type, overridePath) {
  try {
    const path = overridePath ?? editor.selection?.anchor?.path?.[0] ?? _lastKnownPath
    if (path == null) return type === 'before' ? '0' : '24px'
    const sp = _spacingMap.get(path)
    if (!sp) return type === 'before' ? '0' : '24px'
    return (type === 'before' ? sp.before : sp.after) || (type === 'before' ? '0' : '24px')
  } catch (e) { return type === 'before' ? '0' : '24px' }
}

// 设置间距：存入 Map + 应用 inline style
function _applySpacingToDOM(editor, type, value, overridePath) {
  try {
    const path = overridePath ?? editor.selection?.anchor?.path?.[0] ?? _lastKnownPath
    if (path == null) return
    const sp = _spacingMap.get(path) || { before: '0', after: '24px' }
    if (type === 'before') sp.before = value; else sp.after = value
    _spacingMap.set(path, sp)
    // editor.getEditableContainer() 返回 .w-e-text-container（含进度条等子元素），
    // 实际段落是 [data-slate-editor] 的直接子元素
    const editorEl = document.querySelector('[data-slate-editor]')
    const pEl = editorEl?.children?.[path]
    if (pEl) {
      pEl.style.marginTop = sp.before
      pEl.style.marginBottom = sp.after
    }
  } catch (e) { console.warn('applySpacing error:', e) }
}

// 同步所有段落间距到 DOM（处理 wangEditor 重新渲染的情况）
function _syncAllSpacing() {
  try {
    const editor = editorRef.value
    if (!editor) return
    const editorEl = document.querySelector('[data-slate-editor]')
    if (!editorEl) return
    for (const [idx, sp] of _spacingMap) {
      const pEl = editorEl.children[idx]
      if (pEl) {
        // 仅在值不同时才写入，减少 DOM mutation
        if (sp.before && pEl.style.marginTop !== sp.before) pEl.style.marginTop = sp.before
        if (sp.after && pEl.style.marginBottom !== sp.after) pEl.style.marginBottom = sp.after
      }
    }
  } catch (e) { /* ignore */ }
}

function _showSpacingPopup(editor, type, btnEl) {
  // 在 popup 出现前锁定当前段落路径，避免 editor blur 后 selection 丢失
  const savedPath = editor.selection?.anchor?.path?.[0] ?? _lastKnownPath
  if (savedPath == null) return
  document.querySelectorAll('.spacing-popup').forEach(el => el.remove())
  const popup = document.createElement('div')
  popup.className = 'spacing-popup'
  popup.style.cssText = 'position:absolute;background:#fff;border:1px solid #ddd;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.12);padding:4px 0;z-index:9999;min-width:56px;'
  const currentVal = _getSpacingFromMap(editor, type, savedPath)
  for (const v of spacingOptions) {
    const opt = document.createElement('div')
    opt.textContent = v
    opt.style.cssText = `padding:6px 16px;font-size:13px;text-align:center;cursor:pointer;${v === currentVal ? 'color:#CC785C;font-weight:600;background:#fdf5f0;' : 'color:#333;'}`
    opt.onmouseenter = () => { opt.style.background = '#f5f5f5' }
    opt.onmouseleave = () => { opt.style.background = v === currentVal ? '#fdf5f0' : '#fff' }
    opt.onclick = () => { _applySpacingToDOM(editor, type, v, savedPath); popup.remove() }
    popup.appendChild(opt)
  }
  document.body.appendChild(popup)
  const rect = btnEl.getBoundingClientRect()
  popup.style.left = rect.left + 'px'
  popup.style.top = (rect.bottom + 4) + 'px'
  const close = (e) => { if (!popup.contains(e.target)) { popup.remove(); document.removeEventListener('click', close) } }
  setTimeout(() => document.addEventListener('click', close), 0)
}

// 段前距按钮 class（和缩进按钮同模式，editor 由 wangEditor 传入，不依赖闭包）
class ParagraphBeforeMenu {
  constructor() {
    this.title = '段前距'
    this.tag = 'button'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M0 0h1024v128H0z M512 256L320 448h384z M0 576h1024v128H0z M0 768h1024v128H0z" fill="currentColor"></path></svg>'
  }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor) {
    const btn = document.querySelector('button[data-menu-key="paragraphBefore"]')
    if (btn) _showSpacingPopup(editor, 'before', btn)
  }
}

class ParagraphAfterMenu {
  constructor() {
    this.title = '段后距'
    this.tag = 'button'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M0 0h1024v128H0z M0 192h1024v128H0z M320 448h384L512 640z M0 768h1024v128H0z" fill="currentColor"></path></svg>'
  }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor) {
    const btn = document.querySelector('button[data-menu-key="paragraphAfter"]')
    if (btn) _showSpacingPopup(editor, 'after', btn)
  }
}

try {
  Boot.registerMenu({ key: 'paragraphBefore', factory() { return new ParagraphBeforeMenu() } })
} catch (e) { console.warn('registerMenu paragraphBefore:', e.message) }
try {
  Boot.registerMenu({ key: 'paragraphAfter', factory() { return new ParagraphAfterMenu() } })
} catch (e) { console.warn('registerMenu paragraphAfter:', e.message) }

watch(() => props.modelValue, (val) => {
  if (val !== valueHtml.value) {
    valueHtml.value = plainTextToHtml(val)
  }
})

// ─── 工具栏配置 ───
const toolbarConfig = {
  toolbarKeys: [
    // 标题 + 段落
    'headerSelect',
    'blockquote',
    '|',
    // 文字样式
    'bold',
    'underline',
    'italic',
    {
      key: 'group-more-style',
      title: '更多',
      menuKeys: ['through', 'sup', 'sub', 'clearStyle'],
    },
    '|',
    // 字号 + 字体 + 颜色
    'fontSize',
    'fontFamily',
    'color',
    'bgColor',
    '|',
    // 对齐 + 缩进
    'justifyLeft',
    'justifyCenter',
    'justifyRight',
    'justifyJustify',
    'indent',
    'delIndent',
    'paragraphBefore',
    'paragraphAfter',
    '|',
    // 插入
    'insertLink',
    {
      key: 'group-image',
      title: '图片',
      menuKeys: ['insertImage', 'uploadImage'],
    },
    'emotion',
    'insertTable',
    'codeBlock',
    'divider',
    '|',
    // 撤销
    'undo',
    'redo',
    '|',
    // 列表（第二行）
    'bulletedList',
    'numberedList',
    'todo',
  ],
  // 排除视频模块（公众号不支持）
  excludeKeys: ['group-video', 'insertVideo', 'uploadVideo'],
}

// ─── 编辑器配置 ───
const editorConfig = {
  placeholder: props.placeholder,
  // 图片配置
  MENU_CONF: {
    uploadImage: {
      // 不使用内置上传，改为插入 URL
      customUpload: (insertFn) => {
        const url = prompt('请输入图片 URL：')
        if (url) insertFn(url, '', '')
      },
    },
    insertImage: {
      // 也支持直接插入
      onInsertedImage: (imageNode) => {
        if (imageNode == null) return
        const { src } = imageNode
        if (src) ElMessage.success('图片已插入')
      },
    },
    // 字号选项 —— 公众号常用
    fontSize: {
      fontSizeList: [
        { name: '12px', value: '12px' },
        { name: '13px', value: '13px' },
        { name: '14px', value: '14px' },
        { name: '15px', value: '15px' },
        { name: '16px', value: '16px' },
        { name: '18px', value: '18px' },
        { name: '20px', value: '20px' },
        { name: '22px', value: '22px' },
        { name: '24px', value: '24px' },
        { name: '28px', value: '28px' },
        { name: '32px', value: '32px' },
      ],
    },
    // 字体
    fontFamily: {
      fontFamilyList: [
        { name: '默认', value: '' },
        { name: '宋体', value: 'SimSun, serif' },
        { name: '黑体', value: 'SimHei, sans-serif' },
        { name: '楷体', value: 'KaiTi, serif' },
        { name: '仿宋', value: 'FangSong, serif' },
        { name: '微软雅黑', value: '"Microsoft YaHei", sans-serif' },
      ],
    },
    // 颜色 —— 公众号常用色板
    color: {
      colors: [
        '#ffffff', '#000000', '#333333', '#555555', '#666666', '#999999',
        '#c0392b', '#e74c3c',  // 红色系（重点强调）
        '#2c3e50', '#34495e',  // 深蓝灰
        '#8B4513', '#A0522D',  // 棕色系
        '#27ae60', '#16a085',  // 绿色系
        '#2980b9', '#8e44ad',  // 蓝紫
        '#f39c12', '#e67e22',  // 橙色系
      ],
    },
    bgColor: {
      colors: [
        '#000000', '#333333', '#555555',
        '#f5f5dc', '#fff3cd', '#d4edda',
        '#f8d7da', '#d1ecf1', '#e2e3e5',
        '#fef9e7', '#fdebd0', '#fadbd8',
        'transparent',
      ],
    },
    // 表格
    insertTable: {
      maxRow: 10,
      maxCol: 8,
    },
  },
}

// ─── 编辑器事件 ───
const handleCreated = (editor) => {
  editorRef.value = editor
  updateCounts()

  const editableEl = editor.getEditableContainer()
  if (!editableEl) return

  // 粘贴长文时阻止自动滚到底部
  editableEl.addEventListener('paste', () => {
    const scrollEl = editableEl.closest('.wechat-editor-content') || editableEl.parentElement
    if (scrollEl) {
      const scrollTop = scrollEl.scrollTop
      requestAnimationFrame(() => { scrollEl.scrollTop = scrollTop })
    }
  }, true)

  // ── 工具栏 DOM 修改 ──
  const wrap = editableEl.closest('.wechat-editor-wrap')
  if (!wrap) return

  // 1. 点击工具栏时，延迟修改下拉选项（事件委托，不怕元素重建）
  wrap.addEventListener('click', (e) => {
    // headerSelect: 只保留正文+二级标题
    if (e.target.closest('button[data-menu-key="headerSelect"]')) {
      requestAnimationFrame(() => {
        document.querySelectorAll('.w-e-select-list').forEach(panel => {
          panel.querySelectorAll('li[data-value]').forEach(li => {
            const val = li.getAttribute('data-value')
            if (val && val.startsWith('header') && val !== 'header2') li.style.display = 'none'
            if (val === 'header2') {
              const span = li.querySelector('span')
              if (span) span.textContent = '二级标题'
              li.style.fontSize = '14px'
              li.style.fontWeight = 'normal'
            }
            li.addEventListener('click', () => { requestAnimationFrame(patchToolbarBtns) }, { once: true })
          })
        })
      })
    }
    // fontSize: "默认字号" 改成 "16px"
    if (e.target.closest('button[data-menu-key="fontSize"]')) {
      requestAnimationFrame(() => {
        document.querySelectorAll('.w-e-select-list').forEach(panel => {
          panel.querySelectorAll('li[data-value]').forEach(li => {
            if (!li.getAttribute('data-value')) {
              const span = li.querySelector('span')
              if (span) span.textContent = '16px'
            }
          })
        })
      })
    }
    // fontFamily: "默认字体" 改成 "微软雅黑"
    if (e.target.closest('button[data-menu-key="fontFamily"]')) {
      requestAnimationFrame(() => {
        document.querySelectorAll('.w-e-select-list').forEach(panel => {
          panel.querySelectorAll('li[data-value]').forEach(li => {
            if (!li.getAttribute('data-value')) {
              const span = li.querySelector('span')
              if (span) span.textContent = '微软雅黑'
            }
          })
        })
      })
    }
    // headerSelect: 点击时把下拉选项的 H2 改成 二级标题
    if (e.target.closest('button[data-menu-key="headerSelect"]')) {
      requestAnimationFrame(() => {
        document.querySelectorAll('.w-e-select-list').forEach(panel => {
          panel.querySelectorAll('li[data-value]').forEach(li => {
            const val = li.getAttribute('data-value')
            if (val === 'header2') {
              const span = li.querySelector('span')
              if (span) span.textContent = '二级标题'
            }
            li.addEventListener('click', () => { setTimeout(patchToolbarBtns, 250) }, { once: true })
          })
        })
      })
    }
  })

  // 2. 工具栏按钮文字替换（防覆盖）
  const replaceButtonText = (btn, newText) => {
    for (const child of btn.childNodes) {
      if (child.nodeType === 3) {
        child.textContent = newText
        return
      }
    }
    btn.insertBefore(document.createTextNode(newText), btn.firstChild)
  }

  const patchToolbarBtns = () => {
    // headerSelect: 把 H2 改成 二级标题
    const headerBtn = wrap.querySelector('button[data-menu-key="headerSelect"]')
    if (headerBtn) {
      const txt = headerBtn.textContent.trim()
      if (txt.startsWith('H2')) replaceButtonText(headerBtn, '二级标题 ')
    }

    // fontSize: 去掉"默认"，显示 16px
    const sizeBtn = wrap.querySelector('button[data-menu-key="fontSize"]')
    if (sizeBtn) {
      const txt = sizeBtn.textContent.trim()
      if (txt === '默认字号' || txt === '字号') {
        replaceButtonText(sizeBtn, '16px ')
      }
    }

    // fontFamily: 去掉"默认"，显示微软雅黑
    const fontBtn = wrap.querySelector('button[data-menu-key="fontFamily"]')
    if (fontBtn) {
      const txt = fontBtn.textContent.trim()
      if (txt === '默认字体' || txt === '字体') {
        replaceButtonText(fontBtn, '微软雅黑 ')
      }
    }

  }

  _patchToolbarBtns = patchToolbarBtns
  patchToolbarBtns()
  setInterval(patchToolbarBtns, 50)

  // 每 100ms 重新同步段前/段后距（wangEditor 重渲染会清除 inline styles）
  setInterval(_syncAllSpacing, 100)
}

// ─── 工具栏文字更新（模块级，handleChange 也能调用） ───
let _patchToolbarBtns = () => {}

const handleChange = (editor) => {
  const html = editor.getHtml()
  valueHtml.value = html
  emit('update:modelValue', html)
  updateCounts()
  // 更新最后已知段落路径，用于间距 popup 定位
  _lastKnownPath = editor.selection?.anchor?.path?.[0] ?? _lastKnownPath
  _syncAllSpacing()
  // requestAnimationFrame 确保在 wangEditor 更新工具栏之后立即替换
  requestAnimationFrame(() => { _patchToolbarBtns() })
}

const updateCounts = () => {
  if (!editorRef.value) return
  const text = editorRef.value.getText() || ''
  charCount.value = text.replace(/\s/g, '').length
  // 统计段落数（p、h1-h6、li、blockquote 各算一段）
  const html = editorRef.value.getHtml() || ''
  const matches = html.match(/<(p|h[1-6]|li|blockquote)[\s>]/gi)
  paragraphCount.value = matches ? matches.length : 0
}

// ─── 快捷排版功能 ───

const applyTitleStyle = () => {
  const editor = editorRef.value
  if (!editor) return
  const { selection } = editor
  if (!selection) { ElMessage.warning('请先选中一段文字'); return }
  editor.addMark('fontSize', '20px')
  editor.addMark('bold', true)
  editor.addMark('color', '#ffffff')
  editor.addMark('bgColor', '#000000')
  ElMessage.success('已设为大标题样式')
}

const applySubtitleStyle = () => {
  const editor = editorRef.value
  if (!editor) return
  const { selection } = editor
  if (!selection) { ElMessage.warning('请先选中一段文字'); return }
  editor.addMark('fontSize', '18px')
  editor.addMark('bold', true)
  editor.addMark('color', '#000000')
  ElMessage.success('已设为小标题样式')
}

const applyHighlightStyle = () => {
  const editor = editorRef.value
  if (!editor) return
  const { selection } = editor
  if (!selection) { ElMessage.warning('请先选中一段文字'); return }
  editor.addMark('color', '#c0392b')
  editor.addMark('bold', true)
  ElMessage.success('已标红')
}

const clearFormat = () => {
  const editor = editorRef.value
  if (!editor) return
  editor.removeMark('fontSize')
  editor.removeMark('bold')
  editor.removeMark('italic')
  editor.removeMark('underline')
  editor.removeMark('through')
  editor.removeMark('color')
  editor.removeMark('bgColor')
  editor.removeMark('sup')
  editor.removeMark('sub')
  ElMessage.success('已清除格式')
}

const insertDivider = () => {
  const editor = editorRef.value
  if (!editor) return
  editor.insertNode({ type: 'divider', children: [{ text: '' }] })
  ElMessage.success('已插入分割线')
}

// ─── 从编辑器内容中自动提取标题 ───
function extractTitle() {
  const editor = editorRef.value
  if (!editor) return ''
  const html = editor.getHtml() || ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  // 优先取第一个 h1/h2/h3
  const heading = doc.querySelector('h1, h2, h3')
  if (heading && heading.textContent.trim()) {
    return heading.textContent.trim().slice(0, 64)
  }
  // 否则取第一个非空 <p>
  const firstP = doc.querySelector('p')
  if (firstP && firstP.textContent.trim()) {
    return firstP.textContent.trim().slice(0, 64)
  }
  return ''
}

// ─── 生命周期 ───
onBeforeUnmount(() => {
  const editor = editorRef.value
  if (editor) editor.destroy()
})

/**
 * 纯文本 / markdown → HTML
 * 当内容不含 HTML 标签时，将 markdown 格式转为 wangEditor 可识别的 HTML
 * - ## xxx → <h2>xxx</h2>
 * - ### xxx → <h3>xxx</h3>
 * - 段落（双换行分隔）→ <p>xxx</p>
 */
function plainTextToHtml(text) {
  if (!text) return ''
  // 如果已经包含 HTML 块级标签，认为已经是 HTML，原样返回
  if (/<(p|h[1-6]|section|div|ul|ol|li|blockquote|table)[\s>]/i.test(text)) return text
  // 行内 markdown
  const inline = (s) => s
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
  return text
    .split(/\n\n+/)
    .map((para) => {
      const t = para.trim()
      if (!t) return ''
      if (t.startsWith('### ')) return `<h3>${inline(t.slice(4).trim())}</h3>`
      if (t.startsWith('## ')) return `<h2>${inline(t.slice(3).trim())}</h2>`
      if (t.startsWith('# ')) return `<h2>${inline(t.slice(2).trim())}</h2>`
      return `<p>${inline(t.replace(/\n/g, '<br>'))}</p>`
    })
    .join('\n')
}

// ─── 暴露给父组件 ───
defineExpose({
  getEditor: () => editorRef.value,
  getHtml: () => editorRef.value?.getHtml() || '',
  getText: () => editorRef.value?.getText() || '',
  extractTitle: () => extractTitle(),
  setHtml: (html) => {
    if (editorRef.value) {
      const finalHtml = plainTextToHtml(html)
      editorRef.value.setHtml(finalHtml)
      valueHtml.value = finalHtml
    }
  },
  /**
   * 生成公众号兼容的 HTML
   * - 应用公众号排版规范（16px 正文、两端对齐、标题样式等）
   * - 清理不支持的标签
   * - 内联关键样式
   */
  getWechatHtml: () => {
    const editor = editorRef.value
    if (!editor) return ''
    const html = editor.getHtml() || ''
    // 从 _spacingMap 读取每段的间距值
    return convertToWechatHtml(html, spacingBefore.value, spacingAfter.value, _spacingMap)
  },
})

/**
 * 将编辑器 HTML 转换为公众号兼容格式
 */
function convertToWechatHtml(html, spBefore, spAfter, spacingMap) {
  if (!html) return ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const body = doc.body

  // 移除不支持的标签
  body.querySelectorAll('video, audio, iframe, script, style, form, input, button, select, textarea').forEach(el => el.remove())

  // ── 第 1 步：语义标签 → <section>，同时直接写入公众号样式 ──
  // 标题 → section
  body.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {
    const tag = h.tagName.toLowerCase()
    const section = doc.createElement('section')
    section.innerHTML = h.innerHTML

    if (tag === 'h1' || tag === 'h2') {
      // 二级标题：黑底白字，inline-block 让 margin 生效
      section.style.display = 'inline-block'
      section.style.fontSize = '20px'
      section.style.fontWeight = 'bold'
      section.style.color = '#ffffff'
      section.style.backgroundColor = '#000000'
      section.style.lineHeight = '1.75'
      section.style.padding = '2px 6px'
      section.style.marginBottom = '16px'
    } else {
      // h3-h6 小标题：18px 加粗
      section.style.fontSize = '18px'
      section.style.fontWeight = 'bold'
      section.style.color = '#000000'
      section.style.textAlign = 'center'
      section.style.lineHeight = '1.75'
      section.style.marginBottom = '16px'
    }

    h.replaceWith(section)
  })

  // blockquote → section
  body.querySelectorAll('blockquote').forEach(bq => {
    const section = doc.createElement('section')
    section.innerHTML = bq.innerHTML
    section.style.borderLeft = '4px solid #CC785C'
    section.style.paddingLeft = '16px'
    section.style.color = '#666666'
    section.style.fontStyle = 'italic'
    section.style.marginBottom = '16px'
    section.style.lineHeight = '1.75'
    bq.replaceWith(section)
  })

  // ── 第 2 步：遍历剩余块级元素，补充正文段落样式 ──
  const blocks = body.querySelectorAll('p, section, li, td, th')
  let blockIdx = 0
  blocks.forEach(block => {
    const tag = block.tagName.toLowerCase()

    // 清理标点
    cleanPunctuation(block)

    if (tag === 'li') {
      block.style.lineHeight = '1.75'
      block.style.fontSize = '16px'
      block.style.color = '#333333'
    } else if (tag === 'td' || tag === 'th') {
      block.style.border = '1px solid #ddd'
      block.style.padding = '8px 12px'
      block.style.fontSize = '14px'
      if (tag === 'th') {
        block.style.backgroundColor = '#f5f5f5'
        block.style.fontWeight = '600'
      }
    } else if (tag === 'section') {
      // section 由标题/引用转换而来，检查是否有自定义间距
      const sp = spacingMap?.get?.(blockIdx) || spacingMap?.[blockIdx]
      if (sp?.before) block.style.marginTop = sp.before
      if (sp?.after) block.style.marginBottom = sp.after
    } else {
      // 正文段落：从 spacingMap 读取每段独立的间距
      const sp = spacingMap?.get?.(blockIdx) || spacingMap?.[blockIdx]
      block.style.fontSize = '16px'
      block.style.lineHeight = '1.75'
      block.style.textAlign = 'justify'
      block.style.marginTop = sp?.before || spBefore || '0'
      block.style.marginBottom = sp?.after || spAfter || '24px'
      block.style.color = '#333333'
    }
    blockIdx++
  })

  // 表格加 border-collapse
  body.querySelectorAll('table').forEach(table => {
    table.style.borderCollapse = 'collapse'
    table.style.width = '100%'
    table.style.margin = '16px 0'
  })

  // 分割线
  body.querySelectorAll('hr').forEach(hr => {
    hr.style.border = 'none'
    hr.style.borderTop = '1px solid #ddd'
    hr.style.margin = '24px 0'
  })

  // ── 第 3 步：清理属性，只保留 style 和 src/href ──
  body.querySelectorAll('*').forEach(el => {
    const tag = el.tagName.toLowerCase()
    const keepAttrs = ['style']
    if (tag === 'img') keepAttrs.push('src', 'alt')
    if (tag === 'a') keepAttrs.push('href')
    if (tag === 'td' || tag === 'th') keepAttrs.push('colspan', 'rowspan')

    const toRemove = []
    for (const attr of el.attributes) {
      if (!keepAttrs.includes(attr.name)) toRemove.push(attr.name)
    }
    toRemove.forEach(attr => el.removeAttribute(attr))
  })

  // 调试：把转换结果存到 window 上，方便从控制台查看
  const result = body.innerHTML
  if (typeof window !== 'undefined') {
    window.__lastWechatHtml = result
    console.log('[convertToWechatHtml] spBefore:', spBefore, 'spAfter:', spAfter)
    console.log('[convertToWechatHtml] result:', result.substring(0, 500))
  }
  return result
}

function cleanPunctuation(block) {
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT)
  while (walker.nextNode()) {
    const node = walker.currentNode
    let t = node.textContent
    t = t.replace(/[\u201c\u201d]/g, '')
    t = t.replace(/[\u2018\u2019]/g, '')
    t = t.replace(/[《》]/g, '')
    t = t.replace(/——/g, '，')
    const matches = t.match(/……/g)
    if (matches && matches.length > 1) {
      let count = 0
      t = t.replace(/……/g, (m) => { count++; return count === 1 ? m : '。' })
    }
    node.textContent = t
  }
}
</script>

<style scoped>
.wechat-editor-wrap {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  overflow: hidden;
  background: #fff;
  position: relative;
}

/* 工具栏 */
.wechat-toolbar {
  border-bottom: 1px solid var(--line) !important;
  background: var(--bone) !important;
}
.wechat-toolbar :deep(.w-e-bar) {
  background: var(--bone) !important;
  flex-wrap: wrap;
}
.wechat-toolbar :deep(.w-e-bar-item button) {
  color: var(--ink-2) !important;
}
.wechat-toolbar :deep(.w-e-bar-item button:hover) {
  background: rgba(0,0,0,0.05) !important;
}
.wechat-toolbar :deep(.w-e-bar-item .active) {
  background: var(--clay-tint) !important;
  color: var(--clay-deep) !important;
}
.wechat-toolbar :deep(.w-e-bar-item .w-e-bar-item-group) {
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
}

/* 编辑区 */
.wechat-editor-content {
  min-height: 500px;
  max-height: 70vh;
  overflow-y: auto;
}
.wechat-editor-content :deep(.w-e-text-container) {
  background: #fff !important;
}
.wechat-editor-content :deep(.w-e-text-placeholder) {
  color: var(--ink-4) !important;
  font-style: normal !important;
  padding: 12px 24px !important;
  top: 0 !important;
}
.wechat-editor-content :deep(.w-e-text-container [data-slate-editor]) {
  padding: 12px 24px 20px !important;
  font-size: 16px !important;
  font-family: "Microsoft YaHei", "微软雅黑", sans-serif !important;
  line-height: 1.75 !important;
  color: #333 !important;
  min-height: 480px !important;
}
/* 去掉第一个 p 的上 margin，让光标紧贴顶部（不用 !important 以允许 inline style 覆盖） */
.wechat-editor-content :deep(.w-e-text-container [data-slate-editor] > p:first-child) {
  margin-top: 0;
}
.wechat-editor-content :deep(.w-e-text-container p) {
  margin-top: 0;
  margin-bottom: 24px;
  font-size: 16px !important;
  line-height: 24px;
}
/* 段前/段后距由 inline style 控制，不走 CSS 规则 */
/* 编辑器内 H2 样式：黑底白字，用 inline-block 让 margin 生效 */
.wechat-editor-content :deep(.w-e-text-container h2),
.wechat-editor-content :deep(.w-e-text-container [data-slate-editor] h2) {
  display: inline-block;
  font-size: 20px;
  font-weight: bold;
  font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
  color: #ffffff;
  background-color: #000000;
  line-height: 1.75;
  padding: 2px 6px;
  margin-bottom: 16px;
}
/* 表格样式 —— 模拟公众号渲染 */
.wechat-editor-content :deep(.w-e-text-container table) {
  border-collapse: collapse !important;
  width: 100% !important;
  margin: 16px 0 !important;
}
.wechat-editor-content :deep(.w-e-text-container td),
.wechat-editor-content :deep(.w-e-text-container th) {
  border: 1px solid #ddd !important;
  padding: 8px 12px !important;
  font-size: 14px !important;
}
.wechat-editor-content :deep(.w-e-text-container th) {
  background: #f5f5f5 !important;
  font-weight: 600 !important;
}
/* 分割线 */
.wechat-editor-content :deep(.w-e-text-container hr) {
  border: none !important;
  border-top: 1px solid #ddd !important;
  margin: 24px 0 !important;
}
/* 引用块 */
.wechat-editor-content :deep(.w-e-text-container blockquote) {
  border-left: 4px solid var(--clay) !important;
  padding-left: 16px !important;
  color: #666 !important;
  margin: 16px 0 !important;
  font-style: italic !important;
}

/* 底部栏 */
.wechat-editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid var(--line);
  background: var(--bone);
  flex-wrap: wrap;
  gap: 8px;
}
.footer-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.footer-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.footer-divider {
  width: 1px;
  height: 20px;
  background: var(--line);
  margin: 0 4px;
}
.qf-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--ink-2);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.qf-btn:hover {
  border-color: var(--clay-soft);
  color: var(--clay-deep);
  background: var(--clay-tint);
}
.qf-btn-red {
  color: #c0392b;
  border-color: #f5c6cb;
}
.qf-btn-red:hover {
  background: #f8d7da;
  border-color: #c0392b;
  color: #c0392b;
}
.qf-btn-primary {
  background: var(--clay);
  color: #fff;
  border-color: var(--clay);
}
.qf-btn-primary:hover {
  background: var(--clay-deep);
  border-color: var(--clay-deep);
  color: #fff;
}
</style>
