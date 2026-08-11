export const meetingStatusLabel = (value) => ({ extracting: '整理中', ready: '已完成', failed: '失败' }[value] || value || '未知')
export const meetingStatusType = (value) => ({ extracting: 'warning', ready: 'success', failed: 'danger' }[value] || 'info')
export const synthesisParseStatusLabel = (value) => ({ parsed: '结构化输出', repaired: '已自动修复' }[value] || value || '未生成')
export const suggestionStatusLabel = (value) => ({ proposed: '待确认', adopted: '已采纳', in_progress: '执行中', done: '已完成', rejected: '已驳回' }[value] || value || '未知')
export const suggestionStatusType = (value) => ({ proposed: 'info', adopted: 'warning', in_progress: 'primary', done: 'success', rejected: 'danger' }[value] || 'info')
export const priorityType = (value) => ({ P0: 'danger', P1: 'warning', P2: 'info' }[value] || 'info')
export const suggestionStatusOptions = (current) => {
  const next = {
    proposed: ['proposed', 'adopted', 'rejected'],
    adopted: ['adopted', 'in_progress', 'rejected'],
    in_progress: ['in_progress', 'done', 'rejected'],
    done: ['done'],
    rejected: ['rejected'],
  }
  return next[current] || [current]
}
