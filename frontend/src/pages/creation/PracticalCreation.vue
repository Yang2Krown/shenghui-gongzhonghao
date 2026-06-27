<template>
  <div class="page-wrap">
    <!-- Hero + 步骤条 -->
    <div class="tool-hero">
      <div class="kicker"><el-icon :size="14"><MagicStick /></el-icon> 创作工具 · 实操 / 商稿</div>
      <h1 class="serif">输入一个产品，<span class="text-clay">AI 先调研，再带你写实操文</span></h1>
      <p class="desc">产品太新搜不到？AI 联网调研最新信息 → 你确认 → 选要演示的功能 → 生成实操脚本。截图你自己补，文字 AI 包了。</p>
      <div class="step-bar">
        <div v-for="(s, i) in stepLabels" :key="i" class="step-item" :class="{ active: stepIndex === i, done: stepIndex > i }">
          <div class="step-dot">{{ stepIndex > i ? '✓' : i + 1 }}</div>
          <span class="step-label">{{ s }}</span>
        </div>
      </div>
    </div>

    <!-- ① 填写表单 -->
    <div v-if="stage === 'form' && !progress.isRunning.value" class="fade-in">
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div>
              <div class="text-sm font-semibold text-ink">产品信息</div>
              <div class="text-xs text-ink-4">填写产品名和创作模板，AI 开始调研</div>
            </div>
          </div>
        </div>
        <div style="padding: 22px;">
          <div class="form-section">
            <label class="form-label">产品 / 工具名 <span class="req">*</span></label>
            <input class="input" v-model="form.product" type="text" placeholder="请输入产品名称">
          </div>
          <div class="form-section">
            <label class="form-label">商单 brief <span class="opt">选填</span></label>

            <!-- 未解析：直接显示导入面板 -->
            <template v-if="!structuredBrief">
              <div v-for="(source, index) in briefSources" :key="index" class="src-card slide-up">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 13px;">
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="src-number">{{ index + 1 }}</span>
                    <div class="seg">
                      <button v-for="kind in sourceKinds" :key="kind.key"
                        @click="source.kind = kind.key"
                        :class="['seg-btn', { 'seg-btn-active': source.kind === kind.key }]">
                        {{ kind.label }}
                      </button>
                    </div>
                  </div>
                  <button v-if="briefSources.length > 1" @click="briefSources.splice(index, 1)" class="btn-text text-ink-4" style="padding: 4px;">
                    <el-icon :size="15"><Delete /></el-icon>
                  </button>
                </div>

                <!-- 文本输入 -->
                <el-input v-if="source.kind === 'text'" v-model="source.text" type="textarea" :rows="4"
                  placeholder="粘贴商单要求：必提卖点、禁忌、调性、官网链接等" />

                <!-- 链接输入 -->
                <div v-else-if="source.kind === 'link'">
                  <div v-if="source.linkTitle" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                      <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                        <el-icon class="text-clay"><Link /></el-icon> {{ source.linkTitle }}
                      </span>
                      <button @click="source.linkTitle = ''; source.url = ''" class="btn-text text-sm">移除</button>
                    </div>
                  </div>
                  <div v-else style="position: relative;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <div style="flex: 1; position: relative;">
                        <el-icon :size="16" style="position: absolute; left: 13px; top: 13px; color: var(--ink-4); z-index: 1;"><Link /></el-icon>
                        <el-input v-model="source.url" placeholder="粘贴飞书文档/wiki 链接（需先在「设置」连接飞书）"
                          style="padding-left: 38px;" />
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 文件上传 -->
                <div v-else-if="source.kind === 'file'">
                  <div v-if="source.fileName" style="padding: 11px 14px; background: var(--bone); border-radius: var(--r-md);">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                      <span style="display: flex; align-items: center; gap: 9px;" class="text-sm text-ink-2">
                        <el-icon class="text-clay"><Document /></el-icon> {{ source.fileName }}
                      </span>
                      <button @click="source.fileName = ''; source.file = null" class="btn-text text-sm">移除</button>
                    </div>
                  </div>
                  <div v-else class="dropzone" @click="$refs['fileInput' + index]?.click()">
                    <el-icon :size="22" style="margin: 0 auto 6px;"><Upload /></el-icon>
                    <div class="text-sm font-medium">点击或拖拽上传 PDF / Word / TXT / MD</div>
                  </div>
                  <input :ref="'fileInput' + index" type="file" accept=".pdf,.docx,.txt,.md" style="display:none"
                    @change="(e) => handleSourceFile(source, e)" />
                </div>
              </div>

              <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px;">
                <button @click="addBriefSource" class="btn-ghost" style="border-style: dashed;">
                  <el-icon :size="15"><Plus /></el-icon> 添加 brief
                </button>
                <button class="btn-clay" style="padding: 8px 16px;" :disabled="briefLoading" @click="importBrief">
                  <template v-if="briefLoading">
                    <el-icon class="is-loading" :size="14"><Loading /></el-icon> 解析中...
                  </template>
                  <template v-else>
                    读取并解析
                  </template>
                </button>
              </div>
            </template>

            <!-- 已解析：结构化卡片 + 折叠的原文 -->
            <template v-else>
              <BriefStructuredCard :brief="structuredBrief">
                <template #actions>
                  <el-button text size="small" @click="clearBrief">清除</el-button>
                </template>
              </BriefStructuredCard>
              <div class="raw-toggle">
                <el-button text size="small" @click="showRawBrief = !showRawBrief">
                  {{ showRawBrief ? '收起' : '查看 / 编辑' }}写作要求原文（喂给 AI 研究）
                </el-button>
              </div>
              <textarea v-show="showRawBrief" class="input textarea" v-model="form.brief" rows="15" style="margin-top:6px; min-height:340px;"></textarea>
            </template>
          </div>
          <!-- 创作模板切换已隐藏，默认走「工具主线」（form.template = 'tool'） -->
        </div>
      </div>

      <!-- 参考文章链接（选填） -->
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: #EEF3EE; color: var(--leaf);">📎</div>
            <div>
              <div class="text-sm font-semibold text-ink">参考文章链接</div>
              <div class="text-xs text-ink-4">提供已写好的文章，AI 会学习其风格和结构</div>
            </div>
          </div>
        </div>
        <div style="padding: 22px;">
          <div v-for="(link, index) in form.referenceLinks" :key="index" class="src-card slide-up">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="ref-link-type">{{ getLinkType(link) }}</span>
              <input class="input" v-model="form.referenceLinks[index]"
                     placeholder="粘贴公众号/小红书/知乎文章链接"
                     style="flex: 1;" />
              <span v-if="link.trim() && initialLinkStatus[index]" class="link-status" :class="initialLinkStatus[index].type">
                {{ initialLinkStatus[index].icon }}
              </span>
              <button v-if="form.referenceLinks.length > 1"
                      @click="removeInitialLink(index)"
                      class="btn-text text-ink-4"
                      style="padding: 4px;">
                <el-icon :size="15"><Delete /></el-icon>
              </button>
            </div>
            <div v-if="link.trim() && initialLinkStatus[index]?.message" class="link-hint">
              {{ initialLinkStatus[index].message }}
            </div>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px;">
            <button @click="form.referenceLinks.push('')" class="btn-ghost" style="border-style: dashed;">
              <el-icon :size="16"><Plus /></el-icon> 添加链接
            </button>
            <button class="btn-clay" :disabled="!form.referenceLinks.some(l => l.trim())" @click="validateAllInitialLinks">
              识别链接
            </button>
          </div>
        </div>
      </div>
      <button class="cta-bar" style="margin-top: 20px;" :disabled="!form.product.trim()" @click="startResearch">
        开始研究 <CreditHint :cost="3" />
      </button>
    </div>

    <!-- 进度（研究 / 成稿 共用） -->
    <div v-if="progress.isRunning.value" class="fade-in" style="margin-top: 8px;">
      <AgentStatusBar v-for="(step, idx) in progress.steps.value" :key="idx"
        :agent-name="step.agent" :action="step.action" :avatar="step.avatar"
        :is-active="idx === progress.currentStepIndex.value"
        :show-progress="idx === progress.currentStepIndex.value"
        :percent="idx === progress.currentStepIndex.value ? progress.stepPercent.value : (idx < progress.currentStepIndex.value ? 100 : 0)"
        style="margin-bottom: 8px;" />
    </div>

    <div v-if="progress.error.value" class="card" style="padding: 16px; border: 1px solid var(--crimson);">
      <p class="text-sm" style="color: var(--crimson);">{{ progress.error.value }}</p>
    </div>

    <!-- ② 研究确认 + 选功能点（一屏） -->
    <div v-if="stage === 'review' && research && !progress.isRunning.value" class="fade-in">
      <div v-if="research.insufficient" class="info-banner">⚠️ <span>部分信息联网搜索不足，已尽量填写，可手动补充</span></div>

      <!-- 产品定位 -->
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: var(--clay-tint); color: var(--clay-deep);">🎯</div>
            <span class="text-sm font-semibold text-ink">产品定位</span>
          </div>
        </div>
        <div style="padding: 22px;">
          <textarea class="input textarea" v-model="research.positioning" rows="2"></textarea>
        </div>
      </div>

      <!-- 产品优势 -->
      <div class="card" v-if="research.advantages && research.advantages.length">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: #EEF3EE; color: var(--leaf);">🏆</div>
            <span class="text-sm font-semibold text-ink">产品优势</span>
            <span class="text-xs text-ink-4" style="margin-left: auto;">共 {{ research.advantages.length }} 条</span>
          </div>
        </div>
        <div style="padding: 22px;">
          <div class="adv-list">
            <div class="adv-item" v-for="(a, i) in research.advantages" :key="i">
              <span class="adv-num">{{ i + 1 }}</span><span class="adv-text">{{ a }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 参考资料 -->
      <div class="card" v-if="research.references && research.references.length">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: var(--sand-soft); color: var(--sand);">📄</div>
            <span class="text-sm font-semibold text-ink">参考资料</span>
            <span class="ref-count">{{ research.references.length }} 篇</span>
          </div>
        </div>
        <div class="ref-scroll-wrapper">
          <div class="ref-article-list">
            <div class="ref-article-row" v-for="(r, i) in research.references" :key="i">
              <span v-if="r.is_user_reference" class="ref-src-badge is-user-ref">⭐ 我的参考</span>
              <span v-else-if="r.source" class="ref-src-badge" :class="{ 'is-wechat': r.source === '公众号' }">{{ r.source }}</span>
              <span class="ref-article-title">{{ r.title || r.url }}</span>
              <a :href="r.url" target="_blank" class="btn-ref-visit">点击访问</a>
            </div>
          </div>
        </div>
      </div>

      <!-- 搜索建议（资料不足时显示） -->
      <div class="card" v-if="research.search_suggestions && (research.search_suggestions.missing?.length || research.search_suggestions.keywords?.length)">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: #FFF3E0; color: #FF9800;">💡</div>
            <div>
              <div class="text-sm font-semibold text-ink">搜索建议</div>
              <div class="text-xs text-ink-4">以下信息可能需要补充，建议搜索这些关键词</div>
            </div>
          </div>
        </div>
        <div style="padding: 22px;">
          <!-- 缺少什么 -->
          <div v-if="research.search_suggestions.missing?.length" style="margin-bottom: 16px;">
            <div class="text-xs font-semibold text-ink-3" style="margin-bottom: 8px;">当前资料缺少：</div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
              <span v-for="(item, i) in research.search_suggestions.missing" :key="i"
                    class="suggestion-tag missing">
                {{ item }}
              </span>
            </div>
          </div>

          <!-- 建议关键词 -->
          <div v-if="research.search_suggestions.keywords?.length" style="margin-bottom: 16px;">
            <div class="text-xs font-semibold text-ink-3" style="margin-bottom: 8px;">建议搜索关键词：</div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
              <span v-for="(keyword, i) in research.search_suggestions.keywords" :key="i"
                    class="suggestion-tag keyword"
                    @click="copyKeyword(keyword)">
                {{ keyword }}
              </span>
            </div>
          </div>

          <!-- 支持的平台提示 -->
          <div class="text-xs text-ink-4" style="margin-top: 8px;">
            💡 可在公众号、小红书、知乎搜索以上关键词，找到文章后粘贴链接
          </div>
        </div>
      </div>

      <!-- 补充参考链接（可选） -->
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: #EEF3EE; color: var(--leaf);">📎</div>
            <div>
              <div class="text-sm font-semibold text-ink">补充参考文章</div>
              <div class="text-xs text-ink-4">搜索结果不满意？添加更多参考链接重新分析</div>
            </div>
          </div>
        </div>
        <div style="padding: 22px;">
          <div v-for="(link, index) in additionalLinks" :key="index" class="src-card slide-up">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="ref-link-type">{{ getLinkType(link) }}</span>
              <input class="input" v-model="additionalLinks[index]"
                     placeholder="粘贴公众号/小红书/知乎文章链接"
                     style="flex: 1;" />
              <span v-if="link.trim() && linkStatus[index]" class="link-status" :class="linkStatus[index].type">
                {{ linkStatus[index].icon }}
              </span>
              <button v-if="additionalLinks.length > 1"
                      @click="removeAdditionalLink(index)"
                      class="btn-text text-ink-4"
                      style="padding: 4px;">
                <el-icon :size="15"><Delete /></el-icon>
              </button>
            </div>
            <div v-if="link.trim() && linkStatus[index]?.message" class="link-hint">
              {{ linkStatus[index].message }}
            </div>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px;">
            <button @click="additionalLinks.push('')" class="btn-ghost" style="border-style: dashed;">
              <el-icon :size="16"><Plus /></el-icon> 添加链接
            </button>
            <div style="display: flex; gap: 8px;">
              <button class="btn-ghost" :disabled="!additionalLinks.some(l => l.trim())" @click="validateAllAdditionalLinks">
                识别链接
              </button>
              <button class="btn-clay" :disabled="!additionalLinks.some(l => l.trim())" @click="reAnalyze">
                🔄 重新分析
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn-ghost" @click="stage = 'form'">← 重新研究</button>
        <button class="btn-clay" @click="confirmResearch">确认研究结果 →</button>
      </div>
    </div>

    <!-- ③ 选择功能点 -->
    <div v-if="stage === 'selectFeatures' && research && !progress.isRunning.value" class="fade-in">
      <!-- 选择实操段 -->
      <div class="card">
        <div class="panel-head">
          <div class="ph-left">
            <div class="panel-icon" style="background: var(--pine-soft); color: var(--pine);">✅</div>
            <div>
              <div class="text-sm font-semibold text-ink">选择实操段</div>
              <div class="text-xs text-ink-4">打勾的功能点会写进文章（需你自己实操 + 截图）</div>
            </div>
          </div>
          <span class="select-count">已选 {{ selected.length }} / {{ selectableFeatures.length }}</span>
        </div>
        <div style="padding: 22px;">
          <div class="feature-list">
            <div v-for="(f, i) in selectableFeatures" :key="i" class="feature-card" :class="{ selected: selected.includes(f.name) }" @click="toggleSelect(f.name)">
              <div class="feature-top">
                <div class="feature-check"><span class="check-empty"></span></div>
                <div class="feature-info">
                  <div class="feature-name">{{ f.name }}</div>
                  <div class="feature-desc" v-if="f.desc">{{ f.desc }}</div>
                </div>
                <span :class="f.recommend ? 'tag-recommend' : 'tag-skip'">{{ f.recommend ? '推荐' : '可选' }}</span>
              </div>
              <div class="feature-reason" v-if="f.reason">💡 {{ f.reason }}</div>
              <template v-if="f.steps && f.steps.length">
                <div class="feature-steps-toggle" @click.stop="toggleSteps(i)">{{ openSteps.has(i) ? '▼' : '▶' }} 查看 {{ f.steps.length }} 步操作</div>
                <ol class="feature-steps" v-show="openSteps.has(i)">
                  <li v-for="(s, j) in f.steps" :key="j">{{ s }}</li>
                </ol>
              </template>
            </div>
            <button class="add-feature-btn" @click="addFeature">+ 手动添加功能点</button>
          </div>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn-ghost" @click="stage = 'review'">← 重新确认</button>
        <button class="btn-clay" :disabled="!selected.length" @click="startDraft">生成实操脚本 <CreditHint :cost="10" /></button>
      </div>
    </div>

    <!-- ④ 成稿 -->
    <div v-if="stage === 'result' && draft && !progress.isRunning.value" class="fade-in">
      <div class="success-banner">
        <span style="font-size: 20px;">✅</span>
        <div>
          <div class="text-sm font-semibold">生成完成</div>
          <div class="text-xs text-ink-4">{{ draft.word_count }} 字 · 截图位请按段落自行补上</div>
        </div>
      </div>
      <div class="card result-card">
        <div class="result-header">
          <h2 class="serif text-ink" style="font-size: 22px; font-weight: 600; flex: 1; min-width: 0;">{{ draft.title }}</h2>
          <div class="result-actions">
            <button class="btn-ghost btn-sm" @click="copy(draft.text)">📋 复制全文</button>
            <button class="btn-clay btn-sm" @click="toEditor">🚀 公众号编辑器</button>
          </div>
        </div>
        <div class="article" v-html="renderedDraft"></div>
      </div>
      <div class="action-bar" style="justify-content: flex-end; gap: 10px;">
        <button class="btn-ghost" @click="stage = 'selectFeatures'">← 修改功能点</button>
        <button class="btn-ghost" @click="reset">↺ 再写一篇</button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, UploadFilled, Delete, Plus, Upload, Document, Link, Loading } from '@element-plus/icons-vue'
