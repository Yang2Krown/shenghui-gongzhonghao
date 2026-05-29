import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      // 内容资讯（首页）
      {
        path: '',
        name: 'Feed',
        component: () => import('@/pages/feed/FeedScreen.vue'),
        meta: { title: '内容资讯' }
      },
      // 话题详情
      {
        path: 'topic-clusters/:id',
        name: 'TopicClusterDetail',
        component: () => import('@/pages/topics/TopicClusterDetail.vue'),
        meta: { title: '话题详情' }
      },
      // 创作工具
      {
        path: 'angle',
        name: 'Angle',
        component: () => import('@/pages/tools/AngleTool.vue'),
        meta: { title: '创作角度' }
      },
      {
        path: 'outline',
        name: 'Outline',
        component: () => import('@/pages/tools/OutlineTool.vue'),
        meta: { title: '大纲生成' }
      },
      {
        path: 'body',
        name: 'Body',
        component: () => import('@/pages/tools/BodyTool.vue'),
        meta: { title: '正文生成' }
      },
      {
        path: 'title',
        name: 'Title',
        component: () => import('@/pages/tools/TitleTool.vue'),
        meta: { title: '标题生成' }
      },
      // 内容仿写
      {
        path: 'wechat-to-xhs',
        name: 'WechatToXhs',
        component: () => import('@/pages/rewrite/WechatToXhs.vue'),
        meta: { title: '公众号转小红书' }
      },
      {
        path: 'wechat-rewrite',
        name: 'WechatRewrite',
        component: () => import('@/pages/rewrite/WechatRewrite.vue'),
        meta: { title: '公众号仿写' }
      },
      {
        path: 'xhs-to-wechat',
        name: 'XhsToWechat',
        component: () => import('@/pages/rewrite/XhsToWechat.vue'),
        meta: { title: '小红书转公众号' }
      },
      {
        path: 'douyin-to-wechat',
        name: 'DouyinToWechat',
        component: () => import('@/pages/rewrite/DouyinToWechat.vue'),
        meta: { title: '抖音转公众号' }
      },
      {
        path: 'zhihu-to-wechat',
        name: 'ZhihuToWechat',
        component: () => import('@/pages/rewrite/ZhihuToWechat.vue'),
        meta: { title: '知乎转公众号' }
      },
      {
        path: 'content-rewrite',
        name: 'ContentRewrite',
        component: () => import('@/pages/rewrite/ContentRewrite.vue'),
        meta: { title: '内容仿写' }
      },
      // 创作历史
      {
        path: 'history',
        name: 'History',
        component: () => import('@/pages/history/HistoryScreen.vue'),
        meta: { title: '创作历史' }
      },
      // 个人信息
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/pages/profile/ProfileScreen.vue'),
        meta: { title: '个人信息' }
      },
      // ===== 兼容旧路由 =====
      {
        path: 'topic-clusters',
        redirect: '/'
      },
      {
        path: 'topic-candidates',
        redirect: '/'
      },
      {
        path: 'creation',
        redirect: '/'
      },
      {
        path: 'creation/new',
        redirect: '/'
      },
      {
        path: 'creation/editor/:id',
        redirect: '/'
      },
      {
        path: 'creation/:id',
        redirect: '/'
      },
      {
        path: 'settings',
        redirect: '/profile'
      },
      {
        path: 'settings/style',
        redirect: '/profile'
      },
      {
        path: 'standalone-title',
        redirect: '/title'
      },
      {
        path: 'munger-generation',
        redirect: '/title'
      },
      {
        path: 'munger-scorer',
        redirect: '/title'
      },
      {
        path: 'custom-topic',
        redirect: '/angle'
      },
      {
        path: 'history',
        redirect: '/history'
      },
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
    if (savedPosition) return savedPosition
    if (to.path === from.path) return false
    return { top: 0 }
  }
})

const PUBLIC_ROUTES = ['Login', 'Register', 'NotFound']

router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 公众号创作台` : '公众号创作台'
  const userStore = useUserStore()
  const isPublic = PUBLIC_ROUTES.includes(to.name)

  if (!isPublic && !userStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (isPublic && userStore.isAuthenticated && to.name === 'Login') {
    next({ path: '/' })
  } else {
    next()
  }
})

export default router
