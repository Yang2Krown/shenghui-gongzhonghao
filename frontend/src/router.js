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
      {
        path: 'content-info/commercial',
        redirect: '/potential-commercial'
      },
      // 潜在商单（顶级页面，时间轴视图）
      {
        path: 'potential-commercial',
        name: 'PotentialCommercial',
        component: () => import('@/pages/topics/PotentialCommercial.vue'),
        meta: { title: '潜在商单' }
      },
      // 课程资料（顶级页面，章节阅读）
      {
        path: 'courses',
        name: 'CourseMaterials',
        component: () => import('@/pages/courses/CourseMaterials.vue'),
        meta: { title: '课程资料' }
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
        path: 'creation/practical',
        name: 'PracticalCreation',
        component: () => import('@/pages/creation/PracticalCreation.vue'),
        meta: { title: '实操 / 商稿创作' }
      },
      {
        path: 'creation/wechat-editor',
        name: 'WechatEditor',
        component: () => import('@/pages/tools/WechatEditor.vue'),
        meta: { title: '公众号编辑器' }
      },
      // ⚠️ 临时：公众号抓取测试页（feature 验证后整段删除）
      {
        path: 'tools/gzh-test',
        name: 'GzhTest',
        component: () => import('@/pages/tools/GzhTest.vue'),
        meta: { title: '公众号抓取测试', requiresAdmin: true }
      },
      {
        path: 'admin',
        name: 'AdminDashboard',
        component: () => import('@/pages/admin/AdminDashboard.vue'),
        meta: { title: '后台监测', requiresAdmin: true }
      },
      {
        path: 'admin/source-health',
        name: 'AdminSourceHealth',
        component: () => import('@/pages/admin/SourceHealth.vue'),
        meta: { title: '数据源健康', requiresAdmin: true }
      },
      {
        path: 'admin/commercial-diagnostics',
        name: 'AdminCommercialDiagnostics',
        component: () => import('@/pages/admin/CommercialDiagnostics.vue'),
        meta: { title: '商单诊断', requiresAdmin: true }
      },
      {
        path: 'admin/ai-costs',
        name: 'AdminAiCosts',
        component: () => import('@/pages/admin/AiCostMonitor.vue'),
        meta: { title: 'AI 调用成本', requiresAdmin: true }
      },
      {
        path: 'admin/api-health',
        name: 'AdminApiHealth',
        component: () => import('@/pages/admin/ApiHealth.vue'),
        meta: { title: '接口健康', requiresAdmin: true }
      },
      {
        path: 'admin/security-health',
        name: 'AdminSecurityHealth',
        component: () => import('@/pages/admin/SecurityHealth.vue'),
        meta: { title: '安全健康', requiresAdmin: true }
      },
      {
        path: 'admin/user-stats',
        name: 'AdminUserStats',
        component: () => import('@/pages/admin/UserStats.vue'),
        meta: { title: '用户统计', requiresAdmin: true }
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/pages/admin/UserManagement.vue'),
        meta: { title: '用户管理', requiresAdmin: true }
      },
      // ===== 我的创作已下线 → 重定向到选题列表 =====
      {
        path: 'creation',
        redirect: '/content-info'
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
    meta: { title: 'IP罗盘 — 创作不迷路，商单有方向' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/auth/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/register',
    redirect: '/landing'
  },
  {
    path: '/membership',
    redirect: '/landing?show=membership'
  },
  {
    path: '/terms',
    name: 'Terms',
    component: () => import('@/pages/legal/LegalDoc.vue'),
    meta: { title: '用户协议' }
  },
  {
    path: '/privacy',
    name: 'Privacy',
    component: () => import('@/pages/legal/LegalDoc.vue'),
    meta: { title: '隐私政策' }
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
const PUBLIC_ROUTES = ['Login', 'NotFound', 'Landing', 'Terms', 'Privacy']

// 全局前置守卫
router.beforeEach(async (to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - IP罗盘` : 'IP罗盘'

  const userStore = useUserStore()
  if (!userStore.initialized) {
    await userStore.initialize()
  }
  const isPublic = PUBLIC_ROUTES.includes(to.name)

  if (!isPublic && !userStore.isAuthenticated) {
    // 未登录/token过期 → 统一跳 Landing 页
    next({ name: 'Landing', query: { redirect: to.fullPath } })
  } else if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next({ path: '/' })
  } else if (isPublic && userStore.isAuthenticated && to.name === 'Login') {
    // 已登录用户访问登录页 → 跳首页
    next({ path: '/' })
  } else if (to.name === 'Landing' && userStore.isAuthenticated && userStore.isMember) {
    // 已是会员访问 Landing 页 → 跳首页
    next({ path: '/' })
  } else if (userStore.isAuthenticated && !userStore.isMember && !userStore.isAdmin && to.name !== 'Landing') {
    // 已登录但不是会员（且非管理员）→ 跳 Landing 页打开会员弹窗
    next({ name: 'Landing', query: { show: 'membership' } })
  } else {
    next()
  }
})

export default router
