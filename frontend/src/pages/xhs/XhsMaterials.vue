<template>
  <section class="xhs-page">
    <header class="hero masthead"><div class="masthead-brand"><span class="kicker">XHS · AI TOPIC INDEX</span><h1>小红书素材库</h1></div><span class="band-rule"></span><nav class="topic-tabs" aria-label="小红书选题视图"><button v-for="tab in tabs" :key="tab.id" type="button" :class="{active:activeTab===tab.id}" @click="selectTab(tab.id)">{{ tab.label }}<small>{{ tab.hint }}</small></button></nav><div class="masthead-right"><span class="masthead-date">选题号外 · {{ todayEdition }}版</span><span class="live-dot"><i></i>监测中 · 每 2 小时更新</span></div></header>
    <div class="monitor-strip"><div class="ms-item"><b>{{ monitor.topicCount }}</b>个话题在监测</div><span class="ms-sep"></span><div class="ms-item"><b>{{ monitor.sampleCount }}</b>篇样本笔记 <em>今日 +{{ monitor.todayNewNotes }}</em></div><span class="ms-sep"></span><div class="ms-item"><b>{{ monitor.freshCount }}</b>个新切口信号</div><span class="ms-sep"></span><div class="ms-item"><b>{{ compact(monitor.maxLikes) }}</b>单篇最高赞</div><div class="ms-right">DESK EDITION · 数据来源：小红书公开笔记采样</div></div>
    <div v-if="activeTab==='hot'" class="screen-one">
    <section v-if="topics.length" class="topic-board">
      <div class="board" :class="{solo:!railTopics.length}">
        <article class="tb-topic tb-hero" :class="{selected:filters.semantic_topic_id===headline.topic_id,'no-cover':!topNote}" role="button" tabindex="0" :aria-pressed="filters.semantic_topic_id===headline.topic_id" @click="openTopic(headline)" @keydown.enter.prevent="openTopic(headline)" @keydown.space.prevent="openTopic(headline)">
          <span class="sel-chip">✓ 筛选中</span><div class="hero-main"><div class="hero-top"><span class="rank">01</span><span class="badge" :class="headline.kind==='single'?'badge-single':'badge-new'">{{ headline.kind==='single'?'单篇高热':'今日新切口' }}</span><span class="page-tag">A1 · 头条</span></div><h3 class="hero-title">{{ headline.topic }}</h3><p class="hero-deck">{{ headline.ai_highlight || evidence(headline) }}</p>
          <ul class="hero-meta"><li><b>论据</b>今天形成内容热度</li><li><b>{{ headline.sample_count }}</b> 篇样本</li><li>最高 <b>{{ compact(headline.max_likes) }}</b> 赞</li></ul>
          <div v-if="heroMoreNotes.length" class="hero-notes"><div class="notes-label">其余代表笔记 · MORE NOTES</div><button v-for="(n,ni) in heroMoreNotes" :key="n.note_id" type="button" class="note" @click.stop="openDetail({note_id:n.note_id})"><span class="no">NO.{{ ni+2 }}</span><span class="t">「{{ n.title }}」</span><span class="leader"></span><span class="lk"><b>{{ compact(n.likes) }}</b> 赞</span></button></div></div>
          <figure v-if="topNote" class="hero-cover"><img :src="imageUrl(topNote)" :alt="topNote.title" loading="lazy" referrerpolicy="no-referrer" @error="imageFailed($event,topNote,'cover')"><span class="cover-wm">{{ headline.topic.slice(0,1) }}</span><span class="cover-tag">置顶代表笔记</span><figcaption @click.stop="openDetail({note_id:topNote.note_id})"><span class="cover-title">「{{ topNote.title }}」</span><span class="like-chip"><i>♥</i> {{ compact(topNote.likes) }} 赞 · 话题内最热</span></figcaption></figure>
        </article>
        <aside v-if="railTopics.length" class="rail"><div class="rail-head"><b>其余要闻</b><span>A2 · 02—{{ String(railTopics.length+1).padStart(2,'0') }}</span></div>
          <article v-for="(t,i) in railTopics" :key="t.topic_id" class="tb-topic rail-item" :class="{selected:filters.semantic_topic_id===t.topic_id}" role="button" tabindex="0" @click="openTopic(t)" @keydown.enter.prevent="openTopic(t)" @keydown.space.prevent="openTopic(t)"><span class="sel-chip">✓ 筛选中</span><div class="ri-top"><span class="rank">{{ String(i+2).padStart(2,'0') }}</span><h3 class="ri-name">{{ t.topic }}</h3><span class="badge sm" :class="t.kind==='single'?'badge-single':'badge-new'">{{ t.kind==='single'?'单篇高热':'今日新切口' }}</span></div><p v-if="t.ai_highlight" class="ri-deck">{{ t.ai_highlight }}</p><p class="ri-meta">{{ evidence(t) }}</p><ul v-if="t.notes.length" class="ri-notes"><li v-for="n in t.notes.slice(0,3)" :key="n.note_id" @click.stop="openDetail({note_id:n.note_id})"><span class="t">「{{ n.title }}」</span><span class="l">{{ compact(n.likes) }}<em>赞</em></span></li></ul></article>
        </aside>
      </div>
    </section><el-empty v-else description="今日暂无形成规模的内容话题"/></div>
    <section v-if="activeTab==='fermenting'" class="signals-section">
      <div class="page-marker"><span class="pm-no">A2</span><span class="pm-name">趋势版</span><span class="pm-note">近 7 日趋势 · {{ fermentTopics.length }} 组信号追踪<template v-if="boards.generated_at"> · 更新于 {{ dateTime(boards.generated_at) }}</template></span></div>
      <div v-if="boardsLoading" class="signal-grid"><el-skeleton v-for="i in 4" :key="i" animated class="signal-skeleton"/></div>
      <div v-else-if="visibleFermentTopics.length" class="signal-grid">
        <article v-for="(t,i) in visibleFermentTopics" :key="t.topic_id" class="signal-card" role="button" tabindex="0" @click="openTopic(t)" @keydown.enter.prevent="openTopic(t)" @keydown.space.prevent="openTopic(t)">
          <div class="sc-top"><span class="sc-signal"><b>{{ String(i+1).padStart(2,'0') }}</b>SIGNAL</span><span class="sc-day">DAY {{ t.active_days>=7?'7+':t.active_days }}</span></div>
          <h3 class="sc-topic">{{ t.topic }}</h3>
          <p v-if="t.ai_highlight" class="sc-sub">{{ t.ai_highlight }}</p>
          <div class="sc-numbers"><span class="sc-big">{{ t.sample_count }}<small>篇</small></span><span class="sc-numtext">近 24 小时新增 <b>{{ t.new_notes_24h }} 篇</b> / <b>{{ t.new_authors_24h }} 位</b>新作者<br>累计 {{ t.sample_count }} 篇 · {{ t.author_count }} 位作者 · 最高 {{ compact(t.max_likes) }} 赞</span></div>
          <div class="sc-chart"><div class="sc-chart-head"><span>近 7 次监测</span><b>互动走势</b></div><div class="sc-chart-plot"><svg viewBox="0 0 100 90" preserveAspectRatio="none" aria-label="近 7 次监测互动走势"><defs><linearGradient :id="`trend-area-${i}`" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#cc785c" stop-opacity=".24"/><stop offset="100%" stop-color="#cc785c" stop-opacity="0"/></linearGradient></defs><line v-for="y in [22,50,78]" :key="y" x1="2" :y1="y" x2="98" :y2="y" class="grid-line"/><path :d="sparkGeometry(t).area" :fill="`url(#trend-area-${i})`" class="spark-area"/><path :d="sparkGeometry(t).line" class="spark-line"/></svg><span class="spark-end" :style="{left:`${sparkGeometry(t).last.x}%`,top:`${sparkGeometry(t).last.y/90*100}%`}"></span></div></div>
          <div class="sc-chips"><span v-for="e in topicEvidence(t)" :key="e" class="chip">{{ e }}</span></div>
          <div class="sc-notes"><div v-for="n in (t.notes||[]).slice(0,3)" :key="n.note_id" class="note-item" @click.stop="openDetail({note_id:n.note_id})"><span class="ni-title">「{{ n.title }}」</span><span class="ni-like"><b>{{ compact(n.likes) }}</b> 赞</span></div></div>
          <div class="sc-foot"><span>最高 <b>{{ compact(t.max_likes) }}</b> 赞</span><a @click.stop="openTopic(t)">查看趋势与全部笔记 →</a></div>
        </article>
      </div>
      <el-empty v-else description="暂无持续发酵的内容话题"/><button v-if="fermentTopics.length>visibleFerment" type="button" class="more-ferment" @click="visibleFerment+=6">查看更多发酵话题</button>
    </section>
    <div v-if="activeTab==='all'" class="screen-two">
    <div v-if="filters.semantic_topic_id" class="semantic-filter"><span>正在查看语义话题「{{ activeTopicName }}」的相关素材</span><button type="button" @click="clearSemanticFilter">清除筛选</button></div>
    <div ref="filtersEl" class="filters"><el-select v-model="filters.range" @change="load"><el-option label="近 1 天" value="1d"/><el-option label="近 3 天" value="3d"/><el-option label="近 7 天" value="7d"/></el-select><el-input v-model="filters.keyword" clearable placeholder="关键词" @keyup.enter="load"/><el-input v-model="filters.topic" clearable placeholder="AI 话题" @keyup.enter="load"/><el-select v-model="filters.note_type" @change="load"><el-option label="全部类型" value="all"/><el-option label="视频" value="video"/><el-option label="图文" value="image"/></el-select><el-select v-model="filters.sort" @change="load"><el-option label="综合排序" value="comprehensive"/><el-option label="最新" value="latest"/><el-option label="点赞" value="likes"/><el-option label="收藏" value="collects"/><el-option label="评论" value="comments"/></el-select><el-input v-model="filters.q" clearable placeholder="搜索标题、作者或话题" @keyup.enter="load"/><button class="reset" @click="reset">重置</button></div>
    <div class="metrics"><article><span>精选素材</span><strong>{{ total }}</strong></article><article><span>热门话题</span><strong>{{ keywordCount }}</strong></article><article><span>视频 · 图文</span><strong>{{ videoCount }} · {{ imageCount }}</strong></article><article><span>最高点赞</span><strong>{{ compact(maxLikes) }}</strong></article></div>
    <div class="section-title"><h2>高赞素材</h2><span :class="{loading}">{{ loading ? '正在切换…' : `${total} 篇` }}</span></div>
    <div class="body-grid"><div><div v-if="loading&&!items.length" class="material-grid"><el-skeleton v-for="i in 6" :key="i" animated class="material-skeleton"><template #template><el-skeleton-item variant="image" class="skeleton-cover"/><div class="skeleton-lines"><el-skeleton-item variant="h3"/><el-skeleton-item variant="text"/><el-skeleton-item variant="text"/></div></template></el-skeleton></div><div v-else-if="items.length" class="material-grid" :class="{'is-page-loading':loading}"><article v-for="(note,index) in items" :key="note.note_id" class="material-card" @click="openDetail(note)"><div class="cover" :class="{'is-loaded':coverLoaded(note)}"><span class="cover-loading-mark" aria-hidden="true"><i></i><b>正在加载封面</b></span><img :src="imageUrl(note)" :alt="note.title" :loading="index<6?'eager':'lazy'" decoding="async" :fetchpriority="index<6?'high':'low'" referrerpolicy="no-referrer" @load="coverDidLoad(note)" @error="imageFailed($event,note,'cover')"><span class="type">{{ note.note_type==='video' ? '▶ 视频' : '▧ 图文' }}</span></div><div class="content"><h3>{{ note.title }}</h3><div class="meta"><div class="chips"><span v-for="tag in [...note.keywords,...note.ai_topics].map(cleanTag).filter(Boolean).slice(0,4)" :key="tag">{{ tag }}</span></div><div class="author"><img :src="avatarUrl(note)" loading="lazy" decoding="async" fetchpriority="low" referrerpolicy="no-referrer" @error="imageFailed($event,note,'avatar')"><span>{{ note.author.nickname || '未知作者' }} · {{ relative(note.published_at) }}</span></div></div><div class="engagement"><div class="stat"><b>{{ metric(note.engagement.likes) }}</b><span>点赞</span></div><div class="stat"><b>{{ metric(note.engagement.collects) }}</b><span>收藏</span></div><div class="stat"><b>{{ metric(note.engagement.comments) }}</b><span>评论</span></div><div class="stat"><b>{{ metric(note.engagement.shares) }}</b><span>转发</span></div></div></div></article></div><el-empty v-else description="暂时没有符合条件的素材"/><el-pagination v-if="total>filters.page_size" class="materials-pagination" background layout="prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" :disabled="loading" @current-change="load"/></div><aside><div class="side-card"><h3>当前筛选</h3><p>{{ rangeLabel }} · {{ filters.keyword || '全部关键词' }} · {{ typeLabel }}</p></div><div class="side-card"><h3>关键词热度</h3><button v-for="item in keywordHeat" :key="item[0]" @click="filters.keyword=item[0];load()"><span>{{ item[0] }}</span><b>{{ item[1] }}</b></button></div></aside></div>
    </div>
    <teleport to="body"><transition name="xhs-modal"><div v-if="drawer" class="modal-mask" @click.self="drawer=false"><div class="modal-card" role="dialog" aria-modal="true"><button class="modal-close" type="button" aria-label="关闭" @click="drawer=false">×</button><template v-if="selected"><div class="modal-media"><img class="bg" :src="imageUrl(selected)" alt="" aria-hidden="true" referrerpolicy="no-referrer"><img class="fg" :src="imageUrl(selected)" :alt="selected.title" referrerpolicy="no-referrer" @error="imageFailed($event,selected,'cover')"></div><div class="modal-side"><div class="modal-author"><img :src="avatarUrl(selected)" :alt="selected.author.nickname" referrerpolicy="no-referrer" @error="imageFailed($event,selected,'avatar')"><span class="name">{{ selected.author.nickname || '未知作者' }}</span><a :href="selected.original_url" target="_blank" rel="noopener noreferrer">打开原文</a></div><h2 class="modal-title">{{ selected.title }}</h2><p class="modal-content">{{ cleanContent(selected.content) || '暂无正文' }}</p><div class="modal-tail"><div class="chips"><span v-for="tag in [...selected.native_tags,...selected.ai_topics].map(cleanTag).filter(Boolean)" :key="tag">{{ tag }}</span></div><div class="modal-time">发布于 {{ dateTime(selected.published_at) }} · 采集于 {{ dateTime(selected.first_discovered_at) }}<template v-if="selected.keywords.length"> · 相关话题：{{ selected.keywords.join('、') }}</template></div></div><div class="modal-foot"><span title="点赞" aria-label="点赞"><svg class="ic" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg><b>{{ metric(selected.engagement.likes) }}</b></span><span title="收藏" aria-label="收藏"><svg class="ic" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg><b>{{ metric(selected.engagement.collects) }}</b></span><span title="评论" aria-label="评论"><svg class="ic" viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg><b>{{ metric(selected.engagement.comments) }}</b></span><span title="转发" aria-label="转发"><svg class="ic" viewBox="0 0 24 24"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg><b>{{ metric(selected.engagement.shares) }}</b></span></div></div></template></div></div></transition></teleport>
  </section>
