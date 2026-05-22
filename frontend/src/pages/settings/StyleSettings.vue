<template>
  <div class="style-settings">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h1 class="text-h2 font-serif text-ink">风格设置</h1>
      <p class="text-ink-3 mt-1">管理您的写作风格和AI辅助设置</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 左侧：风格档案 -->
      <div>
        <div class="card p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-medium text-ink">风格档案</h3>
            <el-button type="primary" size="small" @click="createNewStyle">
              <el-icon><Plus /></el-icon>
              新建档案
            </el-button>
          </div>
          
          <div v-if="loading" class="flex justify-center py-8">
            <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          </div>
          
          <div v-else-if="styleProfiles.length === 0" class="text-center py-8">
            <el-icon :size="48" class="text-ink-4"><Document /></el-icon>
            <p class="text-ink-3 mt-2">暂无风格档案</p>
            <el-button type="primary" class="mt-4" @click="createNewStyle">
              创建第一个档案
            </el-button>
          </div>
          
          <div v-else class="space-y-4">
            <div
              v-for="profile in styleProfiles"
              :key="profile.id"
              class="border border-line rounded-lg p-4 cursor-pointer hover:border-clay-light transition-colors"
              :class="{ 'border-clay bg-clay-tint': selectedProfile?.id === profile.id }"
              @click="selectProfile(profile)"
            >
              <div class="flex items-center justify-between">
                <div>
                  <h4 class="font-medium text-ink">{{ profile.name }}</h4>
                  <p class="text-sm text-ink-3 mt-1">{{ profile.description || '暂无描述' }}</p>
                </div>
                <div class="flex space-x-2">
                  <el-button size="small" @click.stop="editProfile(profile)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button size="small" type="danger" plain @click.stop="deleteProfile(profile)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
              
              <!-- 风格标签 -->
              <div class="flex flex-wrap gap-1 mt-3">
                <span
                  v-for="tag in (profile.tags || []).slice(0, 5)"
                  :key="tag"
                  class="badge-info text-xs"
                >
                  {{ tag }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 分析文章 -->
        <div class="card p-6 mt-6">
          <h3 class="text-lg font-medium text-ink mb-4">分析文章</h3>
          <p class="text-ink-3 mb-4">
            通过分析您的文章，AI可以更好地学习您的写作风格
          </p>
          
          <div class="space-y-4">
            <div
              v-for="article in analyzedArticles"
              :key="article.id"
              class="flex items-center justify-between p-3 bg-bone rounded-lg"
            >
              <div class="flex-1 min-w-0">
                <div class="font-medium text-ink truncate">{{ article.title }}</div>
                <div class="text-sm text-ink-3">
                  {{ article.word_count }} 字 · {{ formatDate(article.analyzed_at) }}
                </div>
              </div>
              <el-button size="small" type="danger" plain @click="removeArticle(article)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          
          <el-upload
            class="mt-4"
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleArticleUpload"
            accept=".txt,.md,.doc,.docx"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 txt、md、doc、docx 格式，单个文件不超过 10MB
              </div>
            </template>
          </el-upload>
        </div>
      </div>

      <!-- 右侧：风格设置 -->
      <div>
        <div class="card p-6">
          <h3 class="text-lg font-medium text-ink mb-4">风格设置</h3>
          
          <el-form
            ref="styleFormRef"
            :model="styleForm"
            :rules="styleRules"
            label-position="top"
          >
            <el-form-item label="风格名称" prop="name">
              <el-input v-model="styleForm.name" placeholder="例如：专业技术风格" />
            </el-form-item>
            
            <el-form-item label="风格描述" prop="description">
              <el-input
                v-model="styleForm.description"
                type="textarea"
                :rows="3"
                placeholder="描述这种风格的特点..."
              />
            </el-form-item>
            
            <el-form-item label="写作风格" prop="tone">
              <el-select v-model="styleForm.tone" placeholder="选择写作风格" class="w-full">
                <el-option label="专业严谨" value="professional" />
                <el-option label="轻松活泼" value="casual" />
                <el-option label="幽默风趣" value="humorous" />
                <el-option label="简洁明了" value="concise" />
                <el-option label="详细深入" value="detailed" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="目标受众" prop="audience">
              <el-select v-model="styleForm.audience" placeholder="选择目标受众" class="w-full">
                <el-option label="技术人员" value="technical" />
                <el-option label="普通用户" value="general" />
                <el-option label="行业专家" value="expert" />
                <el-option label="初学者" value="beginner" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="文章长度" prop="length">
              <el-select v-model="styleForm.length" placeholder="选择文章长度" class="w-full">
                <el-option label="短篇 (500-1000字)" value="short" />
                <el-option label="中篇 (1000-2000字)" value="medium" />
                <el-option label="长篇 (2000-5000字)" value="long" />
                <el-option label="深度长文 (5000字以上)" value="deep" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="关键词">
              <el-select
                v-model="styleForm.keywords"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="输入关键词后回车"
                class="w-full"
              >
                <el-option
                  v-for="keyword in suggestedKeywords"
                  :key="keyword"
                  :label="keyword"
                  :value="keyword"
                />
              </el-select>
            </el-form-item>
            
            <el-form-item label="示例句子">
              <el-input
                v-model="styleForm.example_sentence"
                type="textarea"
                :rows="2"
                placeholder="输入一个能代表这种风格的例句..."
              />
            </el-form-item>
            
            <el-form-item>
              <div class="flex space-x-3">
                <el-button type="primary" @click="saveStyle" :loading="saving">
                  保存设置
                </el-button>
                <el-button @click="resetForm">
                  重置
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>

        <!-- AI辅助设置 -->
        <div class="card p-6 mt-6">
          <h3 class="text-lg font-medium text-ink mb-4">AI辅助设置</h3>
          
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <div class="font-medium text-ink">自动优化</div>
                <div class="text-sm text-ink-3">AI自动优化您的文章</div>
              </div>
              <el-switch v-model="aiSettings.autoOptimize" />
            </div>
            
            <div class="flex items-center justify-between">
              <div>
                <div class="font-medium text-ink">风格一致性检查</div>
                <div class="text-sm text-ink-3">检查文章是否符合选定风格</div>
              </div>
              <el-switch v-model="aiSettings.styleConsistency" />
            </div>
            
            <div class="flex items-center justify-between">
              <div>
                <div class="font-medium text-ink">智能建议</div>
                <div class="text-sm text-ink-3">提供写作建议和改进意见</div>
              </div>
              <el-switch v-model="aiSettings.smartSuggestions" />
            </div>
            
            <el-form-item label="AI模型">
              <el-select v-model="aiSettings.model" class="w-full">
                <el-option label="GPT-4" value="gpt-4" />
                <el-option label="GPT-3.5 Turbo" value="gpt-3.5-turbo" />
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="通义千问" value="qianwen" />
              </el-select>
            </el-form-item>
          </div>
          
          <div class="mt-6">
            <el-button type="primary" @click="saveAiSettings" :loading="savingAiSettings">
              保存AI设置
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Edit,
  Delete,
  Loading,
  Document,
  UploadFilled
} from '@element-plus/icons-vue'
import { getStyles, createStyle, updateStyle, deleteStyle } from '@/api/style'

