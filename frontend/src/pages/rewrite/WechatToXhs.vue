<template>
  <RewriteTool :config="config" />
</template>

<script setup>
import RewriteTool from '@/components/shared/RewriteTool.vue'

const config = {
  title: '公众号转小红书',
  desc: '把公众号长文转换为小红书风格的标题、正文与话题标签',
  from: { label: '公众号', dot: '公', color: '#07C160' },
  to: { label: '小红书', dot: '书', color: '#FF2442' },
  inputLabel: '公众号文章',
  cta: '转换为小红书',
  loadingText: '正在转换为小红书风格…',
  modes: [
    { key: 'link', label: '文章链接' },
    { key: 'text', label: '粘贴内容' },
  ],
  linkPlaceholder: '粘贴 mp.weixin.qq.com 文章链接',
  textPlaceholder: '粘贴公众号文章正文……',
  apiEndpoint: '/wechat-to-xhs/convert',
  mockResult: {
    title: '别再被风口绑架了😮‍💨这4个动作我真的劝你立刻做',
    body: '姐妹们，最近是不是也被各种"风口""趋势"刷到焦虑了🥹\n\n我蹲了一年多，跟你们说点大实话👇\n\n1️⃣ 信息源砍一半\n只留能给你"事实"的，删掉只会贩卖情绪的账号\n\n2️⃣ 目标拆到周\n别张口就是年度规划，先把这周能做的做完\n\n3️⃣ 问自己一句\n抛开所有声音，这件事对我到底意味着什么❓\n\n4️⃣ 不在浪尖做决定\n潮水还会再来，清醒的人从不慌\n\n真的，焦虑退散，行动起来✨',
    tags: ['认知觉醒', '自我成长', '搞钱思维', '反内耗', '干货分享'],
  },
}
</script>
