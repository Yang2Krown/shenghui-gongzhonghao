<template>
  <section class="monitor">
    <header>
      <div>
        <div class="kicker">后台管理 · XHS COLLECTION</div>
        <h1>小红书采集监测</h1>
        <p>本地安全采集、服务器入库、主动测试与运行监测</p>
      </div>
      <button class="refresh" :disabled="loading" @click="refresh">
        {{ loading ? "刷新中…" : "刷新监测" }}
      </button>
    </header>
    <div v-if="data" class="metric-grid">
      <article>
        <span>基础词完成进度</span
        ><strong
          >{{ data.progress.base_completed }} /
          {{ data.progress.base_total }}</strong
        ><i
          ><b
            :style="{
              width:
                percent(
                  data.progress.base_completed,
                  data.progress.base_total,
                ) + '%',
            }"
          ></b></i
        ><small
          >动态词 {{ data.progress.derived_completed }} /
          {{ data.progress.derived_total }}</small
        >
      </article>
      <article>
        <span>远程图片异常</span
        ><strong>{{ data.image_health.open_reports }}</strong
        ><i
          ><b
            class="clay"
            :style="{
              width: Math.min(100, data.image_health.open_reports * 5) + '%',
            }"
          ></b></i
        ><small
          >缺失 {{ data.image_health.missing }} · 疑似失效
          {{ data.image_health.suspected_invalid }}</small
        >
      </article>
    </div>
    <div v-if="data" class="alerts">
      <div v-for="a in data.alerts" :key="a.message" :class="a.level">
        <span
          >{{ a.level === "critical" ? "严重" : "警告" }} ·
          {{ a.message }}</span
        ><button
          v-if="a.key === 'image_failures'"
          class="alert-action"
          @click="openFailures"
        >
          去处理</button
        ><button
          v-else-if="a.key === 'tikhub_quota' && userStore.isSuperAdmin"
          class="alert-action"
          @click="scrollToTikhub"
        >
          去提额</button
        >
      </div>
      <div v-if="!data.alerts.length" class="ok">
        正常 · 当前没有小红书采集告警
      </div>
    </div>
    <article v-if="data" ref="recoveryCenter" class="panel recovery-center">
      <div class="recovery-head">
        <div>
          <div class="kicker">INCIDENT RECOVERY</div>
          <h2>故障处理中心</h2>
          <p>今日采集失败的关键词会列在这里，可立即重试</p>
        </div>
        <em :class="{ ok: !recoveryItems.length }">{{ recoveryItems.length ? `${recoveryItems.length} 项待处理` : "当前无需处理" }}</em>
      </div>
      <div v-if="recoveryItems.length" class="recovery-list">
        <section v-for="item in recoveryItems" :key="item.key" :class="['recovery-item', item.level]">
          <div class="recovery-copy">
            <div><span>{{ item.label }}</span><strong>{{ item.title }}</strong></div>
            <p>{{ item.cause }}</p>
            <small>建议：{{ item.solution }}</small>
            <small v-if="recoveryResult[item.key]" class="recovery-result">{{ recoveryResult[item.key] }}</small>
          </div>
          <button
            v-if="item.action === 'retry'"
            :disabled="recoveryBusy === item.key || (manualRetryWaitMinutes > 0 && !userStore.isSuperAdmin)"
            @click="retryFailedSlot(item.slot)"
          >{{ recoveryBusy === item.key ? "正在重试…" : manualRetryWaitMinutes > 0 ? userStore.isSuperAdmin ? `跳过冷却并重试` : `安全冷却 ${manualRetryWaitMinutes} 分钟` : "重新执行这个词" }}</button>
        </section>
      </div>
      <div v-else class="recovery-ok"><strong>采集链路正常</strong><span>今天没有待处理的失败。</span></div>
    </article>
    <article v-if="data && data.tikhub" ref="tikhubPanel" class="panel tikhub-panel">
      <div class="panel-head">
        <div>
          <div class="kicker">PAID CHANNEL · TIKHUB</div>
          <h2>TikHub 付费通道</h2>
          <p>配额、成本与调用健康；CLI 被风控时这是付费兜底来源</p>
        </div>
        <div class="tikhub-head-side">
          <span :class="['tikhub-token-badge', data.tikhub.token_configured ? 'ok' : 'bad']">
            {{ data.tikhub.token_configured ? "Token 已配置" : "Token 未配置" }}
          </span>
          <button v-if="userStore.isSuperAdmin" class="quiet" @click="openQuotaEditor">调整每日额度</button>
        </div>
      </div>
      <div class="tikhub-grid">
        <div class="tikhub-quota-card">
          <small>今日额度</small>
          <strong>{{ data.tikhub.today.used }}<em>/ {{ data.tikhub.today.limit }}</em></strong>
          <i><b :class="{ warn: quotaPercent(data.tikhub.today) >= 80 }" :style="{ width: quotaPercent(data.tikhub.today) + '%' }"></b></i>
          <span class="tikhub-quota-sub">剩余 {{ data.tikhub.today.remaining }} · 预留搜索 {{ data.tikhub.today.reserved_searches }}</span>
        </div>
        <div class="tikhub-cost-card">
          <small>今日成本</small>
          <strong>¥{{ (data.tikhub.today.estimated_cost_cny || 0).toFixed(2) }}</strong>
          <span class="tikhub-quota-sub">累计 ¥{{ (data.tikhub.totals.total_cost || 0).toFixed(2) }} · {{ data.tikhub.totals.total_calls }} 次</span>
        </div>
        <div class="tikhub-trend-card">
          <small>近 7 天成本</small>
          <svg viewBox="0 0 100 36" preserveAspectRatio="none" aria-hidden="true">
            <polyline v-if="tikhubCostSparkline" :points="tikhubCostSparkline" fill="none" stroke="var(--pine,#35695a)" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
          <span class="tikhub-quota-sub">{{ tikhubCostSummary }}</span>
        </div>
        <div class="tikhub-op-card">
          <small>今日按操作</small>
          <p v-for="op in data.tikhub.by_operation" :key="op.operation">
            <span>{{ opLabel(op.operation) }}</span><b>{{ op.count }} 次 · ¥{{ op.cost.toFixed(2) }}</b>
          </p>
          <p v-if="!data.tikhub.by_operation.length" class="tikhub-op-empty">今日暂无付费调用</p>
        </div>
      </div>
      <div class="tikhub-calls">
        <div class="tikhub-calls-head"><strong>付费调用明细</strong><span>仅 TikHub 通道,含每笔成本</span></div>
        <div class="table table-scroll tikhub-calls-table">
          <table>
            <thead>
              <tr><th>时间</th><th>操作</th><th>状态</th><th>成本</th><th>延迟</th><th>错误</th></tr>
            </thead>
            <tbody>
              <template v-for="c in tikhubCalls" :key="c.id">
                <tr :class="{ clickable: c.error_message }" @click="toggleCallExpand(c.id)">
                  <td>{{ time(c.created_at) }}</td>
                  <td>{{ opLabel(c.operation) }}</td>
                  <td><em :class="{ bad: c.status !== 'success' }">{{ status(c.status) }}</em></td>
                  <td>{{ c.status === 'success' && c.estimated_cost ? '¥' + c.estimated_cost.toFixed(3) : '—' }}</td>
                  <td>{{ c.latency_ms == null ? '—' : c.latency_ms + 'ms' }}</td>
                  <td class="err">{{ callError(c) }}</td>
                </tr>
                <tr v-if="expandedCall === c.id && c.error_message" class="call-detail">
                  <td colspan="6">{{ c.error_message }}</td>
                </tr>
              </template>
              <tr v-if="!tikhubCalls.length"><td colspan="6">近 24 小时暂无 TikHub 调用</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </article>
    <section v-if="data" class="funnel-section">
      <div class="funnel-head">
        <div><span>DATA FUNNEL · TODAY</span><h2>今日采集过滤漏斗</h2></div>
        <p>仅保留关键节点；重复、过期和详情缺失等淘汰原因可在执行明细中查看</p>
      </div>
      <div class="funnel">
        <div
          v-for="(s, i) in funnelStages"
          :key="s.label"
          class="stage"
          :class="[s.kind, { final: i === funnelStages.length - 1 && s.value > 0 }]"
        >
          <small>{{ s.label }}</small
          ><strong>{{ s.value }}</strong
          ><em v-if="s.conv" :class="{ zero: !s.value }">转化 {{ s.conv }}</em>
          <span v-if="s.note" class="stage-note">{{ s.note }}</span>
        </div>
      </div>
    </section>
    <section v-if="data" class="panel trends-panel">
      <div class="panel-head">
        <div>
          <div class="kicker">TRENDS</div>
          <h2>近 {{ trendDays }} 天采集趋势</h2>
          <p>成功率、入库量与风控(验证码)事件，按天聚合</p>
        </div>
        <div class="trend-tools">
          <button v-for="d in [7, 14, 30]" :key="d" :class="['trend-range', { active: trendDays === d }]" @click="setTrendDays(d)">{{ d }} 天</button>
        </div>
      </div>
      <div v-if="trendSeries.length" class="trends-grid">
        <figure class="trend-card">
          <figcaption>采集成功率<small>{{ trendSummary.success }}</small></figcaption>
          <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
            <polyline v-if="trendPaths.success" :points="trendPaths.success" fill="none" stroke="var(--pine,#35695a)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
        </figure>
        <figure class="trend-card">
          <figcaption>每日入库素材<small>{{ trendSummary.notes }}</small></figcaption>
          <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
            <polyline v-if="trendPaths.notes" :points="trendPaths.notes" fill="none" stroke="var(--pine,#35695a)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
        </figure>
        <figure class="trend-card">
          <figcaption>风控(验证码)事件<small>{{ trendSummary.captcha }}</small></figcaption>
          <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
            <polyline v-if="trendPaths.captcha" :points="trendPaths.captcha" fill="none" stroke="var(--clay,#c0735a)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
        </figure>
      </div>
      <p v-else class="trend-empty">暂无历史趋势数据，采集运行几天后自动生成。</p>
    </section>
    <div v-if="data" class="grid">
      <article class="panel runs">
        <div class="panel-head">
          <div>
            <h2>今日关键词执行</h2>
            <p>成功完成的关键词当天不可再次搜索</p>
          </div>
        </div>
        <div class="table table-scroll table-runs">
          <table>
            <thead>
              <tr>
                <th>关键词</th>
                <th>计划类型</th>
                <th>搜索 / 解析</th>
                <th>今日合格 / 一周合格 / 入库</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in runRows" :key="row.id">
                <td>
                  <b>{{ row.keyword }}</b
                  ><small>{{
                    row.keyword_type === "base" ? "基础词" : "动态词"
                  }}</small>
                </td>
                <td>{{ row.keyword_type === "base" ? "每日基础" : "随机总结" }}</td>
                <td>
                  {{ searchParseLabel(row) }}
                </td>
                <td>{{ filterResultLabel(row) }}</td>
                <td>
                  <em :class="row.status">{{ status(row.status) }}</em
                  ><small v-if="row.error_message" :title="row.error_message">{{
                    row.error_message
                  }}</small>
                </td>
                <td>
                  <div class="row-actions">
                    <button class="link" @click="openRunNotes(row)">明细</button>
                  </div>
                </td>
              </tr>
              <tr v-if="!runRows.length">
                <td colspan="6">今日尚无执行记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
      <aside>
        <article class="panel health">
          <h2>今日淘汰原因</h2>
          <p class="health-intro">搜索、解析、时间与点赞规则过滤掉的笔记，按原因归类。</p>
          <div>
            <p v-for="(count, key) in data.rejections" :key="key">
              {{ reason(key) }} <strong>{{ count }}</strong>
            </p>
            <p v-if="!Object.keys(data.rejections || {}).length" class="health-empty">今日暂无淘汰记录</p>
          </div>
        </article>
      </aside>
    </div>
    <article v-if="data" class="panel keyword-panel">
      <div class="panel-head">
        <div>
          <h2>关键词管理</h2>
          <p>{{ enabledBaseCount }} 个基础词全部参与，另加最多 5 个总结词；总结词连续 3 个有效零产出日自动淘汰</p>
        </div>
        <div class="kw-tools">
          <el-input
            v-model="kwFilter"
            class="kw-filter"
            placeholder="搜索关键词"
            clearable
            size="small"
          /><button v-if="userStore.isSuperAdmin" @click="showAdd = true">
            新增基础词
          </button>
          <button
            v-if="userStore.isSuperAdmin"
            :disabled="analyzeBusy"
            title="对全部素材重建今日热榜 + 持续发酵话题"
            @click="analyzeNow"
          >{{ analyzeBusy ? "分析中…" : "立即分析" }}</button>
        </div>
      </div>
      <div class="kw-grid">
        <div
          v-for="k in filteredKeywords"
          :key="k.id"
          class="kw-card"
          :class="{ off: !k.enabled }"
        >
          <div class="kw-main">
            <b>{{ k.keyword }}</b
            ><span class="kw-state">{{ lifecycleLabel(k) }}{{ k.pinned ? " · 已置顶" : "" }}</span>
          </div>
          <small>近次产出 {{ k.last_yield_count || 0 }} 篇 · 连续零产出 {{ k.zero_yield_streak || 0 }} 天<span v-if="k.quarantine_reason"> · {{ k.quarantine_reason }}</span></small>
          <div class="kw-actions">
            <button
              :disabled="searchBusy === `kw-${k.id}` || !userStore.isSuperAdmin"
              :title="userStore.isSuperAdmin ? '通过 TikHub 付费接口实时采集' : '仅最高管理员可用'"
              @click="searchNow(k)"
              >{{ searchBusy === `kw-${k.id}` ? "搜索中…" : "立即搜索" }}</button
            ><button @click="openKeywordHistory(k)">历史</button
            ><template v-if="userStore.isSuperAdmin"
              ><button @click="openEdit(k)">修改</button
              ><button @click="toggle(k)">
                {{ k.enabled ? "停用" : "启用" }}</button
              ><button @click="pinKeyword(k)">{{ k.pinned ? "取消置顶" : "置顶" }}</button
              ><button v-if="k.lifecycle_status === 'quarantined'" @click="restoreKeyword(k)">恢复试采</button
              ><button v-if="k.type === 'derived'" @click="promote(k)">
                提升</button
              ><button class="danger" @click="removeKeyword(k)">
                删除
              </button></template
            >
          </div>
        </div>
        <p v-if="!filteredKeywords.length" class="kw-empty">
          没有匹配「{{ kwFilter }}」的关键词
        </p>
      </div>
    </article>
    <article v-if="data" class="panel">
      <div class="panel-head">
        <div>
          <h2>最近请求审计</h2>
          <p>TikHub 付费通道的请求记录；不记录 Token 或 Cookie</p>
        </div>
      </div>
      <div class="table table-scroll table-audit">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>来源</th>
              <th>操作</th>
              <th>状态</th>
              <th>延迟</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in tikhubCalls" :key="c.id">
              <td>{{ time(c.created_at) }}</td>
              <td>{{ c.provider }}</td>
              <td>{{ c.operation }}</td>
              <td>{{ status(c.status) }}</td>
              <td>{{ c.latency_ms == null ? "—" : c.latency_ms + "ms" }}</td>
              <td :title="c.error_message || ''">{{ callError(c) }}</td>
            </tr>
            <tr v-if="!tikhubCalls.length"><td colspan="6">近 24 小时暂无 TikHub 调用</td></tr>
          </tbody>
        </table>
      </div>
    </article>
    <el-dialog v-model="showAdd" title="新增小红书基础词" width="420px" append-to-body :lock-scroll="false"
      ><el-form label-position="top"
        ><el-form-item label="关键词"
          ><el-input
            v-model="newKeyword.keyword"
            maxlength="120" /></el-form-item
        ></el-form
      ><template #footer
        ><el-button @click="showAdd = false">取消</el-button
        ><el-button type="primary" @click="addKeyword"
          >确认新增</el-button
        ></template
      ></el-dialog
    >
    <el-dialog v-model="showEdit" title="修改关键词" width="420px" append-to-body :lock-scroll="false"
      ><el-form label-position="top"
        ><el-form-item label="关键词"
          ><el-input
            v-model="editKeyword.keyword"
            maxlength="120"
            @keyup.enter="saveEdit" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="showEdit = false">取消</el-button
        ><el-button type="primary" @click="saveEdit">保存</el-button></template
      ></el-dialog
    >
    <el-dialog
      v-model="showRunNotes"
      :title="`抓取明细 · ${runNotesTitle}`"
      width="780px"
      append-to-body
      :lock-scroll="false"
      ><div v-if="runNotesRun" class="run-diagnostics">
        <template v-if="runNotesRun.has_search_diagnostics">
          <p class="diagnostic-summary" :class="{ warning: runNotesRun.search_state === 'unrecognized' }">
            {{ runDiagnosticSummary(runNotesRun) }}
          </p>
          <div class="diagnostic-grid">
            <div><small>搜索线路</small><b>{{ searchRouteLabel(runNotesRun) }}</b></div>
            <div><small>搜索页返回</small><b>{{ runNotesRun.tikhub_raw_count }}</b></div>
            <div><small>成功解析</small><b>{{ runNotesRun.merged_count }}</b></div>
            <div><small>今日候选</small><b>{{ levelStat(runNotesRun, "daily", "candidate_count") }}</b></div>
            <div><small>搜索页初筛 · 24h赞 &gt; 200</small><b>{{ levelStat(runNotesRun, "daily", "eligible_count") }}</b></div>
            <div><small>一周候选</small><b>{{ levelStat(runNotesRun, "weekly", "candidate_count") }}</b></div>
            <div><small>搜索页初筛 · 7天赞 &gt; 2000</small><b>{{ levelStat(runNotesRun, "weekly", "eligible_count") }}</b></div>
            <div><small>详情解析成功</small><b>{{ runNotesRun.detail_success_count }} / {{ runNotesRun.detail_attempted_count }}</b></div>
            <div><small>详情复核后入库</small><b>{{ runNotesRun.displayable_count }}</b></div>
          </div>
          <div v-if="diagnosticRejections.length" class="diagnostic-rejections">
            <span v-for="item in diagnosticRejections" :key="item.key">{{ reason(item.key) }} <b>{{ item.count }}</b></span>
          </div>
        </template>
        <p v-else class="diagnostic-summary legacy">
          历史运行未上传原始搜索漏斗，无法判断是搜索页返回空，还是结果在后续规则中被过滤；因此不显示为 0 条。
        </p>
      </div><div class="table notes-table">
        <table>
          <thead>
            <tr>
              <th>标题</th>
              <th>作者</th>
              <th>点赞</th>
              <th>发布时间</th>
              <th>来源</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="n in runNotes" :key="n.note_id">
              <td>
                <a
                  class="note-link"
                  :href="n.original_url || n.stable_url"
                  target="_blank"
                  rel="noopener"
                  >{{ n.title || n.note_id }}</a
                >
              </td>
              <td>{{ n.author || "—" }}</td>
              <td>{{ n.like_count ?? "—" }}</td>
              <td>{{ time(n.published_at) }}</td>
              <td>
                {{
                  n.providers
                    .map(
                      (p) => p.provider + (p.rank != null ? " #" + p.rank : ""),
                    )
                    .join(" + ")
                }}
              </td>
              <td>
                <em :class="{ bad: noteStatus(n.status) !== '入库' }">{{
                  noteStatus(n.status)
                }}</em>
              </td>
            </tr>
            <tr v-if="!runNotes.length">
              <td colspan="6">{{ emptyRunNotesMessage }}</td>
            </tr>
          </tbody>
        </table>
      </div></el-dialog
    >
    <el-dialog v-model="showFailures" title="图片失败报告" width="680px" append-to-body :lock-scroll="false"
      ><div class="table fail-table">
        <table>
          <thead>
            <tr>
              <th>笔记</th>
              <th>类型</th>
              <th>失败次数</th>
              <th>最近失败</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in failures" :key="r.id">
              <td>
                <b>{{ r.title || r.note_id }}</b
                ><small>{{ r.note_id }}</small>
              </td>
              <td>{{ r.image_kind === "cover" ? "封面" : "头像" }}</td>
              <td>{{ r.failure_count }}</td>
              <td>{{ time(r.last_failed_at) }}</td>
              <td>
                <button class="link" :disabled="imageRefreshBusy === r.note_id" @click="refreshImage(r)">
                  {{ imageRefreshBusy === r.note_id ? "正在刷新…" : "免费刷新图片" }}</button
                ><button class="link paid" @click="resolveFailure(r)">
                  标记已处理
                </button>
                <small v-if="imageRefreshFeedback[r.note_id]" class="refresh-feedback">{{ imageRefreshFeedback[r.note_id] }}</small>
              </td>
            </tr>
            <tr v-if="!failures.length">
              <td colspan="5">没有未处理的报告</td>
            </tr>
          </tbody>
        </table>
      </div></el-dialog
    >
    <el-dialog v-model="showAgentPairing" title="绑定本地采集节点" width="460px" append-to-body :lock-scroll="false">
      <div class="pairing-box">
        <p>绑定码 10 分钟内有效。安装程序只需运行一次。</p>
        <strong>{{ pairingCode || "正在生成…" }}</strong>
        <ol>
          <li>打开项目中的 <code>local_agents/xhs_collector/install.command</code></li>
          <li>输入上面的绑定码</li>
          <li>安装完成后回到这里刷新节点</li>
        </ol>
      </div>
      <template #footer><el-button @click="showAgentPairing = false">关闭</el-button></template>
    </el-dialog>
    <el-dialog v-model="showLocalLogin" title="本地 Mac 小红书登录" width="460px" append-to-body :lock-scroll="false" :close-on-click-modal="false" @closed="stopLocalLoginPoll">
      <div class="qr-auth">
        <div class="local-auth-methods">
          <button :class="{ active: localLoginMode === 'login' }" @click="startLocalLogin">扫码登录</button>
          <button :class="{ active: localLoginMode === 'browser_login' }" @click="startLocalBrowserLogin">浏览器同步</button>
        </div>
        <p class="local-auth-help">
          {{ localLoginMode === 'browser_login'
            ? '从这台 Mac 的 Chrome/Safari 读取已登录 Cookie，适合浏览器已能正常打开小红书的情况。'
            : localLoginMode === 'verify_session'
              ? '正在检查人机验证后的旧 Cookie，这一步不会生成二维码。'
              : '使用小红书 App 扫码并在手机上确认，新 Cookie 只保存在这台 Mac。' }}
        </p>
        <div v-if="localLoginMode === 'login' && !localLoginQr" class="qr-placeholder">正在让本地 Mac 生成二维码…
        </div>
        <div v-else-if="localLoginMode === 'browser_login'" class="qr-placeholder browser-sync">正在读取本机浏览器登录态…</div>
        <canvas v-show="localLoginMode === 'login' && localLoginQr" ref="localLoginCanvas"></canvas>
        <p :class="['auth-state', localLoginState]">{{ localLoginMessage }}</p>
        <div v-if="localLoginState === 'failed' || localLoginState === 'expired'" class="local-auth-actions">
          <button class="retry-auth" @click="startLocalLogin">重新获取二维码</button>
          <button class="retry-auth" @click="startLocalBrowserLogin">改用浏览器同步</button>
        </div>
        <div v-if="localLoginVerificationUrl" class="auth-verify">
          <a :href="localLoginVerificationUrl" target="_blank" rel="noopener noreferrer">打开小红书人机验证</a>
          <button class="retry-auth" @click="confirmRiskVerification">我已完成验证</button>
          <small>若验证页显示“系统检测到异常行为”，说明这条验证链接不可继续使用，请选择下面的兜底方式。</small>
          <div class="verification-fallbacks">
            <button class="retry-auth" @click="startLocalBrowserLogin">从当前浏览器同步 Cookie</button>
            <button class="retry-auth" @click="startLocalLogin">放弃此链接，重新扫码</button>
          </div>
        </div>
        <small>Cookie 只写入本地 Mac，不会上传服务器。</small>
      </div>
    </el-dialog>
    <el-dialog v-model="showSchedule" title="采集策略" width="440px" append-to-body :lock-scroll="false">
      <el-form label-position="top">
        <el-form-item label="每日采集窗口（开始 ~ 结束）">
          <div class="schedule-window">
            <el-time-select v-model="scheduleForm.window_start" start="00:00" step="00:30" end="23:30" placeholder="开始" />
            <span>~</span>
            <el-time-select v-model="scheduleForm.window_end" start="00:00" step="00:30" end="23:30" placeholder="结束" />
          </div>
        </el-form-item>
        <el-form-item label="每日动态总结词上限">
          <el-input-number v-model="scheduleForm.daily_derived_limit" :min="0" :max="50" />
        </el-form-item>
        <p class="schedule-note">
          只开放采集窗口与总结词上限；请求间隔、详情间隔、风控冷却等参数由服务器固定，避免误调加剧小红书风控。保存后下发到这台 Mac，下一个采集周期生效。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="showSchedule = false">取消</el-button>
        <el-button type="primary" :loading="scheduleSaving" @click="saveSchedule">保存并下发</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showKeywordHistory" :title="`关键词历史 · ${keywordHistoryName}`" width="720px" append-to-body :lock-scroll="false">
      <div class="table table-scroll">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>波次</th>
              <th>搜索返回</th>
              <th>今日合格</th>
              <th>入库</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in keywordHistoryRuns" :key="r.id">
              <td>{{ r.run_date }}</td>
              <td>{{ ({ morning: "上午", afternoon: "下午", manual: "手动" })[r.wave] || r.wave }}</td>
              <td>{{ r.tikhub_raw_count }}</td>
              <td>{{ r.eligible_like_count }}</td>
              <td>{{ r.final_count }}</td>
              <td><em :class="r.status">{{ status(r.status) }}</em><small v-if="r.error_message" :title="r.error_message">{{ r.error_message }}</small></td>
            </tr>
            <tr v-if="!keywordHistoryRuns.length">
              <td colspan="6">近 {{ keywordHistoryDays }} 天没有执行记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </el-dialog>
  </section>
