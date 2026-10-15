<!--
  文件级注释：PA-08 个人信息权利请求处理与系统开关页（Stitch 稿 _6 全量重构）
  上半区：权利请求卡（待处理红标 + 快捷筛选 + 请求表：权利类型图标/SLA 剩余徽章/状态点/操作）
          + 当前工单处理流程卡（选中行展开：分类变更/导出格式 JSON|CSV 分段/安全交付途径分段/
          法定拒绝抗辩理由 500 字 + 理由码必填 → POST /admin/rights/{no}/process 原逻辑）
  下半区：系统开关与全局风控配置卡（业务模块紧急下线熔断勾选——原开关 prompt 理由 + 二次确认逻辑；
          2×2 配置卡网格：价格配置/AI 标识文案/危机渠道清单/灰度发布；
          底部操作条：变更历史抽屉 + 一键回滚 + 保存当前配置——仅 super_admin 可写，
          其他角色 disabled + 提示；配置读写走 GET/PUT /admin/configs/{key}、history、rollback）
-->
<template>
  <div class="rc-page">
    <!-- ═══════ 模块一：个人信息权利请求 ═══════ -->
    <section class="st-card rights-card">
      <!-- 1. 标题与操作栏 -->
      <div class="card-head">
        <div class="head-title-wrap">
          <el-icon class="head-ico"><User /></el-icon>
          <h2 class="card-title">
            个人信息权利请求
            <span v-if="pendingCount" class="pending-badge numeric">待处理 {{ pendingCount }}</span>
          </h2>
          <span class="head-note">依据《个人信息保护法》第四章与 GDPR 响应周期标准</span>
        </div>
        <el-button :icon="Download" @click="exportRightsCsv">导出处理记录</el-button>
      </div>

      <!-- 2. 快捷筛选行 -->
      <div class="quick-filter">
        <div class="qf-fields">
          <span class="qf-label">快捷筛选：</span>
          <el-select v-model="draftRights.type" class="qf-ctrl" placeholder="全部权利类型">
            <el-option label="全部权利类型" value="" />
            <el-option v-for="(v, k) in RIGHT_TYPE" :key="k" :label="v.label" :value="k" />
          </el-select>
          <el-select v-model="draftRights.status" class="qf-ctrl" placeholder="待处理">
            <el-option label="全部状态" value="" />
            <el-option v-for="(v, k) in RIGHT_STATUS" :key="k" :label="v" :value="k" />
          </el-select>
          <el-select v-model="draftRights.sla" class="qf-ctrl" placeholder="全部 SLA 状态">
            <el-option label="全部 SLA 状态" value="" />
            <el-option label="紧急（≤24h）" value="urgent" />
            <el-option label="正常周期内" value="normal" />
          </el-select>
          <el-button type="primary" plain size="small" @click="applyRightsFilter">应用</el-button>
        </div>
        <div class="qf-side">
          <span>法定响应基线：15 个工作日内</span>
          <span class="ok-dot"></span>
        </div>
      </div>

      <!-- 3. 请求表 -->
      <el-table
        :data="filteredRights"
        class="st-table"
        v-loading="rightsLoading"
        :row-class-name="rowClassName"
        @row-click="openProcess"
      >
        <el-table-column label="请求号" width="120">
          <template #default="{ row }">
            <span class="no-cell numeric" :class="{ picked: isPicked(row) }">{{ row.request_no }}</span>
          </template>
        </el-table-column>
        <el-table-column label="权利类型" min-width="180">
          <template #default="{ row }">
            <span class="type-cell">
              <el-icon class="type-ico" :class="{ danger: row.right_type === 'delete' }">
                <component :is="RIGHT_TYPE[row.right_type]?.icon || Document" />
              </el-icon>
              <span>{{ rightTypeLabel(row.right_type) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="用户 ID" width="120">
          <template #default="{ row }">
            <span class="numeric uid">{{ row.user_id || row.user_name || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="SLA 剩余" width="200">
          <template #default="{ row }">
            <span class="sla-badge" :class="slaBadgeClass(row)">
              <el-icon v-if="slaBadgeClass(row) === 'urgent'"><AlarmClock /></el-icon>
              <span class="numeric">{{ slaText(row) }}</span>
              <span v-if="slaBadgeClass(row) === 'urgent'">（红色紧急 SLA）</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="处理状态" width="130">
          <template #default="{ row }">
            <span class="st-tag" :class="statusTagClass(row.status)">{{ rightStatusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="处理人" width="100">
          <template #default="{ row }">{{ row.handler || row.assignee || '--' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="right">
          <template #default="{ row }">
            <span v-if="isPicked(row)" class="st-chip-btn">进入处理</span>
            <button
              v-else
              type="button"
              class="op-link"
              :class="{ urgent: slaBadgeClass(row) === 'urgent' }"
              @click.stop="openProcess(row)"
            >
              {{ slaBadgeClass(row) === 'urgent' ? '[加急处理]' : '[处理]' }}
            </button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>

      <!-- 4. 当前工单处理流程卡（选中行展开） -->
      <div v-if="currentRight" class="process-card">
        <div class="process-head">
          <div class="process-title">
            <span class="title-dot"></span>
            <h3>
              当前工单处置流程：<span class="numeric accent">{{ currentRight.request_no }}</span>
              <span class="plain">（用户: <span class="numeric">{{ currentRight.user_id || currentRight.user_name || '--' }}</span>）</span>
            </h3>
          </div>
          <span class="verify-note">
            <el-icon><Lock /></el-icon>
            安全脱敏合规校验：已通过身份强认证
          </span>
        </div>

        <!-- 三列配置 -->
        <div class="process-grid">
          <div class="p-field">
            <label>权利请求分类变更</label>
            <el-select v-model="processForm.category" placeholder="选择分类">
              <el-option label="查阅 / 更正 / 导出 / 撤回 / 删除 / 账号注销" value="general" />
              <el-option label="导出 (用户画像与咨询留痕包)" value="export" />
              <el-option label="更正 (纠正基本医学/家庭档案)" value="correct" />
              <el-option label="删除 (不可逆物理覆写)" value="delete" />
              <el-option label="账号注销 (注销账户及全量凭据)" value="cancel" />
            </el-select>
          </div>
          <div class="p-field">
            <label>导出格式规范</label>
            <div class="seg-toggle">
              <button
                type="button"
                class="seg-opt"
                :class="{ active: processForm.format === 'json' }"
                @click="processForm.format = 'json'"
              >
                JSON (机器可读)
              </button>
              <button
                type="button"
                class="seg-opt"
                :class="{ active: processForm.format === 'csv' }"
                @click="processForm.format = 'csv'"
              >
                CSV (表格清单)
              </button>
            </div>
          </div>
          <div class="p-field">
            <label>安全交付途径</label>
            <div class="seg-toggle">
              <button
                type="button"
                class="seg-opt"
                :class="{ active: delivery === 'email' }"
                @click="delivery = 'email'"
              >
                <el-icon><Message /></el-icon>
                发送至邮箱
              </button>
              <button
                type="button"
                class="seg-opt"
                :class="{ active: delivery === 'local' }"
                @click="delivery = 'local'"
              >
                <el-icon><Lock /></el-icon>
                本地安全下载
              </button>
            </div>
          </div>
        </div>

        <!-- 法定拒绝抗辩理由 -->
        <div class="reject-block">
          <div class="label-line">
            <label class="p-label">
              法定拒绝抗辩理由
              <span class="tip">（若选择拒绝，必须详尽填写法律依据及事实支撑）</span>
            </label>
            <span class="tip numeric">字数：{{ rejectNote.length }} / 500</span>
          </div>
          <div class="reject-code-row">
            <span class="tip">拒绝理由码（提交拒绝时必选）：</span>
            <el-select v-model="processForm.reject_reason_code" class="code-select" placeholder="选择拒绝理由码" clearable>
              <el-option label="身份核验未通过" value="identity_failed" />
              <el-option label="超出处理范围" value="out_of_scope" />
              <el-option label="涉及他人权益" value="third_party_rights" />
              <el-option label="重复请求" value="duplicate" />
              <el-option label="其他" value="other" />
            </el-select>
          </div>
          <el-input
            v-model="rejectNote"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            resize="none"
            placeholder="拒绝理由（若拒绝必须详尽填写法定理由）：例如：根据《个人信息保护法》第十八条，涉及国家安全/诉讼证据保全，暂不予物理擦除..."
          />
        </div>

        <!-- 操作按钮组与注脚 -->
        <div class="process-foot">
          <div class="pf-btns">
            <el-button type="primary" :icon="Box" :loading="processing" @click="doProcess('generate_export')">
              生成导出包
            </el-button>
            <el-button :icon="CircleCheck" :loading="processing" @click="doProcess('mark_done')">
              标记为完成
            </el-button>
            <el-button class="btn-reject" :icon="CircleClose" :loading="processing" @click="doProcess('reject')">
              拒绝请求
            </el-button>
          </div>
          <div class="audit-note">
            <el-icon><CircleCheck /></el-icon>
            <span>全部操作写入区块式审计留痕</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══════ 模块二：系统开关与全局风控配置 ═══════ -->
    <section class="st-card config-card">
      <!-- 1. 模块标题 -->
      <div class="card-head">
        <div class="head-title-wrap">
          <el-icon class="head-ico"><Setting /></el-icon>
          <h2 class="card-title">系统开关与全局风控配置</h2>
          <span class="sync-chip">生产集群实时同步</span>
        </div>
        <div class="engine-status">
          <span class="ok-dot"></span>
          <span>配置同步引擎：健康正常</span>
        </div>
      </div>

      <!-- 2. 业务模块紧急下线（一键熔断） -->
      <div class="fuse-box">
        <div class="fuse-head">
          <div class="fuse-title">
            <el-icon><Lightning /></el-icon>
            <span>业务模块紧急下线（一键熔断）</span>
          </div>
          <span class="fuse-tip">勾选后将即刻截断端侧路由，并返回合规降级页面</span>
        </div>
        <div class="fuse-switches" v-loading="configsLoading">
          <span class="fuse-label">业务模块紧急下线：</span>
          <el-tooltip
            v-for="(sw, i) in switchItems"
            :key="sw.key"
            :disabled="isSuperAdmin"
            content="仅超管可操作"
            placement="top"
          >
            <span class="btn-wrap">
              <el-checkbox
                :model-value="switchOn(sw)"
                :disabled="!isSuperAdmin"
                @change="(v: any) => onSwitchChange(sw, v)"
              >
                {{ switchLabel(sw, i) }}
              </el-checkbox>
            </span>
          </el-tooltip>
          <span v-if="!switchItems.length && !configsLoading" class="muted">暂无开关配置</span>
        </div>
      </div>

      <!-- 3. 2×2 配置卡网格 -->
      <div class="cfg-grid">
        <!-- 价格配置 -->
        <div class="cfg-item">
          <div class="cfg-info">
            <div class="cfg-name">
              <el-icon><Wallet /></el-icon>
              <span>价格配置</span>
            </div>
            <div class="cfg-value">
              <span class="price-num numeric">{{ displayPrice ?? '--' }}</span>
              <span class="price-unit">元/月</span>
              <span class="tip">（实时下发生效）</span>
            </div>
          </div>
          <el-tooltip :disabled="isSuperAdmin" content="仅超管可操作" placement="top">
            <span class="btn-wrap">
              <el-button :disabled="!isSuperAdmin" :loading="configSavingKey === 'product_price'" @click="modifyPrice">修改价格</el-button>
            </span>
          </el-tooltip>
        </div>

        <!-- AI 标识文案 -->
        <div class="cfg-item">
          <div class="cfg-info">
            <div class="cfg-name">
              <el-icon><MagicStick /></el-icon>
              <span>AI 标识文案编码</span>
            </div>
            <div class="cfg-value">
              <span class="code-chip numeric">AI_GEN_LABEL_V1</span>
              <span class="tip">《生成式人工智能服务管理暂行办法》标引</span>
            </div>
          </div>
          <el-tooltip :disabled="isSuperAdmin" content="仅超管可操作" placement="top">
            <span class="btn-wrap">
              <el-button :disabled="!isSuperAdmin" @click="aiEditVisible = true">编辑文案</el-button>
            </span>
          </el-tooltip>
        </div>

        <!-- 危机求助渠道清单 -->
        <div class="cfg-item">
          <div class="cfg-info">
            <div class="cfg-name">
              <el-icon><Phone /></el-icon>
              <span>危机求助渠道清单</span>
            </div>
            <div class="cfg-value">
              <span class="code-chip numeric">CRISIS_CHANNELS_V1</span>
              <span class="expire-chip">复核到期提醒：2026-12-01</span>
            </div>
          </div>
          <el-button @click="crisisEditVisible = true">编辑清单</el-button>
        </div>

        <!-- 灰度开关与发布网络 -->
        <div class="cfg-item">
          <div class="cfg-info">
            <div class="cfg-name">
              <el-icon><Connection /></el-icon>
              <span>灰度开关与发布网络</span>
            </div>
            <div class="cfg-value">
              <span class="gray-line">
                <span class="tip">体验版:</span>
                <span class="gray-chip on">已开启</span>
              </span>
              <span class="gray-line">
                <span class="tip">正式版:</span>
                <span class="gray-chip off">未开启</span>
              </span>
            </div>
          </div>
          <el-button @click="graySwitch">切换策略</el-button>
        </div>
      </div>

      <!-- 4. 底部回滚与保存控制 -->
      <div class="config-foot">
        <div class="cf-left">
          <el-select v-model="historyKeySelect" class="key-select" placeholder="选择配置项">
            <el-option v-for="k in configKeys" :key="k" :label="k" :value="k" />
          </el-select>
          <el-button :icon="Search" @click="openHistory(historyKeySelect)">查看配置变更历史</el-button>
          <el-tooltip :disabled="isSuperAdmin" content="仅超管可操作" placement="top">
            <span class="btn-wrap">
              <el-button :icon="RefreshLeft" :disabled="!isSuperAdmin" @click="quickRollback(historyKeySelect)">
                一键回滚到上一版本
              </el-button>
            </span>
          </el-tooltip>
        </div>
        <el-tooltip :disabled="isSuperAdmin" content="仅超管可操作" placement="top">
          <span class="btn-wrap">
            <el-button type="primary" size="large" :icon="Finished" :disabled="!isSuperAdmin" @click="saveAllConfigs">
              保存当前配置
            </el-button>
          </span>
        </el-tooltip>
      </div>

      <!-- 审计合规提示小字 -->
      <div class="foot-note">
        <el-icon><InfoFilled /></el-icon>
        <p>开关变更将在 1 分钟内全网全量生效；操作全程留痕并记录超级管理员签名。</p>
      </div>
    </section>

    <!-- AI 标识文案编辑弹窗 -->
    <el-dialog v-model="aiEditVisible" title="编辑 AI 标识文案（AI_GEN_LABEL_V1）" width="560px">
      <el-input
        v-model="copywritingText"
        type="textarea"
        :rows="8"
        :disabled="!isSuperAdmin"
        placeholder="AI 对话兜底/免责/引导文案配置（JSON）"
      />
      <template #footer>
        <el-button @click="aiEditVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!isSuperAdmin"
          :loading="configSavingKey === 'ai_copywriting'"
          @click="saveAiCopy"
        >
          保存文案
        </el-button>
      </template>
    </el-dialog>

    <!-- 危机渠道清单弹窗 -->
    <el-dialog v-model="crisisEditVisible" title="危机求助渠道清单（CRISIS_CHANNELS_V1）" width="620px">
      <el-table :data="crisisChannels" v-loading="configsLoading" size="small">
        <el-table-column prop="name" label="渠道名称" min-width="150" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="phone" label="电话/联系方式" width="150" />
        <el-table-column label="可用" width="80">
          <template #default="{ row }">
            <span class="st-tag" :class="row.available === false ? 'st-tag--gray' : 'st-tag--green'">
              {{ row.available === false ? '停用' : '可用' }}
            </span>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" :image-size="60" /></template>
      </el-table>
      <template #footer>
        <el-button @click="openHistory('crisis_channels')">变更历史</el-button>
        <el-button type="primary" @click="crisisEditVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 配置变更历史抽屉 + 回滚 -->
    <el-drawer v-model="historyVisible" :title="`变更历史 · ${historyKey}`" size="500px">
      <el-table :data="historyRows" v-loading="historyLoading" size="small">
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column prop="changed_by" label="操作人" width="100" />
        <el-table-column prop="changed_at" label="时间" width="160" />
        <el-table-column prop="reason" label="变更摘要" min-width="110" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="danger" plain size="small" @click="rollbackTo(historyKey, row.version)">回滚到该版</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。权利请求处理（导出/完成/拒绝留痕）+ 系统开关熔断/价格/文案/
 * 危机渠道/灰度配置管理与回滚；非 super_admin 全部写操作 disabled 提示。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  AlarmClock,
  Box,
  CircleCheck,
  CircleClose,
  Connection,
  CopyDocument,
  Delete,
  Document,
  Download,
  EditPen,
  Finished,
  InfoFilled,
  Lightning,
  Lock,
  MagicStick,
  Message,
  Phone,
  RefreshLeft,
  Search,
  Setting,
  User,
  View,
  Wallet,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { adminApi, ApiError, getAdminInfo, withConfirm, CONFIRM_TOKEN, downloadBlob } from '../../api/admin'

/** 当前管理员角色（仅 super_admin 可写配置） */
const role = ref<string>(getAdminInfo()?.role || '')
/** 是否超级管理员 */
const isSuperAdmin = computed(() => role.value === 'super_admin')

/** 权利请求列表 */
const rights = ref<any[]>([])
/** 权利加载中 */
const rightsLoading = ref(false)
/** 配置项列表 */
const configItems = ref<any[]>([])
/** 配置加载中 */
const configsLoading = ref(false)

/** 权利处理流程卡：当前选中行 */
const currentRight = ref<any>(null)
/** 权利处理表单（action/format/reject_reason_code 为 API 载荷；category/delivery 为 UI 展示字段） */
const processForm = reactive({ action: 'generate_export', format: 'json', reject_reason_code: '', category: 'export' })
/** 安全交付途径（UI 展示字段：email=发送至邮箱 / local=本地安全下载） */
const delivery = ref<'email' | 'local'>('email')
/** 法定拒绝抗辩理由详述（500 字内，拒绝提交前必填校验） */
const rejectNote = ref('')
/** 处理提交中 */
const processing = ref(false)

/** 价格配置 / AI 文案文本 */
const pricingText = ref('')
const copywritingText = ref('')
/** 会员月卡商品（价格配置卡真实数据源：product 表 member_monthly） */
const memberProduct = ref<any>(null)
/** 加载时的初始快照（"保存当前配置"仅提交发生变化的项） */
const initialPricing = ref('')
const initialCopy = ref('')
/** 正在保存的配置 key（loading 标识） */
const configSavingKey = ref('')

/** 变更历史抽屉状态 */
const historyVisible = ref(false)
const historyKey = ref('')
const historyLoading = ref(false)
const historyRows = ref<any[]>([])
/** 底部操作条选中的配置键 */
const historyKeySelect = ref('pricing_config')

/** AI 文案编辑弹窗 */
const aiEditVisible = ref(false)
/** 危机渠道清单弹窗 */
const crisisEditVisible = ref(false)

/** 权利筛选草稿条件（点"应用"后生效） */
const draftRights = reactive({ type: '', status: '', sla: '' })
/** 已应用的筛选条件 */
const appliedRights = reactive({ type: '', status: '', sla: '' })

/** 预定义的 5 个入口开关 key（后端 config_type='switch' 的真实键：switch.entry.*） */
const SWITCH_KEYS = ['switch.entry.child', 'switch.entry.pet', 'switch.entry.family', 'switch.entry.assessment', 'switch.entry.member']

/** 熔断开关展示标签兜底序列（按索引对应稿子 5 个业务模块） */
const MODULE_LABELS = ['育儿问答', '宠物问答', '家庭综合问答', '气质测评', '会员服务']

/** 权利类型枚举展示（含图标） */
const RIGHT_TYPE: Record<string, { label: string; tag: any; icon: Component }> = {
  export: { label: '数据导出', tag: 'primary', icon: CopyDocument },
  delete: { label: '数据删除', tag: 'danger', icon: Delete },
  correct: { label: '数据更正', tag: 'warning', icon: EditPen },
  access: { label: '数据查阅', tag: 'info', icon: View },
}

/** 权利状态文案 */
const RIGHT_STATUS: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  generating: '导出生成中',
  done: '已完成',
  rejected: '已拒绝',
  closed: '已关闭',
}

/**
 * 函数级注释：权利类型转文案
 * @param t 类型枚举
 * @returns 中文文案
 */
function rightTypeLabel(t: string): string {
  return RIGHT_TYPE[t]?.label || t || '--'
}

/**
 * 函数级注释：权利状态转文案
 * @param s 状态枚举
 * @returns 中文文案
 */
function rightStatusLabel(s: string): string {
  return RIGHT_STATUS[s] || s || '--'
}

/**
 * 函数级注释：权利状态点标签变体类（处理中绿/待处理琥珀/已完成绿/已拒绝红）
 * @param s 状态枚举
 * @returns st-tag 修饰类
 */
function statusTagClass(s: string): any {
  if (s === 'processing') return 'st-tag--green'
  if (['done', 'closed'].includes(s)) return 'st-tag--green'
  if (s === 'rejected') return 'st-tag--red'
  return 'st-tag--amber'
}

/**
 * 函数级注释：权利请求 SLA 文本
 * @param row 权利请求行数据
 * @returns SLA 文案
 */
function slaText(row: any): string {
  const deadline = row.sla_deadline || row.deadline
  if (!deadline) return '--'
  const diff = new Date(deadline).getTime() - Date.now()
  if (Number.isNaN(diff)) return '--'
  const h = diff / 3600000
  if (h <= 0) return `已超时 ${Math.abs(h).toFixed(1)}h`
  return h >= 24 ? `剩 ${(h / 24).toFixed(0)} 天` : `剩 ${h.toFixed(1)}h`
}

/**
 * 函数级注释：SLA 徽章样式档（超时红色紧急/临近 24h 黄色/正常灰色）
 * @param row 权利请求行数据
 * @returns 'urgent' | 'near' | ''
 */
function slaBadgeClass(row: any): string {
  const deadline = row.sla_deadline || row.deadline
  if (!deadline) return ''
  const h = (new Date(deadline).getTime() - Date.now()) / 3600000
  if (Number.isNaN(h)) return ''
  if (h <= 0) return 'urgent'
  if (h <= 24) return 'near'
  return ''
}

/**
 * 函数级注释：待处理请求数量（标题红标）
 */
const pendingCount = computed(() => rights.value.filter((r) => ['pending', 'processing'].includes(r.status)).length)

/**
 * 函数级注释：应用筛选后的权利请求列表（类型/状态/SLA 为前端本地过滤）
 */
const filteredRights = computed(() => {
  const { type, status, sla } = appliedRights
  return rights.value.filter((r) => {
    if (type && r.right_type !== type) return false
    if (status && r.status !== status) return false
    if (sla) {
      const badge = slaBadgeClass(r)
      if (sla === 'urgent' && badge !== 'urgent') return false
      if (sla === 'normal' && badge === 'urgent') return false
    }
    return true
  })
})

/**
 * 函数级注释：应用权利筛选条件
 */
function applyRightsFilter(): void {
  Object.assign(appliedRights, draftRights)
}

/**
 * 函数级注释：行是否处于选中展开态
 * @param row 权利请求行数据
 * @returns 是否选中
 */
function isPicked(row: any): boolean {
  return currentRight.value?.request_no === row.request_no
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
 * 函数级注释：入口开关项（switch.entry.* 前缀键优先，兼容布尔型配置）
 */
const switchItems = computed(() =>
  configItems.value.filter((c) => {
    if (typeof c.key === 'string' && c.key.startsWith('switch.entry.')) return true
    const isBool = c.value_type === 'bool' || typeof c.value === 'boolean'
    return isBool || SWITCH_KEYS.includes(c.key)
  })
)

/**
 * 函数级注释：开关当前勾选态（对象快照 enabled !== false；与后端 1406 判定语义一致）
 * @param item 配置项
 * @returns 是否勾选
 */
function switchOn(item: any): boolean {
  const v = item?.value
  if (v !== null && typeof v === 'object') return v.enabled !== false
  return !!v
}

/**
 * 函数级注释：开关展示标签（snapshot.name 优先，其次 description，最后按索引取稿子模块名兜底）
 * @param item 配置项
 * @param index 索引
 * @returns 展示标签
 */
function switchLabel(item: any, index: number): string {
  const v = item?.value
  if (v && typeof v === 'object' && typeof v.name === 'string' && v.name) return v.name
  return item.description || MODULE_LABELS[index] || item.key
}

/**
 * 函数级注释：危机渠道清单（从 crisis_channels 配置解析数组）
 */
const crisisChannels = computed<any[]>(() => {
  const item = configItems.value.find((c) => c.key === 'crisis_channels')
  const v = item?.value
  if (Array.isArray(v)) return v
  if (typeof v === 'string') {
    try {
      const parsed = JSON.parse(v)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
})

/**
 * 函数级注释：可选择的配置键集合（底部查看历史/回滚用；过滤空键防 undefined 选项）
 */
const configKeys = computed(() => {
  const keys = new Set<string>(['pricing_config', 'ai_copywriting', 'crisis_channels'])
  configItems.value.forEach((c) => {
    if (typeof c.key === 'string' && c.key) keys.add(c.key)
  })
  return Array.from(keys)
})

/**
 * 函数级注释：价格展示值（元/月）——优先真实商品价格（product 表），回退 pricing_config 文本解析
 */
const displayPrice = computed<string | null>(() => {
  if (memberProduct.value?.price_micro != null) {
    const n = Number(memberProduct.value.price_micro)
    if (Number.isFinite(n)) return String(n / 1_000_000)
  }
  try {
    const obj = JSON.parse(pricingText.value)
    const cand = [obj?.price, obj?.monthly, obj?.monthly_fee, obj?.amount, obj?.fee]
    for (const c of cand) {
      const n = Number(c)
      if (Number.isFinite(n)) return String(n)
    }
  } catch {
    /* 配置非 JSON 时按未解析处理 */
  }
  return null
})

/**
 * 函数级注释：加载会员月卡商品价格（product 表，价格配置卡数据源）
 */
async function loadProductPrice(): Promise<void> {
  try {
    const data: any = await adminApi.productList()
    const items: any[] = data?.items || data?.list || data || []
    memberProduct.value = items.find((p: any) => p.product_code === 'member_monthly') || items[0] || null
  } catch {
    memberProduct.value = null
  }
}

/**
 * 函数级注释：加载权利请求列表
 */
async function loadRights(): Promise<void> {
  rightsLoading.value = true
  try {
    const data: any = await adminApi.rightsList({ page: 1, page_size: 100 })
    rights.value = data?.list || data?.items || data || []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '权利请求加载失败')
    rights.value = []
  } finally {
    rightsLoading.value = false
  }
}

/**
 * 函数级注释：加载系统配置列表并填充文本编辑区（同时记录初始快照）
 */
async function loadConfigs(): Promise<void> {
  configsLoading.value = true
  try {
    const data: any = await adminApi.configList()
    const raw: any[] = data?.list || data?.items || data || []
    // 字段归一化：后端契约为 config_key + snapshot（整体对象），映射为内部 key/value
    configItems.value = raw.map((c: any) => ({
      ...c,
      key: c.config_key ?? c.key,
      value: c.snapshot !== undefined ? c.snapshot : c.value,
    }))
    // 填充价格配置 / AI 文案编辑区（对象转 JSON 便于编辑）
    const pricing = configItems.value.find((c) => c.key === 'pricing_config')
    pricingText.value = stringifyConfigValue(pricing?.value)
    initialPricing.value = pricingText.value
    const copy = configItems.value.find((c) => c.key === 'ai_copywriting')
    copywritingText.value = stringifyConfigValue(copy?.value)
    initialCopy.value = copywritingText.value
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '配置加载失败')
    configItems.value = []
  } finally {
    configsLoading.value = false
  }
}

/**
 * 函数级注释：配置值转可编辑文本（对象/数组转 JSON，字符串原样）
 * @param v 配置值
 * @returns 文本
 */
function stringifyConfigValue(v: any): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

/**
 * 函数级注释：入口开关变更（原因必填 + 二次确认 + confirm_token）
 * @param item 配置项
 * @param newVal 目标开关值
 */
async function onSwitchChange(item: any, newVal: any): Promise<void> {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超管可操作')
    return
  }
  const action = newVal ? '开启' : '关闭'
  let reason = ''
  try {
    const r: any = await ElMessageBox.prompt(
      `确认${action}「${switchLabel(item, -1) || item.key}」？${action}入口开关将立即影响用户侧可用性，请填写变更原因。`,
      '系统开关变更',
      {
        confirmButtonText: '下一步',
        cancelButtonText: '取消',
        inputValidator: (v: string) => (v && v.trim() ? true : '原因必填'),
      }
    )
    reason = r.value.trim()
  } catch {
    return // 用户取消，开关不变更（model-value 未绑定，状态自动回弹）
  }
  try {
    // 保持 snapshot 原结构（{name, enabled}），仅覆盖 enabled 字段
    const prev = item.value
    const nextSnapshot =
      prev !== null && typeof prev === 'object' && !Array.isArray(prev)
        ? { ...prev, enabled: !!newVal }
        : { enabled: !!newVal }
    await withConfirm(
      (confirmToken?: string) =>
        adminApi.configUpdate(item.key, {
          snapshot: nextSnapshot,
          reason,
          confirm_token: confirmToken,
        }),
      { message: `该开关直接影响线上入口可用性，确认${action}？` }
    )
    item.value = nextSnapshot
    ElMessage.success(`已${action}`)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '开关变更失败')
  }
}

/**
 * 函数级注释：保存文本型配置（价格/AI 文案），原因必填 + 二次确认
 * @param key 配置键
 * @param text 配置文本（JSON）
 * @returns 是否保存成功
 */
async function saveTextConfig(key: string, text: string): Promise<boolean> {
  // JSON 合法性预校验
  let parsedValue: any = text
  try {
    parsedValue = JSON.parse(text)
  } catch {
    ElMessage.warning('配置内容不是合法 JSON，请检查')
    return false
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
    return false
  }
  configSavingKey.value = key
  try {
    await withConfirm(
      (confirmToken?: string) =>
        adminApi.configUpdate(key, { snapshot: { value: parsedValue }, reason, confirm_token: confirmToken }),
      { message: '配置变更将影响线上行为，确认保存？' }
    )
    ElMessage.success('配置已保存')
    loadConfigs()
    return true
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '保存失败')
    return false
  } finally {
    configSavingKey.value = ''
  }
}

/**
 * 函数级注释：保存当前全部文本型配置（仅提交与初始快照相比发生变化的项；仅超管）
 */
async function saveAllConfigs(): Promise<void> {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超管可操作')
    return
  }
  const changed: { key: string; text: string }[] = []
  if (pricingText.value !== initialPricing.value) changed.push({ key: 'pricing_config', text: pricingText.value })
  if (copywritingText.value !== initialCopy.value) changed.push({ key: 'ai_copywriting', text: copywritingText.value })
  if (!changed.length) {
    ElMessage.info('配置未发生变更')
    return
  }
  // JSON 合法性预校验
  for (const c of changed) {
    try {
      JSON.parse(c.text)
    } catch {
      ElMessage.warning(`${c.key} 内容不是合法 JSON，请检查`)
      return
    }
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
  try {
    await withConfirm(
      async (confirmToken?: string) => {
        for (const c of changed) {
          await adminApi.configUpdate(c.key, {
            snapshot: { value: JSON.parse(c.text) },
            reason,
            confirm_token: confirmToken,
          })
        }
      },
      { message: '配置变更将影响线上行为，确认保存？' }
    )
    ElMessage.success('配置已保存')
    loadConfigs()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '保存失败')
  }
}

/**
 * 函数级注释：修改价格（prompt 输入金额（元）→ 必填原因 → 二次确认更新商品 price_micro；仅超管）
 */
async function modifyPrice(): Promise<void> {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超管可操作')
    return
  }
  let input = ''
  try {
    const r: any = await ElMessageBox.prompt('请输入新的月费价格（元/月）', '修改价格', {
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputPattern: /^\d+(\.\d{1,2})?$/,
      inputErrorMessage: '请输入合法金额（最多两位小数）',
    })
    input = String(r.value).trim()
  } catch {
    return
  }
  let reason = ''
  try {
    const r: any = await ElMessageBox.prompt('请填写本次价格变更原因（写入审计日志）', '变更原因', {
      confirmButtonText: '下一步',
      cancelButtonText: '取消',
      inputValidator: (v: string) => (v && v.trim() ? true : '原因必填'),
    })
    reason = r.value.trim()
  } catch {
    return
  }
  const priceMicro = Math.round(Number(input) * 1_000_000)
  const code = memberProduct.value?.product_code || 'member_monthly'
  configSavingKey.value = 'product_price'
  try {
    await withConfirm(
      (confirmToken?: string) =>
        adminApi.productUpdate(code, { price_micro: priceMicro, reason, confirm_token: confirmToken }),
      { message: '价格变更将影响用户侧下单金额，确认保存？' }
    )
    ElMessage.success('价格已更新')
    loadProductPrice()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '价格更新失败')
  } finally {
    configSavingKey.value = ''
  }
}