import { feishuBriefRead, feishuBriefUpload, feishuBriefSummarize } from '@/api/feishu'
import AgentStatusBar from '@/components/creation/AgentStatusBar.vue'
import BriefStructuredCard from '@/components/creation/BriefStructuredCard.vue'
import { useAgentProgress } from '@/composables/useAgentProgress'
import { publishToWechatEditor } from '@/utils/publishToEditor'
import api from '@/api/api'
import { marked } from 'marked'
import { useCreditStore } from '@/stores/credit'
import CreditHint from '@/components/credit/CreditHint.vue'

const router = useRouter()
const creditStore = useCreditStore()
const progress = useAgentProgress()

const stepLabels = ['产品信息', '研究确认', '选择功能点', '生成成稿']
const templates = [
  { key: 'tool', icon: '🔧', label: '工具主线', hint: '开头引入 + 实操指导 + 结尾升华，主线是工具' },
  { key: 'case', icon: '📖', label: '案例主线', hint: '核心是案例，工具只是其中一小部分' },
]

const stage = ref('form')          // form | review | selectFeatures | result
const form = ref({ product: '', brief: '', template: 'tool', referenceLinks: [''] })
const initialLinkStatus = ref({})  // 阶段1：参考链接状态
const additionalLinks = ref([''])  // 阶段2：补充参考链接
const linkStatus = ref({})         // 阶段2：补充链接状态

