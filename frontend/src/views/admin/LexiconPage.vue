<!--
  文件级注释：PA-04 词库维护页（高危/敏感，Stitch 高保真形态）
  - 页头卡：标题 + 副标 + 高危/敏感类型计数徽章（真实统计，可点击切换）+ 批量导入 + 新增词条
  - 筛选行：类型 / 策略 / 状态 下拉 + 词条搜索（策略/状态/关键词为前端过滤，类型联动 API）
  - 词条表：词条 / 类型 st-tag / 处理策略着色 / 阈值档 chip / 状态绿点 / 更新时间 / 操作（编辑·删除需二次确认）
  - 两级判定配置卡：判定刻度尺可视化（阈值读真实 lexicon 配置 two_level_threshold，三段色带 + 刻度标注）
    + 三策略说明子卡（一级硬拦截 / 二级语义判定 / 灰区以下治理，文案照稿）
  - 医疗/兽药模式规则引擎卡：核心捕获表达式等宽展示 + 复制 + 「编辑规则」打开配置编辑弹窗
    （双阈值 + 三正则 + 原因留痕，1602 自动二次确认重发）+ 输入样例即时命中（防抖调 /admin/lexicon/test）
  - 底部操作条：命中日志（待接入置灰）/ 变更留痕 / 一键回滚配置（原历史抽屉 + 回滚二次确认）+ st-note 生效提示
