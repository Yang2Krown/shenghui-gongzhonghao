<template>
  <div class="app-layout" style="min-height: 100vh; background: var(--ivory);">
    <!-- 侧边栏 -->
    <aside
      class="app-sidebar"
      :class="{ 'is-mobile-open': mobileMenuOpen }"
      :style="{ width: isCollapsed ? '64px' : '248px' }"
    >
      <div class="flex flex-col h-full">
        <!-- Logo区域 -->
        <div class="mobile-sidebar-head flex items-center" style="padding: 13px 20px 13px;">
          <div class="brand-mark">
            <img src="/brand/ip-compass.svg" alt="IP罗盘" />
          </div>
          <div v-if="!isCollapsed" class="brand-copy">
            <div class="brand-title">IP罗盘</div>
            <div class="brand-subtitle">Creator Compass</div>
          </div>
          <button
            class="mobile-menu-close"
            type="button"
            aria-label="关闭导航菜单"
            @click="closeMobileMenu"
          >
            ×
          </button>
        </div>

        <!-- 导航菜单 -->
        <nav class="flex-1 overflow-y-auto" style="padding: 14px 12px; display: flex; flex-direction: column; gap: 3px; border-top: 1px solid var(--line);">
          <template v-for="item in visibleNavItems" :key="item.id">
            <!-- 普通菜单项 -->
            <button
              v-if="!item.children"
              @click="navigateTo(item.id)"
              :class="['nav-item', { 'nav-item--active': activeRoute === item.id }]"
            >
              <el-icon :size="19"><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </button>

            <!-- 可折叠分组 -->
            <div v-else>
              <button
                @click="toggleGroup(item.id)"
                :class="['nav-item nav-item--group', { 'nav-item--active': isChildActive(item) }]"
              >
                <el-icon :size="19"><component :is="item.icon" /></el-icon>
                <span style="flex: 1; text-align: left;">{{ item.label }}</span>
                <el-icon
                  :size="15"
                  class="nav-chevron"
                  :class="{ 'nav-chevron--open': openGroups[item.id] }"
                >
                  <ArrowRight />
                </el-icon>
              </button>
              <div v-if="openGroups[item.id]" class="nav-group-children">
                <button
                  v-for="child in item.children"
                  :key="child.id"
                  @click="navigateTo(child.id)"
                  :class="['nav-item nav-item--indent', { 'nav-item--active': activeRoute === child.id }]"
                >
                  <span>{{ child.label }}</span>
                </button>
              </div>
            </div>
          </template>
        </nav>

        <!-- 用户信息 -->
        <div style="height: 65px; padding: 0 14px; border-top: 1px solid var(--line); display: flex; align-items: center;">
          <button class="nav-user-btn" @click="navigateTo('profile')" style="padding: 6px 8px;">
            <div style="width: 30px; height: 30px; border-radius: 50%; background: var(--clay); color: #fff; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-weight: 600; font-family: var(--serif); overflow: hidden;">
              <img
                v-if="userStore.userAvatar"
                :src="userStore.userAvatar"
                style="width: 100%; height: 100%; object-fit: cover;"
                @error="(e) => e.target.style.display = 'none'"
              />
              <span v-else>{{ userStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}</span>
            </div>
            <div v-if="!isCollapsed" style="text-align: left; min-width: 0;">
              <div class="text-sm font-semibold text-ink truncate" style="max-width: 140px;">
                {{ userStore.user?.full_name || userStore.user?.username || '用户' }}
              </div>
              <div class="text-xs text-ink-4 truncate" style="max-width: 140px;">
                专业版
              </div>
            </div>
          </button>
        </div>
      </div>
    </aside>

    <button
      v-if="mobileMenuOpen"
      class="mobile-menu-backdrop"
      type="button"
      aria-label="关闭导航菜单"
      @click="closeMobileMenu"
    />

    <!-- 主内容区 -->
    <div
      class="app-content-shell transition-all duration-300"
      :style="{ marginLeft: isCollapsed ? '64px' : '248px' }"
    >
      <!-- 顶部导航栏 -->
      <header class="app-topbar" :style="{ left: isCollapsed ? '64px' : '248px' }">
        <button
          class="mobile-menu-button"
          type="button"
          aria-label="打开导航菜单"
          :aria-expanded="mobileMenuOpen"
          @click="mobileMenuOpen = true"
        >
          <el-icon :size="20"><Expand /></el-icon>
        </button>
        <div class="app-breadcrumb flex items-center" style="gap: 8px; color: var(--ink-4); font-size: 13px; flex: 1;">
          <span>首页</span>
          <template v-if="currentGroup">
            <el-icon :size="13"><ArrowRight /></el-icon>
            <span>{{ currentGroup }}</span>
          </template>
          <el-icon :size="13"><ArrowRight /></el-icon>
          <span class="font-semibold text-ink-2">{{ currentLabel }}</span>
        </div>
        <!-- 积分余额 -->
        <div v-if="hasCreationTool" class="credit-topbar-wrap">
          <button class="credit-topbar" @click="router.push('/credits/recharge')" :class="{ 'credit-animate': creditAnimating }">
            <span class="credit-amount">{{ creditStore.formattedBalance }}</span>
            <span class="credit-label">积分</span>
          </button>
          <transition name="credit-toast">
            <div v-if="creditDelta" class="credit-toast" :class="creditDelta > 0 ? 'is-gain' : 'is-cost'">
              {{ creditDelta > 0 ? '充值' : '消耗' }}
              <strong>{{ creditDelta > 0 ? '+' : '-' }}{{ Math.abs(creditDelta) }}</strong>
              积分
            </div>
          </transition>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="app-main" style="padding-top: 60px;">
        <div class="app-main-content fade-in" style="padding: 32px 32px 80px;">
          <router-view v-slot="{ Component, route }">
            <keep-alive :include="['TopicClusterList']">
              <component v-if="!previewProduct" :is="Component" :key="route.name" />
              <ProductPreview v-else :product="previewProduct" />
            </keep-alive>
          </router-view>
        </div>
      </main>
    </div>
    
    <!-- 积分不足弹窗 -->
    <InsufficientCreditsDialog
      v-model="showInsufficientDialog"
      :balance="insufficientInfo.balance"
      :required="insufficientInfo.required"
      :operation="insufficientInfo.operation"
      :operation-desc="insufficientInfo.operationDesc"
    />
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useCreditStore } from '@/stores/credit'
import InsufficientCreditsDialog from '@/components/credit/InsufficientCreditsDialog.vue'
import ProductPreview from '@/components/product/ProductPreview.vue'
import {
  Edit, Setting, ArrowRight, Expand, Fold, User,
  Document, ChatDotSquare, Switch, EditPen, Clock, View, Reading
} from '@element-plus/icons-vue'

