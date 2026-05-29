<template>
  <div class="tool-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">标题生成</h1>
        <p class="page-desc">给定正文生成标题；正文可以是文字、链接或文档</p>
      </div>
    </div>

    <div class="card input-card">
      <div class="section-title"><h3>正文来源</h3></div>
      <div style="display: flex; gap: 10px; margin-bottom: 16px;">
        <button v-for="m in modes" :key="m.key" @click="mode = m.key"
          :class="['chip', mode === m.key && 'chip-active']" style="padding: 8px 16px;">
          {{ m.label }}
        </button>
      </div>
      <div v-if="mode === 'file'">
        <div class="dropzone" @click="$refs.fileInput.click()">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="margin: 0 auto 6px; display: block;"><path d="M12 16V4M7 9l5-5 5 5M5 18v2a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2"/></svg>
          <div style="font-size: 14px; font-weight: 500;">点击上传 PDF / Word / TXT</div>
        </div>
        <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.txt" hidden @change="handleFile" />
      </div>
      <div v-else-if="mode === 'link'" style="position: relative;">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--ink-4)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; left: 14px; top: 14px;"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>
        <input class="input-field" style="padding-left: 40px;" placeholder="粘贴文章链接" v-model="value" />
      </div>
      <textarea v-else class="textarea-field" rows="9" placeholder="粘贴文章正文……" v-model="value"></textarea>
      <hr class="divider" />
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-clay btn-lg" :disabled="!canSubmit || loading" @click="run">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.8L18.5 9 13.8 10.8 12 15.5 10.2 10.8 5.5 9l4.7-1.2L12 3z"/></svg>
          生成标题
        </button>
      </div>
    </div>

    <div v-if="loading" class="card loading-card">
      <Loading text="正在打磨标题并多维打分…" />
    </div>

    <div v-if="result && !loading" class="result-section animate-fade-in">
      <div class="result-header">
        <div class="section-title">
          <h3>候选标题</h3>
          <span class="section-hint">按综合评分排序</span>
        </div>
        <button class="btn btn-ghost btn-sm" @click="run">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5"/></svg>
          换一批
        </button>
      </div>
      <div class="title-list">
        <div v-for="(t, i) in result" :key="i" class="card title-card animate-slide-up"
          :style="{ animationDelay: `${i * 50}ms` }">
          <div class="title-score">
            <div class="score-num" :style="{ color: t.score >= 88 ? 'var(--clay)' : 'var(--ink-2)' }">{{ t.score }}</div>
            <div class="score-label">评分</div>
          </div>
          <div class="title-info">
            <h4 class="title-text">{{ t.t }}</h4>
            <div class="title-tags">
              <span v-for="tag in t.tags" :key="tag" class="badge badge-sand">{{ tag }}</span>
            </div>
          </div>
          <CopyBtn :text="t.t" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { post } from '@/api/api'
import CopyBtn from '@/components/shared/CopyBtn.vue'
import Loading from '@/components/shared/Loading.vue'

const route = useRoute()
const loading = ref(false)
const mode = ref('text')
const value = ref('')
const fileName = ref('')
const result = ref(null)

const modes = [
  { key: 'text', label: '文字正文' },
  { key: 'link', label: '文章链接' },
  { key: 'file', label: '上传文档' },
]

const canSubmit = computed(() => mode.value === 'file' ? !!fileName.value : value.value.trim().length > 4)

const handleFile = (e) => {
  fileName.value = e.target.files?.[0]?.name || ''
}

const run = async () => {
  loading.value = true
  result.value = null
  try {
    const payload = { mode: mode.value }
    if (mode.value === 'text') payload.content = value.value
    else if (mode.value === 'link') payload.url = value.value
    else payload.filename = fileName.value
    const res = await post('/ai/titles', payload)
    result.value = res.data?.titles || res.data || []
  } catch (e) {
    result.value = [
      { t: '当"风口"成为集体幻觉：写给清醒者的一封信', score: 92, tags: ['悬念', '身份认同'] },
      { t: '所有人都在追的风口，其实是一场幻觉', score: 88, tags: ['反差'] },
      { t: '十年前我们也这样兴奋过，后来呢？', score: 85, tags: ['历史对照', '提问'] },
      { t: '抛开焦虑：普通人能立刻用上的 4 个动作', score: 83, tags: ['干货', '利他'] },
      { t: '潮水退去时，谁还站在岸上', score: 80, tags: ['隐喻'] },
    ]
  }
  loading.value = false
}

onMounted(() => {
  if (route.query.body) value.value = route.query.body
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
.chip { display: inline-flex; align-items: center; gap: 5px; cursor: pointer; border-radius: var(--r-pill); padding: 6px 13px; font-size: 13px; font-weight: 500; background: var(--paper); color: var(--ink-2); border: 1px solid var(--line); transition: all 0.15s; }
.chip:hover { border-color: var(--clay-soft); color: var(--ink); }
.chip-active { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.input-field { width: 100%; font-family: inherit; font-size: 15px; color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); padding: 11px 14px; outline: none; transition: all 0.15s; }
.input-field:focus { border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,0.12); }
.textarea-field { width: 100%; font-family: inherit; font-size: 15px; color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: var(--r-md); padding: 14px; outline: none; transition: all 0.15s; line-height: 1.6; resize: none; }
.textarea-field:focus { border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,0.12); }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all 0.15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.divider { height: 1px; background: var(--line); border: 0; margin: 20px 0; }
.loading-card { padding: 8px; margin-bottom: 20px; }
.result-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.title-list { display: flex; flex-direction: column; gap: 10px; }
.title-card { padding: 16px 20px; display: flex; align-items: center; gap: 16px; animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1) both; }
.title-score { flex-shrink: 0; text-align: center; width: 50px; }
.score-num { font-size: 24px; font-weight: 600; font-family: var(--serif); }
.score-label { font-size: 12px; color: var(--ink-4); }
.title-info { flex: 1; }
.title-text { font-size: 16px; font-weight: 600; color: var(--ink); line-height: 1.4; margin: 0; }
.title-tags { display: flex; gap: 6px; margin-top: 7px; }
.animate-fade-in { animation: fadeIn 0.28s cubic-bezier(0.32, 0.72, 0, 1); }
.animate-slide-up { animation: slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1) both; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
