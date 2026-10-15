<!--
  文件级注释：PA-03 知识库条目编辑与版本回滚页（Stitch 高保真形态，路由 /admin/kb/:id，id='new' 为新建）
  - 双栏工作台：左栏编辑区（条目头卡 / 元数据卡 / Markdown 编辑卡 / 发布前合规与模式校验卡 / 变更说明卡），
    右栏追溯面板（并发锁卡 / 版本历史时间线 + 回滚区 / 质控刻度卡）
  - Markdown 工具栏对原生 textarea 做包裹/行首语法插入（最小实现）；预览沿用转义 + 有限渲染（防 XSS，不引 md 库）
  - 发布前合规校验：调用 /admin/lexicon/test 展示敏感词检测行与医疗/兽药模式命中卡
    （改写 / 删除 / 标记为专家复核三处置动作），后端 submit 返回的 warnings 一并展示
  - 版本历史内嵌右栏时间线（当前版本徽章 + 对比差异占位；版本号取审计聚合行的
    after_version 归一化，操作人取 operator_role，摘要取 reason）；回滚弹窗（目标版本
    + 必填原因 + 二次确认 + confirm_token，携带 version 乐观锁）
  - 元数据卡字段对齐后端 KbCreateBody 必填约束（kb_kind/domain/topic_key/topic_category/
    preconditions/source_type/source_ref），保存前逐项校验并明确提示（含适用月龄必选）
  - 保存返回 409（code=1003/1601）时提示"内容已被更新，请刷新"（乐观锁 version）