-->
<template>
  <div class="lexicon-page">
    <!-- 1. 页头卡 -->
    <section class="st-card head-card">
      <div class="head-left">
        <div class="head-text">
          <h2 class="head-title">词库维护（高危 / 敏感）</h2>
          <p class="head-sub">敏感词与高风险词库矩阵 · 命中即阻断或转人工复核</p>
        </div>
        <span class="head-sep"></span>
        <!-- 类型计数徽章（真实两库统计，点击切换当前库） -->
        <div class="kind-tabs">
          <button
            type="button"
            class="kind-tab"
            :class="{ active: activeKind === 'high_risk' }"
            @click="switchKind('high_risk')"
          >
            <span>高危</span>
            <span class="kt-count danger numeric">{{ counts.high_risk }}</span>
          </button>
          <button
            type="button"
            class="kind-tab"
            :class="{ active: activeKind === 'sensitive' }"
            @click="switchKind('sensitive')"
          >
            <span>敏感</span>
            <span class="kt-count numeric">{{ counts.sensitive }}</span>
          </button>
        </div>
      </div>
      <div class="head-actions">
        <el-button :icon="Upload" @click="openBatchImport">批量导入词库</el-button>
        <el-button type="primary" :icon="Plus" @click="openAddTerm">新增词条</el-button>
      </div>
    </section>

    <!-- 2. 筛选行卡 -->
    <section class="st-card filter-card">
      <div class="ff">
        <label>类型</label>
        <el-select v-model="activeKind" placeholder="全部" @change="loadTerms">
          <el-option label="全部" value="" />
          <el-option label="高危" value="high_risk" />
          <el-option label="敏感" value="sensitive" />
        </el-select>
      </div>
      <div class="ff">
        <label>策略</label>
        <el-select v-model="filters.policy" clearable placeholder="全部">
          <el-option v-for="p in POLICY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
      </div>
      <div class="ff">
        <label>状态</label>
        <el-select v-model="filters.status" clearable placeholder="全部">
          <el-option label="生效" value="on" />
          <el-option label="停用" value="off" />
        </el-select>
      </div>
      <div class="ff grow">
        <el-input
          v-model="filters.keyword"
          placeholder="按词条名称 / 逻辑检索..."
          :prefix-icon="Search"
          clearable
        />
      </div>
    </section>

    <!-- 3. 词条表卡 -->
    <section class="st-card table-card">
      <el-table :data="filteredTerms" v-loading="termsLoading" class="lex-table">
        <el-table-column label="词条" min-width="160">
          <template #default="{ row }">
            <span class="term-name">{{ row.term }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="88">
          <template #default="{ row }">
            <span class="st-tag st-tag--plain" :class="row.lexicon_type === 'risk' ? 'st-tag--red' : 'st-tag--amber'">
              {{ row.lexicon_type === 'risk' ? '高危' : '敏感' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="处理策略" width="110">
          <template #default="{ row }">
            <span class="policy-text" :class="policyClass(row.strategy)">{{ policyLabel(row.strategy) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="阈值档" width="110">
          <template #default="{ row }">
            <span v-if="tierOf(row.strategy)" class="tier-chip" :class="tierOf(row.strategy)!.cls">
              {{ tierOf(row.strategy)!.text }}
            </span>
            <span v-else class="muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="st-tag" :class="row.effective === false ? 'st-tag--gray' : 'st-tag--green'">
              {{ row.effective === false ? '停用' : '生效' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="140">
          <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditTerm(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDeleteTerm(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
      <!-- 表尾统计（真实过滤后数量） -->
      <div class="table-foot">
        <span>共展现 {{ filteredTerms.length }} 条{{ kindText }}风控干预定义</span>
        <span class="numeric">词库共 {{ terms.length }} 条</span>
      </div>
    </section>

    <!-- 4. 两级判定配置与量具刻度分档卡 -->
    <section class="st-card cfg-card">
      <div class="sec-head-row">
        <div class="st-section-head">两级判定配置与量具刻度分档</div>
        <span class="cap-note">阈值来源：词库配置 two_level_threshold（当前 {{ config.threshold_low }} / {{ config.threshold_high }}）</span>
      </div>
      <div class="scale-panel">
        <div class="scale-top">
          <span class="scale-name">判定刻度标尺 (Risk Confidence Axis)</span>
          <span class="numeric scale-range">0.0 ———————— 1.0</span>
        </div>
        <!-- 三段色带（宽度按真实阈值动态计算） -->
        <div class="scale-band">
          <div class="band band-safe" :style="{ width: safePct + '%' }">
            <span>安全 · 弱敏感区 (&lt;{{ config.threshold_low }})</span>
          </div>
          <div class="band band-mid" :style="{ width: midPct + '%' }">
            <span>中度灰区 ({{ config.threshold_low }} - {{ config.threshold_high }})</span>
          </div>
          <div class="band band-high" :style="{ width: highPct + '%' }">
            <span>绝对高危 (&gt;{{ config.threshold_high }})</span>
          </div>
        </div>
        <!-- 刻度标注 -->
        <div class="scale-ticks">
          <span class="tick start"><i></i>0.0</span>
          <span class="tick" :style="{ left: safePct + '%' }"><i></i>{{ config.threshold_low }}（初步拦截）</span>
          <span class="tick" :style="{ left: safePct + midPct + '%' }"><i></i>{{ config.threshold_high }}（阻断阈值）</span>
          <span class="tick end"><i></i>1.0</span>
        </div>
        <!-- 三策略说明子卡（文案照稿） -->
        <div class="tier-cards">
          <div class="tier-card">
            <div class="tc-head">
              <span class="tc-badge danger">一级硬拦截</span>
              <span class="tc-side">毫秒级命中</span>
            </div>
            <div class="tc-name">词库 + 正则匹配</div>
            <p class="tc-desc">命中高危硬词库或固定危急正则直接执行阻断逻辑，不进入后续语义模型计算。</p>
          </div>
          <div class="tier-card">
            <div class="tc-head">
              <span class="tc-badge warn">二级语义判定</span>
              <span class="tc-side">仅灰区运算</span>
            </div>
            <div class="tc-name">语义模型评分矩阵</div>
            <p class="tc-desc">评分 &gt;{{ config.threshold_high }} 强制拦截；评分在 {{ config.threshold_low }}-{{ config.threshold_high }} 区间内执行"拦截并注入儿科就诊指引"。</p>
          </div>
          <div class="tier-card">
            <div class="tc-head">
              <span class="tc-badge gray">灰区以下治理</span>
              <span class="tc-side">&lt;{{ config.threshold_low }} 放行</span>
            </div>
            <div class="tc-name">放行与动态抽检</div>
            <p class="tc-desc">正常放行交互并自动打标，按 5% 概率自动纳入次日专家双盲抽检池。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 5. 医疗 / 兽药模式规则引擎卡 -->
    <section class="st-card regex-card">
      <div class="sec-head-row">
        <div class="st-section-head">医疗 / 兽药模式规则引擎 (RegEx Pattern Engine)</div>
        <span class="cap-note">语法环境：PCRE2 · 编辑保存后全量生效</span>
      </div>
      <div class="regex-grid">
        <div class="rg-main">
          <div class="rg-label">核心捕获表达式：儿童及宠物用药频率防诱导模式</div>
          <div class="regex-box">
            <code class="numeric rg-code">{{ config.pattern_drug || '--（未配置药名剂量正则）' }}</code>
            <button type="button" class="copy-btn" title="复制表达式" @click="copyPattern">
              <el-icon><CopyDocument /></el-icon>
            </button>
          </div>
          <div class="rg-desc">
            <el-icon class="rg-desc-ico"><InfoFilled /></el-icon>
            <span>说明：限制无执业医师资质场景下生成确切服药剂量方案与用药频次推荐。</span>
          </div>
          <!-- 输入样例即时命中（防抖调用 /admin/lexicon/test） -->
          <div class="rt-row">
            <el-input
              v-model="testText"
              placeholder="输入样例即时命中测试，如：每日 3 次，每次 5ml"
              clearable
            />
          </div>
          <div v-if="testResult" class="rt-result" :class="testResult.hit ? 'bad' : 'ok'">
            <template v-if="testResult.hit">
              <span class="rt-flag">命中</span>
              <span v-if="testResult.risk_result" class="rt-item">分级：{{ riskGradeText(testResult.risk_result) }}</span>
              <span v-if="testResult.matched_terms?.length" class="rt-item">命中词：{{ termNames(testResult.matched_terms) }}</span>
              <span v-if="testResult.matched_patterns?.length" class="rt-item">命中模式：{{ testResult.matched_patterns.join('、') }}</span>
            </template>
            <template v-else>
              <span class="rt-flag pass">未命中</span>
              <span class="rt-item">当前样例未触发任何敏感词 / 模式规则</span>
              <span v-if="testResult.risk_result?.blocked" class="rt-item">分级：{{ riskGradeText(testResult.risk_result) }}</span>
            </template>
          </div>
        </div>
        <div class="rg-side">
          <el-button class="rg-btn" @click="openConfigEdit">编辑规则</el-button>
        </div>
      </div>
    </section>

    <!-- 6. 底部操作条：命中日志 / 变更留痕 / 一键回滚配置 + 生效提示 -->
    <footer class="st-card foot-bar">
      <div class="foot-top">
        <div class="foot-actions">
          <el-tooltip content="命中日志能力待接入" placement="top">
            <span><el-button disabled :icon="TicketsIcon">命中日志</el-button></span>
          </el-tooltip>
          <el-button :icon="Clock" @click="openHistory">变更留痕</el-button>
          <el-button type="danger" plain :icon="RefreshLeft" @click="openHistory">一键回滚配置</el-button>
        </div>
        <span class="foot-meta numeric">配置键：lexicon</span>
      </div>
      <div class="st-note warn-note">
        <el-icon class="note-ico"><WarningFilled /></el-icon>
        <div><strong>隔离历史直接恢复线上提示：</strong>词库变更直接影响线上拦截，保存后 1 分钟内全量生效并记录版本。</div>
      </div>
    </footer>

    <!-- 新增词条弹窗 -->
    <el-dialog v-model="addVisible" title="新增词条" width="420px">
      <p class="dialog-tip">当前新增到：<strong>{{ activeKind === 'sensitive' ? '敏感词库' : '高危词库' }}</strong></p>
      <el-form label-width="90px">
        <el-form-item label="词条" required>
          <el-input v-model="newTerm.term" placeholder="新词条（如：持续高烧惊厥）" @keyup.enter="handleAddTerm" />
        </el-form-item>
        <el-form-item label="处理策略">
          <el-select v-model="newTerm.policy" style="width: 100%">
            <el-option v-for="p in POLICY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="handleAddTerm">新增</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importVisible" title="批量导入词条" width="480px">
      <p class="dialog-tip">当前导入到：<strong>{{ activeKind === 'sensitive' ? '敏感词库' : '高危词库' }}</strong>，每行一个词条。</p>
      <el-input v-model="importText" type="textarea" :rows="8" placeholder="词条1&#10;词条2&#10;词条3" />
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="confirmImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 编辑词条弹窗 -->
    <el-dialog v-model="editVisible" title="编辑词条" width="420px">
      <el-form label-width="90px">
        <el-form-item label="词条">
          <el-input v-model="editRow.term" disabled />
        </el-form-item>
        <el-form-item label="处理策略">
          <el-select v-model="editRow.policy" style="width: 100%">
            <el-option v-for="p in POLICY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editRow.enabled" active-text="生效" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTerm" @click="confirmEditTerm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 配置编辑弹窗（双阈值 + 三正则，保存需原因留痕） -->
    <el-dialog v-model="configEditVisible" title="编辑词库配置（阈值与模式规则）" width="560px">
      <el-form label-width="130px">
        <el-form-item label="低阈值（引导档）">
          <el-input-number v-model="config.threshold_low" :min="0" :max="1" :step="0.05" />
          <span class="tip-inline">&lt;{{ config.threshold_low }} 放行并打标，纳入抽检</span>
        </el-form-item>
        <el-form-item label="高阈值（拦截档）">
          <el-input-number v-model="config.threshold_high" :min="0" :max="1" :step="0.05" />
          <span class="tip-inline">&gt;{{ config.threshold_high }} 拦截 / {{ config.threshold_low }}-{{ config.threshold_high }} 拦截+引导</span>
        </el-form-item>
        <el-form-item label="药名剂量正则">
          <el-input v-model="config.pattern_drug" type="textarea" :rows="2" placeholder="如：药名\s*\+\s*(mg|kg|片|ml)|每日\s*N\s*次" />
        </el-form-item>
        <el-form-item label="诊断正则">
          <el-input v-model="config.pattern_diagnosis" type="textarea" :rows="2" placeholder="诊断为/疑似/确诊 等表达的正则" />
        </el-form-item>
        <el-form-item label="疗效正则">
          <el-input v-model="config.pattern_efficacy" type="textarea" :rows="2" placeholder="包治/根治/治愈率 等表达的正则" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="configSaving" @click="handleSaveConfig">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- 配置变更历史抽屉 + 一键回滚 -->
    <el-drawer v-model="historyVisible" title="配置变更历史" size="480px">
      <el-table :data="historyRows" v-loading="historyLoading" size="small">
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column prop="changed_by" label="操作人" width="100" />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.changed_at) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="变更摘要" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="danger" plain size="small" @click="handleRollback(row.version)">回滚到该版</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。词库 CRUD、双阈值与正则配置、刻度可视化、规则测试器、变更历史与回滚。
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Clock, CopyDocument, InfoFilled, Plus, RefreshLeft, Search, Tickets, Upload, WarningFilled } from '@element-plus/icons-vue'
import { adminApi, ApiError, withConfirm, CONFIRM_TOKEN } from '../../api/admin'

/** 处理策略枚举与展示（与后端 lexicon_api 约定：block / rewrite / degrade） */
const POLICY_OPTIONS = [
  { label: '阻断', value: 'block' },
  { label: '改写', value: 'rewrite' },
  { label: '降级', value: 'degrade' },
]

/** 当前词库类型（''=全部两库合并；页头徽章与筛选行类型下拉共用） */
const activeKind = ref<'high_risk' | 'sensitive' | ''>('high_risk')
/** 各词库条数（页头计数徽章） */
const counts = reactive<Record<string, number>>({ high_risk: 0, sensitive: 0 })
/** 词条列表（原始） */
const terms = ref<any[]>([])
/** 词条加载中 */
const termsLoading = ref(false)
/** 新增词条表单 */
const newTerm = reactive({ term: '', policy: 'block' })
/** 新增中标志 */
const adding = ref(false)
/** 筛选条件（策略/状态/关键词为前端过滤） */
const filters = reactive({ policy: '', status: '', keyword: '' })

/** 两级判定配置（阈值 + 三个正则） */
const config = reactive({
  threshold_low: 0.5,
  threshold_high: 0.8,
  pattern_drug: '',
  pattern_diagnosis: '',
  pattern_efficacy: '',
})
/** 配置保存中 */
const configSaving = ref(false)
/** 配置编辑弹窗 */
const configEditVisible = ref(false)
/** 词库配置键（历史/回滚复用 /admin/configs/{key} 契约） */
const CONFIG_KEY = 'lexicon'

/** 规则测试器 */
const testText = ref('')
const testResult = ref<any>(null)
/** 防抖定时器 */
let testTimer: ReturnType<typeof setTimeout> | null = null

/** 批量导入弹窗 */
const importVisible = ref(false)
const importText = ref('')
const importing = ref(false)

/** 新增词条弹窗 */
const addVisible = ref(false)

/** 编辑词条弹窗 */
const editVisible = ref(false)
const editRow = reactive<any>({ id: null, term: '', policy: 'block', enabled: true })
const savingTerm = ref(false)

/** 变更历史抽屉 */
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyRows = ref<any[]>([])

/** 图标常量（el-button :icon 需要传入组件引用） */
const TicketsIcon = Tickets

/**
 * 函数级注释：策略值转展示文案
 * @param v 策略枚举值
 * @returns 中文标签（未知值原样返回）
 */
function policyLabel(v: string): string {
  return POLICY_OPTIONS.find((p) => p.value === v)?.label || v || '--'
}

/**
 * 函数级注释：策略 → 处理策略文字着色类（阻断红 / 拦截+引导黄 / 其余中性，照稿）
 * @param v 策略枚举值
 * @returns 着色类名
 */
function policyClass(v: string): string {
  const map: Record<string, string> = {
    block: 'c-danger',
    intercept_guide: 'c-warn',
    rewrite: 'c-ink2',
    downgrade: 'c-ink3',
  }
  return map[v] || 'c-ink2'
}

/**
 * 函数级注释：策略 → 阈值档展示（阻断 >0.8 / 拦截+引导 0.5-0.8 / 改写 规则模式 / 降级无档）
 * @param v 策略枚举值
 * @returns 阈值档 {text, cls} 或 null（显示 '--'）
 */
function tierOf(v: string): { text: string; cls: string } | null {
  const map: Record<string, { text: string; cls: string }> = {
    block: { text: '>0.8', cls: 'tier-high' },
    degrade: { text: '0.5-0.8', cls: 'tier-mid' },
    rewrite: { text: '规则模式', cls: 'tier-rule' },
  }
  return map[v] || null
}

/** 当前类型中文名（表尾统计用） */
const kindText = computed(() =>
  activeKind.value === 'high_risk' ? '高危' : activeKind.value === 'sensitive' ? '敏感' : ''
)

/**
 * 函数级注释：前端过滤后的词条列表（策略/状态/关键词即时过滤，不重复请求）
 */
const filteredTerms = computed<any[]>(() => {
  let list = terms.value
  if (filters.policy) list = list.filter((t) => t.strategy === filters.policy)
  if (filters.status === 'on') list = list.filter((t) => t.effective !== false)
  if (filters.status === 'off') list = list.filter((t) => t.effective === false)
  const kw = filters.keyword.trim()
  if (kw) list = list.filter((t) => String(t?.term || '').includes(kw))
  return list
})

/**
 * 函数级注释：刻度三段宽度（百分比，按真实阈值 clamp 到 0-100）
 */
const safePct = computed(() => clampPct(config.threshold_low * 100))
const midPct = computed(() => clampPct(config.threshold_high * 100) - clampPct(config.threshold_low * 100))
const highPct = computed(() => 100 - clampPct(config.threshold_high * 100))

/**
 * 函数级注释：百分比钳制（阈值越界时保证色带渲染合法）
 * @param n 原始百分比
 * @returns 0-100 内百分比
 */
function clampPct(n: number): number {
  return Math.min(100, Math.max(0, Math.round(n * 10) / 10))
}

/**
 * 函数级注释：规则测试器命中的词条列表转展示文本（对象取 term 字段，兼容字符串数组）
 * @param list 命中词条数组
 * @returns 顿号拼接文本
 */
function termNames(list: any[]): string {
  return (list || []).map((t) => (typeof t === 'string' ? t : t?.term || '')).filter(Boolean).join('、')
}

/**
 * 常量注释：风险类别代码 → 中文展示名映射（与风险引擎类别集对齐）
 */
const RISK_CATEGORY_LABELS: Record<string, string> = {
  child_abuse: '儿童安全类',
  child_selfharm: '儿童自伤类',
  high_fever: '儿童急症类',
  animal_bite: '动物咬伤类',
  depression: '心理抑郁类',
  pet_poison: '宠物中毒类',
  pet_bleeding: '宠物出血类',
  medicine_dosage: '用药剂量类',
  diagnosis: '医疗诊断类',
  efficacy: '疗效承诺类',
  fortune: '命理迷信类',
  semantic_unavailable: '语义服务异常',
}

/**
 * 函数级注释：分级档位文本（与风险引擎分级口径对齐：L1→一级拦截 / L2→二级引导 / 其余→放行）
 * @param risk 测试器响应中的 risk_result 分级判定结构
 * @returns 档位文本
 */
function riskTierText(risk: any): string {
  if (!risk) return ''
  if (risk.level === 'L1') return '一级拦截'
  if (risk.level === 'L2') return '二级引导'
  return '放行'
}

/**
 * 函数级注释：分级结果展示文本（类别 + 档位，如「儿童安全类 · 一级拦截」；放行时仅返回「放行」）
 * @param risk 测试器响应中的 risk_result 分级判定结构
 * @returns 分级展示文本（空结构返回空串）
 */
function riskGradeText(risk: any): string {
  if (!risk) return ''
  const tier = riskTierText(risk)
  if (tier === '放行') return tier
  const label = risk.category_code ? RISK_CATEGORY_LABELS[risk.category_code] || risk.category_code : ''
  return [label, tier].filter(Boolean).join(' · ')
}

/**
 * 函数级注释：切换词库类型（重置前端过滤后重新加载）
 * @param kind 类型 key（''=全部）
 */
function switchKind(kind: 'high_risk' | 'sensitive' | ''): void {
  if (activeKind.value === kind) return
  activeKind.value = kind
  loadTerms()
}

/**
 * 函数级注释：前端词库键 → 后端 lexicon_type（high_risk → risk / sensitive → sensitive）
 * @param kind 前端词库键
 * @returns 后端 lexicon_type
 */
function kindToType(kind: 'high_risk' | 'sensitive'): 'risk' | 'sensitive' {
  return kind === 'high_risk' ? 'risk' : 'sensitive'
}

/**
 * 函数级注释：ISO 时间格式化（YYYY-MM-DD HH:mm；空值回退 --）
 * @param iso ISO8601 字符串
 * @returns 展示时间
 */
function fmtTime(iso?: string): string {
  if (!iso) return '--'
  return String(iso).slice(0, 16).replace('T', ' ')
}

/**
 * 函数级注释：加载词条列表（类型为空时拉取高危+敏感两库合并）并刷新计数
 */
async function loadTerms(): Promise<void> {
  termsLoading.value = true
  try {
    if (activeKind.value) {
      const data: any = await adminApi.lexiconTermList({ type: kindToType(activeKind.value), page: 1, page_size: 100 })
      terms.value = data?.items || data?.list || []
    } else {
      const results = await Promise.allSettled([
        adminApi.lexiconTermList({ type: 'risk', page: 1, page_size: 100 }),
        adminApi.lexiconTermList({ type: 'sensitive', page: 1, page_size: 100 }),
      ])
      const merged: any[] = []
      results.forEach((r) => {
        if (r.status === 'fulfilled') {
          const d: any = r.value
          merged.push(...(d?.items || d?.list || []))
        }
      })
      terms.value = merged
    }
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '词条加载失败')
    terms.value = []
  } finally {
    termsLoading.value = false
  }
}

/**
 * 函数级注释：加载两库条数徽章（进入页面时全量统计一次，失败静默）
 */
async function loadCounts(): Promise<void> {
  for (const kind of ['high_risk', 'sensitive'] as const) {
    try {
      const data: any = await adminApi.lexiconTermList({ type: kindToType(kind), page: 1, page_size: 1 })
      counts[kind] = Number(data?.total ?? (data?.items || []).length)
    } catch {
      // 角标失败静默
    }
  }
}

/** 模式规则 action 元数据（加载时记录，保存时原样回写，避免丢失引擎语义） */
const patternMeta = reactive<Record<string, string>>({
  medicine_dosage_pattern: 'block_or_rewrite',
  diagnosis_pattern: 'rewrite',
  efficacy_pattern: 'rewrite',
})

/**
 * 函数级注释：加载词库配置（GET /admin/lexicon/config 返回全部配置项，按 config_key 取值）
 */
async function loadConfig(): Promise<void> {
  try {
    const data: any = await adminApi.lexiconConfigList()
    const items: any[] = data?.items || []
    const valueOf = (key: string): any => items.find((i) => i.config_key === key)?.config_value || {}
    const th = valueOf('two_level_threshold')
    config.threshold_low = Number(th.gray_low ?? 0.5)
    config.threshold_high = Number(th.gray_high ?? 0.8)
    for (const key of ['medicine_dosage_pattern', 'diagnosis_pattern', 'efficacy_pattern'] as const) {
      const v = valueOf(key)
      if (v.action) patternMeta[key] = String(v.action)
    }
    config.pattern_drug = valueOf('medicine_dosage_pattern').pattern || ''
    config.pattern_diagnosis = valueOf('diagnosis_pattern').pattern || ''
    config.pattern_efficacy = valueOf('efficacy_pattern').pattern || ''
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '配置加载失败')
  }
}

/**
 * 函数级注释：打开新增词条弹窗（清空表单）
 */
function openAddTerm(): void {
  newTerm.term = ''
  newTerm.policy = 'block'
  addVisible.value = true
}

/**
 * 函数级注释：新增词条（提交到当前类型库；类型为"全部"时默认高危库）
 */
async function handleAddTerm(): Promise<void> {
  if (!newTerm.term.trim()) {
    ElMessage.warning('请输入词条')
    return
  }
  adding.value = true
  try {
    await adminApi.lexiconTermCreate({
      term: newTerm.term.trim(),
      lexicon_type: kindToType(activeKind.value === 'sensitive' ? 'sensitive' : 'high_risk'),
      strategy: newTerm.policy,
      effective: true,
    })
    ElMessage.success('词条已新增')
    addVisible.value = false
    newTerm.term = ''
    loadTerms()
    loadCounts()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '新增失败')
  } finally {
    adding.value = false
  }
}

/**
 * 函数级注释：打开编辑词条弹窗
 * @param row 词条行数据
 */
function openEditTerm(row: any): void {
  editRow.id = row.id
  editRow.term = row.term
  editRow.policy = row.strategy || 'block'
  editRow.enabled = row.effective !== false
  editVisible.value = true
}

/**
 * 函数级注释：保存词条编辑
 */
async function confirmEditTerm(): Promise<void> {
  savingTerm.value = true
  try {
    await adminApi.lexiconTermUpdate(editRow.id, { strategy: editRow.policy, effective: editRow.enabled })
    ElMessage.success('已保存')
    editVisible.value = false
    loadTerms()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '保存失败')
  } finally {
    savingTerm.value = false
  }
}

/**
 * 函数级注释：删除词条（危险操作，二次确认；DELETE 携带 confirm_token）
 * @param row 词条行数据
 */
async function handleDeleteTerm(row: any): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除词条「${row.term}」？删除后立即影响线上拦截行为。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await adminApi.lexiconTermDelete(row.id)
    ElMessage.success('已删除')
    loadTerms()
    loadCounts()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '删除失败')
  }
}