</template>
<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import QRCode from "qrcode";
import api from "@/api/api";
import { useUserStore } from "@/stores/user";
const userStore = useUserStore(),
  loading = ref(false),
  data = ref(null),
  showAdd = ref(false),
  showEdit = ref(false),
  newKeyword = reactive({ keyword: "", schedule_group: 1 }),
  editKeyword = reactive({ id: null, keyword: "" }),
  kwFilter = ref(""),
  showFailures = ref(false),
  failures = ref([]),
  showRunNotes = ref(false),
  runNotes = ref([]),
  runNotesRun = ref(null),
  runNotesTitle = ref(""),
  agentData = ref({ devices: [], batches: [] }),
  showAgentPairing = ref(false),
  pairingCode = ref(""),
  showLocalLogin = ref(false),
  localLoginCanvas = ref(null),
  localLoginQr = ref(""),
  localLoginMode = ref("login"),
  localLoginState = ref("waiting"),
  localLoginMessage = ref("等待本地节点响应…"),
  localLoginVerificationUrl = ref(""),
  localLoginCommandId = ref(""),
  imageRefreshBusy = ref(""),
  recoveryBusy = ref(""),
  recoveryResult = reactive({}),
  searchBusy = ref(""),
  analyzeBusy = ref(false),
  imageRefreshFeedback = reactive({}),
  recoveryCenter = ref(null),
  tikhubPanel = ref(null),
  expandedCall = ref(null),
  trendDays = ref(14),
  trendSeries = ref([]),
  showSchedule = ref(false),
  scheduleSaving = ref(false),
  scheduleForm = reactive({ window_start: "00:30", window_end: "23:30", daily_derived_limit: 5 }),
  showKeywordHistory = ref(false),
  keywordHistoryName = ref(""),
  keywordHistoryDays = ref(30),
  keywordHistoryRuns = ref([]);
