<template>
  <RewriteTool :config="config" />
</template>

<script setup>
import RewriteTool from '@/components/shared/RewriteTool.vue'

const config = {
  title: '内容仿写',
  desc: '输入任意文字内容，AI 帮你换一种风格重新表达',
  from: { label: '原始内容', dot: '原', color: '#9A968D' },
  to: { label: '仿写内容', dot: '新', color: '#CC785C' },
  inputLabel: '原始内容',
  cta: '开始仿写',
  loadingText: '正在仿写…',
  modes: [{ key: 'text', label: '文字内容' }],
  linkPlaceholder: '',
  textPlaceholder: '粘贴或输入要仿写的文字内容……',
  apiEndpoint: '/ai/rewrite',
  mockResult: {
    title: '当"风口"成为集体幻觉：写给清醒者的一封信',
    body: '开头不该是结论，而该是一道裂缝。\n\n去年这个时候，几乎所有人都在谈论同一个词。但很少有人停下来问一句：我们究竟是在追逐趋势，还是在逃避焦虑？\n\n潮水还会再来。但清醒的人，从不在浪尖上做决定。',
  },
}
</script>