// 自定义图标组件
const IconFeed = document.createElement('div') // placeholder, 使用 el-icon
const IconTool = EditPen
const IconSwap = Switch
const IconAngle = EditPen
const IconOutline = Document
const IconBody = Document
const IconTitle = ChatDotSquare

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const productForPath = (path) => {
  if (path.startsWith('/xhs-materials')) return 'xhs_topic'
  if (path.startsWith('/potential-commercial') || path.startsWith('/content-info/commercial')) return 'potential_commercial'
  if (path.startsWith('/courses')) return 'practical_camp'
  if (
    path === '/' || path.startsWith('/content-info') || path.startsWith('/topic-clusters') ||
    path.startsWith('/legacy') || path.startsWith('/creation') || path.startsWith('/content-transform') ||
    path.startsWith('/content-imitate') || path.startsWith('/creation-history') || path.startsWith('/history') ||
    path.startsWith('/standalone-title') || path.startsWith('/munger-generation') || path.startsWith('/wechat-to-xhs') ||
    path.startsWith('/custom-topic') || path.startsWith('/munger-scorer')
  ) return 'creation_tool'
  return null
}

const previewProduct = computed(() => {
  const required = route.meta?.product || productForPath(route.path)
  return required && !userStore.hasProduct(required) ? required : null
})
const hasCreationTool = computed(() => userStore.hasProduct('creation_tool'))
const creditStore = useCreditStore()

const isCollapsed = ref(false)
const mobileMenuOpen = ref(false)