let monitorTimer = null;
let localLoginTimer = null;
let localLoginPollFailures = 0;
let monitorDisposed = false;
let monitorRequestController = null;
let agentRequestController = null;
const requestCancelled = (error) =>
  error?.code === "ERR_CANCELED" || error?.name === "CanceledError";
const loadAgent = async () => {
  agentRequestController?.abort();
  const controller = new AbortController();
  agentRequestController = controller;
  try {
    const nextData = (
      await api.get("/admin/xhs-monitoring/agent/devices", {
        skipErrorToast: true,
        signal: controller.signal,
      })
    ).data;
    if (!monitorDisposed && agentRequestController === controller) {
      agentData.value = nextData;
    }
  } catch (error) {
    if (!monitorDisposed && !requestCancelled(error) && agentRequestController === controller) {
      agentData.value = { devices: [], batches: [] };
    }
  } finally {
    if (agentRequestController === controller) agentRequestController = null;
  }
};
const load = async () => {
  monitorRequestController?.abort();
  const controller = new AbortController();
  monitorRequestController = controller;
  loading.value = true;
  try {
    const [monitor] = await Promise.all([
      api.get("/admin/xhs-monitoring", {
        skipErrorToast: true,
        signal: controller.signal,
      }),
      loadAgent(),
    ]);
    if (!monitorDisposed && monitorRequestController === controller) {
      data.value = monitor.data;
    }
  } catch (error) {
    if (!monitorDisposed && !requestCancelled(error) && monitorRequestController === controller) {
      data.value = null;
    }
  } finally {
    if (monitorRequestController === controller) {
      monitorRequestController = null;
      loading.value = false;
    }
  }
};
const primaryAgent = computed(() => agentData.value.devices?.[0] || null);
const localDateKey = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};
const todayPlan = computed(() => {
  const plan = primaryAgent.value?.schedule?.today_plan;
  return plan?.date === localDateKey() ? plan : null;
});
const activeBatch = computed(() =>
  agentData.value.batches?.find((batch) => ["running", "paused"].includes(batch.status)) || null,
);
const latestBatchAt = computed(() => {
  const values = (agentData.value.batches || []).map((batch) => new Date(batch.last_progress_at).getTime()).filter(Number.isFinite);
  return values.length ? Math.max(...values) : 0;
});
const manualRetryWaitMinutes = computed(() => latestBatchAt.value ? Math.max(0, Math.ceil((latestBatchAt.value + 15 * 60 * 1000 - Date.now()) / 60000)) : 0);
const recentBatches = computed(() =>
  (agentData.value.batches || []).filter((batch) => batch.id !== activeBatch.value?.id).slice(0, 4),
);
const canAgentCollect = computed(() => primaryAgent.value?.connected && primaryAgent.value.cookie_status === "valid");
const batchProcessed = (batch) => (batch?.completed_keywords || 0) + (batch?.failed_keywords || 0);
const batchPercent = (batch) => batch?.total_keywords ? Math.min(100, Math.round(batchProcessed(batch) / batch.total_keywords * 100)) : 0;
const batchMode = (mode) => ({ test: "单词测试", scheduled: "定时采集", manual: "手动批量" })[mode] || mode || "采集";
const shortTime = (value) => value ? new Date(value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }) : "—";
const planSlots = computed(() => todayPlan.value?.slots || []);
const failedPlanSlots = computed(() => planSlots.value.filter((slot) => slot.status === "failed"));
const planTotal = computed(() => planSlots.value.length);
const planCompleted = computed(() => planSlots.value.filter((slot) => slot.status === "completed").length);
const planSkipped = computed(() => planSlots.value.filter((slot) => ["skipped", "stopped", "blocked"].includes(slot.status)).length);
const planPending = computed(() => planSlots.value.filter((slot) => ["pending", "running"].includes(slot.status)).length);
const runningPlanSlot = computed(() => planSlots.value.find((slot) => slot.status === "running") || null);
const hasActiveTask = computed(() => Boolean(activeBatch.value || runningPlanSlot.value));
const nextPendingSlot = computed(() => planSlots.value.find((slot) => slot.status === "pending") || null);
const planWindow = computed(() => todayPlan.value ? `${todayPlan.value.window_start}–${todayPlan.value.window_end}` : "00:30–23:30");
const riskResumeAt = computed(() => todayPlan.value?.pause_reason === "risk_cooldown" && todayPlan.value?.resume_after ? new Date(todayPlan.value.resume_after) : null);
const riskCooldownMinutes = computed(() => riskResumeAt.value ? Math.max(0, Math.ceil((riskResumeAt.value.getTime() - Date.now()) / 60000)) : 0);
const planStateLabel = computed(() => todayPlan.value?.stopped ? "今日已停止" : todayPlan.value?.risk_blocked ? "等待人工验证" : riskCooldownMinutes.value ? `风控冷却 ${riskCooldownMinutes.value} 分钟` : todayPlan.value?.paused ? "已暂停" : hasActiveTask.value ? "正在执行" : planPending.value ? "等待下一词" : "今日完成");
const slotTime = (slot) => slot?.scheduled_at?.slice(11, 16) || "—";
const slotTypeLabel = (slot) => slot?.keyword_type === "derived" ? "总结词" : "基础词";
const slotStatus = (value) => ({ pending: "待执行", running: "执行中", completed: "完成", failed: "失败", skipped: "已错过", stopped: "已停止", blocked: "风控停止", risk_blocked: "风控停止" })[value] || value;
const agentIdleTitle = computed(() => {
  if (!primaryAgent.value?.connected) return "本地节点已离线";
  if (primaryAgent.value.cookie_status === "verification_required") return "需要重新验证本地账号";
  if (todayPlan.value?.stopped) return "今日计划已经停止";
  if (riskCooldownMinutes.value) return `风控冷却中，约 ${riskCooldownMinutes.value} 分钟后自动续跑`;
  if (todayPlan.value?.paused) return "今日计划已暂停";
  if (nextPendingSlot.value) return `等待 ${slotTime(nextPendingSlot.value)} · ${nextPendingSlot.value.keyword}`;
  return "今日计划已执行完毕";
});
const agentIdleDescription = computed(() => {
  if (!primaryAgent.value?.connected) return "请保持这台 Mac 开机并检查 Agent 运行状态。";
  if (primaryAgent.value.cookie_status === "verification_required") return "完成扫码或人机验证后才能重新采集。";
  if (riskCooldownMinutes.value) return "Cookie 已更新，但账号/IP 风控不会立即消失，冷却结束后系统会自动恢复。";
  if (!todayPlan.value) return "本地节点正在生成今天的分散采集时间表。";
  return "全天自动分散执行，不需要手动启动整组。";
});
const agentCookieLabel = (value) =>
  ({ valid: "正常", expired: "已失效", missing: "未登录", verification_required: "需要验证", unknown: "待检测" })[value] || value;
const agentStatus = (value) =>
  ({ online: "空闲", idle: "空闲", running: "执行中", paused: "已暂停", risk_blocked: "风控停止", needs_login: "需要登录", offline: "离线", revoked: "已撤销" })[value] || value || "—";
