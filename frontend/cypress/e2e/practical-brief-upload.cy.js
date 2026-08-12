const api = (path) => '**/api/v1/' + path
const uploadEndpoint = api('feishu/brief/upload')
const summarizeEndpoint = api('feishu/brief/summarize')

const makeFile = (fileName = 'brief.txt', contents = '商单 brief 回归测试内容') => ({
  contents: Cypress.Buffer.from(contents),
  fileName,
  mimeType: 'text/plain',
  lastModified: Date.now(),
})

const fakeUser = {
  id: 9001,
  phone: '13900000000',
  username: 'frontend-smoke',
  full_name: '前端 Smoke',
  role: 'user',
  is_member: true,
  is_superuser: false,
  product_access: ['creation_tool'],
}

const prepareAuthenticatedPage = () => {
  cy.intercept('GET', api('users/profile'), {
    statusCode: 200,
    body: fakeUser,
  }).as('profile')
  cy.intercept('GET', api('credits/balance'), {
    statusCode: 200,
    body: { balance: 10000 },
  }).as('creditBalance')
  cy.intercept('GET', api('announcements/active'), {
    statusCode: 200,
    body: { items: [] },
  }).as('announcements')

  cy.visit('/creation/practical', {
    onBeforeLoad(win) {
      win.localStorage.setItem('token', 'cypress-smoke-token')
      win.localStorage.setItem('tokenSavedAt', String(Date.now()))
    },
  })

  cy.get('[data-testid="brief-upload-dropzone-0"]').should('be.visible')
}

const expectFilePickerActivation = (inputSelector, alias) => {
  cy.get(inputSelector).then(($input) => {
    const clickSpy = cy.spy().as(alias)
    $input[0].addEventListener('click', clickSpy)
  })
}

const assertDropzoneLayout = (selector) => {
  cy.get(selector)
    .should('have.css', 'display', 'flex')
    .and('have.css', 'flex-direction', 'column')
    .and('have.css', 'box-sizing', 'border-box')
    .and('have.css', 'min-height', '104px')
    .then(($dropzone) => {
      const rect = $dropzone[0].getBoundingClientRect()
      expect(rect.width).to.be.greaterThan(0)
      expect(rect.height).to.be.at.least(104)
      expect(rect.right).to.be.at.most(Cypress.config('viewportWidth') + 1)
    })
}