const userStore = useUserStore()

// 表单引用
const styleFormRef = ref(null)

// 状态
const loading = ref(false)
const saving = ref(false)
const savingAiSettings = ref(false)

// 风格档案列表
const styleProfiles = ref([])
const selectedProfile = ref(null)

// 分析过的文章
const analyzedArticles = ref([
  {
    id: 1,
    title: '如何学习机器学习',
    word_count: 2500,
    analyzed_at: '2024-01-15'
  },
  {
    id: 2,
    title: 'AI在医疗领域的应用',
    word_count: 3200,
    analyzed_at: '2024-01-10'
  }
])

// 建议关键词
const suggestedKeywords = [
  'AI', '机器学习', '深度学习', '自然语言处理',
  '计算机视觉', '大数据', '云计算', '物联网',
  '区块链', '元宇宙', 'Web3', '数字化转型'
]

// 风格表单
const styleForm = reactive({
  name: '',
  description: '',
  tone: 'professional',
  audience: 'technical',
  length: 'medium',
  keywords: [],
  example_sentence: ''
})

// AI设置
const aiSettings = reactive({
  autoOptimize: true,
  styleConsistency: true,
  smartSuggestions: true,
  model: 'gpt-4'
})

// 表单验证规则
const styleRules = {
  name: [
    { required: true, message: '请输入风格名称', trigger: 'blur' }
  ],
  tone: [
    { required: true, message: '请选择写作风格', trigger: 'change' }
  ],
  audience: [
    { required: true, message: '请选择目标受众', trigger: 'change' }
  ],
  length: [
    { required: true, message: '请选择文章长度', trigger: 'change' }
  ]
}

