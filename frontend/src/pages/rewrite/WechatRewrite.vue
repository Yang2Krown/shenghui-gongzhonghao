<template>
  <RewriteTool :config="config" />
</template>

<script setup>
import RewriteTool from '@/components/shared/RewriteTool.vue'

const config = {
  title: '公众号仿写',
  desc: '给定一篇公众号文章链接，仿照其风格与结构重新创作',
  from: { label: '参考文章', dot: '公', color: '#07C160' },
  to: { label: '原创仿写', dot: '新', color: '#CC785C' },
  inputLabel: '参考文章链接',
  cta: '开始仿写',
  loadingText: '正在分析风格并仿写…',
  modes: [{ key: 'link', label: '文章链接' }],
  linkPlaceholder: '粘贴要仿写的公众号文章链接',
  textPlaceholder: '',
  apiEndpoint: '/ai/rewrite',
  mockResult: {
    title: '当"风口"成为集体幻觉：写给清醒者的一封信',
    body: '开头不该是结论，而该是一道裂缝。\n\n去年这个时候，几乎所有人都在谈论同一个词。但很少有人停下来问一句：我们究竟是在追逐趋势，还是在逃避焦虑？\n\n一组被反复引用、却很少被读完的数据显示，真正完成转化的，不到声量的十分之一。\n\n这并不是要否定变化本身。真正值得警惕的，是"被制造出来的需求"——它借趋势之名，行贩卖之实。\n\n潮水还会再来。但清醒的人，从不在浪尖上做决定。',
  },
}
</script>