const failureGuide = (slot) => {
  const error = String(slot?.error || "").toLowerCase();
  if (/captcha|verification|验证码|461|471|风控/.test(error)) return {
    title: `${slot.keyword} 触发小红书验证`,
    cause: "小红书要求当前账号完成人机验证，系统已经停止继续请求。",
    solution: "打开人工验证，完成后再重新执行这个词。",
    action: "login",
  };
  if (/cookie|登录|授权|expired/.test(error)) return {
    title: `${slot.keyword} 登录状态失效`,
    cause: "本地 Cookie 已失效，继续请求不会成功。",
    solution: "重新扫码登录，Cookie 恢复正常后再执行。",
    action: "login",
  };
  if (/agent|502|timeout|timed out|network|connect|连接|握手|中断/.test(error)) return {
    title: `${slot.keyword} 通信中断`,
    cause: "本地 Agent 与服务器通信异常，原任务没有完整结束；这不是小红书搜索耗时。",
    solution: "节点在线且 Cookie 正常时，可以安全地只重试这个失败词。",
    action: "retry",
  };
  return {
    title: `${slot.keyword} 采集失败`,
    cause: slot?.error || "CLI 没有正常完成本次采集。",
    solution: "先重试一次；若再次失败，页面会保留新的具体错误。",
    action: "retry",
  };
};
const recoveryItems = computed(() => {
  const items = [];
  for (const slot of failedPlanSlots.value) {
    const guide = failureGuide(slot);
    items.push({ key: `slot-${slot.keyword_id}`, level: "warning", label: `${slotTime(slot)} · 失败词`, slot, ...guide });
  }
  return items;
});
// 顶部「现在正常吗」横幅：把散落的连接/计划/冷却状态收敛成一个结论。
const healthTone = computed(() => {
  if (!primaryAgent.value || !primaryAgent.value.connected) return "bad";
  if (primaryAgent.value.cookie_status === "verification_required") return "warn";
  if (failedPlanSlots.value.length) return "warn";
  return "good";
});
const healthTitle = computed(() => {
  if (!primaryAgent.value) return "尚未绑定本地采集节点";
  if (!primaryAgent.value.connected) return "本地采集节点离线";
  if (primaryAgent.value.cookie_status === "verification_required") return "账号需要人机验证";
  if (riskCooldownMinutes.value) return `风控冷却中，约 ${riskCooldownMinutes.value} 分钟后自动续跑`;
  if (activeBatch.value) return `正在采集「${activeBatch.value.current_keyword || primaryAgent.value.current_keyword || "…"}」`;
  if (failedPlanSlots.value.length) return `今日有 ${failedPlanSlots.value.length} 个关键词待处理`;
  if (planPending.value) return "运行正常，等待下一个关键词";
  return "今日采集已完成";
});
const healthSubtitle = computed(() => {
  if (!primaryAgent.value) return "绑定一台 Mac 后，这里会显示实时采集状态。";
  if (!primaryAgent.value.connected) return "服务器无法下发任务，请确认 Mac 开机联网。";
  if (primaryAgent.value.cookie_status === "verification_required") return "完成人机验证或重新登录后即可恢复。";
  if (todayPlan.value?.stopped) return "今日计划已停止，明天会自动生成新计划。";
  if (activeBatch.value) return `已处理 ${batchProcessed(activeBatch.value)} / ${activeBatch.value.total_keywords} 个关键词`;
  return `今日进度 ${planCompleted.value}/${planTotal.value} · 跳过 ${planSkipped.value} · 剩余 ${planPending.value}`;
});
const scrollToRecovery = () => recoveryCenter.value?.scrollIntoView({ behavior: "smooth", block: "start" });
const scrollToTikhub = () => tikhubPanel.value?.scrollIntoView({ behavior: "smooth", block: "start" });
// 采集策略（只放开窗口与总结词上限；风控参数服务器固定）
const openSchedule = () => {
  const s = primaryAgent.value?.schedule || {};
  scheduleForm.window_start = s.window_start || "00:30";
  scheduleForm.window_end = s.window_end || "23:30";
  scheduleForm.daily_derived_limit = s.daily_derived_limit ?? 5;
  showSchedule.value = true;
};
const saveSchedule = async () => {
  if (!primaryAgent.value) return;
  if (scheduleForm.window_start >= scheduleForm.window_end) return ElMessage.warning("采集开始时间必须早于结束时间");
  scheduleSaving.value = true;
  try {
    await api.put(`/admin/xhs-monitoring/agent/devices/${primaryAgent.value.id}/schedule`, {
      window_start: scheduleForm.window_start,
      window_end: scheduleForm.window_end,
      daily_derived_limit: scheduleForm.daily_derived_limit,
    });
    showSchedule.value = false;
    ElMessage.success("采集策略已下发到这台 Mac，下一个采集周期生效");
    await loadAgent();
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || "保存采集策略失败");
  } finally {
    scheduleSaving.value = false;
  }
};
// 历史趋势（按天聚合，数据来自已落库的 runs / provider calls）
const loadTrends = async () => {
  try {
    trendSeries.value = (
      await api.get("/admin/xhs-monitoring/stats/daily", { params: { days: trendDays.value }, skipErrorToast: true })
    ).data.series || [];
  } catch { trendSeries.value = []; }
};
const setTrendDays = (d) => { trendDays.value = d; loadTrends(); };
// 把 [0..1] 归一化后的序列映射成 100x40 的 SVG polyline 点。
const sparkline = (values) => {
  const nums = values.filter((v) => v != null);
  if (!nums.length) return "";
  const max = Math.max(...nums, 1), n = values.length;
  return values.map((v, i) => {
    const x = n > 1 ? (i / (n - 1)) * 100 : 50;
    const y = 38 - ((v || 0) / max) * 34;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
};
const trendPaths = computed(() => ({
  success: sparkline(trendSeries.value.map((d) => (d.success_rate == null ? null : Math.round(d.success_rate * 100)))),
  notes: sparkline(trendSeries.value.map((d) => d.notes_collected || 0)),
  captcha: sparkline(trendSeries.value.map((d) => d.captcha_events || 0)),
}));
// ── TikHub 付费通道 ──
const tikhub = computed(() => data.value?.tikhub || null);
const quotaPercent = (today) => (today?.limit ? Math.min(100, Math.round((today.used / today.limit) * 100)) : 0);
const tikhubCostSparkline = computed(() => sparkline((tikhub.value?.daily_cost_7d || []).map((d) => d.cost || 0)));
const tikhubCostSummary = computed(() => {
  const days = tikhub.value?.daily_cost_7d || [];
  const total = days.reduce((a, d) => a + (d.cost || 0), 0);
  const calls = days.reduce((a, d) => a + (d.calls || 0), 0);
  return `7 天 ¥${total.toFixed(2)} · ${calls} 次`;
});
const tikhubCalls = computed(() => (data.value?.calls || []).filter((c) => c.provider === "tikhub"));
const opLabel = (op) => ({ search: "搜索", detail: "详情补全", image_refresh: "图片刷新", agent_upload: "本地上报" })[op] || op || "—";
const toggleCallExpand = (id) => { expandedCall.value = expandedCall.value === id ? null : id; };
const openQuotaEditor = async () => {
  const current = tikhub.value?.today?.limit ?? 100;
  try {
    const { value } = await ElMessageBox.prompt(
      `当前每日上限 ${current} 次。提高额度会增加今日 TikHub 付费上限,立即生效(仅当天)。`,
      "调整 TikHub 每日额度",
      {
        confirmButtonText: "确认调整",
        cancelButtonText: "取消",
        inputValue: String(current),
        inputPattern: /^([1-9]\d{0,3}|10000)$/,
        inputErrorMessage: "请输入 1–10000 的整数",
        lockScroll: false,
      },
    );
    const limit = parseInt(value, 10);
    await api.post("/admin/xhs-monitoring/tikhub-quota", { limit_count: limit });
    ElMessage.success(`每日额度已调整为 ${limit} 次`);
    await load();
  } catch (error) {
    if (error !== "cancel" && error?.action !== "cancel") {
      ElMessage.error(error?.response?.data?.detail || "调整额度失败");
    }
  }
};
const trendSummary = computed(() => {
  const s = trendSeries.value;
  const runs = s.reduce((a, d) => a + (d.runs || 0), 0);
  const ok = s.reduce((a, d) => a + (d.succeeded || 0), 0);
  return {
    success: runs ? `平均 ${Math.round((ok / runs) * 100)}%` : "暂无数据",
    notes: `共 ${s.reduce((a, d) => a + (d.notes_collected || 0), 0)} 篇`,
    captcha: `共 ${s.reduce((a, d) => a + (d.captcha_events || 0), 0)} 次`,
  };
});
// 单关键词历史下钻
const openKeywordHistory = async (k) => {
  showKeywordHistory.value = true;
  keywordHistoryName.value = k.keyword;
  keywordHistoryRuns.value = [];
  try {
    keywordHistoryRuns.value = (
      await api.get(`/admin/xhs-monitoring/keywords/${k.id}/runs`, { params: { days: keywordHistoryDays.value } })
    ).data.runs || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || "读取关键词历史失败");
  }
};
const createAgentPairing = async () => {
  showAgentPairing.value = true;
  pairingCode.value = "";
  try {
    pairingCode.value = (
      await api.post("/admin/xhs-monitoring/agent/pairings")
    ).data.code;
  } catch (error) {
    showAgentPairing.value = false;
    ElMessage.error(error?.response?.data?.detail || "生成绑定码失败");
  }
};
const sendAgentCommand = async (commandType, extra = {}) => {
  if (!primaryAgent.value?.connected) {
    ElMessage.warning("本地采集节点当前离线");
    return null;
  }
  if (commandType === "test_keyword" && primaryAgent.value.cookie_status !== "valid") {
    ElMessage.warning("请先重新扫码或完成小红书人机验证");
    return null;
  }
  const response = await api.post("/admin/xhs-monitoring/agent/commands", {
    device_id: primaryAgent.value.id,
    command_type: commandType,
    ...extra,
  });
  ElMessage.success("命令已发送到这台 Mac");
  window.setTimeout(() => load(), 900);
  return response.data;
};
const stopTodayPlan = async () => {
  await ElMessageBox.confirm(
    "停止后，今天剩余关键词都会跳过，明天才会自动生成新计划。",
    "停止今日采集计划？",
    { confirmButtonText: "停止今天", cancelButtonText: "取消", type: "warning", lockScroll: false },
  );
  await sendAgentCommand("stop");
};
const confirmCooldownOverride = async () => {
  if (!manualRetryWaitMinutes.value) return false;
  if (!userStore.isSuperAdmin) {
    ElMessage.warning(`请等待 ${manualRetryWaitMinutes.value} 分钟后再试`);
    return null;
  }
  try {
    await ElMessageBox.confirm(
      `当前仍在 15 分钟安全冷却期内，跳过可能增加验证码或风控概率。`,
      "确认立即搜索？",
      { confirmButtonText: "跳过冷却", cancelButtonText: "继续等待", type: "warning", lockScroll: false },
    );
    return true;
  } catch {
    return null;
  }
};
const testKeywordWithAgent = async (keywordId) => {
  const force = await confirmCooldownOverride();
  if (force === null) return;
  await sendAgentCommand("test_keyword", { keyword_id: keywordId, force });
};
const waitForRecovery = async (commandId, itemKey) => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 3000));
    const command = (await api.get(`/admin/xhs-monitoring/agent/commands/${commandId}`, { skipErrorToast: true })).data;
    if (command.status === "succeeded") {
      if (command.result?.failed) throw new Error(command.result.error || "CLI 仍未完成采集");
      recoveryResult[itemKey] = "处理成功：该词已完成，时间轴状态已经同步。";
      ElMessage.success("失败词已恢复并完成");
      await load();
      return;
    }
    if (["failed", "cancelled"].includes(command.status)) throw new Error(command.error || "恢复命令执行失败");
  }
  throw new Error("等待恢复结果超时，请重新检测状态");
};
const retryFailedSlot = async (slot) => {
  const itemKey = `slot-${slot.keyword_id}`;
  recoveryBusy.value = itemKey;
  recoveryResult[itemKey] = "已发送到本地 Mac，正在等待采集结果…";
  try {
    const force = await confirmCooldownOverride();
    if (force === null) return;
    const command = await sendAgentCommand("test_keyword", { keyword_id: slot.keyword_id, force });
    if (!command?.command_id) throw new Error("恢复命令没有成功创建");
    await waitForRecovery(command.command_id, itemKey);
  } catch (error) {
    const message = error?.response?.data?.detail || error?.message || "重新执行失败";
    recoveryResult[itemKey] = `处理失败：${message}`;
    ElMessage.error(message);
    await load();
  } finally {
    recoveryBusy.value = "";
  }
};
const stopLocalLoginPoll = () => {
  if (localLoginTimer) window.clearTimeout(localLoginTimer);
  localLoginTimer = null;
};
const pollLocalLogin = async () => {
  if (monitorDisposed) return;
  const commandId = localLoginCommandId.value;
  if (!commandId) return;
  try {
    const command = (
      await api.get(
        `/admin/xhs-monitoring/agent/commands/${commandId}`,
        { skipErrorToast: true },
      )
    ).data;
    if (commandId !== localLoginCommandId.value) return;
    localLoginPollFailures = 0;
    const result = command.result || {};
    localLoginState.value = result.status || command.status;
    localLoginMessage.value = result.message || (
      result.status === "authenticated"
        ? "本地授权成功"
        : result.status === "scanned"
          ? "已扫码，请在手机上确认"
          : result.status === "waiting" && result.qr_url
            ? "等待扫码…"
            : localLoginMode.value === "verify_session"
              ? "正在检查当前 Cookie…"
              : localLoginMode.value === "browser_login"
                ? "正在读取本机浏览器 Cookie…"
                : "正在让本地 Mac 生成二维码…"
    );
    localLoginVerificationUrl.value = result.verification_url || "";
    if (result.qr_url && result.qr_url !== localLoginQr.value) {
      localLoginQr.value = result.qr_url;
      await nextTick();
      await QRCode.toCanvas(localLoginCanvas.value, result.qr_url, { width: 240, margin: 1 });
    }
    if (["succeeded", "failed", "cancelled"].includes(command.status)) {
      if (command.status === "succeeded" && result.status === "verification_required") {
        localLoginState.value = "verification_required";
        localLoginMessage.value = result.message || "请完成小红书人机验证";
      } else if (command.status === "succeeded" && result.status === "expired") {
        localLoginState.value = "expired";
        localLoginMessage.value = result.message || "当前 Cookie 已失效，请重新登录";
      } else if (command.status === "succeeded") {
        if (result.status === "authenticated") {
          ElMessage.success(result.message || "本地 Cookie 已恢复");
          showLocalLogin.value = false;
        } else {
          localLoginState.value = "failed";
          localLoginMessage.value = result.message || "本地登录没有完成";
        }
      } else if (command.status === "cancelled") {
        localLoginState.value = "cancelled";
        localLoginMessage.value = result.message || "已切换登录方式";
      } else {
        localLoginState.value = "failed";
        localLoginMessage.value = command.error || "本地扫码登录失败";
      }
      stopLocalLoginPoll();
      await loadAgent();
      return;
    }
    if (!monitorDisposed) localLoginTimer = window.setTimeout(pollLocalLogin, 2000);
  } catch {
    if (commandId !== localLoginCommandId.value) return;
    localLoginPollFailures += 1;
    if (localLoginPollFailures <= 5 && showLocalLogin.value) {
      localLoginMessage.value = `与服务器通信短暂中断，正在自动重试（${localLoginPollFailures}/5）…`;
      if (!monitorDisposed) localLoginTimer = window.setTimeout(pollLocalLogin, Math.min(5000, 1000 * localLoginPollFailures));
    } else {
      localLoginState.value = "failed";
      localLoginMessage.value = "连续无法读取登录状态，请检查网络后重试";
      stopLocalLoginPoll();
    }
  }
};
const startLocalAuth = async (commandType) => {
  if (!primaryAgent.value?.connected) return ElMessage.warning("本地采集节点当前离线");
  stopLocalLoginPoll();
  localLoginPollFailures = 0;
  showLocalLogin.value = true;
  localLoginMode.value = commandType;
  localLoginQr.value = "";
  localLoginState.value = "waiting";
  localLoginCommandId.value = "";
  localLoginMessage.value = commandType === "verify_session"
    ? "正在检查当前 Cookie 的人机验证结果…"
    : commandType === "browser_login"
      ? "正在读取本机浏览器的小红书 Cookie…"
      : "正在让本地 Mac 生成二维码…";
  if (commandType !== "verify_session") localLoginVerificationUrl.value = "";
  try {
    const response = await api.post("/admin/xhs-monitoring/agent/commands", {
      device_id: primaryAgent.value.id,
      command_type: commandType,
    });
    localLoginCommandId.value = response.data.command_id;
    localLoginTimer = window.setTimeout(pollLocalLogin, 800);
  } catch (error) {
    localLoginState.value = "failed";
    localLoginMessage.value = error?.response?.data?.detail || "本地验证命令创建失败";
  }
};
const startLocalLogin = () => startLocalAuth("login");
const startLocalBrowserLogin = () => startLocalAuth("browser_login");
const openAgentVerification = () => {
  const verificationUrl = todayPlan.value?.verification_url;
  if (!verificationUrl) return startLocalLogin();
  stopLocalLoginPoll();
  showLocalLogin.value = true;
  localLoginMode.value = "verify_session";
  localLoginQr.value = "";
  localLoginState.value = "verification_required";
  localLoginMessage.value = "请先在新页面完成小红书人机验证";
  localLoginVerificationUrl.value = verificationUrl;
};
const confirmRiskVerification = () => startLocalAuth("verify_session");
const runRows = computed(() => data.value?.runs || []);
const filteredKeywords = computed(() => {
  const q = kwFilter.value.trim().toLowerCase(),
    list = data.value?.keywords || [];
  return q ? list.filter((k) => k.keyword.toLowerCase().includes(q)) : list;
});
const enabledBaseCount = computed(() => (data.value?.keywords || []).filter((item) => item.enabled && item.type === "base").length);
const enabledDerivedCount = computed(() => (data.value?.keywords || []).filter((item) => item.enabled && item.type === "derived").length);
const percent = (a, b) => (b ? Math.round((a / b) * 100) : 0);
const time = (v) =>
  v ? new Date(v).toLocaleString("zh-CN", { hour12: false }) : "—";
