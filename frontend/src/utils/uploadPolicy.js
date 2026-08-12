/**
 * 全站文件上传策略 —— 唯一事实来源。
 *
 * 每个使用场景在这里声明:接受哪些扩展名、大小上限、提示文案。
 * 这些值必须与后端 upload_security.py 的白名单(DOCUMENT_EXTS ∪ IMAGE_EXTS)
 * 以及各上传接口的 max_size 保持一致,改这里就能全站生效。
 *
 * 后端能力(已确认):文档(pdf/docx/txt/md/markdown)+ 图片(png/jpg/jpeg/webp/gif,
 * 走 dashscope qwen-vl 视觉 OCR)。
 */

export const DOCUMENT_EXTS = ['.pdf', '.docx', '.txt', '.md', '.markdown']
export const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.webp', '.gif']

// 后端各接口实际上限(MB),与 upload_security / 路由里的 max_size 对齐
export const UPLOAD_LIMITS = {
  brief: 20,      // POST /feishu/brief/upload
  reference: 20,  // POST /creation-tools/upload(创作工具 8 页共用)
  style: 20,      // POST /styles/sources/upload
  cover: 10,      // POST /images/upload(封面)
  articleReview: 20,
}

export const ARTICLE_REVIEW_UPLOAD_LIMITS = {
  singleMB: UPLOAD_LIMITS.articleReview,
  filesTotalMB: 40,
  requestMB: 45,
}

const DOC_ACCEPT = DOCUMENT_EXTS.join(',')
const DOC_IMAGE_ACCEPT = [...DOCUMENT_EXTS, ...IMAGE_EXTS].join(',')

export const UPLOAD_POLICIES = {
  /** 商单 brief(PracticalCreation)→ /feishu/brief/upload,20MB */
  brief: {
    accept: DOC_IMAGE_ACCEPT,
    extensions: [...DOCUMENT_EXTS, ...IMAGE_EXTS],
    maxMB: UPLOAD_LIMITS.brief,
    allowImage: true,
    hint: `PDF / Word / TXT / MD / 图片,单文件不超过 ${UPLOAD_LIMITS.brief}MB`,
  },
  /** 创作工具参考文件(角度/大纲/正文/标题/续写/润色/转写/仿写)→ /creation-tools/upload,20MB */
  reference: {
    accept: DOC_IMAGE_ACCEPT,
    extensions: [...DOCUMENT_EXTS, ...IMAGE_EXTS],
    maxMB: UPLOAD_LIMITS.reference,
    allowImage: true,
    hint: `PDF / Word / TXT / MD / 图片,单文件不超过 ${UPLOAD_LIMITS.reference}MB`,
  },
  /** 风格源(AddSourceModal)→ /styles/sources/upload,20MB */
  style: {
    accept: DOC_IMAGE_ACCEPT,
    extensions: [...DOCUMENT_EXTS, ...IMAGE_EXTS],
    maxMB: UPLOAD_LIMITS.style,
    allowImage: true,
    hint: `PDF / Word / TXT / MD / 图片,单文件不超过 ${UPLOAD_LIMITS.style}MB`,
  },
  /** 仅文档(不放图片的场景备用)→ 文档扩展名 */
  document: {
    accept: DOC_ACCEPT,
    extensions: [...DOCUMENT_EXTS],
    maxMB: UPLOAD_LIMITS.reference,
    allowImage: false,
    hint: `PDF / Word / TXT / MD,单文件不超过 ${UPLOAD_LIMITS.reference}MB`,
  },
  /** 封面/图片素材 → /images/upload,仅图片 */
  cover: {
    accept: 'image/*',
    extensions: [...IMAGE_EXTS],
    maxMB: UPLOAD_LIMITS.cover,
    allowImage: true,
    imageOnly: true,
    hint: `PNG / JPG / WebP 图片,不超过 ${UPLOAD_LIMITS.cover}MB`,
  },
  /** 文章复盘改前/改后两份文档；单文件和两文件合计分别校验。 */
  articleReview: {
    accept: DOC_ACCEPT,
    extensions: [...DOCUMENT_EXTS],
    maxMB: ARTICLE_REVIEW_UPLOAD_LIMITS.singleMB,
    allowImage: false,
    hint: `改前和改后文件各不超过 ${ARTICLE_REVIEW_UPLOAD_LIMITS.singleMB}MB，两份文件合计不超过 ${ARTICLE_REVIEW_UPLOAD_LIMITS.filesTotalMB}MB`,
  },
}

/**
 * 校验一个待上传文件。返回 null 表示通过,否则返回给用户看的中文错误。
 * @param {File|null} file
 * @param {keyof typeof UPLOAD_POLICIES} policyKey
 */
export function validateUploadFile(file, policyKey = 'reference') {
  if (!file) return null
  const policy = UPLOAD_POLICIES[policyKey] || UPLOAD_POLICIES.reference

  // image/* 的 accept 交给浏览器原生过滤;具体扩展名在客户端再兜底一次
  const name = String(file.name || '')
  const ext = ('.' + (name.split('.').pop() || '')).toLowerCase()

  if (policy.imageOnly) {
    const isImage = (file.type || '').startsWith('image/') || IMAGE_EXTS.includes(ext)
    if (!isImage) return '仅支持 PNG / JPG / WebP 等图片文件'
  } else if (!policy.extensions.includes(ext)) {
    const label = policy.allowImage
      ? '仅支持 PDF、Word（DOCX）、TXT、MD 和图片（PNG/JPG/WebP）文件'
      : '仅支持 PDF、Word（DOCX）、TXT 和 MD 文件'
    return label
  }

  if (file.size > policy.maxMB * 1024 * 1024) {
    const actualMB = (file.size / 1024 / 1024).toFixed(2)
    return `单个文件超限：实际 ${actualMB}MB，限制 ${policy.maxMB}MB`
  }
  return null
}

export function validateArticleReviewFiles(beforeFile, afterFile) {
  const files = [beforeFile, afterFile].filter(Boolean)
  const totalBytes = files.reduce((sum, file) => sum + Number(file.size || 0), 0)
  const limitBytes = ARTICLE_REVIEW_UPLOAD_LIMITS.filesTotalMB * 1024 * 1024
  if (totalBytes > limitBytes) {
    return `本次请求文件总大小超限：实际 ${(totalBytes / 1024 / 1024).toFixed(2)}MB，限制 ${ARTICLE_REVIEW_UPLOAD_LIMITS.filesTotalMB}MB（不含 multipart 开销）`
  }
  return null
}