// brief 导入
const sourceKinds = [
  { key: 'file', label: '文件' },
  { key: 'link', label: '链接' },
  { key: 'text', label: '文本' },
]
const briefSources = ref([{ kind: 'file', text: '', url: '', file: null, fileName: '', linkTitle: '' }])
const briefLoading = ref(false)
const structuredBrief = ref(null)
const showRawBrief = ref(false)

const clearBrief = () => { structuredBrief.value = null; form.value.brief = ''; briefSources.value = [{ kind: 'file', text: '', url: '', file: null, fileName: '', linkTitle: '' }]; showRawBrief.value = false }

// 获取链接类型图标
const getLinkType = (url) => {
  if (!url) return '🔗'
  if (url.includes('mp.weixin.qq.com')) return '📗 公众号'
  if (url.includes('xiaohongshu.com') || url.includes('xhslink.com')) return '📕 小红书'
  if (url.includes('zhihu.com')) return '📘 知乎'
  if (url.includes('douyin.com') || url.includes('iesdouyin.com')) return '🎵 抖音'
  return '🔗 网页'
}

// 删除阶段1的链接
const removeInitialLink = (index) => {
  form.value.referenceLinks.splice(index, 1)
  const newStatus = {}
  Object.keys(initialLinkStatus.value).forEach(key => {
    const k = parseInt(key)
    if (k < index) newStatus[k] = initialLinkStatus.value[k]
    else if (k > index) newStatus[k - 1] = initialLinkStatus.value[k]
  })
  initialLinkStatus.value = newStatus
}

