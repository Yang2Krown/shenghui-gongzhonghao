<template>
  <div class="legal-page">
    <div class="legal-card">
      <h1>{{ doc.title }}</h1>
      <p class="legal-updated">最后更新：{{ updated }}</p>

      <div class="legal-body">
        <p class="legal-intro">{{ doc.intro }}</p>

        <template v-for="(section, i) in doc.sections" :key="i">
          <h2>{{ section.heading }}</h2>
          <p v-for="(para, j) in section.paragraphs" :key="j">{{ para }}</p>
        </template>
      </div>

      <button class="legal-back" @click="goBack">← 返回</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TERMS_DOC, PRIVACY_DOC, LEGAL_UPDATED } from './legalContent'

const route = useRoute()
const router = useRouter()

const doc = computed(() => (route.name === 'Privacy' ? PRIVACY_DOC : TERMS_DOC))
const updated = LEGAL_UPDATED

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
  padding: 44px 48px;
}
.legal-card h1 {
  font-family: var(--serif);
  font-size: 28px;
  color: var(--ink);
  margin: 0;
}
.legal-updated {
  color: var(--ink-4);
  font-size: 13px;
  margin: 8px 0 28px;
}
.legal-intro {
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.9;
  margin: 0 0 8px;
  padding: 16px 18px;
  background: var(--ivory);
  border-radius: var(--r-md, 10px);
  border-left: 3px solid var(--clay-soft, #E9B79E);
}
.legal-body h2 {
  font-family: var(--serif);
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin: 30px 0 10px;
}
.legal-body p {
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.85;
  margin: 0 0 8px;
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
