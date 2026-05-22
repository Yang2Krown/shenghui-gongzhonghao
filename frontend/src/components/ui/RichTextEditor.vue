<template>
  <div class="rich-text-editor">
    <!-- 工具栏 -->
    <div class="editor-toolbar border border-line rounded-t-lg bg-bone p-2 flex flex-wrap gap-1">
      <!-- 文本格式 -->
      <div class="flex items-center space-x-1 border-r border-line pr-2 mr-2">
        <el-button
          :type="isActive('bold') ? 'primary' : 'default'"
          size="small"
          @click="toggleBold"
          title="加粗"
        >
          <strong>B</strong>
        </el-button>
        <el-button
          :type="isActive('italic') ? 'primary' : 'default'"
          size="small"
          @click="toggleItalic"
          title="斜体"
        >
          <em>I</em>
        </el-button>
        <el-button
          :type="isActive('strike') ? 'primary' : 'default'"
          size="small"
          @click="toggleStrike"
          title="删除线"
        >
          <s>S</s>
        </el-button>
      </div>
      
      <!-- 标题 -->
      <div class="flex items-center space-x-1 border-r border-line pr-2 mr-2">
        <el-button
          :type="isActive('heading', { level: 1 }) ? 'primary' : 'default'"
          size="small"
          @click="toggleHeading(1)"
          title="标题1"
        >
          H1
        </el-button>
        <el-button
          :type="isActive('heading', { level: 2 }) ? 'primary' : 'default'"
          size="small"
          @click="toggleHeading(2)"
          title="标题2"
        >
          H2
        </el-button>
        <el-button
          :type="isActive('heading', { level: 3 }) ? 'primary' : 'default'"
          size="small"
          @click="toggleHeading(3)"
          title="标题3"
        >
          H3
        </el-button>
      </div>
      
      <!-- 列表 -->
      <div class="flex items-center space-x-1 border-r border-line pr-2 mr-2">
        <el-button
          :type="isActive('bulletList') ? 'primary' : 'default'"
          size="small"
          @click="toggleBulletList"
          title="无序列表"
        >
          <el-icon><List /></el-icon>
        </el-button>
        <el-button
          :type="isActive('orderedList') ? 'primary' : 'default'"
          size="small"
          @click="toggleOrderedList"
          title="有序列表"
        >
          <el-icon><Sort /></el-icon>
        </el-button>
      </div>
      
      <!-- 引用和代码 -->
      <div class="flex items-center space-x-1 border-r border-line pr-2 mr-2">
        <el-button
          :type="isActive('blockquote') ? 'primary' : 'default'"
          size="small"
          @click="toggleBlockquote"
          title="引用"
        >
          <el-icon><ChatDotRound /></el-icon>
        </el-button>
        <el-button
          :type="isActive('codeBlock') ? 'primary' : 'default'"
          size="small"
          @click="toggleCodeBlock"
          title="代码块"
        >
          <el-icon><Monitor /></el-icon>
        </el-button>
      </div>
      
      <!-- 链接和图片 -->
      <div class="flex items-center space-x-1 border-r border-line pr-2 mr-2">
        <el-button
          :type="isActive('link') ? 'primary' : 'default'"
          size="small"
          @click="setLink"
          title="链接"
        >
          <el-icon><Link /></el-icon>
        </el-button>
        <el-button
          size="small"
          @click="addImage"
          title="图片"
        >
          <el-icon><Picture /></el-icon>
        </el-button>
      </div>
      
      <!-- 撤销和重做 -->
      <div class="flex items-center space-x-1">
        <el-button
          size="small"
          @click="undo"
          :disabled="!editor?.can().undo()"
          title="撤销"
        >
          <el-icon><RefreshLeft /></el-icon>
        </el-button>
        <el-button
          size="small"
          @click="redo"
          :disabled="!editor?.can().redo()"
          title="重做"
        >
          <el-icon><RefreshRight /></el-icon>
        </el-button>
      </div>
      
      <!-- AI辅助按钮 -->
      <div class="flex items-center space-x-1 ml-auto">
        <el-button
          type="primary"
          size="small"
          @click="showAIAssistant = true"
          class="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600"
        >
          <el-icon><MagicStick /></el-icon>
          AI辅助
        </el-button>
      </div>
    </div>
    
    <!-- 编辑器内容 -->
    <editor-content :editor="editor" class="editor-content" />
    
    <!-- 字符统计 -->
    <div class="editor-footer border border-t-0 border-line rounded-b-lg bg-bone px-3 py-2 flex justify-between items-center">
      <div class="text-sm text-ink-3">
        <span v-if="editor">
          字数：{{ editor.storage.characterCount.characters() }} 字
          <span class="mx-2">|</span>
          段落：{{ editor.storage.characterCount.words() }} 段
        </span>
      </div>
      <div class="flex items-center space-x-2">
        <el-tag size="small" type="success">已保存</el-tag>
        <el-button size="small" @click="saveContent">
          保存
        </el-button>
      </div>
    </div>
    
    <!-- AI助手对话框 -->
    <el-dialog
      v-model="showAIAssistant"
      title="AI写作助手"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="space-y-4">
        <div class="flex flex-wrap gap-2">
          <el-button
            v-for="prompt in aiPrompts"
            :key="prompt.id"
            @click="applyAIPrompt(prompt)"
            size="small"
          >
            {{ prompt.title }}
          </el-button>
        </div>
        
        <el-input
          v-model="customPrompt"
          type="textarea"
          :rows="3"
          placeholder="输入自定义指令..."
        />
        
        <div class="flex justify-end space-x-2">
          <el-button @click="showAIAssistant = false">取消</el-button>
          <el-button type="primary" @click="generateAIContent" :loading="aiLoading">
            生成内容
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import CharacterCount from '@tiptap/extension-character-count'
import { List, Sort, ChatDotRound, Monitor, Link, Picture, RefreshLeft, RefreshRight, MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '开始写作...'
  },
  editable: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'save'])

