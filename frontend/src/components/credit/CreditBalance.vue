<template>
  <button class="credit-balance" @click="goToRecharge">
    <div class="credit-icon">
      <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="5" width="16" height="10" rx="2" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="10" cy="10" r="2.5" stroke="currentColor" stroke-width="1.5"/>
        <path d="M2 8h16" stroke="currentColor" stroke-width="1.5"/>
      </svg>
    </div>
    <div v-if="!collapsed" class="credit-info">
      <span class="credit-amount">{{ creditStore.formattedBalance }}</span>
      <span class="credit-label">积分</span>
    </div>
  </button>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCreditStore } from '@/stores/credit'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const router = useRouter()
const creditStore = useCreditStore()

const goToRecharge = () => {
  router.push('/credits/recharge')
}

onMounted(async () => {
  await creditStore.fetchBalance()
})
</script>

<style scoped>
.credit-balance {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: all 0.14s;
  color: var(--ink-2);
  font-family: inherit;
}

.credit-balance:hover {
  background: var(--bone);
  border-color: var(--clay-soft);
  color: var(--ink);
}

.credit-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: var(--clay);
}

.credit-icon svg {
  width: 100%;
  height: 100%;
}

.credit-info {
  display: flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
}

.credit-amount {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.credit-label {
  font-size: 12px;
  color: var(--ink-4);
}
</style>