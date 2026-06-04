<template>
  <el-dialog
    v-model="visible"
    title="发布到小红书"
    width="480px"
    :close-on-click-modal="false"
    :close-on-press-escape="!publishing"
    @close="handleClose"
  >
    <!-- 步骤1：检查登录状态 -->
    <div v-if="step === 'checking'" class="publish-step">
      <el-icon class="spin" :size="24"><Loading /></el-icon>
      <p>正在检查小红书登录状态...</p>
    </div>

    <!-- 需要登录 -->
    <div v-else-if="step === 'need_login'" class="publish-step">
      <el-icon :size="48" style="color: var(--clay); margin-bottom: 16px;"><WarningFilled /></el-icon>
      <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">需要登录小红书</p>
      <p style="color: var(--ink-3); margin-bottom: 20px;">请在弹出的浏览器窗口中扫码登录小红书创作者平台</p>
      <button class="btn-primary" @click="handleOpenLogin">
        <el-icon><Link /></el-icon> 打开登录页面
      </button>
      <button class="btn-text" style="margin-top: 12px;" @click="handleCheckLoginAgain">
        我已登录，重新检查
      </button>
    </div>

    <!-- 步骤2：填写发布信息 -->
    <div v-else-if="step === 'form'" class="publish-step">
      <div class="step-header">
        <span class="step-num">1</span>
        <span>填写发布信息</span>
      </div>
      <el-form label-position="top" style="margin-top: 16px;">
        <el-form-item label="账号（可选）">
          <el-input v-model="form.account" placeholder="留空则使用默认账号" />
        </el-form-item>
      </el-form>
      <button class="btn-primary" @click="handleStartPublish" :disabled="starting">
        <el-icon v-if="starting" class="spin"><Loading /></el-icon>
        <el-icon v-else><Promotion /></el-icon>
        {{ starting ? '启动中...' : '启动发布流程' }}
      </button>
    </div>

    <!-- 步骤3：选择模板 -->
    <div v-else-if="step === 'select_template'" class="publish-step">
      <div class="step-header">
        <span class="step-num">2</span>
        <span>选择排版模板</span>
      </div>
      <p style="color: var(--ink-3); margin: 12px 0;">选择一个排版模板应用到你的文章</p>
      <div class="template-list">
        <button
          v-for="tpl in templates"
          :key="tpl"
          :class="['template-item', { 'template-item--active': selectedTemplate === tpl }]"
          @click="selectedTemplate = tpl"
        >
          {{ tpl }}
        </button>
      </div>
      <button
        class="btn-primary"
        style="margin-top: 16px;"
        @click="handleSelectTemplate"
        :disabled="!selectedTemplate || selecting"
      >
        <el-icon v-if="selecting" class="spin"><Loading /></el-icon>
        <el-icon v-else><Check /></el-icon>
        {{ selecting ? '应用中...' : '应用模板' }}
      </button>
    </div>

    <!-- 步骤4：确认发布 -->
    <div v-else-if="step === 'confirm'" class="publish-step">
      <div class="step-header">
        <span class="step-num">3</span>
        <span>确认发布</span>
      </div>
      <p style="color: var(--ink-3); margin: 12px 0;">模板已应用，请在浏览器中确认内容无误后点击发布</p>
      <div style="background: var(--bone); padding: 12px; border-radius: var(--r-md); margin-bottom: 16px;">
        <p style="font-size: 13px; color: var(--ink-4);">
          <el-icon><InfoFilled /></el-icon>
          浏览器已打开小红书发布页面，内容已自动填充
        </p>
      </div>
      <button class="btn-primary" @click="handlePublish" :disabled="publishing">
        <el-icon v-if="publishing" class="spin"><Loading /></el-icon>
        <el-icon v-else><Promotion /></el-icon>
        {{ publishing ? '发布中...' : '确认发布' }}
      </button>
    </div>

    <!-- 发布成功 -->
    <div v-else-if="step === 'success'" class="publish-step">
      <el-icon :size="48" style="color: #52c41a; margin-bottom: 16px;"><CircleCheckFilled /></el-icon>
      <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">发布成功！</p>
      <p style="color: var(--ink-3);">内容已成功发布到小红书</p>
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
  Loading, Link, Promotion, Check, InfoFilled,
  WarningFilled, CircleCheckFilled, CircleCloseFilled
} from '@element-plus/icons-vue'
import {
  checkXhsLogin,
  openXhsLoginPage,
  startXhsLongArticle,
  selectXhsTemplate,
  clickXhsNextStep,
  clickXhsPublish
} from '@/api/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  content: { type: String, default: '' },
  tags: { type: Array, default: () => [] },
  // 图文混排数据，包含图片和文本块
  blocks: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = ref(false)