/**
 * 函数级注释：保存 AI 文案（弹窗内确认，保存成功后关闭弹窗）
 */
async function saveAiCopy(): Promise<void> {
  const ok = await saveTextConfig('ai_copywriting', copywritingText.value)
  if (ok) aiEditVisible.value = false
}

/**
 * 函数级注释：灰度发布策略切换（发布网络配置接口未接入，前端提示）
 */
function graySwitch(): void {
  ElMessage.info('灰度发布策略切换将接入发布网络配置，暂未开放')
}

/**
 * 函数级注释：打开权利处理流程卡（切换选中行并重置表单）
 * @param row 权利请求行数据
 */
function openProcess(row: any): void {
  if (isPicked(row)) {
    currentRight.value = null
    return
  }
  currentRight.value = row
  processForm.action = 'generate_export'
  processForm.format = 'json'
  processForm.reject_reason_code = ''
  processForm.category = row.right_type || 'export'
  delivery.value = 'email'
  rejectNote.value = ''
}

/**
 * 函数级注释：执行权利请求处理动作（拒绝时理由码+法律依据详述必填）
 * @param action 动作：generate_export / mark_done / reject
 */
async function doProcess(action: string): Promise<void> {
  processForm.action = action
  if (action === 'reject') {
    if (!processForm.reject_reason_code) {
      ElMessage.warning('拒绝时必须选择拒绝理由码')
      return
    }
    if (!rejectNote.value.trim()) {
      ElMessage.warning('拒绝时必须详尽填写法律依据及事实支撑')
      return
    }
  }
  processing.value = true
  try {
    const data: any = await adminApi.rightsProcess(currentRight.value.request_no, {
      action,
      format: action === 'generate_export' ? processForm.format : undefined,
      reject_reason_code: action === 'reject' ? processForm.reject_reason_code : undefined,
    })
    if (action === 'generate_export') {
      const url = data?.download_url || data?.url
      if (url) {
        // 新窗口下载导出文件
        window.open(url, '_blank')
        ElMessage.success('导出文件已生成')
      } else {
        ElMessage.success('导出任务已提交，稍后可在列表查看状态')
      }
    } else {
      ElMessage.success('处理成功')
    }
    currentRight.value = null
    loadRights()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '处理失败')
  } finally {
    processing.value = false
  }
}

