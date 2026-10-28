<!--
  文件级注释：PA-07 高风险事件值班复核与内容追溯处置页（Stitch 稿 _5 全量重构）
  - 页头卡：红盾图标 + 高风险事件 + 今日 N 起/待复核 n 徽章 + 副标 + 导出事件清单（前端 CSV）
  - 筛选行：时间/类别/处置下拉 + 过滤按钮（本地过滤）+ 规则引擎运行行
  - 事件表：事件号/时间/命中类别 chip/置信度分档（score_band）/层级标签/来源场景/处置状态/操作
    （缺陷 N2：列表字段为 category_code / score_band，「查看」改为打开详情弹窗）
  - 事件详情弹窗：GET /admin/risk-events/{event_no} 全字段（事件号/类别/级别/分档/来源场景/
    处置结论/正文是否产出/响应字节/SLA/时间/用户哈希/会话/命中规则/上报状态）
  - 复核与处置决策卡（选中行展开，绿边框+焦点锚点）：复核 SLA 徽章（created_at+24h 实算）
    + 触发句段脱敏只读 + 复核结论三选 + 理由枚举必填（原逻辑）+ 上报主管部门展开区
    （勾选显示上报对象/上报时间/留痕责任人；上报按钮 disposal_result 为空时置灰——原 1103 门控）
    + 暂存并保持静默 / 确认提交处置结论（POST /admin/risk-events/{no}/review）
  - 内容追溯处置区（trace-tasks）：任务切换 chips + 来源条目/影响面统计 + 分级 A/B/C 单选
    + 查看影响清单 + 执行处置（二次确认 + confirm_token，POST /admin/trace-tasks/{id}/dispose）
  - 底部误报回流抽检提示条（st-note）