const step = ref('checking')
const errorMsg = ref('')

// 表单数据
const form = ref({
  account: ''
})

// 模板相关
const templates = ref([])
const selectedTemplate = ref('')
const starting = ref(false)
const selecting = ref(false)
const publishing = ref(false)

// 监听 v-model 变化
watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    initPublish()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

const initPublish = async () => {
  step.value = 'checking'
  errorMsg.value = ''

  try {
    const res = await checkXhsLogin()
    const data = res.data || res
    if (data.logged_in) {
      step.value = 'form'
    } else {
      step.value = 'need_login'
    }
  } catch (e) {
    step.value = 'need_login'
  }
}

const handleOpenLogin = async () => {
  try {
    await openXhsLoginPage(form.value.account)
    ElMessage.info('请在浏览器中完成登录')
  } catch (e) {
    ElMessage.error('打开登录页面失败')
  }
}

const handleCheckLoginAgain = async () => {
  step.value = 'checking'
  try {
    const res = await checkXhsLogin()
    const data = res.data || res
    if (data.logged_in) {
      step.value = 'form'
    } else {
      step.value = 'need_login'
      ElMessage.warning('尚未登录，请先完成登录')
    }
  } catch (e) {
    step.value = 'need_login'
  }
}

const handleStartPublish = async () => {
  starting.value = true
  try {
    const res = await startXhsLongArticle({
      title: props.title,
      content: props.content,
      blocks: props.blocks.length > 0 ? props.blocks : undefined,
      account: form.value.account || undefined
    })
    const data = res.data || res

    if (data.status === 'need_login') {
      step.value = 'need_login'
      ElMessage.warning('需要登录小红书')
    } else if (data.status === 'template_selection') {
      templates.value = data.templates || []
      step.value = 'select_template'
    }
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || '启动发布流程失败'
    step.value = 'error'
  } finally {
    starting.value = false
  }
}

const handleSelectTemplate = async () => {
  if (!selectedTemplate.value) return
  selecting.value = true
  try {
    await selectXhsTemplate(selectedTemplate.value)
    step.value = 'confirm'
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || '选择模板失败'
    step.value = 'error'
  } finally {
    selecting.value = false
  }
}

const handlePublish = async () => {
  publishing.value = true
  try {
    // 先点击下一步，填写描述
    const descParts = []
    if (props.title) descParts.push(props.title)
    if (props.tags?.length) descParts.push(props.tags.map(t => '#' + t).join(' '))
    await clickXhsNextStep(descParts.join('\n\n'))

    // 点击发布
    await clickXhsPublish()
    step.value = 'success'
    emit('success')
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || '发布失败'
    step.value = 'error'
  } finally {
    publishing.value = false
  }
}

const handleRetry = () => {
  step.value = 'form'
  errorMsg.value = ''
}

const handleClose = () => {
  visible.value = false
  emit('update:modelValue', false)
  // 重置状态
  step.value = 'checking'
  errorMsg.value = ''
  selectedTemplate.value = ''
  templates.value = []
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
  margin-bottom: 8px;
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

.template-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  width: 100%;
  margin-top: 12px;
}

.template-item {
  padding: 12px 16px;
  border: 1.5px solid var(--line);
  border-radius: var(--r-md);
  background: var(--paper);
  cursor: pointer;
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-2);
  transition: all 0.15s;
  text-align: center;
}

.template-item:hover {
  border-color: var(--clay-soft);
  background: var(--clay-tint);
}

.template-item--active {
  border-color: var(--clay);
  background: var(--clay-tint);
  color: var(--clay-deep);
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

.btn-secondary:hover {
  border-color: var(--clay-soft);
  background: var(--clay-tint);
}

.btn-text {
  border: none;
  background: transparent;
  color: var(--clay);
  font-family: inherit;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--r-sm);
  transition: background 0.12s;
}

.btn-text:hover {
  background: var(--clay-tint);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