/**
 * 函数级注释：打开配置编辑弹窗（阈值 + 三正则）
 */
function openConfigEdit(): void {
  configEditVisible.value = true
}

/**
 * 函数级注释：保存两级判定配置（原因弹窗留痕 → withConfirm 自动处理 1602 二次确认）
 */
async function handleSaveConfig(): Promise<void> {
  if (!config.pattern_drug.trim() && !config.pattern_diagnosis.trim() && !config.pattern_efficacy.trim()) {
    ElMessage.warning('请至少配置一个模式规则正则')
    return
  }
  let reason = ''
  try {
    const r: any = await ElMessageBox.prompt('请填写本次配置变更原因（写入审计日志）', '变更原因', {
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputValidator: (v: string) => (v && v.trim() ? true : '原因必填'),
    })
    reason = r.value.trim()
  } catch {
    return
  }
  configSaving.value = true
  try {
    // 按后端 RiskRuleConfig 契约逐键保存：two_level_threshold + 三条模式正则
    await withConfirm(
      async (confirmToken?: string) => {
        const put = (key: string, value: Record<string, any>) =>
          adminApi.lexiconConfigPut(key, { config_value: value, reason, confirm_token: confirmToken })
        await put('two_level_threshold', { gray_low: config.threshold_low, gray_high: config.threshold_high })
        await put('medicine_dosage_pattern', { pattern: config.pattern_drug, action: patternMeta.medicine_dosage_pattern })
        await put('diagnosis_pattern', { pattern: config.pattern_diagnosis, action: patternMeta.diagnosis_pattern })
        await put('efficacy_pattern', { pattern: config.pattern_efficacy, action: patternMeta.efficacy_pattern })
      },
      { message: '词库/阈值变更将直接影响线上拦截行为，保存后 1 分钟内全量生效。确认保存？' }
    )
    ElMessage.success('配置已保存')
    configEditVisible.value = false
    loadConfig()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '保存失败')
  } finally {
    configSaving.value = false
  }
}

