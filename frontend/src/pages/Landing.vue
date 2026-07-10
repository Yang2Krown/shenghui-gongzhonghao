<template>
  <div class="lp">
    <!-- Nav -->
    <nav :class="['nav', { scrolled: navScrolled }]">
      <div class="nav-inner">
        <a href="#" class="brand">
          <img class="brand-logo" src="/brand/ip-compass.svg" alt="IP罗盘" />
          <span class="brand-name">IP罗盘</span>
        </a>
        <div class="nav-links">
          <a href="#features">产品功能</a>
          <a href="#tools">创作工具箱</a>
          <a class="nav-camp" @click="goCamp">实战营</a>
        </div>
        <div class="nav-cta">
          <PublicLoginButton @authenticated="goToWorkspace" />
        </div>
      </div>
    </nav>

    <!-- Hero -->
    <section class="hero">
      <div class="hero-decor" aria-hidden="true">
        <svg viewBox="0 0 1400 800" preserveAspectRatio="xMidYMid slice" :style="{ position:'absolute', inset:0, width:'100%', height:'100%', opacity:.5 }">
          <g stroke="#E4DDCE" stroke-width="1" fill="none">
            <path d="M120 180 L240 240 L180 360" stroke-dasharray="3 4"/>
            <path d="M1200 120 L1280 220 L1180 320" stroke-dasharray="3 4"/>
            <path d="M1100 600 L1240 540 L1300 660" stroke-dasharray="3 4"/>
          </g>
          <g fill="#E9B79E">
            <circle cx="120" cy="180" r="3"/><circle cx="240" cy="240" r="2"/><circle cx="180" cy="360" r="2.5"/>
            <circle cx="1200" cy="120" r="2.5"/><circle cx="1280" cy="220" r="2"/><circle cx="1180" cy="320" r="3"/>
          </g>
        </svg>
      </div>
      <div class="container">
        <div class="hero-grid">
          <div>
            <div class="eyebrow"><span class="dot"></span><span>创作者内容经营 · 商业合作导航</span></div>
            <h1 class="hero-title">
              <BlurText text="创作不迷路，" :delay="60" /><br>
              商单有<RotatingText :words="['方向','判断','线索','节奏','交付']" />。
            </h1>
            <p class="hero-sub">
              陪创作者从内容经营走向商业合作：从信息选题、内容生产到潜在商单识别，把每一次创作都校准到更清晰的增长方向。
            </p>
            <div class="hero-actions">
              <MagnetButton @click="startCreationTool">
                <button class="star-btn"><span>立即开始使用 <span class="btn-arrow">→</span></span></button>
              </MagnetButton>
              <a href="#features" class="btn btn-ghost btn-lg">看罗盘怎么跑</a>
            </div>
            <div class="hero-meta">
              <span style="display:flex;align-items:center;gap:6px"><CountUp :end="20" suffix="+" :duration="1800" /><span style="font-size:13px;color:var(--ink-3)">信息源覆盖</span></span>
              <span style="display:flex;align-items:center;gap:6px"><CountUp :end="5" :duration="1500" /><span style="font-size:13px;color:var(--ink-3)">步内容流水线</span></span>
              <span style="display:flex;align-items:center;gap:6px"><CountUp :end="30" suffix="min" :duration="2000" /><span style="font-size:13px;color:var(--ink-3)">完成一篇稿</span></span>
            </div>
          </div>
          <HeroCardStack />
        </div>
      </div>
    </section>

    <!-- Pain Points -->
    <section class="section pain" id="pain">
      <div class="container">
        <div class="section-head center fade-up">
          <div class="section-tag">— AI 科技创作者的困境 —</div>
          <h2 class="section-title">你不是不努力，<br>是被无效的内容劳动耗光了时间。</h2>
          <p class="section-sub">
            做 AI 科技内容最难的不是写，而是跟上。每天都有新模型、新框架、新争议——选题、写稿、改标题、排版、发布，每一步都在消耗你的热情。
          </p>
        </div>
        <div class="pain-grid stagger-grid">
          <div v-for="(p, i) in painPoints" :key="i" class="pain-cell fade-up">
            <div class="pain-q">"</div>
            <div class="pain-text">
              <h4>{{ p[0] }}</h4>
              <p>{{ p[1] }}</p>
            </div>
          </div>
        </div>
        <div class="pain-answer fade-up">
          <p class="pain-answer-text">
            所以我们做了一件事：把<em>整条内容流水线</em>，<br>装进一套懂 AI 科技内容的公众号系统。
          </p>
        </div>
      </div>
    </section>

    <!-- Before/After Compare -->
    <CompareSection />

    <!-- Features -->
    <section class="section features" id="features">
      <div class="container">
        <div class="section-head fade-up">
          <div class="section-tag">— Core Pipeline · 内容流水线 —</div>
          <h2 class="section-title">5 步流水线，<br>把你从内容劳动里解放出来</h2>
          <p class="section-sub">
            你只需要做两件事：挑选题，审终稿。中间所有的"挖、写、改、核、优化"，AI 替你做完。
          </p>
        </div>

        <!-- Step 01 -->
        <div class="feature-block fade-up">
          <div class="fb-text">
            <div class="fb-step"><span class="num">Step 01</span>选题挖掘 · Discover</div>
            <h3>全网信息自动汇集，<br>你来挑选，AI 来深挖</h3>
            <p>系统每天自动采集全网 20+ 渠道的 AI 和科技资讯，你只需浏览、选中一条感兴趣的，AI 就会从中衍生出多个值得写的选题并评分排序。</p>
            <ul class="fb-list">
              <li><span class="li-marker">A</span><div class="li-content"><strong>从 1 条信息衍生 5 个选题</strong><span>不是过滤 100 条留 10 条，而是从每条信息里挖出新角度</span></div></li>
              <li><span class="li-marker">B</span><div class="li-content"><strong>6 维度加权评分</strong><span>痛点直击度、价值密度、传播力、差异化——数据说话，不靠感觉</span></div></li>
              <li><span class="li-marker">C</span><div class="li-content"><strong>4 视角独立评审</strong><span>技术专家、传播达人、产品经理、运营专家各自打分，避免单一偏见</span></div></li>
            </ul>
          </div>
          <div class="fb-visual">
            <div class="mk-head"><div class="t">今日推荐选题</div></div>
            <div class="mk-topics">
              <div v-for="(item, i) in topicRows" :key="i" class="trend-row" :style="i===3 ? { opacity: .55 } : {}">
                <div class="heat-bar" :style="{ background: item.color }"></div>
                <span class="rank">{{ item.rank }}</span>
                <div class="text">{{ item.text }}</div>
                <div class="meta"><span style="color:var(--clay-deep);font-weight:600;font-size:11px">🔥 {{ item.score }}</span></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 02 -->
        <div class="feature-block fade-up reverse">
          <div class="fb-text">
            <div class="fb-step"><span class="num">Step 02</span>正文创作 · Write</div>
            <h3>5 步打磨，<br>写出不像 AI 的文章</h3>
            <p>选好选题，AI 自动生成 2500 字正文。不是一次出稿，而是经过 5 个专业模块逐层打磨——初稿、金句、事实核查、联网验证、去除 AI 痕迹。</p>
            <ul class="fb-list">
              <li><span class="li-marker">A</span><div class="li-content"><strong>风格锁定</strong><span>学习你的写作风格，确保全文语气统一，读起来就像你自己写的</span></div></li>
              <li><span class="li-marker">B</span><div class="li-content"><strong>金句催化</strong><span>在开头、中段、结尾自动植入可独立传播的金句</span></div></li>
              <li><span class="li-marker">C</span><div class="li-content"><strong>联网核实</strong><span>自动搜索验证文章中的事实和数据，发现错误自动修正</span></div></li>
            </ul>
          </div>
          <div class="fb-visual">
            <div class="mk-head"><div class="t">AI 写作进度</div><div class="tag">5 步流水线</div></div>
            <div class="mk-agents">
              <div v-for="(a, i) in agentRows" :key="i" class="agent-row">
                <div :class="['agent-dot', a.status]"></div>
                <div class="agent-name">{{ a.name }}</div>
                <div class="agent-status" :style="a.status==='active' ? { color:'var(--clay-deep)' } : {}">{{ a.desc }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 03 -->
        <div class="feature-block fade-up">
          <div class="fb-text">
            <div class="fb-step"><span class="num">Step 03</span>标题优化 · Title</div>
            <h3>四个角色协作，<br>只为一个好标题</h3>
            <p>多种标题风格 × 多维评分 × 点击预测 × 智能自检。评分不达标自动优化，直到产出满意的标题。</p>
            <ul class="fb-list">
              <li><span class="li-marker">A</span><div class="li-content"><strong>12 种爆款风格</strong><span>悬念式、数字式、对比式、痛点式——覆盖主流标题套路</span></div></li>
              <li><span class="li-marker">B</span><div class="li-content"><strong>点击率预测</strong><span>模拟读者视角，预测哪个标题更吸引点击</span></div></li>
              <li><span class="li-marker">C</span><div class="li-content"><strong>智能自检</strong><span>评分不达标自动重新生成，直到 Top 3 综合评分通过</span></div></li>
            </ul>
          </div>
          <div class="fb-visual">
            <div class="mk-head"><div class="t">标题推荐</div><div class="tag">Top 3 · 已通过自检</div></div>
            <div class="mk-titles">
              <div v-for="(t, i) in titleRows" :key="i" :class="['mk-title-row', { top: t.top }]">
                <div class="mk-title-rank">{{ t.rank }}</div>
                <div class="mk-title-text">{{ t.text }}</div>
                <div class="mk-title-score"><b>{{ t.score }}</b><span>SCORE</span></div>
              </div>
            </div>
            <div style="margin-top:16px;padding:12px 14px;background:var(--ivory);border-radius:var(--r-sm);font-size:12px;color:var(--ink-3);line-height:1.6">
              <strong style="color:var(--clay-deep);font-size:12px">💡 推荐理由：</strong>
              标题 1 用「三年内」制造时间紧迫感 + 直击个人焦虑，预计点击率最高。标题 3 用反转型对比句式，适合引发读者自省和讨论转发。
            </div>
          </div>
        </div>

        <!-- Step 04 -->
        <div class="feature-block fade-up reverse">
          <div class="fb-text">
            <div class="fb-step"><span class="num">Step 04</span>编辑润色 · Edit</div>
            <h3>专为公众号设计的<br>富文本编辑器</h3>
            <p>不是通用编辑器，而是专为微信公众号排版规范设计。16px 正文、20px 黑底白字标题、红字高亮——所有排版规范自动处理。</p>
            <ul class="fb-list">
              <li><span class="li-marker">A</span><div class="li-content"><strong>公众号排版规范</strong><span>自动适配微信排版规则，不用手动调格式</span></div></li>
              <li><span class="li-marker">B</span><div class="li-content"><strong>一键润色</strong><span>对已有文章进行金句补充、事实核查和去 AI 痕迹改写</span></div></li>
              <li><span class="li-marker">C</span><div class="li-content"><strong>一键发布</strong><span>编辑完成后直接发布到公众号，不用切换工具</span></div></li>
            </ul>
          </div>
          <div class="fb-visual" style="padding:0">
            <div class="mk-editor">
              <div class="mk-toolbar">
                <div class="mk-toolbar-btn" style="font-weight:900">B</div>
                <div class="mk-toolbar-btn"><i>I</i></div>
                <div class="mk-toolbar-btn" style="text-decoration:underline">U</div>
                <div style="width:1px;height:18px;background:var(--line);margin:0 4px"></div>
                <div class="mk-toolbar-btn active">H1</div>
                <div class="mk-toolbar-btn">H2</div>
                <div style="width:1px;height:18px;background:var(--line);margin:0 4px"></div>
                <div class="mk-toolbar-btn" style="color:var(--crimson)">红</div>
                <div class="mk-toolbar-btn" style="font-size:11px">引用</div>
                <div style="flex:1"></div>
                <div style="font-size:11px;color:var(--leaf);font-weight:600">✓ 已保存</div>
              </div>
              <div class="mk-body">
                <h5>你的工作会在三年内被 AI 取代吗？</h5>
                <p>上周和一位 4A 广告公司的创意总监聊天，他说了一句让我后背发凉的话：「我们部门 30 个人，明年可能只需要 5 个。」不是因为裁员，而是因为 AI 已经能独立完成 80% 的创意提案。</p>
                <p>从文案撰写到视觉设计，从数据分析到客户方案，<span class="red-hi">AI 正在以你想象不到的速度渗透每一个行业</span>。问题不是「会不会」，而是「什么时候」。</p>
                <p>我调研了 100 家不同行业的公司，总结出 3 个你必须现在就开始准备的方向…</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 05 -->
        <div class="feature-block fade-up">
          <div class="fb-text">
            <div class="fb-step"><span class="num">Step 05</span>跨平台 · Adapt</div>
            <h3>多平台内容，<br>互相转写适配</h3>
            <p>多平台内容互相转写——公众号长文转小红书图文、抖音文案，反过来也能一键适配。不用手动改格式。</p>
            <ul class="fb-list">
              <li><span class="li-marker">A</span><div class="li-content"><strong>一键发布</strong><span>文章定稿后一键推送到公众号草稿箱，同时可同步发布到小红书</span></div></li>
              <li><span class="li-marker">B</span><div class="li-content"><strong>多平台互转</strong><span>小红书、抖音、知乎等平台内容互相转写，自动适配各平台风格</span></div></li>
              <li><span class="li-marker">C</span><div class="li-content"><strong>风格迁移</strong><span>将内容从一种风格转换为另一种风格，适配不同受众</span></div></li>
            </ul>
          </div>
          <div class="fb-visual">
            <div class="mk-head"><div class="t">跨平台发布</div><div class="tag">2 个平台就绪</div></div>
            <div style="display:flex;flex-direction:column;gap:10px">
              <div v-for="(p, i) in platformRows" :key="i" style="display:flex;align-items:center;gap:14px;padding:14px;background:var(--ivory);border-radius:var(--r-md);border:1px solid var(--line)">
                <div :style="{ width:'36px', height:'36px', borderRadius:'8px', background:p.color, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--serif)', fontWeight:700, fontSize:'14px', flexShrink:0 }">{{ p.icon }}</div>
                <div style="flex:1">
                  <div style="font-weight:600;font-size:13.5px;color:var(--ink);margin-bottom:2px">{{ p.name }}</div>
                  <div style="font-size:11.5px;color:var(--ink-3)">{{ p.desc }}</div>
                </div>
                <div style="font-size:11px;color:var(--leaf);font-weight:600;display:flex;align-items:center;gap:4px">
                  <span style="width:14px;height:14px;border-radius:50%;background:var(--leaf);color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700">✓</span>就绪
                </div>
              </div>
              <div style="margin-top:4px;width:100%;background:var(--clay);color:#fff;text-align:center;padding:12px;border-radius:var(--r-md);font-weight:600;font-size:14px;letter-spacing:.04em;box-shadow:var(--sh-clay)">
                同时发布到 2 个平台
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Tools -->
    <section class="section section-alt" id="tools">
      <div class="container">
        <div class="section-head center fade-up">
          <div class="section-tag">— Creator Toolkit · 创作工具箱 —</div>
          <h2 class="section-title">不只是写作，<br>一整套内容创作工具</h2>
          <p class="section-sub">从初稿到成品，从润色到发布——所有工具都在一个平台上，不用在多个软件之间来回切换。</p>
        </div>
        <div class="tools-grid">
          <div v-for="(t, i) in tools" :key="i" class="tool-card fade-up" :data-accent="t.accent" :style="{ transitionDelay: `${i * 0.06}s` }">
            <div class="tool-card-icon">{{ t.icon }}</div>
            <div class="tool-card-title">{{ t.title }}</div>
            <div class="tool-card-desc">{{ t.desc }}</div>
            <div class="tool-card-tag">{{ t.tag }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="section cta-section" id="cta" style="position:relative">
      <div class="noise-overlay"></div>
      <div class="container">
        <div class="section-tag fade-up" style="position:relative;z-index:1">— Get Started —</div>
        <h2 class="section-title fade-up" style="position:relative;z-index:1">让 AI 处理繁琐流程，<br>你专注于内容本身</h2>
        <p class="section-sub fade-up" style="position:relative;z-index:1">
          从海量信息中提炼选题，到打磨出可发布的公众号文章——全流程自动化，你只做最终审核。
        </p>
        <div class="hero-actions fade-up" style="justify-content:center;position:relative;z-index:1">
          <MagnetButton @click="startCreationTool">
            <button class="star-btn"><span>立即开始 <span class="btn-arrow">→</span></span></button>
          </MagnetButton>
          <a href="#features" class="btn btn-ghost btn-lg">了解更多</a>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
      <div class="container">
        <div class="footer-inner">
          <div class="brand">
            <img class="brand-logo" src="/brand/ip-compass.svg" alt="IP罗盘" />
            <span>IP罗盘</span>
          </div>
          <div class="footer-meta">
            <span>© 2026 IP罗盘</span>
            <span>创作不迷路，商单有方向</span>
          </div>
        </div>
      </div>
    </footer>

    <!-- Login Modal -->
    <div v-if="loginOpen" class="modal-backdrop active" @click.self="loginOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <button class="modal-close" @click="loginOpen = false" aria-label="关闭">×</button>
        <div v-if="loginStep === 'form'">
          <h3>登录 / 注册</h3>
          <p class="modal-sub">输入手机号即可一步完成登录或注册。还没有账号？自动创建。</p>
          <div v-if="loginError" class="modal-error active"><strong>提示</strong>{{ loginError }}</div>
          <div class="field">
            <label>手机号</label>
            <input type="tel" placeholder="请输入 11 位手机号" :maxlength="11" autocomplete="tel"
              :value="loginPhone" @input="loginPhone = $event.target.value.replace(/\D/g, '').slice(0, 11)" />
          </div>
          <div class="field">
            <label>验证码</label>
            <div class="field-row">
              <input type="text" placeholder="6 位验证码" :maxlength="6" inputmode="numeric"
                :value="loginCode" @input="loginCode = $event.target.value.replace(/\D/g, '').slice(0, 6)" />
              <button class="btn btn-ghost" :disabled="loginCountdown > 0 || sendingCode" @click="sendCode">
                {{ sendingCode ? '发送中...' : loginCountdown > 0 ? `重新发送 ${loginCountdown}s` : '获取验证码' }}
              </button>
            </div>
          </div>
          <button class="btn btn-primary btn-submit" :disabled="loginLoading" @click="submitLogin">
            {{ loginLoading ? '登录中...' : '登录 / 注册' }}
          </button>
          <div class="modal-foot">
            提交即表示同意 <a href="/terms" target="_blank">《用户协议》</a> 和 <a href="/privacy" target="_blank">《隐私政策》</a>
          </div>
        </div>
        <div v-if="loginStep === 'success'" class="modal-success active">
          <div class="icon" style="background:var(--clay)">✓</div>
          <h4>登录成功</h4>
          <p>
            手机号 <strong style="color:var(--ink)">{{ loginPhone.slice(0,3) }} **** {{ loginPhone.slice(7) }}</strong> 已验证通过。<br>
            即将进入工作台…
          </p>
          <button class="btn btn-primary btn-submit" @click="goToDashboard">
            进入工作台 <span class="btn-arrow">→</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Product Modal -->
    <div v-if="membershipOpen" class="modal-backdrop active">
      <div class="modal" role="dialog" aria-modal="true">
        <button class="modal-close" @click="closeMembership" aria-label="关闭">×</button>

        <!-- 支付成功 -->
        <div v-if="membershipPaid" class="modal-success active">
          <div class="icon" style="background:var(--clay)">✓</div>
          <h4>{{ requestedProductLabel }}开通成功</h4>
          <p>{{ requestedProduct === 'creation_tool' ? '已赠送 6000 积分，' : '' }}正在为你进入对应页面…</p>
        </div>

        <!-- 正常流程 -->
        <div v-else>
          <h3>开通{{ requestedProductLabel }}</h3>
          <p class="modal-sub">{{ currentPlan.description }}</p>

          <div class="benefits-list">
            <div class="benefit-item" v-for="b in currentPlan.benefits" :key="b">
              <span class="benefit-check">✓</span> {{ b }}
            </div>
          </div>

          <div class="price-row" style="text-align:center;margin-bottom:20px;padding:16px 0;border-top:1px dashed var(--line-2);border-bottom:1px dashed var(--line-2)">
            <span style="font-size:18px;color:var(--ink-3);vertical-align:top">¥</span>
            <span style="font-size:42px;font-weight:700;color:var(--clay)">{{ membershipPrice }}</span>
            <span style="font-size:14px;color:var(--ink-3);margin-left:4px">/ {{ currentPlan.period }}</span>
          </div>

          <div v-if="membershipOrder" style="text-align:center;margin-bottom:20px">
            <div style="display:inline-block;padding:12px;background:#fff;border:1px solid var(--line);border-radius:var(--r-md)">
              <img :src="membershipQrUrl" alt="微信支付二维码" style="width:200px;height:200px;display:block" />
            </div>
            <p style="margin-top:12px;font-size:13px;color:var(--ink-3)">
              <span v-if="membershipPolling" class="polling-indicator" style="display:inline-flex;align-items:center;gap:6px">
                <span class="spinner"></span> 等待微信扫码支付...
              </span>
            </p>
            <p style="margin-top:6px;font-size:12.5px;color:var(--clay);line-height:1.6">
              支付完成后请不要刷新或离开页面，系统正在自动确认支付结果。
            </p>
          </div>

          <div v-if="membershipError" class="modal-error active"><strong>提示</strong>{{ membershipError }}</div>

          <button v-if="!membershipOrder" class="btn btn-primary btn-submit" :disabled="membershipLoading" @click="createMembershipOrder">
            {{ membershipLoading ? '创建订单中...' : `立即开通${requestedProductLabel} ¥${membershipPrice} / ${currentPlan.period}` }}
          </button>

          <div class="modal-foot">
            支付即表示同意 <a href="/terms" target="_blank">《用户协议》</a> 和 <a href="/privacy" target="_blank">《隐私政策》</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { sendSmsCode, loginByPhone } from '@/api/auth'
import { post, get } from '@/api/api'
import { ElMessage } from 'element-plus'
import PublicLoginButton from '@/components/product/PublicLoginButton.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

/* ── Nav scroll ── */
const navScrolled = ref(false)
const onScroll = () => { navScrolled.value = window.scrollY > 12 }

/* ── Login Modal ── */
const loginOpen = ref(false)
const loginStep = ref('form')
const loginPhone = ref('')
const loginCode = ref('')
const loginError = ref('')
const loginCountdown = ref(0)
const loginLoading = ref(false)
const sendingCode = ref(false)
let countdownTimer = null

const openLogin = () => {
  loginStep.value = 'form'
  loginPhone.value = ''
  loginCode.value = ''
  loginError.value = ''
  loginCountdown.value = 0
  loginOpen.value = true
}

const goCamp = () => {
  router.push('/camp')
}

// 产品入口只处理本产品的权限；登录本身不再默认开通或跳转任何产品。
const startCreationTool = () => {
  if (!userStore.isAuthenticated) {
    loginIntent.value = 'creation_tool'
    openLogin()
    return
  }
  if (userStore.hasProduct('creation_tool') || userStore.isAdmin) {
    router.push('/')
    return
  }
  openMembership('creation_tool')
}

const goToWorkspace = () => {
  if (userStore.hasProduct('creation_tool') || userStore.isAdmin) router.push('/')
}

const sendCode = async () => {
  if (!/^1[3-9]\d{9}$/.test(loginPhone.value)) {
    loginError.value = '请输入 11 位有效手机号'
    return
  }
  loginError.value = ''
  sendingCode.value = true
  try {
    await sendSmsCode(loginPhone.value)
    ElMessage.success('验证码已发送，请注意查收')
    loginCountdown.value = 60
  } catch (error) {
    loginError.value = error.response?.data?.detail || '发送失败，请稍后重试'
  } finally {
    sendingCode.value = false
  }
}

watch(loginCountdown, (v) => {
  if (v > 0) {
    countdownTimer = setInterval(() => {
      loginCountdown.value--
      if (loginCountdown.value <= 0) clearInterval(countdownTimer)
    }, 1000)
  }
})

const submitLogin = async () => {
  if (!/^1[3-9]\d{9}$/.test(loginPhone.value)) {
    loginError.value = '请输入 11 位有效手机号'
    return
  }
  if (!/^\d{6}$/.test(loginCode.value)) {
    loginError.value = '请输入 6 位验证码'
    return
  }
  loginError.value = ''
  loginLoading.value = true
  try {
    const res = await loginByPhone(loginPhone.value, loginCode.value)
    const { access_token, refresh_token } = res.data
    userStore.token = access_token
    userStore.refreshToken = refresh_token
    localStorage.setItem('token', access_token)
    localStorage.setItem('refreshToken', refresh_token)
    localStorage.setItem('tokenSavedAt', String(Date.now()))
    await userStore.fetchUser()
    if (countdownTimer) clearInterval(countdownTimer)
    ElMessage.success('登录成功')
    goToDashboard()
  } catch (error) {
    loginError.value = error.response?.data?.detail || '登录失败，请检查验证码'
  } finally {
    loginLoading.value = false
  }
}

const goToDashboard = () => {
  loginOpen.value = false
  const intent = loginIntent.value || route.query.intent
  loginIntent.value = ''
  // 从产品 CTA 触发登录后，回到同一个产品继续完成开通；右上角登录仅建立登录状态。
  if (intent === 'practical_camp') {
    router.push({ path: '/camp', query: { openPay: '1' } })
    return
  }
  if (intent === 'creation_tool') {
    openMembership('creation_tool')
    return
  }
  router.push(route.query.redirect || '/landing')
}

/* ── Membership Modal ── */
const membershipOpen = ref(false)
const membershipPaid = ref(false)
const membershipOrder = ref(null)
const membershipQrUrl = ref('')
const membershipPrice = ref(699)
const membershipLoading = ref(false)
const membershipPolling = ref(false)
const membershipError = ref('')
const requestedProduct = ref('creation_tool')
const loginIntent = ref('')
let membershipTimer = null

const productLabels = {
  creation_tool: '创作工具',
  potential_commercial: '潜在商单',
  practical_camp: '实战营'
}

const requestedProductLabel = computed(() => productLabels[requestedProduct.value] || '对应产品')
const productPlans = {
  creation_tool: {
    price: 699, period: '月',
    description: '订阅创作工具，开通信息选题、创作工具、内容仿写和创作历史。每月赠送 6000 积分。',
    benefits: ['AI 选题挖掘：20+ 数据源智能推荐', 'AI 全流程创作：大纲→正文→标题', 'AI 文案润色、续写、仿写、转写', '公众号编辑器 + 草稿箱发布', '每月赠送 6000 积分'],
    fallback: '/',
  },
  potential_commercial: {
    price: 299, period: '月',
    description: '订阅潜在商单，解锁品牌投放线索、投放账号、时间和原文链接。',
    benefits: ['品牌投放聚合与趋势筛选', '投放账号、时间和文章线索', '潜在商单原文与判断依据'],
    fallback: '/potential-commercial',
  },
  practical_camp: {
    price: 3980, period: '年',
    description: '报名 AI 垂类公众号实战营，开通完整课程资料与实战讲义。',
    benefits: ['完整课程资料与章节讲义', '从选题到商业变现的方法论', '实战营专属学习内容'],
    fallback: '/courses',
  },
}
const currentPlan = computed(() => productPlans[requestedProduct.value] || productPlans.creation_tool)

const openMembership = (product) => {
  requestedProduct.value = product || route.query.product || 'creation_tool'
  membershipPrice.value = currentPlan.value.price
  if (
    userStore.isAuthenticated &&
    (userStore.hasProduct(requestedProduct.value) || userStore.isAdmin)
  ) {
    router.replace(route.query.redirect || '/')
    return
  }
  membershipPaid.value = false
  membershipOrder.value = null
  membershipQrUrl.value = ''
  membershipError.value = ''
  membershipOpen.value = true
}

const closeMembership = () => {
  membershipOpen.value = false
  if (membershipTimer) { clearInterval(membershipTimer); membershipTimer = null }
  router.replace('/landing')
}

const dismissMembership = () => {
  membershipOpen.value = false
  if (membershipTimer) { clearInterval(membershipTimer); membershipTimer = null }
  router.replace('/landing')
}

const createMembershipOrder = async () => {
  membershipLoading.value = true
  membershipError.value = ''
  try {
    const res = await post(`/credits/products/${requestedProduct.value}`)
    membershipOrder.value = res.data
    if (res.data.amount_yuan) membershipPrice.value = res.data.amount_yuan
    membershipQrUrl.value = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(res.data.code_url)}`
    startMembershipPolling(res.data.out_trade_no)
  } catch (err) {
    membershipError.value = err.response?.data?.detail || '创建支付订单失败，请稍后重试'
  } finally {
    membershipLoading.value = false
  }
}

const startMembershipPolling = (outTradeNo) => {
  membershipPolling.value = true
  membershipTimer = setInterval(async () => {
    try {
      const res = await get(`/credits/purchase/status/${outTradeNo}`)
      if (res.data.status === 'PAID') {
        membershipPaid.value = true
        membershipPolling.value = false
        clearInterval(membershipTimer)
        membershipTimer = null
        await userStore.fetchUser()
        const target = route.query.redirect || currentPlan.value.fallback
        setTimeout(() => { membershipOpen.value = false; router.push(target) }, 1400)
      }
    } catch { /* 静默重试 */ }
  }, 3000)
}

// 监听路由 query 变化：从其他页面被守卫弹回 /landing?show=membership 时
watch(() => route.query.show, (val) => {
  if (val === 'membership' && !membershipOpen.value) {
    openMembership()
  } else if (val === 'login' && !loginOpen.value) {
    openLogin()
  }
}, { immediate: true })

// 弹窗打开时锁定 body 滚动，防止出现横向滚动条
watch([loginOpen, membershipOpen], ([login, membership]) => {
  document.body.style.overflow = (login || membership) ? 'hidden' : ''
})

/* ── Pain Points data ── */
const painPoints = [
  ['内容天天更，定位却越来越散', '热点、案例、观点都想写，最后账号没有清晰识别度，读者记不住，品牌方也不知道你适合什么合作。'],
  ['选题能涨粉，但不一定能接单', '很多内容有阅读量，却沉淀不出商业信号，不知道哪些方向更容易连接产品、预算和合作场景。'],
  ['商单线索藏在信息流里', '竞品投放、品牌动作、行业需求每天都在发生，但靠人工翻找太慢，常常等别人合作了才发现机会。'],
  ['从内容到报价，总缺一张地图', '写什么、怎么包装、适合谁投、如何交付，没有连续判断，只能凭感觉试错。'],
]

/* ── Feature mockup data ── */
const topicRows = [
  { color: '#CC785C', rank: '01', text: 'AI 会议助手密集投放，内容切入点怎么选', score: '9.6' },
  { color: '#C49B5C', rank: '02', text: '知识管理工具更新：适合做哪类商单内容', score: '9.3' },
  { color: '#3F5C52', rank: '03', text: 'Agent 落地案例升温，品牌合作机会在哪里', score: '9.1' },
  { color: '#6B6862', rank: '04', text: '创作者如何把测评内容升级成合作资产', score: '8.7' },
]
const agentRows = [
  { status: 'done', name: '正文创作', desc: '✓ 已完成 · 2,847 字' },
  { status: 'done', name: '金句催化', desc: '✓ 已完成 · 植入 4 处金句' },
  { status: 'done', name: '事实整理', desc: '✓ 已完成 · 提取 8 条数据' },
  { status: 'done', name: '联网核实', desc: '✓ 已完成 · 修正 2 处' },
  { status: 'active', name: '去除 AI 痕迹', desc: '打磨中…' },
]
const titleRows = [
  { top: true, rank: '1', text: 'AI 工具商单，为什么总找不到你？', score: '9.4' },
  { top: false, rank: '2', text: '我复盘了 30 个创作者合作案例，发现机会都藏在这里', score: '9.1' },
  { top: false, rank: '3', text: '不是内容不够好，是你的商业方向太模糊', score: '8.8' },
]
const platformRows = [
  { color: '#07C160', icon: '公', name: '公众号 · 长文版', desc: '2,847 字 + 排版完成' },
  { color: '#FF2442', icon: '小', name: '小红书 · 种草版', desc: '9 张图 + 合作卖点' },
]

/* ── Tools data ── */
const tools = [
  { icon: '🔄', title: '文案润色', accent: 'clay', desc: '写完初稿后一键润色——补充金句、核查事实、去除 AI 痕迹，让文章读起来像人写的。', tag: '金句补充 · 事实核查 · 去 AI 味' },
  { icon: '📝', title: '正文续写', accent: 'pine', desc: '文章写到一半卡住了？AI 根据上文语境自动续写，保持风格统一，不会突然跑偏。', tag: '语境理解 · 风格延续' },
  { icon: '📋', title: '内容仿写', accent: 'purple', desc: '给一篇参考文章，AI 分析它的结构和风格，帮你仿写出同样调性的新内容。', tag: '风格分析 · 结构模仿' },
  { icon: '🔀', title: '多平台互转', accent: 'blue', desc: '多平台内容互相转写——公众号长文转小红书图文、抖音文案，反过来也能一键适配各平台风格。', tag: '互相转写 · 风格适配' },
  { icon: '🚀', title: '一键发布', accent: 'gold', desc: '文章定稿后，一键推送到公众号草稿箱，同时可同步发布到小红书，不用手动复制粘贴。', tag: '公众号 · 小红书 · 同步发布' },
  { icon: '✏️', title: '公众号编辑器', accent: 'ink', desc: '内置富文本编辑器，支持微信排版规范，写完直接编辑、预览、发布，不用切换工具。', tag: '富文本 · 微信排版 · 预览' },
]

/* ── Scroll fade-up observer ── */
let fadeObserver = null
onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()

  // 检查是否需要打开会员弹窗
  if (route.query.show === 'membership') {
    openMembership()
  } else if (route.query.show === 'login') {
    openLogin()
  }

  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    fadeObserver = new IntersectionObserver(
      entries => entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible')
          fadeObserver.unobserve(e.target)
        }
      }),
      { threshold: 0.15 }
    )
    document.querySelectorAll('.fade-up').forEach(el => fadeObserver.observe(el))
  }
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
  if (fadeObserver) fadeObserver.disconnect()
  if (countdownTimer) clearInterval(countdownTimer)
  if (membershipTimer) clearInterval(membershipTimer)
})
</script>

<!-- Sub-components as inline script -->
<script>
import { defineComponent, h, ref, onMounted, onUnmounted, watch } from 'vue'

/* BlurText */
const BlurText = defineComponent({
  props: { text: String, delay: { type: Number, default: 80 } },
  setup(props) {
    const el = ref(null)
    const inView = ref(false)
    onMounted(() => {
      if (!el.value) return
      const io = new IntersectionObserver(([e]) => {
        if (e.isIntersecting) { inView.value = true; io.disconnect() }
      }, { threshold: 0.2 })
      io.observe(el.value)
    })
    return () => h('span', { ref: el, style: { display: 'inline' } },
      props.text.split('').map((ch, i) =>
        h('span', {
          key: i,
          class: `blur-word${inView.value ? ' visible' : ''}`,
          style: { transitionDelay: `${i * props.delay}ms` }
        }, ch === ' ' ? '\u00A0' : ch)
      )
    )
  }
})

/* RotatingText */
const RotatingText = defineComponent({
  props: { words: Array },
  setup(props) {
    return () => h('span', { class: 'rotating-wrap', 'aria-hidden': 'true' },
      h('span', { class: 'rotating-inner' }, [
        ...props.words.map((w, i) => h('span', { class: 'rotating-word', key: i }, w)),
        h('span', { class: 'rotating-word', key: 'dup' }, props.words[0])
      ])
    )
  }
})

/* MagnetButton */
const MagnetButton = defineComponent({
  emits: ['click'],
  setup(props, { emit, slots }) {
    const el = ref(null)
    const handleMove = (e) => {
      if (!el.value) return
      const rect = el.value.getBoundingClientRect()
      const dx = (e.clientX - (rect.left + rect.width / 2)) / 25
      const dy = (e.clientY - (rect.top + rect.height / 2)) / 25
      const inner = el.value.querySelector('.magnet-inner')
      if (inner) inner.style.transform = `translate(${dx}px, ${dy}px)`
    }
    const handleLeave = () => {
      if (!el.value) return
      const inner = el.value.querySelector('.magnet-inner')
      if (inner) inner.style.transform = 'translate(0,0)'
    }
    return () => h('div', {
      ref: el, class: 'magnet-btn',
      onMousemove: handleMove, onMouseleave: handleLeave,
      style: { cursor: 'pointer' }
    },
      h('div', {
        class: 'magnet-inner',
        onClick: () => emit('click'),
        role: 'button', tabindex: 0
      }, slots.default?.())
    )
  }
})

/* CountUp */
const CountUp = defineComponent({
  props: { end: Number, suffix: { type: String, default: '' }, duration: { type: Number, default: 2000 } },
  setup(props) {
    const val = ref(0)
    const el = ref(null)
    const started = ref(false)
    onMounted(() => {
      if (!el.value) return
      const io = new IntersectionObserver(([e]) => {
        if (e.isIntersecting && !started.value) {
          started.value = true
          const start = performance.now()
          const step = (now) => {
            const p = Math.min((now - start) / props.duration, 1)
            const eased = 1 - Math.pow(1 - p, 3)
            val.value = Math.round(props.end * eased)
            if (p < 1) requestAnimationFrame(step)
          }
          requestAnimationFrame(step)
        }
      }, { threshold: 0.3 })
      io.observe(el.value)
    })
    return () => h('span', { ref: el, class: 'countup-num' }, [
      val.value,
      h('span', { class: 'countup-unit' }, props.suffix)
    ])
  }
})

/* HeroCardStack */
const HeroCardStack = defineComponent({
  setup() {
    const active = ref(1)
    const hovering = ref(false)
    let cycleTimer = null
    let order = []
    let pos = 0

    const cards = [
      {
        id: 'info', cls: 'hc-1 hc-info', icon: '🧭', title: '内容方向自动校准',
        desc: '覆盖 20+ 信息源，每天自动采集、智能去重、归类整理，打开就能看到值得经营的方向。',
        tag: '趋势 · 选题 · 品牌动作 · 合作线索',
        rows: [
          { icon: '💬', label: '公众号趋势', status: '已同步', scls: 'cr-ok' },
          { icon: '🔍', label: '用户问题', status: '已同步', scls: 'cr-ok' },
          { icon: '📰', label: '品牌动态', status: '采集中…', scls: 'cr-run' },
          { icon: '💼', label: '商单线索', status: '已同步', scls: 'cr-ok' },
        ]
      },
      {
        id: 'pipe', cls: 'hc-2 hc-pipe', icon: '⚙️', title: '内容经营流',
        desc: '从方向判断到成稿交付，5 步 AI 流水线自动推进，每步独立 Agent 协作完成。',
        tag: '方向 → 选题 → 大纲 → 正文 → 合作角度',
        pipe: true
      },
      {
        id: 'xform', cls: 'hc-3 hc-xform', icon: '🔀', title: '多平台商业表达',
        desc: '一键将公众号长文改写为小红书种草表达，或根据对标账号仿写，保持你的个人风格。',
        tag: '公众号 → 小红书 · 合作卖点',
        rows: [
          { icon: '📝', label: '公众号原文', status: '2,400 字', scls: 'cr-blue' },
          { icon: '➡️', label: '提炼合作卖点', status: '转写中…', scls: 'cr-run' },
          { icon: '✅', label: '适配标签 + CTA', status: '已完成', scls: 'cr-ok' },
        ]
      },
      {
        id: 'pub', cls: 'hc-4 hc-pub', icon: '🚀', title: '合作内容交付',
        desc: '文章写好后直接推送到微信公众号草稿箱，或整理成跨平台发布素材，不用复制粘贴。',
        tag: '公众号 · 小红书 · 商稿交付',
        rows: [
          { icon: '📱', label: '微信公众号草稿', status: '已推送', scls: 'cr-ok' },
          { icon: '📕', label: '小红书', status: '待发布', scls: 'cr-blue' },
        ]
      }
    ]

    const shuffleOrder = () => {
      const arr = [0, 1, 2, 3]
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]]
      }
      if (arr[0] === active.value && arr.length > 1) [arr[0], arr[1]] = [arr[1], arr[0]]
      return arr
    }

    onMounted(() => {
      order = shuffleOrder()
      pos = 0
      cycleTimer = setInterval(() => {
        if (hovering.value) return
        if (pos >= order.length) { order = shuffleOrder(); pos = 0 }
        active.value = order[pos]
        pos++
      }, 3000)
    })

    onUnmounted(() => { if (cycleTimer) clearInterval(cycleTimer) })

    return () => h('div', { class: 'hero-visual', 'aria-hidden': 'true' },
      h('div', { class: 'card-stack' },
        cards.map((c, i) => {
          let cls = `hero-card ${c.cls}`
          if (active.value === i) cls += ' hc-active'
          else cls += ' hc-dim'
          const children = [
            h('div', { class: 'card-icon' }, c.icon),
            h('div', { class: 'card-title' }, c.title),
            h('div', { class: 'card-desc' }, c.desc),
          ]
          if (c.rows) {
            children.push(h('div', { style: { marginTop: '8px' } },
              c.rows.map((r, ri) => h('div', { class: 'card-row', key: ri }, [
                h('span', { class: 'cr-icon' }, r.icon),
                h('span', { class: 'cr-label' }, r.label),
                h('span', { class: `cr-status ${r.scls}` }, r.status),
              ]))
            ))
          }
          if (c.pipe) {
            children.push(h('div', { style: { marginTop: '8px' } }, [
              h('div', { class: 'pipe-steps', key: 'ps' }, [
                h('div', { class: 'pipe-step done', key: 0 }),
                h('div', { class: 'pipe-step done', key: 1 }),
                h('div', { class: 'pipe-step done', key: 2 }),
                h('div', { class: 'pipe-step active', key: 3 }),
                h('div', { class: 'pipe-step', key: 4 }),
              ]),
              h('div', { class: 'pipe-label', key: 'pl' }, '步骤 4/5 · 正文创作中'),
            ]))
          }
          children.push(h('span', { class: 'card-tag' }, c.tag))
          return h('div', {
            key: c.id, class: cls,
            onMouseenter: () => { hovering.value = true; active.value = i },
            onMouseleave: () => { hovering.value = false }
          }, children)
        })
      )
    )
  }
})

/* CompareSection */
const CompareSection = defineComponent({
  setup() {
    const el = ref(null)
    const visible = ref(false)

    onMounted(() => {
      if (!el.value) return
      const io = new IntersectionObserver(([e]) => {
        if (e.isIntersecting) { visible.value = true; io.disconnect() }
      }, { threshold: 0.2 })
      io.observe(el.value)

      // stat counters
      const counters = el.value.querySelectorAll('.stat-counter')
      if (counters.length) {
        const cio = new IntersectionObserver(([e]) => {
          if (!e.isIntersecting) return
          counters.forEach(cel => {
            const target = parseInt(cel.dataset.target, 10)
            const start = performance.now()
            const step = (now) => {
              const p = Math.min((now - start) / 1200, 1)
              const eased = 1 - Math.pow(1 - p, 3)
              cel.textContent = Math.round(target * eased)
              if (p < 1) requestAnimationFrame(step)
            }
            requestAnimationFrame(step)
          })
          cio.disconnect()
        }, { threshold: 0.3 })
        cio.observe(el.value)
      }
    })

    const oldSteps = [
      ['刷 AI 新闻 2 小时', '推特、Hacker News、GitHub Trending 轮着刷，看完就忘'],
      ['硬憋选题 30 分钟', '追热点怕过时，写深度怕没人看，全凭感觉选'],
      ['查资料 + 写初稿 1.5 小时', '读论文、翻文档、理逻辑，写完读起来像技术报告'],
      ['想标题 30 分钟', '太专业读者看不懂，太通俗又怕被行家嫌弃'],
      ['排版 + 发布 30 分钟', '复制到公众号后台，代码块全乱了，手动调格式'],
    ]
    const newSteps = [
      ['选题自动推送', '20+ 信息源自动采集，AI 按你的领域衍生并评分推荐 Top 选题'],
      ['大纲一键生成', 'AI 按你的写作风格生成结构化大纲，你只需调整逻辑'],
      ['正文 5 步出稿', 'AI 写作 → 金句补充 → 事实核查 → 联网纠错 → 去 AI 味'],
      ['标题智能推荐', '12 种套路生成 + 评分预测，推荐最适合你读者的 3 个'],
      ['一键发布', '自动排版适配公众号格式，直接推送到草稿箱'],
    ]

    return () => h('section', { class: 'section compare-section', id: 'compare', ref: el }, [
      h('div', { class: 'container' }, [
        h('div', { class: 'section-head center fade-up' }, [
          h('div', { class: 'section-tag' }, '— Before & After —'),
          h('h2', { class: 'section-title', innerHTML: '一篇公众号文章，<br>从 4 小时到 30 分钟' }),
          h('p', { class: 'section-sub' }, '不是替代你的思考，而是把重复劳动交给 AI。你专注在最有价值的事：审稿和决策。'),
        ]),
        h('div', { class: 'compare-grid' }, [
          h('div', { class: 'compare-col old fade-up' }, [
            h('div', { class: 'compare-header' }, [
              h('span', { class: 'emoji' }, '😩'),
              h('h3', null, '传统方式'),
              h('span', { class: 'time' }, '≈ 4 小时'),
            ]),
            h('div', { class: 'compare-steps' },
              oldSteps.map(([t, d], i) => h('div', { class: 'compare-step', key: i }, [
                h('div', { class: 'dot' }),
                h('div', { class: 'step-content' }, [
                  h('strong', null, t),
                  h('span', null, d),
                ]),
              ]))
            ),
          ]),
          h('div', { class: 'compare-divider' }, [
            h('div', { class: 'arrow-icon' }, '→'),
          ]),
          h('div', { class: 'compare-col new fade-up' }, [
            h('div', { class: 'compare-header' }, [
              h('span', { class: 'emoji' }, '🚀'),
              h('h3', null, 'AI 方式'),
              h('span', { class: 'time' }, '≈ 20 分钟'),
            ]),
            h('div', { class: 'compare-steps' },
              newSteps.map(([t, d], i) => h('div', { class: 'compare-step', key: i }, [
                h('div', { class: 'dot' }),
                h('div', { class: 'step-content' }, [
                  h('strong', null, t),
                  h('span', null, d),
                ]),
              ]))
            ),
          ]),
        ]),
        h('div', { class: 'compare-result fade-up' }, [
          h('div', { class: 'compare-stats' }, [
            h('div', { class: 'compare-stat-item' }, [
              h('div', null, [
                h('span', { class: 'stat-num stat-counter', 'data-target': '8' }, '0'),
                h('span', { class: 'stat-suffix' }, '×'),
              ]),
              h('div', { class: 'stat-unit' }, '效率提升'),
              h('div', { class: 'stat-desc' }, '从 4 小时缩短到 30 分钟'),
            ]),
            h('div', { class: 'compare-stat-divider' }),
            h('div', { class: 'compare-stat-item' }, [
              h('div', null, [
                h('span', { class: 'stat-num stat-counter', 'data-target': '20' }, '0'),
                h('span', { class: 'stat-suffix' }, '+'),
              ]),
              h('div', { class: 'stat-unit' }, '信息源覆盖'),
              h('div', { class: 'stat-desc' }, '微信/知乎/RSS/GitHub 等自动采集'),
            ]),
            h('div', { class: 'compare-stat-divider' }),
            h('div', { class: 'compare-stat-item' }, [
              h('div', null, [
                h('span', { class: 'stat-num stat-counter', 'data-target': '30' }, '0'),
                h('span', { class: 'stat-suffix' }, 'min'),
              ]),
              h('div', { class: 'stat-unit' }, '完成一篇'),
              h('div', { class: 'stat-desc' }, '从选题到成稿的平均耗时'),
            ]),
          ]),
          h('div', { class: 'compare-result-note', innerHTML: '把时间留给<span class="highlight">真正重要的事</span> — 思考、审稿、与读者互动' }),
        ]),
      ]),
    ])
  }
})

export default {
  components: { BlurText, RotatingText, MagnetButton, CountUp, HeroCardStack, CompareSection }
}
</script>

<style>
/* =========================================================
   Design Tokens
   ========================================================= */
.lp {
  --clay: #CC785C; --clay-deep: #A85A40; --clay-soft: #E9B79E; --clay-tint: #F5E2D5;
  --pine: #3F5C52; --pine-soft: #C9D4CD;
  --sand: #C49B5C; --sand-soft: #ECDCBF;
  --paper: #FAF9F5; --ivory: #F5F1EB; --bone: #EFEAE0;
  --line: #E4DDCE; --line-2: #D9D0BE;
  --ink-3: #6B6862; --ink-2: #3A3935; --ink: #1F1F1E;
  --leaf: #5C8A5C; --crimson: #B85450;
  --serif: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', ui-serif, Georgia, serif;
  --serif-en: 'Fraunces', 'Noto Serif SC', ui-serif, Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --sh-1: 0 1px 2px rgba(31,31,30,.04), 0 2px 6px rgba(31,31,30,.04);
  --sh-2: 0 4px 12px rgba(31,31,30,.06), 0 8px 24px rgba(31,31,30,.05);
  --sh-3: 0 12px 32px rgba(31,31,30,.10), 0 24px 60px rgba(31,31,30,.08);
  --sh-clay: 0 6px 18px rgba(204,120,92,.30);
  --r-xs: 4px; --r-sm: 6px; --r-md: 10px; --r-lg: 16px; --r-xl: 24px;
  --container: 1180px;
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.65;
  color: var(--ink);
  background: var(--ivory);
  background-image:
    radial-gradient(rgba(204,120,92,.022) 1px, transparent 1px),
    radial-gradient(rgba(63,92,82,.018) 1px, transparent 1px);
  background-size: 28px 28px, 44px 44px;
  background-position: 0 0, 14px 22px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
.lp ::selection { background: var(--clay-tint); color: var(--clay-deep); }
.lp a { color: inherit; text-decoration: none; }
.lp img, .lp svg { display: block; max-width: 100%; }
.lp button { font-family: inherit; cursor: pointer; }
.lp h1, .lp h2, .lp h3, .lp h4, .lp h5 {
  font-family: var(--serif); font-weight: 600; letter-spacing: -.01em;
  color: var(--ink); line-height: 1.25; margin: 0;
}
.container { width: 100%; max-width: var(--container); margin: 0 auto; padding: 0 32px; }

/* Nav */
.nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 50;
  height: 68px; display: flex; align-items: center;
  background: rgba(245,241,235,.72);
  backdrop-filter: saturate(150%) blur(14px);
  -webkit-backdrop-filter: saturate(150%) blur(14px);
  border-bottom: 1px solid transparent;
  transition: all .25s ease;
}
.nav.scrolled { background: rgba(245,241,235,.94); border-bottom-color: var(--line); }
.nav-inner {
  width: 100%; max-width: var(--container); margin: 0 auto; padding: 0 32px;
  display: flex; align-items: center; gap: 32px;
}
.brand { display: flex; align-items: center; gap: 10px; font-family: var(--serif); font-weight: 700; font-size: 18px; color: var(--ink); letter-spacing: .02em; }
.brand-logo { width: 28px; height: 28px; border-radius: 8px; display: block; box-shadow: 0 8px 18px rgba(204, 120, 92, .18); flex-shrink: 0; }
.brand-name { transition: color .15s; }
.brand:hover .brand-name { color: var(--clay); }
.nav-links { display: flex; gap: 28px; margin-left: 24px; }
.nav-links a { font-size: 14px; color: var(--ink-2); font-weight: 500; transition: color .15s; }
.nav-links a:hover { color: var(--clay-deep); }
.nav-links a.nav-camp { cursor: pointer; }
.nav-cta { margin-left: auto; display: flex; gap: 10px; align-items: center; }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 0 18px; height: 40px; border-radius: var(--r-md);
  font-size: 14px; font-weight: 500; font-family: inherit;
  border: 1px solid transparent; cursor: pointer;
  transition: all .15s ease; white-space: nowrap; letter-spacing: .01em;
}
.btn-primary { background: var(--clay); color: #fff; box-shadow: var(--sh-clay); }
.btn-primary:hover { background: var(--clay-deep); transform: translateY(-1px); }
.btn-primary:active { transform: translateY(0); }
.btn-secondary { background: var(--ink); color: var(--paper); }
.btn-secondary:hover { background: #000; }
.btn-ghost { background: transparent; color: var(--ink); border-color: var(--line); }
.btn-ghost:hover { background: var(--bone); border-color: var(--line-2); }
.btn-lg { height: 48px; padding: 0 26px; font-size: 15px; }
.btn-arrow { display: inline-block; transition: transform .2s; }
.btn:hover .btn-arrow { transform: translateX(3px); }

/* Hero */
.hero { position: relative; padding: 144px 0 110px; overflow: hidden; }
.hero-decor { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
.hero .container { position: relative; z-index: 1; }
.eyebrow {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 6px 14px; background: var(--paper);
  border: 1px solid var(--line); border-radius: 999px;
  font-size: 12.5px; color: var(--ink-2);
  margin-bottom: 28px; letter-spacing: .02em;
}
.eyebrow .dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--clay);
  box-shadow: 0 0 0 4px rgba(204,120,92,.18);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 4px rgba(204,120,92,.18); } 50% { box-shadow: 0 0 0 7px rgba(204,120,92,.06); } }
.hero-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 48px; align-items: center; }
.hero-title {
  font-size: clamp(44px, 6.4vw, 80px); line-height: 1.05;
  font-weight: 600; letter-spacing: -.02em;
  margin-bottom: 28px; max-width: 14ch;
}
.hero-sub { font-size: 17px; color: var(--ink-2); line-height: 1.78; max-width: 560px; margin-bottom: 40px; }
.hero-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 36px; }
.hero-meta { display: flex; gap: 24px; align-items: center; flex-wrap: wrap; font-size: 13px; color: var(--ink-3); }

/* Hero Visual */
.hero-visual { position: relative; aspect-ratio: 1/1.05; perspective: 1200px; }
.card-stack { position: relative; width: 100%; height: 100%; }
.hero-card {
  position: absolute; background: var(--paper);
  border: 1px solid var(--line); border-radius: var(--r-lg);
  box-shadow: var(--sh-2); padding: 18px;
  cursor: pointer;
  transition: transform 500ms cubic-bezier(0.2, 0, 0, 1), box-shadow 400ms, opacity 400ms;
  will-change: transform, box-shadow;
}
.hero-card .card-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; font-size: 18px; flex-shrink: 0; }
.hero-card .card-title { font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 4px; }
.hero-card .card-desc { font-size: 12px; color: var(--ink-3); line-height: 1.6; }
.hero-card .card-tag {
  display: inline-block; font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 6px; margin-top: 10px;
}
.hc-1 { top: 0; left: -4%; width: 64%; z-index: 1; transform: rotate(-3deg) scale(0.92); opacity: 0.7; }
.hc-2 { top: 18%; left: 14%; width: 68%; z-index: 2; transform: rotate(1deg) scale(0.96); opacity: 0.85; }
.hc-3 { top: 36%; right: -2%; width: 64%; z-index: 3; transform: rotate(-2deg) scale(0.96); opacity: 0.85; }
.hc-4 { bottom: 0; left: 4%; width: 62%; z-index: 1; transform: rotate(2deg) scale(0.92); opacity: 0.7; }
.hc-active { transform: rotate(0deg) scale(1.04) !important; z-index: 10 !important; opacity: 1 !important; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
.hc-dim { opacity: 0.5 !important; }
.hc-info .card-icon { background: rgba(201,100,66,0.1); }
.hc-info .card-tag { background: rgba(201,100,66,0.1); color: var(--clay-deep); }
.hc-pipe .card-icon { background: rgba(92,138,92,0.1); }
.hc-pipe .card-tag { background: rgba(92,138,92,0.1); color: var(--leaf); }
.hc-xform .card-icon { background: rgba(140,120,170,0.1); }
.hc-xform .card-tag { background: rgba(140,120,170,0.1); color: #7a6490; }
.hc-pub .card-icon { background: rgba(80,140,200,0.1); }
.hc-pub .card-tag { background: rgba(80,140,200,0.1); color: #3a7ab8; }
.card-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 12px; color: var(--ink-2); }
.card-row + .card-row { border-top: 1px solid var(--line); }
.card-row .cr-icon { font-size: 14px; width: 20px; text-align: center; flex-shrink: 0; }
.card-row .cr-label { flex: 1; }
.card-row .cr-status { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
.cr-ok { background: rgba(92,138,92,0.1); color: var(--leaf); }
.cr-run { background: rgba(201,100,66,0.1); color: var(--clay-deep); animation: pulse 2s infinite; }
.cr-blue { background: rgba(80,140,200,0.1); color: #3a7ab8; }
.pipe-steps { display: flex; gap: 4px; margin-top: 8px; }
.pipe-step { flex: 1; height: 4px; border-radius: 2px; background: var(--line); position: relative; overflow: hidden; }
.pipe-step.done { background: var(--leaf); }
.pipe-step.active::after {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 60%;
  background: var(--clay); border-radius: 2px; animation: pipePulse 1.5s ease-in-out infinite;
}
@keyframes pipePulse { 0%,100% { width: 30%; } 50% { width: 80%; } }
.pipe-label { font-family: var(--mono); font-size: 10px; color: var(--ink-3); margin-top: 4px; }

/* Section */
.section { padding: 110px 0; position: relative; }
.section-head { margin-bottom: 64px; max-width: 760px; }
.section-head.center { text-align: center; margin-left: auto; margin-right: auto; }
.section-tag {
  display: inline-block; font-family: var(--serif-en); font-size: 13px;
  font-style: italic; color: var(--clay-deep); letter-spacing: .04em; margin-bottom: 14px;
}
.section-title { font-size: clamp(30px, 4vw, 48px); line-height: 1.18; margin-bottom: 18px; letter-spacing: -.015em; }
.section-sub { font-size: 16px; color: var(--ink-2); line-height: 1.78; max-width: 620px; }
.section-head.center .section-sub { margin-left: auto; margin-right: auto; }

/* Pain */
.pain { background: var(--paper); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.pain-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px;
  background: var(--line); border: 1px solid var(--line);
  border-radius: var(--r-lg); overflow: hidden;
}
.pain-cell {
  background: var(--paper); padding: 36px 32px;
  display: flex; gap: 18px; transition: background .2s;
}
.pain-cell:hover { background: var(--ivory); }
.pain-q { font-family: var(--serif); font-size: 48px; line-height: .8; color: var(--clay-soft); flex-shrink: 0; width: 38px; font-weight: 600; }
.pain-text h4 { font-size: 18px; margin-bottom: 6px; }
.pain-text p { font-size: 14px; color: var(--ink-3); margin: 0; line-height: 1.7; }
.pain-answer { margin-top: 64px; text-align: center; }
.pain-answer-text {
  font-family: var(--serif); font-size: clamp(24px, 3vw, 36px);
  color: var(--ink); line-height: 1.45; letter-spacing: -.01em;
}
.pain-answer-text em { font-style: normal; color: var(--clay-deep); position: relative; }
.pain-answer-text em::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: .04em;
  height: .16em; background: var(--clay-tint); z-index: -1;
}

/* Features */
.features { position: relative; }
.feature-block {
  display: grid; grid-template-columns: 1fr 1fr; gap: 80px;
  align-items: center; padding: 72px 0;
  border-top: 1px dashed var(--line-2);
}
.feature-block:first-of-type { border-top: none; padding-top: 24px; }
.feature-block.reverse .fb-text { order: 2; }
.feature-block.reverse .fb-visual { order: 1; }
.fb-step {
  font-family: var(--serif-en); font-style: italic;
  font-size: 14px; color: var(--clay-deep); letter-spacing: .04em;
  margin-bottom: 14px; font-weight: 500;
}
.fb-step .num {
  display: inline-block; font-style: normal; font-weight: 600;
  font-family: var(--serif); color: var(--ink);
  background: var(--clay-tint); padding: 2px 10px;
  border-radius: 999px; margin-right: 10px; font-size: 12px;
}
.fb-text h3 { font-size: clamp(28px, 3.2vw, 38px); line-height: 1.2; margin-bottom: 18px; letter-spacing: -.015em; }
.fb-text > p { font-size: 16px; color: var(--ink-2); line-height: 1.78; margin-bottom: 28px; }
.fb-list { list-style: none; padding: 0; margin: 0; }
.fb-list li {
  padding: 14px 0; border-top: 1px dashed var(--line-2);
  display: flex; gap: 14px; align-items: flex-start;
}
.fb-list li:last-child { border-bottom: 1px dashed var(--line-2); }
.fb-list .li-marker {
  flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
  background: var(--clay-tint); color: var(--clay-deep);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; font-family: var(--serif-en); margin-top: 2px;
}
.fb-list .li-content strong { display: block; font-size: 14.5px; font-weight: 600; color: var(--ink); margin-bottom: 3px; }
.fb-list .li-content span { font-size: 13.5px; color: var(--ink-3); line-height: 1.65; }
.fb-visual {
  position: relative; aspect-ratio: 1/1;
  background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--r-xl); padding: 28px;
  box-shadow: var(--sh-1); overflow: hidden;
}
.mk-head {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 14px; border-bottom: 1px solid var(--line); margin-bottom: 18px;
}
.mk-head .t { font-family: var(--serif); font-size: 14px; font-weight: 600; color: var(--ink); }
.mk-head .tag { font-size: 11px; color: var(--ink-3); background: var(--bone); padding: 3px 8px; border-radius: 4px; }
.mk-topics { display: flex; flex-direction: column; gap: 8px; }
.trend-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--ivory); border-radius: var(--r-sm); position: relative;
}
.trend-row .heat-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 3px 0 0 3px; }
.trend-row .rank { font-family: var(--serif-en); font-style: italic; font-weight: 500; font-size: 18px; color: var(--clay); width: 24px; }
.trend-row .text { flex: 1; font-size: 13px; color: var(--ink); font-weight: 500; line-height: 1.4; }
.trend-row .meta { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--ink-3); }
.mk-agents { display: flex; flex-direction: column; gap: 10px; }
.agent-row {
  display: flex; align-items: center; gap: 12px; padding: 12px 14px;
  background: var(--ivory); border-radius: var(--r-md);
  border: 1px solid var(--line);
}
.agent-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.agent-dot.done { background: var(--leaf); }
.agent-dot.active { background: var(--clay); animation: pulse 2s infinite; }
.agent-name { flex: 1; font-size: 13px; font-weight: 500; color: var(--ink); }
.agent-status { font-size: 11px; color: var(--leaf); font-weight: 600; }
.mk-titles { display: flex; flex-direction: column; gap: 8px; }
.mk-title-row {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; background: var(--ivory);
  border-radius: var(--r-md); border: 1px solid var(--line);
}
.mk-title-row.top { border-left: 3px solid var(--clay); background: #f9f7f2; }
.mk-title-rank { font-family: var(--serif-en); font-weight: 600; font-size: 20px; color: var(--clay); width: 28px; text-align: center; }
.mk-title-text { flex: 1; font-family: var(--serif); font-size: 14px; font-weight: 600; color: var(--ink); line-height: 1.4; }
.mk-title-score { text-align: center; }
.mk-title-score b { display: block; font-family: var(--serif-en); font-size: 18px; color: var(--clay-deep); line-height: 1; }
.mk-title-score span { font-size: 9px; color: var(--ink-3); letter-spacing: .05em; text-transform: uppercase; }
.mk-editor {
  background: #fff; border: 1px solid var(--line);
  border-radius: var(--r-md); overflow: hidden; height: 100%;
  display: flex; flex-direction: column;
}
.mk-toolbar {
  display: flex; align-items: center; gap: 6px; padding: 10px 14px;
  background: #f7f7f5; border-bottom: 1px solid var(--line);
  font-size: 12px; color: var(--ink-3);
}
.mk-toolbar-btn {
  width: 28px; height: 28px; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 13px; color: var(--ink-2);
  background: #fff; border: 1px solid var(--line);
}
.mk-toolbar-btn.active { background: var(--clay-tint); border-color: var(--clay-soft); color: var(--clay-deep); }
.mk-body { flex: 1; padding: 16px 18px; font-family: var(--serif); font-size: 14px; line-height: 1.85; color: var(--ink); overflow: hidden; }
.mk-body h5 { font-size: 20px; font-weight: 700; margin: 0 0 12px; color: var(--ink); text-align: center; }
.mk-body p { margin: 0 0 10px; }
.mk-body .red-hi { color: var(--crimson); font-weight: 600; }

/* Tools */
.tools-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 48px; }
.tool-card {
  background: var(--ivory); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: 28px;
  transition: all 250ms cubic-bezier(0.2, 0, 0, 1); cursor: default;
}
.tool-card:hover { border-color: var(--line-2); box-shadow: var(--sh-2); transform: translateY(-2px); }
.tool-card-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 20px; }
.tool-card-title { font-family: var(--serif); font-size: 19px; font-weight: 600; margin-bottom: 8px; color: var(--ink); }
.tool-card-desc { font-size: 14px; color: var(--ink-3); line-height: 1.65; }
.tool-card-tag { display: inline-block; margin-top: 14px; font-family: var(--mono); font-size: 12px; font-weight: 500; padding: 4px 10px; border-radius: 6px; }
.tool-card[data-accent="clay"] .tool-card-icon { background: rgba(201,100,66,0.1); }
.tool-card[data-accent="clay"] .tool-card-tag { background: rgba(201,100,66,0.08); color: var(--clay-deep); }
.tool-card[data-accent="pine"] .tool-card-icon { background: rgba(92,138,92,0.1); }
.tool-card[data-accent="pine"] .tool-card-tag { background: rgba(92,138,92,0.08); color: var(--leaf); }
.tool-card[data-accent="purple"] .tool-card-icon { background: rgba(140,120,170,0.1); }
.tool-card[data-accent="purple"] .tool-card-tag { background: rgba(140,120,170,0.08); color: #7a6490; }
.tool-card[data-accent="blue"] .tool-card-icon { background: rgba(80,140,200,0.1); }
.tool-card[data-accent="blue"] .tool-card-tag { background: rgba(80,140,200,0.08); color: #3a7ab8; }
.tool-card[data-accent="gold"] .tool-card-icon { background: rgba(180,150,80,0.1); }
.tool-card[data-accent="gold"] .tool-card-tag { background: rgba(180,150,80,0.08); color: #8a7030; }
.tool-card[data-accent="ink"] .tool-card-icon { background: rgba(80,80,80,0.08); }
.tool-card[data-accent="ink"] .tool-card-tag { background: rgba(80,80,80,0.06); color: var(--ink-2); }

/* Compare */
.compare-section { background: var(--paper); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.compare-grid { display: grid; grid-template-columns: 1fr auto 1fr; gap: 0; margin-top: 48px; align-items: stretch; }
.compare-col { padding: 40px 32px; border-radius: var(--r-lg); }
.compare-col.old { background: var(--bone); border: 1px solid var(--line-2); opacity: .75; }
.compare-col.new { background: var(--paper); border: 2px solid var(--clay); box-shadow: var(--sh-clay); position: relative; }
.compare-col.new::before {
  content: '推荐'; position: absolute; top: -12px; left: 24px;
  background: var(--clay); color: #fff; font-size: 11px; font-weight: 700;
  padding: 3px 12px; border-radius: 999px; letter-spacing: .08em;
}
.compare-header { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; padding-bottom: 18px; border-bottom: 1px dashed var(--line-2); }
.compare-header .emoji { font-size: 28px; }
.compare-header h3 { font-size: 20px; margin: 0; }
.compare-header .time { font-family: var(--mono); font-size: 13px; color: var(--ink-3); margin-left: auto; }
.compare-col.new .compare-header .time { color: var(--clay-deep); font-weight: 700; }
.compare-steps { display: flex; flex-direction: column; gap: 16px; }
.compare-step { display: flex; gap: 12px; align-items: flex-start; }
.compare-step .dot { flex-shrink: 0; width: 8px; height: 8px; border-radius: 50%; margin-top: 7px; }
.compare-col.old .dot { background: var(--ink-3); }
.compare-col.new .dot { background: var(--clay); }
.compare-step .step-content { flex: 1; }
.compare-step .step-content strong { display: block; font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.compare-step .step-content span { font-size: 13px; color: var(--ink-3); line-height: 1.5; }
.compare-divider { display: flex; align-items: center; justify-content: center; padding: 0 16px; }
.compare-divider .arrow-icon {
  width: 40px; height: 40px; border-radius: 50%;
  background: var(--clay); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700; box-shadow: var(--sh-clay);
}
.compare-result {
  margin-top: 56px; text-align: center; padding: 48px 32px;
  background: linear-gradient(135deg, #f5f0e8 0%, #f0ebe3 100%);
  border-radius: var(--r-lg); position: relative; overflow: hidden;
}
.compare-result::before {
  content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
  background: radial-gradient(circle at 30% 40%, rgba(201,100,66,0.06) 0%, transparent 50%),
              radial-gradient(circle at 70% 60%, rgba(60,90,60,0.04) 0%, transparent 50%);
  pointer-events: none;
}
.compare-stats { display: flex; justify-content: center; align-items: flex-start; gap: 64px; position: relative; }
.compare-stat-item { text-align: center; }
.compare-stat-item .stat-num {
  font-family: var(--serif-en); font-size: clamp(40px, 6vw, 64px);
  font-weight: 600; color: var(--clay-deep); line-height: 1;
}
.compare-stat-item .stat-suffix { font-family: var(--serif-en); font-size: clamp(24px, 3vw, 36px); font-weight: 400; color: var(--clay); }
.compare-stat-item .stat-unit { font-size: 15px; font-weight: 500; color: var(--ink-2); margin-top: 8px; letter-spacing: 0.02em; }
.compare-stat-item .stat-desc { font-size: 13px; color: var(--ink-3); margin-top: 4px; max-width: 160px; }
.compare-stat-divider { width: 1px; height: 80px; background: var(--line-2); align-self: center; opacity: 0.5; }
.compare-result-note { margin-top: 32px; font-size: 18px; font-weight: 500; color: var(--ink); letter-spacing: 0.01em; position: relative; }
.compare-result-note .highlight { color: var(--clay-deep); font-weight: 600; }

/* CTA */
.cta-section { background: var(--paper); border-top: 1px solid var(--line); text-align: center; padding: 120px 0; }
.cta-section h2 { max-width: 700px; margin: 0 auto 20px; }
.cta-section .section-sub { margin: 0 auto 40px; text-align: center; }

/* Footer */
.footer { padding: 48px 0 36px; border-top: 1px solid var(--line); background: var(--ivory); color: var(--ink-3); font-size: 13px; }
.footer-inner { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 18px; }
.footer .brand { font-size: 15px; }
.footer .brand-logo { width: 24px; height: 24px; border-radius: 7px; }
.footer-meta { display: flex; gap: 20px; flex-wrap: wrap; font-size: 12.5px; }

/* Modal */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(31,31,30,.55);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  z-index: 100; display: flex;
  align-items: center; justify-content: center; padding: 24px;
  animation: fadeIn .2s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.modal {
  background: var(--paper); border-radius: var(--r-xl);
  padding: 40px; max-width: 440px; width: 100%; position: relative;
  box-shadow: var(--sh-3); animation: slideUp .25s cubic-bezier(.2,.8,.2,1);
}
@keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.modal-close {
  position: absolute; top: 16px; right: 16px;
  width: 32px; height: 32px; border: none; background: transparent;
  color: var(--ink-3); font-size: 22px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s; line-height: 1;
}
.modal-close:hover { background: var(--bone); color: var(--ink); }
.modal h3 { font-size: 24px; margin-bottom: 8px; }
.modal-sub { font-size: 13.5px; color: var(--ink-3); margin-bottom: 28px; line-height: 1.65; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 12.5px; color: var(--ink-2); margin-bottom: 6px; font-weight: 500; }
.field-row { display: flex; gap: 8px; }
.field input {
  width: 100%; height: 44px; padding: 0 14px;
  background: var(--ivory); border: 1px solid var(--line);
  border-radius: var(--r-sm); font-size: 14px; font-family: inherit;
  color: var(--ink); transition: all .15s;
}
.field input:focus { outline: none; border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,.15); }
.field-row .btn { flex-shrink: 0; height: 44px; padding: 0 16px; min-width: 108px; }
.field-row .btn:disabled { opacity: .6; cursor: not-allowed; }
.modal .btn-submit { width: 100%; height: 44px; margin-top: 8px; font-size: 14.5px; }
.modal-foot {
  text-align: center; margin-top: 20px; padding-top: 20px;
  border-top: 1px dashed var(--line-2); font-size: 12.5px; color: var(--ink-3); line-height: 1.65;
}
.modal-foot a { color: var(--clay-deep); border-bottom: 1px solid var(--clay-soft); }
.modal-error {
  margin-bottom: 18px; padding: 14px 16px;
  background: #FFF4F0; border: 1px solid var(--clay-soft);
  border-left: 3px solid var(--clay); border-radius: var(--r-sm);
  font-size: 13px; line-height: 1.65; color: var(--ink);
}
.modal-error strong { display: block; color: var(--clay-deep); margin-bottom: 4px; font-size: 14px; }
.modal-success { text-align: center; padding: 8px 0 16px; }
.modal-success .icon {
  width: 56px; height: 56px; border-radius: 50%;
  background: var(--leaf); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; font-weight: 700; margin: 0 auto 18px;
}
.modal-success h4 { font-size: 20px; margin-bottom: 8px; }
.modal-success p { font-size: 13.5px; color: var(--ink-3); margin: 0 0 24px; line-height: 1.65; }

/* Membership modal extras */
.benefits-list { margin-bottom: 24px; }
.benefit-item { font-size: 13px; color: var(--ink-2); line-height: 1.8; display: flex; align-items: center; }
.benefit-check { color: var(--clay); font-weight: 700; margin-right: 8px; flex-shrink: 0; }
.polling-indicator { display: inline-flex; align-items: center; gap: 6px; }
.spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--line); border-top-color: var(--clay);
  border-radius: 50%; animation: spin 0.8s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* BlurText */
.blur-word {
  display: inline-block;
  filter: blur(10px); opacity: 0; transform: translateY(20px);
  transition: filter 0.6s cubic-bezier(0.2,0,0,1), opacity 0.6s cubic-bezier(0.2,0,0,1), transform 0.6s cubic-bezier(0.2,0,0,1);
  will-change: filter, opacity, transform;
}
.blur-word.visible { filter: blur(0); opacity: 1; transform: translateY(0); }

/* RotatingText */
.rotating-wrap {
  display: inline-block; position: relative; overflow: hidden;
  vertical-align: baseline; height: 1.05em; line-height: 1.05;
  min-width: 2ch; transform: translateY(0.08em);
}
.rotating-inner {
  display: flex; flex-direction: column;
  animation: rotate-words 15s cubic-bezier(.4,.0,.2,1) infinite;
}
.rotating-word {
  height: 1.05em; line-height: 1.05;
  color: var(--clay-deep); font-family: var(--serif); font-weight: 600;
  white-space: nowrap; display: block; box-sizing: border-box;
}
@keyframes rotate-words {
  0%,16%   { transform: translateY(0); }
  20%,36%  { transform: translateY(-1.05em); }
  40%,56%  { transform: translateY(-2.1em); }
  60%,76%  { transform: translateY(-3.15em); }
  80%,96%  { transform: translateY(-4.2em); }
  100%     { transform: translateY(0); }
}

/* StarBorder button */
.star-btn {
  position: relative; display: inline-flex; align-items: center; justify-content: center;
  height: 48px; padding: 0 28px; border-radius: var(--r-md);
  background: var(--clay); color: #fff; font-size: 15px; font-weight: 500;
  font-family: inherit; border: none; cursor: pointer;
  overflow: hidden; transition: background .15s; box-shadow: var(--sh-clay);
}
.star-btn:hover { background: var(--clay-deep); transform: translateY(-1px); }
.star-btn::before, .star-btn::after {
  content: ''; position: absolute; width: 300%; height: 50%;
  border-radius: 50%; opacity: 0.5; pointer-events: none;
}
.star-btn::before {
  bottom: -12px; right: -250%;
  background: radial-gradient(circle, rgba(255,255,255,.4) 0%, transparent 10%);
  animation: star-bottom 6s linear infinite alternate;
}
.star-btn::after {
  top: -12px; left: -250%;
  background: radial-gradient(circle, rgba(255,255,255,.4) 0%, transparent 10%);
  animation: star-top 6s linear infinite alternate;
}
.star-btn > span { position: relative; z-index: 1; }
@keyframes star-bottom { 0% { transform: translate(0,0); opacity: .6; } 100% { transform: translate(-66%,0); opacity: 0; } }
@keyframes star-top { 0% { transform: translate(0,0); opacity: .6; } 100% { transform: translate(66%,0); opacity: 0; } }

/* MagnetButton */
.magnet-btn { position: relative; display: inline-flex; }
.magnet-inner { transition: transform .4s cubic-bezier(.2,0,0,1); will-change: transform; }
.magnet-btn:hover .magnet-inner { transition: transform .15s ease-out; }

/* CountUp */
.countup-num { font-family: var(--serif-en); font-weight: 600; font-size: 28px; color: var(--clay-deep); line-height: 1; }
.countup-unit { font-size: 14px; color: var(--ink-3); font-weight: 400; margin-left: 2px; }

/* Noise overlay */
.noise-overlay {
  position: absolute; inset: 0; pointer-events: none; z-index: 0;
  opacity: .35; mix-blend-mode: overlay;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.5'/%3E%3C/svg%3E");
  background-repeat: repeat; background-size: 200px 200px;
  animation: noise-jitter .3s steps(3) infinite;
}
@keyframes noise-jitter {
  0%   { transform: translate(0,0); }
  33%  { transform: translate(-1px,1px); }
  66%  { transform: translate(1px,-1px); }
  100% { transform: translate(0,0); }
}

/* Fade-Up */
@media (prefers-reduced-motion: no-preference) {
  .fade-up {
    opacity: 0; transform: translateY(28px);
    transition: opacity .7s cubic-bezier(.2,0,0,1), transform .7s cubic-bezier(.2,0,0,1);
  }
  .fade-up.visible { opacity: 1; transform: translateY(0); }
  .stagger-grid .fade-up:nth-child(1) { transition-delay: 0s; }
  .stagger-grid .fade-up:nth-child(2) { transition-delay: .08s; }
  .stagger-grid .fade-up:nth-child(3) { transition-delay: .16s; }
  .stagger-grid .fade-up:nth-child(4) { transition-delay: .24s; }
}

/* Responsive */
@media (max-width: 980px) {
  .hero { padding: 110px 0 80px; }
  .hero-grid { grid-template-columns: 1fr; gap: 32px; }
  .hero-visual { aspect-ratio: 1/.85; max-width: 520px; margin: 0 auto; }
  .hero-card { padding: 14px; }
  .hc-1 { top: 2%; left: -2%; width: 66%; }
  .hc-2 { top: 20%; left: 10%; width: 70%; }
  .hc-3 { top: 38%; right: 0; width: 66%; }
  .hc-4 { bottom: 2%; left: 6%; width: 64%; }
  .nav-links { display: none; }
  .pain-grid { grid-template-columns: 1fr; }
  .feature-block, .feature-block.reverse { grid-template-columns: 1fr; gap: 40px; }
  .feature-block.reverse .fb-text, .feature-block.reverse .fb-visual { order: initial; }
  .tools-grid { grid-template-columns: repeat(2, 1fr); }
  .section { padding: 80px 0; }
  .section-head { margin-bottom: 48px; }
  .compare-grid { grid-template-columns: 1fr; gap: 32px; }
  .compare-divider { display: none; }
  .compare-stats { flex-direction: column; gap: 32px; align-items: center; }
}
@media (max-width: 540px) {
  .container { padding: 0 20px; }
  .nav-inner { padding: 0 20px; }
  .hero { padding: 96px 0 60px; }
  .hero-title { font-size: 38px; }
  .hero-actions { flex-direction: column; align-items: stretch; }
  .hero-actions .btn { width: 100%; }
  .tools-grid { grid-template-columns: 1fr; }
  .modal { padding: 32px 24px; }
}
</style>

<!--
  Unscoped styles for child components (BlurText, RotatingText, HeroCardStack, CompareSection)
  Vue scoped CSS cannot penetrate into children rendered with h().
  .lp prefix limits global leakage.
-->
<style>
/* BlurText */
.lp .blur-word {
  display: inline-block;
  filter: blur(10px); opacity: 0; transform: translateY(20px);
  transition: filter 0.6s cubic-bezier(0.2,0,0,1), opacity 0.6s cubic-bezier(0.2,0,0,1), transform 0.6s cubic-bezier(0.2,0,0,1);
  will-change: filter, opacity, transform;
}
.lp .blur-word.visible { filter: blur(0); opacity: 1; transform: translateY(0); }

/* RotatingText */
.lp .rotating-wrap {
  display: inline-block; position: relative; overflow: hidden;
  vertical-align: baseline; height: 1.05em; line-height: 1.05;
  min-width: 2ch; transform: translateY(0.08em);
}
.lp .rotating-inner {
  display: flex; flex-direction: column;
  animation: lp-rotate-words 15s cubic-bezier(.4,.0,.2,1) infinite;
}
.lp .rotating-word {
  height: 1.05em; line-height: 1.05;
  color: var(--clay-deep); font-family: var(--serif); font-weight: 600;
  white-space: nowrap; display: block; box-sizing: border-box;
}
@keyframes lp-rotate-words {
  0%,16%   { transform: translateY(0); }
  20%,36%  { transform: translateY(-1.05em); }
  40%,56%  { transform: translateY(-2.1em); }
  60%,76%  { transform: translateY(-3.15em); }
  80%,96%  { transform: translateY(-4.2em); }
  100%     { transform: translateY(0); }
}

/* HeroCardStack */
.lp .hero-visual { position: relative; aspect-ratio: 1/1.05; perspective: 1200px; }
.lp .card-stack { position: relative; width: 100%; height: 100%; }
.lp .hero-card {
  position: absolute; background: var(--paper);
  border: 1px solid var(--line); border-radius: var(--r-lg);
  box-shadow: var(--sh-2); padding: 18px;
  cursor: pointer;
  transition: transform 500ms cubic-bezier(0.2, 0, 0, 1), box-shadow 400ms, opacity 400ms;
  will-change: transform, box-shadow;
}
.lp .hero-card .card-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; font-size: 18px; flex-shrink: 0; }
.lp .hero-card .card-title { font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 4px; }
.lp .hero-card .card-desc { font-size: 12px; color: var(--ink-3); line-height: 1.6; }
.lp .hero-card .card-tag {
  display: inline-block; font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 6px; margin-top: 10px;
}
.lp .hc-1 { top: 0; left: -4%; width: 64%; z-index: 1; transform: rotate(-3deg) scale(0.92); opacity: 0.7; }
.lp .hc-2 { top: 18%; left: 14%; width: 68%; z-index: 2; transform: rotate(1deg) scale(0.96); opacity: 0.85; }
.lp .hc-3 { top: 36%; right: -2%; width: 64%; z-index: 3; transform: rotate(-2deg) scale(0.96); opacity: 0.85; }
.lp .hc-4 { bottom: 0; left: 4%; width: 62%; z-index: 1; transform: rotate(2deg) scale(0.92); opacity: 0.7; }
.lp .hc-active { transform: rotate(0deg) scale(1.04) !important; z-index: 10 !important; opacity: 1 !important; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
.lp .hc-dim { opacity: 0.5 !important; }
.lp .hc-info .card-icon { background: rgba(201,100,66,0.1); }
.lp .hc-info .card-tag { background: rgba(201,100,66,0.1); color: var(--clay-deep); }
.lp .hc-pipe .card-icon { background: rgba(92,138,92,0.1); }
.lp .hc-pipe .card-tag { background: rgba(92,138,92,0.1); color: var(--leaf); }
.lp .hc-xform .card-icon { background: rgba(140,120,170,0.1); }
.lp .hc-xform .card-tag { background: rgba(140,120,170,0.1); color: #7a6490; }
.lp .hc-pub .card-icon { background: rgba(80,140,200,0.1); }
.lp .hc-pub .card-tag { background: rgba(80,140,200,0.1); color: #3a7ab8; }
.lp .card-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 12px; color: var(--ink-2); }
.lp .card-row + .card-row { border-top: 1px solid var(--line); }
.lp .card-row .cr-icon { font-size: 14px; width: 20px; text-align: center; flex-shrink: 0; }
.lp .card-row .cr-label { flex: 1; }
.lp .card-row .cr-status { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
.lp .cr-ok { background: rgba(92,138,92,0.1); color: var(--leaf); }
.lp .cr-run { background: rgba(201,100,66,0.1); color: var(--clay-deep); animation: lp-pulse 2s infinite; }
.lp .cr-blue { background: rgba(80,140,200,0.1); color: #3a7ab8; }
.lp .pipe-steps { display: flex; gap: 4px; margin-top: 8px; }
.lp .pipe-step { flex: 1; height: 4px; border-radius: 2px; background: var(--line); position: relative; overflow: hidden; }
.lp .pipe-step.done { background: var(--leaf); }
.lp .pipe-step.active::after {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 60%;
  background: var(--clay); border-radius: 2px; animation: lp-pipePulse 1.5s ease-in-out infinite;
}
@keyframes lp-pipePulse { 0%,100% { width: 30%; } 50% { width: 80%; } }
.lp .pipe-label { font-family: var(--mono); font-size: 10px; color: var(--ink-3); margin-top: 4px; }
@keyframes lp-pulse { 0%,100% { box-shadow: 0 0 0 4px rgba(204,120,92,.18); } 50% { box-shadow: 0 0 0 7px rgba(204,120,92,.06); } }

/* MagnetButton */
.lp .magnet-btn { position: relative; display: inline-flex; }
.lp .magnet-inner { transition: transform .4s cubic-bezier(.2,0,0,1); will-change: transform; }
.lp .magnet-btn:hover .magnet-inner { transition: transform .15s ease-out; }

/* CountUp */
.lp .countup-num { font-family: var(--serif-en); font-weight: 600; font-size: 28px; color: var(--clay-deep); line-height: 1; }
.lp .countup-unit { font-size: 14px; color: var(--ink-3); font-weight: 400; margin-left: 2px; }

/* CompareSection */
.lp .compare-section { background: var(--paper); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.lp .compare-section .section-head.center { text-align: center; max-width: 760px; margin-left: auto; margin-right: auto; }
.lp .compare-section .section-sub { max-width: 620px; margin-left: auto; margin-right: auto; }
.lp .compare-grid { display: grid; grid-template-columns: 1fr auto 1fr; gap: 0; margin-top: 48px; align-items: stretch; }
.lp .compare-col { padding: 40px 32px; border-radius: var(--r-lg); }
.lp .compare-col.old { background: var(--bone); border: 1px solid var(--line-2); opacity: .75; }
.lp .compare-col.new {
  background: var(--paper); border: 2px solid var(--clay); box-shadow: var(--sh-clay);
  position: relative; padding-top: 52px;
}
.lp .compare-col.new::before {
  content: '推荐'; position: absolute; top: 12px; left: 24px;
  background: var(--clay); color: #fff; font-size: 11px; font-weight: 700;
  padding: 3px 12px; border-radius: 999px; letter-spacing: .08em;
}
.lp .compare-header { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; padding-bottom: 18px; border-bottom: 1px dashed var(--line-2); }
.lp .compare-header .emoji { font-size: 28px; }
.lp .compare-header h3 { font-size: 20px; margin: 0; }
.lp .compare-header .time { font-family: var(--mono); font-size: 13px; color: var(--ink-3); margin-left: auto; }
.lp .compare-col.new .compare-header .time { color: var(--clay-deep); font-weight: 700; }
.lp .compare-steps { display: flex; flex-direction: column; gap: 16px; }
.lp .compare-step { display: flex; gap: 12px; align-items: flex-start; }
.lp .compare-step .dot { flex-shrink: 0; width: 8px; height: 8px; border-radius: 50%; margin-top: 7px; }
.lp .compare-col.old .dot { background: var(--ink-3); }
.lp .compare-col.new .dot { background: var(--clay); }
.lp .compare-step .step-content { flex: 1; }
.lp .compare-step .step-content strong { display: block; font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.lp .compare-step .step-content span { font-size: 13px; color: var(--ink-3); line-height: 1.5; }
.lp .compare-divider { display: flex; align-items: center; justify-content: center; padding: 0 16px; }
.lp .compare-divider .arrow-icon {
  width: 40px; height: 40px; border-radius: 50%;
  background: var(--clay); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700; box-shadow: var(--sh-clay);
}
.lp .compare-result {
  margin-top: 56px; text-align: center; padding: 48px 32px;
  background: linear-gradient(135deg, #f5f0e8 0%, #f0ebe3 100%);
  border-radius: var(--r-lg); position: relative; overflow: hidden;
}
.lp .compare-result::before {
  content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
  background: radial-gradient(circle at 30% 40%, rgba(201,100,66,0.06) 0%, transparent 50%),
              radial-gradient(circle at 70% 60%, rgba(60,90,60,0.04) 0%, transparent 50%);
  pointer-events: none;
}
.lp .compare-stats { display: flex; justify-content: center; align-items: flex-start; gap: 64px; position: relative; }
.lp .compare-stat-item { text-align: center; }
.lp .compare-stat-item .stat-num {
  font-family: var(--serif-en); font-size: clamp(40px, 6vw, 64px);
  font-weight: 600; color: var(--clay-deep); line-height: 1;
}
.lp .compare-stat-item .stat-suffix { font-family: var(--serif-en); font-size: clamp(24px, 3vw, 36px); font-weight: 400; color: var(--clay); }
.lp .compare-stat-item .stat-unit { font-size: 15px; font-weight: 500; color: var(--ink-2); margin-top: 8px; letter-spacing: 0.02em; }
.lp .compare-stat-item .stat-desc { font-size: 13px; color: var(--ink-3); margin-top: 4px; max-width: 160px; }
.lp .compare-stat-divider { width: 1px; height: 80px; background: var(--line-2); align-self: center; opacity: 0.5; }
.lp .compare-result-note { margin-top: 32px; font-size: 18px; font-weight: 500; color: var(--ink); letter-spacing: 0.01em; position: relative; }
.lp .compare-result-note .highlight { color: var(--clay-deep); font-weight: 600; }

/* Fade-Up — must be unscoped for child components */
@media (prefers-reduced-motion: no-preference) {
  .lp .fade-up {
    opacity: 0; transform: translateY(28px);
    transition: opacity .7s cubic-bezier(.2,0,0,1), transform .7s cubic-bezier(.2,0,0,1);
  }
  .lp .fade-up.visible { opacity: 1; transform: translateY(0); }
  .lp .stagger-grid .fade-up:nth-child(1) { transition-delay: 0s; }
  .lp .stagger-grid .fade-up:nth-child(2) { transition-delay: .08s; }
  .lp .stagger-grid .fade-up:nth-child(3) { transition-delay: .16s; }
  .lp .stagger-grid .fade-up:nth-child(4) { transition-delay: .24s; }
}
</style>
