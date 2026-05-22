<template>
  <div class="creation-editor">
    <!-- 页面标题 -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-h2 font-serif text-ink">
          {{ isEditing ? '编辑创作' : '新建创作' }}
        </h1>
        <p class="text-ink-3 mt-1">
          {{ isEditing ? '修改您的创作内容' : '基于选题创作公众号文章' }}
        </p>
      </div>
      <div class="flex space-x-3">
        <el-button @click="saveDraft" :loading="saving">
          <el-icon><Document /></el-icon>
          保存草稿
        </el-button>
        <el-button type="primary" @click="publishCreation" :loading="publishing">
          <el-icon><Upload /></el-icon>
          发布创作
        </el-button>
      </div>
    </div>
    
    <!-- 创作表单 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 主编辑区 -->
      <div class="lg:col-span-2">
        <div class="card p-6">
          <!-- 标题输入 -->
          <div class="mb-6">
            <label class="label">创作标题</label>
            <el-input
              v-model="form.title"
              placeholder="请输入创作标题"
              size="large"
              class="text-lg"
            />
          </div>
          
          <!-- 富文本编辑器 -->
          <div class="mb-6">
            <label class="label">创作内容</label>
            <RichTextEditor
              v-model="form.content"
              placeholder="开始写作..."
              @save="saveContent"
            />
          </div>
          
          <!-- 摘要 -->
          <div class="mb-6">
            <label class="label">内容摘要</label>
            <el-input
              v-model="form.summary"
              type="textarea"
              :rows="3"
              placeholder="请输入内容摘要（可选）"
            />
          </div>
        </div>
      </div>
      
      <!-- 侧边栏 -->
      <div class="space-y-6">
        <!-- 选题信息 -->
        <div v-if="topicInfo" class="card p-6">
          <h3 class="text-h4 font-sans text-ink mb-4">选题信息</h3>
          <div class="space-y-3">
            <div>
              <span class="text-sm text-ink-3">选题标题：</span>
              <p class="text-sm font-medium text-ink mt-1">{{ topicInfo.title }}</p>
            </div>
            <div v-if="topicInfo.summary">
              <span class="text-sm text-ink-3">选题摘要：</span>
              <p class="text-sm text-ink-2 mt-1">{{ topicInfo.summary }}</p>
            </div>
            <div>
              <el-button size="small" @click="viewTopic">
                查看选题详情
              </el-button>
            </div>
          </div>
        </div>
        
        <!-- 风格设置 -->
        <div class="card p-6">
          <h3 class="text-h4 font-sans text-ink mb-4">风格设置</h3>
          <div class="space-y-4">
            <div>
              <label class="label">写作风格</label>
              <el-select v-model="form.style_profile_id" placeholder="选择写作风格" class="w-full">
                <el-option
                  v-for="style in styleProfiles"
                  :key="style.id"
                  :label="style.name"
                  :value="style.id"
                />
              </el-select>
            </div>
            
            <div>
              <label class="label">内容类型</label>
              <el-select v-model="form.content_type" class="w-full">
                <el-option label="公众号文章" value="article" />
                <el-option label="内容摘要" value="summary" />
                <el-option label="内容大纲" value="outline" />
                <el-option label="社交媒体帖子" value="social_post" />
              </el-select>
            </div>
            
            <el-button type="primary" class="w-full" @click="generateWithAI">
              <el-icon><MagicStick /></el-icon>
              AI生成内容
            </el-button>
          </div>
        </div>
        
        <!-- 标签设置 -->
        <div class="card p-6">
          <h3 class="text-lg font-semibold text-ink mb-4">标签设置</h3>
          <div class="space-y-4">
            <div>
              <label class="label">文章标签</label>
              <el-select
                v-model="form.tags"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="请选择或创建标签"
                class="w-full"
              >
                <el-option
                  v-for="tag in commonTags"
                  :key="tag"
                  :label="tag"
                  :value="tag"
                />
              </el-select>
            </div>
            
            <div>
              <label class="label">特色图片</label>
              <el-upload
                class="w-full"
                drag
                action="/api/v1/upload"
                :on-success="handleImageSuccess"
                :before-upload="beforeImageUpload"
              >
                <el-icon class="el-icon--upload"><Upload /></el-icon>
                <div class="el-upload__text">
                  将文件拖到此处，或<em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    只能上传jpg/png文件，且不超过500kb
                  </div>
                </template>
              </el-upload>
            </div>
          </div>
        </div>
        
        <!-- 创作统计 -->
        <div class="card p-6">
          <h3 class="text-lg font-semibold text-ink mb-4">创作统计</h3>
          <div class="space-y-3">
            <div class="flex justify-between">
              <span class="text-sm text-ink-3">字数：</span>
              <span class="text-sm font-medium text-ink">{{ wordCount }} 字</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-ink-3">预计阅读时间：</span>
              <span class="text-sm font-medium text-ink">{{ readingTime }} 分钟</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-ink-3">状态：</span>
              <span :class="statusClass">{{ statusText }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-ink-3">最后保存：</span>
              <span class="text-sm text-ink">{{ lastSaved || '未保存' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCreationStore } from '@/stores/creation'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Upload, MagicStick } from '@element-plus/icons-vue'
import RichTextEditor from '@/components/ui/RichTextEditor.vue'

const route = useRoute()
const router = useRouter()
const creationStore = useCreationStore()
const userStore = useUserStore()

// 状态
const saving = ref(false)
const publishing = ref(false)
const topicInfo = ref(null)
const styleProfiles = ref([])
const lastSaved = ref(null)

// 表单数据
const form = reactive({
  title: '',
  content: '',
  summary: '',
  style_profile_id: null,
  content_type: 'article',
  tags: [],
  featured_image: null,
  topic_id: null
})

// 常用标签
const commonTags = ref([
  'AI', '人工智能', '机器学习', '深度学习', '自然语言处理',
  '计算机视觉', '科技', '创新', '技术', '应用'
])

// 计算属性
const isEditing = computed(() => !!route.params.id)

const wordCount = computed(() => {
  return form.content ? form.content.replace(/<[^>]*>/g, '').length : 0
})

const readingTime = computed(() => {
  return Math.max(1, Math.ceil(wordCount.value / 500))
})

const statusText = computed(() => {
  if (isEditing.value) {
    return '编辑中'
  }
  return '新建草稿'
})

const statusClass = computed(() => {
  return 'text-sm font-medium text-clay'
})

// 生命周期
onMounted(async () => {
  // 加载风格档案
  await loadStyleProfiles()
  
  // 如果是编辑模式，加载创作数据
  if (isEditing.value) {
    await loadCreation()
  } else {
    // 从URL参数获取选题信息
    if (route.query.topic_id) {
      form.topic_id = parseInt(route.query.topic_id)
      topicInfo.value = {
        id: form.topic_id,
        title: route.query.topic_title || '',
        summary: route.query.topic_summary || ''
      }
    }
  }
})

// 加载风格档案
const loadStyleProfiles = async () => {
  try {
    // 这里应该调用API获取风格档案
    // 暂时使用模拟数据
    styleProfiles.value = [
      { id: 1, name: '默认风格' },
      { id: 2, name: '专业风格' },
      { id: 3, name: '轻松风格' }
    ]
  } catch (error) {
    console.error('Load style profiles error:', error)
  }
}

// 加载创作数据
const loadCreation = async () => {
  try {
    const creationId = route.params.id
    await creationStore.fetchCreation(creationId)
    
    const creation = creationStore.currentCreation
    if (creation) {
      form.title = creation.title
      form.content = creation.content
      form.summary = creation.summary
      form.style_profile_id = creation.style_profile_id
      form.content_type = creation.content_type || 'article'
      form.tags = creation.tags || []
      form.featured_image = creation.featured_image
      form.topic_id = creation.topic_id
      
      if (creation.topic_id) {
        topicInfo.value = {
          id: creation.topic_id,
          title: creation.topic_title || '选题标题',
          summary: creation.topic_summary || ''
        }
      }
    }
  } catch (error) {
    ElMessage.error('加载创作数据失败')
    console.error('Load creation error:', error)
  }
}

// 保存草稿
const saveDraft = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入创作标题')
    return
  }
  
  saving.value = true
  
  try {
    const creationData = {
      title: form.title,
      content: form.content,
      summary: form.summary,
      style_profile_id: form.style_profile_id,
      content_type: form.content_type,
      tags: form.tags,
      featured_image: form.featured_image,
      topic_id: form.topic_id,
      status: 'draft'
    }
    
    if (isEditing.value) {
      await creationStore.updateCreation(route.params.id, creationData)
      ElMessage.success('草稿更新成功')
    } else {
      await creationStore.createCreation(creationData)
      ElMessage.success('草稿保存成功')
    }
    
    lastSaved.value = new Date().toLocaleTimeString('zh-CN')
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('Save draft error:', error)
  } finally {
    saving.value = false
  }
}