</template>
<script setup>
import { computed,onMounted,onUnmounted,reactive,ref,watch } from 'vue';import api from '@/api/api'
const tabs=[{id:'hot',label:'今日热榜',hint:'滚动 24 小时'},{id:'fermenting',label:'持续发酵',hint:'近 7 日趋势'},{id:'all',label:'全部',hint:'高赞素材'}];const activeTab=ref('hot'),visibleFerment=ref(6),activeTopicName=ref('');
const selectTab=id=>{const leavingFilteredResults=id!=='all'&&filters.semantic_topic_id;if(leavingFilteredResults){filters.semantic_topic_id='';activeTopicName.value='';load()}if(activeTab.value!==id)activeTab.value=id;if(id==='all'&&!items.value.length)load();window.scrollTo({top:0,behavior:'smooth'})};
const loading=ref(false),boardsLoading=ref(false),items=ref([]),total=ref(0),drawer=ref(false),selected=ref(null);const failed=new Set(),loadedCovers=reactive(new Set());const placeholder='/brand/xhs-placeholder.svg';const coverKey=n=>`${n.note_id}:${n.cover_url||'placeholder'}`;const coverLoaded=n=>loadedCovers.has(coverKey(n));const coverDidLoad=n=>loadedCovers.add(coverKey(n));const filters=reactive({range:'7d',keyword:'',topic:'',semantic_topic_id:'',note_type:'all',sort:'comprehensive',q:'',page:1,page_size:18});let notesController=null,boardsController=null,detailController=null;const cancelled=e=>e?.code==='ERR_CANCELED'||e?.name==='CanceledError';
const load=async(page=1)=>{const targetPage=Number.isInteger(page)?page:1;notesController?.abort();const controller=new AbortController();notesController=controller;loading.value=true;try{const {data}=await api.get('/xhs/notes',{params:{...filters,page:targetPage},signal:controller.signal});if(notesController!==controller)return;items.value=data.items;total.value=data.total;filters.page=targetPage}catch(e){if(!cancelled(e)&&notesController===controller&&!items.value.length){total.value=0}}finally{if(notesController===controller){notesController=null;loading.value=false}}};const reset=()=>{Object.assign(filters,{range:'7d',keyword:'',topic:'',semantic_topic_id:'',note_type:'all',sort:'comprehensive',q:'',page:1});activeTopicName.value='';load()};const openDetail=async n=>{detailController?.abort();const controller=new AbortController();detailController=controller;const hasFullData=Boolean(n&&n.author&&n.content!==undefined);if(hasFullData){selected.value=n;drawer.value=true}try{const latest=(await api.get(`/xhs/notes/${n.note_id}`,{signal:controller.signal})).data;if(detailController===controller){selected.value=latest;if(!hasFullData)drawer.value=true}}catch(e){if(cancelled(e))return;if(!hasFullData){selected.value=n;drawer.value=true}}finally{if(detailController===controller)detailController=null}};const mediaHash=s=>{let h=0;for(let i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))|0;return(h>>>0).toString(36)};const mediaUrl=(u,n,kind)=>u?`/api/v1/xhs/media/${n.note_id}/${kind}?v=${mediaHash(u)}`:placeholder;const imageUrl=n=>mediaUrl(n.cover_url,n,'cover');const avatarUrl=n=>mediaUrl(n.author.avatar_url,n,'avatar');const imageFailed=(event,note,kind)=>{const original=event.target.src;if(original.endsWith('xhs-placeholder.svg'))return;event.target.src=placeholder;const key=`${note.note_id}:${kind}:${original}`;if(failed.has(key))return;failed.add(key);api.post(`/xhs/notes/${note.note_id}/image-failures`,{image_kind:kind,failed_url:kind==='cover'?note.cover_url:note.author.avatar_url},{skipErrorToast:true}).catch(()=>{})};const metric=n=>n===null||n===undefined?'—':compact(n);const compact=n=>n>=10000?`${(n/10000).toFixed(n>=100000?0:1)}万`:String(n||0);const dateTime=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'—';const relative=v=>{if(!v)return '时间未知';const d=Math.floor((Date.now()-new Date(v))/86400000);return d<=0?'今天':`${d} 天前`};const keywordHeat=computed(()=>{const map={};items.value.forEach(n=>n.keywords.forEach(k=>map[k]=(map[k]||0)+1));return Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0,10)});const keywordCount=computed(()=>keywordHeat.value.length);const videoCount=computed(()=>items.value.filter(n=>n.note_type==='video').length);const imageCount=computed(()=>items.value.length-videoCount.value);const cleanTag=t=>(t||'').replace(/\[话题\]/g,'').replace(/^#+|#+$/g,'').trim();const cleanContent=c=>(c||'').replace(/#[^#\[\]\s]{1,40}\[话题\]#/g,'').replace(/[^\S\n]+/g,' ').replace(/ *\n */g,'\n').replace(/\n{3,}/g,'\n\n').trim();const maxLikes=computed(()=>Math.max(0,...items.value.map(n=>n.engagement.likes||0)));const rangeLabel=computed(()=>({'1d':'近 1 天','3d':'近 3 天','7d':'近 7 天'})[filters.range]);const typeLabel=computed(()=>filters.note_type==='video'?'视频':filters.note_type==='image'?'图文':'全部类型');
// 热榜看板：独立于筛选器拉取，失败静默降级为空，不阻塞页面
const boards=ref({generated_at:null,edition_date:null,hot:[],fermenting:[],monitor:null,today_new_notes:0});const loadBoards=async()=>{boardsController?.abort();const controller=new AbortController();boardsController=controller;boardsLoading.value=true;try{const {data}=await api.get('/xhs/topic-boards',{skipErrorToast:true,signal:controller.signal});if(boardsController!==controller)return;boards.value={generated_at:data.generated_at||null,edition_date:data.edition_date||null,hot:data.hot||data.fresh||[],fermenting:data.fermenting||[],monitor:data.monitor||null,today_new_notes:data.today_new_notes||0}}catch(e){if(!cancelled(e)&&boardsController===controller)boards.value={generated_at:null,edition_date:null,hot:[],fermenting:[],monitor:null,today_new_notes:0}}finally{if(boardsController===controller){boardsController=null;boardsLoading.value=false}}};
const topics=computed(()=>boards.value.hot.map(t=>({...t,status:'fresh'})).slice(0,6));const fermentTopics=computed(()=>boards.value.fermenting);const visibleFermentTopics=computed(()=>fermentTopics.value.slice(0,visibleFerment.value));
const sparkGeometry=t=>{let values=(t.trend_points||[]).slice(-7).map(p=>Number(p.score||p.new_notes||0));if(!values.length)values=[0,0];if(values.length===1)values=[values[0],values[0]];const min=Math.min(...values),max=Math.max(...values),points=values.map((v,i)=>({x:2+i*96/(values.length-1),y:72-(v-min)/Math.max(1,max-min)*50}));let line=`M ${points[0].x} ${points[0].y}`;for(let i=1;i<points.length;i++){const prev=points[i-1],point=points[i],mid=(prev.x+point.x)/2;line+=` C ${mid} ${prev.y}, ${mid} ${point.y}, ${point.x} ${point.y}`}const last=points[points.length-1];return{line,area:`${line} L ${last.x} 82 L ${points[0].x} 82 Z`,last}};
const topicEvidence=t=>(t.evidence||[]).slice(0,3).length?(t.evidence||[]).slice(0,3):[`内容样本 ${t.sample_count} 篇`,`涉及 ${t.author_count} 位作者`,`今日监测 ${t.new_notes_24h} 篇`];
// 发酵天数的参考日：所有上榜话题 last_seen_at 的最大值
const referenceTime=computed(()=>Math.max(0,...topics.value.map(t=>+new Date(t.last_seen_at)||0)));
const fermentDays=t=>Math.max(1,Math.round((referenceTime.value-+new Date(t.first_seen_at))/86400000));
const evidence=t=>{if(t.status==='fresh')return `${t.fallback_source==='keyword'?'今日采集再次命中':'今天首次形成热度'} · ${t.sample_count} 篇样本 · 最高 ${compact(t.max_likes)} 赞`;return `${fermentDays(t)} 天前出现 · 今天仍在发酵 · 最高 ${compact(t.max_likes)} 赞`};
// v3 报纸风版面：第 1 名进头条位，02–04 进右侧要闻榜；亮点句优先 ai_highlight，为 null 时回退 evidence 数据句
const headline=computed(()=>topics.value[0]||null);const railTopics=computed(()=>topics.value.slice(1,4));const topNote=computed(()=>headline.value?.notes?.[0]||null);const heroMoreNotes=computed(()=>(headline.value?.notes||[]).slice(1,3));const filtersEl=ref(null);
// 刊头版期：优先用看板实际锚定的采集日（后端 edition_date），无数据时回退当天 →「选题号外 · 07月17日版」
const todayEdition=computed(()=>{if(boards.value.edition_date){const[,m,d]=boards.value.edition_date.split('-');return `${m}月${d}日`}const d=new Date();return `${String(d.getMonth()+1).padStart(2,'0')}月${String(d.getDate()).padStart(2,'0')}日`});
// 监测状态条：由看板数据汇总，接口不可用时全为 0
const monitor=computed(()=>{const all=[...boards.value.hot,...boards.value.fermenting],server=boards.value.monitor||{};return{topicCount:server.topic_count??all.length,sampleCount:server.sample_count??all.reduce((s,t)=>s+(t.sample_count||0),0),freshCount:server.fresh_count??boards.value.hot.length,maxLikes:server.max_likes??Math.max(0,...all.map(t=>t.max_likes||0)),todayNewNotes:server.today_new_notes??boards.value.today_new_notes??0}});
// 卡片只按内容语义话题筛选，采集关键词不参与话题展示或跳转。
const openTopic=t=>{if(t.kind==='single'&&t.notes?.[0])return openDetail({note_id:t.notes[0].note_id});filters.semantic_topic_id=t.topic_id;filters.keyword='';activeTopicName.value=t.topic;activeTab.value='all';load().then(()=>setTimeout(()=>document.querySelector('.body-grid')?.scrollIntoView({behavior:'smooth',block:'start'})))};const clearSemanticFilter=()=>{filters.semantic_topic_id='';activeTopicName.value='';load()};onMounted(loadBoards)
// 弹窗打开时锁定背景滚动：补偿滚动条宽度防止布局晃动，不改 scrollTop（不回顶），Esc 关闭
watch(drawer,v=>{const de=document.documentElement;if(v){const sw=window.innerWidth-de.clientWidth;de.style.paddingRight=sw>0?sw+'px':'';de.style.overflow='hidden'}else{de.style.overflow='';de.style.paddingRight=''}});const onKey=e=>{if(e.key==='Escape')drawer.value=false};
// #app 默认的 overflow-x:hidden 会让 sticky 工作带失效；clip 不会制造额外滚动容器。
const appEl=document.getElementById('app');onMounted(()=>{window.addEventListener('keydown',onKey);if(appEl)appEl.style.overflowX='clip'});onUnmounted(()=>{notesController?.abort();boardsController?.abort();detailController?.abort();window.removeEventListener('keydown',onKey);if(appEl)appEl.style.overflowX='';const de=document.documentElement;de.style.overflow='';de.style.paddingRight=''})
</script>
<style scoped>
.xhs-page{box-sizing:border-box;width:100%;max-width:1440px;min-width:0;margin:-32px auto 0;color:var(--ink);container-type:inline-size}.xhs-page *{box-sizing:border-box}.hero{margin-bottom:20px}.kicker{font-size:12px;letter-spacing:.12em;color:var(--clay-deep);font-weight:700}.hero h1{font-family:"PingFang SC","Helvetica Neue","Microsoft YaHei",Arial,sans-serif;font-size:36px;font-weight:650;letter-spacing:-.035em;line-height:1.2;margin:6px 0}.chips span{background:var(--clay-tint);color:var(--clay-deep);border-radius:99px;padding:5px 9px;font-size:12px}.filters{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr)) 1.6fr auto;gap:9px;padding:14px;margin:12px 0;background:var(--paper);border:1px solid var(--line);border-radius:14px}.reset{border:1px solid var(--line);background:white;border-radius:8px;padding:0 14px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.metrics article,.side-card{padding:16px;background:var(--paper);border:1px solid var(--line);border-radius:14px}.metrics span{color:var(--ink-3);font-size:12px}.metrics strong{display:block;font:700 26px var(--serif);margin-top:4px}.section-title{display:flex;justify-content:space-between;align-items:end;margin:24px 0 10px}.section-title h2{font:700 22px var(--serif);margin:0}.section-title span{color:var(--ink-3);font-size:12px}.body-grid{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:14px}.material-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.material-card{background:var(--paper);border:1px solid var(--line);border-radius:14px;overflow:hidden;transition:.18s;cursor:pointer;display:flex;flex-direction:column}.material-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-card)}.cover{position:relative;aspect-ratio:4/5;background:var(--bone);overflow:hidden}.cover>img{width:100%;height:100%;object-fit:cover}.type{position:absolute;left:9px;top:9px;padding:4px 8px;border-radius:99px;font-size:11px;background:rgba(255,255,255,.9)}.content{padding:13px;display:flex;flex-direction:column;flex:1}.content h3{font:700 15px/1.45 var(--serif);margin:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.chips{display:flex;gap:5px;flex-wrap:wrap;margin:9px 0}.chips span{font-size:10px;padding:3px 7px}.meta{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px;margin-bottom:9px}.meta .chips{flex:1;min-width:0;margin:0}.author{display:flex;align-items:center;gap:6px;flex-shrink:0;max-width:48%;min-width:0;color:var(--ink-3);font-size:11px}.author img{width:22px;height:22px;border-radius:50%;object-fit:cover;flex-shrink:0}.author span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.engagement{display:flex;justify-content:space-between;border-top:1px solid var(--line);margin-top:auto;padding-top:9px;color:var(--ink-3);font-size:12px}.engagement b{color:var(--ink);font-weight:600;font-size:13px;font-variant-numeric:tabular-nums}.side-card{margin-bottom:12px}.side-card h3{font:700 16px var(--serif);margin:0 0 10px}.side-card p{color:var(--ink-3)}.side-card button{display:flex;justify-content:space-between;width:100%;border:0;border-bottom:1px solid var(--line);background:none;padding:9px 0}@media(max-width:1200px){.filters{grid-template-columns:repeat(3,1fr)}.material-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.body-grid{grid-template-columns:1fr}.body-grid aside{grid-row:1}.material-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.filters,.metrics,.material-grid{grid-template-columns:1fr}.hero h1{font-size:30px}}
.materials-pagination{display:flex;justify-content:center;margin:24px 0 8px}
.section-title span.loading{color:var(--clay-deep)}
.material-grid.is-page-loading{opacity:.72;pointer-events:none;transition:opacity .15s ease}
.material-skeleton{overflow:hidden;border:1px solid var(--line);border-radius:14px;background:var(--paper)}
.material-skeleton .skeleton-cover{display:block;width:100%;height:auto;aspect-ratio:4/5}
.skeleton-lines{display:grid;gap:11px;padding:14px}
.cover-loading-mark{position:absolute;inset:0;z-index:1;display:grid;place-content:center;justify-items:center;gap:9px;overflow:hidden;color:var(--ink-4);background:linear-gradient(105deg,var(--bone) 18%,#f7eee5 38%,var(--bone) 58%);background-size:220% 100%;transition:opacity .38s ease,visibility .38s ease;animation:xhs-cover-shimmer 1.45s linear infinite}
.cover-loading-mark i{width:22px;height:22px;border:2px solid rgba(169,79,67,.18);border-top-color:var(--clay-deep);border-radius:50%;animation:xhs-cover-spin .9s linear infinite}
.cover-loading-mark b{font-size:10px;font-weight:600;letter-spacing:.08em}
.cover>img{position:relative;z-index:2;opacity:0;transform:scale(1.025);transition:opacity .45s ease,transform .65s cubic-bezier(.22,.72,.2,1)}
.cover.is-loaded>img{opacity:1;transform:scale(1)}
.cover.is-loaded .cover-loading-mark{visibility:hidden;opacity:0;animation:none}
.cover .type{z-index:3}
@keyframes xhs-cover-shimmer{to{background-position:-220% 0}}
@keyframes xhs-cover-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.cover-loading-mark,.cover-loading-mark i{animation:none}.cover>img{transition:opacity .15s ease;transform:none}}
/* v4 编辑室工作带：完整复刻 brand / rule / tabs / issue 的横向骨架。 */
.hero.masthead {
  position: sticky;
  top: 60px;
  z-index: 50;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 36px;
  height: 76px;
  margin: 0 -32px 39px;
  padding: 0 32px;
  background: var(--paper);
  border-bottom: 3px solid var(--ink);
}
.hero.masthead::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -7px;
  height: 1px;
  background: var(--ink);
}
.masthead-brand { display: flex; align-items: baseline; gap: 14px; flex: none; min-width: 0; }
.hero.masthead .kicker { font-size: 10px; letter-spacing: 0.22em; white-space: nowrap; text-transform: uppercase; }
.hero.masthead h1 {
  margin: 0;
  font-family: "Source Han Serif SC", "Songti SC", "STSong", "Noto Serif SC", Georgia, serif;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.06em;
  white-space: nowrap;
}
.band-rule { width: 1px; height: 28px; background: var(--line); flex: none; }
.masthead-right { flex: none; text-align: right; font-size: 11px; color: var(--ink-3); letter-spacing: 0.08em; line-height: 1.5; }
.masthead-date { display: block; font: 600 13px var(--serif); color: var(--ink); letter-spacing: 0.1em; }
.live-dot { display: flex; align-items: center; justify-content: flex-end; gap: 6px; white-space: nowrap; }
.live-dot i { width: 7px; height: 7px; border-radius: 50%; background: var(--clay); animation: tb-pulse 2.2s ease-out infinite; }
@media (max-width: 768px) {
  /* 窄屏工作带换行：tab 组占整行，右侧状态与日期并成一行 */
  .xhs-page { margin-top: -18px; }
  .hero.masthead { top: 58px; flex-wrap: wrap; gap: 10px 14px; height: auto; min-height: 108px; margin: 0 -14px 25px; padding: 12px 14px; }
  .masthead-right { flex-direction: row; align-items: center; gap: 10px; margin-left: auto; text-align: left; }
  .band-rule { display: none; }
}

/* 监测状态条：话题/样本/新切口/最高赞一览 */
.monitor-strip {
  display: flex; align-items: center; gap: 24px;
  background: var(--paper); border: 1px solid var(--line);
  padding: 11px 22px; margin-bottom: 18px; overflow-x: auto;
}
.monitor-strip .ms-item { display: flex; align-items: baseline; gap: 8px; font-size: 12px; color: var(--ink-3); white-space: nowrap; }
.monitor-strip .ms-item b { font: 700 20px var(--serif); color: var(--ink); }
.monitor-strip .ms-item em { font-style: normal; color: var(--clay-deep); font-weight: 600; }
.monitor-strip .ms-sep { width: 1px; height: 22px; background: var(--line); flex: none; }
.monitor-strip .ms-right { margin-left: auto; font-size: 11px; color: var(--ink-4); letter-spacing: .06em; white-space: nowrap; }
@media (max-width: 900px) {
  .monitor-strip .ms-right { display: none; }
}
.hero .kicker {
  font-size: 10px;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: 0.24em;
  color: var(--clay-deep);
}
.masthead-right .masthead-date {
  flex: none;
  padding-bottom: 0;
  font: 600 13px var(--serif);
  letter-spacing: 0.1em;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.filters > * {
  width: 100%;
  min-width: 0;
}
.filters :deep(.el-input__wrapper),
.filters :deep(.el-select__wrapper) {
  box-sizing: border-box;
  width: 100%;
  min-height: 42px;
  height: 42px;
}
.filters .reset {
  box-sizing: border-box;
  width: 100%;
  height: 42px;
}
@media (min-width: 1201px) {
  .filters {
    grid-template-columns: repeat(6, minmax(0, 1fr)) 82px;
  }
}

/* ============ 今日热榜 v4 · 自然文档流 ============ */
.screen-one {
  display: flex;
  flex-direction: column;
}
.screen-two,
.filters,
.body-grid {
  scroll-margin-top: 152px;
}
@media (max-width: 768px) {
  .screen-two,
  .filters,
  .body-grid {
    scroll-margin-top: 178px;
  }
}
.topic-board {
  --serif: "Source Han Serif SC", "Songti SC", "STSong", "Noto Serif SC", Georgia, serif;
  --sans: "PingFang SC", "Helvetica Neue", "Microsoft YaHei", Arial, sans-serif;
  display: flex;
  flex-direction: column;
  margin-top: 0;
}
@keyframes tb-pulse {
  0% { box-shadow: 0 0 0 0 rgba(204, 120, 92, 0.45); }
  70% { box-shadow: 0 0 0 9px rgba(204, 120, 92, 0); }
  100% { box-shadow: 0 0 0 0 rgba(204, 120, 92, 0); }
}
/* 头版版面：左头条 60% + 右要闻榜 */
.board {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 7.2fr) minmax(0, 4.8fr);
  gap: 18px;
  align-items: stretch;
  margin-top: 16px;
}
.board.solo {
  grid-template-columns: 1fr;
}
.tb-topic {
  position: relative;
  cursor: pointer;
  user-select: none;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease,
    background 0.25s ease, opacity 0.25s ease;
}
.tb-topic:focus-visible {
  outline: 2px solid var(--pine);
  outline-offset: 3px;
}
.topic-board.has-selection .tb-topic:not(.selected) {
  opacity: 0.42;
}
.topic-board.has-selection .tb-topic:not(.selected):hover {
  opacity: 0.92;
}
/* 选中角标（头条与榜单共用） */
.sel-chip {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 5;
  pointer-events: none;
  font-size: 11px;
  letter-spacing: 0.1em;
  font-weight: 600;
  color: var(--ivory);
  background: var(--clay-deep);
  padding: 5px 10px;
  border-radius: 2px;
  opacity: 0;
  transform: translateY(-5px);
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.tb-topic.selected .sel-chip {
  opacity: 1;
  transform: none;
}
/* 排名印章（头条大 / 榜单小） */
.rank {
  flex: none;
  display: grid;
  place-items: center;
  font-family: var(--serif);
  font-weight: 700;
  color: var(--clay-deep);
  border: 2px solid var(--clay-deep);
  transition: background 0.22s ease, color 0.22s ease;
}
.tb-topic.selected .rank {
  background: var(--clay-deep);
  color: var(--ivory);
}
/* 状态徽章：今日新切口 = 黏土实心印章 / 持续发酵 = 松绿虚线描边 */
.badge {
  flex: none;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  padding: 6px 12px;
  line-height: 1;
}
.badge-new {
  background: var(--clay-deep);
  color: var(--ivory);
  box-shadow: 2px 2px 0 var(--clay-soft);
}
/* 单篇高热 = 黏土描边空心章，与聚类话题的实心章区分 */
.badge-single {
  color: var(--clay-deep);
  border: 1.5px solid var(--clay-deep);
  padding: 5px 11px;
}
.badge-ferment {
  color: var(--pine);
  border: 1.5px dashed var(--pine);
  padding: 5px 11px;
}
.badge.sm {
  font-size: 10.5px;
  padding: 4px 9px;
  letter-spacing: 0.1em;
}
.badge-ferment.sm {
  padding: 3px 8px;
}
/* ---------- 头条 HERO ---------- */
.tb-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.02fr) minmax(0, 0.98fr);
  gap: 26px;
  background: var(--paper);
  border: 1px solid var(--line);
  padding: 26px 26px 24px;
}
.tb-hero:hover {
  transform: translateY(-3px);
  border-color: var(--clay-soft);
  box-shadow: 0 16px 38px -14px rgba(122, 74, 50, 0.28);
}
.tb-hero.selected {
  border-color: var(--clay-deep);
  background: linear-gradient(180deg, var(--paper) 0%, var(--clay-tint) 130%);
  box-shadow: 0 0 0 1px var(--clay-deep), 0 18px 42px -14px rgba(168, 90, 64, 0.4);
}
.tb-hero.no-cover {
  grid-template-columns: 1fr;
}
.hero-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.hero-top {
  display: flex;
  align-items: center;
  gap: 14px;
}
.tb-hero .rank {
  width: 54px;
  height: 54px;
  font-size: 26px;
}
.page-tag {
  margin-left: auto;
  font-size: 10.5px;
  letter-spacing: 0.22em;
  color: var(--ink-4);
  white-space: nowrap;
}
.hero-title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: clamp(30px, 3.1vw, 58px);
  line-height: 1.1;
  letter-spacing: 0.02em;
  margin: 18px 0 12px;
  /* 小屏长标题最多 4 行，超出截断，防止头条卡被撑爆 */
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  transition: color 0.25s ease;
}
.tb-hero:hover .hero-title {
  color: var(--clay-deep);
}
.hero-deck {
  margin: 0;
  font-family: var(--serif);
  font-style: italic;
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink-2);
  max-width: 34em;
  /* 导语最多 3 行，避免超长文本压缩右侧要闻栏 */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  row-gap: 6px;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
  font-size: 12.5px;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.hero-meta li {
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.hero-meta li + li::before {
  content: "·";
  margin: 0 8px;
  color: var(--clay);
  font-weight: 700;
}
.hero-meta b {
  color: var(--ink);
  font-weight: 600;
}
.hero-notes {
  margin-top: auto;
  padding-top: 16px;
}
.hero-notes .notes-label {
  font-size: 10.5px;
  letter-spacing: 0.24em;
  color: var(--ink-4);
  border-top: 1px solid var(--line);
  padding-top: 14px;
  margin-bottom: 6px;
}
.note {
  display: flex;
  align-items: baseline;
  gap: 10px;
  width: 100%;
  padding: 7px 6px;
  margin: 0 -6px;
  border: 0;
  border-radius: 3px;
  background: none;
  font-family: var(--serif);
  font-size: 14.5px;
  color: var(--ink-2);
  text-align: left;
  cursor: pointer;
  transition: background 0.2s ease;
}
.note:hover {
  background: var(--ivory);
}
.note .no {
  font-family: var(--sans);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--clay);
  flex: none;
}
.note .t {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.note .leader {
  flex: 1;
  border-bottom: 1px dotted var(--line);
  min-width: 12px;
}
.note .lk {
  font-family: var(--sans);
  font-size: 12px;
  color: var(--ink-4);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.note .lk b {
  color: var(--clay-deep);
  font-size: 13.5px;
  font-weight: 700;
}
/* 头条封面：真实封面图压在品牌渐变底上，加载失败回退现有 placeholder */
.hero-cover {
  position: relative;
  overflow: hidden;
  margin: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 360px;
  padding: 18px;
  color: var(--ivory);
  background:
    radial-gradient(130% 90% at 82% 6%, rgba(233, 183, 158, 0.9) 0%, rgba(233, 183, 158, 0) 52%),
    radial-gradient(120% 120% at 8% 100%, rgba(63, 92, 82, 0.38) 0%, rgba(63, 92, 82, 0) 55%),
    linear-gradient(158deg, #cc785c 0%, #a85a40 56%, #7c4530 100%);
}
.hero-cover > img {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero-cover::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: linear-gradient(
    180deg,
    rgba(31, 31, 30, 0.18) 0%,
    rgba(31, 31, 30, 0) 34%,
    rgba(31, 31, 30, 0) 52%,
    rgba(31, 31, 30, 0.62) 100%
  );
}
.cover-wm {
  position: absolute;
  right: 2px;
  top: 30%;
  z-index: 0;
  font-family: var(--serif);
  font-weight: 700;
  font-size: 180px;
  line-height: 1;
  color: rgba(250, 249, 245, 0.13);
  user-select: none;
  pointer-events: none;
}
.cover-tag {
  position: relative;
  z-index: 3;
  align-self: flex-start;
  font-size: 10px;
  letter-spacing: 0.2em;
  border: 1px solid rgba(250, 249, 245, 0.55);
  color: var(--ivory);
  background: rgba(31, 31, 30, 0.25);
  padding: 5px 9px;
}
.hero-cover figcaption {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
}
.cover-title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: clamp(19px, 1.55vw, 23px);
  line-height: 1.5;
  text-shadow: 0 1px 10px rgba(90, 40, 20, 0.35);
}
.like-chip {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(31, 31, 30, 0.38);
  color: var(--ivory);
  font-size: 12.5px;
  padding: 5px 11px;
  border-radius: 2px;
  font-variant-numeric: tabular-nums;
}
.like-chip i {
  font-style: normal;
  color: var(--clay-soft);
}
/* ---------- 侧边榜单 RAIL ---------- */
.rail {
  display: flex;
  flex-direction: column;
  background: var(--paper);
  border: 1px solid var(--line);
}
.rail-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 13px 18px 11px;
  border-bottom: 3px solid var(--ink);
}
.rail-head b {
  font-family: var(--serif);
  font-size: 15px;
  letter-spacing: 0.08em;
  color: var(--ink);
}
.rail-head span {
  font-size: 10px;
  letter-spacing: 0.22em;
  color: var(--ink-4);
}
.rail-item {
  /* flex 基准用 auto 而非 0：自然流里网格按内容撑高，各卡等量分配剩余空间，
     空隙统一留在 meta 与钉底笔记之间（与素材卡同理），不再出现卡底大留白 */
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  padding: 15px 18px 13px;
  background: transparent;
  /* 内容多时裁剪在本卡内，绝不溢出到相邻卡 */
  overflow: hidden;
}
.rail-item + .rail-item {
  border-top: 1px solid var(--line);
}
.rail-item:hover {
  background: var(--ivory);
}
.rail-item.selected {
  background: var(--clay-tint);
  box-shadow: inset 3px 0 0 var(--clay-deep);
}
.rail-item.selected::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  border: 1px solid var(--clay-deep);
}
.ri-top {
  display: flex;
  align-items: center;
  gap: 11px;
}
.rail-item .rank {
  width: 33px;
  height: 33px;
  font-size: 15px;
  border-width: 1.5px;
}
.ri-name {
  margin: 0;
  font-family: var(--serif);
  font-weight: 700;
  font-size: 20px;
  letter-spacing: 0.02em;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.22s ease;
}
.rail-item:hover .ri-name {
  color: var(--clay-deep);
}
.ri-top .badge {
  margin-left: auto;
}
.ri-deck {
  margin: 9px 0 0;
  font-family: var(--serif);
  font-style: italic;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--ink-2);
}
.ri-meta {
  margin: 9px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.ri-deck + .ri-meta {
  margin-top: 6px;
}
.ri-notes {
  margin: auto 0 0;
  padding: 8px 0 0;
  list-style: none;
  border-top: 1px dashed var(--line);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.ri-notes li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 2px 4px;
  margin: 0 -4px;
  border-radius: 3px;
  font-family: var(--serif);
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
}
.ri-notes li:hover {
  background: var(--ivory);
}
.ri-notes li:hover .t {
  color: var(--clay-deep);
}
.ri-notes .t {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ri-notes .l {
  margin-left: auto;
  flex: none;
  font-family: var(--sans);
  font-size: 11.5px;
  font-weight: 600;
  color: var(--clay-deep);
  font-variant-numeric: tabular-nums;
}
.ri-notes .l em {
  font-style: normal;
  font-weight: 400;
  color: var(--ink-4);
  margin-left: 2px;
}
/* 响应式：≤1024px 榜单收头条下方，≤800px 头条自身收单列 */
@media (max-width: 1024px) {
  .board {
    grid-template-columns: 1fr;
  }
  .hero-cover {
    min-height: 320px;
  }
}
@media (max-width: 800px) {
  .tb-hero {
    grid-template-columns: 1fr;
    padding: 20px;
  }
  .hero-cover {
    min-height: 240px;
  }
  .cover-wm {
    font-size: 130px;
  }
}

/* 素材卡互动数据条：四格均分，数字放大；margin-top:auto 钉在卡片底部 */
.engagement {
  display: flex;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.engagement .stat {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}
.engagement .stat b {
  color: var(--ink);
  font-size: 19px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.engagement .stat span {
  color: var(--ink-3);
  font-size: 11px;
}

/* 详情弹窗：仿小红书网页端，居中平滑弹出；背景锁滚动但不回顶 */
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(31, 31, 30, 0.45);
  backdrop-filter: blur(3px);
}
.modal-card {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(300px, 2fr);
  width: min(920px, 100%);
  height: min(660px, 88vh);
  background: var(--paper);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(31, 31, 30, 0.28);
}
.modal-close {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
  color: var(--ink-2);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.modal-media {
  position: relative;
  min-width: 0;
  background: #17110e;
  overflow: hidden;
}
/* 模糊底图铺满：任意封面比例都不露黑边 */
.modal-media .bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: blur(26px) brightness(0.55);
  transform: scale(1.25);
}
.modal-media .fg {
  position: relative;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.modal-side {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.modal-author {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 44px 14px 16px;
  border-bottom: 1px solid var(--line);
}
.modal-author img {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--bone);
}
.modal-author .name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.modal-author a {
  flex-shrink: 0;
  padding: 5px 12px;
  border: 1px solid var(--clay);
  border-radius: 99px;
  color: var(--clay-deep);
  font-size: 12px;
  text-decoration: none;
}
/* 右栏三段式：标题固定、正文滚动、tag+时间固定底部 */
.modal-title {
  margin: 0;
  padding: 16px 16px 10px;
  font: 700 18px/1.4 var(--serif);
}
.modal-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin: 0;
  padding: 0 16px 16px;
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
}
.modal-tail {
  padding: 12px 16px 14px;
  border-top: 1px solid var(--line);
}
.modal-time {
  margin-top: 10px;
  color: var(--ink-4);
  font-size: 12px;
}
.modal-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  color: var(--ink-3);
  font-size: 14px;
}
.modal-foot span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
/* 简笔线条图标：心=赞 星=藏 气泡=评 分享=享 */
.modal-foot .ic {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.modal-foot b {
  color: var(--ink);
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* 平滑弹出/收起动画 */
.xhs-modal-enter-active,
.xhs-modal-leave-active {
  transition: opacity 0.22s ease;
}
.xhs-modal-enter-from,
.xhs-modal-leave-to {
  opacity: 0;
}
.xhs-modal-enter-active .modal-card {
  transition: transform 0.24s cubic-bezier(0.2, 0.9, 0.3, 1.15), opacity 0.22s ease;
}
.xhs-modal-leave-active .modal-card {
  transition: transform 0.18s ease-in, opacity 0.18s ease;
}
.xhs-modal-enter-from .modal-card,
.xhs-modal-leave-to .modal-card {
  opacity: 0;
  transform: translateY(14px) scale(0.97);
}
@media (max-width: 800px) {
  .modal-card {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 42%) 1fr;
    height: 92vh;
  }
}
/* 视图切换：骨底槽 + 陶土 pill 分段控件（hint 内联单行），嵌在工作带正中 */
.topic-tabs{display:flex;gap:4px;padding:4px;background:var(--bone);border:1px solid var(--line);border-radius:999px;margin:0 auto}
.topic-tabs button{border:0;border-radius:999px;padding:7px 18px;background:transparent;color:var(--ink-3);font:400 13px/1.4 var(--sans);letter-spacing:.02em;cursor:pointer;transition:all .18s;white-space:nowrap;outline:none}
.topic-tabs button small{font-size:10px;opacity:.62;margin-left:5px;letter-spacing:.04em}
.topic-tabs button:hover{color:var(--ink)}
.topic-tabs button.active{background:var(--clay);color:#fff;font-weight:600;box-shadow:0 2px 8px rgba(204,120,92,.3)}
.topic-tabs button.active small{opacity:.85;color:#fff}
.topic-tabs button:focus-visible{box-shadow:0 0 0 2px var(--clay-soft)}
/* ============ 持续发酵（报纸趋势版排版：合并边框信号卡） ============ */
.semantic-filter{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--clay-tint);border:1px solid var(--clay-soft);border-radius:10px;color:var(--clay-deep)}.semantic-filter button{border:0;background:transparent;color:inherit;font-weight:700;cursor:pointer}
.signals-section{padding:4px 0 50px}
.page-marker{display:flex;align-items:baseline;gap:16px;margin:8px 0 26px}
.page-marker .pm-no{font:900 15px var(--serif);letter-spacing:.08em}
.page-marker .pm-name{font:400 15px var(--serif);letter-spacing:.28em;color:var(--ink)}
.page-marker .pm-note{font-size:11px;color:var(--ink-3);letter-spacing:.14em}
.page-marker::after{content:"";flex:1;height:1px;background:var(--line);align-self:center}
.signal-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%;max-width:100%;min-width:0;gap:0;margin-top:22px}
.signal-card{min-width:0;max-width:100%;overflow:hidden;background:var(--paper);border:1px solid var(--line);padding:28px 30px 24px;margin:-1px 0 0 -1px;display:flex;flex-direction:column;cursor:pointer;transition:background .2s}
.signal-card:hover,.signal-card:focus-visible{background:var(--ivory);outline:none}
.sc-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.sc-signal{font-size:11px;letter-spacing:.3em;color:var(--ink-3)}
.sc-signal b{font:700 15px var(--serif);color:var(--ink);letter-spacing:.06em;margin-right:8px}
.sc-day{font-size:10.5px;letter-spacing:.18em;padding:3px 10px 2px;border:1px solid var(--clay-deep);color:var(--clay-deep);font-weight:600;line-height:1.5}
.sc-topic{margin:0 0 10px;font-family:"Source Han Serif SC","Songti SC","STSong","Noto Serif SC",Georgia,serif;font-size:clamp(36px,2.6vw,42px);font-weight:700;line-height:1.22;letter-spacing:-.015em;color:var(--ink);-webkit-text-stroke:.35px currentColor;font-synthesis:weight}
.sc-sub{margin:0 0 16px;font:500 13px/1.7 var(--serif);color:var(--ink-3)}
.sc-numbers{display:flex;min-width:0;align-items:baseline;gap:12px;border-top:1px solid var(--ink);padding-top:14px;margin-bottom:6px}
.sc-big{font:700 46px/1 var(--serif);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.sc-big small{font-size:15px;font-weight:400;color:var(--ink-3);margin-left:4px}
.sc-numtext{min-width:0;font-size:12.5px;color:var(--ink-3);line-height:1.6;overflow-wrap:anywhere}
.sc-numtext b{color:var(--clay-deep);font-weight:600}
.sc-chart{margin:14px 0 18px;padding:12px 14px 8px;background:linear-gradient(180deg,var(--ivory),rgba(248,245,239,.36));border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.sc-chart-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;font-size:10px;line-height:1.4;letter-spacing:.18em;color:var(--ink-4)}
.sc-chart-head b{font-weight:600;color:var(--clay-deep)}
.sc-chart-plot{position:relative;height:92px;overflow:hidden}
.sc-chart svg{display:block;width:100%;height:100%;overflow:hidden}
.grid-line{stroke:var(--line);stroke-width:.7;stroke-dasharray:1.5 2.5;vector-effect:non-scaling-stroke}
.spark-area{stroke:none}
.spark-line{fill:none;stroke:var(--clay);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.spark-end{position:absolute;width:10px;height:10px;border:3px solid var(--clay-deep);border-radius:50%;background:var(--paper);box-shadow:0 0 0 3px rgba(204,120,92,.14);transform:translate(-50%,-50%);pointer-events:none}
.sc-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.chip{font-size:11px;color:var(--ink-3);letter-spacing:.05em;border:1px solid var(--line);padding:3px 10px;line-height:1.5;background:none}
.sc-notes{border-top:1px solid var(--line);margin-bottom:6px}
.note-item{display:flex;align-items:baseline;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);cursor:pointer}
.note-item:last-child{border-bottom:none}
.note-item .ni-title{flex:1;min-width:0;font-size:13.5px;line-height:1.55;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.note-item:hover .ni-title{color:var(--clay-deep)}
.ni-like{font:400 13px var(--serif);color:var(--ink-3);white-space:nowrap}
.ni-like b{color:var(--clay-deep);font-weight:700}
.sc-foot{margin-top:auto;padding-top:14px;display:flex;flex-wrap:wrap;gap:8px 16px;justify-content:space-between;align-items:center;font-size:12px;color:var(--ink-3);letter-spacing:.06em}
.sc-foot b{font:700 14px var(--serif);color:var(--clay-deep)}
.sc-foot a{color:var(--ink);cursor:pointer;font:400 12.5px var(--serif);letter-spacing:.1em;border-bottom:1px solid var(--clay);padding-bottom:1px}
.sc-foot a:hover{color:var(--clay-deep)}
.signal-skeleton{min-height:360px;padding:24px;background:var(--paper);border:1px solid var(--line)}
.more-ferment{display:block;margin:26px auto 0;padding:10px 28px;background:transparent;border:1px solid var(--ink);color:var(--ink);font:600 13px var(--serif);letter-spacing:.1em;cursor:pointer;transition:.2s}
.more-ferment:hover{background:var(--ink);color:var(--ivory)}
@container (max-width:1100px){.signal-grid{grid-template-columns:minmax(0,1fr)}.topic-tabs button small{display:none}.hero.masthead{gap:18px}.topic-tabs button{padding-inline:14px}}
@container (max-width:860px){.masthead-right{display:none}.masthead-brand{gap:8px}.hero.masthead h1{font-size:22px}.band-rule{display:none}}
@container (max-width:520px){.sc-topic{font-size:30px;letter-spacing:-.015em}}
@media(max-width:800px){.topic-tabs{order:3;width:100%}.topic-tabs button{flex:1;padding:7px 4px;font-size:13px}.signal-grid{grid-template-columns:minmax(0,1fr)}.page-marker{flex-wrap:wrap;gap:8px 14px}}
</style>
