<template>
  <div class="credit-page">
    <div class="page-header">
      <h1>积分充值</h1>
    </div>

    <!-- 当前余额 -->
    <div class="balance-card">
      <div class="balance-info">
        <div class="balance-label">当前积分余额</div>
        <div class="balance-amount">
          <span class="number">{{ creditStore.formattedBalance }}</span>
          <span class="unit">积分</span>
        </div>
      </div>
      <button class="history-btn" @click="router.push('/creation-history')">
        消耗记录
        <el-icon :size="14"><ArrowRight /></el-icon>
      </button>
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
      <p>· 开通会员赠送 6000 积分</p>
      <p>· 积分永不过期，操作失败不扣费</p>
      <p>· 1 积分 = ¥0.10</p>
    </div>

    <el-dialog
      v-model="payDialogVisible"
      title="微信扫码支付"
      width="360px"
      :close-on-click-modal="false"
      @closed="stopPolling"
    >
      <div class="pay-dialog">
        <div class="pay-summary">
          <div class="pay-package">{{ activeOrder?.package }}</div>
          <div class="pay-amount">¥{{ activeOrder?.amount_yuan }}</div>
          <div class="pay-credits">{{ activeOrder?.credits }} 积分</div>
        </div>
        <canvas ref="qrCanvasRef" class="qr-canvas"></canvas>
        <p class="qr-tip">请使用微信扫一扫完成支付</p>
        <p class="qr-sub">支付成功后页面会自动刷新余额</p>
        <p class="qr-warn">支付完成后请不要刷新或离开页面，系统正在自动确认支付结果。</p>
      </div>
      <template #footer>
        <el-button @click="payDialogVisible = false">稍后支付</el-button>
        <el-button type="primary" :loading="checkingPay" @click="checkStatusOnce">我已支付</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import { getPurchaseStatus } from '@/api/credit'
import { useCreditStore } from '@/stores/credit'

const router = useRouter()
const creditStore = useCreditStore()
const payDialogVisible = ref(false)
const activeOrder = ref(null)
const qrCanvasRef = ref(null)
const pollTimer = ref(null)
const checkingPay = ref(false)

onMounted(async () => {
  await Promise.all([
    creditStore.fetchBalance(),
    creditStore.fetchPackages(),
  ])
})

onBeforeUnmount(() => {
  stopPolling()
})

const handlePurchase = async (pkg) => {
  try {
    await ElMessageBox.confirm(
      `确定购买 ${pkg.name}（${pkg.credits} 积分，¥${pkg.price_yuan}）？`,
      '确认微信支付',
      { confirmButtonText: '生成二维码', cancelButtonText: '取消' }
    )
    const order = await creditStore.purchase(pkg.name)
    if (!order) return
    activeOrder.value = order
    payDialogVisible.value = true
    await nextTick()
    await renderQr(order.code_url)
    startPolling(order.out_trade_no)
  } catch {
    // 用户取消
  }
}

const renderQr = async (codeUrl) => {
  if (!qrCanvasRef.value || !codeUrl) return
  await QRCode.toCanvas(qrCanvasRef.value, codeUrl, {
    width: 220,
    margin: 1,
    color: {
      dark: '#1f1f1f',
      light: '#ffffff',
    },
  })
}

const startPolling = (outTradeNo) => {
  stopPolling()
  pollTimer.value = window.setInterval(() => {
    checkStatusOnce(outTradeNo)
  }, 2000)
}

const stopPolling = () => {
  if (pollTimer.value) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const checkStatusOnce = async (tradeNo = activeOrder.value?.out_trade_no) => {
  if (!tradeNo || checkingPay.value) return
  checkingPay.value = true
  try {
    const res = await getPurchaseStatus(tradeNo)
    const data = res.data || res
    if (data.status === 'PAID') {
      stopPolling()
      payDialogVisible.value = false
      await creditStore.fetchBalance()
      ElMessage.success('支付成功，积分已到账')
    }
  } finally {
    checkingPay.value = false
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 24px;
  margin-bottom: 24px;
}

.history-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 8px 16px;
  border-radius: var(--r-pill);
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-3);
  background: transparent;
  border: 1px solid var(--line);
  cursor: pointer;
  transition: all 0.15s;
}

.history-btn:hover {
  color: var(--clay-deep);
  border-color: var(--clay);
  background: var(--clay-tint);
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

.pay-dialog {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

:deep(.el-dialog__footer) {
  text-align: center;
}

.pay-summary {
  margin-bottom: 16px;
}

.pay-package {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-2);
}

.pay-amount {
  margin-top: 4px;
  font-size: 28px;
  font-weight: 700;
  color: var(--clay);
}

.pay-credits,
.qr-sub {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ink-4);
}

.qr-canvas {
  display: block;
  box-sizing: content-box;
  width: 220px;
  height: 220px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: #fff;
}

.qr-tip {
  margin: 14px 0 0;
  font-size: 14px;
  color: var(--ink-2);
}

.qr-warn {
  margin: 8px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--clay);
}
</style>