-->
<template>
  <div class="kb-edit-page">
    <div class="edit-grid">
      <!-- ══════════ 左栏：编辑区 ══════════ -->
      <section class="col-main">
        <!-- 1. 条目头卡：KB 编号 chip + 标题 + 状态标签 + 顶级动作 -->
        <section class="st-card head-card">
          <div class="head-left">
            <span class="kb-chip numeric">{{ isNew ? 'KB-NEW' : kbId }}</span>
            <el-input
              v-model="form.title"
              class="title-input"
              placeholder="条目标题"
              maxlength="60"
              show-word-limit
            />
            <span v-if="!isNew" class="st-tag" :class="statusTagClass(status)">{{ statusLabel(status) }}</span>
          </div>
          <div class="head-actions">
            <el-button :loading="saving" @click="handleSave">保存草稿</el-button>
            <el-button type="primary" :loading="saving" @click="handleSubmit">
              <el-icon class="btn-ico"><CircleCheck /></el-icon>提交审核
            </el-button>
          </div>
        </section>

        <!-- 2. 元数据卡：条目类型 / 领域 / 月龄 / 类目 / 主题键 / 宠物类型 + 来源溯源 + 适用前提 + 条目标签 chips
             （对齐后端 KbCreateBody 必填约束：domain/topic_key/topic_category/preconditions/source_type/source_ref） -->
        <section class="st-card meta-card">
          <div class="meta-grid">
            <div class="meta-field">
              <label>条目类型</label>
              <el-select v-model="form.kb_kind" placeholder="选择类型" style="width: 100%">
                <el-option label="育儿知识" value="child" />
                <el-option label="宠物知识" value="pet" />
                <el-option label="测评题库" value="assessment_pool" />
                <el-option label="风险词库" value="risk_lexicon" />
                <el-option label="敏感词库" value="sensitive_lexicon" />
              </el-select>
            </div>
            <div class="meta-field">
              <label>领域归属</label>
              <el-select v-model="form.domain" placeholder="选择领域" style="width: 100%">
                <el-option label="育儿（child）" value="child" />
                <el-option label="宠物（pet）" value="pet" />
              </el-select>
            </div>
            <div class="meta-field">
              <label>适用月龄</label>
              <el-select v-model="form.age_range" placeholder="选择月龄段" clearable style="width: 100%">
                <el-option label="0-6 月" value="0-6m" />
                <el-option label="6-12 月" value="6-12m" />
                <el-option label="12-36 月" value="12-36m" />
                <el-option label="3-6 岁" value="3-6y" />
              </el-select>
            </div>
            <div class="meta-field">
              <label>主题类目</label>
              <el-select
                v-model="form.topic_category"
                placeholder="选择或输入类目"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option v-for="c in TOPIC_CATEGORIES" :key="c" :label="c" :value="c" />
              </el-select>
            </div>
            <div class="meta-field">
              <label>主题键</label>
              <el-input v-model="form.topic_key" placeholder="如 sleep_training" maxlength="64" />
            </div>
            <div class="meta-field">
              <label>宠物类型</label>
              <el-select v-model="form.pet_type" :disabled="form.kb_kind !== 'pet'" style="width: 100%">
                <template v-if="form.kb_kind === 'pet'">
                  <el-option label="猫" value="cat" />
                  <el-option label="狗" value="dog" />
                  <el-option label="通用" value="general" />
                </template>
                <el-option v-else label="--" value="general" />
              </el-select>
            </div>
          </div>
          <!-- 来源溯源行（source_type/source_ref 后端必填，可溯源） -->
          <div class="meta-grid source-grid">
            <div class="meta-field">
              <label>来源类型</label>
              <el-select v-model="form.source_type" placeholder="选择来源类型" style="width: 100%">
                <el-option label="专家原创" value="expert_original" />
                <el-option label="文献改写" value="literature_rewrite" />
                <el-option label="内部整理" value="internal" />
              </el-select>
            </div>
            <div class="meta-field">
              <label>来源引用</label>
              <el-input
                v-model="form.source_ref"
                placeholder="如 DOI / URL / 内部文档编号（必填，可溯源）"
                maxlength="256"
              />
            </div>
          </div>
          <!-- 适用前提（后端一票否决项，必填） -->
          <div class="meta-field precond-field">
            <label>
              适用前提
              <span class="req">*</span>
              <span class="field-hint">（必填：一票否决项，如“适用于 12-36 月龄、无发热症状”）</span>
            </label>
            <el-input
              v-model="form.preconditions"
              type="textarea"
              :rows="2"
              placeholder="请输入该条目的适用前提条件（必填）"
            />
          </div>
          <!-- 标签行：chips + 添加标签（保留原输入逻辑） -->
          <div class="tags-row">
            <span class="tags-label">条目标签：</span>
            <span v-for="tag in form.tags" :key="tag" class="tag-chip">
              {{ tag }}
              <el-icon class="tag-x" @click="removeTag(tag)"><Close /></el-icon>
            </span>
            <el-input
              v-if="tagInputVisible"
              ref="tagInputRef"
              v-model="tagInputValue"
              class="tag-input"
              size="small"
              @keyup.enter="confirmTag"
              @blur="confirmTag"
            />
            <button v-else type="button" class="tag-add" @click="showTagInput">
              <el-icon><Plus /></el-icon>添加标签
            </button>
          </div>
        </section>

        <!-- 3. Markdown 编辑卡：工具栏行（包裹/行首语法插入）+ 字数统计 + 预览切换 -->
        <section class="st-card md-card">
          <div class="md-toolbar">
            <div class="md-tools">
              <button type="button" class="md-btn" title="加粗" @click="insertWrap('**')"><b>B</b></button>
              <button type="button" class="md-btn" title="斜体" @click="insertWrap('*')"><i>I</i></button>
              <button type="button" class="md-btn" title="一级标题" @click="insertLinePrefix('# ')">H1</button>
              <button type="button" class="md-btn" title="二级标题" @click="insertLinePrefix('## ')">H2</button>
              <span class="md-sep"></span>
              <button type="button" class="md-btn" title="有序列表" @click="insertLinePrefix('1. ')">1.</button>
              <button type="button" class="md-btn" title="无序列表" @click="insertLinePrefix('- ')">•</button>
              <button type="button" class="md-btn" title="引用" @click="insertLinePrefix('> ')">"</button>
              <button type="button" class="md-btn" title="代码" @click="insertWrap('`')">&lt;&gt;</button>
            </div>
            <div class="md-right">
              <span class="word-count numeric">字数: {{ form.content.length }}</span>
              <button type="button" class="mode-btn" @click="mode = mode === 'edit' ? 'preview' : 'edit'">
                {{ mode === 'edit' ? 'Markdown 预览' : '返回编辑' }}
              </button>
            </div>
          </div>
          <!-- 编辑态：原生 textarea（工具栏直接操作光标选区） -->
          <textarea
            v-if="mode === 'edit'"
            ref="contentRef"
            v-model="form.content"
            class="md-textarea"
            rows="14"
            placeholder="请输入知识库正文 Markdown 内容..."
          ></textarea>
          <!-- 预览态：内容先经 escapeHtml 再做有限语法替换，避免 XSS -->
          <div v-else class="md-preview" v-html="previewHtml"></div>
        </section>

        <!-- 4. 发布前合规与模式校验卡 -->
        <section class="st-card check-card">
          <div class="sec-head-row">
            <div class="st-section-head">发布前合规与模式校验</div>
            <el-button size="small" :loading="checking" @click="runCheck">运行校验</el-button>
          </div>
          <!-- 后端 submit 返回的 warnings -->
          <el-alert
            v-for="(w, i) in warnings"
            :key="'w' + i"
            :title="typeof w === 'string' ? w : w.message || JSON.stringify(w)"
            type="warning"
            :closable="false"
          />
          <!-- ① 敏感词检测行 -->
          <div class="check-line" :class="termState">
            <div class="cl-left">
              <el-icon v-if="checkResult" :class="termState === 'ok' ? 'ico-ok' : 'ico-bad'">
                <CircleCheck />
              </el-icon>
              <span>敏感词检测</span>
              <span class="cl-sub">— {{ termResultText }}</span>
            </div>
            <span class="cl-badge" :class="termState === 'ok' ? 'badge-ok' : 'badge-bad'">
              {{ termState === 'ok' ? '验证通过' : '检测未通过' }}
            </span>
          </div>
          <!-- 命中敏感词列表 -->
          <div v-if="checkResult?.matched_terms?.length" class="hit-chips">
            <code v-for="t in checkResult.matched_terms" :key="t" class="hit-code">{{ t }}</code>
          </div>
          <!-- ② 医疗/兽药模式规则：命中 → 黄色命中卡 + 三处置动作；未命中 → 验证通过行 -->
          <div v-if="patternCount > 0" class="pattern-card">
            <div class="pc-head">
              <div class="pc-title">
                <el-icon class="ico-warn"><WarningFilled /></el-icon>
                <span>医疗/兽药模式规则</span>
                <span class="pc-sub">— !! {{ patternCount }} 命中</span>
              </div>
              <span v-if="!expertReviewed" class="pc-flag">触发处方合规拦截</span>
              <span v-else class="st-tag st-tag--amber">已标记专家复核</span>
            </div>
            <div class="pc-hit">
              <span class="pc-hint">命中片段：</span>
              <code v-for="p in checkResult!.matched_patterns" :key="p" class="hit-code">{{ p }}</code>
              <span class="pc-hint">(严禁在通用知识中提供剂量指示)</span>
              <div class="pc-actions">
                <button type="button" class="act-btn rewrite" @click="rewriteHit">改写</button>
                <button type="button" class="act-btn del" @click="deleteHit">删除</button>
                <button type="button" class="act-btn review" @click="markExpertReview">标记为专家复核</button>
              </div>
            </div>
          </div>
          <div v-else-if="checkResult" class="check-line ok">
            <div class="cl-left">
              <el-icon class="ico-ok"><CircleCheck /></el-icon>
              <span>医疗/兽药模式规则</span>
              <span class="cl-sub">— OK 通过 0 命中</span>
            </div>
            <span class="cl-badge badge-ok">验证通过</span>
          </div>
          <div v-else class="check-line">
            <div class="cl-left">
              <span>医疗/兽药模式规则</span>
              <span class="cl-sub">— 待运行：点击右上角「运行校验」对当前正文执行敏感词与模式规则检测</span>
            </div>
          </div>
          <p v-if="checkResult?.hit" class="check-tip">命中风险规则：改写 / 删除命中片段 / 标记为专家复核（CG14）后才能提交审核。</p>
        </section>

        <!-- 5. 变更说明卡（必填） -->
        <section class="st-card note-card">
          <label class="note-label">
            <span>变更说明</span>
            <span class="req">*</span>
            <span class="note-hint">(必填，用于版本审计追踪)</span>
          </label>
          <el-input
            v-model="form.change_note"
            type="textarea"
            :rows="3"
            placeholder="变更说明（必填）：请输入本次版本修改核心摘要，说明优化背景与排查步骤更新依据..."
          />
        </section>
      </section>

      <!-- ══════════ 右栏：版本追溯面板 ══════════ -->
      <aside class="col-side">
        <!-- 6. 并发锁正常卡（当前编辑人取真实登录账号信息） -->
        <section class="st-card lock-card">
          <span class="lock-dot"></span>
          <div class="lock-text">
            <p class="lt-main">并发锁正常</p>
            <p class="lt-sub">当前由 <span class="lt-name">{{ adminName }}</span> 独占编辑</p>
          </div>
          <el-icon class="lock-ico"><Lock /></el-icon>
        </section>

        <!-- 7. 版本历史与内容追溯卡（时间线 + 当前版本徽章 + 对比差异占位） -->
        <section v-if="!isNew" class="st-card ver-card" v-loading="versionsLoading">
          <div class="sec-head-row">
            <div class="st-section-head">版本历史与内容追溯</div>
            <span class="numeric ver-count">{{ versions.length }} 个版本存档</span>
          </div>
          <div class="ver-list">
            <div
              v-for="v in sortedVersions"
              :key="v.version"
              class="ver-item"
              :class="{ current: v.version === form.version }"
            >
              <div class="ver-head">
                <span class="ver-no numeric">v{{ v.version }}</span>
                <span v-if="v.version === form.version" class="cur-badge">当前版本</span>
                <button v-else type="button" class="diff-link" @click="diffVersion(v)">对比差异</button>
              </div>
              <div class="ver-meta">
                <span class="ver-op">{{ fmtVerOp(v) }}</span>
                <span>·</span>
                <span class="numeric">{{ fmtVerTime(v) }}</span>
              </div>
              <p class="ver-note">{{ fmtVerNote(v) }}</p>
            </div>
            <el-empty v-if="!versionsLoading && versions.length === 0" description="暂无版本记录" :image-size="64" />
          </div>
          <!-- 高敏感版本更替（回滚区） -->
          <div class="rollback-zone">
            <div class="rz-head">
              <span class="rz-title"><el-icon><RefreshLeft /></el-icon>高敏感版本更替</span>
              <span class="rz-side">需二级审计</span>
            </div>
            <button
              type="button"
              class="rollback-btn"
              :disabled="!rollbackTarget || saving"
              @click="rollbackTarget && openRollback(rollbackTarget)"
            >
              <el-icon><RefreshLeft /></el-icon>
              回滚到 v{{ rollbackTarget ?? '--' }}
            </button>
            <div class="st-note warn-note">
              <el-icon class="note-ico"><WarningFilled /></el-icon>
              <div>回滚后触发内容追溯处置；历史问答不重写正文，仅追加提示</div>
            </div>
          </div>
        </section>

        <!-- 8. 质控刻度参考卡（仅在条目存在真实审核评分时展示，无演示数字） -->
        <section v-if="entryScore !== null" class="st-card qc-card">
          <h4 class="qc-title">质控标尺参考度量</h4>
          <div class="qc-row">
            <span>审核质量评分</span>
            <span class="qc-val numeric">{{ entryScore }} 分</span>
          </div>
          <div class="st-meter">
            <div class="st-meter__fill" :style="{ width: Math.min(entryScore, 100) + '%' }"></div>
          </div>
        </section>
      </aside>
    </div>

    <!-- 回滚弹窗：输目标版本 + 必填原因 + 二次确认 -->
    <el-dialog v-model="rollbackVisible" title="版本回滚" width="440px">
      <el-alert type="warning" :closable="false" title="回滚将触发内容追溯处置；历史问答与报告不重写正文，仅追加提示（A11）" class="dialog-alert" />
      <el-form label-width="90px" style="margin-top: 12px">
        <el-form-item label="目标版本" required>
          <el-input-number v-model="rollbackForm.target_version" :min="1" :max="form.version - 1 || 1" />
        </el-form-item>
        <el-form-item label="回滚原因" required>
          <el-input v-model="rollbackForm.reason" type="textarea" :rows="3" placeholder="必填：说明回滚原因，将写入审计日志" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rollbackVisible = false">取消</el-button>
        <el-button type="danger" plain :loading="saving" @click="confirmRollback">确认回滚</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。编辑/新建条目（乐观锁保存），发布前合规校验，右栏版本时间线与回滚。
 */
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, Close, Lock, Plus, RefreshLeft, WarningFilled } from '@element-plus/icons-vue'
import { adminApi, ApiError, CONFIRM_TOKEN, getAdminInfo } from '../../api/admin'

