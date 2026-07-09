<template>
  <div class="admin-page">
    <div class="admin-head">
      <div>
        <h1>商单诊断</h1>
        <p>检查极致了公众号商单链路：入库、正文、AI 判断、前端可见结果。</p>
      </div>
      <div class="actions">
        <select v-model.number="days" @change="fetchDiagnostics">
          <option :value="7">最近 7 天</option>
          <option :value="30">最近 30 天</option>
          <option :value="90">最近 90 天</option>
          <option :value="180">最近 180 天</option>
        </select>
        <button @click="fetchDiagnostics">刷新</button>
      </div>
    </div>

    <div v-if="loading" class="diag-empty">加载中...</div>
    <div v-else-if="diagnostics" class="diag-wrap">
      <section class="diag-result">
        <span>当前结论</span>
        <strong>{{ diagnostics.diagnosis }}</strong>
      </section>

      <section class="diag-grid">
        <div><b>{{ diagnostics.total }}</b><span>极致了总入库</span></div>
        <div><b>{{ diagnostics.total_in_days }}</b><span>当前范围入库</span></div>
        <div><b>{{ diagnostics.with_fulltext }}</b><span>已有正文</span></div>
        <div><b>{{ diagnostics.ai_done }}</b><span>AI 已判断</span></div>
        <div><b>{{ diagnostics.ai_none }}</b><span>判为 none</span></div>
        <div><b>{{ diagnostics.suspected }}</b><span>疑似商单</span></div>
        <div><b>{{ diagnostics.likely }}</b><span>高概率商单</span></div>
        <div><b>{{ diagnostics.frontend_visible }}</b><span>前端当前可见</span></div>
      </section>
    </div>
    <div v-else class="diag-empty">
      <strong>诊断数据加载失败</strong>
      <p v-if="errorText">{{ errorText }}</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getCommercialDiagnostics } from '@/api/admin'

const days = ref(30)
const loading = ref(false)
const diagnostics = ref(null)
const errorText = ref('')

const fetchDiagnostics = async () => {
  loading.value = true
  errorText.value = ''
  try {
    const res = await getCommercialDiagnostics({ days: days.value })
    diagnostics.value = res.data || null
  } catch (e) {
    diagnostics.value = null
    const status = e?.response?.status
    const detail = e?.response?.data?.detail || e?.message || '未知错误'
    errorText.value = status ? `HTTP ${status}: ${detail}` : String(detail)
    ElMessage.error(errorText.value)
  } finally {
    loading.value = false
  }
}

onMounted(fetchDiagnostics)
</script>

<style scoped>
.admin-page { max-width: 1180px; margin: 0 auto; padding: 24px 12px 80px; }
.admin-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 18px; margin-bottom: 18px; }
.admin-head h1 { margin: 0; color: var(--ink); font-size: 26px; }
.admin-head p { margin: 6px 0 0; color: var(--ink-4); font-size: 14px; }
.actions { display: flex; gap: 8px; }
.actions select, .actions button { height: 34px; border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 0 10px; }
.actions button { cursor: pointer; color: var(--clay); }
.diag-result { padding: 18px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); margin-bottom: 14px; }
.diag-result span { display: block; color: var(--ink-4); font-size: 12px; margin-bottom: 6px; }
.diag-result strong { color: var(--ink); font-size: 18px; line-height: 1.5; }
.diag-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.diag-grid div { padding: 16px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }
.diag-grid b { display: block; color: var(--clay); font-size: 26px; }
.diag-grid span { color: var(--ink-4); font-size: 13px; }
.diag-empty { padding: 50px 20px; text-align: center; border: 1px dashed var(--line); border-radius: 8px; color: var(--ink-4); background: var(--paper); }
.diag-empty strong { display: block; color: var(--ink); margin-bottom: 8px; }
.diag-empty p { margin: 0; color: #b42318; }
@media (max-width: 900px) {
  .admin-head { flex-direction: column; align-items: stretch; }
  .diag-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
