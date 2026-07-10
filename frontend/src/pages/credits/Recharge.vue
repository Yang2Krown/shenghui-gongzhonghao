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
        <div v-if="creditStore.subscriptionAccess === 'admin'" class="expire-hint admin-access">
          <span class="dot"></span>
          管理员账号 · 积分永久有效
        </div>
        <div v-else-if="creditStore.isSubscriptionActive" class="expire-hint">
          <span class="dot"></span>
          积分有效期：还剩 <strong>{{ creditStore.daysUntilExpire }}</strong> 天 · 将于 {{ creditStore.expireDateText }} 清零
        </div>
        <div v-else class="expire-hint inactive">
          <span class="dot"></span>
          未开通创作工具订阅，积分暂不可用
        </div>
      </div>
      <button class="history-btn" @click="router.push('/creation-history')">
        消耗记录
        <el-icon :size="14"><ArrowRight /></el-icon>
      </button>
    </div>

    <div class="recharge-rule-bar">
      <span class="rule-bar-label">充值说明</span>
      <span>1 元 = 10 积分 · 积分一经使用不支持退款</span>
      <a href="/terms" target="_blank" rel="noopener">查看用户协议 →</a>
    </div>

    <!-- 套餐列表 -->
    <div class="packages-grid">
      <div
        v-for="pkg in creditStore.packages"
        :key="pkg.name"
        class="package-card"
        :class="{
          recommended: pkg.badge,
          value: pkg.bonus_rate === 10,
          featured: pkg.bonus_rate === 20,
        }"
        @click="handlePurchase(pkg)"
      >
        <div class="package-glow"></div>
        <div class="package-topline">
          <span class="package-name">{{ pkg.name }}</span>
          <span class="package-badge" v-if="pkg.badge">{{ pkg.badge }}</span>
        </div>
        <div class="package-rate">基础比例 · 1 元 = 10 积分</div>
        <div class="package-credits">
          <span class="number">{{ pkg.credits }}</span>
          <span class="unit">积分</span>
        </div>
        <div class="package-benefit" :class="{ base: !pkg.bonus_credits }">
          <template v-if="pkg.bonus_credits">
            <strong>+{{ pkg.bonus_credits }}</strong> 赠送积分 <span>· 加赠 {{ pkg.bonus_rate }}%</span>
          </template>
          <template v-else>按需补充，灵活充值</template>
        </div>
        <div class="package-footer">
          <div>
            <span class="package-price">¥{{ pkg.price_yuan }}</span>
            <span class="package-price-unit">实付</span>
          </div>
          <button class="purchase-btn" @click.stop="handlePurchase(pkg)">
            立即充值 <span>→</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 说明 -->
    <div class="tips">
      <p>· 创作工具 ¥699 / 月，开通即赠 6000 积分</p>
      <p>· <strong>积分一个月过期</strong>：订阅到期后余额整体清零，需续费重新开通</p>
      <p>· 充值后即时到账 · 1 元 = 10 积分 · 操作失败不扣费</p>
      <div class="tips-disclaimer">
        <p>积分使用、退款与其他交易规则以 <a href="/terms" target="_blank" rel="noopener">《用户协议》</a> 为准。</p>
      </div>
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
    creditStore.fetchAccount(),
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
      await creditStore.fetchAccount()
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

.recharge-rule-bar {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: -10px 0 22px;
  padding: 10px 14px;
  border: 1px solid #eee2d7;
  border-radius: 10px;
  color: var(--ink-3);
  background: #fffaf6;
  font-size: 12px;
}

.rule-bar-label {
  flex-shrink: 0;
  color: var(--clay-deep);
  font-weight: 700;
}

.recharge-rule-bar a,
.tips-disclaimer a {
  flex-shrink: 0;
  color: var(--clay-deep);
  font-weight: 600;
  text-decoration: none;
}

.recharge-rule-bar a:hover,
.tips-disclaimer a:hover {
  text-decoration: underline;
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

.expire-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 5px 12px;
  border-radius: var(--r-pill);
  font-size: 12.5px;
  color: var(--clay-deep);
  background: var(--clay-tint);
}