/**
 * 函数级注释：打开配置变更历史抽屉
 * @param key 配置键
 */
async function openHistory(key: string): Promise<void> {
  historyKey.value = key
  historyVisible.value = true
  historyLoading.value = true
  try {
    const data: any = await adminApi.configHistory(key)
    historyRows.value = data?.list || data?.items || data || []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '变更历史加载失败')
    historyRows.value = []
  } finally {
    historyLoading.value = false
  }
}

/**
 * 函数级注释：回滚配置到指定版本（二次确认 + confirm_token）
 * @param key 配置键
 * @param targetVersion 目标版本号
 */
async function rollbackTo(key: string, targetVersion: number): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认将配置 ${key} 回滚到 v${targetVersion}？`, '二次确认', {
      type: 'warning',
      confirmButtonText: '确认回滚',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await adminApi.configRollback(key, { target_version: targetVersion, confirm_token: CONFIRM_TOKEN })
    ElMessage.success('已回滚')
    historyVisible.value = false
    loadConfigs()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '回滚失败')
  }
}

/**
 * 函数级注释：一键回滚到上一版本（取变更历史最新两条，回滚到较早的一条）
 * @param key 配置键
 */
async function quickRollback(key: string): Promise<void> {
  if (!isSuperAdmin.value) {
    ElMessage.warning('仅超管可操作')
    return
  }
  try {
    const data: any = await adminApi.configHistory(key)
    const rows: any[] = data?.list || data?.items || data || []
    if (rows.length < 2) {
      ElMessage.warning('暂无可回滚的历史版本')
      return
    }
    // 历史按版本倒序时第二行即上一版本；按正序时取倒数第二
    const sorted = rows.slice().sort((a, b) => Number(b.version) - Number(a.version))
    await rollbackTo(key, sorted[1].version)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '获取变更历史失败')
  }
}

/**
 * 函数级注释：导出权利处理记录为 CSV（前端本地生成）
 */
function exportRightsCsv(): void {
  const header = ['请求号', '权利类型', '用户ID', 'SLA剩余', '处理状态', '处理人']
  const lines = filteredRights.value.map((r) => [
    r.request_no,
    rightTypeLabel(r.right_type),
    r.user_id || r.user_name || '--',
    slaText(r),
    rightStatusLabel(r.status),
    r.handler || r.assignee || '--',
  ])
  const csv =
    '\ufeff' +
    [header, ...lines].map((cells) => cells.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `rights-records-${Date.now()}.csv`)
  ElMessage.success('处理记录已导出')
}

onMounted(() => {
  loadRights()
  loadConfigs()
  loadProductPrice()
})
</script>

<style scoped lang="scss">
/* 页面纵向排布 */
.rc-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------- 卡片头 ---------- */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.head-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.head-ico {
  color: var(--accent);
  font-size: 24px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

/* 待处理红标 */
.pending-badge {
  padding: 1px 10px;
  border-radius: var(--radius-pill);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--fs-sub);
  font-weight: 500;
}

.head-note {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* 状态点通用 */
.ok-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

/* ---------- 快捷筛选行 ---------- */
.quick-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-bright);
}

.qf-fields {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.qf-label {
  color: var(--ink-2);
  font-size: var(--fs-sub);
  font-weight: 500;
}

.qf-ctrl {
  width: 170px;
}

.qf-side {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* ---------- 请求表 ---------- */
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

.type-cell {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--ink-1);
  font-weight: 500;
}

.type-ico {
  color: var(--accent);

  &.danger {
    color: var(--danger);
  }
}

.uid {
  color: var(--ink-2);
}

/* SLA 徽章 */
.sla-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--radius-ctl);
  font-size: var(--fs-caption);
  font-weight: 500;
  white-space: nowrap;

  &.near {
    background: var(--warn-soft);
    color: var(--warn);
  }

  &.urgent {
    border: 1px solid var(--danger);
    background: var(--danger-soft);
    color: var(--danger);
    font-weight: 700;
  }

  &:not(.near):not(.urgent) {
    background: var(--surface-2);
    color: var(--ink-2);
  }
}

/* 进入处理 chip */
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

.op-link {
  border: none;
  background: none;
  color: var(--accent);
  font-size: var(--fs-caption);
  font-weight: 500;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }

  &.urgent {
    color: var(--danger);
    font-weight: 700;
  }
}

/* ---------- 工单处理流程卡 ---------- */
.process-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-face);
  background: var(--sc-low);
}

.process-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}

.process-title {
  display: flex;
  align-items: center;
  gap: 8px;

  .title-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
  }

  h3 {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);

    .accent {
      color: var(--accent);
    }

    .plain {
      font-weight: 400;
      color: var(--ink-2);
    }
  }
}

.verify-note {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-3);
  font-size: var(--fs-caption);

  .el-icon {
    color: var(--accent);
  }
}

/* 三列配置 */
.process-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.p-field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    color: var(--ink-2);
    font-size: var(--fs-sub);
    font-weight: 500;
  }
}

/* 分段切换按钮组 */
.seg-toggle {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  height: 40px;
}

.seg-opt {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-2);
  font-size: var(--fs-caption);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;

  &:hover:not(.active) {
    color: var(--ink-1);
  }

  &.active {
    border-color: var(--line);
    background: var(--surface);
    color: var(--accent);
    font-weight: 500;
    box-shadow: var(--shadow-e1);
  }
}

/* 拒绝抗辩理由区 */
.reject-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.p-label {
  color: var(--ink-2);
  font-size: var(--fs-sub);
  font-weight: 500;
}

.tip {
  color: var(--ink-3);
  font-size: var(--fs-caption);
  font-weight: 400;
}

.reject-code-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.code-select {
  width: 220px;
}

/* 底部按钮行 */
.process-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.pf-btns {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-reject {
  --el-button-bg-color: var(--danger-soft);
  --el-button-border-color: var(--danger);
  --el-button-text-color: var(--danger);
  --el-button-hover-bg-color: var(--danger);
  --el-button-hover-border-color: var(--danger);
  --el-button-hover-text-color: #fff;
}

.audit-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  color: var(--ink-3);
  font-size: var(--fs-caption);

  .el-icon {
    color: var(--accent);
  }
}

/* ---------- 下半区：系统配置 ---------- */
.config-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sync-chip {
  padding: 1px 8px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.engine-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-2);
  font-size: var(--fs-caption);
}

/* 熔断卡（黄色警示底） */
.fuse-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--warn);
  border-radius: var(--radius-face);
  background: var(--warn-soft);
}

.fuse-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.fuse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 600;

  .el-icon {
    color: var(--warn);
    font-size: 18px;
  }
}

.fuse-tip {
  color: var(--warn);
  font-size: var(--fs-caption);
  font-weight: 500;
}

.fuse-switches {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.fuse-label {
  color: var(--ink-2);
  font-size: var(--fs-sub);
}

.muted {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* 2×2 配置卡网格 */
.cfg-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.cfg-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  background: var(--surface-bright);
  transition: border-color 0.15s ease;

  &:hover {
    border-color: var(--line-strong);
  }
}

.cfg-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.cfg-name {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 500;

  .el-icon {
    color: var(--ink-2);
  }
}

.cfg-value {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.price-num {
  color: var(--accent);
  font-size: var(--fs-title);
  font-weight: 700;
}

.price-unit {
  color: var(--ink-2);
  font-size: var(--fs-sub);
}

.code-chip {
  padding: 2px 8px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--surface);
  color: var(--ink-1);
  font-size: var(--fs-caption);
  font-weight: 500;
}

.expire-chip {
  padding: 2px 8px;
  border: 1px solid var(--warn);
  border-radius: 4px;
  background: var(--warn-soft);
  color: var(--warn);
  font-size: var(--fs-caption);
}

.gray-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.gray-chip {
  padding: 1px 8px;
  border-radius: 4px;
  font-size: var(--fs-caption);
  font-weight: 500;

  &.on {
    background: var(--accent-soft);
    color: var(--accent);
  }

  &.off {
    background: var(--surface-2);
    color: var(--ink-3);
  }
}

/* 底部操作条 */
.config-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.cf-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.key-select {
  width: 200px;
}

.foot-note {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-3);
  font-size: var(--fs-caption);

  .el-icon {
    color: var(--accent);
  }
}

.btn-wrap {
  display: inline-block;
}

/* 响应式：窄屏单列 */
@media (max-width: 900px) {
  .process-grid,
  .cfg-grid,
  .report-grid {
    grid-template-columns: 1fr;
  }
}

/* 手机窄屏（375 视口）：配置项按钮换行、控件收缩，消除横向滚动 */
@media (max-width: 640px) {
  .cfg-item {
    flex-wrap: wrap;
  }
  .cfg-item .el-button,
  .cfg-item .btn-wrap {
    margin-left: auto;
  }
  .qf-ctrl,
  .key-select {
    flex: 1 1 100%;
    width: auto;
    min-width: 0;
  }
  .qf-fields {
    flex: 1 1 100%;
  }
  .reject-code-row {
    flex-wrap: wrap;
  }
  .reject-code-row .el-input {
    flex: 1;
    width: auto;
    min-width: 0;
  }
}
</style>
