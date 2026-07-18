<template>
  <div class="camp" ref="root">
    <!-- Nav -->
    <nav :class="['camp-nav', { scrolled: navScrolled }]">
      <div class="camp-nav-inner">
        <a class="brand" @click="goLanding">
          <img class="brand-logo" src="/brand/ip-compass.svg" alt="IP罗盘" />
          <span class="brand-name">IP罗盘</span>
        </a>
        <div class="camp-nav-links">
          <a href="#outline">课程大纲</a>
          <a href="#price">报名</a>
        </div>
        <div class="camp-nav-cta">
          <button class="btn btn-ghost" @click="onLoginEntry">
            {{ userStore.isAuthenticated ? '退出登录' : '登录 / 注册' }}
          </button>
          <button class="btn btn-primary" @click="openModal('pay')">立即报名 <span class="btn-arrow">→</span></button>
        </div>
      </div>
    </nav>

    <!-- ============ HERO ============ -->
    <header class="hero">
      <div class="hero-decor" aria-hidden="true">
        <svg viewBox="0 0 1400 800" preserveAspectRatio="xMidYMid slice" style="position:absolute;inset:0;width:100%;height:100%;opacity:.5">
          <g stroke="#E4DDCE" stroke-width="1" fill="none">
            <path d="M120 180 L240 240 L180 360" stroke-dasharray="3 4" />
            <path d="M1200 120 L1280 220 L1180 320" stroke-dasharray="3 4" />
            <path d="M1100 600 L1240 540 L1300 660" stroke-dasharray="3 4" />
          </g>
          <g fill="#E9B79E">
            <circle cx="120" cy="180" r="3" /><circle cx="240" cy="240" r="2" /><circle cx="180" cy="360" r="2.5" />
            <circle cx="1200" cy="120" r="2.5" /><circle cx="1280" cy="220" r="2" /><circle cx="1180" cy="320" r="3" />
          </g>
        </svg>
      </div>
      <div class="container">
        <div class="hero-badge fade-up">AI 垂类公众号 · 陪伴营</div>
        <h1 class="fade-up">从 0 开始做 AI 垂类公众号<br><strong>从选题，一直讲到商业变现</strong></h1>
        <p class="subtitle fade-up">不讲理论，只讲我们在真实账号上跑出来的方法：怎么找到会火的选题、怎么让数据稳定、怎么接到商单。选题和加热这两套打法，已经让先学的人显著提升了收入。</p>
        <div class="hero-cta fade-up">
          <a class="btn btn-primary" @click="openModal('pay')">立即报名</a>
          <a class="btn btn-ghost" @click="openModal('wx')">了解详情</a>
        </div>
        <div class="stats fade-up">
          <div><div class="stat-value">1000<em> 万+</em></div><div class="stat-label">讲师新媒体累计变现</div></div>
          <div><div class="stat-value">3<em> 个月</em></div><div class="stat-label">从 0 到月入近 20 万</div></div>
          <div><div class="stat-value">1:10</div><div class="stat-label">实测加热投产比</div></div>
          <div><div class="stat-value">12<em> 章</em></div><div class="stat-label">完整讲义 + SOP 工具包</div></div>
        </div>
      </div>
    </header>

    <!-- ============ 痛点 ============ -->
    <section class="alt">
      <div class="container">
        <div class="kicker fade-up">先说扎心的</div>
        <h2 class="sec-title fade-up">做公众号赚不到钱的人，问题高度集中在三点</h2>
        <p class="sec-lead fade-up">我见过大量半途而废的账号，死因几乎是一样的。先看看你中了几条。</p>
        <div class="grid grid-3 stagger">
          <div class="card fade-up">
            <span class="pain-mark">死因一</span>
            <h3>纯自嗨，当日记写</h3>
            <p>写自己想写的，不写读者想看的。数据一直起不来，写着写着就放弃了。</p>
            <p class="fix">→ 课程第 2、7 章：面向甲方创作 + 面向用户写作</p>
          </div>
          <div class="card fade-up">
            <span class="pain-mark">死因二</span>
            <h3>数据忽高忽低</h3>
            <p>一篇 1 万、下一篇 300。甲方看到这种波动，根本不敢投你。</p>
            <p class="fix">→ 课程第 5、8 章：选题方法论 + 加热维稳打法</p>
          </div>
          <div class="card fade-up">
            <span class="pain-mark">死因三</span>
            <h3>太要脸，等单上门</h3>
            <p>不开互选、不找号主、不发邮件自荐。前期的商单都是主动要来的，不是等来的。</p>
            <p class="fix">→ 课程第 9 章：商单三渠道 + 自荐模板</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 为什么是现在 ============ -->
    <section>
      <div class="container">
        <div class="kicker fade-up">为什么是 AI 公众号，为什么是现在</div>
        <h2 class="sec-title fade-up">这可能是普通人做自媒体、做 AI 最好的窗口期</h2>
        <div class="grid grid-2 stagger">
          <div class="card fade-up"><h3>平台不饱和</h3><p>AI 是新赛道，竞争度远低于情感、职场、母婴等老赛道。同样质量的内容，更容易被推荐出来。</p></div>
          <div class="card fade-up"><h3>甲方投放量非常大</h3><p>AI 公司融资多、抢用户急，预算充足。去翻翻头部 AI 号的商单频率，投放需求摆在明面上。</p></div>
          <div class="card fade-up"><h3>内容制作难度不大</h3><p>不需要出镜、不需要剪辑团队。深度用 AI + 一套正确的方法，一个人就是一条生产线。</p></div>
          <div class="card fade-up"><h3>AI 还有很长的路要走</h3><p>这不是三个月过气的热点。未来几年会持续出现新产品、新话题、新预算——素材和商单都不会断。</p></div>
        </div>
      </div>
    </section>

    <!-- ============ 方法论亮点 ============ -->
    <section class="alt">
      <div class="container">
        <div class="kicker fade-up">你将学到的核心方法</div>
        <h2 class="sec-title fade-up">五套验证过的打法，不是理论，是 SOP</h2>
        <p class="sec-lead fade-up">每一套都在真实账号上反复跑过，拆解成你照着做就能执行的步骤。</p>

        <div class="method fade-up">
          <div class="method-num">01</div>
          <div>
            <h3>低粉爆款选题法（全课核心）</h3>
            <p>选题决定一篇内容数据的 60%。教你找到"别人已经帮你做好 A/B 测试"的选题：五步验证流程 + 评论区挖掘 + 联想词 + 预判式布局，把碰运气变成走流程。</p>
            <p class="quote">"一条有可能是概率，两条可能是并集，三条大概率就是规律。"</p>
          </div>
        </div>
        <div class="method fade-up">
          <div class="method-num">02</div>
          <div>
            <h3>选题证明题制度</h3>
            <p>动笔之前，用论据 1、2、3 证明这个选题会火，再加三问自检。写了不该写的文章，是新手最大的时间黑洞——这个制度帮你把它堵死。</p>
          </div>
        </div>
        <div class="method fade-up">
          <div class="method-num">03</div>
          <div>
            <h3>标题心理学</h3>
            <p>公众号的消息列表里，标题几乎是唯一入口，用户只给你 0.8 秒。五种让大脑"刹车"的心理力量 + 每次起标题的固定流程 + 杀伤力自测。</p>
          </div>
        </div>
        <div class="method fade-up">
          <div class="method-num">04</div>
          <div>
            <h3>加热维稳打法</h3>
            <p>充值走哪个入口、时长选多少、金额怎么分段、被拒的两个原因怎么规避——全部是真金白银测出来的结论，实测投产比约 1:10。这是维持"甲方敢投你"的数据稳定性的关键。</p>
          </div>
        </div>
        <div class="method fade-up">
          <div class="method-num">05</div>
          <div>
            <h3>商单获取与商稿写作</h3>
            <p>商单的三个来源、两类商稿的不同打法、合规红线清单、和甲方沟通的话术。从接到 Brief 到交付一篇甲方和读者都满意的稿子，完整走一遍。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 大纲 ============ -->
    <section id="outline">
      <div class="container">
        <div class="kicker fade-up">课程大纲</div>
        <h2 class="sec-title fade-up">12 章完整体系，从认知到收钱</h2>
        <p class="sec-lead fade-up nowrap">每章讲义 + 实操作业，最后一章附 90 天行动计划。学完的标准不是"看懂了"，是账号做起来了。</p>
        <div class="outline-wrap fade-up">
          <table class="outline">
            <thead>
              <tr><th>章节</th><th>主题</th><th class="hide-m">解决什么问题</th></tr>
            </thead>
            <tbody>
              <tr><td class="ch">第 1 章</td><td class="name">认知篇</td><td class="hide-m">为什么是 AI 垂类公众号，收入公式怎么拆</td></tr>
              <tr><td class="ch">第 2 章</td><td class="name">定位篇</td><td class="hide-m">面向甲方创作：方向、调性、用户画像、对标账号</td></tr>
              <tr><td class="ch">第 3 章</td><td class="name">机制篇</td><td class="hide-m">推荐机制与爆款心理学，理解流量从哪来</td></tr>
              <tr><td class="ch">第 4 章</td><td class="name">选题篇 · 上</td><td class="hide-m">信息源系统搭建，第一时间抓到热点</td></tr>
              <tr><td class="ch">第 5 章</td><td class="name">选题篇 · 下<span class="core-tag">全课核心</span></td><td class="hide-m">低粉爆款、评论区、联想词、预判、选题证明题</td></tr>
              <tr><td class="ch">第 6 章</td><td class="name">标题篇</td><td class="hide-m">五种心理力量 + 起标题固定流程</td></tr>
              <tr><td class="ch">第 7 章</td><td class="name">创作篇</td><td class="hide-m">大纲→初稿→终稿 SOP + AI 辅助生产七步工作流</td></tr>
              <tr><td class="ch">第 8 章</td><td class="name">加热篇<span class="core-tag">独家实测</span></td><td class="hide-m">冷启动与数据维稳，全部实测结论</td></tr>
              <tr><td class="ch">第 9 章</td><td class="name">变现篇</td><td class="hide-m">商单三渠道、两类商稿写法、甲方沟通话术</td></tr>
              <tr><td class="ch">第 10 章</td><td class="name">复盘篇</td><td class="hide-m">现象≠结论的复盘方法 + 90 天行动计划</td></tr>
              <tr><td class="ch">附录</td><td class="name">SOP 工具包</td><td class="hide-m">生产清单、证明题模板、信息源清单、加热速查卡</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ============ 适合谁 ============ -->
    <section class="alt">
      <div class="container">
        <div class="kicker fade-up">报名之前</div>
        <h2 class="sec-title fade-up">这门课适合谁，不适合谁</h2>
        <div class="grid grid-2 stagger">
          <div class="card fade-up">
            <h3 class="fit-title fit-title-yes">适合你，如果</h3>
            <ul class="fit-list fit-yes">
              <li>写过公众号，有基本的发文和后台操作经验</li>
              <li>想做副业或转型自媒体，愿意每周投入 8-10 小时执行</li>
              <li>已经在做 AI 账号，但数据不稳、没接到过商单</li>
              <li>对 AI 工具有兴趣，愿意深度使用并写出实测内容</li>
              <li>相信方法和复盘，而不是等灵感和运气</li>
            </ul>
          </div>
          <div class="card fade-up">
            <h3 class="fit-title fit-title-no">不适合你，如果</h3>
            <ul class="fit-list fit-no">
              <li>完全没做过公众号（本期暂不接收零基础学员）</li>
              <li>想找"躺赚"项目，不打算动手写、动手测</li>
              <li>期待一夜暴富——3 个月月入 20 万是跑通方法后的结果，不是承诺</li>
              <li>完全不愿意花钱使用 AI 工具（工具费是生产资料）</li>
              <li>只想收藏课程，不做作业</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 讲师 ============ -->
    <section>
      <div class="container">
        <div class="kicker fade-up">谁在教你</div>
        <h2 class="sec-title fade-up">一个靠新媒体赚到过 1000 万的实操者</h2>
        <div class="card teacher-card fade-up">
          <p>我做新媒体赚过的钱超过 1000 万。从 2017 年开始做自媒体，后来自己的工作和创业都是从新媒体出发，目前公司近百人团队。</p>
          <p>从 3 个月前开始转 AI 垂类新媒体以来，3 个月做到了月收入 20 万左右。</p>
          <p>这门课里没有从别处搬来的理论。每一条方法——低粉爆款怎么找、加热金额怎么分段、商稿红线在哪——都是我们团队在真实账号上花时间、花钱验证过的结论，包括踩过的坑和失败的复盘。</p>
          <p>课程上线前，选题和加热这两套方法我先教给了几个人：他们的收入已经有了显著提升。现在，我把从选题到变现的完整链路整理成了这 12 章。</p>
        </div>
      </div>
    </section>

    <!-- ============ FAQ ============ -->
    <section class="alt">
      <div class="container">
        <div class="kicker fade-up">常见问题</div>
        <h2 class="sec-title fade-up">你可能想问</h2>
        <details class="fade-up">
          <summary>我完全没做过公众号，能报吗？</summary>
          <p>暂时不能。本期陪伴营只接受写过公众号的学员——你需要有基本的发文和后台操作经验，我们的时间才能都花在选题、数据和变现这些真正值钱的问题上。完全零基础的朋友，建议先自己开号发几篇文章，下期再来。</p>
        </details>
        <details class="fade-up">
          <summary>现在入场 AI 赛道，会不会已经晚了？</summary>
          <p>AI 垂类目前仍处在"内容供给跟不上甲方预算"的阶段：平台竞争度低、投放需求大。而且 AI 行业本身每隔几周就有新产品新话题，选题红利是持续滚动的。越晚入场竞争越多，这是事实——所以答案是：不晚，但别再等。</p>
        </details>
        <details class="fade-up">
          <summary>课程是什么形式？"陪伴"具体指什么？</summary>
          <p>课程本体是 12 章图文讲义（网页版随时看），购买后长期有效、持续更新。陪伴指的是一整年的服务：学员群内随时答疑、最新运营知识同步，外加 1 年内 2-3 次一对一电话沟通——你做账号路上遇到的具体问题（定位卡住了、数据掉了、商单怎么报价），都有人陪你解决。</p>
        </details>
        <details class="fade-up">
          <summary>需要额外花什么钱？</summary>
          <p>两块：AI 工具会员（生产资料，每月几百元量级，按你的方向选择）和加热预算（可选，单篇一两百元起，实测投产比约 1:10）。课程里会教你每一分钱怎么花在刀刃上。</p>
        </details>
        <details class="fade-up">
          <summary>和市面上其他公众号课有什么区别？</summary>
          <p>大部分课教"怎么写"，这门课教"怎么赚"：从第一天起就面向甲方做账号。而且所有方法都附带我们自己账号的验证过程——包括加热投产比这种别人不会告诉你的实测数据，和"标签混乱导致数据翻车"这种真实失败复盘。</p>
        </details>
      </div>
    </section>

    <!-- ============ 价格 ============ -->
    <section id="price">
      <div class="container">
        <div style="text-align:center">
          <div class="kicker fade-up">报名</div>
          <h2 class="sec-title fade-up">一单商稿的收入，覆盖整门课</h2>
          <p class="sec-lead center fade-up">AI 垂类公众号单篇商稿的市场价通常在几千元。这门课教你的，是持续接单的完整系统。</p>
        </div>
        <div class="price-card fade-up">
          <div class="price-old">原价 ¥3980 / 年</div>
          <div class="price-now"><em>¥</em>1980<em> / 年</em></div>
          <div class="price-note">首期学员价 · 含一整年全部陪伴权益 · 随期数上涨</div>
          <div class="includes-label">课程内容</div>
          <ul class="includes">
            <li>12 章完整图文讲义，长期有效、持续更新（含 SOP 工具包：生产清单 / 选题证明题模板 / 加热速查卡 / 信息源与对标账号清单 / 商稿红线与甲方话术）</li>
            <li>AI 垂类公众号运营的最新知识分享——方法有迭代、平台有变化，第一时间同步给你</li>
          </ul>
          <div class="includes-label">陪伴服务（一整年）</div>
          <ul class="includes">
            <li>加入学员群，一整年内有任何问题，我随时答疑</li>
            <li>1 年内 2-3 次一对一电话沟通（每次 1 小时内），定位、选题、报价都可以聊</li>
          </ul>
          <a class="btn btn-primary btn-block" @click="openModal('pay')">扫码报名 · 锁定首期价</a>
          <div class="guarantee">报名前有任何疑问，<a class="link" @click="openModal('wx')">点这里加微信直接问我</a></div>
        </div>
      </div>
    </section>

    <footer class="camp-footer">
      <div class="container">AI垂类公众号陪伴营 · 从选题到商业变现</div>
    </footer>

    <!-- ============ 微信二维码弹窗 ============ -->
    <Teleport to="body">
      <Transition name="camp-modal">
        <div v-if="activeModal" class="camp-modal-backdrop" @click.self="closeModal">
          <div class="camp-modal-box" role="dialog" aria-modal="true">
            <button class="camp-modal-close" @click="closeModal" aria-label="关闭">×</button>
            <template v-if="activeModal === 'pay'">
              <h3>微信扫码支付</h3>
              <div class="camp-pay-summary">
                <div class="camp-pay-package">AI 垂类公众号实战营</div>
                <div class="camp-pay-amount">¥1980</div>
                <div class="camp-pay-benefit">1 年课程陪伴权益</div>
              </div>
              <p v-if="payError" class="camp-pay-error">{{ payError }}</p>
              <p v-else-if="payLoading" class="camp-pay-loading">正在生成微信支付二维码…</p>
              <template v-else>
                <div class="camp-qr"><canvas ref="payCanvas"></canvas></div>
                <p class="camp-qr-tip">请使用微信扫一扫完成支付</p>
                <p class="camp-qr-sub">支付成功后会自动进入课程资料</p>
              </template>
              <p v-if="payPolling" class="camp-pay-wait">支付完成后请不要刷新或离开页面，系统正在自动确认支付结果。</p>
            </template>
            <template v-else>
              <h3>扫码添加微信</h3>
              <p>备注「实战营」，课程问题随便问</p>
              <div class="camp-qr">
                <img src="/brand/wechat-qr.jpg" alt="微信二维码" />
              </div>
            </template>
            <p v-if="activeModal === 'pay'" class="camp-modal-alt">
              <a @click="switchModal('wx')">想先咨询？点这里加微信</a>
            </p>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ============ 登录弹窗（登录成功后继续报名流程） ============ -->
    <PhoneLoginModal v-model:open="loginOpen" @success="onLoginSuccess" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QRCode from 'qrcode'
