<template>
  <RewriteTool :config="config" />
</template>

<script setup>
import RewriteTool from '@/components/shared/RewriteTool.vue'

const config = {
  title: '小红书转公众号',
  desc: '把小红书笔记链接扩写为公众号长文风格',
  from: { label: '小红书', dot: '书', color: '#FF2442' },
  to: { label: '公众号', dot: '公', color: '#07C160' },
  inputLabel: '小红书笔记链接',
  cta: '转换为公众号',
  loadingText: '正在扩写为公众号长文…',
  modes: [{ key: 'link', label: '笔记链接' }],
  linkPlaceholder: '粘贴小红书笔记链接',
  textPlaceholder: '',
  apiEndpoint: '/ai/rewrite',
  mockResult: {
    title: '当"风口"成为集体幻觉：写给清醒者的一封信',
    body: '开头不该是结论，而该是一道裂缝。\n\n去年这个时候，几乎所有人都在谈论同一个词。但很少有人停下来问一句：我们究竟是在追逐趋势，还是在逃避焦虑？\n\n潮水还会再来。但清醒的人，从不在浪尖上做决定。',
  },
}
</script>