// 编辑器实例
const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit,
    Placeholder.configure({
      placeholder: props.placeholder,
    }),
    CharacterCount.configure({
      limit: 10000,
    }),
  ],
  onUpdate: ({ editor }) => {
    emit('update:modelValue', editor.getHTML())
  },
})

// AI助手相关
const showAIAssistant = ref(false)
const customPrompt = ref('')
const aiLoading = ref(false)

// AI提示词模板
const aiPrompts = ref([
  { id: 1, title: '扩写段落', prompt: '请扩写以下内容，增加更多细节和例子：' },
  { id: 2, title: '精简内容', prompt: '请精简以下内容，保持核心观点：' },
  { id: 3, title: '改变语气', prompt: '请将以下内容改为更专业的语气：' },
  { id: 4, title: '添加总结', prompt: '请为以下内容添加一个总结：' },
  { id: 5, title: '生成标题', prompt: '请为以下内容生成5个吸引人的标题：' },
])

// 工具栏方法
const isActive = (name, attrs = {}) => {
  return editor.value?.isActive(name, attrs)
}

const toggleBold = () => {
  editor.value?.chain().focus().toggleBold().run()
}

const toggleItalic = () => {
  editor.value?.chain().focus().toggleItalic().run()
}

const toggleStrike = () => {
  editor.value?.chain().focus().toggleStrike().run()
}

const toggleHeading = (level) => {
  editor.value?.chain().focus().toggleHeading({ level }).run()
}

const toggleBulletList = () => {
  editor.value?.chain().focus().toggleBulletList().run()
}

const toggleOrderedList = () => {
  editor.value?.chain().focus().toggleOrderedList().run()
}

const toggleBlockquote = () => {
  editor.value?.chain().focus().toggleBlockquote().run()
}

const toggleCodeBlock = () => {
  editor.value?.chain().focus().toggleCodeBlock().run()
}

const setLink = () => {
  const url = window.prompt('请输入链接URL：')
  if (url) {
    editor.value?.chain().focus().setLink({ href: url }).run()
  }
}

const addImage = () => {
  const url = window.prompt('请输入图片URL：')
  if (url) {
    editor.value?.chain().focus().setImage({ src: url }).run()
  }
}

const undo = () => {
  editor.value?.chain().focus().undo().run()
}