const labels = {
  pending: "待执行",
  running: "执行中",
  completed: "完成",
  partial: "部分异常",
  success: "成功",
  failed: "失败",
  cooldown: "曾触发验证码",
  risk_blocked: "风控停止",
  stopped: "已停止",
  blocked: "已阻断",
  blocked_budget: "额度阻断",
  skipped: "免费跳过",
  skipped_free: "免费跳过",
};
const status = (s) => labels[s] || s || "—";
const callError = (call) => ({
  AgentVerificationRequired: "需重新扫码 / 人机验证",
  AgentCollectionError: "本地采集失败",
})[call.error_code] || call.error_code || "—";
const reasons = {
  invalid_payload: "无法解析",
  old: "超过 7 天",
  unknown_date: "发布时间未知",
  low_like: "未达到所在层级点赞门槛",
  unknown_metric: "指标未知",
  unknown_type: "类型未知",
  core_incomplete: "核心详情缺失",
  rank_overflow: "历史版本数量截断",
  rank: "历史版本数量截断",
};
const reason = (k) => reasons[k] || k;
const searchParseLabel = (row) =>
  row.run_source === "local_agent" && !row.has_search_diagnostics
    ? `未知 / 已上传 ${row.merged_count}`
    : `${row.cli_raw_count} / ${row.merged_count}`;
const levelStat = (row, level, field) => row?.level_stats?.[level]?.[field] ?? "—";
const searchRouteLabel = (row) => {
  const sorts = (row?.searches || []).map((item) => item.sort).filter(Boolean);
  return sorts.length ? sorts.join(" + ") : "历史批次";
};
const filterResultLabel = (row) =>
  row.run_source === "local_agent" && !row.has_search_diagnostics
    ? `未知 / 未知 / ${row.displayable_count}`
    : `${levelStat(row, "daily", "eligible_count")} / ${levelStat(row, "weekly", "eligible_count")} / ${row.displayable_count}`;
