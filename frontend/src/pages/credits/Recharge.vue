<template>
  <div class="credit-page">
    <div class="page-header">
      <h1>积分充值</h1>
    </div>

    <!-- 当前余额 -->
    <div class="balance-card">
      <div class="balance-label">当前积分余额</div>
      <div class="balance-amount">
        <span class="number">{{ creditStore.formattedBalance }}</span>
        <span class="unit">积分</span>
      </div>
    </div>

    <!-- 套餐列表 -->
    <div class="packages-grid">
      <div
        v-for="pkg in creditStore.packages"
        :key="pkg.name"
        class="package-card"
        :class="{ recommended: pkg.badge }"
        @click="handlePurchase(pkg)"
      >
        <div class="package-badge" v-if="pkg.badge">{{ pkg.badge }}</div>
        <div class="package-name">{{ pkg.name }}</div>
        <div class="package-credits">
          <span class="number">{{ pkg.credits }}</span>
          <span class="unit">积分</span>
        </div>
        <div class="package-price">¥{{ pkg.price_yuan }}</div>
        <div class="package-original" v-if="pkg.original_price_yuan">
          ¥{{ pkg.original_price_yuan }}
        </div>
      </div>
    </div>

    <!-- 说明 -->
    <div class="tips">
      <p>· 新用户注册即送 20 积分</p>
      <p>· 积分永不过期，操作失败不扣费</p>
      <p>· 1 积分 = ¥0.10</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useCreditStore } from '@/stores/credit'

const creditStore = useCreditStore()

onMounted(async () => {
  await Promise.all([
    creditStore.fetchBalance(),
    creditStore.fetchPackages(),
  ])
})

const handlePurchase = async (pkg) => {
  try {
    await ElMessageBox.confirm(
      `确定购买 ${pkg.name}（${pkg.credits} 积分）？`,
      '确认购买',
      { confirmButtonText: '确定购买', cancelButtonText: '取消' }
    )
    await creditStore.purchase(pkg.name)
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.credit-page {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px 0;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 24px;
}

/* 余额 */
.balance-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 24px;
  margin-bottom: 24px;
}

.balance-label {
  font-size: 13px;
  color: var(--ink-4);
  margin-bottom: 8px;
}

.balance-amount {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.balance-amount .number {
  font-size: 32px;
  font-weight: 700;
  color: var(--ink);
}

.balance-amount .unit {
  font-size: 14px;
  color: var(--ink-3);
}

/* 套餐 */
.packages-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.package-card {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 24px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.14s;
}

.package-card:hover {
  border-color: var(--clay);
  background: var(--clay-tint);
}

.package-card.recommended {
  border-color: var(--clay);
}

.package-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  padding: 3px 10px;
  background: var(--clay);
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: var(--r-pill);
}

.package-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 16px;
}

.package-credits {
  margin-bottom: 12px;
}

.package-credits .number {
  font-size: 32px;
  font-weight: 700;
  color: var(--ink);
}

.package-credits .unit {
  font-size: 13px;
  color: var(--ink-4);
  margin-left: 4px;
}

.package-price {
  font-size: 20px;
  font-weight: 700;
  color: var(--clay);
}

.package-original {
  font-size: 13px;
  color: var(--ink-4);
  text-decoration: line-through;
  margin-top: 4px;
}

/* 说明 */
.tips {
  background: var(--ivory);
  border-radius: var(--r-md);
  padding: 16px 20px;
}

.tips p {
  font-size: 13px;
  color: var(--ink-3);
  line-height: 2;
  margin: 0;
}
</style>