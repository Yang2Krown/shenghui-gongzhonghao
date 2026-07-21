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
        <span>TikHub 今日共享额度</span
        ><strong>{{ data.quota.used }} / {{ data.quota.limit }}</strong
        ><i
          ><b
            class="clay"
            :style="{ width: percent(data.quota.used, data.quota.limit) + '%' }"
          ></b></i
        ><small
          >剩余 {{ data.quota.remaining }} · 预留搜索
          {{ data.quota.reserved_searches }} · 预计 ¥{{
            data.quota.estimated_cost_cny
          }}</small
        >
      </article>
      <article>
        <span>CLI 最近成功率</span
        ><strong>{{ rate(data.providers.cli.success_rate) }}</strong
        ><i
          ><b
            :style="{ width: (data.providers.cli.success_rate || 0) + '%' }"
          ></b></i
        ><small
          >v{{ data.providers.cli.version || "未安装" }} · Cookie
          {{
            data.providers.cli.cookie_configured ? "已挂载" : "未配置"
          }}<template v-if="data.providers.cli.cooldown_remaining_seconds">
            · 剩余冷却
            {{ cooldownMinutes(data.providers.cli.cooldown_remaining_seconds) }}
            分钟</template
          ></small
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
          v-if="a.key === 'cli_auth' && userStore.isSuperAdmin"
          class="alert-action"
          @click="startCliAuth"
        >
          重新扫码
        </button>
      </div>
      <div v-if="!data.alerts.length" class="ok">
        正常 · 当前没有小红书采集告警
      </div>
    </div>
    <article v-if="primaryAgent" class="panel recovery-center">
      <div class="recovery-head">
        <div>
          <div class="kicker">INCIDENT RECOVERY</div>
          <h2>故障处理中心</h2>
          <p>不仅提示异常，也给出原因、影响和可以立即执行的恢复动作</p>
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
            :disabled="recoveryBusy === item.key || !canAgentCollect || !!activeBatch || (manualRetryWaitMinutes > 0 && !userStore.isSuperAdmin)"
            @click="retryFailedSlot(item.slot)"
          >{{ recoveryBusy === item.key ? "正在重试…" : manualRetryWaitMinutes > 0 ? userStore.isSuperAdmin ? `跳过冷却并重试` : `安全冷却 ${manualRetryWaitMinutes} 分钟` : "重新执行这个词" }}</button>
          <button v-else-if="item.action === 'login'" :disabled="!primaryAgent.connected" @click="startLocalLogin">打开人工验证</button>
          <button v-else @click="refresh">重新检测状态</button>
        </section>
      </div>
      <div v-else class="recovery-ok"><strong>采集链路正常</strong><span>本地节点在线、Cookie 正常，今天没有待处理失败。</span></div>
    </article>
    <article v-if="data" class="panel agent-panel">
      <div class="panel-head">
        <div>
          <div class="kicker">LOCAL COLLECTOR</div>
          <h2>本地采集节点</h2>
          <p>当前任务、批次进度和本地账号状态</p>
        </div>
        <div class="agent-head-actions">
          <span v-if="primaryAgent" :class="['connection-badge', primaryAgent.connected ? 'online' : 'offline']">
            {{ primaryAgent.connected ? "节点在线" : "节点离线" }}
          </span>
          <button class="quiet" @click="refresh">刷新</button>
          <button v-if="userStore.isSuperAdmin && !primaryAgent" class="quiet" @click="createAgentPairing">绑定 Mac</button>
        </div>
      </div>
      <template v-if="primaryAgent">
        <section :class="['active-task', { idle: !hasActiveTask, blocked: primaryAgent.cookie_status === 'verification_required' }]">
          <div class="active-task-copy">
            <div class="task-label">
              <span class="status-dot"></span>
              {{ hasActiveTask ? "正在采集" : primaryAgent.cookie_status === "verification_required" ? "采集已阻断" : "当前空闲" }}
              <span v-if="activeBatch" class="auto-refresh">每 5 秒更新</span>
            </div>
            <h3>{{ hasActiveTask ? (activeBatch?.current_keyword || primaryAgent.current_keyword || runningPlanSlot?.keyword || "正在读取当前关键词…") : agentIdleTitle }}</h3>
            <p v-if="activeBatch">
              {{ batchMode(activeBatch.mode) }} · 已处理 {{ batchProcessed(activeBatch) }} / {{ activeBatch.total_keywords }} 个关键词
              <span class="phase-hint">最近进度 {{ shortTime(activeBatch.last_progress_at) }} · 当前只执行这一个关键词</span>
            </p>
            <p v-else-if="runningPlanSlot">定时采集正在本地执行；后续到点任务会按顺序衔接。</p>
            <p v-else>{{ agentIdleDescription }}</p>
          </div>
          <div v-if="activeBatch" class="task-progress-card">
            <strong>{{ batchProcessed(activeBatch) ? batchPercent(activeBatch) + "%" : "执行中" }}</strong>
            <span>当前单词任务 · 完成 {{ activeBatch.completed_keywords }} · 异常 {{ activeBatch.failed_keywords }}</span>
            <i><b :style="{ width: batchPercent(activeBatch) + '%' }"></b></i>
          </div>
          <div v-else-if="runningPlanSlot" class="task-progress-card">
            <strong>执行中</strong>
            <span>{{ slotTime(runningPlanSlot) }} 开始 · 当前只执行这一个关键词</span>
            <i><b style="width: 18%"></b></i>
          </div>
          <div v-else class="task-ready-card">
            <small>Cookie</small>
            <strong>{{ agentCookieLabel(primaryAgent.cookie_status) }}</strong>
          </div>
        </section>

        <div class="agent-facts">
          <div><small>本地账号</small><strong>{{ agentCookieLabel(primaryAgent.cookie_status) }}</strong><span>Cookie 仅保存在 Mac</span></div>
          <div><small>今日关键词</small><strong>{{ todayPlan ? `${todayPlan.base_count} + ${todayPlan.derived_count}` : "正在生成" }}</strong><span>09:40 / 14:20 两波 · 重点词重复</span></div>
          <div><small>{{ runningPlanSlot ? "当前任务" : "下一次" }}</small><strong>{{ runningPlanSlot ? "执行中" : nextPendingSlot ? slotTime(nextPendingSlot) : "今日已结束" }}</strong><span>{{ runningPlanSlot?.keyword || nextPendingSlot?.keyword || "没有待执行关键词" }}</span></div>
          <div><small>今日进度</small><strong>{{ planCompleted }} / {{ planTotal }}</strong><span>跳过 {{ planSkipped }} · 剩余 {{ planPending }}</span></div>
        </div>
      </template>
      <div v-if="primaryAgent?.cookie_status === 'verification_required'" class="agent-risk-alert">
        <div><strong>小红书要求人机验证</strong><span>今日计划已暂停。先完成验证；Cookie 恢复正常后，再点击“继续今日计划”。</span></div>
        <button @click="startLocalLogin">打开人工验证</button>
      </div>
      <div v-if="!primaryAgent" class="agent-empty"><strong>尚未绑定本地采集节点</strong><p>生成绑定码后，在这台 Mac 上运行一次安装程序；之后自动启动。</p></div>
      <section v-if="primaryAgent && todayPlan" class="daily-plan">
        <div class="daily-plan-head">
          <div><strong>今日采集时间轴</strong><span>每次只采一个词；到点后按队列串行执行</span></div>
          <em :class="{ paused: todayPlan.paused, stopped: todayPlan.stopped }">{{ planStateLabel }}</em>
        </div>
        <div class="plan-track">
          <div v-for="slot in todayPlan.slots" :key="`${slot.wave || 'manual'}-${slot.keyword_id}-${slot.scheduled_at}`" :class="['plan-slot', slot.status]" :title="slot.error || slot.reason || ''">
            <time>{{ slotTime(slot) }}</time><span>{{ slot.keyword }}</span><b>{{ slotTypeLabel(slot) }} · {{ slotStatus(slot.status) }}</b>
            <small v-if="slot.error">{{ slot.error }}</small>
            <button v-if="slot.status === 'failed'" :disabled="recoveryBusy === `slot-${slot.keyword_id}` || !canAgentCollect || !!activeBatch || (manualRetryWaitMinutes > 0 && !userStore.isSuperAdmin)" @click="retryFailedSlot(slot)">{{ manualRetryWaitMinutes > 0 ? userStore.isSuperAdmin ? "跳过冷却并重试" : `${manualRetryWaitMinutes} 分钟后可重试` : "重试" }}</button>
          </div>
        </div>
      </section>
      <div v-if="primaryAgent" class="agent-command-bar">
        <div class="command-copy"><strong>全天自动计划</strong><span>Mac 保持开机即可，无需手动执行整组</span></div>
        <div class="agent-utilities">
          <button class="utility" :disabled="!primaryAgent.connected || !!activeBatch" @click="startLocalLogin">更换本地账号</button>
          <span class="utility-divider"></span>
          <button v-if="!todayPlan?.paused" class="utility" :disabled="!primaryAgent.connected || todayPlan?.stopped" @click="sendAgentCommand('pause')">暂停今日计划</button>
          <button v-else class="utility" :disabled="!primaryAgent.connected || todayPlan?.stopped || primaryAgent.cookie_status !== 'valid'" @click="sendAgentCommand('resume')">继续今日计划</button>
          <button class="utility danger" :disabled="!primaryAgent.connected || todayPlan?.stopped" @click="stopTodayPlan">停止今日计划</button>
        </div>
      </div>
      <div v-if="recentBatches.length" class="recent-batches">
        <div class="recent-batches-head"><strong>最近批次</strong><span>以下均为历史记录，不代表当前状态</span></div>
        <div class="recent-batch-list">
          <div v-for="batch in recentBatches" :key="batch.id" class="recent-batch-item">
            <span>{{ batchMode(batch.mode) }}</span>
            <strong :class="batch.status">{{ status(batch.status) }}</strong>
            <span>{{ batch.completed_keywords }}/{{ batch.total_keywords }} 完成</span>
            <time>{{ shortTime(batch.last_progress_at) }}</time>
          </div>
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
                <th>TikHub</th>
                <th>CLI</th>
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
                  {{ status(row.tikhub_status)
                  }}<small>{{ row.tikhub_raw_count }} 条</small>
                </td>
                <td>
                  {{ status(row.cli_status)
                  }}<small>{{ cliResultLabel(row) }}</small>
                </td>
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
                    <button v-if="row.status !== 'completed'" class="link" :disabled="!canAgentCollect || !!activeBatch" @click="testKeywordWithAgent(row.keyword_id)">本地测试</button>
                    <button v-if="userStore.isSuperAdmin && row.status !== 'completed'" class="link paid" @click="retry(row, true)">付费刷新</button>
                  </div>
                </td>
              </tr>
              <tr v-if="!runRows.length">
                <td colspan="8">今日尚无执行记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
      <aside>
        <article class="panel health">
          <h2>来源健康</h2>
          <div>
            <b>TikHub</b
            ><em :class="data.providers.tikhub.status">{{
              rate(data.providers.tikhub.success_rate)
            }}</em>
            <p>搜索与详情共用 100 次硬上限；达到上限后 CLI 免费链路继续。</p>
          </div>
          <div>
            <b>xiaohongshu-cli</b
            ><em
              :class="
                data.providers.cli.auth_status === 'expired'
                  ? 'critical'
                  : data.providers.cli.status
              "
              >{{ cliAuthLabel(data.providers.cli) }}</em
            >
            <p>
              锁定 0.6.4 · 一周内搜索 · 今日 &gt; 200 / 一周 &gt; 2000 · 最多点赞 · 全局并发
              1。验证码冷却最长 10 分钟，重新扫码可立即解除。
            </p>
            <button
              v-if="userStore.isSuperAdmin"
              class="auth-entry"
              @click="startCliAuth"
            >
              {{
                data.providers.cli.auth_status === "expired"
                  ? "重新扫码登录"
                  : "更新扫码登录"
              }}
            </button>
          </div>
          <div>
            <b>淘汰原因</b>
            <p v-for="(count, key) in data.rejections" :key="key">
              {{ reason(key) }} <strong>{{ count }}</strong>
            </p>
          </div>
        </article>
      </aside>
    </div>
    <article v-if="data" class="panel keyword-panel">
      <div class="panel-head">
        <div>
          <h2>关键词管理</h2>
          <p>{{ enabledBaseCount + enabledDerivedCount }} 个启用词参与两波采集；连续 3 个有效零产出日自动隔离，最多保留 30 个</p>
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
            <button @click="searchNow(k)">立即搜索</button
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
          <p>不记录 Token 或 Cookie；费用按配置单价估算</p>
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
              <th>付费请求</th>
              <th>预计费用</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in data.calls" :key="c.id">
              <td>{{ time(c.created_at) }}</td>
              <td>{{ c.provider }}</td>
              <td>{{ c.operation }}</td>
              <td>{{ status(c.status) }}</td>
              <td>{{ c.latency_ms == null ? "—" : c.latency_ms + "ms" }}</td>
              <td>{{ c.paid_request ? "是" : "否" }}</td>
              <td>¥{{ c.estimated_cost }}</td>
              <td :title="c.error_message || ''">{{ callError(c) }}</td>
            </tr>
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
            <div><small>搜索页返回</small><b>{{ runNotesRun.cli_raw_count }}</b></div>
            <div><small>成功解析</small><b>{{ runNotesRun.merged_count }}</b></div>
            <div><small>今日候选</small><b>{{ levelStat(runNotesRun, "daily", "candidate_count") }}</b></div>
            <div><small>今日赞 &gt; 200</small><b>{{ levelStat(runNotesRun, "daily", "eligible_count") }}</b></div>
            <div><small>一周候选</small><b>{{ levelStat(runNotesRun, "weekly", "candidate_count") }}</b></div>
            <div><small>一周赞 &gt; 2000</small><b>{{ levelStat(runNotesRun, "weekly", "eligible_count") }}</b></div>
            <div><small>详情成功</small><b>{{ runNotesRun.detail_success_count }} / {{ runNotesRun.detail_attempted_count }}</b></div>
            <div><small>最终入库</small><b>{{ runNotesRun.displayable_count }}</b></div>
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
    <el-dialog
      v-model="showCliAuth"
      title="重新授权小红书采集"
      width="430px"
      append-to-body
      :lock-scroll="false"
      :close-on-click-modal="false"
      @closed="cancelCliAuth"
      ><div class="qr-auth">
        <div v-if="authCreating" class="qr-placeholder">正在获取二维码…</div>
        <canvas
          v-show="!authCreating && authState !== 'authenticated'"
          ref="authQrCanvas"
        ></canvas>
        <div v-if="authState === 'authenticated'" class="auth-success">
          <strong>授权成功</strong
          ><span>新 Cookie 已保存到服务器，CLI 采集已恢复</span>
        </div>
        <p :class="['auth-state', authState]">{{ authMessage }}</p>
        <div v-if="authState === 'verification_required'" class="auth-verify">
          <a :href="authVerificationUrl" target="_blank" rel="noopener noreferrer"
            >打开小红书人机验证</a
          ><button class="retry-auth" @click="resumeCliAuth">我已完成，继续检查</button>
          <small>验证页会在新窗口打开；完成后回到这里继续，不需要重新扫码。</small>
        </div>
        <small v-if="authState === 'waiting' || authState === 'scanned'"
          >请使用小红书 App 扫码并在手机上确认；二维码 4 分钟内有效。</small
        ><button
          v-if="authState === 'failed' || authState === 'expired'"
          class="retry-auth"
          @click="startCliAuth"
        >
          重新获取二维码
        </button>
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
    <el-dialog v-model="showLocalLogin" title="本地节点扫码登录" width="430px" append-to-body :lock-scroll="false" @closed="stopLocalLoginPoll">
      <div class="qr-auth">
        <div v-if="!localLoginQr" class="qr-placeholder">正在让本地 Mac 生成二维码…</div>
        <canvas v-show="localLoginQr" ref="localLoginCanvas"></canvas>
        <p :class="['auth-state', localLoginState]">{{ localLoginMessage }}</p>
        <button v-if="localLoginState === 'failed'" class="retry-auth" @click="startLocalLogin">重新获取二维码</button>
        <div v-if="localLoginVerificationUrl" class="auth-verify">
          <a :href="localLoginVerificationUrl" target="_blank" rel="noopener noreferrer">打开小红书人机验证</a>
          <small>在新页面完成验证后回到这里等待“本地授权成功”，然后关闭窗口并点击“继续今日计划”。</small>
        </div>
        <small>Cookie 只写入本地 Mac，不会上传服务器。</small>
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
  showCliAuth = ref(false),
  authCreating = ref(false),
  authState = ref("idle"),
  authMessage = ref(""),
  authQrCanvas = ref(null),
  authSessionId = ref(""),
  authVerificationUrl = ref(""),
  agentData = ref({ devices: [], batches: [] }),
  showAgentPairing = ref(false),
  pairingCode = ref(""),
  showLocalLogin = ref(false),
  localLoginCanvas = ref(null),
  localLoginQr = ref(""),
  localLoginState = ref("waiting"),
  localLoginMessage = ref("等待本地节点响应…"),
  localLoginVerificationUrl = ref(""),
  localLoginCommandId = ref(""),
  imageRefreshBusy = ref(""),
  recoveryBusy = ref(""),
  recoveryResult = reactive({}),
  imageRefreshFeedback = reactive({});