// 生命周期
onMounted(() => {
  loadStyleProfiles()
})

// 加载风格档案
const loadStyleProfiles = async () => {
  loading.value = true
  
  try {
    const response = await getStyles()
    styleProfiles.value = response.data || []
    
    // 如果有档案，选中第一个
    if (styleProfiles.value.length > 0) {
      selectProfile(styleProfiles.value[0])
    }
  } catch (error) {
    console.error('Load style profiles error:', error)
    ElMessage.error('加载风格档案失败')
  } finally {
    loading.value = false
  }
}

// 选择档案
const selectProfile = (profile) => {
  selectedProfile.value = profile
  
  // 填充表单
  styleForm.name = profile.name || ''
  styleForm.description = profile.description || ''
  styleForm.tone = profile.tone || 'professional'
  styleForm.audience = profile.audience || 'technical'
  styleForm.length = profile.length || 'medium'
  styleForm.keywords = profile.keywords || []
  styleForm.example_sentence = profile.example_sentence || ''
}

// 创建新档案
const createNewStyle = () => {
  selectedProfile.value = null
  resetForm()
}

// 编辑档案
const editProfile = (profile) => {
  selectProfile(profile)
}

// 删除档案
const deleteProfile = async (profile) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除风格档案"${profile.name}"吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await deleteStyle(profile.id)
    
    // 从列表移除
    styleProfiles.value = styleProfiles.value.filter(p => p.id !== profile.id)
    
    // 如果删除的是当前选中的，清空选择
    if (selectedProfile.value?.id === profile.id) {
      selectedProfile.value = null
      resetForm()
    }
    
    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error('Delete style error:', error)
    }
  }
}

// 保存风格
const saveStyle = async () => {
  try {
    await styleFormRef.value.validate()
    
    saving.value = true
    
    const styleData = {
      name: styleForm.name,
      description: styleForm.description,
      tone: styleForm.tone,
      audience: styleForm.audience,
      length: styleForm.length,
      keywords: styleForm.keywords,
      example_sentence: styleForm.example_sentence
    }
    
    if (selectedProfile.value) {
      // 更新
      await updateStyle(selectedProfile.value.id, styleData)
      ElMessage.success('风格更新成功')
    } else {
      // 创建
      const response = await createStyle(styleData)
      styleProfiles.value.unshift(response.data)
      selectedProfile.value = response.data
      ElMessage.success('风格创建成功')
    }
    
    // 重新加载列表
    await loadStyleProfiles()
  } catch (error) {
    if (error !== false) {
      ElMessage.error('保存失败')
      console.error('Save style error:', error)
    }
  } finally {
    saving.value = false
  }
}

// 重置表单
const resetForm = () => {
  styleForm.name = ''
  styleForm.description = ''
  styleForm.tone = 'professional'
  styleForm.audience = 'technical'
  styleForm.length = 'medium'
  styleForm.keywords = []
  styleForm.example_sentence = ''
}

// 保存AI设置
const saveAiSettings = async () => {
  savingAiSettings.value = true
  
  try {
    // 这里应该调用API保存AI设置
    await new Promise(resolve => setTimeout(resolve, 500))
    
    ElMessage.success('AI设置保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('Save AI settings error:', error)
  } finally {
    savingAiSettings.value = false
  }
}

// 处理文章上传
const handleArticleUpload = (file) => {
  // 验证文件大小
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过10MB')
    return
  }
  
  // 这里应该调用API上传文章进行分析
  ElMessage.success('文章上传成功，正在分析...')
  
  // 模拟添加到列表
  analyzedArticles.value.push({
    id: Date.now(),
    title: file.name,
    word_count: Math.floor(Math.random() * 3000) + 1000,
    analyzed_at: new Date().toISOString().split('T')[0]
  })
}

// 移除文章
const removeArticle = (article) => {
  ElMessageBox.confirm(
    `确定要移除文章"${article.title}"吗？`,
    '确认移除',
    {
      confirmButtonText: '移除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    analyzedArticles.value = analyzedArticles.value.filter(a => a.id !== article.id)
    ElMessage.success('移除成功')
  }).catch(() => {})
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.style-settings {
  max-width: 1200px;
  margin: 0 auto;
}
</style>