import { post, get } from '@/api/api'
import { useUserStore } from '@/stores/user'
import PhoneLoginModal from '@/components/auth/PhoneLoginModal.vue'
import { useBodyScrollLock } from '@/utils/bodyScrollLock'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const root = ref(null)

const navScrolled = ref(false)
const onScroll = () => { navScrolled.value = window.scrollY > 12 }

const activeModal = ref('')
const payCanvas = ref(null)
const payLoading = ref(false)
const payPolling = ref(false)
const payError = ref('')
const campOrderNo = ref('')
let payTimer = null

const stopPayPolling = () => {
  if (payTimer) window.clearInterval(payTimer)
  payTimer = null
  payPolling.value = false
}

// 用户取消支付时关闭未支付订单，让二维码立即失效（尽力而为，不阻塞 UI）。
const closeCampOrder = () => {
  if (!campOrderNo.value) return
  const no = campOrderNo.value
  campOrderNo.value = ''
  post(`/credits/purchase/close/${no}`).catch(() => {})
}

const createCampOrder = async () => {
  if (userStore.hasProduct('practical_camp')) {
    router.push('/courses')
    return
  }
  payLoading.value = true
  payError.value = ''
  try {
    const res = await post('/credits/products/practical_camp')
    campOrderNo.value = res.data.out_trade_no
    // 必须先关掉 loading，二维码 <canvas>（v-if="!payLoading"）才会挂载，
    // 否则 payCanvas.value 还是 null，toCanvas 画到游离画布上 → 空白码。
    payLoading.value = false
    await nextTick()
    await QRCode.toCanvas(payCanvas.value, res.data.code_url, { width: 220, margin: 1 })
    payPolling.value = true
    payTimer = window.setInterval(async () => {
      try {
        const status = await get(`/credits/purchase/status/${res.data.out_trade_no}`)
        if (status.data.status === 'PAID') {
          campOrderNo.value = ''
          stopPayPolling()
          await userStore.fetchUser()
          activeModal.value = ''
          router.push('/courses')
        }
      } catch { /* 后端回调可能仍在处理，下次轮询继续 */ }
    }, 2500)
  } catch (error) {
    payError.value = error.response?.data?.detail || '创建支付订单失败，请稍后重试'
    payLoading.value = false
  }
}

