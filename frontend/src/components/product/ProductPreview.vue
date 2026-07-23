<template>
  <section class="preview-page" :class="`is-${product}`">
    <div class="preview-window" aria-hidden="true">
      <div class="preview-topbar">
        <span class="preview-dot"></span><span class="preview-dot"></span><span class="preview-dot"></span>
        <span class="preview-address">IP罗盘 · {{ plan.label }}</span>
      </div>

      <div v-if="product === 'potential_commercial'" class="commercial-preview">
        <div class="preview-heading">
          <div><b>潜在商单</b><small>最近 10 天 · 品牌投放情报</small></div>
          <span>12 个品牌</span>
        </div>
        <div class="preview-chips"><i>全部</i><i>内容创作</i><i>AI平台</i><i>办公效率</i></div>
        <div class="commercial-cards">
          <article v-for="item in commercialCards" :key="item.brand">
            <div class="card-brand"><b>{{ item.brand }}</b><span>{{ item.count }} 篇投放</span></div>
            <p>{{ item.title }}</p><small>{{ item.account }} · {{ item.time }}</small>
          </article>
        </div>
      </div>

      <div v-else-if="product === 'practical_camp'" class="course-preview">
        <aside><b>AI垂类公众号实战营</b><small>从选题到商业变现</small>
          <i v-for="chapter in courseChapters" :key="chapter">{{ chapter }}</i>
        </aside>
        <article><span>第 03 章 · 选题篇</span><h2>让每一个选题，<br>都更接近一次合作</h2><p>真正有商业价值的选题，不是追热点，而是找到内容、受众与品牌需求的交点。</p><div class="course-lines"><i></i><i></i><i></i></div></article>
      </div>

      <div v-else-if="product === 'xhs_topic'" class="xhs-preview">
        <aside><b>小红书选题</b><small>DESK EDITION · 每 2 小时更新</small>
          <i>今日新切口</i><i>话题监测</i><i>爆款素材库</i><i>关键词热度</i>
        </aside>
        <article><span>AI 选题号外</span><h2>小红书爆款切口，<br>每天替你盯出来</h2><p>聚合小红书公开笔记采样，按语义话题聚类，标注今日新切口与发酵信号，帮你抢先找到值得写的角度。</p><div class="xhs-lines"><i></i><i></i><i></i></div></article>
      </div>

      <div v-else class="creation-preview">
        <aside><b>IP罗盘</b><i>信息选题</i><i>创作工具</i><i>内容仿写</i><i>创作历史</i></aside>
        <article><div class="creation-title"><div><small>今日推荐选题</small><b>AI 助手开始进入真实业务场景</b></div><span>新建创作</span></div>
          <div class="topic-row" v-for="(topic, index) in creationTopics" :key="topic"><em>{{ String(index + 1).padStart(2, '0') }}</em><b>{{ topic }}</b><span>{{ 96 - index * 3 }} 分</span></div>
        </article>
      </div>
    </div>

    <div class="preview-veil"></div>
    <div class="preview-lock">
      <div class="lock-icon">⌁</div>
      <span class="eyebrow">PREVIEW · 已为你保留</span>
      <h1>{{ plan.label }}暂未开通</h1>
      <p>{{ plan.description }}</p>
      <button class="unlock-btn" @click="goUnlock">{{ plan.action }} <span>→</span></button>
      <span class="price">{{ plan.price }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const props = defineProps({ product: { type: String, required: true } })
const router = useRouter()
const route = useRoute()

const plans = {
  creation_tool: { label: '创作工具', price: '¥699 / 月', action: '开通创作工具', description: '解锁信息选题、创作工具、内容仿写与创作历史。' },
  potential_commercial: { label: '潜在商单', price: '¥299 / 月', action: '立即开通', description: '解锁品牌投放线索、账号、时间与原文链接，快速发现可合作机会。' },
  practical_camp: { label: 'AI 垂类公众号实战营', price: '¥1980 / 年', action: '查看实战营', description: '报名后即可进入完整课程资料，从选题到商业变现系统学习。' },
  xhs_topic: { label: '小红书选题', price: '灰测中 · 限时开放', action: '申请开通', description: '灰测期间由管理员定向开放，解锁小红书话题监测、今日新切口与爆款素材库。' },
}
const commercialCards = [
  { brand: '深度求索', count: 4, title: 'AI 搜索场景内容投放持续升温', account: 'AI 产品观察', time: '今天 10:20' },
  { brand: '字节跳动', count: 3, title: '办公效率工具投放策略拆解', account: '科技新知', time: '昨天 16:42' },
  { brand: '智谱 AI', count: 2, title: '开发者生态合作内容正在释放', account: '极客视角', time: '7 月 08 日' },
]
const courseChapters = ['01 · 账号定位', '02 · 赛道选择', '03 · 商业化选题', '04 · 内容生产', '05 · 商单交付']
const creationTopics = ['Agent 落地后，企业最愿意为哪类内容买单？', 'AI 办公工具集体更新，怎么写才有合作价值？', '一个真实案例，看懂品牌筛选创作者的逻辑']
const plan = computed(() => plans[props.product] || plans.creation_tool)

const goUnlock = () => {
  if (props.product === 'practical_camp') {
    router.push('/camp')
    return
  }
  if (props.product === 'xhs_topic') {
    // 小红书选题处于灰测阶段，不开放自助付费，引导用户联系管理员开通。
    ElMessage.info('小红书选题灰测中，请联系管理员为你开通')
    return
  }
  router.push({ name: 'Landing', query: { show: 'membership', product: props.product, redirect: route.fullPath } })
}
</script>

<style scoped>
.preview-page { min-height: 600px; position: relative; overflow: hidden; border: 1px solid var(--line); border-radius: var(--r-lg); background: #e9e4dc; box-shadow: 0 16px 46px rgba(68, 51, 33, .08); }
.preview-window { position: absolute; inset: 22px; overflow: hidden; border: 1px solid rgba(94, 77, 60, .18); border-radius: 14px; background: #fbfaf7; filter: blur(5px); transform: scale(1.018); opacity: .88; }
.preview-topbar { height: 40px; display: flex; align-items: center; gap: 6px; padding: 0 14px; border-bottom: 1px solid #e6dfd5; background: #f2eee8; }.preview-dot { width: 8px; height: 8px; border-radius: 50%; background: #cfc5b8; }.preview-address { margin-left: 10px; color: #82796e; font-size: 11px; }.preview-veil { position: absolute; inset: 0; background: linear-gradient(135deg, rgba(246,243,238,.32), rgba(232,222,211,.64)); backdrop-filter: blur(2px); }
.preview-lock { position: absolute; z-index: 2; left: 50%; top: 50%; width: min(430px, calc(100% - 42px)); box-sizing: border-box; padding: 30px 32px 27px; transform: translate(-50%, -50%); text-align: center; background: rgba(255,253,249,.94); border: 1px solid rgba(204,120,92,.48); border-radius: 18px; box-shadow: 0 24px 68px rgba(61,48,35,.2); backdrop-filter: blur(16px); }.lock-icon { width: 40px; height: 40px; margin: 0 auto 11px; display: grid; place-items: center; border-radius: 50%; background: var(--clay); color: #fff; font-size: 25px; }.eyebrow { color: var(--clay-deep); font-size: 11px; letter-spacing: .12em; font-weight: 700; }.preview-lock h1 { margin: 8px 0 10px; color: var(--ink); font-family: var(--serif); font-size: 24px; }.preview-lock p { margin: 0 auto 19px; color: var(--ink-3); font-size: 14px; line-height: 1.7; }.unlock-btn { border: 0; border-radius: 9px; padding: 12px 19px; color: #fff; background: var(--clay); cursor: pointer; font-weight: 650; font-size: 14px; box-shadow: 0 8px 18px rgba(204,120,92,.26); }.unlock-btn:hover { background: var(--clay-deep); transform: translateY(-1px); }.unlock-btn span { margin-left: 6px; }.price { display: block; margin-top: 11px; color: var(--ink-4); font-size: 12px; }
.commercial-preview { padding: 24px; }.preview-heading { display: flex; justify-content: space-between; align-items: end; }.preview-heading b { display: block; color: #28231e; font-size: 23px; }.preview-heading small { display: block; margin-top: 7px; color: #8c8378; }.preview-heading span { padding: 7px 10px; border-radius: 99px; background: #f5e6df; color: #a76047; font-size: 12px; }.preview-chips { display: flex; gap: 8px; margin: 21px 0 17px; }.preview-chips i { padding: 7px 11px; border: 1px solid #ded6cb; border-radius: 99px; color: #7d7368; font-size: 12px; font-style: normal; }.commercial-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }.commercial-cards article { padding: 15px; border: 1px solid #e4ddd3; border-radius: 10px; background: #fff; }.card-brand { display: flex; justify-content: space-between; gap: 6px; }.card-brand b { color: #34302b; font-size: 14px; }.card-brand span { color: #ad674d; font-size: 11px; }.commercial-cards p { min-height: 42px; margin: 17px 0 12px; color: #4f4942; font-size: 13px; line-height: 1.6; }.commercial-cards small { color: #938a80; font-size: 11px; }
.course-preview { height: calc(100% - 40px); display: grid; grid-template-columns: 190px 1fr; }.course-preview aside, .creation-preview aside, .xhs-preview aside { padding: 24px 18px; background: #ede6db; border-right: 1px solid #ddd5c9; }.course-preview aside b, .xhs-preview aside b { display: block; color: #312a24; font-size: 14px; }.course-preview aside small, .xhs-preview aside small { display: block; margin: 6px 0 24px; color: #8b8176; font-size: 11px; }.course-preview aside i, .xhs-preview aside i { display: block; margin: 0 0 13px; color: #645c54; font-size: 12px; font-style: normal; }.course-preview article, .xhs-preview article { padding: 48px 52px; }.course-preview article span, .xhs-preview article span { color: #ba694d; font-size: 12px; font-weight: 700; letter-spacing: .08em; }.course-preview h2, .xhs-preview h2 { margin: 17px 0; color: #302a25; font-family: var(--serif); font-size: 33px; line-height: 1.35; }.course-preview p, .xhs-preview p { max-width: 490px; color: #71685f; line-height: 1.9; }.course-lines, .xhs-lines { margin-top: 30px; }.course-lines i, .xhs-lines i { display: block; height: 10px; margin: 12px 0; border-radius: 6px; background: #e2dad0; }.course-lines i:nth-child(2), .xhs-lines i:nth-child(2) { width: 87%; }.course-lines i:nth-child(3), .xhs-lines i:nth-child(3) { width: 64%; }
.xhs-preview { height: calc(100% - 40px); display: grid; grid-template-columns: 190px 1fr; }
.creation-preview { height: calc(100% - 40px); display: grid; grid-template-columns: 175px 1fr; }.creation-preview aside b { display: block; margin-bottom: 26px; color: #332b25; font-size: 18px; }.creation-preview aside i { display: block; margin: 0 -7px 13px; padding: 9px; border-radius: 7px; color: #61574f; font-size: 13px; font-style: normal; }.creation-preview aside i:first-of-type { background: #f5ddd2; color: #a35e45; }.creation-preview article { padding: 30px 32px; }.creation-title { display: flex; justify-content: space-between; align-items: end; margin-bottom: 25px; }.creation-title small { display: block; color: #9a9085; }.creation-title b { display: block; margin-top: 8px; color: #302a25; font-size: 20px; }.creation-title span { padding: 9px 12px; border-radius: 7px; background: #c9785d; color: #fff; font-size: 12px; }.topic-row { display: flex; align-items: center; gap: 14px; margin-top: 10px; padding: 17px; border: 1px solid #e4ddd4; border-radius: 10px; background: #fff; }.topic-row em { color: #bf7257; font-style: normal; font-weight: 700; }.topic-row b { flex: 1; color: #4e4740; font-size: 13px; }.topic-row span { color: #bf7257; font-size: 12px; }
@media (max-width: 680px) { .preview-page { min-height: 540px; }.preview-window { inset: 12px; }.commercial-preview { padding: 18px; }.commercial-cards { grid-template-columns: 1fr; }.commercial-cards article:nth-child(3) { display: none; }.course-preview { grid-template-columns: 120px 1fr; }.course-preview aside { padding: 18px 11px; }.course-preview article { padding: 35px 21px; }.course-preview h2 { font-size: 23px; }.creation-preview { grid-template-columns: 118px 1fr; }.creation-preview aside { padding: 18px 11px; }.creation-preview article { padding: 25px 18px; }.preview-lock { padding: 26px 22px 23px; } }
</style>