const route = useRoute()
const router = useRouter()

/** 编辑模式：edit=编辑 / preview=预览 */
const mode = ref<'edit' | 'preview'>('edit')
/** 保存中标志 */
const saving = ref(false)
/** 校验中标志 */
const checking = ref(false)
/** 后端返回的发布前校验 warnings */
const warnings = ref<any[]>([])
/** 本地规则测试结果（hit/matched_terms/matched_patterns） */
const checkResult = ref<any>(null)
/** 是否已标记为专家复核（模式命中后的处置动作之一） */
const expertReviewed = ref(false)
/** 条目当前状态（从详情带入，头卡状态标签展示） */
const status = ref('draft')
/** 条目审核质量评分（有真实 score 才展示质控刻度卡，无演示数字） */
const entryScore = ref<number | null>(null)

/** 状态枚举 → 中文标签映射 */
const STATUS_LABELS: Record<string, string> = {
  draft: '草稿状态',
  pending_review: '待审核',
  published: '已发布状态',
  rejected: '已驳回',
  unpublished: '已下架',
}

/**
 * 函数级注释：状态枚举 → 中文标签
 * @param s 条目状态枚举
 * @returns 状态中文名（未知值原样返回）
 */
function statusLabel(s: string): string {
  return STATUS_LABELS[s] || s
}

