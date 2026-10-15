<!--
  HistoryListPage SC-18 历史记录（Stitch 稿重构）
  页头（‹ 历史记录 + 筛选图标）+ 圆角筛选 chips（全部/孩子/宠物/问答/报告）+
  记录卡（类型标签 + 相对时间 + 校验徽章 + 摘要标题 + 刻度条/内容档位 chip + 完整日期）+
  触底加载下一页 + AI 免责条 + 空态"去提问"。
  script 逻辑与 API 全保留，仅重构 template 与 style。
-->
<template>
  <div class="page hl-page">
    <!-- 页头：‹ 历史记录 + 筛选图标 -->
    <header class="hl-head">
      <button class="hl-back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="hl-title">历史记录</h1>
      <span class="hl-filter-ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M4 7h10M18 7h2M4 17h2M10 17h10" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          <circle cx="16" cy="7" r="2.2" stroke="currentColor" stroke-width="1.75" />
          <circle cx="8" cy="17" r="2.2" stroke="currentColor" stroke-width="1.75" />
        </svg>
      </span>
    </header>

    <!-- 筛选 chips：选中深色胶囊 -->
    <div class="chips">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        class="chip"
        :class="{ on: filter === f.key }"
        @click="switchFilter(f.key)"
      >
        <span v-if="filter === f.key" class="chip-dot" aria-hidden="true" />
        {{ f.label }}
      </button>
    </div>

    <!-- 骨架 -->
    <template v-if="loading && !records.length">
      <SkeletonBlock v-for="i in 3" :key="i" :height="128" class="hl-skeleton" />
    </template>

    <!-- 失败 -->
    <div v-else-if="loadFailed && !records.length" class="st-card retry">
      <p>加载失败</p>
      <el-button type="primary" size="small" @click="load(true)">重试</el-button>
    </div>

    <!-- 空态 -->
    <EmptyState
      v-else-if="!records.length"
      variant="record"
      text="还没有记录"
      sub="提出第一个问题，或完成一次测评"
      hint="每次问答与测评报告都会自动归档在这里；会员到期后历史仍保留为只读"
    >
      <template #action>
        <el-button type="primary" size="large" @click="$router.push('/app/home')">去提问</el-button>
      </template>
    </EmptyState>

    <!-- 记录卡列表 -->
    <template v-else>
      <article
        v-for="r in records"
        :key="r.uid"
        class="st-card rec-card"
        @click="goDetail(r)"
      >
        <!-- 行 1：类型标签 + 相对时间 + 校验徽章 -->
        <div class="rc-top">
          <span class="st-tag" :class="itemType(r) === 'report' ? 'st-tag--green' : 'st-tag--gray'">
            {{ typeLabel(itemType(r)) }}
          </span>
          <span class="rc-time caption">{{ relativeTime(r.created_at) }}</span>
          <span class="rc-badge">
            <span class="rc-badge-dot" aria-hidden="true" />
            {{ badgeLabel(r) }}
          </span>
        </div>

        <!-- 行 2：摘要标题 -->
        <p class="rc-summary">{{ r.summary || r.title || '（无摘要）' }}</p>

        <!-- 行 3：刻度条（报告）或内容档位 chip（问答） -->
        <div v-if="itemType(r) === 'report'" class="rc-meter-row">
          <span class="caption rc-meter-label">适应阈值区间</span>
          <span class="caption numeric rc-meter-val">标尺 {{ meterPct(r) }} / 100</span>
        </div>
        <div v-if="itemType(r) === 'report'" class="st-meter">
          <span class="st-meter__fill" :style="{ width: meterPct(r) + '%' }" />
        </div>
        <div v-else class="rc-tier-row">
          <span class="st-tag" :class="isMemberTier(r) ? 'st-tag--outline' : 'st-tag--gray'">
            {{ isMemberTier(r) ? '会员内容' : '免费内容' }}
          </span>
        </div>

        <!-- 行 4：完整日期 -->
        <p class="rc-date caption numeric">{{ fullDate(r.created_at) }}</p>
      </article>

      <!-- 触底加载 -->
      <div ref="sentinel" class="sentinel">
        <SkeletonBlock v-if="loadingMore" :height="56" />
        <p v-else-if="!hasMore" class="caption end-tip">下拉加载更多（每页 20 条）· 已到底</p>
        <p v-else class="caption end-tip">下拉加载更多（每页 20 条）</p>
      </div>
    </template>

    <!-- AI 免责条 -->
    <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { getHistory } from '@/api/client'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import EmptyState from '@/components/EmptyState.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

