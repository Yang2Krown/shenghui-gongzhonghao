<template>
  <div class="custom-topic">
    <!-- 页头 -->
    <header class="mb-6">
      <h1 class="text-h3 font-serif text-ink">自定义选题创作</h1>
      <p class="text-sm text-ink-3 mt-1">输入你的选题和参考资料，直接进入创作工作流</p>
    </header>

    <!-- 输入表单 -->
    <div class="card p-6 mb-6">
      <div class="mb-5">
        <label class="label">选题标题 <span class="text-crimson">*</span></label>
        <el-input
          v-model="form.title"
          placeholder="输入选题标题，如：为什么年轻人开始反向消费"
          maxlength="500"
          show-word-limit
        />
        <p class="text-xs text-ink-4 mt-1">14-500 字，一个好的标题能让 AI 更精准地理解你的创作意图</p>
      </div>

      <div class="mb-5">
        <label class="label">内容方向 <span class="text-crimson">*</span></label>
        <el-select v-model="form.direction" placeholder="选择内容方向" class="w-full">
          <el-option
            v-for="d in directions"
            :key="d.value"
            :label="d.label"
            :value="d.value"
          />
        </el-select>
        <p class="text-xs text-ink-4 mt-1">内容方向决定了文章的叙事策略和结构风格</p>
      </div>

      <div class="mb-5">
        <label class="label">参考资料 <span class="text-ink-3">（选填）</span></label>
        <el-input
          v-model="form.reference"
          type="textarea"
          placeholder="粘贴你的素材、信息源、关键数据、灵感笔记等参考资料...&#10;&#10;例如：&#10;- 某某报告显示，2024年XX消费下降了30%&#10;- 小红书上关于反向消费的热门讨论&#10;- 个人经历：我从去年开始..."
          :autosize="{ minRows: 6, maxRows: 16 }"
          resize="none"
        />
        <p class="text-xs text-ink-4 mt-1">参考资料会作为"创作角度体检"的信息源，帮助 AI 更好地把握创作方向</p>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-sm text-ink-3">
          {{ form.title.length }} 字标题
          {{ form.reference ? `· ${form.reference.length} 字参考资料` : '' }}
        </span>
        <el-button
          type="primary"
          size="large"
          @click="submit"
          :loading="loading"
          :disabled="!isValid"
        >
          <el-icon><Promotion /></el-icon>
          开始创作
        </el-button>
      </div>
    </div>

    <!-- 流程说明 -->
    <div class="card p-6">
      <h3 class="text-h4 font-sans text-ink mb-4">创作流程</h3>
      <div class="flow-steps">
        <div class="flow-step">
          <span class="flow-num">1</span>
          <div>
            <p class="text-sm font-semibold text-ink">创作角度体检</p>
            <p class="text-xs text-ink-3">审计信息源、检验角度陌生化、设计内容节奏</p>
          </div>
        </div>
        <div class="flow-arrow">
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div class="flow-step">
          <span class="flow-num">2</span>
          <div>
            <p class="text-sm font-semibold text-ink">大纲生成</p>
            <p class="text-xs text-ink-3">4 个 Agent 协作：创作 → 评审 → 挑刺 → 自检</p>
          </div>
        </div>
        <div class="flow-arrow">
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div class="flow-step">
          <span class="flow-num">3</span>
          <div>
            <p class="text-sm font-semibold text-ink">标题生成</p>
            <p class="text-xs text-ink-3">多维度打分，选出最优标题方案</p>
          </div>
        </div>
        <div class="flow-arrow">
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div class="flow-step">
          <span class="flow-num">4</span>
          <div>
            <p class="text-sm font-semibold text-ink">正文生成</p>
            <p class="text-xs text-ink-3">AI 撰写 + 去 AI 味 + 8 维度诊断</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Promotion, ArrowRight } from '@element-plus/icons-vue'
import { post } from '@/api/api'

const router = useRouter()

const form = ref({
  title: '',
  direction: '',
  reference: '',
})

const loading = ref(false)

const directions = [
  { label: '资讯型 — 传递新信息、新变化', value: '资讯型' },
  { label: '观点型 — 表达态度、立场、判断', value: '观点型' },
  { label: '故事型 — 叙事驱动，人物/经历/情节', value: '故事型' },
  { label: '干货型 — 实操方法、工具、清单', value: '干货型' },
  { label: '情感型 — 引发共鸣、情绪连接', value: '情感型' },
  { label: '趣味型 — 轻松好玩、反常识、冷知识', value: '趣味型' },
]

const isValid = computed(() => {
  return form.value.title.trim().length >= 2 && form.value.direction
})

const submit = async () => {
  if (!isValid.value) {
    ElMessage.warning('请填写选题标题并选择内容方向')
    return
  }

  loading.value = true
  try {
    const res = await post('/topic-candidates/custom', {
      title: form.value.title.trim(),
      direction: form.value.direction,
      reference: form.value.reference.trim() || null,
    })
    const data = res.data || res
    ElMessage.success('选题创建成功，进入创作工作流')
    router.push({
      path: '/creation/new',
      query: {
        candidate_id: data.id,
        topic_title: data.title,
        topic_direction: data.direction,
      },
    })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '创建失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.custom-topic {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 80px;
}

.label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}

/* 流程步骤 */
.flow-steps {
  display: flex;
  align-items: center;
  gap: 12px;
  overflow-x: auto;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bone);
  border-radius: var(--r-md);
  min-width: 0;
  flex: 1;
}

.flow-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--clay);
  color: var(--paper);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.flow-arrow {
  color: var(--ink-4);
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .flow-steps {
    flex-direction: column;
  }

  .flow-arrow {
    transform: rotate(90deg);
  }
}
</style>
