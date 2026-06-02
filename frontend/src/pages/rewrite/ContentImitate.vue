<template>
  <div style="max-width: 860px; margin: 0 auto;">
    <div class="tool-hero">
      <div class="kicker">
        <el-icon :size="14"><Edit /></el-icon>
        内容仿写 · 仿写
      </div>
      <h1 class="font-serif text-ink" style="font-size: 38px; line-height: 1.15; letter-spacing: -.01em;">
        读懂它的<span class="text-clay">门道</span>，写出你的版本
      </h1>
      <p class="text-body text-ink-3" style="margin-top: 12px; max-width: 600px;">
        给一篇参考内容 —— 链接或文字，AI 会学习它的结构与语感，为你重新创作一篇原创内容。
      </p>
    </div>

    <!-- 参考内容 -->
    <div class="card soft-panel" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">
            <el-icon :size="17"><Document /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">参考内容</div>
            <div class="text-xs text-ink-4">提供一篇想模仿其风格的内容</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div class="seg" style="margin-bottom: 16px;">
          <button @click="mode = 'link'" :class="['seg-btn', { 'seg-btn-active': mode === 'link' }]">参考链接</button>
          <button @click="mode = 'text'" :class="['seg-btn', { 'seg-btn-active': mode === 'text' }]">参考文字</button>
        </div>
        <el-input v-if="mode === 'link'" v-model="value"
          placeholder="粘贴想仿写的文章链接（公众号 / 小红书 / 知乎 等）" />
        <el-input v-else v-model="value" type="textarea" :rows="7"
          placeholder="粘贴想仿写的参考文字内容……" />
      </div>
    </div>

    <!-- 额外要求 -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 16px;">
      <div class="panel-head">
        <div style="display: flex; align-items: center; gap: 11px;">
          <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div>
            <div class="text-sm font-semibold text-ink">额外要求 <span class="text-xs text-ink-4" style="font-weight: 400;">选填</span></div>
            <div class="text-xs text-ink-4">补充仿写时的额外要求</div>
          </div>
        </div>
      </div>
      <div style="padding: 22px;">
        <div style="display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px;">
          <button v-for="chip in rewriteChips" :key="chip" @click="toggleChip(chip)"
            :class="['type-chip', { 'type-chip-active': preference.includes(chip) }]">
            {{ chip }}
          </button>
        </div>
        <el-input v-model="preference" type="textarea" :rows="3"
          placeholder="例如：换一个主题但保持同样的叙事节奏，语气更亲切一些……" />
      </div>
    </div>

    <button class="cta-bar" :disabled="!canGenerate || generating" @click="handleGenerate">
      <template v-if="generating">
        <el-icon class="spin"><Loading /></el-icon> 正在仿写…
      </template>
      <template v-else>开始仿写</template>
    </button>

    <div v-if="generating" style="margin-top: 24px;" class="fade-in">
      <div style="text-align: center; padding: 56px 0;">
        <el-icon :size="30" class="spin text-clay" style="margin: 0 auto;"><Loading /></el-icon>
        <p class="text-sm text-ink-3" style="margin-top: 14px;">正在学习风格并仿写…</p>
      </div>
    </div>

    <div v-if="result && !generating" class="fade-in" style="margin-top: 32px;">
      <RewriteResult :result="result" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Document, Edit, Loading } from '@element-plus/icons-vue'
import RewriteResult from './RewriteResult.vue'

const rewriteChips = ['更口语', '更精简', '更有网感', '加 emoji', '去 AI 味', '保留原意']

const mode = ref('link')
const value = ref('')
const preference = ref('')
const generating = ref(false)
const result = ref(null)

const canGenerate = computed(() => mode.value === 'link' ? /\w|[一-龥]/.test(value.value) : value.value.trim().length > 6)

const toggleChip = (chip) => {
  if (preference.value.includes(chip)) {
    preference.value = preference.value.replace(new RegExp(chip + '[、，,]?'), '').trim()
  } else {
    preference.value = preference.value ? preference.value.replace(/[、，,]?\s*$/, '') + '、' + chip : chip
  }
}

const handleGenerate = async () => {
  generating.value = true
  result.value = null
  // TODO: 调用后端 API
  await new Promise(r => setTimeout(r, 1600))
  result.value = {
    title: '当"风口"成为集体幻觉：写给清醒者的一封信',
    body: `开头不该是结论，而该是一道裂缝。\n\n去年这个时候，几乎所有人都在谈论同一个词。但很少有人停下来问一句：我们究竟是在追逐趋势，还是在逃避焦虑？\n\n一组被反复引用、却很少被读完的数据显示，真正完成转化的，不到声量的十分之一。\n\n这并不是要否定变化本身。真正值得警惕的，是"被制造出来的需求"——它借趋势之名，行贩卖之实。\n\n潮水还会再来。但清醒的人，从不在浪尖上做决定。`,
  }
  generating.value = false
}
</script>

<style scoped>
.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }
.soft-panel { background: radial-gradient(120% 80% at 100% 0%, rgba(204,120,92,.06) 0%, transparent 55%), var(--paper); }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.cta-bar { width: 100%; display: flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-in { animation: fadeIn .28s cubic-bezier(.32,.72,0,1); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