// 未登录时先在页内弹登录框，登录成功后继续报名流程，不再跳转 Landing 登录。
const loginOpen = ref(false)

const onLoginEntry = () => {
  if (userStore.isAuthenticated) {
    userStore.logout()
    return
  }
  loginOpen.value = true
}

const onLoginSuccess = () => {
  openModal('pay')
}

const openModal = async (id) => {
  // 未登录先走页内登录：不置 activeModal，避免弹窗态（及滚动锁）残留
  if (id === 'pay' && !userStore.isAuthenticated) {
    loginOpen.value = true
    return
  }
  activeModal.value = id
  if (id === 'pay') await createCampOrder()
}
const closeModal = () => { stopPayPolling(); closeCampOrder(); activeModal.value = '' }
const switchModal = (id) => { stopPayPolling(); closeCampOrder(); activeModal.value = id }

const goLanding = () => { router.push('/landing') }

const onKeydown = (e) => { if (e.key === 'Escape') closeModal() }

// 弹窗打开时锁定 body 滚动（计数式共享锁，卸载自动释放，见 utils/bodyScrollLock）
useBodyScrollLock(() => Boolean(activeModal.value) || loginOpen.value)

/* ── 滚动进入动画 ── */
let fadeObserver = null

onMounted(async () => {
  window.addEventListener('scroll', onScroll, { passive: true })
  document.addEventListener('keydown', onKeydown)
  onScroll()

  if (route.query.openPay === '1') {
    await openModal('pay')
  }

  await nextTick()
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && root.value) {
    fadeObserver = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('in')
          fadeObserver.unobserve(e.target)
        }
      }),
      { threshold: 0.12 }
    )
    root.value.querySelectorAll('.fade-up').forEach((el) => fadeObserver.observe(el))
  } else if (root.value) {
    root.value.querySelectorAll('.fade-up').forEach((el) => el.classList.add('in'))
  }
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
  document.removeEventListener('keydown', onKeydown)
  if (fadeObserver) fadeObserver.disconnect()
  stopPayPolling()
  closeCampOrder()
})
</script>