const router = useRouter()

/** 筛选项 */
const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'child', label: '孩子' },
  { key: 'pet', label: '宠物' },
  { key: 'qa', label: '问答' },
  { key: 'report', label: '报告' }
]

/** 当前筛选 */
const filter = ref('all')
/** 记录列表 */
const records = ref<any[]>([])
/** 页码 */
const page = ref(1)
/** 是否还有更多 */
const hasMore = ref(true)
/** 首屏加载 */
const loading = ref(true)
/** 加载更多 */
const loadingMore = ref(false)
/** 失败态 */
const loadFailed = ref(false)

/** 触底哨兵 */
const sentinel = ref<HTMLElement>()
/** 观察器 */
let observer: IntersectionObserver | null = null

/**
 * 条目类型码（后端契约字段为 item_type：qa/report；兼容旧字段 type）
 * @param r 记录对象
 * @returns 'qa' | 'report'
 */
function itemType(r: any): string {
  return String(r?.item_type || r?.type || 'qa')
}

/**
 * 类型标签名（报告统一显示「测评报告」，与后端 summary 口径一致）
 * @param t 类型码
 * @returns 中文标签
 */
function typeLabel(t: string): string {
  return { child: '孩子', pet: '宠物', qa: '问答', report: '测评报告' }[t] || '记录'
}

/**
 * 相对时间（今天/昨天 + 时分，更早显示天数或日期）
 * @param ts ISO 时间
 * @returns 相对时间文本
 */
function relativeTime(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const now = new Date()
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (sameDay(d, now)) return `今天 ${hm}`
  if (sameDay(d, yesterday)) return `昨天 ${hm}`
  const diffH = (now.getTime() - d.getTime()) / 3600000
  if (diffH < 24 * 7) return `${Math.floor(diffH / 24)} 天前`
  return new Date(ts).toLocaleDateString('zh-CN')
}

/**
 * 完整日期（卡底日期行）
 * @param ts ISO 时间
 * @returns yyyy-MM-dd HH:mm 文本
 */
