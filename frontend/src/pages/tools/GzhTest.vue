<template>
  <div class="gzh-test-page">
    <!-- Hero -->
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><View /></el-icon>
        临时功能 · 公众号抓取测试
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        看看公众号抓到了<span class="text-clay">什么文章</span>
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        该页面仅用于功能验证，验证完后整文件删除（路由 /tools/gzh-test + 前端页 + 后端 _test_gzh_fetch.py）。
      </p>
    </div>

    <!-- 总览 -->
    <div v-loading="loading" style="margin-bottom: 16px;">
      <div class="card" style="padding: 18px 22px; display: flex; align-items: center; gap: 28px;">
        <div>
          <div style="font-size: 13px; color: var(--ink-4);">公众号数</div>
          <div style="font-size: 26px; font-weight: 700; font-family: var(--font-serif); color: var(--ink);">
            {{ summary.total_accounts || 0 }}
          </div>
        </div>
        <div>
          <div style="font-size: 13px; color: var(--ink-4);">总文章数</div>
          <div style="font-size: 26px; font-weight: 700; font-family: var(--font-serif); color: var(--ink);">
            {{ summary.total_articles || 0 }}
          </div>
        </div>
        <div style="flex: 1;"></div>
        <button class="btn-ghost btn-uniform" @click="loadSummary" :disabled="loading">刷新</button>
      </div>
    </div>

    <!-- 公众号列表 -->
    <div v-if="!loading && summary.accounts && summary.accounts.length">
      <div class="text-sm" style="color: var(--ink-4); margin-bottom: 10px;">
        点击公众号名查看它抓到的文章
      </div>
      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="gzh-table">
          <thead>
            <tr>
              <th>公众号</th>
              <th>平台</th>
              <th style="text-align: right;">文章数</th>
              <th>首次抓取</th>
              <th>最近抓取</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="acc in summary.accounts" :key="acc.source_account_id + acc.platform + acc.account_name"
                class="gzh-tr" :class="{ selected: selectedAccountId === acc.source_account_id }"
                @click="openAccount(acc)">
              <td>
                <div style="font-weight: 600; color: var(--ink);">{{ acc.account_name }}</div>
                <div v-if="acc.handle" style="font-size: 12px; color: var(--ink-4);">{{ acc.handle }}</div>
              </td>
              <td><el-tag size="small" type="info">{{ acc.platform }}</el-tag></td>
              <td style="text-align: right; font-variant-numeric: tabular-nums; font-weight: 600;">
                {{ acc.articles_count }}
              </td>
              <td style="font-size: 13px; color: var(--ink-3);">{{ fmtDate(acc.first_scraped_at) }}</td>
              <td style="font-size: 13px; color: var(--ink-3);">{{ fmtDate(acc.last_scraped_at) }}</td>
              <td><button class="btn-ghost btn-sm" @click.stop="openAccount(acc)">查看</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 空态 -->
    <div v-if="!loading && summary.accounts && !summary.accounts.length" class="card" style="padding: 48px; text-align: center;">
      <el-empty description="暂无公众号数据 — 先去跑一波 exa_wechat / sogou_wechat / gzh_explosive 的抓取" />
    </div>

    <!-- 单公众号详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="`${selectedAccount?.display_name || '公众号'} · 最近文章`" size="64%" :with-header="true">
      <div v-loading="articlesLoading">
        <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 12px;">
          <el-tag size="small">{{ selectedAccount?.platform }}</el-tag>
          <el-tag size="small" type="success">{{ selectedAccount?.source_type }}</el-tag>
          <div style="flex: 1;"></div>
          <el-input v-model="kw" placeholder="标题关键词" clearable style="width: 220px;" @change="loadArticles(0)" />
        </div>
        <div v-if="articles.items && articles.items.length" class="card" style="padding: 0; overflow: hidden;">
          <table class="gzh-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>作者</th>
                <th>发布时间</th>
                <th>抓取时间</th>
                <th>疑似商单</th>
                <th style="width: 70px;"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="art in articles.items" :key="art.id">
                <td style="max-width: 380px;">
                  <a :href="art.url" target="_blank" rel="noopener" class="art-link" :title="art.title">{{ art.title }}</a>
                  <div v-if="art.summary" class="art-summary">{{ art.summary }}</div>
                </td>
                <td style="font-size: 13px; color: var(--ink-3);">{{ art.author || '—' }}</td>
                <td style="font-size: 13px; color: var(--ink-3);">{{ fmtDate(art.published_at) }}</td>
                <td style="font-size: 13px; color: var(--ink-3);">{{ fmtDate(art.scraped_at) }}</td>
                <td>
                  <el-tag v-if="art.commercial_level === 'suspected'" size="small" type="warning">疑似</el-tag>
                  <el-tag v-else-if="art.commercial_level === 'likely'" size="small" type="danger">很高</el-tag>
                  <span v-else style="color: var(--ink-4);">—</span>
                </td>
                <td><a :href="art.url" target="_blank" rel="noopener" class="btn-ghost btn-sm">打开</a></td>
              </tr>
            </tbody>
          </table>

          <div style="display: flex; justify-content: flex-end; padding: 12px 16px;">
            <el-pagination
              background
              layout="prev, pager, next"
              :total="articles.total"
              :page-size="20"
              v-model:current-page="page"
              @current-change="(p) => loadArticles((p - 1) * 20)"
            />
          </div>
        </div>
        <el-empty v-else description="该公众号下暂无文章数据" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { get } from '@/api/api'
