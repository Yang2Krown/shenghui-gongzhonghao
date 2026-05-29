<template>
  <RewriteTool :config="config" />
</template>

<script setup>
import RewriteTool from '@/components/shared/RewriteTool.vue'

const config = {
  title: '抖音转公众号',
  desc: '把抖音视频/文案链接转换为公众号图文长文',
  from: { label: '抖音', dot: '抖', color: '#000000' },
  to: { label: '公众号', dot: '公', color: '#07C160' },
  inputLabel: '抖音视频链接',
  cta: '转换为公众号',
  loadingText: '正在转写并扩写为长文…',
  modes: [{ key: 'link', label: '视频链接' }],
  linkPlaceholder: '粘贴抖音视频分享链接',
  textPlaceholder: '',
  apiEndpoint: '/ai/rewrite',
  mockResult: {
    title: '当"风口"成为集体幻觉：写给清醒者的一封信',
    body: '开头不该是结论，而该是一道裂缝。\n\n去年这个时候，几乎所有人都在谈论同一个词。但很少有人停下来问一句：我们究竟是在追逐趋势，还是在逃避焦虑？\n\n潮水还会再来。但清醒的人，从不在浪尖上做决定。',
  },
}
</script>
