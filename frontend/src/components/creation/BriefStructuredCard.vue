<template>
  <div class="bsc" v-if="brief">
    <div class="bsc-head">
      <span class="bsc-title">
        <el-icon color="#16a34a"><CircleCheck /></el-icon> 已解析商单 brief
      </span>
      <slot name="actions" />
    </div>

    <!-- 核心主张 -->
    <div v-if="brief.core_message" class="bsc-hero">
      <span class="bsc-hero-label">核心主张</span>
      <span class="bsc-hero-text">{{ brief.core_message }}</span>
    </div>

    <!-- 必须覆盖 -->
    <div v-if="brief.must_cover && brief.must_cover.length" class="bsc-section">
      <div class="bsc-sec-h">
        <span class="dot cover"></span>必须覆盖<span class="cnt">{{ brief.must_cover.length }}</span>
      </div>
      <div class="bsc-rows">
        <div class="bsc-row" v-for="(x, i) in brief.must_cover" :key="i">
          <span class="num cover">{{ i + 1 }}</span><span class="txt">{{ x }}</span>
        </div>
      </div>
    </div>

    <!-- 禁忌 / 红线 -->
    <div v-if="brief.banned && brief.banned.length" class="bsc-section">
      <div class="bsc-sec-h">
        <span class="dot ban"></span>禁忌 / 红线<span class="cnt">{{ brief.banned.length }}</span>
      </div>
      <div class="bsc-rows">
        <div class="bsc-row" v-for="(x, i) in brief.banned" :key="i">
          <span class="num ban">{{ i + 1 }}</span><span class="txt ban">{{ x }}</span>
        </div>
      </div>
    </div>

    <!-- meta 字段 -->
    <div class="bsc-meta" v-if="hasMeta">
      <div v-if="brief.tone" class="bsc-meta-row"><span class="k">调性</span><span class="v">{{ brief.tone }}</span></div>
      <div v-if="brief.audience" class="bsc-meta-row"><span class="k">目标读者</span><span class="v">{{ brief.audience }}</span></div>
      <div v-if="brief.publish" class="bsc-meta-row"><span class="k">发布档期</span><span class="v">{{ brief.publish }}</span></div>
      <div v-if="brief.cta" class="bsc-meta-row"><span class="k">引导动作</span><span class="v">{{ brief.cta }}</span></div>
      <div v-if="brief.review_notes" class="bsc-meta-row"><span class="k">审核要求</span><span class="v">{{ brief.review_notes }}</span></div>
      <div v-if="brief.notes" class="bsc-meta-row"><span class="k">其他</span><span class="v">{{ brief.notes }}</span></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { CircleCheck } from '@element-plus/icons-vue'

const props = defineProps({ brief: { type: Object, default: null } })
const hasMeta = computed(() => {
  const b = props.brief || {}
  return !!(b.tone || b.audience || b.publish || b.cta || b.review_notes || b.notes)
})
</script>

<style scoped>
.bsc {
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--paper);
  overflow: hidden;
}
.bsc-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--line);
  background: rgba(204,120,92,.04);
}
.bsc-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--ink); }

/* 核心主张 */
.bsc-hero {
  margin: 14px 16px;
  padding: 12px 14px;
  background: var(--clay-tint);
  border-radius: 10px;
  display: flex; flex-direction: column; gap: 4px;
}
.bsc-hero-label { font-size: 11px; color: var(--clay-deep); letter-spacing: .05em; font-weight: 600; }
.bsc-hero-text { font-size: 15px; color: var(--ink); font-weight: 600; line-height: 1.5; }

/* 分区 */
.bsc-section { padding: 4px 16px 8px; }
.bsc-sec-h {
  display: flex; align-items: center; gap: 7px;
  font-size: 13px; font-weight: 600; color: var(--ink-2);
  margin: 8px 0 10px;
}
.bsc-sec-h .dot { width: 8px; height: 8px; border-radius: 50%; }
.bsc-sec-h .dot.cover { background: #16a34a; }
.bsc-sec-h .dot.ban { background: #dc2626; }
.bsc-sec-h .cnt {
  font-weight: 500; font-size: 12px; color: var(--ink-4);
  background: var(--paper); border: 1px solid var(--line);
  border-radius: 10px; padding: 0 8px; line-height: 18px;
}

/* 序号行 */
.bsc-rows { display: flex; flex-direction: column; }
.bsc-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 7px 0;
}
.bsc-row + .bsc-row { border-top: 1px solid rgba(228,221,206,.5); }
.num {
  flex-shrink: 0; width: 20px; height: 20px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; margin-top: 1px;
}
.num.cover { background: rgba(22,163,74,.12); color: #15803d; }
.num.ban { background: rgba(220,38,38,.1); color: #b91c1c; }
.txt { font-size: 13px; color: var(--ink-2); line-height: 1.55; }
.txt.ban { color: #b54134; }

/* meta */
.bsc-meta { padding: 8px 16px 16px; margin-top: 4px; border-top: 1px dashed var(--line); }
.bsc-meta-row { display: flex; gap: 12px; font-size: 13px; line-height: 1.6; padding: 4px 0; }
.bsc-meta-row .k { flex-shrink: 0; color: var(--ink-4); width: 64px; }
.bsc-meta-row .v { color: var(--ink-2); }
</style>
