import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 路由配置
const routes = [
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      // 首页 = 话题库（新流程）
      {
        path: '',
        name: 'Home',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '话题库' }
      },
      // 话题库主入口
      {
        path: 'topic-clusters',
        name: 'TopicClusters',
        component: () => import('@/pages/topics/TopicClusterList.vue'),
        meta: { title: '话题库' }
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
        redirect: '/topic-clusters'
      },
      {
        path: 'topics/:id',
        redirect: '/topic-clusters'
      },
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
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/settings/ProfileSettings.vue'),
        meta: { title: '设置' }
      },
      {
        path: 'settings/style',
        redirect: '/settings'
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
      {
        path: 'history',
        name: 'History',
        component: () => import('@/pages/history/GenerationHistory.vue'),
        meta: { title: '生成记录' }
      }
    ]
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
    // 浏览器前进/后退：还原原位置
    if (savedPosition) return savedPosition
    // 同一路径只变 query（点 chip / 写 URL 状态等），保持当前滚动位置不变
    if (to.path === from.path) return false
    // 切换路由：回到顶部
    return { top: 0 }
  }
})

// 不需要登录的页面
const PUBLIC_ROUTES = ['Login', 'Register', 'NotFound']

// 全局前置守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - AI公众号内容运营平台` : 'AI公众号内容运营平台'

  const userStore = useUserStore()
  const isPublic = PUBLIC_ROUTES.includes(to.name)

  if (!isPublic && !userStore.isAuthenticated) {
    next({
      name: 'Login',
      query: { redirect: to.fullPath }
    })
  } else if (isPublic && userStore.isAuthenticated && to.name === 'Login') {
    // 已登录用户访问登录页，跳转首页
    next({ path: '/' })
  } else {
    next()
  }
})

export default router