<template>
  <div class="admin-page">
    <div class="admin-head">
      <div>
        <h1>商单诊断</h1>
        <p>检查极致了公众号商单链路：入库、正文、AI 判断、前端可见结果。</p>
      </div>
      <div class="actions">
        <select v-model.number="days" @change="fetchDiagnostics">
          <option :value="10">最近 10 天</option>
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

      <section class="diag-records">
        <div class="records-head">
          <div>
            <h2>商单记录</h2>
            <p>当前时间范围内的疑似和高概率商单，最多展示 200 条。</p>
          </div>
          <span class="records-count">{{ diagnostics.frontend_visible || 0 }} 条</span>
        </div>

        <div v-if="diagnostics.items?.length" class="record-list">
          <article v-for="item in diagnostics.items" :key="item.id" class="record-row">
            <div class="record-main">
              <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer" class="record-title">
                {{ item.title || '未命名文章' }}
              </a>
              <strong v-else class="record-title">{{ item.title || '未命名文章' }}</strong>
              <div class="record-meta">
                <span :class="['record-level', item.commercial_level]">
                  {{ item.commercial_level === 'likely' ? '高概率' : '疑似' }}
                </span>
                <span v-if="item.commercial_brand">{{ item.commercial_brand }}</span>
                <span v-if="item.commercial_category">{{ item.commercial_category }}</span>
                <span v-if="item.product">{{ item.product }}</span>
                <span>{{ formatDate(item.scraped_at || item.published_at) }}</span>
              </div>
            </div>
            <button
              v-if="userStore.isSuperAdmin"
              class="delete-button"
              type="button"
              @click="removeRecord(item)"
            >
              删除
            </button>
          </article>
        </div>
        <div v-else class="records-empty">当前时间范围内没有可管理的商单记录。</div>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteCommercialDiagnostic, getCommercialDiagnostics } from '@/api/admin'
import { useUserStore } from '@/stores/user'

const days = ref(10)
const loading = ref(false)
const diagnostics = ref(null)
const errorText = ref('')
const userStore = useUserStore()

const formatDate = (value) => {
  if (!value) return '时间未知'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

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

const removeRecord = async (item) => {
  try {
    await ElMessageBox.confirm(
      `删除后会移除这篇文章的商单标记，但原文仍会保留。确定删除「${item.title || '未命名文章'}」吗？`,
      '删除商单记录',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
    await deleteCommercialDiagnostic(item.id)
    await fetchDiagnostics()
    ElMessage.success('商单记录已删除，原文已保留')
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    const detail = e?.response?.data?.detail || e?.message || '删除失败'
    ElMessage.error(String(detail))
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
.diag-records { margin-top: 14px; padding: 20px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }
.records-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.records-head h2 { margin: 0; color: var(--ink); font-size: 18px; }
.records-head p { margin: 5px 0 0; color: var(--ink-4); font-size: 13px; }
.records-count { flex: none; color: var(--clay); font-size: 13px; }
.record-list { border-top: 1px solid var(--line); }
.record-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px 0; border-bottom: 1px solid var(--line); }
.record-row:last-child { border-bottom: 0; }
.record-main { min-width: 0; }
.record-title { display: block; overflow: hidden; color: var(--ink); font-size: 15px; font-weight: 700; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
a.record-title { text-decoration: none; }
a.record-title:hover { color: var(--clay); }
.record-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-top: 8px; color: var(--ink-4); font-size: 12px; }
.record-meta > span:not(.record-level)::before { content: '·'; margin-right: 7px; color: var(--line-strong, #cfc4b2); }
.record-level { padding: 3px 7px; border-radius: 999px; font-weight: 700; }
.record-level.suspected { color: #9a6413; background: #fff4da; }
.record-level.likely { color: #a84e32; background: #fbe5dc; }
.delete-button { flex: none; padding: 7px 13px; border: 1px solid #e4b8a9; border-radius: 7px; color: #b34e32; background: transparent; cursor: pointer; }
.delete-button:hover { color: #fff; background: #c96d4e; }
.records-empty { padding: 24px 0 5px; color: var(--ink-4); text-align: center; font-size: 13px; }
.diag-empty { padding: 50px 20px; text-align: center; border: 1px dashed var(--line); border-radius: 8px; color: var(--ink-4); background: var(--paper); }
.diag-empty strong { display: block; color: var(--ink); margin-bottom: 8px; }
.diag-empty p { margin: 0; color: #b42318; }
@media (max-width: 900px) {
  .admin-head { flex-direction: column; align-items: stretch; }
  .diag-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
  .diag-records { padding: 16px; }
  .record-row { align-items: flex-start; }
  .record-title { white-space: normal; }
}
</style>