/**
 * 函数级注释：状态枚举 → st-tag 变体类
 * @param s 条目状态枚举
 * @returns st-tag 修饰类名
 */
function statusTagClass(s: string): string {
  const map: Record<string, string> = {
    draft: 'st-tag--outline',
    pending_review: 'st-tag--amber',
    published: 'st-tag--green',
    rejected: 'st-tag--red',
    unpublished: 'st-tag--gray',
  }
  return map[s] || 'st-tag--gray'
}

/**
 * 函数级注释：解析路由中的条目 ID（兼容 id/kb_id 两种参数名；'new' 表示新建）
 * @returns 条目 ID 或 'new' 或空串
 */
const kbId = computed<string>(() => {
  const v = (route.params.id || route.params.kbId || route.params.kb_id || '') as string
  return v
})
/** 是否新建模式 */
const isNew = computed(() => !kbId.value || kbId.value === 'new')

/** 条目表单（version 用于乐观锁；字段对齐后端 KbCreateBody/KbUpdateBody 约束） */
const form = reactive({
  title: '',
  kb_kind: 'child',
  domain: 'child',
  topic_key: '',
  topic_category: '',
  age_range: '',
  pet_type: 'general',
  preconditions: '',
  source_type: 'expert_original',
  source_ref: '',
  tags: [] as string[],
  content: '',
  change_note: '',
  version: 1,
})

/** 主题类目候选（与种子数据类目对齐；下拉支持输入自定义类目） */
const TOPIC_CATEGORIES = ['睡眠', '喂养与辅食', '安全与意外预防', '情绪与社交', '疫苗与健康', '气质测评题库']

/**
 * 函数级注释：条目类型联动领域归属（child → child、pet → pet；其余类型保持当前领域）
 */
watch(
  () => form.kb_kind,
  (kind) => {
    if (kind === 'child' || kind === 'pet') form.domain = kind
  }
)

/** 标签输入态 */
const tagInputVisible = ref(false)
const tagInputValue = ref('')
const tagInputRef = ref<any>(null)

/** 版本历史（右栏内嵌时间线） */
const versionsLoading = ref(false)
const versions = ref<any[]>([])

/** 回滚弹窗状态 */
const rollbackVisible = ref(false)
const rollbackForm = reactive({ target_version: 1, reason: '' })

/** 正文 textarea 实例（Markdown 工具栏操作光标选区用） */
const contentRef = ref<HTMLTextAreaElement | null>(null)

/** 当前编辑人（真实登录账号信息；无则回落到"当前管理员"） */
const adminName = computed<string>(() => getAdminInfo()?.display_name || getAdminInfo()?.username || '当前管理员')

/** 版本时间线按版本号倒序（最新在上，与稿面一致） */
const sortedVersions = computed<any[]>(() =>
  [...versions.value].sort((a, b) => Number(b.version) - Number(a.version))
)

/** 可回滚目标：小于当前版本的最大版本号（无历史时为 null，回滚按钮禁用） */
const rollbackTarget = computed<number | null>(() => {
  const older = versions.value.map((v) => Number(v.version)).filter((n) => n < form.version)
  return older.length ? Math.max(...older) : null
})

/** 敏感词命中数量（matched_terms） */
const termCount = computed(() => checkResult.value?.matched_terms?.length || 0)
/** 模式规则命中数量（matched_patterns） */
const patternCount = computed(() => checkResult.value?.matched_patterns?.length || 0)
/** 敏感词行状态：未运行 neutral / 通过 ok / 命中 bad */
const termState = computed(() => {
  if (!checkResult.value) return 'neutral'
  return termCount.value > 0 || checkResult.value.hit ? 'bad' : 'ok'
})
/** 敏感词行结果文案 */
const termResultText = computed(() => {
  if (!checkResult.value) return '待运行：点击「运行校验」检测正文'
  return termState.value === 'ok' ? 'OK 通过 0 命中' : `命中 ${termCount.value} 项`
})
/** 全部命中片段（敏感词 + 模式），供删除处置定位正文片段 */
const hitSnippets = computed<string[]>(() => {
  const r = checkResult.value
  if (!r) return []
  return [...(r.matched_terms || []), ...(r.matched_patterns || [])]
})

