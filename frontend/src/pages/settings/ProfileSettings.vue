<template>
  <div class="profile-settings">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h1 class="text-h2 font-serif text-ink">个人设置</h1>
      <p class="text-ink-3 mt-1">管理您的个人信息和账号设置</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 左侧：头像和个人信息 -->
      <div class="lg:col-span-1">
        <div class="card p-6">
          <div class="text-center">
            <!-- 头像 -->
            <div class="relative inline-block mb-4">
              <el-avatar :size="120" :src="userAvatar" class="bg-primary-500">
                <span class="text-4xl">{{ userName.charAt(0).toUpperCase() }}</span>
              </el-avatar>
              <el-button
                class="absolute bottom-0 right-0"
                circle
                size="small"
                @click="triggerAvatarUpload"
              >
                <el-icon><Camera /></el-icon>
              </el-button>
              <input
                ref="avatarInput"
                type="file"
                accept="image/*"
                class="hidden"
                @change="handleAvatarChange"
              />
            </div>
            
            <!-- 用户名 -->
            <h2 class="text-xl font-semibold text-ink">{{ userName }}</h2>
            <p class="text-ink-3">{{ user?.email }}</p>
            
            <!-- 统计信息 -->
            <div class="mt-6 grid grid-cols-2 gap-4">
              <div class="text-center">
                <div class="text-2xl font-bold text-clay">{{ stats.creations || 0 }}</div>
                <div class="text-sm text-ink-3">创作</div>
              </div>
              <div class="text-center">
                <div class="text-2xl font-bold text-clay">{{ stats.collected || 0 }}</div>
                <div class="text-sm text-ink-3">收藏</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：设置表单 -->
      <div class="lg:col-span-2">
        <div class="card">
          <!-- 基本信息 -->
          <div class="p-6 border-b border-line">
            <h3 class="text-lg font-medium text-ink mb-4">基本信息</h3>
            
            <el-form
              ref="profileFormRef"
              :model="profileForm"
              :rules="profileRules"
              label-width="100px"
              label-position="top"
            >
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <el-form-item label="用户名" prop="name">
                  <el-input v-model="profileForm.name" placeholder="请输入用户名" />
                </el-form-item>
                
                <el-form-item label="邮箱" prop="email">
                  <el-input v-model="profileForm.email" placeholder="请输入邮箱" disabled />
                </el-form-item>
              </div>
              
              <el-form-item label="个人简介" prop="bio">
                <el-input
                  v-model="profileForm.bio"
                  type="textarea"
                  :rows="3"
                  placeholder="介绍一下自己..."
                />
              </el-form-item>
              
              <el-form-item label="网站" prop="website">
                <el-input v-model="profileForm.website" placeholder="https://example.com" />
              </el-form-item>
              
              <el-form-item label="所在地" prop="location">
                <el-input v-model="profileForm.location" placeholder="城市，国家" />
              </el-form-item>
              
              <el-form-item>
                <el-button type="primary" @click="saveProfile" :loading="saving">
                  保存修改
                </el-button>
              </el-form-item>
            </el-form>
          </div>

          <!-- 修改密码 -->
          <div class="p-6 border-b border-line">
            <h3 class="text-lg font-medium text-ink mb-4">修改密码</h3>
            
            <el-form
              ref="passwordFormRef"
              :model="passwordForm"
              :rules="passwordRules"
              label-width="100px"
              label-position="top"
            >
              <el-form-item label="当前密码" prop="currentPassword">
                <el-input
                  v-model="passwordForm.currentPassword"
                  type="password"
                  placeholder="请输入当前密码"
                  show-password
                />
              </el-form-item>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <el-form-item label="新密码" prop="newPassword">
                  <el-input
                    v-model="passwordForm.newPassword"
                    type="password"
                    placeholder="请输入新密码"
                    show-password
                  />
                </el-form-item>
                
                <el-form-item label="确认新密码" prop="confirmPassword">
                  <el-input
                    v-model="passwordForm.confirmPassword"
                    type="password"
                    placeholder="请再次输入新密码"
                    show-password
                  />
                </el-form-item>
              </div>
              
              <el-form-item>
                <el-button type="primary" @click="changePassword" :loading="changingPassword">
                  修改密码
                </el-button>
              </el-form-item>
            </el-form>
          </div>

          <!-- 通知设置 -->
          <div class="p-6 border-b border-line">
            <h3 class="text-lg font-medium text-ink mb-4">通知设置</h3>
            
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <div>
                  <div class="font-medium text-ink">邮件通知</div>
                  <div class="text-sm text-ink-3">接收重要更新和通知</div>
                </div>
                <el-switch v-model="notificationSettings.email" />
              </div>
              
              <div class="flex items-center justify-between">
                <div>
                  <div class="font-medium text-ink">选题推荐</div>
                  <div class="text-sm text-ink-3">每日推荐热门选题</div>
                </div>
                <el-switch v-model="notificationSettings.topics" />
              </div>
              
              <div class="flex items-center justify-between">
                <div>
                  <div class="font-medium text-ink">创作提醒</div>
                  <div class="text-sm text-ink-3">提醒您定期创作内容</div>
                </div>
                <el-switch v-model="notificationSettings.creations" />
              </div>
            </div>
            
            <div class="mt-6">
              <el-button type="primary" @click="saveNotificationSettings" :loading="savingNotifications">
                保存设置
              </el-button>
            </div>
          </div>

          <!-- 账号操作 -->
          <div class="p-6">
            <h3 class="text-lg font-medium text-ink mb-4">账号操作</h3>
            
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <div>
                  <div class="font-medium text-ink">退出登录</div>
                  <div class="text-sm text-ink-3">退出当前账号</div>
                </div>
                <el-button type="danger" plain @click="handleLogout">
                  退出登录
                </el-button>
              </div>
              
              <div class="flex items-center justify-between">
                <div>
                  <div class="font-medium text-crimson">删除账号</div>
                  <div class="text-sm text-ink-3">永久删除您的账号和所有数据</div>
                </div>
                <el-button type="danger" @click="confirmDeleteAccount">
                  删除账号
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera } from '@element-plus/icons-vue'
import { updateProfile, changePassword as changePasswordApi, uploadAvatar } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