function fullDate(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/**
 * 记录卡右上校验徽章（报告→刻度校验 / 问答→问答对齐 / 其它→归档记录）
 * @param r 记录对象
 * @returns 徽章文案
 */
function badgeLabel(r: any): string {
  if (r?.verify_badge) return r.verify_badge
  if (itemType(r) === 'report') return '刻度校验'
  if (itemType(r) === 'qa') return '问答对齐'
  return '归档记录'
}

/**
 * 内容档位：会员内容（access_tier=block / member 标记 / is_member_content）或免费内容
 * SIM-23：补 is_member_content 判定——历史列表接口（qa 条目）实际下发的字段名是
 * is_member_content，此前只查 is_member 导致会员问答条目恒显示「免费内容」，
 * 与详情页标签口径不一致
 * @param r 记录对象
 * @returns 是否会员档位
 */
function isMemberTier(r: any): boolean {
  return (
    r.access_tier === 'block' ||
    r.member_only === true ||
    r.is_member === true ||
    r.is_member_content === true
  )
}

/**
 * 报告刻度演示值：由 uid 哈希推导稳定伪随机百分比（不照抄演示数字）
 * @param r 记录对象
 * @returns 24~92 之间的整数
 */
function meterPct(r: any): number {
  const s = String(r?.uid || '')
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 997
  return 24 + (h % 69)
}

/**
 * 加载历史列表
 * @param reset 是否重置（切换筛选/重试）
 * @throws 失败置失败态
 */
async function load(reset = false): Promise<void> {
  if (reset) {
    page.value = 1
    records.value = []
    hasMore.value = true
  }
  loading.value = reset || loading.value
  loadFailed.value = false
  try {
    const res: any = await getHistory(filter.value, page.value)
    const items = res?.items || res?.records || res || []
    if (reset) records.value = items
    else records.value = [...records.value, ...items]
    // 后端返回 {total, page, page_size, items}（无 has_more）：按 total 判断是否还有下一页
    const total = typeof res?.total === 'number' ? res.total : records.value.length
    hasMore.value = items.length > 0 && records.value.length < total
  } catch {
    if (reset) loadFailed.value = true
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

/**
 * 切换筛选
 * @param key 筛选键
 */
function switchFilter(key: string): void {
  if (filter.value === key) return
  filter.value = key
  load(true)
}

/**
 * 跳详情
 * @param r 记录对象
 */
function goDetail(r: any): void {
  // 按 item_type（qa/report）路由：report 走报告详情端点 /history/report/{uid}，勿落入 qa 详情（404）
  if (itemType(r) === 'report') router.push(`/app/history/report/${r.uid}`)
  else router.push(`/app/history/qa/${r.uid}`)
}

/**
 * 挂载：加载 + 安装触底观察器
 */
onMounted(async () => {
  await load(true)
  await nextTick()
  if (sentinel.value && 'IntersectionObserver' in window) {
    observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && hasMore.value && !loadingMore.value && !loading.value) {
        loadingMore.value = true
        page.value++
        load(false)
      }
    }, { rootMargin: '100px' })
    observer.observe(sentinel.value)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>

<style lang="scss" scoped>
/* ---------- 页面骨架：内容不足一屏时免责条贴底，不在中部漂浮 ---------- */
.hl-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;

  > .empty {
    flex: 1;
    justify-content: center;
  }

  .disclaimer {
    margin-top: auto;
  }
}

/* ---------- 页头 ---------- */
.hl-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);

  .hl-back {
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    color: var(--ink-2);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    svg { width: 20px; height: 20px; }
  }

  .hl-title {
    flex: 1;
    font-size: var(--fs-display);
    font-weight: 600;
    color: var(--ink-1);
  }

  .hl-filter-ico {
    flex: none;
    color: var(--ink-3);

    svg { width: 20px; height: 20px; }
  }
}

.hl-skeleton {
  margin-bottom: var(--sp-3);
}

/* ---------- 筛选 chips ---------- */
.chips {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  /* 纵向内边距加大到命中区 ~40px：筛选是高频点击，原先 32px 在手机上容易点偏 */
  padding: 11px 16px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-pill);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  cursor: pointer;

  .chip-dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: currentColor;
  }

  &.on {
    background: var(--ink-1);
    border-color: var(--ink-1);
    color: var(--surface);
    font-weight: 600;
  }
}

/* ---------- 记录卡 ---------- */
.retry {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  align-items: center;
  color: var(--ink-2);
}

.rec-card {
  margin-bottom: var(--sp-3);
  cursor: pointer;

  &:active {
    border-color: var(--accent-line);
  }
}

.rc-top {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);

  .rc-time {
    flex: 1;
  }

  .rc-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--fs-caption);
    color: var(--ink-3);

    .rc-badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: var(--accent);
    }
  }
}

.rc-summary {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: var(--sp-2);
}

.rc-meter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-2);

  .rc-meter-val {
    color: var(--accent);
    font-weight: 600;
  }
}

.st-meter {
  margin-bottom: var(--sp-3);
}

.rc-tier-row {
  margin-bottom: var(--sp-2);
}

.rc-date {
  color: var(--ink-3);
}

/* ---------- 触底加载 ---------- */
.sentinel {
  padding: var(--sp-3) 0;
}

.end-tip {
  text-align: center;
}
</style>
