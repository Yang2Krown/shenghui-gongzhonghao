<template>
  <div class="profile-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">个人信息</h1>
        <p class="page-desc">管理你的账户、创作偏好与使用情况</p>
      </div>
    </div>

    <!-- 用户卡片 -->
    <div class="card user-card">
      <div class="user-avatar">{{ name.charAt(0) }}</div>
      <div class="user-info">
        <h3 class="user-name">{{ name }}</h3>
        <p class="user-email">{{ userStore.user?.email || 'user@example.com' }} · 专业版</p>
      </div>
      <div class="user-stats">
        <div v-for="s in stats" :key="s.label" class="stat-item">
          <div class="stat-value">{{ s.value }}<span class="stat-unit">{{ s.unit }}</span></div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <!-- 创作偏好 -->
    <div class="card prefs-card">
      <div class="section-title">
        <h3>创作偏好</h3>
        <span class="section-hint">影响所有生成工具的默认风格</span>
      </div>
      <div class="pref-field">
        <label class="label">昵称</label>
        <input class="input-field" style="max-width: 320px;" v-model="name" />
      </div>
      <div class="pref-field">
        <label class="label">默认写作语气</label>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button v-for="t in tones" :key="t" @click="tone = t"
            :class="['chip', tone === t && 'chip-active']">{{ t }}</button>
        </div>
      </div>
      <div class="pref-field">
        <label class="label">个人简介 / 账号定位</label>
        <textarea class="textarea-field" rows="3" placeholder="描述你的公众号定位、目标读者、内容方向……"
          v-model="bio"></textarea>
      </div>
    </div>

    <!-- 账户 -->
    <div class="card account-card">
      <div class="section-title"><h3>账户</h3></div>
      <div class="account-list">
        <div v-for="(item, i) in accountInfo" :key="item[0]" class="account-row"
          :style="{ borderTop: i ? '1px solid var(--line)' : 'none' }">
          <span class="account-key">{{ item[0] }}</span>
          <span class="account-val">{{ item[1] }}</span>
        </div>
      </div>
      <div style="display: flex; gap: 12px; margin-top: 18px;">
        <button class="btn btn-clay" @click="save">保存修改</button>
        <button class="btn btn-ghost" @click="logout">退出登录</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const name = ref(userStore.user?.full_name || userStore.user?.username || '用户')
const tone = ref('理性克制')
const bio = ref('关注商业与社会观察，写给愿意慢下来思考的人。')

const tones = ['理性克制', '亲切口语', '犀利观点', '温暖治愈']

const stats = [
  { label: '累计创作', value: '128', unit: '篇' },
  { label: '本月生成', value: '23', unit: '次' },
  { label: '仿写转换', value: '41', unit: '次' },
]

const accountInfo = [
  ['当前套餐', '专业版 · 2026-12-31 到期'],
  ['绑定公众号', '待配置'],
  ['登录设备', '1 台'],
]

const save = () => {
  // TODO: 保存用户设置
}

const logout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-page { max-width: 760px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 30px; line-height: 1.2; font-weight: 500; font-family: var(--serif); color: var(--ink); margin: 0; }
.page-desc { font-size: 14px; color: var(--ink-3); margin-top: 6px; }

.user-card {
  padding: 28px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--clay);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 600;
  font-family: var(--serif);
  flex-shrink: 0;
}

.user-info { flex: 1; }
.user-name { font-size: 22px; font-weight: 600; color: var(--ink); margin: 0; }
.user-email { font-size: 14px; color: var(--ink-3); margin-top: 4px; }

.user-stats { display: flex; gap: 28px; }
.stat-item { text-align: center; }
.stat-value { font-size: 26px; font-weight: 600; color: var(--clay); font-family: var(--serif); }
.stat-unit { font-size: 14px; color: var(--ink-4); margin-left: 2px; }
.stat-label { font-size: 12px; color: var(--ink-4); }

.prefs-card, .account-card { padding: 28px; margin-bottom: 20px; }

.section-title { display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; }
.section-title h3 { font-size: 16px; font-weight: 600; color: var(--ink); margin: 0; }
.section-hint { font-size: 12px; color: var(--ink-4); }

.pref-field { margin-bottom: 20px; }
.label { display: block; font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 8px; }

.input-field {
  width: 100%;
  font-family: inherit;
  font-size: 15px;
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 11px 14px;
  outline: none;
  transition: all 0.15s;
}

.input-field:focus {
  border-color: var(--clay);
  box-shadow: 0 0 0 3px rgba(204,120,92,0.12);
}

.textarea-field {
  width: 100%;
  font-family: inherit;
  font-size: 15px;
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 14px;
  outline: none;
  transition: all 0.15s;
  line-height: 1.6;
  resize: none;
}

.textarea-field:focus {
  border-color: var(--clay);
  box-shadow: 0 0 0 3px rgba(204,120,92,0.12);
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  border-radius: var(--r-pill);
  padding: 6px 13px;
  font-size: 13px;
  font-weight: 500;
  background: var(--paper);
  color: var(--ink-2);
  border: 1px solid var(--line);
  transition: all 0.15s;
}

.chip:hover { border-color: var(--clay-soft); color: var(--ink); }
.chip-active { background: var(--ink); color: var(--paper); border-color: var(--ink); }

.account-list { display: flex; flex-direction: column; }
.account-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
}
.account-key { font-size: 14px; font-weight: 500; color: var(--ink-2); }
.account-val { font-size: 14px; color: var(--ink-3); }
</style>