/**
 * 函数级注释：复制核心捕获表达式到剪贴板
 */
async function copyPattern(): Promise<void> {
  if (!config.pattern_drug) {
    ElMessage.warning('尚未配置药名剂量正则')
    return
  }
  try {
    await navigator.clipboard.writeText(config.pattern_drug)
    ElMessage.success('表达式已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

/**
 * 函数级注释：规则测试器输入防抖（400ms）后即时调用 /admin/lexicon/test
 */
watch(testText, (v) => {
  if (testTimer) clearTimeout(testTimer)
  testTimer = setTimeout(async () => {
    if (!v.trim()) {
      testResult.value = null
      return
    }
    try {
      testResult.value = await adminApi.lexiconTest(v)
    } catch {
      // 测试器失败静默，不打断输入
    }
  }, 400)
})

/**
 * 函数级注释：打开批量导入弹窗
 */
function openBatchImport(): void {
  importText.value = ''
  importVisible.value = true
}

/**
 * 函数级注释：批量导入（每行一词，逐条提交；统计成功/失败数）
 */
async function confirmImport(): Promise<void> {
  const lines = importText.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
  if (lines.length === 0) {
    ElMessage.warning('请输入至少一个词条')
    return
  }
  importing.value = true
  const kind = activeKind.value === 'sensitive' ? 'sensitive' : 'high_risk'
  let ok = 0
  const failed: string[] = []
  for (const term of lines) {
    try {
      await adminApi.lexiconTermCreate({ term, lexicon_type: kindToType(kind), strategy: newTerm.policy || 'block', effective: true })
      ok++
    } catch {
      failed.push(term)
    }
  }
  importing.value = false
  importVisible.value = false
  ElMessage({
    type: failed.length ? 'warning' : 'success',
    message: `导入完成：成功 ${ok} 条${failed.length ? `，失败 ${failed.length} 条（${failed.slice(0, 3).join('、')}${failed.length > 3 ? '…' : ''}）` : ''}`,
  })
  loadTerms()
  loadCounts()
}

/**
 * 函数级注释：打开配置变更历史抽屉并加载
 */
async function openHistory(): Promise<void> {
  historyVisible.value = true
  historyLoading.value = true
  try {
    const data: any = await adminApi.configHistory(CONFIG_KEY)
    historyRows.value = data?.list || data?.items || data || []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '变更历史加载失败')
    historyRows.value = []
  } finally {
    historyLoading.value = false
  }
}

/**
 * 函数级注释：一键回滚配置到指定版本（二次确认 + confirm_token）
 * @param targetVersion 目标版本号
 */
async function handleRollback(targetVersion: number): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认将词库配置回滚到 v${targetVersion}？回滚立即影响线上拦截行为。`,
      '二次确认',
      { type: 'warning', confirmButtonText: '确认回滚', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await adminApi.configRollback(CONFIG_KEY, { target_version: targetVersion, confirm_token: CONFIRM_TOKEN })
    ElMessage.success('已回滚')
    historyVisible.value = false
    loadConfig()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '回滚失败')
  }
}

onMounted(() => {
  loadTerms()
  loadCounts()
  loadConfig()
})

onBeforeUnmount(() => {
  if (testTimer) clearTimeout(testTimer)
})
</script>

<style scoped>
/* 页面纵向排布 */
.lexicon-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------- 1. 页头卡 ---------- */
.head-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 24px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
  min-width: 0;
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.35;
}

.head-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.head-sep {
  width: 1px;
  height: 32px;
  background: var(--line);
}

/* 类型计数徽章组（高危/敏感，真实统计） */
.kind-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
}

.kind-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-2);
  font-size: var(--fs-sub);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.kind-tab:hover:not(.active) {
  background: var(--surface);
  color: var(--ink-1);
}

.kind-tab.active {
  border-color: var(--accent-line);
  background: var(--surface);
  color: var(--accent);
  font-weight: 500;
  box-shadow: var(--shadow-e1);
}

.kt-count {
  padding: 0 6px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 600;
  line-height: 18px;
}

.kt-count.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.kind-tab.active .kt-count {
  background: var(--surface-2);
}

.head-actions {
  display: flex;
  gap: 8px;
}

/* ---------- 2. 筛选行卡 ---------- */
.filter-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
}

.ff {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ff label {
  font-size: var(--fs-sub);
  color: var(--ink-3);
  white-space: nowrap;
}

.ff .el-select {
  width: 130px;
}

.ff.grow {
  flex: 1;
  justify-content: flex-end;
}

.ff.grow .el-input {
  width: 260px;
}

/* ---------- 3. 词条表卡 ---------- */
.table-card {
  padding: 0;
  overflow: hidden;
}

.term-name {
  color: var(--ink-1);
  font-weight: 500;
}

.policy-text {
  font-weight: 500;
}

.policy-text.c-danger {
  color: var(--danger);
}

.policy-text.c-warn {
  color: var(--warn);
}

.policy-text.c-ink2 {
  color: var(--ink-2);
}

.policy-text.c-ink3 {
  color: var(--ink-3);
}

/* 阈值档 chip */
.tier-chip {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  font-weight: 600;
}

.tier-chip.tier-high {
  background: var(--surface-2);
  color: var(--ink-1);
}

.tier-chip.tier-mid {
  background: var(--warn-soft);
  color: var(--warn);
}

.tier-chip.tier-rule {
  background: var(--surface-2);
  color: var(--ink-3);
  font-weight: 400;
}

.muted {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 24px;
  background: var(--sc-low);
  border-top: 1px solid var(--line);
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* ---------- 4. 两级判定配置卡 ---------- */
.cfg-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
}

.sec-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}

.cap-note {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-family: var(--font-numeric);
}

.scale-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  border-radius: var(--radius-face);
  background: var(--sc-low);
  border: 1px solid var(--line);
}

.scale-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--ink-2);
}

.scale-range {
  color: var(--ink-3);
  font-weight: 400;
}

/* 三段色带 */
.scale-band {
  display: flex;
  height: 26px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--line-strong);
}

.band {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.band + .band {
  border-left: 1px solid var(--line);
}

.band span {
  padding: 0 6px;
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
}

.band-safe {
  background: var(--accent-soft);
  color: var(--accent);
}

.band-mid {
  background: var(--warn-soft);
  color: var(--warn);
}

.band-high {
  background: var(--danger-soft);
  color: var(--danger);
}

/* 刻度标注 */
.scale-ticks {
  position: relative;
  height: 30px;
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.tick {
  position: absolute;
  top: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  transform: translateX(-50%);
  white-space: nowrap;
}

.tick.start {
  left: 0;
  transform: none;
  align-items: flex-start;
}

.tick.end {
  left: 100%;
  transform: translateX(-100%);
  align-items: flex-end;
}

.tick i {
  width: 1px;
  height: 6px;
  margin-bottom: 2px;
  background: var(--line-strong);
}

/* 三策略说明子卡 */
.tier-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 4px;
}

.tier-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: var(--radius-ctl);
  background: var(--surface);
  border: 1px solid var(--line);
}

.tc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tc-badge {
  padding: 2px 8px;
  border-radius: 4px;
  color: #fff;
  font-size: var(--fs-caption);
  font-weight: 600;
}

.tc-badge.danger {
  background: var(--danger);
}

.tc-badge.warn {
  background: var(--warn);
}

.tc-badge.gray {
  background: var(--ink-2);
}

.tc-side {
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.tc-name {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
}

.tc-desc {
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.7;
}

/* ---------- 5. 正则引擎卡 ---------- */
.regex-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
}

.regex-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
  align-items: start;
}

.rg-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.rg-label {
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-2);
}

.regex-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line-strong);
}

.rg-code {
  color: var(--brand-primary);
  font-weight: 600;
  font-size: var(--fs-sub);
  word-break: break-all;
}

.copy-btn {
  flex: none;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.copy-btn:hover {
  background: var(--surface-2);
  color: var(--accent);
}

.rg-desc {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.rg-desc-ico {
  color: var(--accent);
}

.rt-row {
  margin-top: 4px;
}

/* 即时命中结果行 */
.rt-result {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: var(--fs-caption);
}

.rt-result.bad {
  background: var(--danger-soft);
  color: var(--danger);
}

.rt-result.ok {
  background: var(--accent-soft);
  color: var(--accent);
}

.rt-flag {
  font-weight: 700;
}

.rt-flag.pass {
  color: var(--accent);
}

.rt-item {
  color: var(--ink-2);
}

.rg-side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 28px;
}

.rg-btn {
  width: 120px;
}

/* ---------- 6. 底部操作条 ---------- */
.foot-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 24px;
}

.foot-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.foot-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.foot-meta {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.warn-note {
  background: var(--warn-soft);
  border-color: var(--line-strong);
  color: var(--warn);
}

.warn-note .note-ico {
  color: var(--warn);
}

/* ---------- 弹窗 ---------- */
.dialog-tip {
  margin: 0 0 10px;
  color: var(--ink-2);
  font-size: var(--fs-sub);
}

.tip-inline {
  margin-left: 10px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

@media (max-width: 960px) {
  .meta-grid,
  .tier-cards {
    grid-template-columns: 1fr;
  }
  .regex-grid {
    grid-template-columns: 1fr;
  }
  .rg-side {
    flex-direction: row;
    padding-top: 0;
  }
}

/* 手机窄屏（375 视口）：筛选控件纵排全宽、页头收紧，消除横向滚动 */
@media (max-width: 640px) {
  .head-card {
    padding: 12px 16px;
  }
  .head-left {
    gap: 12px;
  }
  .head-sep {
    display: none;
  }
  .kind-tabs {
    flex-wrap: wrap;
  }
  .head-actions {
    flex-wrap: wrap;
  }
  .filter-card {
    flex-wrap: wrap;
    row-gap: 10px;
    padding: 12px 16px;
  }
  .ff {
    flex: 1 1 100%;
  }
  .ff .el-select {
    flex: 1;
    width: auto;
    min-width: 0;
  }
  .ff.grow {
    flex: 1 1 100%;
    justify-content: flex-start;
  }
  .ff.grow .el-input {
    flex: 1;
    width: auto;
    min-width: 0;
  }
  .table-foot {
    padding: 12px 16px;
  }
}
</style>