// 批量识别阶段1的链接（调用后端真正验证）
const validateAllInitialLinks = async () => {
  const links = form.value.referenceLinks.filter(l => l.trim())
  if (!links.length) { ElMessage.warning('请先添加参考链接'); return }

  form.value.referenceLinks.forEach((link, i) => {
    if (link.trim()) initialLinkStatus.value[i] = { type: 'loading', icon: '⏳', message: '正在验证链接...' }
  })

  let ok = 0, fail = 0
  for (let i = 0; i < form.value.referenceLinks.length; i++) {
    const url = form.value.referenceLinks[i]?.trim()
    if (!url) continue
    try {
      const res = await api.post('/practical/validate-link', { url }, { timeout: 15000 })
      const data = res?.data || res
      initialLinkStatus.value[i] = data.valid
        ? { type: 'success', icon: '✅', message: data.message }
        : { type: 'error', icon: '❌', message: data.message }
      data.valid ? ok++ : fail++
    } catch {
      initialLinkStatus.value[i] = { type: 'error', icon: '❌', message: '验证失败，请检查网络' }
      fail++
    }
  }
  if (ok && !fail) ElMessage.success(`✅ 全部识别成功！共 ${ok} 个有效链接`)
  else if (ok && fail) ElMessage.warning(`⚠️ ${ok} 个成功，${fail} 个失败`)
  else if (fail) ElMessage.error(`❌ ${fail} 个链接识别失败，请检查链接是否有效`)
}

// 删除阶段2的链接
const removeAdditionalLink = (index) => {
  additionalLinks.value.splice(index, 1)
  const newStatus = {}
  Object.keys(linkStatus.value).forEach(key => {
    const k = parseInt(key)
    if (k < index) newStatus[k] = linkStatus.value[k]
    else if (k > index) newStatus[k - 1] = linkStatus.value[k]
  })
  linkStatus.value = newStatus
}

// 批量识别阶段2的链接（调用后端真正验证）
const validateAllAdditionalLinks = async () => {
  const links = additionalLinks.value.filter(l => l.trim())
  if (!links.length) { ElMessage.warning('请先添加参考链接'); return }

  additionalLinks.value.forEach((link, i) => {
    if (link.trim()) linkStatus.value[i] = { type: 'loading', icon: '⏳', message: '正在验证链接...' }
  })

  let ok = 0, fail = 0
  for (let i = 0; i < additionalLinks.value.length; i++) {
    const url = additionalLinks.value[i]?.trim()
    if (!url) continue
    try {
      const res = await api.post('/practical/validate-link', { url }, { timeout: 15000 })
      const data = res?.data || res
      linkStatus.value[i] = data.valid
        ? { type: 'success', icon: '✅', message: data.message }
        : { type: 'error', icon: '❌', message: data.message }
      data.valid ? ok++ : fail++
    } catch {
      linkStatus.value[i] = { type: 'error', icon: '❌', message: '验证失败，请检查网络' }
      fail++
    }
  }
  if (ok && !fail) ElMessage.success(`✅ 全部识别成功！共 ${ok} 个有效链接`)
  else if (ok && fail) ElMessage.warning(`⚠️ ${ok} 个成功，${fail} 个失败`)
  else if (fail) ElMessage.error(`❌ ${fail} 个链接识别失败，请检查链接是否有效`)
}