describe('实操 / 商稿 brief 上传 smoke', () => {
  beforeEach(() => {
    prepareAuthenticatedPage()
  })

  it('keeps the upload card centered, sized, and keyboard reachable at desktop and narrow widths', () => {
    cy.viewport(1536, 900)
    assertDropzoneLayout('[data-testid="brief-upload-dropzone-0"]')
    cy.get('[data-testid="brief-upload-dropzone-0"]')
      .should('have.attr', 'role', 'button')
      .should('have.attr', 'tabindex', '0')
      .focus()
      .should('be.focused')
    cy.screenshot('practical-brief-upload-desktop')

    cy.viewport(390, 844)
    assertDropzoneLayout('[data-testid="brief-upload-dropzone-0"]')
    cy.window().then((win) => {
      expect(win.document.documentElement.scrollWidth).to.be.at.most(win.innerWidth)
    })
    cy.screenshot('practical-brief-upload-mobile')
  })

  it('activates the native file input from both v-for upload cards and from Enter', () => {
    const firstDropzone = '[data-testid="brief-upload-dropzone-0"]'
    const firstInput = '[data-testid="brief-upload-input-0"]'

    expectFilePickerActivation(firstInput, 'firstPicker')
    cy.get(firstDropzone).click()
    cy.get('@firstPicker').should('have.been.calledOnce')

    expectFilePickerActivation(firstInput, 'keyboardPicker')
    cy.get(firstDropzone).focus().trigger('keydown', { key: 'Enter' })
    cy.get('@keyboardPicker').should('have.been.calledOnce')

    expectFilePickerActivation(firstInput, 'spacePicker')
    cy.get(firstDropzone).focus().trigger('keydown', { key: ' ', code: 'Space', keyCode: 32, which: 32 })
    cy.get('@spacePicker').should('have.been.calledOnce')

    cy.get('[data-testid="brief-add-source"]').click()
    const secondDropzone = '[data-testid="brief-upload-dropzone-1"]'
    const secondInput = '[data-testid="brief-upload-input-1"]'
    cy.get(secondDropzone).should('be.visible')
    expectFilePickerActivation(secondInput, 'secondPicker')
    cy.get(secondDropzone).click()
    cy.get('@secondPicker').should('have.been.calledOnce')
  })

  it('accepts a valid file, accepts drag/drop, and permits selecting the same file after removal', () => {
    const firstInput = '[data-testid="brief-upload-input-0"]'
    const firstDropzone = '[data-testid="brief-upload-dropzone-0"]'

    cy.get(firstDropzone)
      .trigger('dragover')
      .should('have.class', 'dropzone-active')
      .trigger('drop', { dataTransfer: { files: [] } })
      .should('not.have.class', 'dropzone-active')
    cy.get(firstDropzone)
      .trigger('dragover')
      .should('have.class', 'dropzone-active')
      .trigger('dragleave')
      .should('not.have.class', 'dropzone-active')

    cy.get(firstInput).selectFile(makeFile('repeat.txt'), { force: true })
    cy.contains('repeat.txt').should('be.visible')
    cy.contains('button', '移除').click()
    cy.get(firstInput).selectFile(makeFile('repeat.txt'), { force: true })
    cy.contains('repeat.txt').should('be.visible')

    cy.get('[data-testid="brief-add-source"]').click()
    cy.get('[data-testid="brief-upload-dropzone-1"]').selectFile(
      makeFile('dropped.md', '# 拖拽 brief'),
      { action: 'drag-drop' },
    )
    cy.contains('dropped.md').should('be.visible')
  })

  it('blocks unsupported and oversized files before upload requests are sent', () => {
    cy.intercept('POST', uploadEndpoint).as('unexpectedUpload')

    cy.get('[data-testid="brief-upload-input-0"]').selectFile(makeFile('brief.exe'), { force: true })
    cy.contains('仅支持 PDF、Word（DOCX）、TXT、MD 和图片（PNG/JPG/WebP）文件').should('be.visible')
    cy.get('[data-testid="brief-import"]').click()
    cy.get('@unexpectedUpload.all').should('have.length', 0)

    cy.get('[data-testid="brief-upload-input-0"]').selectFile({
      contents: Cypress.Buffer.alloc(20 * 1024 * 1024 + 1),
      fileName: 'too-large.txt',
      mimeType: 'text/plain',
      lastModified: Date.now(),
    }, { force: true })
    cy.contains('文件大小不能超过 20MB').should('be.visible')
    cy.get('[data-testid="brief-import"]').click()
    cy.get('@unexpectedUpload.all').should('have.length', 0)
  })

  // 回归:商单 brief 曾被前端 accept 框死只收文档,客户拖截图进不去。
  // 现在放开图片(后端 qwen-vl OCR),拖图片必须被接受并触发上传。
  it('accepts an image brief (screenshot) and sends it for upload', () => {
    cy.intercept('POST', uploadEndpoint, {
      statusCode: 200,
      body: { title: 'brief.png', raw_text: '图片里 OCR 出的 brief 文字' },
    }).as('imageUpload')
    cy.intercept('POST', summarizeEndpoint, {
      statusCode: 200,
      body: {
        product: '图片 brief 产品', brief: '图片要求', core_message: null,
        must_cover: [], banned: [], tone: null, cta: null, audience: null,
        publish: null, review_notes: null, notes: null,
      },
    }).as('imageSummarize')

    cy.get('[data-testid="brief-upload-input-0"]').selectFile({
      contents: Cypress.Buffer.from('fake-png-bytes'),
      fileName: 'brief.png',
      mimeType: 'image/png',
      lastModified: Date.now(),
    }, { force: true })
    cy.contains('brief.png').should('be.visible')
    cy.get('[data-testid="brief-import"]').click()
    cy.wait('@imageUpload')
    cy.wait('@imageSummarize')
    cy.get('[data-testid="brief-structured-card"]').should('be.visible')
  })

  it('sends multipart upload, retries a failed summary, and renders the parsed brief', () => {
    let summarizeAttempts = 0

    cy.intercept('POST', uploadEndpoint, (request) => {
      expect(request.headers['content-type']).to.include('multipart/form-data')
      request.reply({
        statusCode: 200,
        body: {
          title: 'brief.txt',
          raw_text: '这是待解析的商单 brief。',
        },
      })
    }).as('briefUpload')

    cy.intercept('POST', summarizeEndpoint, (request) => {
      summarizeAttempts += 1
      expect(request.body).to.deep.equal({
        raw_text: '这是待解析的商单 brief。',
        title: '',
      })
      if (summarizeAttempts === 1) {
        request.reply({ statusCode: 500, body: { detail: '总结服务暂时不可用' } })
        return
      }
      request.reply({
        statusCode: 200,
        body: {
          product: '回归测试产品',
          brief: '回归测试写作要求',
          core_message: '稳定上传',
          must_cover: ['文件选择器可用'],
          banned: [],
          tone: '清晰',
          cta: null,
          audience: null,
          publish: null,
          review_notes: null,
          notes: null,
        },
      })
    }).as('briefSummarize')

    cy.get('[data-testid="brief-upload-input-0"]').selectFile(makeFile(), { force: true })
    cy.get('[data-testid="brief-import"]').click()
    cy.wait('@briefUpload')
    cy.wait('@briefSummarize')
    cy.contains('总结服务暂时不可用').should('be.visible')

    cy.get('[data-testid="brief-import"]').click()
    cy.wait('@briefUpload')
    cy.wait('@briefSummarize')
    cy.get('[data-testid="brief-structured-card"]').should('be.visible')
    cy.contains('已解析商单 brief').should('be.visible')
    cy.get('[data-testid="practical-product-name"]').should('have.value', '回归测试产品')
  })

  it('shows an upload 400 error and retries the same source successfully', () => {
    let uploadAttempts = 0

    cy.intercept('POST', uploadEndpoint, (request) => {
      uploadAttempts += 1
      if (uploadAttempts === 1) {
        request.reply({ statusCode: 400, body: { detail: '文件内容无法解析' } })
        return
      }
      request.reply({
        statusCode: 200,
        body: { title: 'brief.txt', raw_text: '重试后的 brief 内容' },
      })
    }).as('briefUploadRetry')

    cy.intercept('POST', summarizeEndpoint, {
      statusCode: 200,
      body: {
        product: '上传重试产品',
        brief: '重试成功',
        core_message: null,
        must_cover: [],
        banned: [],
        tone: null,
        cta: null,
        audience: null,
        publish: null,
        review_notes: null,
        notes: null,
      },
    }).as('briefSummarizeRetry')

    cy.get('[data-testid="brief-upload-input-0"]').selectFile(makeFile(), { force: true })
    cy.get('[data-testid="brief-import"]').click()
    cy.wait('@briefUploadRetry')
    cy.contains('文件内容无法解析').should('be.visible')

    cy.get('[data-testid="brief-import"]').click()
    cy.wait('@briefUploadRetry')
    cy.wait('@briefSummarizeRetry')
    cy.get('[data-testid="brief-structured-card"]').should('be.visible')
    cy.get('[data-testid="practical-product-name"]').should('have.value', '上传重试产品')
  })
})