// 发布创作
const publishCreation = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入创作标题')
    return
  }
  
  if (!form.content.trim()) {
    ElMessage.warning('请输入创作内容')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      '确定要发布这篇创作吗？发布后将无法修改。',
      '确认发布',
      {
        confirmButtonText: '确定发布',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    publishing.value = true
    
    const creationData = {
      title: form.title,
      content: form.content,
      summary: form.summary,
      style_profile_id: form.style_profile_id,
      content_type: form.content_type,
      tags: form.tags,
      featured_image: form.featured_image,
      topic_id: form.topic_id,
      status: 'published'
    }
    
    if (isEditing.value) {
      await creationStore.updateCreation(route.params.id, creationData)
      await creationStore.publishCreation(route.params.id)
    } else {
      const creation = await creationStore.createCreation(creationData)
      await creationStore.publishCreation(creation.id)
    }
    
    ElMessage.success('创作发布成功')
    router.push('/creation')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('发布失败')
      console.error('Publish creation error:', error)
    }
  } finally {
    publishing.value = false
  }
}

// 保存内容
const saveContent = (content) => {
  form.content = content
}

// AI生成内容
const generateWithAI = async () => {
  if (!topicInfo.value && !form.title) {
    ElMessage.warning('请先选择选题或输入标题')
    return
  }
  
  try {
    // 这里应该调用AI生成API
    // 暂时使用模拟生成
    const generatedContent = `
      <h2>AI技术发展现状与趋势分析</h2>
      <p>随着人工智能技术的快速发展，AI已经渗透到我们生活的方方面面。从智能语音助手到自动驾驶汽车，从医疗诊断到金融风控，AI正在改变着各行各业。</p>
      <h3>1. 技术突破</h3>
      <p>近年来，深度学习技术取得了重大突破，特别是在自然语言处理和计算机视觉领域。大型语言模型的出现，使得机器能够更好地理解和生成人类语言。</p>
      <h3>2. 应用场景</h3>
      <p>AI技术的应用场景越来越广泛：</p>
      <ul>
        <li>医疗健康：辅助诊断、药物研发</li>
        <li>金融科技：风险评估、智能投顾</li>
        <li>教育培训：个性化学习、智能辅导</li>
        <li>智能制造：质量控制、预测性维护</li>
      </ul>
      <h3>3. 未来展望</h3>
      <p>展望未来，AI技术将继续快速发展。多模态AI、边缘计算、AI伦理等将成为重要的发展方向。同时，AI与人类协作的模式也将更加成熟。</p>
      <p>对于内容创作者来说，了解AI技术的发展趋势，将有助于创作出更有价值的内容。</p>
    `
    
    form.content = generatedContent
    ElMessage.success('AI内容生成成功')
  } catch (error) {
    ElMessage.error('AI内容生成失败')
    console.error('Generate with AI error:', error)
  }
}

// 图片上传成功
const handleImageSuccess = (response, file) => {
  form.featured_image = URL.createObjectURL(file.raw)
  ElMessage.success('图片上传成功')
}

// 图片上传前验证
const beforeImageUpload = (file) => {
  const isJPGorPNG = file.type === 'image/jpeg' || file.type === 'image/png'
  const isLt500K = file.size / 1024 < 500

  if (!isJPGorPNG) {
    ElMessage.error('只能上传 JPG/PNG 文件!')
  }
  if (!isLt500K) {
    ElMessage.error('图片大小不能超过 500KB!')
  }
  
  return isJPGorPNG && isLt500K
}

// 查看选题
const viewTopic = () => {
  if (topicInfo.value) {
    router.push(`/topics/${topicInfo.value.id}`)
  }
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>