<template>
  <div class="legal-page">
    <div class="legal-card">
      <h1>{{ title }}</h1>
      <p class="legal-updated">最后更新：{{ updated }}</p>
      <!-- ponytail: 占位正文，待替换为正式法律文本 -->
      <div class="legal-body">
        <p>本文档正文待补充。以下为占位内容。</p>
        <h2>一、总则</h2>
        <p>欢迎使用本服务。在使用本服务前，请您仔细阅读本{{ short }}。您一旦开始使用本服务，即视为您已阅读并同意接受本{{ short }}的全部内容。</p>
        <h2>二、服务说明</h2>
        <p>本服务为面向公众号创作者的 AI 内容辅助工具，具体功能以平台实际提供为准。</p>
        <h2>三、其他</h2>
        <p>本{{ short }}的最终解释权归本平台所有。如有疑问，请通过平台公示的联系方式与我们联系。</p>
      </div>
      <button class="legal-back" @click="goBack">← 返回</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const title = computed(() => route.meta.title || '')
const short = computed(() => (route.name === 'Privacy' ? '隐私政策' : '用户协议'))
const updated = '2026-06-17'

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/landing')
}
</script>

<style scoped>
.legal-page {
  min-height: 100vh;
  background: var(--ivory);
  display: flex;
  justify-content: center;
  padding: 56px 20px 80px;
}
.legal-card {
  max-width: 720px;
  width: 100%;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg, 16px);
  padding: 40px 44px;
}
.legal-card h1 {
  font-family: var(--serif);
  font-size: 26px;
  color: var(--ink);
  margin: 0;
}
.legal-updated {
  color: var(--ink-4);
  font-size: 13px;
  margin: 8px 0 28px;
}
.legal-body h2 {
  font-size: 16px;
  color: var(--ink);
  margin: 26px 0 8px;
}
.legal-body p {
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.8;
  margin: 0 0 4px;
}
.legal-back {
  margin-top: 36px;
  padding: 9px 18px;
  border: 1px solid var(--line);
  background: transparent;
  border-radius: var(--r-pill, 999px);
  color: var(--ink-2);
  font-family: inherit;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.14s;
}
.legal-back:hover {
  background: var(--bone);
  color: var(--ink);
}
</style>
