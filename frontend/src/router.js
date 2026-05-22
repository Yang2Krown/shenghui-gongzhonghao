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
        path: 'creation/:id',
        name: 'EditCreation',
        component: () => import('@/pages/creation/CreationEditor.vue'),
        meta: { title: '编辑创作' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/settings/ProfileSettings.vue'),
        meta: { title: '个人设置' }
      },
      {
        path: 'settings/style',
        name: 'StyleSettings',
        component: () => import('@/pages/settings/StyleSettings.vue'),
        meta: { title: '风格设置' }
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
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// 全局前置守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - AI公众号内容运营平台` : 'AI公众号内容运营平台'
  
  // 检查是否需要登录
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  const userStore = useUserStore()
  
  if (requiresAuth && !userStore.isAuthenticated) {
    next({
      name: 'Login',
      query: { redirect: to.fullPath }
    })
  } else {
    next()
  }
})

export default router