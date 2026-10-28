<!--
  文件级注释：PA-05 Agent 调用日志页（Stitch 高保真形态）
  - 页头卡：「调用日志」+ 副标（多模型路由决策全链路追溯·毫秒级性能与合规监测）+ 近 24h 量（真实 count）+ 导出 CSV（二次确认）
  - 筛选行：时间 / Agent / 风险 / 冲突 下拉 + 会话 ID / 关键词输入 + 搜索主按钮 + 重置（风险/冲突为前端过滤）
  - 日志表：会话 ID / 时间 / 输入摘要(脱敏) / Agent 标签 chip / 耗时 / 风险 chip / 冲突 chip / 操作（查看详情行内展开）
  - 展开详情（六卡网格）：调度决策（output_json）/ 参与 Agent 状态（agent_call_log 字段）/ 知识库引用（evidence_ref 等宽）/
    风险判定结论 / 审计合规存证（留存 ≥6 个月 + SHA256 字样）/ 运营审计操作（按钮占位置灰）
  - 分页 + 底部脱敏声明（照稿）；CSV 导出二次确认后带 confirm_token 查询参数下载 blob
-->
<template>
  <div class="agent-log-page">
    <!-- 1. 页头卡 -->
    <section class="st-card head-card">
      <div class="head-left">
        <div class="head-ico">
          <el-icon :size="22"><DataAnalysis /></el-icon>
        </div>
        <div class="head-text">
          <div class="head-title-row">
            <h2 class="head-title">调用日志</h2>
            <span v-if="recent24h !== null" class="kpi-chip numeric">近 24h {{ recent24h.toLocaleString() }} 条</span>
          </div>
          <p class="head-sub">多模型路由决策全链路追溯 · 调用耗时与拦截结果记录</p>
        </div>
      </div>
      <el-button :icon="Download" @click="handleExport">导出 CSV</el-button>
    </section>

    <!-- 2. 筛选行卡 -->
    <section class="st-card filter-card">
      <div class="filters">
        <div class="ff">
          <label>时间</label>
          <el-date-picker
            v-model="filters.range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            class="ff-date"
          />
        </div>
        <div class="ff">
          <label>Agent</label>
          <el-select v-model="filters.agent_id" clearable placeholder="全部" class="ff-sel">
            <el-option label="调度器" value="dispatcher" />
            <el-option label="育儿" value="child_care" />
            <el-option label="宠物" value="pet" />
            <el-option label="题库" value="quiz" />
            <el-option label="多智能体" value="multi" />
          </el-select>
        </div>
        <div class="ff">
          <label>风险</label>
          <el-select v-model="filters.risk" clearable placeholder="全部" class="ff-sel-sm">
            <el-option label="命中" value="hit" />
            <el-option label="无" value="none" />
          </el-select>
        </div>
        <div class="ff">
          <label>冲突</label>
          <el-select v-model="filters.conflict" clearable placeholder="全部" class="ff-sel-sm">
            <el-option label="有" value="yes" />
            <el-option label="无" value="no" />
          </el-select>
        </div>
        <div class="ff grow">
          <el-input
            v-model="filters.session_id"
            placeholder="按会话 ID / 关键词..."
            :prefix-icon="Search"
            clearable
            @keyup.enter="handleSearch"
          />
        </div>
      </div>
      <div class="filter-actions">
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
    </section>

    <!-- 3. 日志表卡（行内展开详情） -->
    <section class="st-card table-card">
      <el-table
        ref="tableRef"
        :data="filteredRows"
        v-loading="loading"
        row-key="id"
        class="log-table"
        :expand-row-keys="expandedKeys"
        @expand-change="onExpandChange"
      >
        <!-- 行内展开：六卡网格详情 -->
        <el-table-column type="expand" width="36">
          <template #default="{ row }">
            <div class="exp-panel" v-loading="row._loading">
              <!-- 展开面板头：会话标题 + 链路追踪 ID + 状态徽章 -->
              <div class="exp-head">
                <div class="exp-title">
                  <el-icon class="exp-title-ico"><Share /></el-icon>
                  <h3>会话详情 · {{ row.session_id || '--' }} 链路决策与审计还原</h3>
                </div>
                <div class="exp-badges">
                  <span class="trk-chip numeric">链路追踪ID: {{ traceId(row) }}</span>
                  <span class="st-tag st-tag--plain" :class="statusOk(row) ? 'st-tag--green' : 'st-tag--red'">
                    {{ statusText(row) }}
                  </span>
                </div>
              </div>
              <!-- 六卡网格 -->
              <div class="exp-grid">
                <!-- ① 调度决策（output_json） -->
                <div class="dcard">
                  <div class="dc-head"><el-icon><Guide /></el-icon><span>调度决策</span></div>
                  <div class="dc-box numeric">
                    <div>意图={{ decisionInfo(row).intent }}</div>
                    <div>复合={{ decisionInfo(row).compound }}</div>
                    <div>置信度={{ decisionInfo(row).confidence }}</div>
                    <div>权重版本={{ row._detail?.weight_version ?? row.weight_version ?? '--' }}</div>
                  </div>
                </div>
                <!-- ② 参与 Agent 状态（agent_call_log 字段） -->
                <div class="dcard">
                  <div class="dc-head"><el-icon><User /></el-icon><span>参与 Agent 状态</span></div>
                  <div v-if="agentLines(row).length || agentModel(row)" class="dc-box numeric">
                    <div v-for="(line, i) in agentLines(row)" :key="'a' + i">{{ line }}</div>
                    <div v-if="agentModel(row)">模型载体：{{ agentModel(row) }}</div>
                    <div>输出Token数：{{ agentTokens(row) }}</div>
                  </div>
                  <p v-else class="dc-note">无参与 Agent 记录</p>
                </div>
                <!-- ③ 知识库引用（等宽 evidence_ref） -->
                <div class="dcard">
                  <div class="dc-head"><el-icon><Notebook /></el-icon><span>知识库引用凭证 (等宽体)</span></div>
                  <div v-if="evidenceRefs(row).length" class="dc-box numeric dc-ev">
                    evidence_ref：{{ evidenceRefs(row).join(', ') }}
                  </div>
                  <div v-else class="dc-box numeric dc-ev">evidence_ref：--</div>
                </div>
                <!-- ④ 风险判定结论 -->
                <div class="dcard">
                  <div class="dc-head"><el-icon><CircleCheck /></el-icon><span>风险判定结论</span></div>
                  <div class="dc-box">
                    <div class="risk-line" :class="hasRisk(row) ? 'bad' : 'ok'">
                      <el-icon>
                        <WarningFilled v-if="hasRisk(row)" />
                        <CircleCheckFilled v-else />
                      </el-icon>
                      <span>风险判定：{{ riskText(row) }}</span>
                    </div>
                    <span v-if="riskReason(row)" class="risk-reason">{{ riskReason(row) }}</span>
                    <span v-if="riskHitsText(row)" class="risk-reason">命中风险词：{{ riskHitsText(row) }}</span>
                  </div>
                </div>
                <!-- ⑤ 审计合规存证 -->
                <div class="dcard">
                  <div class="dc-head"><el-icon><Stamp /></el-icon><span>审计合规存证</span></div>
                  <div class="dc-box">
                    <span class="dc-strong">留存期 — 网络日志 ≥6 个月（合规基线）</span>
                    <span class="dc-dim">哈希引用：{{ hashText(row) }}</span>
                  </div>
                  <p class="dc-note">符合《中华人民共和国网络安全法》第 21 条规范要求</p>
                </div>
                <!-- ⑥ 运营审计操作（按钮占位置灰） -->
                <div class="dcard">
                  <div class="dc-head"><el-icon><Search /></el-icon><span>运营审计操作</span></div>
                  <p class="dc-note">如需发起专家人工评审或对本条对话结论进行重训微调标定，可点击提交质检工单。</p>
                  <div class="dc-actions">
                    <el-button size="small" disabled>查看原始 Token 账单</el-button>
                    <el-button size="small" type="primary" disabled>创建质检标定</el-button>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="session_id" label="会话 ID" width="130">
          <template #default="{ row }">
            <span class="numeric sid">{{ row.session_id || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">
            <span class="numeric time-cell">{{ row.created_at || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="输入摘要(脱敏)" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'sum-hit': hasRisk(row) }">{{ row.input_preview || row.input_summary || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Agent" width="120">
          <template #default="{ row }">
            <span
              v-if="agentLabel(row)"
              class="agent-chip"
              :class="{ multi: row.agent_id === 'multi' || row.agent === 'multi' }"
            >
              {{ agentLabel(row) }}
            </span>
            <span v-else class="muted numeric">--</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="80" align="right">
          <template #default="{ row }">
            <span class="numeric">{{ durationText(row.duration_ms ?? row.latency_ms) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="110" align="center">
          <template #default="{ row }">
            <span v-if="hasRisk(row)" class="pill pill-danger">{{ riskText(row) }}</span>
            <span v-else class="pill pill-plain">无</span>
          </template>
        </el-table-column>
        <el-table-column label="冲突" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.conflict_flag || row.conflict" class="pill pill-warn">有 (冲突调和)</span>
            <span v-else class="pill pill-plain">无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="right" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" class="exp-btn" @click="toggleExpand(row)">
              {{ isExpanded(row) ? '收起详情' : '查看详情' }}
              <el-icon class="exp-arrow" :class="{ up: isExpanded(row) }"><ArrowDown /></el-icon>
            </el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </section>

    <!-- 4. 底部：脱敏声明 + 分页 -->
    <footer class="page-foot">
      <div class="foot-note">
        <el-icon><Lock /></el-icon>
        <span>日志中的用户输入仅保留脱敏摘要；完整原文不在后台展示，严守个人信息最小化原则。</span>
      </div>
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="load"
      />
    </footer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。日志筛选/列表/行内展开六卡详情/CSV 导出（二次确认 + X-Confirm-Token）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown,
  CircleCheck,
  CircleCheckFilled,
  DataAnalysis,
  Download,
  Guide,
  Lock,
  Notebook,
  Search,
  Share,
  Stamp,
  User,
  WarningFilled,
} from '@element-plus/icons-vue'
import { adminApi, ApiError, downloadBlob, exportAgentLogsCsv } from '../../api/admin'

/** 筛选条件（range 为日期区间数组；risk/conflict 为前端过滤维度） */
const filters = reactive<{ range: string[] | null; agent_id: string; risk: string; conflict: string; session_id: string }>({
  range: null,
  agent_id: '',
  risk: '',
  conflict: '',
  session_id: '',
})
/** 列表数据 */
const rows = ref<any[]>([])
/** 加载中 */
const loading = ref(false)
/** 分页状态 */
const page = ref(1)
const pageSize = 20
const total = ref(0)
/** 近 24h 日志量（真实 count，页头 KPI 徽章；无数据时隐藏） */
const recent24h = ref<number | null>(null)

/** 表格实例（操作列切换行展开用） */
const tableRef = ref()
/** 当前展开行 key 集合（绑定 expand-row-keys 与操作列文案） */
const expandedKeys = ref<string[]>([])

/**
 * 函数级注释：耗时毫秒转展示文案
 * @param ms 毫秒数
 * @returns 如 "3.2s"；空值返回 '--'
 */
function durationText(ms: any): string {
  const n = Number(ms)
  if (!ms || Number.isNaN(n)) return '--'
  return `${(n / 1000).toFixed(1)}s`
}

/**
 * 函数级注释：风险层级枚举转文案
 * @param v 风险枚举值
 * @returns 中文标签
 */
function riskLabel(v: string): string {
  const map: Record<string, string> = {
    none: '无',
    low: '低风险',
    mid: '中风险',
    high: '高风险',
    blocked: '已阻断',
    hit: '命中',
  }
  return map[v] || v || ''
}

/**
 * 函数级注释：Agent 枚举 → 中文标签（multi 显示"多Agent协同"，与稿面一致）
 * @param row 日志行数据
 * @returns Agent 中文名或空串（展示 '--'）
 */
function agentLabel(row: any): string {
  const v = row.agent_id || row.agent || ''
  const map: Record<string, string> = {
    dispatcher: '调度器',
    child_care: '育儿',
    pet: '宠物',
    quiz: '题库',
    multi: '多Agent协同',
  }
  return map[v] || v
}

/**
 * 函数级注释：行是否风险命中（列表行/详情均兼容）
 * @param row 日志行数据
 * @returns 是否命中风险
 */
function hasRisk(row: any): boolean {
  const lv = row?._detail?.risk_level || row?.risk_level
  return !!lv && lv !== 'none'
}

/**
 * 函数级注释：风险列/结论展示文案（命中时取枚举文案，未命中为"无风险命中"）
 * @param row 日志行数据
 * @returns 风险文案
 */
function riskText(row: any): string {
  const d = row?._detail || {}
  const lv = d.risk_level || row?.risk_level
  return hasRisk(row) ? riskLabel(lv) || '命中' : '无风险命中'
}

/**
 * 函数级注释：风险命中词/规则摘要文案（D-06）
 * @param row 日志行数据（列表行或详情）
 * @returns 逗号拼接的命中项；无命中返回空串
 */
function riskHitsText(row: any): string {
  const d = row?._detail || {}
  const hits = d.risk_hits ?? row?.risk_hits
  if (Array.isArray(hits)) {
    return hits
      .map((hit: any) => (typeof hit === 'string' ? hit : hit?.rule_id || hit?.category || ''))
      .filter(Boolean)
      .slice(0, 4)
      .join('、')
  }
  return hits ? String(hits) : ''
}

/**
 * 函数级注释：风险原因（详情优先，回退行数据）
 * @param row 日志行数据
 * @returns 风险原因或空串
 */
function riskReason(row: any): string {
  return row?._detail?.risk_reason || row?.risk_reason || ''
}

/**
 * 函数级注释：链路追踪 ID（详情 trace_id/request_id，回退会话 ID）
 * @param row 日志行数据
 * @returns 追踪 ID 展示文案
 */
function traceId(row: any): string {
  const d = row?._detail || {}
  return d.trace_id || d.request_id || row?.session_id || '--'
}

/**
 * 函数级注释：行状态是否执行成功（detail.status=ok 视为 200 OK）
 * @param row 日志行数据
 * @returns 是否成功
 */
function statusOk(row: any): boolean {
  const s = row?._detail?.status || row?.status
  return s === 'ok'
}

/**
 * 函数级注释：状态徽章文案
 * @param row 日志行数据
 * @returns "执行完成 (200 OK)" / "执行异常 (...)" / "状态: --"
 */
function statusText(row: any): string {
  const s = row?._detail?.status || row?.status
  if (!s) return '状态: --'
  return s === 'ok' ? '执行完成 (200 OK)' : `执行异常 (${s})`
}

/**
 * 函数级注释：解析详情中的调度决策对象（兼容 output_json 字符串/对象与 decision 字段）
 * @param row 日志行数据
 * @returns {intent, compound, confidence} 展示字段
 */
function decisionInfo(row: any): { intent: string; compound: string; confidence: string } {
  const d = row?._detail || {}
  let obj: any = d.output_json ?? d.decision ?? {}
  if (typeof obj === 'string') {
    try {
      obj = JSON.parse(obj)
    } catch {
      obj = {}
    }
  }
  const intent = d.intent || obj?.intent || '--'
  const compRaw = d.is_compound ?? obj?.is_compound
  const compound = compRaw == null ? '--' : compRaw ? '是' : '否'
  const conf = d.confidence ?? obj?.confidence
  return { intent, compound, confidence: conf == null ? '--' : String(conf) }
}

/**
 * 函数级注释：详情中的参与 Agent 数组（兼容 agents/steps/participants/agent_call_log 结构）
 * @param row 日志行数据
 * @returns Agent 调用记录数组
 */
function agentArr(row: any): any[] {
  const d = row?._detail || {}
  const arr = d.agents || d.steps || d.participants || d.agent_call_log
  return Array.isArray(arr) ? arr : []
}

/**
 * 函数级注释：参与 Agent 展示行（Agent 名 + 耗时 + 状态）
 * @param row 日志行数据
 * @returns 展示文案数组
 */
function agentLines(row: any): string[] {
  return agentArr(row).map((a: any) => {
    const name = a.agent || a.agent_id || a.name || '--'
    const dur = a.duration_ms ?? a.duration
    const st = a.status || a.state || ''
    return `参与 Agent：${name}${dur ? ` (${durationText(dur)}${st ? ', ' + st : ''})` : ''}`
  })
}

/**
 * 函数级注释：模型载体（detail.model，回退首个 Agent 记录的 model 字段）
 * @param row 日志行数据
 * @returns 模型名或空串
 */
function agentModel(row: any): string {
  const d = row?._detail || {}
  return d.model || d.model_name || agentArr(row).find((a) => a.model)?.model || ''
}

/**
 * 函数级注释：输出 Token 数（detail.output_tokens，回退后端实际字段 completion_tokens / Agent 记录字段）
 * @param row 日志行数据
 * @returns Token 数展示文案
 */
function agentTokens(row: any): string {
  const d = row?._detail || {}
  if (d.output_tokens != null) return String(d.output_tokens)
  // 后端详情响应字段名为 completion_tokens（无 output_tokens 别名），做兼容回退
  if (d.completion_tokens != null) return String(d.completion_tokens)
  const t = agentArr(row).find((a) => a.output_tokens != null || a.completion_tokens != null)
  const v = t?.output_tokens ?? t?.completion_tokens
  return v == null ? '--' : String(v)
}

/**
 * 函数级注释：引用来源列表（兼容字符串数组或对象数组）
 * @param row 日志行数据
 * @returns 引用标识数组
 */
function evidenceRefs(row: any): string[] {
  const ev = row?._detail?.evidence_ref ?? row?._detail?.evidence_refs
  if (!Array.isArray(ev)) return ev ? [String(ev)] : []
  return ev.map((x: any) => (typeof x === 'string' ? x : x.ref || x.kb_id || JSON.stringify(x)))
}

/**
 * 函数级注释：哈希引用文案（详情有真实 audit_hash 时展示值，否则只保留 SHA256 字样不编造哈希）
 * @param row 日志行数据
 * @returns 哈希引用展示文案
 */
function hashText(row: any): string {
  const h = row?._detail?.audit_hash || row?._detail?.hash
  return h ? `SHA256:${h}` : 'SHA256 算法存证（由审计系统管理）'
}

/**
 * 函数级注释：前端过滤后的日志行（风险/冲突维度，类型来自当前页数据）
 */
const filteredRows = computed<any[]>(() => {
  let list = rows.value
  if (filters.risk === 'hit') list = list.filter((r) => hasRisk(r))
  if (filters.risk === 'none') list = list.filter((r) => !hasRisk(r))
  if (filters.conflict === 'yes') list = list.filter((r) => r.conflict_flag || r.conflict)
  if (filters.conflict === 'no') list = list.filter((r) => !(r.conflict_flag || r.conflict))
  return list
})

/**
 * 函数级注释：行 key（row-key 与展开集合统一使用）
 * @param row 日志行数据
 * @returns 行唯一 key 字符串
 */
function rowKeyOf(row: any): string {
  return String(row?.id ?? row?.log_id ?? row?.session_id ?? '')
}

/**
 * 函数级注释：行是否处于展开态
 * @param row 日志行数据
 * @returns 是否展开
 */
function isExpanded(row: any): boolean {
  return expandedKeys.value.includes(rowKeyOf(row))
}

/**
 * 函数级注释：操作列切换行展开
 * @param row 日志行数据
 */
function toggleExpand(row: any): void {
  tableRef.value?.toggleRowExpansion(row)
}

/**
 * 函数级注释：行展开变化回调（展开时懒加载详情，失败兜底展示行内基础信息）
 * @param row 当前行
 * @param expandedList 当前展开行数组
 */
async function onExpandChange(row: any, expandedList: any[]): Promise<void> {
  const isOpen = expandedList.includes(row)
  expandedKeys.value = isOpen ? [rowKeyOf(row)] : expandedKeys.value.filter((k) => k !== rowKeyOf(row))
  if (isOpen && !row._detail) {
    row._loading = true
    try {
      row._detail = await adminApi.agentLogDetail(row.id ?? row.log_id)
    } catch (e) {
      ElMessage.error(e instanceof ApiError ? e.message : '详情加载失败，已展示行内基础信息')
      row._detail = row // 兜底：直接展示行数据
    } finally {
      row._loading = false
    }
  }
}

/**
 * 函数级注释：组装查询参数（含时间范围拆分为 time_start/time_end）
 * @returns 查询参数对象
 */
function buildParams(): Record<string, any> {
  return {
    time_start: filters.range?.[0] || '',
    time_end: filters.range?.[1] || '',
    agent_id: filters.agent_id,
    session_id: filters.session_id,
    page: page.value,
    page_size: pageSize,
  }
}

/**
 * 函数级注释：加载日志列表（清空行展开态）
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data: any = await adminApi.agentLogList(buildParams())
    rows.value = data?.list || data?.items || data || []
    total.value = Number(data?.total ?? rows.value.length)
    expandedKeys.value = []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '日志加载失败')
    rows.value = []
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：加载近 24h 日志量（真实 count；失败静默隐藏徽章）
 */
async function loadRecentCount(): Promise<void> {
  try {
    const start = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
    const data: any = await adminApi.agentLogList({ time_start: start, page: 1, page_size: 1 })
    recent24h.value = Number(data?.total ?? (Array.isArray(data) ? data.length : 0))
  } catch {
    recent24h.value = null
  }
}

/**
 * 函数级注释：查询（重置页码）
 */
function handleSearch(): void {
  page.value = 1
  load()
}

/**
 * 函数级注释：重置筛选
 */
function handleReset(): void {
  filters.range = null
  filters.agent_id = ''
  filters.risk = ''
  filters.conflict = ''
  filters.session_id = ''
  page.value = 1
  load()
}

/**
 * 函数级注释：导出 CSV（二次确认 → 带 X-Confirm-Token 头请求 → blob 下载）
 */
async function handleExport(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '导出将生成当前筛选条件下的日志 CSV 文件，并记录审计日志（操作人/时间/条件）。确认导出？',
      '导出确认',
      { type: 'warning', confirmButtonText: '确认导出', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const blob = await exportAgentLogsCsv(buildParams())
    downloadBlob(blob, `agent-logs-${new Date().toISOString().slice(0, 10)}.csv`)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '导出失败')
  }
}

onMounted(() => {
  load()
  loadRecentCount()
})
</script>

<style scoped>
/* 页面纵向排布 */
.agent-log-page {
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
  padding: 16px 24px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.head-ico {
  flex: none;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-face);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.head-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.35;
}

/* 近 24h 量徽章（真实 count） */
.kpi-chip {
  padding: 1px 10px;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 500;
  white-space: nowrap;
}

.head-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* ---------- 2. 筛选行卡 ---------- */
.filter-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 14px 24px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
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

.ff-date {
  width: 240px;
}

.ff-sel {
  width: 120px;
}

.ff-sel-sm {
  width: 96px;
}

.ff.grow {
  flex: 1;
  min-width: 180px;
  max-width: 260px;
}

.filter-actions {
  display: flex;
  gap: 8px;
}

/* ---------- 3. 日志表卡 ---------- */
.table-card {
  padding: 0;
  overflow: hidden;
}

.sid {
  color: var(--ink-1);
  font-weight: 500;
}

.time-cell {
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

/* 风险命中行的输入摘要红色 */
.sum-hit {
  color: var(--danger);
  font-weight: 500;
}

.muted {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* Agent 标签 chip */
.agent-chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 4px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 500;
}

.agent-chip.multi {
  background: var(--accent-soft);
  border-color: var(--accent-line);
  color: var(--accent);
}

/* 风险/冲突圆角 pill */
.pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-caption);
  font-weight: 500;
  white-space: nowrap;
}

.pill-plain {
  background: var(--surface-2);
  color: var(--ink-3);
  font-weight: 400;
}

.pill-danger {
  background: var(--danger-soft);
  border: 1px solid var(--line-strong);
  color: var(--danger);
}

.pill-warn {
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  color: var(--warn);
}

/* 操作列展开按钮 */
.exp-btn .exp-arrow {
  margin-left: 2px;
  transition: transform 0.2s ease;
}

.exp-btn .exp-arrow.up {
  transform: rotate(180deg);
}

/* ---------- 展开详情面板（背景明度差区分层级，无彩色左条） ---------- */
.exp-panel {
  padding: 20px 24px;
  background: var(--surface-bright);
}

.exp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.exp-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.exp-title-ico {
  color: var(--accent);
}

.exp-title h3 {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.exp-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.trk-chip {
  padding: 3px 10px;
  border-radius: 4px;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

/* 六卡网格 */
.exp-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.dcard {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: var(--radius-face);
  background: var(--surface);
  border: 1px solid var(--line);
}

.dc-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  font-weight: 500;
  color: var(--ink-3);
}

.dc-head .el-icon {
  color: var(--ink-3);
}

.dc-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: var(--fs-caption);
  color: var(--ink-1);
  line-height: 1.7;
  word-break: break-all;
}

/* 知识库引用：等宽 + accent 色 */
.dc-ev {
  color: var(--accent);
}

.dc-strong {
  font-weight: 500;
  color: var(--ink-1);
}

.dc-dim {
  color: var(--ink-3);
}

.dc-note {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.7;
  margin: 0;
}

.risk-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}

.risk-line.ok {
  color: var(--accent);
}

.risk-line.bad {
  color: var(--danger);
}

.risk-reason {
  color: var(--ink-3);
}

.dc-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
}