const diagnosticRejections = computed(() =>
  Object.entries(runNotesRun.value?.rejection_counts || {})
    .filter(([key, count]) => !key.startsWith("_") && Number(count) > 0)
    .map(([key, count]) => ({ key, count })),
);
const runDiagnosticSummary = (run) => {
  if (run.search_state === "unrecognized")
    return "小红书返回了无法识别的响应，本次不能判定为 0 条，请检查 CLI 或重新登录。";
  if (run.cli_raw_count === 0) return "小红书搜索页本次真实返回 0 条。";
  if (run.displayable_count === 0)
    return `搜索页返回 ${run.cli_raw_count} 条，但结果均在解析、时间、点赞或详情规则中被过滤。`;
  const initialEligible =
    Number(levelStat(run, "daily", "eligible_count") || 0) +
    Number(levelStat(run, "weekly", "eligible_count") || 0);
  return `搜索页初筛 ${initialEligible} 条进入详情，详情复核后入库 ${run.displayable_count} 条；详情页的真实发布时间和点赞会覆盖搜索卡片初值。`;
};
const emptyRunNotesMessage = computed(() => {
  const run = runNotesRun.value;
  if (!run) return "正在读取抓取明细…";
  if (!run.has_search_diagnostics)
    return "这次历史运行没有记录原始搜索漏斗，不能判定为搜索结果 0 条。";
  if (run.search_state === "unrecognized")
    return "搜索响应无法解析，不能判定为搜索结果 0 条。";
  if (run.cli_raw_count === 0) return "小红书搜索页本次真实返回 0 条。";
  return `搜索页返回 ${run.cli_raw_count} 条，但没有笔记通过完整入库规则；请查看上方淘汰原因。`;
});
const toggle = async (k) => {
  await api.patch(`/admin/xhs-monitoring/keywords/${k.id}/enabled`, null, {
    params: { enabled: !k.enabled },
  });
  load();
};
const lifecycleLabel = (k) => ({ candidate: "候选中", trial: "试采中", active: "启用中", quarantined: "已隔离" })[k.lifecycle_status] || (k.enabled ? "启用中" : "已停用");
const pinKeyword = async (k) => { await api.patch(`/admin/xhs-monitoring/keywords/${k.id}/pin`,null,{params:{pinned:!k.pinned}});ElMessage.success(k.pinned ? "已取消置顶" : "已置顶");load() };
const restoreKeyword = async (k) => { await api.post(`/admin/xhs-monitoring/keywords/${k.id}/restore`);ElMessage.success("已恢复为试采关键词");load() };
const promote = async (k) => {
  await api.post(`/admin/xhs-monitoring/keywords/${k.id}/promote`);
  ElMessage.success("已提升为基础词");
  load();
};
const waitForKeywordRun = async (keywordId) => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 3000));
    const runs = (
      await api.get(`/admin/xhs-monitoring/keywords/${keywordId}/runs`, { params: { days: 1 }, skipErrorToast: true })
    ).data.runs || [];
    const latest = runs[0];
    if (!latest || latest.status === "running") continue;
    await load();
    if (latest.status === "failed") throw new Error(latest.error_message || "采集失败");
    ElMessage.success(
      latest.status === "partial"
        ? `部分完成，入库 ${latest.final_count || 0} 篇`
        : `采集完成，入库 ${latest.final_count || 0} 篇`,
    );
    return;
  }
  throw new Error("等待采集结果超时，请稍后刷新查看");
};
const searchNow = async (k) => {
  if (!userStore.isSuperAdmin) return ElMessage.warning("仅最高管理员可用");
  let timeFilter;
  try {
    // confirm=一周内(7天)；cancel(非关闭)=一天内(24h)；点 X 关闭=放弃
    const action = await ElMessageBox.confirm(
      `将对「${k.keyword}」通过 TikHub 付费接口实时采集，会产生费用。请选择采集时间范围。`,
      "确认立即搜索？",
      {
        confirmButtonText: "近一周",
        cancelButtonText: "近 24 小时",
        distinguishCancelAndClose: true,
        showCancelButton: true,
        type: "warning",
        lockScroll: false,
      },
    );
    timeFilter = action === "confirm" ? "一周内" : "一天内";
  } catch (action) {
    if (action === "cancel") timeFilter = "一天内";
    else return; // close = 放弃
  }
  searchBusy.value = `kw-${k.id}`;
  try {
    await api.post(`/admin/xhs-monitoring/keywords/${k.id}/retry-paid`, null, { params: { time_filter: timeFilter } });
    ElMessage.success(`已提交 TikHub 付费采集（${timeFilter === "一天内" ? "近 24 小时" : "近一周"}），正在等待结果…`);
    await waitForKeywordRun(k.id);
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.message || "立即搜索失败");
  } finally {
    searchBusy.value = "";
  }
};
const analyzeNow = async () => {
  if (!userStore.isSuperAdmin) return ElMessage.warning("仅最高管理员可用");
  try {
    await ElMessageBox.confirm(
      "将对全部素材重建「今日热榜 + 持续发酵」话题分析。",
      "确认立即分析？",
      { confirmButtonText: "立即分析", cancelButtonText: "取消", type: "warning", lockScroll: false },
    );
  } catch {
    return;
  }
  analyzeBusy.value = true;
  try {
    await api.post("/admin/xhs-monitoring/analyze-topics");
    ElMessage.success("已提交全局话题分析，稍候刷新看板查看结果");
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.message || "立即分析失败");
  } finally {
    analyzeBusy.value = false;
  }
};
const removeKeyword = async (k) => {
  await ElMessageBox.confirm(
    `删除「${k.keyword}」？其执行记录与素材关联将一并删除（已入库素材保留），且不可恢复。`,
    "确认删除",
    { type: "warning", lockScroll: false },
  );
  await api.delete(`/admin/xhs-monitoring/keywords/${k.id}`);
  ElMessage.success("已删除");
  load();
};
const refresh = async () => {
  await load();
  ElMessage.success("监测数据已刷新");
};
const funnelStages = computed(() => {
  const f = data.value?.funnel || {},
    pct = (a, b) => (b ? `${Math.round((a / b) * 100)}%` : null),
    raw = (f.tikhub_raw_count || 0),
    parsedOut = Math.max(0, raw - (f.merged_count || 0));
  return [
    {
      label: "搜索页返回",
      value: raw,
      note: "TikHub 付费采集",
    },
    {
      label: "解析并去重",
      value: f.merged_count || 0,
      conv: pct(f.merged_count, raw),
      note: parsedOut ? `排除重复或无效 ${parsedOut}` : "已按 note_id 去重",
    },
    {
      label: "点赞门槛合格",
      value: f.eligible_like_count || 0,
      conv: pct(f.eligible_like_count, f.merged_count),
      note: "近 24h >200 · 1–7 天 >2000",
    },
    {
      label: "完整入库",
      value: f.final_count || 0,
      conv: pct(f.final_count, f.eligible_like_count),
      note: "标题、正文、作者与封面完整",
    },
    {
      label: "今日新增素材",
      value: f.unique_ingested_today_count || 0,
      note: `当前可展示：24h ${f.current_daily_displayable_count || 0} · 7 天 ${f.current_displayable_count || 0}`,
    },
  ];
});
const openFailures = async () => {
  showFailures.value = true;
  failures.value = (
    await api.get("/admin/xhs-monitoring/image-failures")
  ).data.reports;
};
const resolveFailure = async (r) => {
  await api.post(`/admin/xhs-monitoring/image-failures/${r.id}/resolve`);
  ElMessage.success("已标记处理");
  openFailures();
  load();
};
const refreshImage = async (r) => {
  if (!primaryAgent.value?.connected) return ElMessage.warning("本地采集节点当前离线");
  if (primaryAgent.value.cookie_status !== "valid") return ElMessage.warning("请先完成本地节点扫码登录");
  imageRefreshBusy.value = r.note_id;
  imageRefreshFeedback[r.note_id] = "正在发送到本地 Mac，通常 10–30 秒…";
  try {
    const response = await api.post("/admin/xhs-monitoring/agent/commands", {
      device_id: primaryAgent.value.id,
      command_type: "refresh_image",
      note_id: r.note_id,
    });
    const commandId = response.data.command_id;
    imageRefreshFeedback[r.note_id] = "本地 Mac 正在读取小红书笔记…";
    for (let attempt = 0; attempt < 75; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const command = (await api.get(`/admin/xhs-monitoring/agent/commands/${commandId}`, { skipErrorToast: true })).data;
      if (command.status === "succeeded") {
        imageRefreshFeedback[r.note_id] = "刷新成功，封面已缓存";
        ElMessage.success("封面已刷新并开始本地缓存");
        await Promise.all([openFailures(), load()]);
        return;
      }
      if (["failed", "cancelled"].includes(command.status)) throw new Error(command.error || "图片刷新失败");
    }
    throw new Error("图片刷新超时，请稍后查看失败报告");
  } catch (error) {
    const message = error?.response?.data?.detail || error?.message || "图片刷新失败";
    imageRefreshFeedback[r.note_id] = `刷新失败：${message}`;
    ElMessage.error(message);
  } finally {
    imageRefreshBusy.value = "";
  }
};
const noteStatus = (s) =>
  ["ready", "ready_degraded", "synced"].includes(s)
    ? "入库"
    : s && s.startsWith("rejected_")
      ? reason(s.slice(9))
      : s || "—";
