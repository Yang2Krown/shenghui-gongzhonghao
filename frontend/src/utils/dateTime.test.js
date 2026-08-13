import { describe, expect, it } from 'vitest'
import { formatDateTimeMinute } from './dateTime'

describe('formatDateTimeMinute', () => {
  it('formats naive API Beijing timestamps without a trailing colon', () => {
    expect(formatDateTimeMinute('2026-08-13T17:47:32')).toBe('2026/8/13 17:47')
    expect(formatDateTimeMinute('2026-08-13 07:05:00')).toBe('2026/8/13 07:05')
  })

  it('converts timestamps with an explicit offset to Beijing time', () => {
    expect(formatDateTimeMinute('2026-08-13T09:47:32Z')).toBe('2026/8/13 17:47')
  })

  it('uses the fallback for empty or invalid input', () => {
    expect(formatDateTimeMinute('')).toBe('—')
    expect(formatDateTimeMinute('not-a-date', '暂无时间')).toBe('暂无时间')
  })
})