import { formatDateTimeMinute } from '@/utils/dateTime'

const loading = ref(false)
const articlesLoading = ref(false)
const summary = reactive({ total_accounts: 0, total_articles: 0, accounts: [] })
const articles = reactive({ items: [], total: 0, offset: 0, limit: 20 })
const kw = ref('')
const page = ref(1)
const drawerVisible = ref(false)
const selectedAccountId = ref(null)
const drawerQuery = ref({ type: null, id: null })
const selectedAccount = ref(null)

async function loadSummary() {
  loading.value = true
  try {
    const r = await get('/_test_gzh_fetch/summary')
    const d = r?.data ?? r
    summary.total_accounts = d.total_accounts || 0
    summary.total_articles = d.total_articles || 0
    summary.accounts = d.accounts || []
  } catch (e) {
    ElMessage.error('加载失败：' + (e?.response?.data?.message || e?.message || ''))
  } finally {
    loading.value = false
  }
}

async function loadArticles(offset = 0) {
  articlesLoading.value = true
  try {
    const q = drawerQuery.value
    let path = ''
    if (q.type === 'account') {
      path = `/_test_gzh_fetch/account/${q.id}`
    } else if (q.type === 'ungrouped') {
      path = `/_test_gzh_fetch/ungrouped/${q.id}`
    } else {
      articles.items = []
      articles.total = 0
      return
    }
    const r = await get(path, { limit: 20, offset, keyword: kw.value || undefined })
    const d = r?.data ?? r
    articles.items = d.items || []
    articles.total = d.total || 0
    articles.offset = offset
  } catch (e) {
    articles.items = []
    articles.total = 0
    ElMessage.error('加载文章失败：' + (e?.response?.data?.detail || e?.response?.data?.message || e?.message || ''))
  } finally {
    articlesLoading.value = false
  }
}

async function openAccount(acc) {
  // 已绑定 source_account_id → 按号查；没绑定的"未分组"行 → 按 registry + source_account_id IS NULL 查
  if (acc.source_account_id) {
    selectedAccountId.value = acc.source_account_id
    selectedAccount.value = acc
    drawerQuery.value = { type: 'account', id: acc.source_account_id }
  } else if (acc.source_registry_id) {
    selectedAccountId.value = null
    selectedAccount.value = { ...acc, display_name: acc.account_name }
    drawerQuery.value = { type: 'ungrouped', id: acc.source_registry_id }
  } else {
    ElMessage.warning('公众号数据不完整，既没 source_account_id 也没 source_registry_id')
    return
  }
  kw.value = ''
  page.value = 1
  drawerVisible.value = true
  await loadArticles(0)
}

function fmtDate(s) {
  if (!s) return '—'
  try {
    return formatDateTimeMinute(s)
  } catch {
    return s
  }
}

onMounted(loadSummary)
</script>

<style scoped>
.gzh-test-page { max-width: 1100px; margin: 0 auto; padding: 32px 20px 80px; }
.gzh-table { width: 100%; border-collapse: collapse; }
.gzh-table th {
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-4);
  padding: 10px 14px;
  border-bottom: 1px solid var(--ink-1, #eee);
  background: var(--ink-0, #fafafa);
}
.gzh-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--ink-1, #eee);
  vertical-align: top;
}
.gzh-tr { cursor: pointer; transition: background .15s; }
.gzh-tr:hover { background: var(--ink-0, #fafafa); }
.gzh-tr.selected { background: color-mix(in srgb, var(--clay, #c2562f) 6%, transparent); }
.art-link {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--ink);
  text-decoration: none;
}
.art-link:hover { color: var(--clay, #c2562f); text-decoration: underline; }
.art-summary {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-4);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