// 积分动画
const creditAnimating = ref(false)
const creditDelta = ref(0)
let creditDeltaTimer = null
watch(() => creditStore.balance, (newVal, oldVal) => {
  // oldVal 为 undefined/0 时是首次加载，不提示
  if (!oldVal || newVal === oldVal) return
  if (newVal < oldVal) {
    creditAnimating.value = true
    setTimeout(() => { creditAnimating.value = false }, 600)
  }
  creditDelta.value = newVal - oldVal
  clearTimeout(creditDeltaTimer)
  creditDeltaTimer = setTimeout(() => { creditDelta.value = 0 }, 2600)
})

// 积分不足弹窗
const showInsufficientDialog = ref(false)
const insufficientInfo = ref({
  balance: 0,
  required: 0,
  operation: '',
  operationDesc: '',
})

// 监听积分不足事件
const handleInsufficientCredits = (event) => {
  insufficientInfo.value = event.detail
  showInsufficientDialog.value = true
}

onMounted(() => {
  window.addEventListener('insufficient-credits', handleInsufficientCredits)
  // 积分只属于创作工具；实战营用户不请求该接口，避免被创作工具门禁误拦。
  if (hasCreationTool.value) creditStore.fetchBalance()
})

onUnmounted(() => {
  window.removeEventListener('insufficient-credits', handleInsufficientCredits)
})

const openGroups = reactive({
  'topic-info': true,
  create: true,
  rewrite: true,
  team: true,
  admin: true,
})

// 导航结构
const navItems = [
  {
    id: 'topic-info',
    label: '信息选题',
    icon: 'Document',
    children: [
      { id: 'content-info', label: '选题列表' },
      { id: 'content-info-news', label: '资讯信息' },
      { id: 'content-info-cases', label: '实操案例' },
    ],
  },
  {
    id: 'xhs-materials',
    label: '小红书选题',
    icon: 'TrendCharts',
    product: 'xhs_topic',
  },
  {
    id: 'potential-commercial',
    label: '潜在商单',
    icon: 'View',
  },
  {
    id: 'courses',
    label: '课程资料',
    icon: 'Reading',
  },
  {
    id: 'create',
    label: '创作工具',
    icon: 'EditPen',
    children: [
      { id: 'creation-angle', label: '创作角度' },
      { id: 'creation-outline', label: '大纲生成' },
      { id: 'creation-body', label: '正文生成' },
      { id: 'creation-title', label: '标题生成' },
      { id: 'creation-continuation', label: '正文续写' },
      { id: 'creation-polish', label: '文案润色' },
      { id: 'creation-practical', label: '实操 / 商稿' },
      { id: 'creation-wechat-editor', label: '公众号编辑器' },
    ],
  },
  {
    id: 'rewrite',
    label: '内容仿写',
    icon: 'Switch',
    children: [
      { id: 'content-transform', label: '转写' },
      { id: 'content-imitate', label: '仿写' },
    ],
  },
  {
    id: 'creation-history',
    label: '创作历史',
    icon: 'Clock',
  },
  {
    id: 'profile',
    label: '个人信息',
    icon: 'User',
  },
  {
    id: 'team',
    label: '团队协作',
    icon: 'User',
    employeeOnly: true,
    children: [
      { id: 'team-members', label: '团队管理' },
      { id: 'meetings', label: '会议方法论' },
      { id: 'article-reviews', label: '文章复盘' },
      { id: 'experience', label: '经验库' },
    ],
  },
  {
    id: 'admin',
    label: '后台管理',
    icon: 'Setting',
    adminOnly: true,
    children: [
      { id: 'admin-dashboard', label: '监测总览' },
      { id: 'admin-source-health', label: '数据源健康' },
      { id: 'admin-xhs-monitoring', label: '小红书采集监测' },
      { id: 'admin-commercial-diagnostics', label: '商单诊断' },
      { id: 'admin-ai-costs', label: 'AI 成本' },
      { id: 'admin-api-health', label: '接口健康' },
      { id: 'admin-security-health', label: '安全健康' },
      { id: 'admin-user-stats', label: '用户统计' },
      { id: 'admin-users', label: '用户管理' },
      { id: 'admin-announcements', label: '系统公告' },
      { id: 'admin-task-center', label: '任务中心' },
      { id: 'gzh-test', label: '公众号抓取测试' },
    ],
  },
]