-->
<template>
  <div class="risk-page">
    <!-- ═══ 1. 页头卡 ═══ -->
    <section class="st-card head-card">
      <div class="head-left">
        <div class="shield-ico">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 2L4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z"
              fill="currentColor"
            />
            <path
              d="M12 8v5m0 3h.01"
              fill="none"
              stroke="var(--surface)"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        </div>
        <div class="head-text">
          <div class="head-line">
            <h1 class="head-title">高风险事件</h1>
            <div class="count-pill">
              <span>今日 <strong class="numeric">{{ todayCount }}</strong> 起</span>
              <span class="v-sep">|</span>
              <span class="danger-num">待复核 <strong class="numeric">{{ pendingCount }}</strong></span>
            </div>
          </div>
          <p class="head-sub">涉童涉危内容硬拦截 · 人工复核 · 处置全程留痕可溯源</p>
        </div>
      </div>
      <el-button :icon="Download" @click="exportCsv">导出事件清单</el-button>
    </section>

    <!-- ═══ 2. 筛选行卡 ═══ -->
    <section class="st-card filter-card">
      <div class="filter-fields">
        <div class="f-field">
          <label>时间</label>
          <el-select v-model="draftFilters.time" class="f-ctrl">
            <el-option label="全部时间" value="" />
            <el-option label="今日 (24h)" value="today" />
            <el-option label="近7天" value="7d" />
            <el-option label="近30天" value="30d" />
          </el-select>
        </div>
        <div class="f-field">
          <label>类别</label>
          <el-select v-model="draftFilters.category" class="f-ctrl">
            <el-option label="全部类别" value="" />
            <el-option v-for="(v, k) in CATEGORY_MAP" :key="k" :label="v" :value="k" />
          </el-select>
        </div>
        <div class="f-field">
          <label>处置</label>
          <el-select v-model="draftFilters.status" class="f-ctrl">
            <el-option label="全部状态" value="" />
            <el-option label="待复核" value="pending" />
            <el-option label="已处置" value="done" />
          </el-select>
        </div>
        <el-button type="primary" :icon="Filter" @click="applyFilters">过滤</el-button>
      </div>
      <div class="engine-line">
        <span class="ok-dot"></span>
        <span>规则引擎运行中</span>
      </div>
    </section>

    <!-- ═══ 3. 事件表卡 ═══ -->
    <section class="st-card table-card">
      <el-table
        :data="filteredEvents"
        class="st-table"
        v-loading="eventsLoading"
        :row-class-name="rowClassName"
        @row-click="toggleReview"
      >
        <el-table-column label="事件号" width="130">
          <template #default="{ row }">
            <span class="no-cell numeric" :class="{ picked: isPicked(row) }">{{ row.event_no }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="110">
          <template #default="{ row }">
            <span class="time-cell numeric">{{ fmtTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="命中类别" width="150">
          <template #default="{ row }">
            <span class="st-tag st-tag--plain" :class="categoryTagClass(row.category_code)">
              {{ categoryLabel(row.category_code) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="置信度 / 分档" width="150">
          <template #default="{ row }">
            <span class="st-tag" :class="scoreBandTagClass(row.score_band)">{{ scoreBandLabel(row.score_band) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="层级" width="130">
          <template #default="{ row }">
            <span class="st-tag st-tag--plain" :class="levelTagClass(row.level)">{{ levelLabel(row.level) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源场景" width="110">
          <template #default="{ row }">{{ sceneLabel(row.source_scene) }}</template>
        </el-table-column>
        <el-table-column label="处置状态" width="140">
          <template #default="{ row }">
            <span class="st-tag" :class="row.disposal_result ? 'st-tag--gray' : 'st-tag--amber'">
              {{ disposalLabel(row.disposal_result) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="right">
          <template #default="{ row }">
            <!-- N2 修复：行内「查看」改为打开详情弹窗（GET /admin/risk-events/{event_no}） -->
            <el-button link type="primary" size="small" @click.stop="openDetail(row)">查看</el-button>
            <el-button v-if="!isPicked(row)" link type="primary" size="small" @click.stop="toggleReview(row)">复核</el-button>
            <span v-else class="st-chip-btn">复核处置中</span>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </section>

    <!-- ═══ 4. 复核与处置决策卡（选中事件展开，绿边框） ═══ -->
    <section v-if="currentEvent" class="review-panel">
      <div class="focus-anchor">
        <el-icon><Stamp /></el-icon>
        <span>当前值班复核焦点</span>
      </div>
      <div class="panel-head">
        <div class="panel-title-wrap">
          <el-icon class="head-ico"><CircleCheck /></el-icon>
          <h2 class="panel-title">
            复核与处置决策 · <span class="numeric">{{ currentEvent.event_no }}</span>（{{ categoryLabel(currentEvent.category_code) }}）
          </h2>
        </div>
        <div class="sla-pill">
          <el-icon><Timer /></el-icon>
          <span>复核 SLA：24 小时（<strong class="numeric" :class="{ danger: remainHours <= 0 }">{{ remainText }}</strong>）</span>
        </div>
      </div>

      <!-- 触发上下文（脱敏只读） -->
      <div class="context-box">
        <div class="context-meta">
          <span>
            触发对话段落哈希:
            <span class="numeric">#{{ contextHash }}</span>
          </span>
          <span>模型判定依据: 包含未成年极端心理自损暗示关键词组合</span>
        </div>
        <blockquote class="context-quote">
          {{ currentEvent.summary || currentEvent.context || '（无上下文快照）' }}
        </blockquote>
      </div>

      <!-- 复核结论三选 -->
      <div class="decision-row">
        <span class="form-label">复核结论：</span>
        <el-radio-group v-model="reviewForm.conclusion">
          <el-radio value="upheld">维持阻断</el-radio>
          <el-radio value="misreport">判定误报</el-radio>
          <el-radio value="need_more">需补充信息</el-radio>
        </el-radio-group>
        <el-select v-model="reviewForm.reason_code" class="reason-select" placeholder="复核理由（必填）">
          <el-option v-for="r in currentReasons" :key="r.value" :label="r.label" :value="r.value" />
        </el-select>
        <el-input
          v-model="reviewForm.note"
          class="note-input"
          type="textarea"
          :rows="1"
          placeholder="补充说明（可选）"
        />
      </div>

      <!-- 上报主管部门展开区 -->
      <div class="report-box">
        <el-checkbox v-model="reportExpanded" class="report-check">
          <span class="report-check-text">
            上报主管部门（启动跨部门未成年人紧急心理防护协作）
          </span>
        </el-checkbox>
        <div v-if="reportExpanded" class="report-grid">
          <div class="r-field">
            <label>上报对象</label>
            <el-input v-model="reportedTarget" placeholder="如：当地未成年人保护专班 / 12377 平台" />
          </div>
          <div class="r-field">
            <label>上报时间</label>
            <div class="r-static numeric">{{ nowText }}</div>
          </div>
          <div class="r-field">
            <label>留痕责任人</label>
            <div class="r-static">
              <span>{{ currentEvent.duty_officer || adminName }}</span>
              <el-icon class="r-verified"><CircleCheck /></el-icon>
            </div>
          </div>
        </div>
        <div v-if="reportExpanded" class="report-actions">
          <el-tooltip :disabled="!!currentEvent.disposal_result" content="复核结论出具前不可上报" placement="top">
            <span>
              <el-button
                type="danger"
                plain
                size="small"
                :disabled="!currentEvent.disposal_result"
                :loading="reporting"
                @click="confirmReport"
              >
                确认上报
              </el-button>
            </span>
          </el-tooltip>
        </div>
      </div>

      <!-- 面板底部确认栏 -->
      <div class="panel-foot">
        <span class="foot-tip">该复核行为将计入网络安全国家级风控专网审计日志，责任终身倒查。</span>
        <div class="foot-btns">
          <el-button @click="stashReview">暂存并保持静默</el-button>
          <el-button type="primary" :icon="Select" :loading="reviewing" @click="confirmReview">
            确认提交处置结论
          </el-button>
        </div>
      </div>
    </section>

    <!-- ═══ 5. 内容追溯处置区（按 kb_id 反查受影响内容） ═══ -->
    <section class="st-card trace-card">
      <div class="trace-head">
        <div class="trace-title">
          <el-icon><Search /></el-icon>
          <h2>内容追溯处置（按 kb_id 反查受影响内容）</h2>
        </div>
        <span class="trace-model">溯源图谱反向遍历模型：BFS-v2</span>
      </div>

      <!-- 任务切换 chips（多任务时） -->
      <div v-if="traceTasks.length > 1" class="trace-chips">
        <button
          v-for="t in traceTasks"
          :key="t.id"
          type="button"
          class="trace-chip"
          :class="{ active: activeTraceId === t.id }"
          @click="activeTraceId = t.id"
        >
          <span class="numeric">#{{ t.id }}</span>
          <span class="numeric">{{ t.kb_id }}</span>
          <span v-if="t.disposed_at" class="chip-done">已处置</span>
        </button>
      </div>

      <template v-if="activeTrace">
        <!-- 来源条目与影响面统计 -->
        <div class="trace-info">
          <div class="ti-col">
            <span class="ti-label">来源条目：</span>
            <div class="ti-line">
              <span class="numeric ti-kb">{{ activeTrace.kb_id }}</span>
              <span class="ti-name">{{ activeTrace.trigger || activeTrace.trigger_source || '知识条目' }}</span>
              <span v-if="!activeTrace.disposed_at" class="st-tag st-tag--red">风险下架</span>
              <span v-else class="st-tag st-tag--green">已处置</span>
            </div>
          </div>
          <div class="ti-col">
            <span class="ti-label">影响面统计：</span>
            <div class="ti-line">
              <span class="ti-stat">
                <el-icon><ChatLineSquare /></el-icon>
                历史问答 <strong class="numeric">{{ activeTrace.qa_count ?? '--' }}</strong> 条
              </span>
              <span class="v-sep">/</span>
              <span class="ti-stat">
                <el-icon><Document /></el-icon>
                测评报告 <strong class="numeric">{{ activeTrace.report_count ?? '--' }}</strong> 份
              </span>
            </div>
            <span v-if="traceImpactText" class="ti-impact">{{ traceImpactText }}</span>
          </div>
        </div>

        <!-- 分级处置单选 -->
        <div class="level-row">
          <span class="form-label">分级处置：</span>
          <el-radio-group v-model="activeTrace._dispose_level">
            <el-radio value="A">A 级 无影响</el-radio>
            <el-radio value="B">B 级 追溯加提示（向历史问答生成卡片标注科学勘误说明）</el-radio>
            <el-radio value="C">C 级 批量下架</el-radio>
          </el-radio-group>
        </div>
      </template>
      <el-empty v-else-if="!traceLoading" description="暂无追溯任务" :image-size="60" />

      <!-- 底部时限与执行条 -->
      <div class="trace-foot">
        <div class="deadline-tip">
          <el-icon class="warn-ico"><AlarmClock /></el-icon>
          <span>
            闭环时限：<strong>7 个工作日内全部完成处置</strong>（医疗养育知识纠偏专则）
          </span>
        </div>
        <div class="trace-btns">
          <el-button :icon="List" :disabled="!activeTrace" @click="traceListVisible = true">查看影响清单</el-button>
          <el-button
            type="primary"
            :icon="CaretRight"
            :disabled="!activeTrace || !!activeTrace?.disposed_at"
            @click="handleDispose(activeTrace)"
          >
            {{ activeTrace?.disposed_at ? '已处置' : '执行处置' }}
          </el-button>
        </div>
      </div>
    </section>

    <!-- ═══ 6. 误报回流抽检提示条 ═══ -->
    <footer class="st-note">
      <el-icon class="note-ico"><RefreshLeft /></el-icon>
      <div>
        <strong>误报回流抽检：</strong>
        判定误报的事件将自动进入回流抽检池，按周抽样复核并校准规则引擎阈值；抽检结论同步计入审计日志。
      </div>
    </footer>

    <!-- 事件详情弹窗（缺陷 N2：行内「查看」打开详情；字段来自 GET /admin/risk-events/{event_no}） -->
    <el-dialog v-model="detailVisible" :title="`事件详情 · ${detail?.event_no || ''}`" width="680px">
      <div v-loading="detailLoading" class="detail-wrap">
        <el-descriptions v-if="detail" :column="2" size="small" border>
          <el-descriptions-item label="事件号">
            <span class="numeric">{{ detail.event_no }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="发生时间">
            <span class="numeric">{{ fmtFullTime(detail.created_at) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="命中类别">
            <span class="st-tag st-tag--plain" :class="categoryTagClass(detail.category_code)">
              {{ categoryLabel(detail.category_code) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="级别">
            <span class="st-tag st-tag--plain" :class="levelTagClass(detail.level)">{{ levelLabel(detail.level) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="置信度 / 分档">
            <span class="st-tag" :class="scoreBandTagClass(detail.score_band)">{{ scoreBandLabel(detail.score_band) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="来源场景">{{ sceneLabel(detail.source_scene) }}</el-descriptions-item>
          <el-descriptions-item label="处置结论">{{ disposalLabel(detail.disposal_result) }}</el-descriptions-item>
          <el-descriptions-item label="正文是否产出">{{ detail.body_emitted ? '已产出' : '未产出' }}</el-descriptions-item>
          <el-descriptions-item label="响应字节">
            <span class="numeric">{{ detail.response_bytes ?? '--' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="复核 SLA 截止">
            <span class="numeric">{{ fmtFullTime(detail.sla_due_at) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="用户哈希">
            <span class="numeric">{{ detail.user_id_hash || '--' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="会话 ID">
            <span class="numeric">{{ detail.session_id || '--' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="命中规则 ID">
            <span class="numeric">{{ detail.rule_hit_id || '--' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="复核时间">
            <span class="numeric">{{ fmtFullTime(detail.reviewed_at) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="已上报监管部门" :span="2">
            {{ detail.reported ? `是（${detail.reported_target || '上报对象未记录'}）` : '否' }}
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else-if="!detailLoading" description="暂无详情数据" :image-size="60" />
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="reviewFromDetail">进入复核</el-button>
      </template>
    </el-dialog>

    <!-- 影响清单弹窗 -->
    <el-dialog v-model="traceListVisible" title="受影响内容清单" width="480px">
      <template v-if="activeTrace">
        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="任务号">#{{ activeTrace.id }}</el-descriptions-item>
          <el-descriptions-item label="kb_id">{{ activeTrace.kb_id }}</el-descriptions-item>
          <el-descriptions-item label="触发来源">{{ activeTrace.trigger || activeTrace.trigger_source || '--' }}</el-descriptions-item>
          <el-descriptions-item label="影响面">{{ activeTrace.impact || activeTrace.impact_scope || '--' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ activeTrace.created_at || '--' }}</el-descriptions-item>
          <el-descriptions-item label="处置状态">{{ activeTrace.disposed_at ? `已处置（${activeTrace.disposed_at}）` : '待处置' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer>
        <el-button @click="traceListVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。事件复核流（结论+理由枚举）、上报门控（disposal_result 置灰）、
 * 内容追溯分级处置；筛选/导出为前端本地实现，复核与追溯 API 与原逻辑一致。
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  AlarmClock,
  CaretRight,
  ChatLineSquare,
  CircleCheck,
  Document,
  Download,
  Filter,
  List,
  RefreshLeft,
  Search,
  Select,
  Stamp,
  Timer,
} from '@element-plus/icons-vue'
import { adminApi, ApiError, CONFIRM_TOKEN, downloadBlob, getAdminInfo } from '../../api/admin'

/** 事件列表 */
const events = ref<any[]>([])
/** 事件加载中 */
const eventsLoading = ref(false)
/** 追溯任务列表 */
const traceTasks = ref<any[]>([])
/** 追溯加载中 */
const traceLoading = ref(false)
/** 当前时间（驱动复核 SLA 徽章，30s 刷新） */
const now = ref(Date.now())
/** SLA 定时器 */
let slaTimer: ReturnType<typeof setInterval> | null = null

/** 复核面板：当前选中事件 */
const currentEvent = ref<any>(null)
/** 事件详情弹窗可见性（缺陷 N2：行内「查看」） */
const detailVisible = ref(false)
/** 事件详情加载中 */
const detailLoading = ref(false)
/** 事件详情（GET /admin/risk-events/{event_no} 全字段） */
const detail = ref<any>(null)
/** 复核表单（结论/理由枚举/备注——理由必填为原约定） */
const reviewForm = reactive({ conclusion: 'upheld', reason_code: '', note: '' })
/** 复核提交中 */
const reviewing = ref(false)

/** 上报主管部门展开区勾选态 */
const reportExpanded = ref(false)
/** 上报对象（必填） */
const reportedTarget = ref('')
/** 上报提交中 */
const reporting = ref(false)

/** 影响清单弹窗可见性 */
const traceListVisible = ref(false)
/** 当前选中的追溯任务 id */
const activeTraceId = ref<string | number | null>(null)

/** 当前管理员显示名（留痕责任人兜底） */
const adminName = computed(() => getAdminInfo()?.display_name || getAdminInfo()?.username || 'admin')

/** 复核理由枚举（按结论切换） */
const REASON_OPTIONS: Record<string, { value: string; label: string }[]> = {
  upheld: [
    { value: 'hit_high_risk_rule', label: '命中高危规则' },
    { value: 'confidence_high', label: '模型置信度高' },
    { value: 'manual_confirm', label: '人工确认风险属实' },
  ],
  misreport: [
    { value: 'keyword_ambiguous', label: '关键词歧义' },
    { value: 'test_expression', label: '测试性表达' },
    { value: 'context_misjudge', label: '上下文误判' },
  ],
  need_more: [
    { value: 'need_user_info', label: '需补充用户信息' },
    { value: 'need_expert_review', label: '需专家复核' },
    { value: 'need_context', label: '需补充上下文' },
  ],
}

/** 当前结论对应的理由选项 */
const currentReasons = computed(() => REASON_OPTIONS[reviewForm.conclusion] || [])

/** 风险类别枚举展示（键与后端风险引擎类别集对齐；保留历史键兼容旧数据） */
const CATEGORY_MAP: Record<string, string> = {
  // 与 app/risk/engine.py 类别集一致
  child_abuse: '儿童受虐',
  child_selfharm: '儿童自伤',
  high_fever: '儿童急症',
  animal_bite: '动物咬伤',
  depression: '抑郁情绪',
  pet_poison: '宠物中毒',
  pet_bleeding: '宠物出血',
  medicine_dosage: '用药剂量',
  diagnosis: '医疗诊断',
  efficacy: '疗效承诺',
  fortune: '命理迷信',
  semantic_unavailable: '语义服务异常',
  risk_unavailable: '风险服务不可用',
  // 历史/占位键（旧数据兼容）
  self_harm: '自伤/自杀',
  medical: '医疗风险',
  pet_medical: '宠物医疗',
  other: '其他',
}

/** 筛选草稿条件（点"过滤"后生效） */
const draftFilters = reactive({ time: '', category: '', status: '' })
/** 已应用的筛选条件 */
const appliedFilters = reactive({ time: '', category: '', status: '' })

/**
 * 函数级注释：风险类别转文案
 * @param c 类别枚举
 * @returns 中文文案
 */
function categoryLabel(c: string): string {
  return CATEGORY_MAP[c] || c || '--'
}

/**
 * 函数级注释：命中类别 chip 变体类（自伤/儿童受虐红，医疗/情绪琥珀，其他灰）
 * @param c 类别枚举
 * @returns st-tag 修饰类
 */
function categoryTagClass(c: string): string {
  if (['self_harm', 'child_abuse', 'child_selfharm', 'high_fever', 'animal_bite'].includes(c)) {
    return 'st-tag--red'
  }
  if (
    ['medical', 'pet_medical', 'depression', 'medicine_dosage', 'pet_poison', 'pet_bleeding', 'risk_unavailable'].includes(c)
  ) {
    return 'st-tag--amber'
  }
  return 'st-tag--gray'
}

/**
 * 函数级注释：层级转文案（L1=一级硬拦截 / L2=二级语义拦截）
 * @param level 层级枚举
 * @returns 中文文案
 */
function levelLabel(level: string): string {
  if (level === 'L1') return '一级硬拦截'
  if (level === 'L2') return '二级语义拦截'
  return level || '--'
}

/**
 * 函数级注释：层级标签变体类
 * @param level 层级枚举
 * @returns st-tag 修饰类
 */
function levelTagClass(level: string): string {
  if (level === 'L1') return 'st-tag--red'
  if (level === 'L2') return 'st-tag--amber'
  return 'st-tag--outline'
}

/**
 * 函数级注释：置信度分档转文案（缺陷 N2：列表字段为 score_band，
 * 取值为 rule_hit / high / mid / low，原代码错绑 confidence 导致整列显示 --）
 * @param band 分档枚举
 * @returns 中文文案
 */
function scoreBandLabel(band: any): string {
  if (band === null || band === undefined || band === '') return '--'
  const map: Record<string, string> = {
    rule_hit: '硬规则命中',
    high: '高（≥0.8）',
    mid: '中（0.5-0.8）',
    medium: '中（0.5-0.8）',
    low: '低（<0.5）',
  }
  return map[String(band)] || String(band)
}

/**
 * 函数级注释：置信度分档标签变体类
 * @param band 分档枚举
 * @returns st-tag 修饰类
 */
function scoreBandTagClass(band: any): string {
  if (band === 'rule_hit' || band === 'high') return 'st-tag--red'
  if (band === 'mid' || band === 'medium') return 'st-tag--amber'
  if (band === 'low') return 'st-tag--gray'
  return 'st-tag--outline'
}

/**
 * 函数级注释：事件来源场景转文案
 * @param scene 来源场景（qa / appeal）
 * @returns 中文文案
 */
function sceneLabel(scene: any): string {
  if (!scene) return '--'
  const map: Record<string, string> = { qa: '问答', appeal: '申诉复核' }
  return map[String(scene)] || String(scene)
}

/**
 * 函数级注释：处置结论转文案
 * @param result 处置结论（upheld / misreport / need_more）
 * @returns 中文文案（空值=待复核）
 */
function disposalLabel(result: any): string {
  if (!result) return '待复核'
  const map: Record<string, string> = {
    upheld: '维持阻断',
    misreport: '判定误报',
    need_more: '需补充信息',
  }
  return map[String(result)] || String(result)
}

/**
 * 函数级注释：完整时间格式化（YYYY-MM-DD HH:mm:ss；空值回退 --）
 * @param t 原始时间串
 * @returns 格式化文案
 */
function fmtFullTime(t: any): string {
  if (!t) return '--'
  return String(t).slice(0, 19).replace('T', ' ')
}

/**
 * 函数级注释：事件时间格式化（YYYY-MM-DD HH:mm:ss → MM-DD HH:mm）
 * @param t 原始时间串
 * @returns 格式化文案
 */
function fmtTime(t: string): string {
  if (!t || t.length < 16) return t || '--'
  return t.slice(5, 16)
}

/**
 * 函数级注释：复核 SLA 剩余小时数（优先用后端 sla_due_at；缺失时按 created_at + 24h 实算）
 */
const remainHours = computed(() => {
  const due = currentEvent.value?.sla_due_at
  if (due) {
    const dueAt = new Date(due).getTime()
    if (!Number.isNaN(dueAt)) return (dueAt - now.value) / 3600000
  }
  if (!currentEvent.value?.created_at) return 24
  const created = new Date(currentEvent.value.created_at).getTime()
  if (Number.isNaN(created)) return 24
  return (created + 24 * 3600000 - now.value) / 3600000
})

/**
 * 函数级注释：复核 SLA 剩余文案
 */
const remainText = computed(() => {
  const h = remainHours.value
  if (h <= 0) return `已超时 ${Math.abs(h).toFixed(1)} 小时`
  return `剩余 ${h.toFixed(1)} 小时`
})

/**
 * 函数级注释：触发段落哈希占位（由事件号派生的稳定展示值）
 */
const contextHash = computed(() => {
  const no = String(currentEvent.value?.event_no || '')
  let h = 0
  for (let i = 0; i < no.length; i++) {
    h = (h * 31 + no.charCodeAt(i)) >>> 0
  }
  return h.toString(16).padStart(8, '0')
})

/**
 * 函数级注释：当前时间文案（上报时间只读展示）
 */
const nowText = computed(() => {
  const d = new Date(now.value)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

/**
 * 函数级注释：今日起事件数（created_at 为今天的数量）
 */
const todayCount = computed(() => {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  return events.value.filter((e) => {
    const t = new Date(e.created_at || 0).getTime()
    return t >= start.getTime()
  }).length
})

/**
 * 函数级注释：待复核事件数（disposal_result 为空）
 */
const pendingCount = computed(() => events.value.filter((e) => !e.disposal_result).length)

/**
 * 函数级注释：应用筛选后的事件列表（时间/类别/处置为前端本地过滤）
 */
const filteredEvents = computed(() => {
  const { time, category, status } = appliedFilters
  return events.value.filter((e) => {
    // 缺陷 N2：类别字段为 category_code（原绑 e.category 恒为空 → 筛选永不命中）
    if (category && e.category_code !== category) return false
    if (status === 'pending' && e.disposal_result) return false
    if (status === 'done' && !e.disposal_result) return false
    if (time) {
      const t = new Date(e.created_at || 0).getTime()
      if (!t) return false
      if (time === 'today') {
        const start = new Date()
        start.setHours(0, 0, 0, 0)
        if (t < start.getTime()) return false
      } else {
        const hours = time === '7d' ? 168 : 720
        if (now.value - t > hours * 3600000) return false
      }
    }
    return true
  })
})

/**
 * 函数级注释：应用筛选条件
 */
function applyFilters(): void {
  Object.assign(appliedFilters, draftFilters)
}

/**
 * 函数级注释：行是否处于选中展开态
 * @param row 事件行数据
 * @returns 是否选中
 */
function isPicked(row: any): boolean {
  return currentEvent.value?.event_no === row.event_no
}

/**
 * 函数级注释：表格行类名（选中行高亮）
 * @param param0 { row }
 * @returns 类名
 */
function rowClassName({ row }: { row: any }): string {
  return isPicked(row) ? 'row-selected' : ''
}

/**
 * 函数级注释：打开事件详情弹窗（缺陷 N2：原「查看」按钮只切换复核面板且无反馈，
 * 现改为拉取详情接口并以对话框展示全字段）
 * @param row 事件行数据（列表项字段）
 */
async function openDetail(row: any): Promise<void> {
  detail.value = row
  detailVisible.value = true
  detailLoading.value = true
  try {
    detail.value = await adminApi.riskEventDetail(row.event_no)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '事件详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

/**
 * 函数级注释：从详情弹窗进入复核面板（复用当前详情数据，避免二次请求）
 */
function reviewFromDetail(): void {
  const row = detail.value
  detailVisible.value = false
  if (!row) return
  selectEvent(row)
}

/**
 * 函数级注释：选中事件进入复核面板并重置表单
 * @param row 事件行数据或详情数据
 */
function selectEvent(row: any): void {
  currentEvent.value = row
  reviewForm.conclusion = 'upheld'
  reviewForm.reason_code = ''
  reviewForm.note = ''
  reportExpanded.value = false
  reportedTarget.value = ''
}

/**
 * 函数级注释：切换选中事件（展开/收起复核面板，重置表单）
 * @param row 事件行数据
 */
function toggleReview(row: any): void {
  if (isPicked(row)) {
    currentEvent.value = null
    return
  }
  selectEvent(row)
}

/** 结论切换时清空理由枚举（理由集合不同） */
watch(
  () => reviewForm.conclusion,
  () => {
    reviewForm.reason_code = ''
  }
)

/**
 * 函数级注释：暂存并保持静默（收起面板，不提交）
 */
function stashReview(): void {
  currentEvent.value = null
  ElMessage.info('已暂存，保持静默')
}

/**
 * 函数级注释：提交复核结论（理由枚举必填）
 */
async function confirmReview(): Promise<void> {
  if (!reviewForm.reason_code) {
    ElMessage.warning('请选择复核理由（必填）')
    return
  }
  reviewing.value = true
  try {
    await adminApi.riskEventReview(currentEvent.value.event_no, {
      conclusion: reviewForm.conclusion,
      reason_code: reviewForm.reason_code,
      note: reviewForm.note || undefined,
    })
    ElMessage.success('复核结论已提交')
    currentEvent.value = null
    loadEvents()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '复核提交失败')
  } finally {
    reviewing.value = false
  }
}

/**
 * 函数级注释：确认上报（上报对象必填；disposal_result 为空时入口已置灰，此处双重校验）
 */
async function confirmReport(): Promise<void> {
  if (!currentEvent.value?.disposal_result) {
    ElMessage.warning('复核结论出具前不可上报')
    return
  }
  if (!reportedTarget.value.trim()) {
    ElMessage.warning('请填写上报对象')
    return
  }
  reporting.value = true
  try {
    await adminApi.riskEventReportAuthority(currentEvent.value.event_no, {
      reported_target: reportedTarget.value.trim(),
    })
    ElMessage.success('已上报')
    loadEvents()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '上报失败')
  } finally {
    reporting.value = false
  }
}

/**
 * 函数级注释：当前选中的追溯任务对象
 */
const activeTrace = computed(() => traceTasks.value.find((t) => t.id === activeTraceId.value) || null)

/**
 * 函数级注释：追溯任务影响面补充文本（qa_count/report_count 缺失时回退展示 impact 原文）
 */
const traceImpactText = computed(() => {
  const t = activeTrace.value
  if (!t) return ''
  if (t.qa_count !== undefined || t.report_count !== undefined) return ''
  return t.impact || t.impact_scope || ''
})

/**
 * 函数级注释：加载高风险事件列表
 */
async function loadEvents(): Promise<void> {
  eventsLoading.value = true
  try {
    const data: any = await adminApi.riskEventList({ page: 1, page_size: 100 })
    events.value = data?.list || data?.items || data || []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '事件加载失败')
    events.value = []
  } finally {
    eventsLoading.value = false
  }
}

/**
 * 函数级注释：加载内容追溯任务列表（为每行补充分级选择字段并默认选中第一条）
 */
async function loadTraceTasks(): Promise<void> {
  traceLoading.value = true
  try {
    const data: any = await adminApi.traceTaskList({ page: 1, page_size: 100 })
    const list: any[] = data?.list || data?.items || data || []
    traceTasks.value = list.map((r) => ({ ...r, _dispose_level: r.disposal_level || 'A' }))
    if (!traceTasks.value.some((t) => t.id === activeTraceId.value)) {
      activeTraceId.value = traceTasks.value[0]?.id ?? null
    }
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '追溯任务加载失败')
    traceTasks.value = []
  } finally {
    traceLoading.value = false
  }
}

/**
 * 函数级注释：刷新两个列表
 */
function loadAll(): void {
  loadEvents()
  loadTraceTasks()
}

/**
 * 函数级注释：执行内容追溯分级处置（二次确认 + confirm_token）
 * @param row 追溯任务行数据（_dispose_level 为所选分级）
 */
async function handleDispose(row: any): Promise<void> {
  if (!row) return
  const level = row._dispose_level || 'A'
  try {
    await ElMessageBox.confirm(
      `确认对任务 #${row.id}（kb_id=${row.kb_id}）执行 ${level} 级处置？该操作将影响线上内容。`,
      '二次确认',
      { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await adminApi.traceTaskDispose(row.id, {
      disposal_level: level,
      confirm_token: CONFIRM_TOKEN,
    })
    ElMessage.success('处置已执行')
    loadTraceTasks()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '处置失败')
  }
}

/**
 * 函数级注释：导出事件清单为 CSV（前端本地生成）
 */
function exportCsv(): void {
  const header = ['事件号', '时间', '命中类别', '置信度/分档', '层级', '来源场景', '处置状态']
  const lines = events.value.map((e) => [
    e.event_no,
    fmtTime(e.created_at),
    categoryLabel(e.category_code),
    scoreBandLabel(e.score_band),
    levelLabel(e.level),
    sceneLabel(e.source_scene),
    disposalLabel(e.disposal_result),
  ])
  const csv =
    '\ufeff' +
    [header, ...lines].map((cells) => cells.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `risk-events-${Date.now()}.csv`)
  ElMessage.success('事件清单已导出')
}

onMounted(() => {
  loadAll()
  // 复核 SLA 徽章：每 30s 刷新当前时间
  slaTimer = setInterval(() => {
    now.value = Date.now()
  }, 30000)
})

onBeforeUnmount(() => {
  if (slaTimer) clearInterval(slaTimer)
})
</script>

<style scoped lang="scss">
/* 页面纵向排布 */
.risk-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---------- 页头卡 ---------- */
.head-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 16px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

/* 红盾图标块 */
.shield-ico {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 46px;
  height: 46px;
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  background: var(--danger-soft);
  color: var(--danger);

  svg {
    width: 24px;
    height: 24px;
  }
}

.head-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.head-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

/* 今日/待复核计数胶囊 */
.count-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 3px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: var(--fs-caption);

  strong {
    color: var(--ink-1);
  }

  .danger-num {
    color: var(--danger);
    font-weight: 500;

    strong {
      color: var(--danger);
    }
  }
}

.v-sep {
  color: var(--line-strong);
}

.head-sub {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* ---------- 筛选行卡 ---------- */
.filter-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
}

.filter-fields {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.f-field {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-2);
  font-size: var(--fs-sub);

  label {
    color: var(--ink-3);
    white-space: nowrap;
  }
}

.f-ctrl {
  width: 150px;
}

.engine-line {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.ok-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

/* ---------- 事件表卡 ---------- */
.table-card {
  padding: 0;
  overflow: hidden;
}

.st-table {
  width: 100%;

  :deep(th.el-table__cell) {
    background: var(--surface-2);
    color: var(--ink-3);
    font-size: var(--fs-caption);
    font-weight: 500;
  }

  :deep(td.el-table__cell) {
    padding: 10px 0;
  }

  :deep(tbody tr) {
    cursor: pointer;
  }

  :deep(.row-selected > td.el-table__cell) {
    background: var(--accent-soft);
  }
}

.no-cell {
  color: var(--ink-1);
  font-weight: 500;

  &.picked {
    color: var(--accent);
    font-weight: 700;
  }
}

.time-cell {
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

/* 置信度 + 横向刻度条 */
.conf-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.conf-num {
  font-weight: 600;

  &.conf--danger {
    color: var(--danger);
  }
  &.conf--warn {
    color: var(--warn);
  }
  &.conf--ink {
    color: var(--ink-2);
  }
}

.conf-bar {
  display: inline-block;
  width: 64px;
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  overflow: hidden;
}

.conf-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-pill);

  &.fill--danger {
    background: var(--danger);
  }
  &.fill--warn {
    background: var(--warn);
  }
  &.fill--ink {
    background: var(--line-strong);
  }
}

/* 复核处置中 chip */
.st-chip-btn {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: var(--radius-ctl);
  background: var(--accent);
  color: #fff;
  font-size: var(--fs-caption);
  font-weight: 500;
  white-space: nowrap;
}

/* ---------- 复核与处置决策卡（绿边框） ---------- */
.review-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  border: 2px solid var(--accent);
  border-radius: var(--radius-face);
  background: var(--surface);
}

/* 顶部焦点锚点 */
.focus-anchor {
  position: absolute;
  top: -12px;
  left: 20px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border-radius: var(--radius-ctl);
  background: var(--accent);
  color: #fff;
  font-size: var(--fs-caption);
  font-weight: 600;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  padding-top: 4px;
  border-bottom: 1px solid var(--line);
}

.panel-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-ico {
  color: var(--accent);
  font-size: 20px;
}

.panel-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

/* 复核 SLA 徽章 */
.sla-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--warn);
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  color: var(--warn);
  font-size: var(--fs-sub);

  strong {
    font-weight: 700;

    &.danger {
      color: var(--danger);
    }
  }
}

/* 触发上下文（脱敏只读） */
.context-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
}

.context-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--ink-3);
  font-size: var(--fs-caption);

  .numeric {
    color: var(--ink-2);
  }
}

.context-quote {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-1);
  font-size: var(--fs-body);
  line-height: 1.7;
}

/* 决策行 */
.decision-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.form-label {
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 600;
  white-space: nowrap;
}

.reason-select {
  width: 190px;
}

.note-input {
  flex: 1;
  min-width: 200px;
}

/* 上报主管部门展开区 */
.report-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-bright);
}

.report-check-text {
  color: var(--danger);
  font-weight: 600;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.r-field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    color: var(--ink-2);
    font-size: var(--fs-sub);
    font-weight: 500;
  }
}

.r-static {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-1);
  font-size: var(--fs-sub);
}

.r-verified {
  color: var(--accent);
}

.report-actions {
  display: flex;
  justify-content: flex-end;
}

/* 面板底部确认栏 */
.panel-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.foot-tip {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.foot-btns {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ---------- 内容追溯处置区 ---------- */
.trace-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.trace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}

.trace-title {
  display: flex;
  align-items: center;
  gap: 8px;

  .el-icon {
    color: var(--accent);
    font-size: 20px;
  }

  h2 {
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
  }
}

.trace-model {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* 任务切换 chips */
.trace-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.trace-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-pill);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  cursor: pointer;

  &:hover:not(.active) {
    border-color: var(--line-strong);
    color: var(--ink-1);
  }

  &.active {
    border-color: var(--accent-line);
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }
}

.chip-done {
  color: var(--accent);
}

/* 来源条目与影响面 */
.trace-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
}

.ti-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.ti-label {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.ti-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ti-kb {
  color: var(--ink-1);
  font-weight: 700;
}

.ti-name {
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 500;
}

.ti-stat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-1);
  font-size: var(--fs-sub);

  .el-icon {
    color: var(--accent);
  }

  strong {
    color: var(--accent);
    font-weight: 700;
  }
}

.ti-impact {
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

/* 分级处置单选 */
.level-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

/* 底部时限与执行条 */
.trace-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.deadline-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-3);
  font-size: var(--fs-caption);

  .warn-ico {
    color: var(--warn);
  }

  strong {
    color: var(--ink-1);
    font-weight: 600;
  }
}

.trace-btns {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 手机窄屏（375 视口）：单选纵排、按钮换行、追溯信息单列，消除横向滚动 */
@media (max-width: 640px) {
  .head-card,
  .filter-card {
    padding: 12px 16px;
  }
  .trace-info {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 12px;
  }
  .level-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .level-row :deep(.el-radio-group) {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }
  .level-row :deep(.el-radio) {
    height: auto;
    margin-right: 0;
    white-space: normal;
    align-items: flex-start;
  }
  .trace-btns,
  .foot-btns {
    flex-wrap: wrap;
  }
  .reason-select {
    flex: 1;
    width: auto;
    min-width: 0;
  }
  .note-input {
    min-width: 0;
  }
  .report-grid {
    grid-template-columns: 1fr;
  }
}
</style>
