import { describe, expect, it } from 'vitest'
import {
  meetingStatusLabel,
  synthesisParseStatusLabel,
  suggestionStatusLabel,
  suggestionStatusOptions,
} from './meetingUi'

describe('meeting workbench view rules', () => {
  it('明确展示提取失败和建议终态', () => {
    expect(meetingStatusLabel('failed')).toBe('失败')
    expect(meetingStatusLabel('ready')).toBe('已完成')
    expect(synthesisParseStatusLabel('repaired')).toBe('已自动修复')
    expect(suggestionStatusLabel('done')).toBe('已完成')
    expect(suggestionStatusLabel('rejected')).toBe('已驳回')
  })

  it('前端状态选项与后端状态机一致', () => {
    expect(suggestionStatusOptions('proposed')).toEqual(['proposed', 'adopted', 'rejected'])
    expect(suggestionStatusOptions('adopted')).toEqual(['adopted', 'in_progress', 'rejected'])
    expect(suggestionStatusOptions('in_progress')).toEqual(['in_progress', 'done', 'rejected'])
    expect(suggestionStatusOptions('done')).toEqual(['done'])
    expect(suggestionStatusOptions('rejected')).toEqual(['rejected'])
  })
})