const research = ref(null)
const selected = ref([])
const draft = ref(null)
const openSteps = ref(new Set())

const stepIndex = computed(() => ({ form: 0, review: 1, selectFeatures: 2, result: 3 }[stage.value]))
const templateHint = computed(() => templates.find(t => t.key === form.value.template)?.hint || '')
const selectableFeatures = computed(() => (research.value?.features || []).filter(f => f.name?.trim()))
const renderedDraft = computed(() => marked.parse(draft.value?.text || ''))

const toggleSelect = (name) => {
  const i = selected.value.indexOf(name)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(name)
}
const toggleSteps = (i) => {
  const s = openSteps.value
  s.has(i) ? s.delete(i) : s.add(i)
  openSteps.value = new Set(s)
}
const addFeature = () => {
  ElMessageBox.prompt('功能点名称', '手动添加功能点', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPlaceholder: '请输入功能点名称',
    inputValidator: (val) => val?.trim() ? true : '名称不能为空',
  }).then(({ value }) => {
    const name = value?.trim()
    if (name) {
      research.value.features.push({ name, desc: '', steps: [], recommend: true, reason: '手动添加' })
      selected.value.push(name)
    }
  }).catch(() => {})
}

const unwrap = (res) => (res && res.data !== undefined ? res.data : res)

const addBriefSource = () => {
  briefSources.value.push({ kind: 'file', text: '', url: '', file: null, fileName: '', linkTitle: '' })
}

const handleSourceFile = (source, e) => {
  const file = e.target.files?.[0]
  if (file) {
    source.file = file
    source.fileName = file.name
  }
}

// 把结构化 brief 拼成可读文本，喂进 research 的 brief
const composeBriefText = (sb) => {
  const parts = []
  if (sb.brief) parts.push(sb.brief)
  if (sb.core_message) parts.push(`【核心主张】${sb.core_message}`)
  if (sb.must_cover?.length) parts.push('【必须覆盖】\n' + sb.must_cover.map(x => '· ' + x).join('\n'))
  if (sb.banned?.length) parts.push('【禁忌/红线】\n' + sb.banned.map(x => '· ' + x).join('\n'))
  if (sb.tone) parts.push(`【调性】${sb.tone}`)
  if (sb.cta) parts.push(`【引导动作】${sb.cta}`)
  if (sb.audience) parts.push(`【目标读者】${sb.audience}`)
  if (sb.publish) parts.push(`【发布档期】${sb.publish}`)
  if (sb.notes) parts.push(`【其他】${sb.notes}`)
  return parts.join('\n\n')
}

// 直接对当前文本框里的内容做 AI 总结
const summarizeCurrent = async () => {
  const raw = form.value.brief.trim()
  if (!raw) return
  briefLoading.value = true
  try {
    const sb = unwrap(await feishuBriefSummarize(raw, ''))
    structuredBrief.value = sb
    if (!form.value.product.trim() && sb.product) form.value.product = sb.product
    form.value.brief = composeBriefText(sb)
    ElMessage.success('已结构化')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '总结失败')
  } finally {
    briefLoading.value = false
  }
}

const importBrief = async () => {
  briefLoading.value = true
  try {
    // 1) 取原文
    const parts = []
    for (const source of briefSources.value) {
      if (source.kind === 'text') {
        if (source.text?.trim()) parts.push(source.text.trim())
      } else if (source.kind === 'link') {
        if (source.url?.trim()) {
          const d = unwrap(await feishuBriefRead('feishu_link', source.url.trim()))
          if (d.raw_text) parts.push(d.raw_text)
        }
      } else if (source.kind === 'file') {
        if (source.file) {
          const d = unwrap(await feishuBriefUpload(source.file))
          if (d.raw_text) parts.push(d.raw_text)
        }
      }
    }
    const rawText = parts.join('\n\n---\n\n')
    if (!rawText.trim()) { ElMessage.warning('未读到内容'); return }

    // 2) 结构化总结
    const sb = unwrap(await feishuBriefSummarize(rawText, ''))
    structuredBrief.value = sb
    if (!form.value.product.trim() && sb.product) form.value.product = sb.product
    form.value.brief = composeBriefText(sb)
    ElMessage.success('brief 已导入并解析')
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message || '导入失败'
    ElMessage.error(typeof msg === 'string' ? msg : '导入失败')
  } finally {
    briefLoading.value = false
  }
}

