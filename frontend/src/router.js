import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 路由配置
const routes = [
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      // 首页 = 内容资讯
      {
        path: '',
        name: 'Home',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '内容资讯' }
      },
      // 内容资讯
      {
        path: 'content-info',
        name: 'ContentInfo',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '内容资讯' }
      },
      // 资讯型（仅资讯型，按时间排序）
      { 
        path: 'content-info/news',
        name: 'ContentInfoNews',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '资讯型', preset: '资讯型' }
      },
      // 实操案例（仅实操案例型，按当前价值分排序）
      {
        path: 'content-info/cases',
        name: 'ContentInfoCases',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '实操案例', preset: '实操案例型' }
      },
      // 话题库（保留旧路由，兼容）
      {
        path: 'topic-clusters',
        name: 'TopicClusters',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '内容资讯' }
      },
      {
        path: 'topic-clusters/:id',
        name: 'TopicClusterDetail',
        component: () => import('@/pages/topics/TopicClusterDetail.vue'),
        meta: { title: '话题详情' }
      },
      // 候选选题清单（二级视图）
      {
        path: 'topic-candidates',
        name: 'TopicCandidates',
        component: () => import('@/pages/topics/TopicCandidateList.vue'),
        meta: { title: '候选选题清单' }
      },
      // ===== Legacy 旧表入口（隐藏，但保留可访问） =====
      {
        path: 'legacy/topics',
        name: 'LegacyTopics',
        component: () => import('@/pages/topics/TopicList.vue'),
        meta: { title: '原始素材库（旧）', hideInMenu: true }
      },
      {
        path: 'legacy/topics/:id',
        name: 'LegacyTopicDetail',
        component: () => import('@/pages/topics/TopicDetail.vue'),
        meta: { title: '原始素材详情（旧）', hideInMenu: true }
      },
      // ===== 旧路由 → 重定向，避免书签失效 =====
      {
        path: 'topics',
        redirect: '/content-info'
      },
      {
        path: 'topics/:id',
        redirect: '/content-info'
      },
      // ===== 创作工具（新的独立页面） =====
      {
        path: 'creation/angle',
        name: 'CreationAngle',
        component: () => import('@/pages/tools/CreationAngle.vue'),
        meta: { title: '创作角度' }
      },
      {
        path: 'creation/outline',
        name: 'CreationOutline',
        component: () => import('@/pages/tools/CreationOutline.vue'),
        meta: { title: '大纲生成' }
      },
      {
        path: 'creation/body',
        name: 'CreationBody',
        component: () => import('@/pages/tools/CreationBody.vue'),
        meta: { title: '正文生成' }
      },
      {
        path: 'creation/title',
        name: 'CreationTitle',
        component: () => import('@/pages/tools/CreationTitle.vue'),
        meta: { title: '标题生成' }
      },
      {
        path: 'creation/continuation',
        name: 'CreationContinuation',
        component: () => import('@/pages/tools/CreationContinuation.vue'),
        meta: { title: '正文续写' }
      },
      {
        path: 'creation/polish',
        name: 'CreationPolish',
        component: () => import('@/pages/tools/CreationPolish.vue'),
        meta: { title: '文案润色' }
      },
      {
        path: 'creation/wechat-editor',
        name: 'WechatEditor',
        component: () => import('@/pages/tools/WechatEditor.vue'),
        meta: { title: '公众号编辑器' }
      },
      // ===== 我的创作（保留旧入口） =====
      {
        path: 'creation',
        name: 'Creation',
        component: () => import('@/pages/creation/CreationList.vue'),
        meta: { title: '我的创作' }
      },
      {
        path: 'creation/new',
        name: 'NewCreation',
        component: () => import('@/pages/creation/CreationEditor.vue'),
        meta: { title: '新建创作' }
      },
      {
        path: 'creation/editor/:id',
        name: 'EditCreation',
        component: () => import('@/pages/creation/CreationEditor.vue'),
        meta: { title: '编辑创作' }
      },
      {
        path: 'creation/:id',
        name: 'CreationDraft',
        component: () => import('@/pages/creation/CreationDraft.vue'),
        meta: { title: '草稿详情' }
      },
      // ===== 内容仿写 =====
      {
        path: 'content-transform',
        name: 'ContentTransform',
        component: () => import('@/pages/rewrite/ContentTransform.vue'),
        meta: { title: '转写' }
      },
      {
        path: 'content-imitate',
        name: 'ContentImitate',
        component: () => import('@/pages/rewrite/ContentImitate.vue'),
        meta: { title: '仿写' }
      },
      // ===== 创作历史 =====
      {
        path: 'creation-history',
        name: 'CreationHistory',
        component: () => import('@/pages/history/GenerationHistory.vue'),
        meta: { title: '创作历史' }
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/pages/history/GenerationHistory.vue'),
        meta: { title: '创作历史' }
      },
      // ===== 个人信息 =====
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/pages/settings/ProfileSettings.vue'),
        meta: { title: '个人信息' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/settings/ProfileSettings.vue'),
        meta: { title: '个人信息' }
      },
      // ===== 积分充值 =====
      {
        path: 'credits/recharge',
        name: 'CreditRecharge',
        component: () => import('@/pages/credits/Recharge.vue'),
        meta: { title: '积分充值' }
      },
      {
        path: 'settings/style',
        redirect: '/profile'
      },
      // ===== 旧路由 → 重定向到创作工作台 =====
      {
        path: 'outlines',
        redirect: '/creation'
      },
      {
        path: 'outlines/:id',
        redirect: '/creation'
      },
      {
        path: 'title-generation',
        redirect: '/creation'
      },
      {
        path: 'title-history',
        redirect: '/creation'
      },
      {
        path: 'content-generation',
        redirect: '/creation'
      },
      // 独立标题生成（复用创作流水线）
      {
        path: 'standalone-title',
        name: 'StandaloneTitle',
        component: () => import('@/pages/titles/StandaloneTitleGeneration.vue'),
        meta: { title: '智能起标题' }
      },
      // 芒格版标题
      {
        path: 'munger-generation',
        name: 'MungerGeneration',
        component: () => import('@/pages/titles/MungerGeneration.vue'),
        meta: { title: '芒格版标题生成' }
      },
      // 公众号转小红书
      {
        path: 'wechat-to-xhs',
        name: 'WechatToXhs',
        component: () => import('@/pages/conversion/WechatToXhs.vue'),
        meta: { title: '公众号转小红书' }
      },
      // 自定义选题创作
      {
        path: 'custom-topic',
        name: 'CustomTopic',
        component: () => import('@/pages/custom/CustomTopic.vue'),
        meta: { title: '自定义选题' }
      },
      {
        path: 'munger-scorer',
        name: 'MungerScorer',
        component: () => import('@/pages/titles/TitleScorer.vue'),
        meta: { title: '芒格版标题评分' }
      },
    ]
  },
  {
    path: '/landing',
    name: 'Landing',
    component: () => import('@/pages/Landing.vue'),
    meta: { title: '公众号智能体 — 从选题到发布，AI 全程帮你搞定' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/auth/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/pages/auth/Register.vue'),
    meta: { title: '注册' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/error/NotFound.vue'),
    meta: { title: '页面未找到' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.path === from.path) return false
    if (['Home', 'TopicClusters', 'ContentInfo', 'ContentInfoNews', 'ContentInfoCases'].includes(to.name)) return false
    return { top: 0 }
  }
})

// 不需要登录的页面
const PUBLIC_ROUTES = ['Login', 'Register', 'NotFound', 'Landing']

// 全局前置守卫
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 公众号创作台` : '公众号创作台'

  const userStore = useUserStore()
  const isPublic = PUBLIC_ROUTES.includes(to.name)

  if (!isPublic && !userStore.isAuthenticated) {
    // 未登录/token过期 → 统一跳 Landing 页
    next({
      name: 'Landing',
      query: { redirect: to.fullPath }
    })
  } else if (isPublic && userStore.isAuthenticated && (to.name === 'Login' || to.name === 'Landing')) {
    next({ path: '/' })
  } else {
    next()
  }
})

export default router