let authTimer = null;
let monitorTimer = null;
let localLoginTimer = null;
const loadAgent = async () => {
  try {
    agentData.value = (
      await api.get("/admin/xhs-monitoring/agent/devices", {
        skipErrorToast: true,
      })
    ).data;
  } catch {
    agentData.value = { devices: [], batches: [] };
  }
};
const load = async () => {
  loading.value = true;
  try {
    const [monitor] = await Promise.all([
      api.get("/admin/xhs-monitoring", { skipErrorToast: true }),
      loadAgent(),
    ]);
    data.value = monitor.data;
  } catch {
    data.value = null;
  } finally {
    loading.value = false;
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
const planWindow = computed(() => todayPlan.value ? `${todayPlan.value.window_start}–${todayPlan.value.window_end}` : "09:30–22:30");
const planStateLabel = computed(() => todayPlan.value?.stopped ? "今日已停止" : todayPlan.value?.risk_blocked ? "等待人工验证" : todayPlan.value?.paused ? "已暂停" : hasActiveTask.value ? "正在执行" : planPending.value ? "等待下一词" : "今日完成");
const slotTime = (slot) => slot?.scheduled_at?.slice(11, 16) || "—";
const slotTypeLabel = (slot) => slot?.keyword_type === "derived" ? "总结词" : "基础词";
const slotStatus = (value) => ({ pending: "待执行", running: "执行中", completed: "完成", failed: "失败", skipped: "已错过", stopped: "已停止", blocked: "风控停止", risk_blocked: "风控停止" })[value] || value;
const agentIdleTitle = computed(() => {
  if (!primaryAgent.value?.connected) return "本地节点已离线";
  if (primaryAgent.value.cookie_status === "verification_required") return "需要重新验证本地账号";
  if (todayPlan.value?.stopped) return "今日计划已经停止";
  if (todayPlan.value?.paused) return "今日计划已暂停";
  if (nextPendingSlot.value) return `等待 ${slotTime(nextPendingSlot.value)} · ${nextPendingSlot.value.keyword}`;
  return "今日计划已执行完毕";
});
const agentIdleDescription = computed(() => {
  if (!primaryAgent.value?.connected) return "请保持这台 Mac 开机并检查 Agent 运行状态。";
  if (primaryAgent.value.cookie_status === "verification_required") return "完成扫码或人机验证后才能重新采集。";
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
  if (!primaryAgent.value?.connected) items.push({
    key: "agent-offline", level: "critical", label: "本地节点", title: "Mac 采集节点离线",
    cause: "服务器无法向你的 Mac 下发任务，定时采集不会执行。",
    solution: "确认 Mac 已开机且联网，然后重新检测；Agent 会自动重连。", action: "refresh",
  });
  if (primaryAgent.value?.cookie_status === "verification_required") items.push({
    key: "verification", level: "critical", label: "账号验证", title: "小红书要求人工验证",
    cause: "系统已暂停后续请求，避免继续触发风控。",
    solution: "打开人工验证并完成扫码，成功后点击继续今日计划。", action: "login",
  });
  for (const slot of failedPlanSlots.value) {
    const guide = failureGuide(slot);
    items.push({ key: `slot-${slot.keyword_id}`, level: "warning", label: `${slotTime(slot)} · 失败词`, slot, ...guide });
  }
  return items;
});
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
  if (!localLoginCommandId.value) return;
  try {
    const command = (
      await api.get(
        `/admin/xhs-monitoring/agent/commands/${localLoginCommandId.value}`,
        { skipErrorToast: true },
      )
    ).data;
    const result = command.result || {};
    localLoginState.value = result.status || command.status;
    localLoginMessage.value = result.message ||
      (result.status === "authenticated" ? "本地授权成功" : result.status === "scanned" ? "已扫码，请在手机上确认" : "等待扫码…");
    localLoginVerificationUrl.value = result.verification_url || "";
    if (result.qr_url && result.qr_url !== localLoginQr.value) {
      localLoginQr.value = result.qr_url;
      await nextTick();
      await QRCode.toCanvas(localLoginCanvas.value, result.qr_url, { width: 240, margin: 1 });
    }
    if (command.status === "succeeded" || command.status === "failed") {
      if (command.status === "succeeded") ElMessage.success("本地 Cookie 已更新");
      else {
        localLoginState.value = "failed";
        localLoginMessage.value = command.error || "本地扫码登录失败";
      }
      stopLocalLoginPoll();
      await loadAgent();
      return;
    }
    localLoginTimer = window.setTimeout(pollLocalLogin, 2000);
  } catch {
    localLoginMessage.value = "登录状态读取失败";
    stopLocalLoginPoll();
  }
};
const startLocalLogin = async () => {
  if (!primaryAgent.value?.connected) return ElMessage.warning("本地采集节点当前离线");
  stopLocalLoginPoll();
  showLocalLogin.value = true;
  localLoginQr.value = "";
  localLoginState.value = "waiting";
  localLoginMessage.value = "正在让本地 Mac 生成二维码…";
  localLoginVerificationUrl.value = "";
  const response = await api.post("/admin/xhs-monitoring/agent/commands", {
    device_id: primaryAgent.value.id,
    command_type: "login",
  });
  localLoginCommandId.value = response.data.command_id;
  localLoginTimer = window.setTimeout(pollLocalLogin, 800);
};
const runRows = computed(() => data.value?.runs || []);
const filteredKeywords = computed(() => {
  const q = kwFilter.value.trim().toLowerCase(),
    list = data.value?.keywords || [];
  return q ? list.filter((k) => k.keyword.toLowerCase().includes(q)) : list;
});
const enabledBaseCount = computed(() => (data.value?.keywords || []).filter((item) => item.enabled && item.type === "base").length);
const enabledDerivedCount = computed(() => (data.value?.keywords || []).filter((item) => item.enabled && item.type === "derived").length);
const percent = (a, b) => (b ? Math.round((a / b) * 100) : 0);
const rate = (n) => (n == null ? "暂无样本" : `${n}%`);
const cooldownMinutes = (seconds) => Math.max(1, Math.ceil(seconds / 60));
const time = (v) =>
  v ? new Date(v).toLocaleString("zh-CN", { hour12: false }) : "—";
const cliAuthLabel = (cli) =>
  cli.auth_status === "expired"
    ? "登录已失效"
    : cli.auth_status === "missing"
      ? "未授权"
      : cli.installed
        ? "已配置"
        : "未安装";
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
const cliResultLabel = (row) => {
  if (row.run_source === "local_agent" && !row.has_search_diagnostics)
    return "历史未记录原始搜索数";
  if (row.search_state === "unrecognized") return "搜索响应无法解析";
  return `搜索返回 ${row.cli_raw_count} 条`;
};
const searchParseLabel = (row) =>
  row.run_source === "local_agent" && !row.has_search_diagnostics
    ? `未知 / 已上传 ${row.merged_count}`
    : `${row.tikhub_raw_count + row.cli_raw_count} / ${row.merged_count}`;
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
  return `搜索页返回 ${run.cli_raw_count} 条，最终入库 ${run.displayable_count} 条。`;
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
const retry = async (row, paid) => {
  await ElMessageBox.confirm(
    paid
      ? "本操作可能产生 TikHub 费用，确认由最高管理员执行？"
      : "本次只执行免费链路，不消耗 TikHub 额度。",
    "确认重试",
    { lockScroll: false },
  );
  await api.post(
    `/admin/xhs-monitoring/keywords/${row.keyword_id}/retry-${paid ? "paid" : "free"}`,
  );
  ElMessage.success("已提交任务");
  load();
};
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
const searchNow = async (k) => {
  await testKeywordWithAgent(k.id);
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
    raw = (f.tikhub_raw_count || 0) + (f.cli_raw_count || 0),
    cliIncomplete = (f.cli_missing_diagnostics_count || 0) > 0,
    parsedOut = Math.max(0, raw - (f.merged_count || 0));
  return [
    {
      label: "搜索页返回",
      value: cliIncomplete ? "未完整记录" : raw,
      note: cliIncomplete
        ? `${f.cli_missing_diagnostics_count} 个历史批次未知`
        : f.tikhub_raw_count
          ? `CLI ${f.cli_raw_count || 0} · TikHub ${f.tikhub_raw_count}`
          : "本地 CLI",
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
const stopAuthPoll = () => {
  if (authTimer) {
    clearTimeout(authTimer);
    authTimer = null;
  }
};
const pollCliAuth = async () => {
  if (!authSessionId.value) return;
  try {
    const result = (
      await api.get(
        `/admin/xhs-monitoring/cli-auth/sessions/${authSessionId.value}`,
        { skipErrorToast: true },
      )
    ).data;
    authState.value = result.status;
    if (result.status === "scanned") {
      authMessage.value = "已扫码，请在手机上确认登录";
    } else if (result.status === "waiting") {
      authMessage.value = "等待扫码…";
    } else if (result.status === "authenticated") {
      authMessage.value = "授权成功，采集已恢复";
      authSessionId.value = "";
      stopAuthPoll();
      ElMessage.success("小红书 CLI 授权已更新");
      await load();
      return;
    } else if (result.status === "verification_required") {
      authMessage.value = result.message || "请先完成人机验证";
      authVerificationUrl.value = result.verification_url || "";
      stopAuthPoll();
      return;
    } else if (result.status === "failed" || result.status === "expired") {
      authMessage.value = result.message || "授权失败";
      authSessionId.value = "";
      stopAuthPoll();
      return;
    }
    authTimer = setTimeout(pollCliAuth, 2000);
  } catch (error) {
    authState.value = "failed";
    authMessage.value =
      error?.response?.data?.detail || "授权状态查询失败";
    authSessionId.value = "";
    stopAuthPoll();
  }
};
const resumeCliAuth = () => {
  if (!authSessionId.value) return;
  authState.value = "waiting";
  authMessage.value = "正在检查验证结果…";
  authVerificationUrl.value = "";
  pollCliAuth();
};
const startCliAuth = async () => {
  stopAuthPoll();
  if (authSessionId.value) {
    await api
      .delete(
        `/admin/xhs-monitoring/cli-auth/sessions/${authSessionId.value}`,
        { skipErrorToast: true },
      )
      .catch(() => {});
  }
  showCliAuth.value = true;
  authCreating.value = true;
  authState.value = "waiting";
  authMessage.value = "正在获取二维码…";
  authSessionId.value = "";
  authVerificationUrl.value = "";
  try {
    const result = (
      await api.post("/admin/xhs-monitoring/cli-auth/sessions")
    ).data;
    authSessionId.value = result.session_id;
    await nextTick();
    await QRCode.toCanvas(authQrCanvas.value, result.qr_url, {
      width: 240,
      margin: 1,
      color: { dark: "#24211d", light: "#fffdf8" },
    });
    authMessage.value = "等待扫码…";
    authTimer = setTimeout(pollCliAuth, 1200);
  } catch (error) {
    authState.value = "failed";
    authMessage.value =
      error?.response?.data?.detail || "获取二维码失败";
  } finally {
    authCreating.value = false;
  }
};
const cancelCliAuth = async () => {
  stopAuthPoll();
  const sessionId = authSessionId.value;
  authSessionId.value = "";
  if (sessionId) {
    await api
      .delete(`/admin/xhs-monitoring/cli-auth/sessions/${sessionId}`, {
        skipErrorToast: true,
      })
      .catch(() => {});
  }
};
const scheduleMonitorRefresh = () => {
  if (monitorTimer) window.clearTimeout(monitorTimer);
  monitorTimer = window.setTimeout(async () => {
    if (document.visibilityState === "visible") {
      if (activeBatch.value) await load();
      else await loadAgent();
    }
    scheduleMonitorRefresh();
  }, activeBatch.value ? 5000 : 30000);
};
onMounted(() => {
  load();
  scheduleMonitorRefresh();
});
onBeforeUnmount(() => {
  cancelCliAuth();
  stopLocalLoginPoll();
  if (monitorTimer) window.clearTimeout(monitorTimer);
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
</style>