/**
 * 函数级注释：HTML 转义（防 XSS 的第一步）
 * @param src 原始文本
 * @returns 转义后文本
 */
function escapeHtml(src: string): string {
  return src
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 函数级注释：极简 Markdown 渲染（先整体转义再做有限语法替换，不引第三方库）
 * @param src Markdown 源文本
 * @returns 可安全用于 v-html 的 HTML 片段
 */
function mdToHtml(src: string): string {
  let s = escapeHtml(src || '')
  s = s.replace(/^### (.*)$/gm, '<h3>$1</h3>')
  s = s.replace(/^## (.*)$/gm, '<h2>$1</h2>')
  s = s.replace(/^# (.*)$/gm, '<h1>$1</h1>')
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>')
  s = s.replace(/^[-*] (.*)$/gm, '• $1')
  s = s.replace(/\n/g, '<br/>')
  return s
}

/** 预览 HTML（computed 缓存） */
const previewHtml = computed(() => mdToHtml(form.content))

/**
 * 函数级注释：在光标选区两侧插入包裹语法（B/I/代码）；无选区时插入带占位文本的成对语法
 * @param wrap 包裹语法（如 '**'、'`'）
 */
function insertWrap(wrap: string): void {
  const el = contentRef.value
  if (!el) return
  const start = el.selectionStart ?? form.content.length
  const end = el.selectionEnd ?? start
  const sel = form.content.slice(start, end)
  const body = sel || '文本'
  form.content = form.content.slice(0, start) + wrap + body + wrap + form.content.slice(end)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + wrap.length, start + wrap.length + body.length)
  })
}

/**
 * 函数级注释：在光标所在行行首插入前缀语法（H1/H2/列表/引用）
 * @param prefix 行首前缀（如 '# '、'- '）
 */
function insertLinePrefix(prefix: string): void {
  const el = contentRef.value
  if (!el) return
  const start = el.selectionStart ?? form.content.length
  const lineStart = form.content.lastIndexOf('\n', Math.max(start - 1, 0)) + 1
  form.content = form.content.slice(0, lineStart) + prefix + form.content.slice(lineStart)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + prefix.length, start + prefix.length)
  })
}

/**
 * 函数级注释：模式命中处置——改写（切回编辑态并聚焦正文，提示手动改写）
 */
function rewriteHit(): void {
  mode.value = 'edit'
  nextTick(() => contentRef.value?.focus())
  ElMessage.info('请在正文中改写命中片段，完成后重新「运行校验」')
}

/**
 * 函数级注释：模式命中处置——删除（从正文移除首个可定位的命中片段并自动重新校验）
 */
function deleteHit(): void {
  for (const s of hitSnippets.value) {
    const idx = form.content.indexOf(s)
    if (idx >= 0) {
      form.content = form.content.slice(0, idx) + form.content.slice(idx + s.length)
      ElMessage.success('已删除首个命中片段，正在重新校验')
      runCheck()
      return
    }
  }
  ElMessage.info('命中片段为规则表达式，请在正文中手动删除对应内容后重新校验')
}

/**
 * 函数级注释：模式命中处置——标记为专家复核（CG14），标记后仍可提交审核（提交时二次确认）
 */
function markExpertReview(): void {
  expertReviewed.value = true
  ElMessage.success('已标记为专家复核（CG14），提交审核时将进入专家复核环节')
}

/**
 * 函数级注释：加载条目详情（新建模式跳过），同时带入状态与审核评分
 */
async function loadDetail(): Promise<void> {
  if (isNew.value) return
  try {
    // keyword 仅按标题匹配，无法用于按 kb_id 定位；改为拉取一页后在本地按 kb_id 精确匹配
    const data: any = await adminApi.kbList({ page: 1, page_size: 100 })
    const list: any[] = data?.list || data?.items || data || []
    const hit = list.find((r) => String(r.kb_id) === String(kbId.value))
    if (!hit) {
      ElMessage.warning('未找到该条目，可能已被删除')
      return
    }
    form.title = hit.title || ''
    form.kb_kind = hit.kb_kind || 'child'
    form.domain = hit.domain || 'child'
    form.topic_key = hit.topic_key || ''
    form.topic_category = hit.topic_category || ''
    form.preconditions = hit.preconditions || ''
    form.source_type = hit.source_type || 'expert_original'
    form.source_ref = hit.source_ref || ''
    form.age_range = hit.age_band || ''
    form.pet_type = hit.species || 'general'
    form.tags = Array.isArray(hit.tags) ? hit.tags : []
    form.content = hit.content || hit.body || ''
    form.version = Number(hit.version || 1)
    status.value = hit.status || 'draft'
    const sc = Number(hit.score ?? hit.review_score ?? 0)
    entryScore.value = sc > 0 ? sc : null
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '条目加载失败')
  }
}

/**
 * 函数级注释：提交前表单校验（与后端 KbCreateBody 必填约束一致，逐项给出明确提示）
 * @returns 首个未通过项的提示文案；全部通过返回空串
 */