const canSeeAdminChild = (child) => {
  if (userStore.isSuperAdmin) return true
  if (!child.roles) return true
  return child.roles.includes(userStore.user?.role)
}

const visibleNavItems = computed(() => navItems
  .filter(item => {
    if (item.adminOnly && !userStore.isAdmin) return false
    if (item.employeeOnly && !userStore.isTeamMember) return false
    if (item.product && !userStore.hasProduct(item.product)) return false
    return true
  })
  .map(item => {
    if (!item.children) return item
    return {
      ...item,
      children: item.children.filter(child => (!child.adminOnly || userStore.isAdmin) && canSeeAdminChild(child)),
    }
  }))

// 当前激活路由
const activeRoute = computed(() => {
  const path = route.path
  if (path === '/content-info/news') return 'content-info-news'
  if (path === '/content-info/cases') return 'content-info-cases'
  if (path === '/xhs-materials') return 'xhs-materials'
  if (path === '/potential-commercial' || path === '/content-info/commercial') return 'potential-commercial'
  if (path.startsWith('/courses')) return 'courses'
  if (path === '/' || path.startsWith('/topic-clusters') || path === '/content-info') return 'content-info'
  if (path.startsWith('/creation/angle')) return 'creation-angle'
  if (path.startsWith('/creation/outline')) return 'creation-outline'
  if (path.startsWith('/creation/body')) return 'creation-body'
  if (path.startsWith('/creation/title')) return 'creation-title'
  if (path.startsWith('/creation/continuation')) return 'creation-continuation'
  if (path.startsWith('/creation/polish')) return 'creation-polish'
  if (path.startsWith('/creation/practical')) return 'creation-practical'
  if (path.startsWith('/creation/wechat-editor')) return 'creation-wechat-editor'
  if (path.startsWith('/creation')) {
    // 检查是否是旧的创作列表页面
    if (path === '/creation' || path === '/creation/') return 'creation'
    return 'creation'
  }
  if (path.startsWith('/content-transform')) return 'content-transform'
  if (path.startsWith('/content-imitate')) return 'content-imitate'
  if (path.startsWith('/history') || path.startsWith('/creation-history')) return 'creation-history'
  if (path.startsWith('/settings') || path.startsWith('/profile')) return 'profile'
  if (path.startsWith('/team')) return 'team-members'
  if (path.startsWith('/meetings')) return 'meetings'
  if (path.startsWith('/article-reviews')) return 'article-reviews'
  if (path.startsWith('/experience')) return 'experience'
  if (path.startsWith('/admin/source-health')) return 'admin-source-health'
  if (path.startsWith('/admin/xhs-monitoring')) return 'admin-xhs-monitoring'
  if (path.startsWith('/admin/commercial-diagnostics')) return 'admin-commercial-diagnostics'
  if (path.startsWith('/admin/ai-costs')) return 'admin-ai-costs'
  if (path.startsWith('/admin/api-health')) return 'admin-api-health'
  if (path.startsWith('/admin/security-health')) return 'admin-security-health'
  if (path.startsWith('/admin/user-stats')) return 'admin-user-stats'
  if (path.startsWith('/admin/users')) return 'admin-users'
  if (path.startsWith('/admin/announcements')) return 'admin-announcements'
  if (path.startsWith('/admin/task-center')) return 'admin-task-center'
  if (path.startsWith('/admin')) return 'admin-dashboard'
  if (path.startsWith('/tools/gzh-test')) return 'gzh-test'
  return 'content-info'
})

// 当前分组名
const currentGroup = computed(() => {
  const id = activeRoute.value
  for (const item of visibleNavItems.value) {
    if (item.id === id) return null
    if (item.children?.some(c => c.id === id)) return item.label
  }
  return null
})

// 当前标签
const currentLabel = computed(() => {
  const id = activeRoute.value
  for (const item of visibleNavItems.value) {
    if (item.id === id) return item.label
    if (item.children) {
      const child = item.children.find(c => c.id === id)
      if (child) return child.label
    }
  }
  return ''
})

