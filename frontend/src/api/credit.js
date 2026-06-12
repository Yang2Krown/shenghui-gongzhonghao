import { get, post } from './api'

/**
 * 获取积分余额
 */
export const getCreditBalance = () => get('/credits/balance')

/**
 * 获取积分账户详情
 */
export const getCreditAccount = () => get('/credits/account')

/**
 * 检查积分是否足够
 */
export const checkCredits = (operation) => post(`/credits/check?operation=${operation}`)

/**
 * 获取交易记录
 */
export const getTransactions = (params = {}) => get('/credits/transactions', params)

/**
 * 获取消耗统计
 */
export const getConsumptionStats = () => get('/credits/consumption-stats')

/**
 * 获取积分套餐列表
 */
export const getCreditPackages = () => get('/credits/packages')

/**
 * 购买积分套餐（模拟，直接到账）
 */
export const purchaseCredits = (packageName) => post(`/credits/purchase?package_name=${encodeURIComponent(packageName)}`)