function validateForm(): string {
  if (!form.title.trim()) return '请填写条目标题'
  if (!form.domain) return '请选择领域归属'
  if (!form.topic_key.trim()) return '请填写主题键（如 sleep_training）'
  if (!form.topic_category) return '请选择主题类目'
  if (!form.age_range) return '请选择适用月龄'
  if (!form.preconditions.trim()) return '请填写适用前提（一票否决项，必填）'
  if (!form.source_type) return '请选择来源类型'
  if (!form.source_ref.trim()) return '请填写来源引用（必填，可溯源）'
  if (!form.content.trim()) return '请填写正文内容'
  if (!form.change_note.trim()) return '请填写变更说明（必填）'
  return ''
}

/**
 * 函数级注释：保存草稿/更新条目（乐观锁）
 * @returns 是否保存成功
 * @throws 409 并发冲突（code=1003/1601）时提示刷新，不抛出中断流程
 */
async function handleSave(): Promise<boolean> {
  const invalid = validateForm()
  if (invalid) {
    ElMessage.warning(invalid)
    return false
  }
  saving.value = true
  try {
    if (isNew.value) {
      // 新建载荷对齐 KbCreateBody：domain/topic_key/topic_category/preconditions/source_type/source_ref 必填
      const data: any = await adminApi.kbCreate({
        kb_kind: form.kb_kind,
        domain: form.domain,
        topic_key: form.topic_key.trim(),
        topic_category: form.topic_category,
        title: form.title.trim(),
        content: form.content,
        preconditions: form.preconditions.trim(),
        source_type: form.source_type,
        source_ref: form.source_ref.trim(),
        age_band: form.age_range || null,
        species: form.pet_type,
      })
      const newId = data?.kb_id || data?.id
      ElMessage.success('条目已创建')
      if (newId) router.replace(`/admin/kb/${newId}`)
    } else {
      // PUT 携带 version 乐观锁；后端返回 409/1003/1601 时提示刷新
      await adminApi.kbUpdate(kbId.value, {
        version: form.version,
        title: form.title.trim(),
        content: form.content,
        preconditions: form.preconditions.trim(),
        topic_category: form.topic_category,
        source_type: form.source_type,
        source_ref: form.source_ref.trim(),
        age_band: form.age_range || null,
        species: form.pet_type,
      })
      ElMessage.success('已保存')
      loadDetail()
    }
    return true
  } catch (e) {
    if (e instanceof ApiError && (e.code === 1003 || e.code === 1601 || e.code === 409)) {
      ElMessage.error('内容已被更新，请刷新后重试')
    } else {
      ElMessage.error(e instanceof ApiError ? e.message : '保存失败')
    }
    return false
  } finally {
    saving.value = false
  }
}

/**
 * 函数级注释：提交审核（先保存，再调用提交接口；命中风险规则时要求二次确认）
 */
async function handleSubmit(): Promise<void> {
  if (isNew.value) {
    ElMessage.warning('请先保存草稿后再提交审核')
    return
  }
  if (checkResult.value?.hit) {
    try {
      await ElMessageBox.confirm(
        '正文命中敏感词/模式规则，确定仍要提交审核？（专家复核环节会再次校验）',
        '风险确认',
        { type: 'warning' }
      )
    } catch {
      return
    }
  }
  const ok = await handleSave()
  if (!ok) return
  try {
    const data: any = await adminApi.kbSubmit(kbId.value)
    // 后端返回的 warnings 展示到发布前校验块
    if (data?.warnings?.length) warnings.value = data.warnings
    ElMessage.success('已提交审核')
    loadDetail()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '提交失败')
  }
}

/**
 * 函数级注释：运行发布前校验（复用词库规则测试接口检测正文）
 */
async function runCheck(): Promise<void> {
  if (!form.content.trim()) {
    ElMessage.warning('正文为空，无需校验')
    return
  }
  checking.value = true
  try {
    checkResult.value = await adminApi.lexiconTest(form.content)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '校验失败')
  } finally {
    checking.value = false
  }
}

/**
 * 函数级注释：显示标签输入框并聚焦
 */
function showTagInput(): void {
  tagInputVisible.value = true
  nextTick(() => tagInputRef.value?.focus?.())
}

/**
 * 函数级注释：确认添加标签（去重）
 */
function confirmTag(): void {
  const v = tagInputValue.value.trim()
  if (v && !form.tags.includes(v)) form.tags.push(v)
  tagInputVisible.value = false
  tagInputValue.value = ''
}

/**
 * 函数级注释：移除标签
 * @param tag 待移除的标签
 */
function removeTag(tag: string): void {
  form.tags = form.tags.filter((t) => t !== tag)
}

/**
 * 函数级注释：加载版本历史（右栏时间线；失败静默不打断编辑）
 * 后端 /kb/entries/{id}/versions 从审计日志聚合返回 after_version/before_version，
 * 此处归一化为 version 字段供时间线/回滚目标计算使用（修复版本号渲染为空导致回滚按钮永久禁用）。
 */
async function loadVersions(): Promise<void> {
  versionsLoading.value = true
  try {
    const data: any = await adminApi.kbVersions(kbId.value)
    const raw: any[] = data?.items || data?.list || data || []
    versions.value = raw.map((r) => ({
      ...r,
      version: Number(r.after_version ?? r.before_version ?? r.version ?? 0),
    }))
  } catch {
    versions.value = []
  } finally {
    versionsLoading.value = false
  }
}

/**
 * 函数级注释：对比差异（占位交互，差异对比能力待接入）
 * @param v 目标版本行
 */
function diffVersion(v: any): void {
  ElMessage.info(`v${v.version} 与当前版本的内容对比能力即将上线`)
}

/**
 * 函数级注释：格式化版本时间（取日期部分，与稿面时间线一致）
 * @param v 版本行
 * @returns yyyy-MM-dd 或 '--'
 */