// 是否有子项激活
const isChildActive = (item) => {
  return item.children?.some(c => c.id === activeRoute.value)
}

// 切换分组
const toggleGroup = (id) => {
  openGroups[id] = !openGroups[id]
}

// 路由映射
const routeMap = {
  'content-info': '/content-info',
  'content-info-news': '/content-info/news',
  'content-info-cases': '/content-info/cases',
  'xhs-materials': '/xhs-materials',
  'potential-commercial': '/potential-commercial',
  'courses': '/courses',
  'creation-angle': '/creation/angle',
  'creation-outline': '/creation/outline',
  'creation-body': '/creation/body',
  'creation-title': '/creation/title',
  'creation-continuation': '/creation/continuation',
  'creation-polish': '/creation/polish',
  'creation-practical': '/creation/practical',
  'creation-wechat-editor': '/creation/wechat-editor',
  'content-transform': '/content-transform',
  'content-imitate': '/content-imitate',
  'creation-history': '/creation-history',
  'profile': '/profile',
  'team-members': '/team',
  'meetings': '/meetings',
  'article-reviews': '/article-reviews',
  'experience': '/experience',
  'creation': '/creation',
  'admin-dashboard': '/admin',
  'admin-source-health': '/admin/source-health',
  'admin-xhs-monitoring': '/admin/xhs-monitoring',
  'admin-commercial-diagnostics': '/admin/commercial-diagnostics',
  'admin-ai-costs': '/admin/ai-costs',
  'admin-api-health': '/admin/api-health',
  'admin-security-health': '/admin/security-health',
  'admin-user-stats': '/admin/user-stats',
  'admin-users': '/admin/users',
  'admin-announcements': '/admin/announcements',
  'admin-task-center': '/admin/task-center',
  'gzh-test': '/tools/gzh-test',
}

// 导航
const navigateTo = (id) => {
  const path = routeMap[id]
  if (path) {
    router.push(path)
    window.scrollTo({ top: 0 })
    closeMobileMenu()
  }
}

const closeMobileMenu = () => {
  mobileMenuOpen.value = false
}

const handleMobileMenuKeydown = (event) => {
  if (event.key === 'Escape') closeMobileMenu()
}

watch(() => route.path, closeMobileMenu)

onMounted(() => {
  window.addEventListener('keydown', handleMobileMenuKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleMobileMenuKeydown)
})
</script>

<style scoped>
.brand-mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  flex-shrink: 0;
  overflow: hidden;
  box-shadow: 0 8px 18px rgba(204, 120, 92, .22);
}

.brand-mark img {
  width: 100%;
  height: 100%;
  display: block;
}

.brand-copy {
  margin-left: 11px;
  min-width: 0;
  transform: translateY(-1px);
}

.brand-title {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', ui-serif, Georgia, serif;
  font-size: 19px;
  font-weight: 700;
  line-height: 1.02;
  color: var(--ink);
  letter-spacing: .01em;
}

.brand-subtitle {
  margin-top: 3px;
  font-family: 'Fraunces', ui-serif, Georgia, serif;
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1;
  color: var(--ink-4);
  letter-spacing: .075em;
}

.app-sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  background: var(--paper);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  z-index: 30;
  overflow: hidden;
  transition: width 0.3s cubic-bezier(.32,.72,0,1);
}

.mobile-menu-button,
.mobile-menu-backdrop,
.mobile-menu-close {
  display: none;
}

.app-content-shell {
  min-width: 0;
}

.app-topbar {
  position: fixed;
  top: 0;
  right: 0;
  height: 60px;
  /* 实心背景：半透明 +  backdrop 模糊会让下方滚动内容在顶栏透出，观感割裂 */
  background: var(--ivory);
  border-bottom: 1px solid var(--line);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  transition: left 0.3s cubic-bezier(.32,.72,0,1);
}

/* 导航项 */
.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  text-align: left;
  padding: 10px 14px;
  border: none;
  cursor: pointer;
  border-radius: var(--r-md);
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-2);
  background: transparent;
  transition: all 0.14s;
}

.nav-item:hover {
  color: var(--ink);
  background: var(--bone);
}

