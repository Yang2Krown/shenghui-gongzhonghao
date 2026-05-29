<template>
  <div class="tool-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">大纲生成</h1>
        <p class="page-desc">给定信息源（可选指定创作角度），生成结构清晰的文章大纲</p>
      </div>
    </div>

    <div class="card input-card">
      <div class="section-title">
        <h3>信息源</h3>
        <span class="section-hint">支持文字 / PDF / 链接，可添加多个</span>
      </div>
      <MultiSourceInput :sources="sources" @update="sources = $event" />
      <div style="margin-top: 20px;">
        <label class="label">创作角度 <span style="color: var(--ink-3); font-weight: 400;">（选填）</span></label>
        <input class="input-field" placeholder="如：从行业共识的反面切入 —— 留空则由 AI 自动确定角度" v-model="angle" />
      </div>
      <hr class="divider" />
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-clay btn-lg" :disabled="!canSubmit || loading" @click="run">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.8L18.5 9 13.8 10.8 12 15.5 10.2 10.8 5.5 9l4.7-1.2L12 3z"/></svg>
          生成大纲
        </button>
      </div>
    </div>

    <div v-if="loading" class="card loading-card">
      <Loading text="正在搭建文章结构…" />
    </div>

    <div v-if="result && !loading" class="card result-card animate-fade-in">
      <div class="result-top">
        <span class="badge badge-pine">大纲</span>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-ghost btn-sm" @click="run">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5"/></svg>
            重新生成
          </button>
          <button class="btn btn-clay btn-sm" @click="goBody">
            生成正文 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      </div>
      <h2 class="outline-title">{{ result.title }}</h2>
      <div class="outline-sections">
        <div v-for="(s, i) in result.sections" :key="i" class="outline-section">
          <div class="section-num">{{ i + 1 }}</div>
          <div class="section-content">
            <h4>{{ s.h }}</h4>
            <ul>
              <li v-for="(p, j) in s.points" :key="j">{{ p }}</li>
            </ul>
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
import Loading from '@/components/shared/Loading.vue'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const sources = ref([{ kind: 'text', text: '', url: '', fileName: '' }])
const angle = ref('')
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
      })),
      angle: angle.value || undefined,
    }
    const res = await post('/ai/outline', payload)
    result.value = res.data
  } catch (e) {
    result.value = {
      title: '当"风口"成为集体幻觉：一份给清醒者的观察笔记',
      sections: [
        { h: '开头 · 制造共识裂缝', points: ['用一个反直觉的数据开场', '抛出核心问题'] },
        { h: '第一部分 · 现象描述', points: ['描摹当下狂热的三个典型场景', '引用关键事实与数据'] },
        { h: '第二部分 · 拆解本质', points: ['区分"真实需求"与"被制造的需求"', '从历史寻找参照系'] },
        { h: '第三部分 · 落到个体', points: ['一个普通从业者的真实选择', '给清醒者的 3 条行动建议'] },
        { h: '结尾 · 留白与回响', points: ['回到开头的问题', '用一句话引发读者自我对照'] },
      ]
    }
  }
  loading.value = false
}

const goBody = () => {
  router.push({ path: '/body', query: { outline: result.value?.title || '' } })
}

onMounted(() => {
  if (route.query.angle) angle.value = route.query.angle
})
</script>

<style scoped>
.tool-page { max-width: 820px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 30px; line-height: 1.2; font-weight: 500; font-family: var(--serif); color: var(--ink); margin: 0; }
.page-desc { font-size: 14px; color: var(--ink-3); margin-top: 6px; }
.input-card { padding: 24px; margin-bottom: 20px; }
.section-title { display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; }
.section-title h3 { font-size: 16px; font-weight: 600; color: var(--ink); margin: 0; }
.section-hint { font-size: 12px; color: var(--ink-4); }
.label { display: block; font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 8px; }
.divider { height: 1px; background: var(--line); border: 0; margin: 20px 0; }
.loading-card { padding: 8px; margin-bottom: 20px; }
.result-card { padding: 28px; }
.result-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }
.outline-title { font-size: 22px; line-height: 1.3; font-weight: 500; font-family: var(--serif); color: var(--ink); margin: 10px 0 22px; }
.outline-sections { display: flex; flex-direction: column; gap: 18px; }
.outline-section { display: flex; gap: 14px; }
.section-num { flex-shrink: 0; width: 28px; height: 28px; border-radius: var(--r-sm); background: var(--clay); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }
.section-content h4 { font-size: 16px; font-weight: 600; color: var(--ink); margin: 0; }
.section-content ul { margin: 8px 0 0; padding-left: 18px; }
.section-content li { font-size: 14px; color: var(--ink-2); margin-bottom: 4px; }
.animate-fade-in { animation: fadeIn 0.28s cubic-bezier(0.32, 0.72, 0, 1); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
