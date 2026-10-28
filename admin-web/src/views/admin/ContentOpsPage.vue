<!--
  文件级注释：V3.1 内容运营页（RQ-12 / RQ-13 / RQ-14；菜单键 content）
  - 两个 tab：专题包（含草稿、双签与上架校验问题）/ 轻工具（含内容合规问题）
  - 专题包：GET /admin/topics 列表（status / publish_issues / 育儿+宠物双签状态 /
    价格 / 红旗前置）；新建与编辑对话框（topic_code 编辑时只读）、
    redflag_blocks 与 content_blocks 用 JSON 文本域编辑，保存走 POST /admin/topics。
    status=on 且不满足条件时后端返回 422（code=1001）并把问题写在 message 里，原样展示。
  - 轻工具：GET /admin/tools 列表（tool_type / issues / kb_refs / 排序）；
    新建与编辑对话框，content 用 JSON 文本域编辑，保存走 POST /admin/tools；
    内容含「能吃 / 不能吃」类确定性结论时后端 422，message 原样展示。
  - 保存成功一律重新拉取列表（后端返回的 publish_issues / issues 是唯一校验口径）。
-->
<template>
  <div class="content-page">
    <!-- ═══ 1. 页头卡 ═══ -->
    <section class="st-card head-card">
      <div class="head-text">
        <h2 class="head-title">内容运营（专题包 / 轻工具）</h2>
        <p class="head-sub">
          专题包独立计费、会员不享；交叉主题须育儿 + 宠物双签、红旗前置；轻工具内容取自知识资产
        </p>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button
          v-if="canEdit && activeTab === 'topics'"
          type="primary"
          :icon="Plus"
          @click="openTopicCreate"
        >
          新建专题包
        </el-button>
        <el-button v-else-if="canEdit" type="primary" :icon="Plus" @click="openToolCreate">新建轻工具</el-button>
      </div>
    </section>

    <!-- ═══ 2. tab 切换 ═══ -->
    <el-tabs v-model="activeTab" class="content-tabs">
      <!-- ─────────── 专题包 ─────────── -->
      <el-tab-pane label="专题包" name="topics">
        <section class="st-card table-card">
          <el-table :data="topics" v-loading="loading" size="small" row-key="topic_code">
            <el-table-column label="编码" width="140">
              <template #default="{ row }">
                <span class="numeric code-cell">{{ row.topic_code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="标题" min-width="180">
              <template #default="{ row }">
                <span class="title-cell">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column label="领域" width="100">
              <template #default="{ row }">{{ domainLabel(row.domain) }}</template>
            </el-table-column>
            <el-table-column label="价格" width="100">
              <template #default="{ row }">
                <span class="numeric">{{ priceText(row.price_micro) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="红旗前置" width="100">
              <template #default="{ row }">
                <span class="st-tag st-tag--plain" :class="row.redflag_first ? 'st-tag--green' : 'st-tag--gray'">
                  {{ row.redflag_first ? '已前置' : '未前置' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="双签状态" width="160">
              <template #default="{ row }">
                <span class="sign-cell">
                  <span class="st-tag st-tag--plain" :class="row.review_child_signoff ? 'st-tag--green' : 'st-tag--gray'">
                    育儿 {{ row.review_child_signoff ? '已签' : '未签' }}
                  </span>
                  <span class="st-tag st-tag--plain" :class="row.review_pet_signoff ? 'st-tag--green' : 'st-tag--gray'">
                    宠物 {{ row.review_pet_signoff ? '已签' : '未签' }}
                  </span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <span class="st-tag" :class="topicStatusClass(row.status)">{{ topicStatusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="上架校验" min-width="220">
              <template #default="{ row }">
                <span v-if="row.publish_issues?.length" class="issue-list">
                  <span v-for="(issue, i) in row.publish_issues" :key="i" class="issue-item">{{ issue }}</span>
                </span>
                <span v-else class="ok-text">无阻塞问题</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canEdit" link type="primary" size="small" @click="openTopicEdit(row)">编辑</el-button>
                <span v-else class="muted">只读</span>
              </template>
            </el-table-column>
            <template #empty><el-empty description="暂无专题包" /></template>
          </el-table>
          <div class="table-foot">
            <span>共 {{ topics.length }} 个专题包（含草稿与已下架）</span>
            <span>上架校验由服务端判定，前端不自行判定可上架</span>
          </div>
        </section>
      </el-tab-pane>

      <!-- ─────────── 轻工具 ─────────── -->
      <el-tab-pane label="轻工具" name="tools">
        <section class="st-card table-card">
          <el-table :data="tools" v-loading="loading" size="small" row-key="tool_code">
            <el-table-column label="编码" width="140">
              <template #default="{ row }">
                <span class="numeric code-cell">{{ row.tool_code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="标题" min-width="180">
              <template #default="{ row }">
                <span class="title-cell">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="110">
              <template #default="{ row }">
                <span class="st-tag st-tag--plain" :class="row.tool_type === 'parser' ? 'st-tag--amber' : 'st-tag--green'">
                  {{ row.tool_type === 'parser' ? '解析器' : '清单' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="领域" width="90">
              <template #default="{ row }">{{ toolDomainLabel(row.domain) }}</template>
            </el-table-column>
            <el-table-column label="知识引用" width="100">
              <template #default="{ row }">
                <span class="numeric">{{ row.kb_refs?.length || 0 }} 条</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <span class="st-tag st-tag--plain" :class="row.status === 'on' ? 'st-tag--green' : 'st-tag--gray'">
                  {{ row.status === 'on' ? '已上架' : '已下架' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="排序" width="80">
              <template #default="{ row }">
                <span class="numeric">{{ row.sort_order }}</span>
              </template>
            </el-table-column>
            <el-table-column label="内容校验" min-width="220">
              <template #default="{ row }">
                <span v-if="row.issues?.length" class="issue-list">
                  <span v-for="(issue, i) in row.issues" :key="i" class="issue-item">{{ issue }}</span>
                </span>
                <span v-else class="ok-text">无阻塞问题</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canEdit" link type="primary" size="small" @click="openToolEdit(row)">编辑</el-button>
                <span v-else class="muted">只读</span>
              </template>
            </el-table-column>
            <template #empty><el-empty description="暂无轻工具" /></template>
          </el-table>
          <div class="table-foot">
            <span>共 {{ tools.length }} 个轻工具（含已下架）</span>
            <span>内容含确定性进食结论将被拒绝保存（AC-RQ12-4）</span>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>

    <!-- ═══ 3. 底部提示 ═══ -->
    <footer class="st-note">
      <el-icon class="note-ico"><InfoFilled /></el-icon>
      <div>
        <strong>上架口径：</strong>
        专题包 status=on 时必须满足双签与红旗前置，否则保存被拒绝并列出问题；
        轻工具内容不得给出「能吃 / 不能吃」类确定性结论，须引用知识资产（kb_refs）并提示就医边界。
      </div>
    </footer>

    <!-- ═══ 4. 专题包对话框 ═══ -->
    <el-dialog
      v-model="topicVisible"
      :title="topicEditing ? `编辑专题包 · ${topicForm.topic_code}` : '新建专题包'"
      width="720px"
    >
      <el-form label-width="130px">
        <el-form-item label="专题编码" required>
          <el-input v-model="topicForm.topic_code" :disabled="topicEditing" maxlength="32" placeholder="如：cross_bite_001" />
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="topicForm.title" maxlength="128" />
        </el-form-item>
        <el-form-item label="领域" required>
          <el-select v-model="topicForm.domain" style="width: 100%">
            <el-option label="cross（育儿 × 宠物交叉）" value="cross" />
            <el-option label="behavior（行为内容线）" value="behavior" />
            <el-option label="child（育儿）" value="child" />
            <el-option label="pet（宠物）" value="pet" />
          </el-select>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="topicForm.summary" type="textarea" :rows="2" maxlength="300" />
        </el-form-item>
        <el-form-item label="价格（元）">
          <el-input-number v-model="topicForm.price_yuan" :min="0" :precision="2" :step="1" controls-position="right" />
          <span class="field-hint">独立计费，会员不享；落库按 price_micro 存储</span>
        </el-form-item>
        <el-form-item label="商品编码">
          <el-input v-model="topicForm.product_code" maxlength="64" placeholder="指向 product 表（可留空）" />
        </el-form-item>
        <el-form-item label="红旗前置">
          <el-switch v-model="topicForm.redflag_first" />
          <span class="field-hint">开启后 redflag_blocks 必须在正文之前展示</span>
        </el-form-item>
        <el-form-item label="红旗区块（JSON）">
          <el-input
            v-model="topicForm.redflag_blocks"
            type="textarea"
            :rows="5"
            class="json-input"
            placeholder='[{"type":"redflag","title":"先看这一条","content":"..."}]'
          />
          <div v-if="redflagError" class="json-error">{{ redflagError }}</div>
        </el-form-item>
        <el-form-item label="正文区块（JSON）">
          <el-input
            v-model="topicForm.content_blocks"
            type="textarea"
            :rows="6"
            class="json-input"
            placeholder='[{"type":"section","title":"...","content":"..."}]'
          />
          <div class="field-hint">
            编辑时已自动剔除后端视图合并进来的红旗区块前缀，保存不会重复；语法错误将在此处拦截。
          </div>
          <div v-if="contentError" class="json-error">{{ contentError }}</div>
        </el-form-item>
        <el-form-item label="育儿专家签署">
          <el-input v-model="topicForm.review_child_signoff" maxlength="64" placeholder="姓名 / 工号" />
        </el-form-item>
        <el-form-item label="宠物专家签署">
          <el-input v-model="topicForm.review_pet_signoff" maxlength="64" placeholder="姓名 / 工号" />
        </el-form-item>
        <el-form-item label="状态" required>
          <el-select v-model="topicForm.status" style="width: 100%">
            <el-option label="draft（草稿）" value="draft" />
            <el-option label="on（上架）" value="on" />
            <el-option label="off（下架）" value="off" />
          </el-select>
          <div class="field-hint">选择 on 时后端校验双签与红旗前置，不满足则返回 422 并列出问题</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="topicVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTopic" @click="submitTopic">保存</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 5. 轻工具对话框 ═══ -->
    <el-dialog
      v-model="toolVisible"
      :title="toolEditing ? `编辑轻工具 · ${toolForm.tool_code}` : '新建轻工具'"
      width="680px"
    >
      <el-form label-width="130px">
        <el-form-item label="工具编码" required>
          <el-input v-model="toolForm.tool_code" :disabled="toolEditing" maxlength="32" placeholder="如：checklist_bite" />
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="toolForm.title" maxlength="128" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="toolForm.tool_type" style="width: 100%">
            <el-option label="checklist（清单）" value="checklist" />
            <el-option label="parser（解析器）" value="parser" />
          </el-select>
        </el-form-item>
        <el-form-item label="领域">
          <el-select v-model="toolForm.domain" style="width: 100%">
            <el-option label="child（育儿）" value="child" />
            <el-option label="pet（宠物）" value="pet" />
          </el-select>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="toolForm.summary" type="textarea" :rows="2" maxlength="300" />
        </el-form-item>
        <el-form-item label="知识引用">
          <el-input
            v-model="toolForm.kb_refs"
            type="textarea"
            :rows="3"
            placeholder="每行一个 kb_id（内容须来自知识资产，可追溯）"
          />
        </el-form-item>
        <el-form-item label="内容（JSON）">
          <el-input
            v-model="toolForm.content"
            type="textarea"
            :rows="8"
            class="json-input"
            placeholder='{"items":[{"label":"观察项","hint":"..."}]}'
          />
          <div class="field-hint">
            不得包含「能吃 / 不能吃」类确定性结论，否则后端拒绝保存（422）。
            列表接口不返回既有内容：编辑保存为全量覆盖，必须粘贴完整内容 JSON 后才能保存。
          </div>
          <div v-if="toolContentError" class="json-error">{{ toolContentError }}</div>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="toolForm.sort_order" :min="0" :max="9999" controls-position="right" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="toolForm.status" style="width: 100%">
            <el-option label="on（上架）" value="on" />
            <el-option label="off（下架）" value="off" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="toolVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTool" @click="submitTool">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。专题包与轻工具均为 upsert 语义（同编码即更新）；
 * 保存失败直接展示后端 message（422/code=1001 会逐条列出问题），成功后刷新列表。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Plus, Refresh } from '@element-plus/icons-vue'
import { adminApi, ApiError, getAdminInfo, type ToolItem, type TopicItem } from '../../api/admin'

/** 当前角色（内容维护 content:edit 仅 super_admin / operator；服务端 1103 仍为真边界） */
const role = String(getAdminInfo()?.role || '')
/** 是否可维护内容 */
const canEdit = ['super_admin', 'operator'].includes(role)

/** 专题包列表 */
const topics = ref<TopicItem[]>([])
/** 轻工具列表 */
const tools = ref<ToolItem[]>([])
/** 列表加载中 */
const loading = ref(false)
/** 当前 tab（topics / tools） */
const activeTab = ref<'topics' | 'tools'>('topics')

/** 专题包对话框可见性 / 编辑态 / 提交中 */
const topicVisible = ref(false)
const topicEditing = ref(false)
const savingTopic = ref(false)
/** 轻工具对话框可见性 / 编辑态 / 提交中 */
const toolVisible = ref(false)
const toolEditing = ref(false)
const savingTool = ref(false)

/** 专题包 JSON 语法错误 */
const redflagError = ref('')
/** 正文 JSON 语法错误 */
const contentError = ref('')
/** 轻工具内容 JSON 语法错误 */
const toolContentError = ref('')

/** 专题包表单（price_yuan 为元，提交转 price_micro） */
const topicForm = reactive({
  topic_code: '',
  title: '',
  domain: 'cross',
  summary: '',
  price_yuan: 0,
  product_code: '',
  redflag_first: true,
  redflag_blocks: '[]',
  content_blocks: '[]',
  review_child_signoff: '',
  review_pet_signoff: '',
  status: 'draft' as 'draft' | 'on' | 'off',
})

/** 轻工具表单（kb_refs 多行文本） */
const toolForm = reactive({
  tool_code: '',
  title: '',
  tool_type: 'checklist' as 'checklist' | 'parser',
  domain: 'child',
  summary: '',
  kb_refs: '',
  content: '{}',
  sort_order: 100,
  status: 'on',
})

/**
 * 函数级注释：专题领域中文名
 * @param d 领域编码
 * @returns 中文名
 */
function domainLabel(d: string): string {
  const map: Record<string, string> = {
    cross: '交叉主题',
    behavior: '行为内容',
    child: '育儿',
    pet: '宠物',
  }
  return map[d] || d || '--'
}

/**
 * 函数级注释：轻工具领域中文名
 * @param d 领域编码
 * @returns 中文名
 */
function toolDomainLabel(d: string): string {
  const map: Record<string, string> = { child: '育儿', pet: '宠物' }
  return map[d] || d || '--'
}

/**
 * 函数级注释：专题状态中文名
 * @param s 状态枚举
 * @returns 中文名
 */
function topicStatusLabel(s: string): string {
  const map: Record<string, string> = { draft: '草稿', on: '已上架', off: '已下架' }
  return map[s] || s || '--'
}

/**
 * 函数级注释：专题状态标签变体类
 * @param s 状态枚举
 * @returns st-tag 修饰类
 */
function topicStatusClass(s: string): string {
  if (s === 'on') return 'st-tag--green'
  if (s === 'draft') return 'st-tag--amber'
  return 'st-tag--gray'
}

/**
 * 函数级注释：价格展示（price_micro → 元，两位小数）
 * @param micro 微单位价格（1 元 = 1,000,000）
 * @returns 价格文案
 */
function priceText(micro?: number): string {
  const n = Number(micro || 0)
  if (!n) return '免费'
  return `${(n / 1_000_000).toFixed(2)} 元`
}

/**
 * 函数级注释：数组 ↔ 缩进 JSON 文本
 * @param list 区块数组
 * @returns JSON 文本
 */
function jsonOf(list?: Array<Record<string, any>>): string {
  try {
    return JSON.stringify(Array.isArray(list) ? list : [], null, 2)
  } catch {
    return '[]'
  }
}

/**
 * 函数级注释：解析 JSON 数组文本（非数组或语法错误抛出）
 * @param text JSON 文本
 * @param label 字段中文名（拼接错误提示）
 * @returns 区块数组
 */
function parseBlocks(text: string, label: string): Array<Record<string, any>> {
  const parsed = JSON.parse(text || '[]')
  if (!Array.isArray(parsed)) throw new Error(`${label}必须为 JSON 数组`)
  return parsed as Array<Record<string, any>>
}

/**
 * 函数级注释：拆分后端视图合并的区块（to_public 在 redflag_first 时把红旗区块
 * 前置拼进 content_blocks，编辑回填必须剔除，否则保存会重复红旗区块）
 * @param row 专题包行数据
 * @returns {redflag_blocks, content_blocks} 原始两段
 */
function splitBlocks(row: TopicItem): {
  redflag_blocks: Array<Record<string, any>>
  content_blocks: Array<Record<string, any>>
} {
  const redflag = Array.isArray(row.redflag_blocks) ? row.redflag_blocks : []
  const merged = Array.isArray(row.content_blocks) ? row.content_blocks : []
  if (!row.redflag_first || !redflag.length || merged.length < redflag.length) {
    return { redflag_blocks: redflag, content_blocks: merged }
  }
  const prefix = merged.slice(0, redflag.length)
  const samePrefix = JSON.stringify(prefix) === JSON.stringify(redflag)
  return {
    redflag_blocks: redflag,
    content_blocks: samePrefix ? merged.slice(redflag.length) : merged,
  }
}

/**
 * 函数级注释：加载两个列表（tab 各自独立数据源，一次拉全便于切换无等待）
 */
async function loadAll(): Promise<void> {
  loading.value = true
  try {
    const [topicData, toolData] = await Promise.all([
      adminApi.topicList().catch((e) => {
        ElMessage.error(e instanceof ApiError ? e.message : '专题包加载失败')
        return { items: [] as TopicItem[] }
      }),
      adminApi.toolList().catch((e) => {
        ElMessage.error(e instanceof ApiError ? e.message : '轻工具加载失败')
        return { items: [] as ToolItem[] }
      }),
    ])
    topics.value = Array.isArray(topicData?.items) ? topicData.items : []
    tools.value = Array.isArray(toolData?.items) ? toolData.items : []
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：打开新建专题包对话框
 */
function openTopicCreate(): void {
  topicEditing.value = false
  topicForm.topic_code = ''
  topicForm.title = ''
  topicForm.domain = 'cross'
  topicForm.summary = ''
  topicForm.price_yuan = 0
  topicForm.product_code = ''
  topicForm.redflag_first = true
  topicForm.redflag_blocks = '[]'
  topicForm.content_blocks = '[]'
  topicForm.review_child_signoff = ''
  topicForm.review_pet_signoff = ''
  topicForm.status = 'draft'
  redflagError.value = ''
  contentError.value = ''
  topicVisible.value = true
}

/**
 * 函数级注释：打开编辑专题包对话框（回填并拆分合并区块）
 * @param row 专题包行数据
 */
function openTopicEdit(row: TopicItem): void {
  const { redflag_blocks, content_blocks } = splitBlocks(row)
  topicEditing.value = true
  topicForm.topic_code = row.topic_code || ''
  topicForm.title = row.title || ''
  topicForm.domain = row.domain || 'cross'
  topicForm.summary = row.summary || ''
  topicForm.price_yuan = Number(row.price_micro || 0) / 1_000_000
  topicForm.product_code = row.product_code || ''
  topicForm.redflag_first = !!row.redflag_first
  topicForm.redflag_blocks = jsonOf(redflag_blocks)
  topicForm.content_blocks = jsonOf(content_blocks)
  topicForm.review_child_signoff = row.review_child_signoff || ''
  topicForm.review_pet_signoff = row.review_pet_signoff || ''
  topicForm.status = (row.status as 'draft' | 'on' | 'off') || 'draft'
  redflagError.value = ''
  contentError.value = ''
  topicVisible.value = true
}

/**
 * 函数级注释：提交专题包（status=on 时后端校验双签/红旗前置，失败原样展示 message）
 */
async function submitTopic(): Promise<void> {
  if (!topicForm.topic_code.trim() || !topicForm.title.trim()) {
    ElMessage.warning('专题编码与标题为必填项')
    return
  }
  let redflagBlocks: Array<Record<string, any>>
  let contentBlocks: Array<Record<string, any>>
  try {
    redflagBlocks = parseBlocks(topicForm.redflag_blocks, '红旗区块')
    redflagError.value = ''
  } catch (e: any) {
    redflagError.value = `红旗区块 JSON 解析失败：${e?.message || '语法错误'}`
    ElMessage.warning('红旗区块 JSON 语法有误')
    return
  }
  try {
    contentBlocks = parseBlocks(topicForm.content_blocks, '正文区块')
    contentError.value = ''
  } catch (e: any) {
    contentError.value = `正文区块 JSON 解析失败：${e?.message || '语法错误'}`
    ElMessage.warning('正文区块 JSON 语法有误')
    return
  }
  savingTopic.value = true
  try {
    await adminApi.topicUpsert({
      topic_code: topicForm.topic_code.trim(),
      title: topicForm.title.trim(),
      domain: topicForm.domain,
      summary: topicForm.summary.trim() || undefined,
      price_micro: Math.round(Number(topicForm.price_yuan || 0) * 1_000_000),
      product_code: topicForm.product_code.trim() || undefined,
      redflag_first: topicForm.redflag_first,
      redflag_blocks: redflagBlocks,
      content_blocks: contentBlocks,
      review_child_signoff: topicForm.review_child_signoff.trim() || undefined,
      review_pet_signoff: topicForm.review_pet_signoff.trim() || undefined,
      status: topicForm.status,
    })
    ElMessage.success('专题包已保存')
    topicVisible.value = false
    await loadAll()
  } catch (e) {
    // 422/code=1001 的 message 已逐条列出不满足的上架条件，原样展示
    ElMessage.error(e instanceof ApiError ? e.message : '专题包保存失败')
  } finally {
    savingTopic.value = false
  }
}

/**
 * 函数级注释：打开新建轻工具对话框
 */
function openToolCreate(): void {
  toolEditing.value = false
  toolForm.tool_code = ''
  toolForm.title = ''
  toolForm.tool_type = 'checklist'
  toolForm.domain = 'child'
  toolForm.summary = ''
  toolForm.kb_refs = ''
  toolForm.content = '{}'
  toolForm.sort_order = 100
  toolForm.status = 'on'
  toolContentError.value = ''
  toolVisible.value = true
}

/**
 * 函数级注释：打开编辑轻工具对话框
 * @param row 轻工具行数据
 */
function openToolEdit(row: ToolItem): void {
  toolEditing.value = true
  toolForm.tool_code = row.tool_code || ''
  toolForm.title = row.title || ''
  toolForm.tool_type = row.tool_type === 'parser' ? 'parser' : 'checklist'
  toolForm.domain = row.domain || 'child'
  toolForm.summary = row.summary || ''
  toolForm.kb_refs = Array.isArray(row.kb_refs) ? row.kb_refs.join('\n') : ''
  // 后台列表接口已回显 content（V3.1）：直接回填，避免「整块覆盖成空对象」
  toolForm.content = row.content && Object.keys(row.content).length ? JSON.stringify(row.content, null, 2) : ''
  toolForm.sort_order = Number(row.sort_order || 100)
  toolForm.status = row.status || 'on'
  toolContentError.value = ''
  toolVisible.value = true
}

/**
 * 函数级注释：提交轻工具（内容含确定性结论时后端 422，message 原样展示）
 */
async function submitTool(): Promise<void> {
  if (!toolForm.tool_code.trim() || !toolForm.title.trim()) {
    ElMessage.warning('工具编码与标题为必填项')
    return
  }
  let content: Record<string, any>
  if (!toolForm.content.trim()) {
    toolContentError.value = '请填写内容 JSON：保存为全量覆盖，空内容会清空工具正文'
    ElMessage.warning('请粘贴完整内容 JSON 后再保存（保存为全量覆盖）')
    return
  }
  try {
    const parsed = JSON.parse(toolForm.content || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('内容必须为 JSON 对象')
    }
    content = parsed
    toolContentError.value = ''
  } catch (e: any) {
    toolContentError.value = `内容 JSON 解析失败：${e?.message || '语法错误'}`
    ElMessage.warning('内容 JSON 语法有误')
    return
  }
  savingTool.value = true
  try {
    await adminApi.toolUpsert({
      tool_code: toolForm.tool_code.trim(),
      title: toolForm.title.trim(),
      tool_type: toolForm.tool_type,
      domain: toolForm.domain,
      summary: toolForm.summary.trim() || undefined,
      kb_refs: toolForm.kb_refs
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      content,
      sort_order: Number(toolForm.sort_order || 100),
      status: toolForm.status,
    })
    ElMessage.success('轻工具已保存')
    toolVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '轻工具保存失败')
  } finally {
    savingTool.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.content-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 页头 */
.head-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 24px;
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.head-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* tabs */
.content-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.table-card {
  padding: var(--sp-6);
}

.code-cell {
  font-size: var(--fs-caption);
  color: var(--ink-1);
}

.title-cell {
  color: var(--ink-1);
}

.sign-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.issue-item {
  font-size: var(--fs-caption);
  color: var(--danger);
  line-height: 1.5;
}

.ok-text {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.muted {
  color: var(--ink-3);
}

.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
  flex-wrap: wrap;
}

/* 对话框 */
.field-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ink-3);
  line-height: 1.6;
}

.json-error {
  margin-top: 6px;
  font-size: var(--fs-caption);
  color: var(--danger);
}

.json-input :deep(textarea) {
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  line-height: 1.6;
}

@media (max-width: 640px) {
  .head-card {
    padding: 16px;
  }
  .head-actions {
    flex-wrap: wrap;
  }
}
</style>