.nav-item--active {
  font-weight: 600;
  color: var(--clay-deep);
  background: var(--clay-tint);
}

.nav-item--group {
  font-weight: 600;
}

.nav-item--indent {
  padding: 9px 14px 9px 40px;
  font-size: 13px;
}

.nav-chevron {
  color: var(--ink-4);
  transition: transform 0.18s;
}

.nav-chevron--open {
  transform: rotate(90deg);
}

.nav-group-children {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
}

/* 用户按钮 */
.nav-user-btn {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: var(--r-md);
  font-family: inherit;
  transition: background 0.14s;
}

.nav-user-btn:hover {
  background: var(--bone);
}

/* 折叠按钮 */
.nav-collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: var(--r-sm);
  color: var(--ink-3);
  transition: all 0.14s;
}

.nav-collapse-btn:hover {
  background: var(--bone);
  color: var(--ink);
}

/* 右上角积分 */
.credit-topbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  cursor: pointer;
  transition: all 0.14s;
  font-family: inherit;
}

.credit-topbar:hover {
  border-color: var(--clay-soft);
  background: var(--clay-tint);
}

.credit-topbar .credit-amount {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.credit-topbar .credit-label {
  font-size: 12px;
  color: var(--ink-4);
}

/* 积分扣除动画 */
.credit-animate {
  animation: credit-deduct 0.6s ease;
}

@keyframes credit-deduct {
  0% { transform: scale(1); }
  30% { transform: scale(1.1); border-color: var(--clay); background: var(--clay-tint); }
  100% { transform: scale(1); }
}

/* 积分变动弹窗（从积分框下边缘向下弹出） */
.credit-topbar-wrap {
  position: relative;
}

.credit-toast {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: var(--r-md);
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.1);
  font-size: 12px;
  color: var(--ink-3);
  white-space: nowrap;
}

.credit-toast strong {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.credit-toast.is-cost {
  border-color: rgba(192, 57, 43, 0.3);
  color: #c0392b;
}
.credit-toast.is-gain {
  border-color: rgba(31, 157, 85, 0.35);
  color: #1f9d55;
}

/*
 * Mobile layout is deliberately isolated behind a media query. The desktop
 * sidebar, fixed topbar, spacing and collapse behavior above remain unchanged.
 */
@media (max-width: 768px) {
  .app-sidebar {
    width: min(86vw, 320px) !important;
    max-width: 320px;
    transform: translateX(-105%);
    box-shadow: 18px 0 48px rgba(31, 31, 30, .12);
    transition: transform .26s cubic-bezier(.32,.72,0,1);
    z-index: 1100;
  }

  .app-sidebar.is-mobile-open {
    transform: translateX(0);
  }

  .mobile-sidebar-head {
    padding-right: 14px !important;
  }

  .mobile-menu-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    margin-left: auto;
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    background: transparent;
    color: var(--ink-3);
    font-size: 24px;
    line-height: 1;
    cursor: pointer;
  }

  .mobile-menu-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 1090;
    border: 0;
    padding: 0;
    background: rgba(31, 31, 30, .28);
    backdrop-filter: blur(2px);
  }

  .app-content-shell {
    margin-left: 0 !important;
  }

  .app-topbar {
    left: 0 !important;
    height: 58px;
    padding: 0 14px;
    z-index: 1000;
  }

  .mobile-menu-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 38px;
    width: 38px;
    height: 38px;
    margin-right: 6px;
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    background: var(--paper);
    color: var(--ink-2);
    cursor: pointer;
  }

  .app-breadcrumb {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  .app-breadcrumb > span {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .app-breadcrumb > .el-icon:nth-of-type(1),
  .app-breadcrumb > span:first-child {
    display: none;
  }

  .credit-topbar {
    gap: 4px;
    padding: 6px 9px;
  }

  .credit-topbar .credit-label {
    display: none;
  }

  .app-main {
    padding-top: 58px !important;
  }

  .app-main-content {
    padding: 18px 14px 56px !important;
  }
}

.credit-toast-enter-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease;
}
.credit-toast-leave-active {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.credit-toast-enter-from,
.credit-toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}

</style>