/* ---------- 4. 底部：脱敏声明 + 分页 ---------- */
.page-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 0 4px;
}

.foot-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.foot-note .el-icon {
  color: var(--ink-3);
}

@media (max-width: 1080px) {
  .exp-grid {
    grid-template-columns: 1fr;
  }
}

/* 手机窄屏（375 视口）：筛选控件纵排全宽、页头与分页收紧，消除横向滚动 */
@media (max-width: 640px) {
  .head-card {
    padding: 12px 16px;
  }
  .head-left {
    gap: 10px;
  }
  .head-title-row {
    flex-wrap: wrap;
  }
  .filter-card {
    padding: 12px 16px;
    row-gap: 10px;
  }
  .filters {
    flex: 1 1 100%;
    gap: 10px;
  }
  .ff {
    flex: 1 1 100%;
  }
  /* el-date-picker 根元素带内部 tooltip 片段，无 scoped 属性，需 :deep 穿透；
     否则仍是 EP 默认 350px，撑破 .ff 行 */
  .ff :deep(.ff-date),
  .ff :deep(.ff-sel),
  .ff :deep(.ff-sel-sm) {
    flex: 1;
    width: auto;
    min-width: 0;
  }
  .ff.grow {
    flex: 1 1 100%;
    min-width: 0;
    max-width: none;
  }
  .ff.grow .el-input {
    flex: 1;
    min-width: 0;
  }
  .filter-actions {
    flex-wrap: wrap;
  }
  .page-foot :deep(.el-pagination) {
    flex-wrap: wrap;
    row-gap: 6px;
    max-width: 100%;
    justify-content: center;
  }
  .page-foot :deep(.el-pager) {
    flex-wrap: wrap;
    row-gap: 6px;
    justify-content: center;
  }
  .page-foot :deep(.el-pager li) {
    margin: 0 2px;
    min-width: 30px;
  }
}
</style>
