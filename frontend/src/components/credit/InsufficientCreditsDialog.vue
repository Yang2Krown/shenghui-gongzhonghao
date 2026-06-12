<template>
  <el-dialog
    v-model="visible"
    title="积分不足"
    width="400px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="insufficient-content">
      <div class="warning-icon">
        <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M24 4L4 42h40L24 4z" stroke="var(--clay)" stroke-width="3" stroke-linejoin="round"/>
          <path d="M24 18v10" stroke="var(--clay)" stroke-width="3" stroke-linecap="round"/>
          <circle cx="24" cy="34" r="2" fill="var(--clay)"/>
        </svg>
      </div>
      
      <div class="message">
        <p class="title">当前积分不足</p>
        <p class="detail">
          本次操作需要 <strong>{{ required }}</strong> 积分，
          当前余额 <strong>{{ balance }}</strong> 积分
        </p>
        <p class="operation" v-if="operationDesc">
          {{ operationDesc }}
        </p>
      </div>

      <div class="packages-section" v-if="packages.length > 0">
        <p class="section-title">快速充值</p>
        <div class="packages-grid">
          <div 
            v-for="pkg in packages" 
            :key="pkg.name"
            class="package-item"
            :class="{ recommended: pkg.badge }"
            @click="selectPackage(pkg)"
          >
            <div class="package-badge" v-if="pkg.badge">{{ pkg.badge }}</div>
            <div class="package-credits">{{ pkg.credits }}<span class="unit">积分</span></div>
            <div class="package-price">¥{{ pkg.price_yuan }}</div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">稍后再说</el-button>
        <el-button type="primary" @click="goToRecharge">
          去充值
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useCreditStore } from '@/stores/credit'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  balance: {
    type: Number,
    default: 0
  },
  required: {
    type: Number,
    default: 0
  },
  operation: {
    type: String,
    default: ''
  },
  operationDesc: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'recharge'])

const router = useRouter()
const creditStore = useCreditStore()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const packages = computed(() => creditStore.packages)

watch(visible, async (val) => {
  if (val && packages.value.length === 0) {
    await creditStore.fetchPackages()
  }
})

const selectPackage = (pkg) => {
  emit('recharge', pkg)
  handleClose()
}

const goToRecharge = () => {
  router.push('/credits/recharge')
  handleClose()
}

const handleClose = () => {
  visible.value = false
}
</script>

<style scoped>
.insufficient-content {
  text-align: center;
  padding: 10px 0;
}

.warning-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 20px;
}

.warning-icon svg {
  width: 100%;
  height: 100%;
}

.message {
  margin-bottom: 24px;
}

.message .title {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 12px;
}

.message .detail {
  font-size: 14px;
  color: var(--ink-3);
  margin-bottom: 8px;
  line-height: 1.6;
}

.message .detail strong {
  color: var(--clay);
  font-weight: 600;
}

.message .operation {
  font-size: 13px;
  color: var(--ink-4);
  margin-top: 4px;
}

.packages-section {
  text-align: left;
  padding: 16px;
  background: var(--ivory);
  border-radius: var(--r-md);
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 12px;
}

.packages-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.package-item {
  position: relative;
  padding: 14px 12px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: all 0.14s;
  text-align: center;
}

.package-item:hover {
  border-color: var(--clay-soft);
  background: var(--clay-tint);
}

.package-item.recommended {
  border-color: var(--clay);
}

.package-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  padding: 2px 8px;
  background: var(--clay);
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: var(--r-pill);
}

.package-credits {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 4px;
}

.package-credits .unit {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-4);
  margin-left: 2px;
}

.package-price {
  font-size: 14px;
  color: var(--clay);
  font-weight: 600;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>