<style scoped>
/* =========================================================
   实战营课程介绍页 — 对齐 IP罗盘 设计体系
   字体 / 配色 / 圆角 / 阴影 全部复用全局 token
   ========================================================= */
.camp {
  /* 字体（与项目 tailwind fontFamily 完全一致，避免与站内其他页面串字体） */
  --serif: 'Source Han Serif SC', 'Songti SC', 'STSong', 'Noto Serif SC', Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', Inter, 'Helvetica Neue', sans-serif;

  /* 背景 / 文字 */
  --bg-000:#ffffff;
  --bg-100:#FAF9F5;   /* paper */
  --bg-200:#F5F1EB;   /* ivory */
  --bg-300:#EFEAE0;   /* bone  */
  --bg-line:#E4DDCE;  /* line  */
  --text-100:#1F1F1E; /* ink   */
  --text-200:#3A3935; /* ink-2 */
  --text-400:#6B6862; /* ink-3 */
  /* 强调色 */
  --accent-brand:#CC785C; /* clay */
  --accent-deep:#A85A40;  /* clay-deep */
  --accent-soft:#E9B79E;  /* clay-soft */
  --accent-tint:#F5E2D5;  /* clay-tint */
  --success:#5C8A5C;      /* leaf */
  --danger:#B85450;       /* crimson */
  --border-light:rgba(31,31,30,0.06);
  --border-medium:rgba(31,31,30,0.10);
  --shadow-sm:0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04);
  --shadow-md:0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04);
  --shadow-lg:0 12px 32px rgba(31,31,30,.08), 0 0 0 1px rgba(31,31,30,.04);
  --shadow-clay:0 8px 24px rgba(204,120,92,.18);
  --radius-sm:6px; --radius-md:10px; --radius-lg:16px; --radius-xl:24px;
  --container:960px;

  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.7;
  background: var(--bg-200);
  background-image:
    radial-gradient(rgba(204,120,92,.022) 1px, transparent 1px),
    radial-gradient(rgba(63,92,82,.018) 1px, transparent 1px);
  background-size: 28px 28px, 44px 44px;
  background-position: 0 0, 14px 22px;
  color: var(--text-200);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  min-height: 100vh;
}
.camp * { box-sizing: border-box; }
.camp ::selection { background: var(--accent-tint); color: var(--accent-deep); }
.camp a { color: inherit; text-decoration: none; cursor: pointer; }