// 表单引用
const profileFormRef = ref(null)
const passwordFormRef = ref(null)
const avatarInput = ref(null)

// 状态
const saving = ref(false)
const changingPassword = ref(false)
const savingNotifications = ref(false)

// 用户信息
const user = computed(() => userStore.user)
const userName = computed(() => userStore.userName)
const userAvatar = computed(() => userStore.userAvatar)

// 统计信息
const stats = reactive({
  creations: 0,
  collected: 0
})

// 个人信息表单
const profileForm = reactive({
  name: '',
  email: '',
  bio: '',
  website: '',
  location: ''
})

// 密码表单
const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 通知设置
const notificationSettings = reactive({
  email: true,
  topics: true,
  creations: true
})

// 表单验证规则
const profileRules = {
  name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ]
}

const passwordRules = {
  currentPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度在 6 到 20 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 生命周期
onMounted(() => {
  loadUserProfile()
  loadStats()
})

// 加载用户信息
const loadUserProfile = () => {
  if (user.value) {
    profileForm.name = user.value.name || ''
    profileForm.email = user.value.email || ''
    profileForm.bio = user.value.bio || ''
    profileForm.website = user.value.website || ''
    profileForm.location = user.value.location || ''
  }
}

// 加载统计信息
const loadStats = async () => {
  // 这里应该调用API获取用户统计信息
  // 暂时使用模拟数据
  stats.creations = 12
  stats.collected = 8
}

// 保存个人信息
const saveProfile = async () => {
  try {
    await profileFormRef.value.validate()
    
    saving.value = true
    
    await updateProfile({
      name: profileForm.name,
      bio: profileForm.bio,
      website: profileForm.website,
      location: profileForm.location
    })
    
    // 更新store中的用户信息
    userStore.updateUser({
      name: profileForm.name,
      bio: profileForm.bio,
      website: profileForm.website,
      location: profileForm.location
    })
    
    ElMessage.success('个人信息保存成功')
  } catch (error) {
    if (error !== false) {
      ElMessage.error('保存失败')
      console.error('Save profile error:', error)
    }
  } finally {
    saving.value = false
  }
}

// 修改密码
const changePassword = async () => {
  try {
    await passwordFormRef.value.validate()
    
    changingPassword.value = true
    
    await changePasswordApi({
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword
    })
    
    ElMessage.success('密码修改成功')
    
    // 清空表单
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch (error) {
    if (error !== false) {
      ElMessage.error('密码修改失败')
      console.error('Change password error:', error)
    }
  } finally {
    changingPassword.value = false
  }
}

// 触发头像上传
const triggerAvatarUpload = () => {
  avatarInput.value.click()
}

// 处理头像变化
const handleAvatarChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  
  // 验证文件类型
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }
  
  // 验证文件大小（5MB）
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过5MB')
    return
  }
  
  try {
    const formData = new FormData()
    formData.append('avatar', file)
    
    const response = await uploadAvatar(formData)
    const { avatar_url } = response.data
    
    // 更新用户头像
    userStore.updateUser({ avatar: avatar_url })
    
    ElMessage.success('头像更新成功')
  } catch (error) {
    ElMessage.error('头像上传失败')
    console.error('Upload avatar error:', error)
  }
}

// 保存通知设置
const saveNotificationSettings = async () => {
  savingNotifications.value = true
  
  try {
    // 这里应该调用API保存通知设置
    await new Promise(resolve => setTimeout(resolve, 500))
    
    ElMessage.success('通知设置保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('Save notification settings error:', error)
  } finally {
    savingNotifications.value = false
  }
}

// 退出登录
const handleLogout = () => {
  ElMessageBox.confirm(
    '确定要退出登录吗？',
    '确认退出',
    {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    userStore.logout()
    router.push('/login')
  }).catch(() => {})
}

// 确认删除账号
const confirmDeleteAccount = () => {
  ElMessageBox.confirm(
    '此操作将永久删除您的账号和所有数据，且无法恢复。确定要删除吗？',
    '确认删除账号',
    {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'error'
    }
  ).then(() => {
    ElMessage.info('账号删除功能开发中')
  }).catch(() => {})
}
</script>

<style scoped>
.profile-settings {
  max-width: 1200px;
  margin: 0 auto;
}
</style>