function fmtVerTime(v: any): string {
  return String(v?.created_at || v?.changed_at || '').slice(0, 10) || '--'
}

/**
 * 函数级注释：格式化版本操作人（审计聚合行仅含 operator_role 快照）
 * @param v 版本行
 * @returns 操作角色/操作人名或 '--'
 */
function fmtVerOp(v: any): string {
  return v?.operator_role || v?.operator_name || v?.operator || v?.changed_by || '--'
}

/**
 * 函数级注释：格式化版本摘要（审计聚合行的变更原因为 reason 字段）
 * @param v 版本行
 * @returns 变更摘要或占位符
 */
function fmtVerNote(v: any): string {
  return v?.reason || v?.change_note || v?.summary || '—'
}

/**
 * 函数级注释：打开回滚弹窗（预填目标版本）
 * @param target 目标版本号
 */
function openRollback(target: number): void {
  rollbackForm.target_version = target
  rollbackForm.reason = ''
  rollbackVisible.value = true
}

/**
 * 函数级注释：确认回滚（必填原因 + 二次确认 + confirm_token）
 */
async function confirmRollback(): Promise<void> {
  if (!rollbackForm.reason.trim()) {
    ElMessage.warning('请填写回滚原因（必填）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认回滚到 v${rollbackForm.target_version}？回滚将触发内容追溯处置。`,
      '二次确认',
      { type: 'warning', confirmButtonText: '确认回滚', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await adminApi.kbRollback(kbId.value, {
      target_version: rollbackForm.target_version,
      version: form.version, // 乐观锁：后端 KbRollbackBody 必填，比对当前版本
      reason: rollbackForm.reason.trim(),
      confirm_token: CONFIRM_TOKEN,
    })
    ElMessage.success('已回滚')
    rollbackVisible.value = false
    loadDetail()
    loadVersions()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '回滚失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadDetail()
  if (isNew.value) return
  // 编辑模式：右栏自动加载版本时间线
  await loadVersions()
  // 列表页带 ?rollback=1 进入时自动打开回滚弹窗
  if (route.query.rollback === '1' && rollbackTarget.value) openRollback(rollbackTarget.value)
})
</script>

<style scoped>
/* 页面双栏工作台 */
.edit-grid {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.col-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.col-side {
  flex: none;
  width: 340px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1080px) {
  .edit-grid {
    flex-direction: column;
  }
  .col-side {
    width: 100%;
  }
}

/* ---------- 1. 条目头卡 ---------- */
.head-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 16px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 300px;
}

.kb-chip {
  flex: none;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-sub);
  font-weight: 500;
  white-space: nowrap;
}

.title-input {
  flex: 1;
  max-width: 380px;
}

.head-actions {
  display: flex;
  gap: 8px;
}

.btn-ico {
  margin-right: 4px;
}

/* ---------- 2. 元数据卡 ---------- */
.meta-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.meta-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-field label {
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-2);
}

/* 来源溯源行：类型 1 列 + 引用 2 列 */
.source-grid {
  grid-template-columns: 1fr 2fr;
}

/* 适用前提（一票否决项）行 */
.precond-field {
  padding-top: 2px;
}

/* 字段提示文案（与 note-hint 同风格） */
.field-hint {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-weight: 400;
}

.tags-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.tags-label {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-weight: 500;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border-radius: 4px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

.tag-x {
  cursor: pointer;
  color: var(--ink-3);
}

.tag-x:hover {
  color: var(--danger);
}

.tag-input {
  width: 110px;
}

.tag-add {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border: 1px dashed var(--accent-line);
  border-radius: 4px;
  background: transparent;
  color: var(--accent);
  font-size: var(--fs-caption);
  cursor: pointer;
  transition: background 0.15s ease;
}

.tag-add:hover {
  background: var(--accent-soft);
}

/* ---------- 3. Markdown 编辑卡 ---------- */
.md-card {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.md-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 16px;
  background: var(--surface-bright);
  border-bottom: 1px solid var(--line);
}

.md-tools {
  display: flex;
  align-items: center;
  gap: 2px;
}

.md-btn {
  min-width: 28px;
  height: 28px;
  padding: 0 7px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13px;
  font-family: var(--font-numeric);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, color 0.15s ease;
}

.md-btn:hover {
  background: var(--surface-2);
  color: var(--ink-1);
}

.md-sep {
  width: 1px;
  height: 16px;
  background: var(--line);
  margin: 0 6px;
}

.md-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.word-count {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.mode-btn {
  height: 22px;
  padding: 0 10px;
  border: none;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 500;
  cursor: pointer;
}

.mode-btn:hover {
  background: var(--surface-2);
}

.md-textarea {
  width: 100%;
  min-height: 320px;
  padding: 16px;
  border: none;
  outline: none;
  resize: vertical;
  background: var(--surface);
  color: var(--ink-1);
  font-family: var(--font-numeric);
  font-size: var(--fs-sub);
  line-height: 1.8;
}

.md-preview {
  min-height: 320px;
  padding: 16px;
  font-size: var(--fs-sub);
  line-height: 1.8;
  word-break: break-word;
}

.md-preview :deep(h1),
.md-preview :deep(h2),
.md-preview :deep(h3) {
  margin: 10px 0 6px;
  color: var(--ink-1);
}

.md-preview :deep(code) {
  background: var(--surface-2);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--font-numeric);
  font-size: 13px;
}

/* ---------- 4. 发布前合规与模式校验卡 ---------- */
.check-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.sec-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}

.check-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--surface-bright);
  border: 1px solid var(--line);
}

.cl-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-sub);
  color: var(--ink-1);
  min-width: 0;
}

