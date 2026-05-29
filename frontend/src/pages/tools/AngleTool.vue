<template>
  <div class="tool-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">创作角度</h1>
        <p class="page-desc">给定一个或多个信息源，AI 帮你发掘陌生化、有张力的切入角度</p>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="card input-card">
      <div class="section-title">
        <h3>信息源</h3>
        <span class="section-hint">支持文字 / PDF / 链接，可添加多个</span>
      </div>
      <MultiSourceInput :sources="sources" @update="sources = $event" />
      <hr class="divider" />
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-clay btn-lg" :disabled="!canSubmit || loading" @click="run">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.8L18.5 9 13.8 10.8 12 15.5 10.2 10.8 5.5 9l4.7-1.2L12 3z"/></svg>
          生成创作角度
        </button>
      </div>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card loading-card">
      <Loading text="正在分析信息源，发掘创作角度…" />
    </div>

    <!-- 结果 -->
    <div v-if="result && !loading" class="result-section animate-fade-in">
      <div class="result-header">
        <div class="section-title">
          <h3>推荐角度</h3>
          <span class="section-hint">{{ result.length }} 个角度</span>
        </div>
        <button class="btn btn-ghost btn-sm" @click="run">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5"/></svg>
          换一批
        </button>
      </div>
      <div class="angle-grid">
        <div v-for="(a, i) in result" :key="i" class="card angle-card animate-slide-up"
          :style="{ animationDelay: `${i * 60}ms` }">
          <div class="angle-header">
            <span class="badge badge-clay">{{ a.tag }}</span>
            <span :class="['badge', a.heat === '高' ? 'badge-leaf' : 'badge-sand']">热度 {{ a.heat }}</span>
          </div>
          <h4 class="angle-title">{{ a.title }}</h4>
          <p class="angle-desc">{{ a.desc }}</p>
          <div class="angle-actions">
            <button class="btn btn-dark btn-sm" @click="goOutline(a.title)">
              用此角度写大纲 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </button>
            <CopyBtn :text="a.title" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { post } from '@/api/api'
import MultiSourceInput from '@/components/shared/MultiSourceInput.vue'
import CopyBtn from '@/components/shared/CopyBtn.vue'
import Loading from '@/components/shared/Loading.vue'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const sources = ref([{ kind: 'text', text: '', url: '', fileName: '' }])
const result = ref(null)

const canSubmit = computed(() => sources.value.some(s => s.text || s.url || s.fileName))

const run = async () => {
  loading.value = true
  result.value = null
  try {
    const payload = {
      sources: sources.value.filter(s => s.text || s.url || s.fileName).map(s => ({
        type: s.kind,
        content: s.text || s.url || s.fileName,
      }))
    }
    const res = await post('/ai/angle', payload)
    result.value = res.data?.angles || res.data || []
  } catch (e) {
    console.error('生成角度失败:', e)
    // 模拟数据
    result.value = [
      { tag: '反差视角', title: '所有人都在追的"风口"，其实是一场集体幻觉', desc: '从行业共识的反面切入，用一个被忽视的数据撕开裂缝。', heat: '高' },
      { tag: '个体叙事', title: '一个普通从业者的 365 天', desc: '以小人物的真实经历承载宏观议题。', heat: '中' },
      { tag: '历史对照', title: '十年前我们也这样兴奋过，后来呢？', desc: '把当下与历史上的相似时刻并置。', heat: '中' },
      { tag: '方法拆解', title: '抛开焦虑，普通人能立刻用上的 4 个动作', desc: '从信息源里提炼可操作的清单。', heat: '高' },
    ]
  }
  loading.value = false
}

const goOutline = (angle) => {
  router.push({ path: '/outline', query: { angle } })
}

onMounted(() => {
  if (route.query.from) {
    sources.value = [{ kind: 'text', text: route.query.from, url: '', fileName: '' }]
  }
})
</script>

<style scoped>
.tool-page {
  max-width: 820px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 30px;
  line-height: 1.2;
  font-weight: 500;
  font-family: var(--serif);
  color: var(--ink);
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: var(--ink-3);
  margin-top: 6px;
}

.input-card {
  padding: 24px;
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
}

.section-title h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

.section-hint {
  font-size: 12px;
  color: var(--ink-4);
}

.divider {
  height: 1px;
  background: var(--line);
  border: 0;
  margin: 20px 0;
}

.loading-card {
  padding: 8px;
  margin-bottom: 20px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.angle-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.angle-card {
  padding: 20px;
}

.angle-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.angle-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
  margin: 0;
}

.angle-desc {
  font-size: 14px;
  color: var(--ink-3);
  margin-top: 8px;
}

.angle-actions {
  margin-top: 14px;
  display: flex;
  gap: 8px;
}

.animate-fade-in {
  animation: fadeIn 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}

.animate-slide-up {
  animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1) both;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