.expire-hint strong {
  font-weight: 700;
}

.expire-hint .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--clay);
  flex-shrink: 0;
}

.expire-hint.inactive {
  color: var(--ink-3);
  background: var(--bone);
}

.expire-hint.inactive .dot {
  background: var(--ink-4);
}

/* 套餐 */
.packages-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.package-card {
  position: relative;
  isolation: isolate;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 18px;
  min-height: 252px;
  padding: 22px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.package-card:hover {
  border-color: var(--clay);
  box-shadow: 0 16px 32px rgba(112, 67, 48, 0.16);
  transform: translateY(-5px);
}

.package-card.recommended {
  border: 2px solid var(--clay);
  padding: 21px;
}

.package-card.value {
  background: linear-gradient(145deg, #fffaf4 0%, #f8ece1 100%);
  border-color: #d68a68;
}

.package-card.featured {
  color: #fffaf2;
  background: linear-gradient(140deg, #4a3028 0%, #7e4334 52%, #ba6349 130%);
  border-color: #4a3028;
  box-shadow: 0 10px 24px rgba(91, 47, 36, 0.25);
}

.package-glow {
  position: absolute;
  z-index: -1;
  top: -34px;
  right: -24px;
  width: 112px;
  height: 112px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(221, 131, 91, 0.12), rgba(221, 131, 91, 0) 70%);
}

.featured .package-glow {
  background: radial-gradient(circle, rgba(255, 221, 156, 0.2), rgba(255, 221, 156, 0) 70%);
}

.package-topline,
.package-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.package-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.package-badge {
  flex-shrink: 0;
  padding: 5px 10px;
  color: #fff;
  background: var(--clay);
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.package-rate {
  margin-top: 13px;
  font-size: 12px;
  color: var(--ink-4);
}

.package-credits {
  margin-top: 24px;
  letter-spacing: -0.04em;
}

.package-credits .number {
  font-size: 42px;
  font-weight: 800;
  line-height: 1;
}

.package-credits .unit {
  margin-left: 5px;
  font-size: 14px;
  color: var(--ink-3);
  letter-spacing: 0;
}

.package-benefit {
  min-height: 22px;
  margin-top: 13px;
  font-size: 13px;
  color: var(--clay-deep);
}

.package-benefit strong {
  font-size: 16px;
}

.package-benefit.base {
  color: var(--ink-4);
}

.package-footer {
  margin-top: 22px;
}

.package-price {
  font-size: 25px;
  font-weight: 800;
  color: var(--clay-deep);
}

.package-price-unit {
  margin-left: 5px;
  font-size: 12px;
  color: var(--ink-4);
}

.purchase-btn {
  border: 0;
  border-radius: 10px;
  padding: 10px 12px;
  color: #fff;
  background: var(--ink);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.16s ease, background 0.16s ease;
}

.purchase-btn span {
  margin-left: 2px;
  font-size: 17px;
  line-height: 0;
}

.purchase-btn:hover {
  background: var(--clay-deep);
  transform: translateX(2px);
}

.featured .package-rate,
.featured .package-credits .unit,
.featured .package-price-unit {
  color: rgba(255, 250, 242, 0.7);
}

.featured .package-benefit,
.featured .package-price {
  color: #ffe3b0;
}

.featured .package-badge {
  color: #693625;
  background: #ffe3b0;
}

.featured .purchase-btn {
  color: #6b3428;
  background: #ffe3b0;
}

.featured .purchase-btn:hover {
  background: #fff5de;
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

.tips-disclaimer {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
}

.tips-disclaimer p {
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-4);
}

@media (max-width: 560px) {
  .recharge-rule-bar {
    align-items: flex-start;
    flex-wrap: wrap;
    line-height: 1.55;
  }
}

.expire-hint.admin-access {
  color: #3d7657;
  background: #e6f3e9;
}

.expire-hint.admin-access .dot {
  background: #4b9368;
}

@media (max-width: 560px) {
  .credit-page {
    padding: 12px 0;
  }

  .balance-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-btn {
    align-self: flex-end;
  }

  .packages-grid {
    grid-template-columns: 1fr;
  }
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