const startResearch = async () => {
  if (!form.value.product.trim()) return
  progress.stop(); draft.value = null

  // 过滤空链接
  const referenceLinks = form.value.referenceLinks.filter(url => url.trim())

  try {
    const res = await api.post('/practical/research', {
      product: form.value.product.trim(),
      brief: form.value.brief.trim(),
      reference_links: referenceLinks,
    }, { timeout: 10000 })
    const runId = (res?.data || res)?.run_id
    if (runId) progress.start(`/api/v1/practical/stream/${runId}`)
    else progress.error.value = '未获取到任务 ID'
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

const startDraft = async () => {
  if (!selected.value.length) return
  progress.stop()
  stage.value = 'result'  // 切到第4步，让进度条显示正确
  try {
    const res = await api.post('/practical/draft', {
      research: research.value,
      selected: selected.value,
      template: form.value.template,
      brief_banned: structuredBrief.value?.banned || [],
      brief_tone: structuredBrief.value?.tone || null,
    }, { timeout: 10000 })
    const runId = (res?.data || res)?.run_id
    if (runId) progress.start(`/api/v1/practical/stream/${runId}`)
    else progress.error.value = '未获取到任务 ID'
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

// 补充参考链接后重新分析
const reAnalyze = async () => {
  const newLinks = additionalLinks.value.filter(url => url.trim())

  if (!newLinks.length) {
    ElMessage.warning('请先添加参考链接')
    return
  }

  // 检查链接格式
  const invalidLinks = newLinks.filter(url => !url.startsWith('http'))
  if (invalidLinks.length > 0) {
    ElMessage.warning('链接需要以 http:// 或 https:// 开头')
    return
  }

  progress.stop()
  linkStatus.value = {}  // 清空状态

  try {
    const res = await api.post('/practical/re-analyze', {
      product: research.value.product,
      brief: form.value.brief.trim(),
      existing_research: research.value,  // 上次的研究结果（可能被用户编辑过）
      new_reference_links: newLinks,
    }, { timeout: 10000 })

    const runId = (res?.data || res)?.run_id
    if (runId) {
      ElMessage.info(`正在抓取 ${newLinks.length} 个参考链接并重新分析...`)
      progress.start(`/api/v1/practical/stream/${runId}`)
    } else {
      progress.error.value = '未获取到任务 ID'
    }
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

// 确认研究结果，进入功能点分析
const confirmResearch = async () => {
  progress.stop()
  stage.value = 'selectFeatures'  // 先切换阶段，让进度条显示正确
  try {
    const res = await api.post('/practical/analyze-features', {
      research: research.value,  // 用户确认后的研究结果（可能被编辑过）
    }, { timeout: 10000 })

    const runId = (res?.data || res)?.run_id
    if (runId) progress.start(`/api/v1/practical/stream/${runId}`)
    else progress.error.value = '未获取到任务 ID'
  } catch (err) {
    progress.error.value = err?.response?.data?.detail || err.message || '请求失败'
  }
}

watch(() => progress.result.value, (data) => {
  if (!data) return

  // 研究结果（有 positioning 字段）
  if (data.positioning !== undefined) {
    research.value = data
    // 研究阶段可能没有 features，或 features 没有 steps
    if (data.features && data.features.length > 0 && data.features[0].steps) {
      // 功能点分析结果
      selected.value = data.features.filter(f => f.recommend && f.name).map(f => f.name)
      openSteps.value = new Set()
      stage.value = 'selectFeatures'
    } else {
      // 初始研究结果
      stage.value = 'review'
      additionalLinks.value = ['']
    }
    linkStatus.value = {}  // 清空链接状态
    creditStore.fetchBalance()
  } else if (typeof data.text === 'string') {  // 成稿结果
    draft.value = data
    stage.value = 'result'
    creditStore.fetchBalance()
  }
})

const copy = (text) => {
  navigator.clipboard?.writeText(text).then(() => ElMessage.success('已复制全文')).catch(() => ElMessage.error('复制失败'))
}

// 复制搜索关键词
const copyKeyword = (keyword) => {
  navigator.clipboard?.writeText(keyword).then(() => ElMessage.success(`已复制：${keyword}`)).catch(() => ElMessage.error('复制失败'))
}
const toEditor = async () => {
  await publishToWechatEditor(router, draft.value?.text || '', draft.value?.title || '')
}
const reset = () => {
  progress.stop()
  stage.value = 'form'
  form.value = { product: '', brief: '', template: 'tool', referenceLinks: [''] }
  initialLinkStatus.value = {}
  additionalLinks.value = ['']
  linkStatus.value = {}
  research.value = null; selected.value = []; draft.value = null
  structuredBrief.value = null
  openSteps.value = new Set()
}

onUnmounted(() => progress.stop())
</script>

<style scoped>
.page-wrap { max-width: 860px; margin: 0 auto; padding: 8px 0 64px; }
.raw-toggle { margin-top: 8px; }
.src-card {
  position: relative;
  border: 1.5px solid var(--line);
  border-radius: var(--r-md);
  padding: 18px 18px 18px 20px;
  margin-bottom: 12px;
  background: var(--paper);
  transition: border-color .18s, box-shadow .18s;
}
.src-card::before {
  content: '';
  position: absolute;
  top: 12px;
  left: 0;
  width: 3px;
  height: 0;
  background: var(--clay);
  border-radius: 0 3px 3px 0;
  transition: height .2s;
}
.src-card:focus-within { border-color: var(--clay-soft); box-shadow: var(--sh-2); }
.src-card:focus-within::before { height: calc(100% - 24px); }
.src-number { width: 26px; height: 26px; border-radius: 8px; background: var(--clay); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }
.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.dropzone { border: 1px dashed var(--line); border-radius: var(--r-lg); background: var(--paper); padding: 22px; text-align: center; cursor: pointer; transition: all .15s; color: var(--ink-3); }
.dropzone:hover { border-color: var(--clay); background: var(--clay-tint); color: var(--clay-deep); }
.btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: 1.5px solid var(--line); border-radius: var(--r-md); background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .18s; }
.btn-ghost:hover { border-color: var(--clay-soft); color: var(--clay-deep); background: var(--ivory); }
.btn-text { background: none; border: none; cursor: pointer; font-family: inherit; }
.btn-text:hover { color: var(--clay); }
.slide-up { animation: slideUp .3s cubic-bezier(.32,.72,0,1); }
@keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.serif { font-family: "Source Han Serif SC", "Songti SC", "Noto Serif SC", Georgia, serif; font-weight: 500; }
.ref-link-type {
  flex-shrink: 0;
  font-size: 13px;
  padding: 4px 10px;
  background: var(--bone);
  border-radius: var(--r-pill);
  white-space: nowrap;
}

.suggestion-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--r-pill);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.suggestion-tag.missing {
  background: #FFF3E0;
  color: #E65100;
  border: 1px solid #FFE0B2;
}

.suggestion-tag.keyword {
  background: var(--clay-tint);
  color: var(--clay-deep);
  border: 1px solid var(--clay-soft);
  cursor: pointer;
  transition: all .15s;
}

.suggestion-tag.keyword:hover {
  background: var(--clay);
  color: #fff;
}

.suggestion-tag.platform {
  background: #E3F2FD;
  color: #1565C0;
  border: 1px solid #BBDEFB;
}

.link-status {
  flex-shrink: 0;
  font-size: 14px;
}

.link-status.loading {
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.link-hint {
  margin-top: 6px;
  padding-left: 50px;
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.4;
}

.link-status.success + .link-hint { color: var(--leaf); }
.link-status.error + .link-hint { color: var(--crimson); }
.link-status.warning + .link-hint { color: #E65100; }
.link-status.info + .link-hint { color: #1565C0; }
.link-status.loading + .link-hint { color: var(--ink-4); }

.tool-hero { position: relative; margin-bottom: 26px; }
.tool-hero .kicker { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: var(--clay-deep); background: var(--clay-tint); border: 1px solid var(--clay-soft); padding: 5px 12px; border-radius: var(--r-pill); margin-bottom: 14px; }
.tool-hero h1 { font-size: 38px; line-height: 1.15; letter-spacing: -.01em; color: var(--ink); }
.tool-hero .desc { margin-top: 12px; font-size: 15px; color: var(--ink-3); line-height: 1.6; max-width: 620px; }

.step-bar { display: flex; align-items: center; margin-top: 24px; padding: 16px 24px; background: linear-gradient(135deg, rgba(204,120,92,.04), rgba(63,92,82,.04)); border: 1px solid rgba(204,120,92,.12); border-radius: 14px; }
.step-item { display: flex; align-items: center; gap: 10px; flex: 1; position: relative; }
.step-item:last-child { flex: 0 0 auto; }
.step-item:not(:last-child)::after { content: ''; flex: 1; height: 1px; background: linear-gradient(90deg, var(--clay-soft), rgba(204,120,92,.08)); margin: 0 14px; }
.step-item.done:not(:last-child)::after { background: linear-gradient(90deg, var(--clay), var(--clay-soft)); }
.step-dot { width: 30px; height: 30px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; background: var(--bone); color: var(--ink-4); border: 1.5px solid var(--line); flex-shrink: 0; transition: all .3s; }
.step-label { font-size: 13px; font-weight: 500; color: var(--ink-4); white-space: nowrap; transition: color .3s; }
.step-item.done .step-dot { background: var(--clay); color: #fff; border-color: var(--clay); box-shadow: 0 2px 8px rgba(204,120,92,.2); }
.step-item.done .step-label { color: var(--clay-deep); font-weight: 600; }
.step-item.active .step-dot { background: #fff; color: var(--clay-deep); border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,.12), 0 2px 8px rgba(204,120,92,.15); }
.step-item.active .step-label { color: var(--ink); font-weight: 600; }

.card { background: var(--paper); border-radius: var(--r-lg); box-shadow: var(--sh-1); overflow: hidden; margin-bottom: 16px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 24px; border-bottom: 1px solid var(--line); }
.ph-left { display: flex; align-items: center; gap: 11px; flex: 1; }
.panel-icon { width: 32px; height: 32px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 17px; }

.text-sm { font-size: 13px; } .text-xs { font-size: 12px; } .font-semibold { font-weight: 600; }
.text-ink { color: var(--ink); } .text-ink-3 { color: var(--ink-3); } .text-ink-4 { color: var(--ink-4); } .text-clay { color: var(--clay); }

.seg { display: inline-flex; gap: 2px; padding: 3px; background: var(--bone); border-radius: var(--r-pill); }
.seg-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border: none; background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; border-radius: var(--r-pill); cursor: pointer; transition: all .18s; }
.seg-btn:hover { color: var(--ink); }
.seg-btn-active { background: var(--paper); color: var(--clay-deep); box-shadow: var(--sh-1); }
.template-hint { margin-top: 10px; font-size: 13px; color: var(--ink-4); line-height: 1.5; }

.form-section { margin-bottom: 22px; }
.form-section:last-of-type { margin-bottom: 0; }
.form-label { display: block; font-size: 13px; font-weight: 600; color: var(--ink-2); margin-bottom: 8px; }
.req { color: var(--crimson); } .opt { font-weight: 400; color: var(--ink-4); }
.input { width: 100%; padding: 10px 14px; border: 1.5px solid var(--line); border-radius: var(--r-md); background: var(--paper); font-family: inherit; font-size: 14px; color: var(--ink); outline: none; transition: border-color .18s, box-shadow .18s; }
.input:hover { border-color: var(--clay-soft); }
.input:focus { border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,.12); }
.textarea { resize: vertical; min-height: 72px; line-height: 1.6; }

.info-banner { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-radius: var(--r-md); background: var(--sand-soft); color: var(--sand); font-size: 13px; font-weight: 500; margin-bottom: 16px; }

.ref-count { margin-left: auto; font-size: 11px; font-weight: 600; color: var(--clay-deep); background: var(--clay-tint); padding: 2px 8px; border-radius: var(--r-pill); }
.ref-scroll-wrapper {
  max-height: 180px;
  overflow-y: auto;
  padding: 0 22px 16px;
}
.ref-scroll-wrapper::-webkit-scrollbar { width: 4px; }
.ref-scroll-wrapper::-webkit-scrollbar-track { background: transparent; }
.ref-scroll-wrapper::-webkit-scrollbar-thumb { background: var(--line); border-radius: 4px; }
.ref-scroll-wrapper::-webkit-scrollbar-thumb:hover { background: var(--ink-4); }
.ref-article-list { display: flex; flex-direction: column; }
.ref-article-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--line); }
.ref-article-row:last-child { border-bottom: none; }
.ref-src-badge { flex-shrink: 0; margin-right: 8px; font-size: 11px; font-weight: 500; color: var(--ink-4); background: var(--line); padding: 2px 7px; border-radius: 5px; white-space: nowrap; }
.ref-src-badge.is-wechat { color: #07803a; background: rgba(7, 193, 96, 0.12); }
.ref-src-badge.is-user-ref { color: #07803a; background: rgba(7, 193, 96, 0.2); font-weight: 600; }
.ref-article-title { font-size: 13px; color: var(--ink-2); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-ref-visit { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 500; color: var(--clay-deep); text-decoration: none; white-space: nowrap; margin-left: 12px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line); transition: all .15s; }
.btn-ref-visit:hover { background: var(--clay-tint); border-color: var(--clay); color: var(--clay); }

.select-count { font-size: 12px; font-weight: 600; color: var(--clay-deep); background: var(--clay-tint); padding: 4px 10px; border-radius: var(--r-pill); white-space: nowrap; }

.adv-list { display: flex; flex-direction: column; gap: 10px; }
.adv-item { display: flex; align-items: flex-start; gap: 10px; }
.adv-num { flex-shrink: 0; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-size: 12px; font-weight: 600; background: var(--clay-tint); color: var(--clay-deep); border: 1px solid rgba(204,120,92,.18); }
.adv-text { font-size: 14px; color: var(--ink); line-height: 22px; padding-top: 1px; }

.feature-list { display: flex; flex-direction: column; gap: 10px; }
.feature-card { border: 1.5px solid var(--line); border-radius: var(--r-md); padding: 14px 16px; cursor: pointer; transition: all .18s; background: var(--paper); }
.feature-card:hover { border-color: var(--clay-soft); background: var(--ivory); }
.feature-card.selected { border-color: var(--clay); background: var(--clay-tint); }
.feature-top { display: flex; align-items: flex-start; gap: 10px; }
.feature-check { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
.check-empty { width: 18px; height: 18px; border-radius: 4px; border: 1.5px solid var(--line); display: block; }
.feature-card.selected .check-empty { border-color: var(--clay); background: var(--clay); position: relative; }
.feature-card.selected .check-empty::after { content: '✓'; color: #fff; font-size: 11px; font-weight: 700; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }
.feature-info { flex: 1; min-width: 0; }
.feature-name { font-size: 14px; font-weight: 600; color: var(--ink); line-height: 1.4; }
.feature-desc { font-size: 12px; color: var(--ink-3); margin-top: 2px; line-height: 1.5; }
.feature-reason { font-size: 12px; color: var(--ink-4); margin-top: 8px; padding-left: 32px; line-height: 1.5; }
.feature-steps-toggle { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--clay-deep); margin-top: 8px; padding-left: 32px; cursor: pointer; }
.feature-steps-toggle:hover { color: var(--clay); }
.feature-steps { margin: 8px 0 0 32px; padding-left: 16px; }
.feature-steps li { font-size: 12px; color: var(--ink-3); line-height: 1.7; margin-bottom: 2px; }
.tag-recommend { font-size: 11px; padding: 2px 8px; border-radius: var(--r-pill); background: #EEF3EE; color: var(--leaf); white-space: nowrap; flex-shrink: 0; font-weight: 600; }
.tag-skip { font-size: 11px; padding: 2px 8px; border-radius: var(--r-pill); background: var(--bone); color: var(--ink-4); white-space: nowrap; flex-shrink: 0; }
.add-feature-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px; border: 1.5px dashed var(--line); border-radius: var(--r-md); background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; cursor: pointer; transition: all .15s; }
.add-feature-btn:hover { border-color: var(--clay-soft); color: var(--clay-deep); background: var(--ivory); }

.action-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 24px; }

.cta-bar { position: relative; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 9px; font-family: inherit; font-weight: 600; font-size: 16px; color: #fff; cursor: pointer; border: none; border-radius: var(--r-lg); padding: 16px 24px; background: linear-gradient(135deg, var(--clay) 0%, var(--clay-deep) 100%); box-shadow: 0 10px 28px rgba(204,120,92,.30); transition: all .2s; }
.cta-bar:hover:not([disabled]) { transform: translateY(-2px); box-shadow: 0 16px 38px rgba(204,120,92,.38); }
.cta-bar[disabled] { background: var(--bone); color: var(--ink-4); box-shadow: none; cursor: not-allowed; transform: none; }

.btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: 1.5px solid var(--line); border-radius: var(--r-md); background: transparent; color: var(--ink-3); font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .18s; }
.btn-ghost:hover { border-color: var(--clay-soft); color: var(--clay-deep); background: var(--ivory); }
.btn-clay { display: inline-flex; align-items: center; gap: 6px; padding: 8px 20px; border: none; border-radius: var(--r-md); background: var(--clay); color: #fff; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .18s; }
.btn-clay:hover:not([disabled]) { background: var(--clay-deep); }
.btn-clay[disabled] { background: var(--bone); color: var(--ink-4); cursor: not-allowed; }
.btn-sm { padding: 6px 12px; font-size: 12px; }

.success-banner { display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-radius: var(--r-md); background: #EEF3EE; color: var(--leaf); margin-bottom: 18px; }
.result-card { padding: 0; }
.result-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; border-bottom: 1px solid var(--line); gap: 16px; }
.result-actions { display: flex; gap: 8px; flex-shrink: 0; }
.article { font-size: 15px; line-height: 1.85; color: var(--ink); background: var(--ivory); padding: 24px 28px; max-height: 520px; overflow: auto; }
.article :deep(h1), .article :deep(h2), .article :deep(h3) { font-family: "Source Han Serif SC", serif; color: var(--ink); margin: 18px 0 10px; line-height: 1.3; font-weight: 600; }
.article :deep(h2) { font-size: 19px; } .article :deep(h3) { font-size: 16px; }
.article :deep(p) { margin: 10px 0; }
.article :deep(ul), .article :deep(ol) { margin: 10px 0; padding-left: 24px; }
.article :deep(li) { margin: 4px 0; }
.article :deep(strong) { color: var(--clay-deep); }

.fade-in { animation: fadeIn .32s cubic-bezier(.32,.72,0,1); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