.cl-sub {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.ico-ok {
  color: var(--accent);
}

.ico-bad {
  color: var(--danger);
}

.ico-warn {
  color: var(--warn);
}

.cl-badge {
  flex: none;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-caption);
  font-weight: 600;
}

.badge-ok {
  background: var(--accent-soft);
  color: var(--accent);
}

.badge-bad {
  background: var(--danger-soft);
  color: var(--danger);
}

.hit-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hit-code {
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--danger-soft);
  color: var(--danger);
  font-family: var(--font-numeric);
  font-size: var(--fs-sub);
  font-weight: 500;
}

/* 模式规则命中卡（黄底） */
.pattern-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 8px;
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
}

.pc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.pc-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-1);
}

.pc-sub {
  font-size: var(--fs-caption);
  color: var(--warn);
  font-weight: 700;
}

.pc-flag {
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--warn-soft);
  border: 1px solid var(--warn);
  color: var(--warn);
  font-size: var(--fs-caption);
  font-weight: 700;
}

.pc-hit {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--surface);
  border: 1px solid var(--line);
}

.pc-hint {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.pc-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.act-btn {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--surface);
  font-size: var(--fs-caption);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
}

.act-btn.rewrite {
  color: var(--accent);
}

.act-btn.del {
  color: var(--danger);
}

.act-btn.review {
  background: var(--warn-soft);
  border-color: var(--warn);
  color: var(--warn);
}

.act-btn:hover {
  background: var(--surface-2);
}

.check-tip {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  margin: 0;
}

/* ---------- 5. 变更说明卡 ---------- */
.note-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.note-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-1);
}

.req {
  color: var(--danger);
  font-weight: 700;
}

.note-hint {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-weight: 400;
}

/* ---------- 6. 并发锁卡 ---------- */
.lock-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}

.lock-dot {
  position: relative;
  width: 10px;
  height: 10px;
  flex: none;
}

.lock-dot::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.4;
  animation: lock-pulse 1.6s ease-out infinite;
}

.lock-dot::after {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  background: var(--accent);
}

@keyframes lock-pulse {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}

.lock-text {
  flex: 1;
  min-width: 0;
}

.lt-main {
  font-size: var(--fs-caption);
  font-weight: 500;
  color: var(--ink-1);
}

.lt-sub {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.lt-name {
  color: var(--accent);
  font-family: var(--font-numeric);
  font-weight: 500;
}

.lock-ico {
  color: var(--ink-3);
}

/* ---------- 7. 版本历史卡 ---------- */
.ver-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ver-count {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-weight: 500;
}

.ver-list {
  position: relative;
  margin-left: 6px;
  padding-left: 18px;
  border-left: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ver-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--surface);
  transition: background 0.15s ease;
}

.ver-item:hover {
  background: var(--surface-2);
}

.ver-item.current {
  background: var(--accent-soft);
  border-color: var(--accent-line);
}

/* 时间线节点圆点 */
.ver-item::before {
  content: '';
  position: absolute;
  left: -25px;
  top: 14px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--line-strong);
  border: 2px solid var(--surface);
}

.ver-item.current::before {
  background: var(--accent);
}

.ver-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ver-no {
  font-size: var(--fs-sub);
  font-weight: 700;
  color: var(--ink-1);
}

.ver-item.current .ver-no {
  color: var(--accent);
}

.cur-badge {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  line-height: 1.4;
}

.diff-link {
  border: none;
  background: none;
  color: var(--accent);
  font-size: var(--fs-caption);
  cursor: pointer;
}

.diff-link:hover {
  text-decoration: underline;
}

.ver-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.ver-op {
  font-weight: 500;
  color: var(--ink-2);
}

.ver-note {
  font-size: var(--fs-sub);
  color: var(--ink-2);
  margin-top: 2px;
}

/* 回滚区 */
.rollback-zone {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.rz-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--fs-caption);
}

.rz-title {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--danger);
  font-weight: 600;
}

.rz-side {
  color: var(--ink-3);
}

.rollback-btn {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  border: 1px solid var(--danger);
  background: var(--surface);
  color: var(--danger);
  font-size: var(--fs-sub);
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: background 0.15s ease;
}

.rollback-btn:hover:not(:disabled) {
  background: var(--danger-soft);
}

.rollback-btn:disabled {
  border-color: var(--line-strong);
  color: var(--ink-3);
  opacity: 0.6;
  cursor: not-allowed;
}

.warn-note {
  background: var(--warn-soft);
  border-color: var(--line-strong);
  color: var(--warn);
}

.warn-note .note-ico {
  color: var(--warn);
}

/* ---------- 8. 质控刻度卡 ---------- */
.qc-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.qc-title {
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--ink-2);
  letter-spacing: 0.05em;
}

.qc-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.qc-val {
  color: var(--accent);
  font-weight: 500;
}

/* ---------- 弹窗 ---------- */
.dialog-alert {
  margin-bottom: 4px;
}

/* 手机窄屏（375 视口）：解除固定宽约束、工具条与元数据纵排，消除横向滚动 */
@media (max-width: 640px) {
  .head-left {
    flex: 1 1 100%;
    flex-wrap: wrap;
    min-width: 0;
  }
  .title-input {
    flex: 1 1 100%;
    max-width: none;
  }
  .head-actions {
    flex-wrap: wrap;
  }
  .meta-grid {
    grid-template-columns: 1fr;
  }
  .source-grid {
    grid-template-columns: 1fr;
  }
  .md-toolbar {
    flex-wrap: wrap;
    row-gap: 6px;
  }
  .md-tools {
    flex-wrap: wrap;
  }
}
</style>