.container { max-width: var(--container); margin: 0 auto; padding: 0 32px; }
.camp section { padding: 80px 0; }

.kicker { font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent-deep); margin-bottom: 12px; }
.sec-title { font-family: var(--serif); font-size: clamp(24px, 3.2vw, 32px); font-weight: 600; color: var(--text-100); letter-spacing: -.01em; margin: 0 0 14px; line-height: 1.32; }
.sec-lead { font-size: 15.5px; color: var(--text-400); max-width: 640px; margin-bottom: 44px; line-height: 1.75; }
.sec-lead.center { margin-left: auto; margin-right: auto; }
/* 桌面端强制单行，避免短句末尾孤字换行；移动端保持自然换行防溢出 */
@media (min-width: 821px) {
  .sec-lead.nowrap { white-space: nowrap; }
}

/* Nav */
.camp-nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 50; height: 64px; display: flex; align-items: center;
  background: rgba(245,241,235,.72);
  backdrop-filter: saturate(150%) blur(14px);
  -webkit-backdrop-filter: saturate(150%) blur(14px);
  border-bottom: 1px solid transparent; transition: background .25s ease, border-color .25s ease;
}
.camp-nav.scrolled { background: rgba(245,241,235,.94); border-bottom-color: var(--bg-line); }
.camp-nav-inner { width: 100%; max-width: 1180px; margin: 0 auto; padding: 0 32px; display: flex; align-items: center; gap: 32px; }
.brand { display: flex; align-items: center; gap: 10px; font-family: var(--serif); font-weight: 700; font-size: 18px; color: var(--text-100); letter-spacing: .02em; }
.brand-logo { width: 28px; height: 28px; border-radius: 8px; display: block; box-shadow: 0 8px 18px rgba(204,120,92,.18); flex-shrink: 0; }
.brand-name { transition: color .15s; }
.brand:hover .brand-name { color: var(--accent-brand); }
.camp-nav-links { display: flex; gap: 28px; margin-left: 16px; }
.camp-nav-links a { font-size: 14px; color: var(--text-200); font-weight: 500; transition: color .15s; }
.camp-nav-links a:hover { color: var(--accent-deep); }
.camp-nav-cta { margin-left: auto; display: flex; gap: 10px; align-items: center; }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px; font-size: 15px; font-weight: 500;
  border-radius: var(--radius-md); padding: 12px 28px; cursor: pointer; border: 1px solid transparent;
  text-decoration: none; font-family: inherit; white-space: nowrap; transition: transform .15s ease, background .15s ease, box-shadow .15s ease, border-color .15s ease; letter-spacing: .01em;
}
.camp-nav-cta .btn { padding: 0 18px; height: 40px; font-size: 14px; }
.btn-primary { background: var(--accent-brand); color: #fff; box-shadow: var(--shadow-clay); }
.btn-primary:hover { background: var(--accent-deep); transform: translateY(-1px); box-shadow: 0 10px 26px rgba(204,120,92,.28); }
.btn-primary:active { transform: translateY(0); }
.btn-ghost { background: var(--bg-000); color: var(--text-100); border-color: var(--border-medium); }
/* <a> 版按钮要盖过 .camp a { color: inherit }（特异性更高），否则文字会继承深墨色变成褐字 */
.camp a.btn-primary { color: #fff; }
.camp a.btn-ghost { color: var(--text-100); }
.btn-ghost:hover { border-color: rgba(31,31,30,.2); box-shadow: var(--shadow-sm); transform: translateY(-1px); }
.btn-block { width: 100%; max-width: 320px; margin-top: 4px; }
.btn-arrow { display: inline-block; transition: transform .2s; }
.btn:hover .btn-arrow { transform: translateX(3px); }

/* hero */
.hero { position: relative; padding: 152px 0 84px; text-align: center; overflow: hidden; }
.hero-decor { position: absolute; inset: 0; pointer-events: none; z-index: 0; animation: camp-float 16s ease-in-out infinite; }
@keyframes camp-float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
.hero .container { position: relative; z-index: 1; }
.hero-badge { display: inline-block; font-size: 13px; color: var(--accent-deep); background: rgba(204,120,92,.1); border-radius: 999px; padding: 5px 16px; margin-bottom: 24px; font-weight: 600; }
.hero h1 { font-family: var(--serif); font-size: clamp(30px, 5vw, 50px); font-weight: 500; color: var(--text-100); letter-spacing: -.01em; line-height: 1.25; max-width: 820px; margin: 0 auto; }
.hero h1 strong { font-weight: 700; }
.hero .subtitle { font-size: 16.5px; color: var(--text-400); max-width: 640px; margin: 22px auto 0; line-height: 1.8; }
.hero-cta { margin-top: 38px; display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.stats { display: flex; justify-content: center; gap: 56px; flex-wrap: wrap; margin-top: 60px; }
.stat-value { font-family: var(--serif); font-size: 38px; font-weight: 600; color: var(--text-100); letter-spacing: -.01em; }
.stat-value em { font-style: normal; font-size: 19px; color: var(--text-400); font-weight: 400; }
.stat-label { font-size: 13px; color: var(--text-400); letter-spacing: .04em; margin-top: 6px; }

/* cards */
.grid { display: grid; gap: 18px; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.card { background: var(--bg-000); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow-sm); transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
.card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); border-color: var(--border-medium); }
.card h3 { font-family: var(--serif); font-size: 18px; font-weight: 600; color: var(--text-100); margin: 0 0 8px; line-height: 1.4; }
.card p { font-size: 14.5px; color: var(--text-200); margin: 0; line-height: 1.72; }
.card p + p { margin-top: 10px; }

.alt { background: var(--bg-100); border-top: 1px solid var(--border-light); border-bottom: 1px solid var(--border-light); }

/* pain */
.pain-mark { display: inline-block; font-size: 11px; font-weight: 600; color: var(--danger); background: rgba(184,84,80,.08); border-radius: var(--radius-sm); padding: 3px 10px; margin-bottom: 14px; letter-spacing: .02em; }
.fix { font-size: 13.5px; color: var(--success); margin-top: 12px; }

/* method list */
.method { display: flex; gap: 22px; background: var(--bg-000); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 28px 30px; margin-bottom: 14px; box-shadow: var(--shadow-sm); transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
.method:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); border-color: var(--border-medium); }
.method-num { font-family: var(--serif); font-size: 24px; font-weight: 600; color: var(--accent-brand); flex-shrink: 0; width: 40px; font-variant-numeric: tabular-nums; line-height: 1.2; }
.method h3 { font-family: var(--serif); font-size: 17px; font-weight: 600; color: var(--text-100); margin: 0 0 6px; }
.method p { font-size: 14.5px; margin: 0; line-height: 1.72; }
.method .quote { font-size: 13.5px; color: var(--text-400); margin-top: 10px; border-left: 2px solid var(--accent-soft); padding-left: 14px; font-style: italic; }

/* outline table — 柔和纸张卡片，避免生硬的黑色表格外框 */
.outline-wrap {
  margin-top: 8px;
  overflow: hidden;
  background: rgba(255,255,255,.54);
  border: 1px solid var(--bg-line);
  border-radius: var(--radius-lg);
  box-shadow: 0 12px 32px rgba(74,55,39,.045), 0 1px 2px rgba(74,55,39,.025);
}
.outline { width: 100%; border-collapse: collapse; border: 0; background: transparent; box-shadow: none; }
.outline thead th {
  text-align: left; font-size: 12px; font-weight: 600; color: var(--text-400); text-transform: uppercase;
  letter-spacing: .06em; padding: 14px 22px; border: 0; border-bottom: 1px solid var(--bg-line);
  background: rgba(245,241,235,.72);
}
.outline tbody td {
  padding: 17px 22px; font-size: 14.5px; border: 0; border-bottom: 1px solid rgba(228,221,206,.72);
  vertical-align: middle; color: var(--text-200); background: transparent;
  transition: background .18s ease, color .18s ease;
}
.outline tbody tr:last-child td { border-bottom: 0; }
.outline tbody tr:hover td { background: rgba(204,120,92,.055); }
.outline tbody tr:hover td:first-child { box-shadow: inset 3px 0 0 var(--accent-soft); color: var(--accent-deep); }
.outline .ch { color: var(--text-400); font-size: 13px; white-space: nowrap; width: 110px; }
.outline .name { font-family: var(--serif); font-weight: 600; color: var(--text-100); white-space: nowrap; }
.core-tag { display: inline-block; font-size: 11px; font-weight: 600; color: var(--accent-deep); background: rgba(204,120,92,.12); border-radius: 999px; padding: 2px 9px; margin-left: 10px; vertical-align: 1px; font-family: var(--sans); }

/* fit */
.fit-title { font-family: var(--serif); font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.fit-title-yes { color: var(--success); }
.fit-title-no { color: var(--text-400); }
.fit-list { list-style: none; padding: 0; margin: 8px 0 0; }
.fit-list li { padding: 11px 0 11px 30px; position: relative; font-size: 14.5px; border-bottom: 1px solid var(--border-light); color: var(--text-200); }
.fit-list li:last-child { border-bottom: none; }
.fit-yes li::before { content: "✓"; position: absolute; left: 2px; color: var(--success); font-weight: 700; }
.fit-no li::before { content: "✕"; position: absolute; left: 2px; color: var(--text-400); font-weight: 700; }

/* teacher */
.teacher-card { padding: 36px 38px; }
.teacher-card p { font-size: 15.5px; color: var(--text-200); line-height: 1.85; }
.teacher-card p + p { margin-top: 14px; }

/* faq */
.camp details { background: var(--bg-000); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 18px 24px; margin-bottom: 12px; box-shadow: var(--shadow-sm); transition: border-color .2s ease, box-shadow .2s ease; }
.camp details:hover { border-color: var(--border-medium); box-shadow: var(--shadow-md); }
.camp summary { font-family: var(--serif); font-size: 16px; font-weight: 600; color: var(--text-100); cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.camp summary::-webkit-details-marker { display: none; }
.camp summary::after { content: "+"; font-size: 22px; font-weight: 300; color: var(--accent-brand); transition: transform .2s ease; flex-shrink: 0; }
.camp details[open] summary::after { content: "−"; }
.camp details p { font-size: 14.5px; margin-top: 12px; color: var(--text-200); line-height: 1.75; animation: camp-reveal .28s ease; }
@keyframes camp-reveal { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

/* pricing */
.price-card { background: var(--bg-000); border: 1px solid var(--border-medium); border-radius: var(--radius-xl); box-shadow: var(--shadow-lg); padding: 48px 44px; max-width: 560px; margin: 8px auto 0; text-align: center; }
.price-old { font-size: 16px; color: var(--text-400); text-decoration: line-through; }
.price-now { font-family: var(--serif); font-size: 56px; font-weight: 600; color: var(--text-100); letter-spacing: -.02em; margin: 4px 0 2px; }
.price-now em { font-style: normal; font-size: 24px; color: var(--text-400); font-weight: 400; }
.price-note { font-size: 13px; color: var(--accent-deep); margin-bottom: 30px; }
.includes-label { font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--accent-deep); text-align: left; max-width: 400px; margin: 0 auto 8px; }
.includes { text-align: left; margin: 0 auto 24px; max-width: 400px; list-style: none; padding: 0; }
.includes li { padding: 9px 0 9px 28px; position: relative; font-size: 14.5px; border-bottom: 1px dashed var(--border-light); line-height: 1.6; }
.includes li:last-child { border-bottom: none; }
.includes li::before { content: "✓"; position: absolute; left: 2px; top: 9px; color: var(--accent-brand); font-weight: 700; }
.guarantee { font-size: 13px; color: var(--text-400); margin-top: 20px; }
.guarantee .link { color: var(--accent-deep); border-bottom: 1px solid var(--accent-soft); }
.guarantee .link:hover { color: var(--accent-brand); }

/* footer */
.camp-footer { padding: 40px 0 60px; text-align: center; font-size: 13px; color: var(--text-400); border-top: 1px solid var(--border-light); background: var(--bg-200); }

/* fade-up 进场动画 */
.fade-up { opacity: 0; transform: translateY(24px); transition: opacity .7s cubic-bezier(.2,0,0,1), transform .7s cubic-bezier(.2,0,0,1); }
.fade-up.in { opacity: 1; transform: none; }
.stagger .fade-up:nth-child(1) { transition-delay: 0s; }
.stagger .fade-up:nth-child(2) { transition-delay: .08s; }
.stagger .fade-up:nth-child(3) { transition-delay: .16s; }
.stagger .fade-up:nth-child(4) { transition-delay: .24s; }
@media (prefers-reduced-motion: reduce) {
  .fade-up { opacity: 1; transform: none; transition: none; }
  .hero-decor { animation: none; }
}

@media (max-width: 820px) {
  .container { padding: 0 20px; }
  .camp-nav-inner { padding: 0 20px; }
  .camp-nav-links { display: none; }
  .camp section { padding: 56px 0; }
  .hero { padding: 112px 0 52px; }
  .grid-3, .grid-2 { grid-template-columns: 1fr; }
  .stats { gap: 32px; }
  .outline .hide-m { display: none; }
  .outline .ch { width: auto; }
  .price-card { padding: 36px 24px; }
}
</style>

<!-- 弹窗 Teleport 到 body，使用全局 token，保证视口居中 + 背景模糊 -->
<style scoped>
.camp-modal-backdrop {
  position: fixed; inset: 0; z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 24px;
  background: rgba(31,31,30,.5);
  backdrop-filter: blur(8px) saturate(120%);
  -webkit-backdrop-filter: blur(8px) saturate(120%);
  overflow-y: auto;
}
.camp-modal-box {
  position: relative; width: 100%; max-width: 360px; margin: auto;
  background: var(--paper, #FAF9F5); border-radius: var(--r-xl, 24px);
  box-shadow: 0 24px 60px rgba(31,31,30,.24), 0 0 0 1px rgba(31,31,30,.06);
  padding: 40px 36px 34px; text-align: center;
}
.camp-modal-close {
  position: absolute; top: 12px; right: 14px; width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; line-height: 1; color: var(--ink-3, #6B6862);
  background: none; border: none; border-radius: 8px; cursor: pointer; transition: background .15s, color .15s;
}
.camp-modal-close:hover { background: var(--bone, #EFEAE0); color: var(--ink, #1F1F1E); }
.camp-modal-box h3 { font-family: 'Source Han Serif SC', 'Songti SC', 'Noto Serif SC', Georgia, serif; font-size: 19px; font-weight: 600; color: var(--ink, #1F1F1E); margin: 0 0 6px; }
.camp-modal-box p { font-size: 13.5px; color: var(--ink-3, #6B6862); margin: 0 0 20px; line-height: 1.6; }
.camp-pay-summary { margin: 14px 0 16px; text-align: center; }
.camp-pay-package { font-size: 15px; font-weight: 600; color: var(--ink-2, #3A3935); }
.camp-pay-amount { margin-top: 4px; font-family: var(--serif, 'Source Han Serif SC', Georgia, serif); font-size: 30px; font-weight: 700; line-height: 1.2; color: var(--clay, #CC785C); }
.camp-pay-benefit,
.camp-qr-sub { margin-top: 4px !important; margin-bottom: 0 !important; font-size: 13px !important; color: var(--ink-4, #8A8680) !important; }
.camp-pay-loading { margin: 30px 0 !important; }
.camp-qr {
  box-sizing: content-box; width: 220px; margin: 0 auto; padding: 10px;
  background: #fff; border: 1px solid var(--line, #E4DDCE); border-radius: var(--r-md, 10px);
}
.camp-qr img,
.camp-qr canvas { width: 100%; height: auto; display: block; border-radius: 6px; }
.camp-qr-tip { margin: 14px 0 0 !important; font-size: 14px !important; color: var(--ink-2, #3A3935) !important; }
.camp-modal-alt { margin: 18px 0 0; }
.camp-modal-alt a { font-size: 13.5px; color: var(--clay-deep, #A85A40); cursor: pointer; border-bottom: 1px solid var(--clay-soft, #E9B79E); }
.camp-modal-alt a:hover { color: var(--clay, #CC785C); }
.camp-pay-wait { margin: 8px 0 0 !important; color: var(--clay-deep, #A85A40) !important; font-size: 12.5px !important; }
.camp-pay-error { color: #b43b33 !important; }

/* 弹窗过渡 */
.camp-modal-enter-active, .camp-modal-leave-active { transition: opacity .22s ease; }
.camp-modal-enter-from, .camp-modal-leave-to { opacity: 0; }
.camp-modal-enter-active .camp-modal-box { transition: transform .28s cubic-bezier(.2,.8,.2,1), opacity .28s ease; }
.camp-modal-enter-from .camp-modal-box { transform: translateY(16px) scale(.98); opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .camp-modal-enter-active, .camp-modal-leave-active,
  .camp-modal-enter-active .camp-modal-box { transition: none; }
}
</style>
