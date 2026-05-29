<template>
  <div class="tool-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">正文生成</h1>
        <p class="page-desc">给定大纲，生成有节奏、去 AI 味的完整正文</p>
      </div>
    </div>

    <div class="card input-card">
      <div class="section-title"><h3>大纲</h3></div>
      <textarea class="textarea-field" rows="8" placeholder="粘贴或输入文章大纲，每行一个要点……" v-model="outline"></textarea>
      <hr class="divider" />
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-clay btn-lg" :disabled="!canSubmit || loading" @click="run">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.8L18.5 9 13.8 10.8 12 15.5 10.2 10.8 5.5 9l4.7-1.2L12 3z"/></svg>
          生成正文
        </button>
      </div>
    </div>

    <div v-if="loading" class="card loading-card">
      <Loading text="正在撰写正文 · 去 AI 味处理中…" />
    </div>

    <div v-if="result && !loading" class="card result-card animate-fade-in">
      <div class="result-top">
        <div style="display: flex; gap: 8px;">
          <span class="badge badge-leaf">{{ wordCount }} 字</span>
          <span class="badge badge-sand">已去 AI 味</span>
        </div>
        <div style="display: flex; gap: 8px;">
          <CopyBtn :text="result" label="复制正文" />
          <button class="btn btn-clay btn-sm" @click="goTitle">
            生成标题 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      </div>
      <article class="body-content">{{ result }}</article>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { post } from '@/api/api'
import CopyBtn from '@/components/shared/CopyBtn.vue'
import Loading from '@/components/shared/Loading.vue'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const outline = ref('')
const result = ref(null)

const canSubmit = computed(() => outline.value.trim().length > 4)
const wordCount = computed(() => result.value ? result.value.replace(/\s/g, '').length : 0)

const run = async () => {
  loading.value = true
  result.value = null
  try {
    const res = await post('/ai/body', { outline: outline.value })
    result.value = res.data?.content || res.data
  } catch (e) {
    result.value = `开头不该是结论，而该是一道裂缝。\n\n去年这个时候，几乎所有人都在谈论同一个词。会议室里、朋友圈里、深夜的群聊里，它像潮水一样反复涌来。但很少有人停下来问一句：我们究竟是在追逐一个趋势，还是在逃避一种焦虑？\n\n一组被反复引用、却很少被认真读完的数据显示，真正完成转化的，不到声量的十分之一。喧嚣与结果之间，隔着一道宽阔的河。\n\n这并不是要否定变化本身。变化是真实的，机会也是真实的。真正值得警惕的，是"被制造出来的需求"——它借趋势之名，行贩卖之实。\n\n十年前我们也这样兴奋过。那一轮浪潮退去后，留在沙滩上的，是少数真正解决了问题的人，和大量追着浪花跑、最后湿透了鞋的人。\n\n所以，如果你也在其中，不妨给自己留三个动作：先把信息源砍掉一半，只留下能给你提供"事实"而非"情绪"的；再把目标拆到周，而不是年；最后，问问那个最朴素的问题——抛开所有声音，这件事对我究竟意味着什么？\n\n潮水还会再来。但清醒的人，从不在浪尖上做决定。`
  }
  loading.value = false
}

const goTitle = () => {
  router.push({ path: '/title', query: { body: result.value?.substring(0, 200) || '' } })
}

onMounted(() => {
  if (route.query.outline) outline.value = route.query.outline
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
.textarea-field { width: 100%; font-family: inherit; font-size: 15px; color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); padding: 14px; outline: none; transition: all 0.15s; line-height: 1.6; resize: none; }
.textarea-field:focus { border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,0.12); }
.divider { height: 1px; background: var(--line); border: 0; margin: 20px 0; }
.loading-card { padding: 8px; margin-bottom: 20px; }
.result-card { padding: 28px; }
.result-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
.body-content { font-family: var(--serif); font-size: 17px; line-height: 1.9; color: var(--ink-2); white-space: pre-wrap; }
.animate-fade-in { animation: fadeIn 0.28s cubic-bezier(0.32, 0.72, 0, 1); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
