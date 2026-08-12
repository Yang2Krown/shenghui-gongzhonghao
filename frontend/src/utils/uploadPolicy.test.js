import { describe, expect, it } from 'vitest'
import {
  UPLOAD_POLICIES,
  UPLOAD_LIMITS,
  validateUploadFile,
} from './uploadPolicy'

const file = (name, size = 1, type = '') => ({ name, size, type })

describe('uploadPolicy 与后端契约一致', () => {
  it('文档类 brief/reference/style 统一 20MB,cover 保持 10MB', () => {
    expect(UPLOAD_POLICIES.brief.maxMB).toBe(20)
    expect(UPLOAD_POLICIES.reference.maxMB).toBe(20)
    expect(UPLOAD_POLICIES.style.maxMB).toBe(20)
    expect(UPLOAD_LIMITS.cover).toBe(10)
  })

  it('reference/brief/style 放开图片(后端 qwen-vl OCR),cover 仅图片', () => {
    for (const key of ['brief', 'reference', 'style']) {
      expect(UPLOAD_POLICIES[key].allowImage).toBe(true)
      expect(UPLOAD_POLICIES[key].extensions).toContain('.png')
    }
    expect(UPLOAD_POLICIES.cover.imageOnly).toBe(true)
    expect(UPLOAD_POLICIES.document.allowImage).toBe(false)
  })
})

describe('validateUploadFile', () => {
  it('reference 接受文档和图片', () => {
    for (const n of ['a.pdf', 'b.DOCX', 'c.txt', 'd.md', 'e.png', 'f.jpg', 'g.webp']) {
      expect(validateUploadFile(file(n), 'reference')).toBeNull()
    }
  })

  it('document 策略支持文章复盘文件并统一 20MB 上限', () => {
    expect(validateUploadFile(file('before.pdf'), 'document')).toBeNull()
    expect(validateUploadFile(file('after.markdown'), 'document')).toBeNull()
    const limit = UPLOAD_POLICIES.document.maxMB * 1024 * 1024
    expect(validateUploadFile(file('large.docx', limit + 1), 'document')).toBe('文件大小不能超过 20MB')
  })

  it('document 策略拒绝图片', () => {
    expect(validateUploadFile(file('a.png', 1, 'image/png'), 'document')).toMatch(/仅支持/)
  })

  it('拒绝不支持的类型与老版 .doc', () => {
    expect(validateUploadFile(file('a.exe'), 'reference')).toMatch(/仅支持/)
    expect(validateUploadFile(file('a.doc'), 'reference')).toMatch(/仅支持/)
  })

  it('cover 策略只收图片', () => {
    expect(validateUploadFile(file('a.png', 1, 'image/png'), 'cover')).toBeNull()
    expect(validateUploadFile(file('a.pdf', 1, 'application/pdf'), 'cover')).toMatch(/图片/)
  })

  it('大小边界:恰好上限通过,超 1 字节拒绝,文案含正确上限', () => {
    const brief = UPLOAD_POLICIES.brief.maxMB * 1024 * 1024
    expect(validateUploadFile(file('a.txt', brief), 'brief')).toBeNull()
    expect(validateUploadFile(file('a.txt', brief + 1), 'brief')).toBe('文件大小不能超过 20MB')

    const ref = UPLOAD_POLICIES.reference.maxMB * 1024 * 1024
    expect(validateUploadFile(file('a.txt', ref + 1), 'reference')).toBe('文件大小不能超过 20MB')
  })

  it('空文件返回 null(由后端空校验兜底)', () => {
    expect(validateUploadFile(null, 'reference')).toBeNull()
  })
})