const openRunNotes = async (row) => {
  showRunNotes.value = true;
  runNotesTitle.value = row.keyword;
  runNotes.value = [];
  runNotesRun.value = null;
  const response = await api.get(`/admin/xhs-monitoring/runs/${row.id}/notes`);
  runNotes.value = response.data.notes;
  runNotesRun.value = response.data.run;
};
const addKeyword = async () => {
  if (!newKeyword.keyword.trim()) return;
  await api.post("/admin/xhs-monitoring/keywords", newKeyword);
  showAdd.value = false;
  newKeyword.keyword = "";
  ElMessage.success("基础词已新增");
  load();
};
const openEdit = (k) => {
  editKeyword.id = k.id;
  editKeyword.keyword = k.keyword;
  showEdit.value = true;
};
const saveEdit = async () => {
  const kw = editKeyword.keyword.trim();
  if (!kw) return;
  await api.patch(`/admin/xhs-monitoring/keywords/${editKeyword.id}`, {
    keyword: kw,
  });
  showEdit.value = false;
  ElMessage.success("关键词已修改");
  load();
};
const stopMonitorRefresh = () => {
  if (monitorTimer) window.clearTimeout(monitorTimer);
  monitorTimer = null;
};
const scheduleMonitorRefresh = () => {
  stopMonitorRefresh();
  if (monitorDisposed || document.visibilityState !== "visible") return;
  monitorTimer = window.setTimeout(async () => {
    monitorTimer = null;
    if (monitorDisposed || document.visibilityState !== "visible") return;
    if (activeBatch.value) await load();
    else await loadAgent();
    if (monitorDisposed) return;
    scheduleMonitorRefresh();
  }, activeBatch.value ? 15000 : 60000);
};
const handleVisibilityChange = () => {
  if (document.visibilityState !== "visible") {
    stopMonitorRefresh();
    return;
  }
  loadAgent();
  scheduleMonitorRefresh();
};
onMounted(() => {
  monitorDisposed = false;
  load();
  loadTrends();
  scheduleMonitorRefresh();
  document.addEventListener("visibilitychange", handleVisibilityChange);
});
onBeforeUnmount(() => {
  monitorDisposed = true;
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  stopMonitorRefresh();
  monitorRequestController?.abort();
  agentRequestController?.abort();
  stopLocalLoginPoll();
});
</script>
<style scoped>
.monitor {
  max-width: 1560px;
  margin: auto;
}
.monitor > header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.kicker {
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--clay-deep);
  font-weight: 700;
}
.monitor h1 {
  font: 700 36px var(--serif);
  margin: 4px 0;
}
.monitor header p,
.panel-head p {
  color: var(--ink-3);
  margin: 0;
}
.refresh,
.panel-head button {
  border: 0;
  background: var(--ink);
  color: white;
  border-radius: 9px;
  padding: 10px 14px;
}
.agent-panel { background: linear-gradient(145deg, var(--paper) 0%, #f3f6f1 100%); }
.agent-head-actions { display: flex; align-items: center; gap: 8px; }
.agent-head-actions button.quiet { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.72); color: var(--ink-2); padding: 7px 11px; cursor: pointer; }
.connection-badge { display: inline-flex; align-items: center; gap: 6px; border-radius: 99px; padding: 6px 10px; font-size: 11px; font-weight: 700; }
.connection-badge::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.connection-badge.online { color: var(--pine); background: #e4eee9; }
.connection-badge.offline { color: var(--clay-deep); background: var(--clay-tint); }
.active-task { display: grid; grid-template-columns: minmax(0, 1fr) 230px; gap: 28px; align-items: center; min-height: 132px; padding: 22px 24px; border-radius: 14px; color: #fff; background: linear-gradient(125deg, #244f43, #35695a); box-shadow: 0 12px 28px rgba(36, 79, 67, .14); }
.active-task.idle { color: var(--ink); background: rgba(255, 255, 255, .72); border: 1px solid var(--line); box-shadow: none; }
.active-task.blocked { color: #71351f; background: #fff1e6; border-color: #e6b397; }
.task-label { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; opacity: .88; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #d6f3df; box-shadow: 0 0 0 5px rgba(214, 243, 223, .12); }
.active-task.idle .status-dot { background: var(--pine); box-shadow: 0 0 0 5px rgba(46, 93, 80, .09); }
.active-task.blocked .status-dot { background: var(--clay-deep); box-shadow: 0 0 0 5px rgba(169, 79, 67, .09); }
.auto-refresh { margin-left: 4px; padding-left: 11px; border-left: 1px solid rgba(255,255,255,.35); font-weight: 400; letter-spacing: 0; text-transform: none; }
.active-task h3 { margin: 0; font: 700 27px var(--serif); }
.active-task p { margin: 7px 0 0; font-size: 12px; opacity: .78; }
.phase-hint { display: block; margin-top: 5px; font-size: 10px; }
.task-progress-card,
.task-ready-card { padding: 15px 17px; border: 1px solid rgba(255,255,255,.22); border-radius: 11px; background: rgba(255,255,255,.1); }
.task-progress-card strong,
.task-ready-card strong { display: block; font: 700 27px var(--serif); }
.task-progress-card span,
.task-ready-card small { display: block; margin-top: 3px; font-size: 11px; opacity: .76; }
.task-progress-card i { display: block; height: 6px; margin-top: 12px; overflow: hidden; border-radius: 99px; background: rgba(255,255,255,.2); }
.task-progress-card i b { display: block; height: 100%; border-radius: inherit; background: #d6f3df; transition: width .3s ease; }
.active-task.idle .task-ready-card { border-color: var(--line); background: var(--ivory); }
.agent-facts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; margin-top: 10px; }
.agent-facts > div { min-width: 0; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; background: rgba(255,255,255,.56); }
.agent-facts small,
.agent-facts span { display: block; color: var(--ink-3); font-size: 10px; }
.agent-facts strong { display: block; margin: 3px 0; overflow: hidden; color: var(--ink-2); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.agent-risk-alert { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin: 0 0 12px; padding: 12px 14px; border: 1px solid #d79a78; border-radius: 10px; background: #fff2e8; color: #8b3f24; }
.agent-risk-alert strong,
.agent-risk-alert span { display: block; }
.agent-risk-alert span { margin-top: 3px; font-size: 12px; }
.agent-risk-alert button { flex: none; border: 0; border-radius: 8px; padding: 8px 11px; color: white; background: var(--clay-deep); cursor: pointer; }
.risk-actions { display: flex; justify-content: flex-end; gap: 7px; flex-wrap: wrap; }
.agent-risk-alert button.secondary { border: 1px solid #c98969; color: #8b3f24; background: transparent; }
.agent-empty { padding: 16px; margin: 12px 0; border: 1px dashed var(--line); border-radius: 10px; color: var(--ink-3); }
.agent-empty p { margin-bottom: 0; }
.daily-plan { margin-top: 14px; padding: 14px; border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,.68); }
.daily-plan-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.daily-plan-head strong,
.daily-plan-head span { display: block; }
.daily-plan-head strong { font-size: 13px; }
.daily-plan-head span { margin-top: 3px; color: var(--ink-3); font-size: 10px; }
.daily-plan-head em { flex: none; padding: 5px 9px; border-radius: 99px; color: var(--pine); background: #e4eee9; font-size: 10px; font-style: normal; font-weight: 700; }
.daily-plan-head em.paused { color: #8d632b; background: #f8ead6; }
.daily-plan-head em.stopped { color: var(--clay-deep); background: var(--clay-tint); }
.plan-track { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 6px; max-height: 190px; margin-top: 12px; overflow-y: auto; scrollbar-width: thin; }
.plan-slot { display: grid; grid-template-columns: auto 1fr; gap: 2px 8px; min-width: 0; padding: 8px 9px; border: 1px solid transparent; border-radius: 8px; background: var(--ivory); }
.plan-slot time { color: var(--ink-3); font: 700 10px ui-monospace, monospace; }
.plan-slot span { overflow: hidden; color: var(--ink-2); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.plan-slot b { grid-column: 2; color: var(--ink-3); font-size: 9px; font-weight: 500; }
.plan-slot small { grid-column: 1 / -1; overflow: hidden; color: var(--clay-deep); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.plan-slot > button { grid-column: 1 / -1; justify-self: start; border: 0; padding: 2px 0; color: var(--pine); background: transparent; font-size: 9px; font-weight: 700; cursor: pointer; }
.plan-slot > button:disabled { opacity: .4; cursor: not-allowed; }
.plan-slot.running { border-color: var(--pine); background: #e7f0eb; }
.plan-slot.running b,
.plan-slot.completed b { color: var(--pine); }
.plan-slot.completed { opacity: .72; }
.plan-slot.skipped,
.plan-slot.stopped,
.plan-slot.blocked,
.plan-slot.risk_blocked { background: #f4efea; opacity: .68; }
.plan-slot.failed b,
.plan-slot.blocked b,
.plan-slot.risk_blocked b { color: var(--clay-deep); }
.agent-command-bar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 14px; align-items: center; margin-top: 14px; padding: 13px; border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,.62); }
.command-copy strong,
.command-copy span { display: block; }
.command-copy strong { font-size: 13px; }
.command-copy span { margin-top: 2px; color: var(--ink-3); font-size: 10px; }
.agent-utilities { display: flex; align-items: center; gap: 5px; }
.agent-utilities .utility { border: 0; border-radius: 7px; background: transparent; color: var(--ink-3); padding: 8px 9px; font-size: 11px; cursor: pointer; }
.agent-utilities .utility:hover { background: var(--ivory); color: var(--ink); }
.agent-utilities .utility.danger { color: var(--clay-deep); }
.agent-utilities .utility:disabled { opacity: .42; cursor: not-allowed; }
.utility-divider { width: 1px; height: 22px; margin: 0 3px; background: var(--line); }
.recent-batches { margin-top: 13px; padding-top: 12px; border-top: 1px solid var(--line); }
.recent-batches-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.recent-batches-head strong { font-size: 12px; }
.recent-batches-head span { color: var(--ink-3); font-size: 10px; }
.recent-batch-list { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; margin-top: 8px; }
.recent-batch-item { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; padding: 9px 10px; border-radius: 9px; background: var(--ivory); color: var(--ink-3); font-size: 10px; }
.recent-batch-item strong { color: var(--ink-2); }
.recent-batch-item strong.risk_blocked,
.recent-batch-item strong.failed { color: var(--clay-deep); }
.recent-batch-item time { text-align: right; }
.pairing-box > strong { display: block; padding: 15px; text-align: center; font: 700 27px ui-monospace, monospace; letter-spacing: 0.12em; color: var(--pine); background: var(--ivory); border-radius: 10px; }
.pairing-box li { margin: 8px 0; }
.pairing-box code { word-break: break-all; }
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 11px;
  margin-top: 20px;
}
.metric-grid article,
.panel {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
}
.metric-grid span {
  color: var(--ink-3);
  font-size: 12px;
}
.metric-grid strong {
  display: block;
  font: 700 27px var(--serif);
  margin: 5px 0;
}
.metric-grid i {
  display: block;
  height: 7px;
  background: var(--bone);
  border-radius: 99px;
  overflow: hidden;
}
.metric-grid i b {
  display: block;
  height: 100%;
  background: var(--pine);
}
.metric-grid i b.clay {
  background: var(--clay);
}
.metric-grid small {
  display: block;
  color: var(--ink-3);
  margin-top: 7px;
}
.run-diagnostics {
  margin-bottom: 14px;
}
.diagnostic-summary {
  margin: 0 0 10px;
  padding: 10px 12px;
  border-radius: 9px;
  background: #e4eee9;
  color: var(--pine);
  font-size: 12px;
  line-height: 1.55;
}
.diagnostic-summary.warning,
.diagnostic-summary.legacy {
  background: var(--clay-tint);
  color: var(--clay-deep);
}
.diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.diagnostic-grid > div {
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--ivory);
}
.diagnostic-grid small {
  display: block;
  color: var(--ink-3);
  font-size: 10px;
}
.diagnostic-grid b {
  display: block;
  margin-top: 3px;
  font: 700 19px var(--serif);
}
.diagnostic-rejections {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}
.diagnostic-rejections span {
  padding: 4px 8px;
  border-radius: 99px;
  background: var(--clay-tint);
  color: var(--clay-deep);
  font-size: 10px;
}
.alerts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.alerts > div {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  border-radius: 8px;
  font-size: 12px;
}
.recovery-center { margin: 12px 0; background: linear-gradient(145deg, #fffdfa, #f5f7f3); }
.recovery-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.recovery-head h2 { margin: 3px 0; font: 700 21px var(--serif); }
.recovery-head p { margin: 0; color: var(--ink-3); font-size: 11px; }
.recovery-head > em { flex: none; border-radius: 99px; padding: 6px 10px; color: var(--clay-deep); background: var(--clay-tint); font-size: 10px; font-style: normal; font-weight: 700; }
.recovery-head > em.ok { color: var(--pine); background: #e4eee9; }
.recovery-list { display: grid; gap: 8px; margin-top: 13px; }
.recovery-item { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 16px; align-items: center; padding: 13px 14px; border: 1px solid #e8cfbd; border-radius: 11px; background: #fff8f1; }
.recovery-item.critical { border-color: #dfb19b; background: #fff1e8; }
.recovery-copy > div { display: flex; align-items: baseline; gap: 9px; }
.recovery-copy > div span { color: var(--clay-deep); font-size: 9px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.recovery-copy strong { font-size: 13px; }
.recovery-copy p { margin: 5px 0 0; color: var(--ink-2); font-size: 11px; }
.recovery-copy small { display: block; margin-top: 3px; color: var(--ink-3); font-size: 10px; }
.recovery-copy small.recovery-result { color: var(--pine); font-weight: 700; }
.recovery-item > button { border: 0; border-radius: 8px; padding: 9px 12px; color: #fff; background: var(--pine); font-size: 10px; font-weight: 700; cursor: pointer; }
.recovery-item > button:disabled { opacity: .45; cursor: not-allowed; }
.recovery-ok { display: flex; gap: 9px; align-items: baseline; margin-top: 13px; padding: 11px 13px; border-radius: 9px; color: var(--pine); background: #e9f1ed; }
.recovery-ok strong { font-size: 12px; }
.recovery-ok span { font-size: 10px; opacity: .8; }
.alert-action {
  border: 0;
  background: rgba(0, 0, 0, 0.08);
  color: inherit;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
}
.fail-table {
  max-height: 360px;
}
.fail-table table {
  min-width: 560px;
}
.refresh-feedback { display: block; margin-top: 5px; max-width: 190px; color: var(--ink-3); line-height: 1.45; }
.notes-table {
  max-height: 420px;
}
.notes-table table {
  min-width: 700px;
}
td em.bad {
  background: var(--clay-tint);
  color: var(--clay-deep);
}
.note-link {
  color: var(--ink);
  text-decoration: none;
}
.note-link:hover {
  color: var(--pine);
  text-decoration: underline;
}
.warning {
  background: #f8ead6;
  color: #9d6529;
}
.critical {
  background: #f5deda;
  color: #a94f43;
}
.ok {
  background: #e4eee9;
  color: var(--pine);
}
.funnel-section {
  margin-top: 34px;
  padding-top: 24px;
  border-top: 1px solid var(--line);
}
.funnel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 28px;
  margin-bottom: 14px;
}
.funnel-head span {
  color: var(--clay-deep);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .16em;
}
.funnel-head h2 {
  margin: 4px 0 0;
  font: 700 20px var(--serif);
}
.funnel-head p {
  max-width: 520px;
  margin: 0;
  color: var(--ink-3);
  font-size: 11px;
  line-height: 1.6;
  text-align: right;
}
.funnel {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}
.stage {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  min-height: 92px;
  padding: 13px 14px;
}
.stage small {
  color: var(--ink-3);
  font-size: 11px;
}
.stage strong {
  display: block;
  font: 700 25px var(--serif);
  margin-top: 2px;
}
.stage em {
  display: inline-block;
  margin-top: 5px;
  font-style: normal;
  font-size: 10px;
  color: var(--pine);
  background: #e4eee9;
  border-radius: 99px;
  padding: 2px 7px;
}
.stage em.zero {
  color: var(--clay-deep);
  background: var(--clay-tint);
}
.stage-note {
  display: block;
  margin-top: 6px;
  color: var(--ink-4);
  font-size: 9px;
  line-height: 1.4;
}
.stage.final {
  border-color: var(--pine);
}
.stage.final strong {
  color: var(--pine);
}
.stage.attrition {
  border-color: #e7c9b7;
  background: #fff8f2;
}
.stage.attrition strong {
  color: var(--clay-deep);
}
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) 330px;
  gap: 13px;
  margin-top: 28px;
}
.panel {
  margin-top: 13px;
}
.grid .panel {
  margin-top: 0;
}
.grid > aside {
  display: flex;
  min-width: 0;
}
.grid > aside > .panel {
  flex: 1;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.panel h2 {
  font: 700 19px var(--serif);
  margin: 0;
}
.table {
  width: 100%;
  max-height: 460px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
}
.table-scroll { display: block; overflow-y: scroll; scrollbar-gutter: stable both-edges; border: 1px solid var(--line); border-radius: 10px; }
.table-runs { height: min(50vh, 520px); min-height: 330px; }
.table-audit { height: min(46vh, 460px); min-height: 280px; }
.table-scroll table { min-width: 900px; }
.table::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.table::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 99px;
}
.table::-webkit-scrollbar-thumb:hover {
  background: var(--ink-3);
}
.table::-webkit-scrollbar-corner {
  background: transparent;
}
thead th {
  position: sticky;
  top: 0;
  background: var(--paper);
  z-index: 1;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}
th,
td {
  padding: 10px 8px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  font-size: 12px;
}
th {
  color: var(--ink-3);
}
td small {
  display: block;
  color: var(--ink-3);
  max-width: 170px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
td em,
.health em {
  font-style: normal;
  background: #e4eee9;
  color: var(--pine);
  padding: 4px 7px;
  border-radius: 99px;
  font-size: 10px;
}
.link {
  border: 0;
  background: none;
  color: var(--pine);
  padding: 3px;
}
.link:disabled { opacity: .4; cursor: not-allowed; }
.row-actions { display: flex; flex-wrap: wrap; gap: 3px 8px; min-width: 150px; }
.link.paid {
  color: var(--clay-deep);
}
.health > div {
  padding: 13px 0;
  border-bottom: 1px solid var(--line);
}
.health em {
  float: right;
}
.health p {
  color: var(--ink-3);
  font-size: 12px;
}
.health p strong {
  float: right;
  color: var(--ink);
}
.kw-tools {
  display: flex;
  gap: 8px;
  align-items: center;
}
.kw-filter {
  width: 180px;
}
.kw-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 8px;
}
.kw-card {
  background: var(--ivory);
  border: 1px solid transparent;
  border-radius: 11px;
  padding: 11px 12px;
  transition: border-color 0.15s;
}
.kw-card:hover {
  border-color: var(--line);
}
.kw-card.off {
  opacity: 0.55;
}
.kw-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.kw-main b {
  font-size: 14px;
  word-break: break-all;
}
.kw-state {
  flex: none;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 99px;
  background: #e4eee9;
  color: var(--pine);
}
.kw-card.off .kw-state {
  background: var(--clay-tint);
  color: var(--clay-deep);
}
.kw-card > small {
  display: block;
  color: var(--ink-3);
  margin: 5px 0 9px;
}
.kw-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  border-top: 1px dashed var(--line);
  padding-top: 8px;
}
.kw-actions button {
  border: 0;
  background: none;
  color: var(--pine);
  font-size: 11px;
  padding: 0;
  cursor: pointer;
}
.kw-actions button:hover {
  text-decoration: underline;
}
.kw-actions button.danger {
  color: var(--clay-deep);
}
.kw-empty {
  color: var(--ink-3);
  font-size: 12px;
  text-align: center;
  padding: 18px 0;
  margin: 0;
}
.auth-entry,
.retry-auth {
  border: 0;
  border-radius: 8px;
  background: var(--pine);
  color: white;
  padding: 7px 11px;
  font-size: 11px;
  cursor: pointer;
}
.qr-auth {
  text-align: center;
  padding: 4px 12px 12px;
}
.local-auth-methods {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
  padding: 4px;
  border-radius: 10px;
  background: var(--ivory);
}
.local-auth-methods button {
  border: 0;
  border-radius: 7px;
  padding: 9px 10px;
  color: var(--ink-3);
  background: transparent;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.local-auth-methods button.active {
  color: #fff;
  background: var(--pine);
}
.local-auth-help {
  min-height: 42px;
  margin: 0 4px 10px;
  color: var(--ink-3);
  font-size: 10px;
  line-height: 1.55;
  text-align: left;
}
.qr-auth canvas {
  width: 240px !important;
  height: 240px !important;
  border: 10px solid #fffdf8;
  border-radius: 12px;
}
.qr-placeholder {
  height: 250px;
  display: grid;
  place-items: center;
  color: var(--ink-3);
  background: var(--ivory);
  border-radius: 12px;
}
.qr-placeholder.browser-sync {
  height: 150px;
}
.auth-state {
  font-weight: 700;
  margin: 12px 0 4px;
}
.auth-state.scanned {
  color: var(--clay-deep);
}
.auth-state.verification_required {
  color: #a56a25;
}
.auth-state.failed,
.auth-state.expired {
  color: #a94f43;
}
.qr-auth > small {
  display: block;
  color: var(--ink-3);
  line-height: 1.6;
}
.local-auth-actions { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
.retry-auth {
  margin-top: 14px;
}
.auth-verify {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
.auth-verify a {
  border-radius: 8px;
  background: #a56a25;
  color: white;
  padding: 9px 12px;
  text-decoration: none;
  font-size: 12px;
  font-weight: 700;
}
.auth-verify .retry-auth {
  margin-top: 0;
}
.auth-verify small {
  color: var(--ink-3);
  line-height: 1.6;
}
.verification-fallbacks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.verification-fallbacks .retry-auth { min-height: 38px; }
.auth-success {
  height: 250px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  color: var(--pine);
  background: #e4eee9;
  border-radius: 12px;
}
.auth-success strong {
  font: 700 26px var(--serif);
}
.auth-success span {
  font-size: 12px;
}
@media (max-width: 1100px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .agent-command-bar { grid-template-columns: 1fr; }
  .agent-utilities { justify-content: flex-end; }
  .recent-batch-list { grid-template-columns: repeat(2, 1fr); }
  .grid {
    grid-template-columns: 1fr;
  }
  .funnel {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 620px) {
  .metric-grid,
  .kw-grid,
  .agent-facts {
    grid-template-columns: 1fr;
  }
  .active-task { grid-template-columns: 1fr; gap: 16px; padding: 18px; }
  .active-task h3 { font-size: 23px; }
  .agent-utilities { justify-content: flex-start; flex-wrap: wrap; }
  .recent-batch-list { grid-template-columns: 1fr; }
  .recent-batches-head { align-items: flex-start; flex-direction: column; }
  .agent-risk-alert { align-items: flex-start; flex-direction: column; }
  .risk-actions { justify-content: flex-start; }
  .verification-fallbacks { grid-template-columns: 1fr; }
  .funnel {
    grid-template-columns: repeat(2, 1fr);
  }
  .funnel-head { align-items: flex-start; flex-direction: column; gap: 8px; }
  .funnel-head p { text-align: left; }
  .diagnostic-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .monitor h1 {
    font-size: 29px;
  }
}
/* ── TikHub 付费通道面板 ─────────────────────── */
.tikhub-panel { background: linear-gradient(145deg, #fdfcf9, #f4f6f2); }
.tikhub-head-side { display: flex; align-items: center; gap: 8px; }
.tikhub-head-side button.quiet { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.75); color: var(--ink-2); padding: 7px 12px; cursor: pointer; }
.tikhub-token-badge { display: inline-flex; align-items: center; border-radius: 99px; padding: 6px 11px; font-size: 11px; font-weight: 700; }
.tikhub-token-badge.ok { color: var(--pine); background: #e4eee9; }
.tikhub-token-badge.bad { color: var(--clay-deep); background: var(--clay-tint); }
.tikhub-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 4px; }
.tikhub-grid > div { min-width: 0; padding: 13px 14px; border: 1px solid var(--line); border-radius: 11px; background: rgba(255,255,255,.66); }
.tikhub-grid small { display: block; color: var(--ink-3); font-size: 11px; }
.tikhub-grid strong { display: block; margin: 4px 0; font: 700 24px var(--serif); color: var(--ink-2); }
.tikhub-grid strong em { font: 500 13px var(--serif); color: var(--ink-3); font-style: normal; }
.tikhub-quota-card i { display: block; height: 7px; margin-top: 8px; background: var(--bone); border-radius: 99px; overflow: hidden; }
.tikhub-quota-card i b { display: block; height: 100%; background: var(--pine); border-radius: inherit; transition: width .3s ease; }
.tikhub-quota-card i b.warn { background: var(--clay); }
.tikhub-quota-sub { display: block; margin-top: 7px; color: var(--ink-3); font-size: 10px; }
.tikhub-trend-card svg { display: block; width: 100%; height: 36px; margin-top: 6px; }
.tikhub-op-card p { display: flex; justify-content: space-between; gap: 8px; margin: 5px 0 0; font-size: 11px; color: var(--ink-2); }
.tikhub-op-card p b { color: var(--ink-3); font-weight: 500; }
.tikhub-op-empty { color: var(--ink-3); }
.tikhub-calls { margin-top: 14px; }
.tikhub-calls-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.tikhub-calls-head strong { font-size: 13px; }
.tikhub-calls-head span { color: var(--ink-3); font-size: 10px; }
.tikhub-calls-table { max-height: 300px; }
.tikhub-calls-table table { min-width: 640px; }
.tikhub-calls-table td.err { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tikhub-calls-table tr.clickable { cursor: pointer; }
.tikhub-calls-table tr.clickable:hover { background: var(--ivory); }
.tikhub-calls-table tr.call-detail td { background: var(--ivory); color: var(--clay-deep); font-size: 11px; white-space: normal; word-break: break-all; }
@media (max-width: 900px) { .tikhub-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px) { .tikhub-grid { grid-template-columns: 1fr; } }

/* ── 今日状态横幅 ─────────────────────────────── */
.health-banner { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 14px 0 16px; padding: 14px 18px; border-radius: 13px; border: 1px solid var(--line); }
.health-banner.good { border-color: #cfe0d4; background: linear-gradient(120deg, #eef4ef, #e6efe9); }
.health-banner.warn { border-color: #ecd6b4; background: linear-gradient(120deg, #fbf3e4, #f8ecd8); }
.health-banner.bad { border-color: #e3c0ae; background: linear-gradient(120deg, #fbe9df, #f7e0d2); }
.health-banner-main { display: flex; align-items: center; gap: 12px; min-width: 0; }
.health-dot { flex: none; width: 11px; height: 11px; border-radius: 50%; }
.health-banner.good .health-dot { background: var(--pine); box-shadow: 0 0 0 4px rgba(63, 92, 82, .16); }
.health-banner.warn .health-dot { background: #b9832f; box-shadow: 0 0 0 4px rgba(185, 131, 47, .16); }
.health-banner.bad .health-dot { background: var(--clay-deep); box-shadow: 0 0 0 4px rgba(168, 90, 64, .18); }
.health-banner-main strong { display: block; font-size: 15px; color: var(--ink-2); }
.health-banner-main p { margin: 2px 0 0; color: var(--ink-3); font-size: 12px; }
.health-banner-side { display: flex; flex-direction: column; align-items: flex-end; gap: 7px; flex: none; }
.health-banner-side span { color: var(--ink-3); font-size: 11px; }
.banner-action { border: 0; border-radius: 8px; padding: 7px 13px; color: #fff; background: var(--clay-deep); font-size: 12px; cursor: pointer; }
/* ── 趋势面板 ─────────────────────────────────── */
.trends-panel { margin-bottom: 16px; }
.trend-tools { display: flex; gap: 6px; }
.trend-range { border: 1px solid var(--line); border-radius: 8px; padding: 5px 11px; background: transparent; color: var(--ink-3); font-size: 11px; cursor: pointer; }
.trend-range.active { border-color: var(--pine); color: var(--pine); background: #e9f0eb; font-weight: 700; }
.trends-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 4px; }
.trend-card { margin: 0; padding: 12px 14px; border: 1px solid var(--line); border-radius: 11px; background: rgba(255, 255, 255, .6); }
.trend-card figcaption { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; color: var(--ink-2); font-size: 12px; font-weight: 600; }
.trend-card figcaption small { color: var(--ink-3); font-size: 10px; font-weight: 500; }
.trend-card svg { display: block; width: 100%; height: 40px; margin-top: 8px; }
.trend-empty { margin: 6px 0 0; color: var(--ink-3); font-size: 12px; }
/* ── 采集策略表单 ─────────────────────────────── */
.schedule-window { display: flex; align-items: center; gap: 10px; width: 100%; }
.schedule-window .el-select { flex: 1; }
.schedule-note { margin: 4px 0 0; padding: 10px 12px; border-radius: 9px; background: var(--ivory); color: var(--ink-3); font-size: 11px; line-height: 1.6; }
/* ── 关键词历史 / 侧栏健康 ────────────────────── */
.health-intro { margin: 2px 0 10px; color: var(--ink-3); font-size: 11px; }
.health-empty { color: var(--ink-3); font-size: 11px; }
@media (max-width: 900px) {
  .trends-grid { grid-template-columns: 1fr; }
  .health-banner { flex-direction: column; align-items: flex-start; }
  .health-banner-side { align-items: flex-start; }
}
</style>