const redo = () => {
  editor.value?.chain().focus().redo().run()
}

// AI辅助方法
const applyAIPrompt = (prompt) => {
  customPrompt.value = prompt.prompt
}

const generateAIContent = async () => {
  if (!customPrompt.value.trim()) {
    ElMessage.warning('请输入指令')
    return
  }
  
  aiLoading.value = true
  
  try {
    // 模拟AI生成（实际应调用API）
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    const selectedText = editor.value?.state.doc.textBetween(
      editor.value.state.selection.from,
      editor.value.state.selection.to,
      ' '
    ) || ''
    
    const aiResponse = `【AI生成内容】\n\n基于您的指令"${customPrompt.value}"，以下是生成的内容：\n\n${selectedText ? `原文：${selectedText}\n\n` : ''}这是AI生成的内容示例，实际应用中会调用真实的AI服务。`
    
    // 插入AI生成的内容
    editor.value?.commands.insertContent(aiResponse)
    
    ElMessage.success('AI内容生成成功')
    showAIAssistant.value = false
    customPrompt.value = ''
  } catch (error) {
    ElMessage.error('AI内容生成失败')
    console.error('AI generation error:', error)
  } finally {
    aiLoading.value = false
  }
}

// 保存内容
const saveContent = () => {
  emit('save', editor.value?.getHTML())
  ElMessage.success('内容已保存')
}

// 监听外部内容变化
watch(() => props.modelValue, (newContent) => {
  if (editor.value && editor.value.getHTML() !== newContent) {
    editor.value.commands.setContent(newContent, false)
  }
})

// 监听可编辑状态变化
watch(() => props.editable, (newEditable) => {
  if (editor.value) {
    editor.value.setEditable(newEditable)
  }
})

// 组件销毁时销毁编辑器
onBeforeUnmount(() => {
  editor.value?.destroy()
})
</script>

<style scoped>
.rich-text-editor {
  @apply border border-line rounded-lg overflow-hidden;
}

.editor-toolbar {
  @apply border-b border-line;
}

.editor-content {
  @apply min-h-[300px] max-h-[600px] overflow-y-auto;
}

.editor-content :deep(.tiptap) {
  @apply p-4 focus:outline-none;
}

.editor-content :deep(.tiptap p) {
  @apply mb-3;
}

.editor-content :deep(.tiptap h1) {
  @apply text-2xl font-bold mb-4;
}

.editor-content :deep(.tiptap h2) {
  @apply text-xl font-bold mb-3;
}

.editor-content :deep(.tiptap h3) {
  @apply text-lg font-bold mb-2;
}

.editor-content :deep(.tiptap ul) {
  @apply list-disc pl-6 mb-3;
}

.editor-content :deep(.tiptap ol) {
  @apply list-decimal pl-6 mb-3;
}

.editor-content :deep(.tiptap li) {
  @apply mb-1;
}

.editor-content :deep(.tiptap blockquote) {
  @apply border-l-4 border-line pl-4 italic text-ink-3 mb-3;
}

.editor-content :deep(.tiptap code) {
  @apply bg-bone px-1 py-0.5 rounded text-sm font-mono;
}

.editor-content :deep(.tiptap pre) {
  @apply bg-ink text-ivory p-4 rounded-lg mb-3 overflow-x-auto;
}

.editor-content :deep(.tiptap pre code) {
  @apply bg-transparent p-0;
}

.editor-content :deep(.tiptap a) {
  @apply text-clay-deep underline;
}

.editor-content :deep(.tiptap img) {
  @apply max-w-full h-auto rounded-lg;
}

.editor-content :deep(.tiptap table) {
  @apply w-full border-collapse mb-3;
}

.editor-content :deep(.tiptap th),
.editor-content :deep(.tiptap td) {
  @apply border border-line px-3 py-2;
}

.editor-content :deep(.tiptap th) {
  @apply bg-bone font-semibold;
}

.editor-content :deep(.tiptap p.is-editor-empty:first-child::before) {
  @apply text-ink-4 float-left pointer-events-none h-0;
  content: attr(data-placeholder);
}

.editor-footer {
  @apply border-t-0;
}
</style>