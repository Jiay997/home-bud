<!--
  ReportImagePage SC-17 报告长图（Stitch 稿重构）
  版式：页头（‹ 报告长图）→ 标定校准协议·长图模式状态条（含免责占比/次数，来自长图 API）→
  长图画布卡（顶部标尺带 + 报告头卡 + 四维行为倾向刻度（GraduatedBand 档位化游标，无精确数值）+
  核心养育洞察集 + 波动提示黄条 + 法定免责声明（一）（二）卡（备案占位/二维码占位/编号）+
  底部标尺带）→ 隐私安全提示卡（7 项提示 + 打码开关 + 脸数计数）→ 保存报告主按钮 +
  分享好友/复制链接 → 底部 AI 免责。
  数据：GET /history/report/{uid}/image（sections 仅免费区块；disclaimer_ratio/count 合规元数据）。
  合规：仅呈现档位（低/中/高），剔除稿中精确数值；备案号未定用占位文案。
-->
<template>
  <div class="image-page">
    <!-- ===== 页头 ===== -->
    <header class="img-head">
      <button class="head-back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">报告长图</h1>
    </header>

    <!-- ===== 顶部状态指示条：标定校准协议 · 长图模式 ===== -->
    <div class="status-strip">
      <span class="strip-left">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6" />
          <path d="M7 9h.01M7 12h.01M7 15h.01M11 9h6M11 12h6M11 15h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
        <span>标定校准协议 · 长图模式</span>
      </span>
      <span v-if="imageMeta" class="strip-right caption">免责占比 {{ ratioPct }}% · 出现 {{ imageMeta.disclaimer_count }} 次</span>
    </div>

    <main class="img-main">
      <!-- 骨架 -->
      <template v-if="loading">
        <SkeletonBlock :height="120" style="margin-bottom: 14px" />
        <SkeletonBlock :height="220" style="margin-bottom: 14px" />
        <SkeletonBlock :height="180" />
      </template>

      <!-- 失败 -->
      <div v-else-if="loadFailed" class="st-card retry">
        <p>长图数据加载失败</p>
        <el-button type="primary" @click="load">重试</el-button>
      </div>

      <template v-else>
        <!-- ===== 长图画布卡 ===== -->
        <section class="canvas-card">
          <!-- SIM-20：免费用户长图平铺水印（会员态无水印）。
               image_meta 协议 V1 无会员字段，按前端已知会员态（user store isMember）渲染；
               文案用用户 uid 脱敏前缀 + 时间戳，低透明度平铺 + pointer-events 关闭，
               不拦截交互、不遮蔽正文与免责声明可读性。 -->
          <div v-if="showWatermark" class="wm-layer" aria-hidden="true">
            <span v-for="(t, i) in watermarkTiles" :key="i" class="wm-item">{{ t }}</span>
          </div>
          <!-- 顶部标尺装饰带 -->
          <div class="ruler-band is-top" />

          <div class="canvas-body">
            <!-- 报告头卡 -->
            <div class="img-report-head">
              <div class="irh-left">
                <span class="irh-chip">成长观察报告档</span>
                <h2 class="irh-title">{{ nickname }} · {{ typeName }}气质报告</h2>
              </div>
              <div class="irh-badge">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M9.5 3a6.5 6.5 0 0 1 6.5 6.5c0 1.7-.7 3.3-1.8 4.4-.8.8-1.2 1.9-1.2 3.1v.5h-7v-.5c0-1.2-.4-2.3-1.2-3.1A6.5 6.5 0 0 1 9.5 3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                  <path d="M7 21h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                </svg>
                <span class="badge-name">{{ typeName }}</span>
              </div>
            </div>
            <!-- 绿字描述（四象趣味定标） -->
            <div class="irh-desc">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" />
                <path d="m12 3 2.4 5.2 5.6.6-4.2 3.8 1.2 5.6-5-2.9-5 2.9 1.2-5.6L4 8.8l5.6-.6L12 3Z" stroke="currentColor" stroke-width="1.2" opacity="0.5" />
                <path d="M12 7.5v9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity="0.6" />
              </svg>
              <p><strong>四象趣味定标：</strong>{{ typeDesc }}</p>
            </div>

            <!-- 四维行为倾向刻度（GraduatedBand：档位化游标，无精确数值） -->
            <div class="dims-block">
              <div class="dims-head">
                <span class="st-section-head dims-title">四维行为倾向刻度</span>
                <span class="caption dims-mark">仅档位呈现</span>
              </div>
              <GraduatedBand
                v-for="d in dimRows"
                :key="d.dimension"
                :label="d.sub ? `${d.name}（${d.sub}）` : d.name"
                :bands="BAND_NAMES"
                :level-labels="BAND_LEVEL_LABELS"
                :value="d.value"
                :partial="d.partial"
              />
            </div>

            <!-- ▎核心养育洞察集 -->
            <div class="insight-block">
              <div class="insight-head">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="4" y="4" width="16" height="16" rx="2.5" stroke="currentColor" stroke-width="1.6" />
                  <path d="m8 12.2 2.4 2.4 5-5.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <span>核心养育洞察集</span>
              </div>
              <div class="quote-list">
                <p class="quote"><strong>【类型解读】</strong>{{ typeDesc }}</p>
                <p class="quote"><strong>【适配养育方式】</strong>{{ adviceText }}</p>
                <p class="quote"><strong>【沟通技巧】</strong>{{ talkText }}</p>
              </div>
            </div>

            <!-- 波动提示与观察建议黄条 -->
            <div v-if="waveTriggered" class="wave-bar">
              <div class="wave-title">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" />
                  <path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                </svg>
                <span>波动提示与观察建议</span>
              </div>
              <p>
                <strong>"气质不是宿命判定，而是天生风格的初始度量。"</strong>{{ nonFatalismText }}
              </p>
            </div>

            <!-- 法定医学与免责声明（一） -->
            <div class="legal-card">
              <div class="legal-head">
                <span class="legal-title">
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M5 4h11l3 3v13H5V4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                    <path d="M9 12h6M9 15.5h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                  </svg>
                  法定医学与免责声明（一）
                </span>
                <span class="legal-mark">标准规约</span>
              </div>
              <p class="legal-body">
                本报告依据家长主观问卷观测记录进行算法分析，测量结果反映特定观察周期内的行为倾向，<strong>严禁作为儿科临床诊断、神经发育障碍、孤独症谱系或心理病理学判定的依据</strong>。若儿童伴随严重的社会退缩或言语停滞，请务必前往三甲医院发育行为儿科或心理科就诊咨询。
              </p>
            </div>

            <!-- 法定版权与技术免责说明（二） + 备案占位 + 二维码占位 -->
            <div class="legal-card">
              <div class="legal-head">
                <span class="legal-title">
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                  </svg>
                  法定版权与技术免责说明（二）
                </span>
                <span class="legal-mark">规约条目 2.4</span>
              </div>
              <p class="legal-body">
                报告中所含图表与文字生成均经过双向脱敏处理，受《个人信息保护法》与儿童隐私指引严格约束。评测结果不可用于民事鉴定、入园入学能力筛选及一切商业征信评估。
              </p>
              <!-- 元数据栏：AI 标识 + 备案占位 + 编号 + 二维码占位 -->
              <div class="legal-meta">
                <div class="meta-lines">
                  <span class="ai-line"><i class="ai-dot" />AI 生成内容模型算法标识</span>
                  <span class="meta-line">产品运营主体备案：占位文案（备案信息未定）</span>
                  <span class="meta-line">ICP 备案号：占位文案（备案号未定）</span>
                  <span class="meta-line">防伪溯源编号：{{ traceNo }}</span>
                </div>
                <!-- 二维码占位方块 -->
                <div class="qr-box">
                  <div class="qr-grid">
                    <i v-for="n in 16" :key="n" :class="{ dark: QR_PATTERN[n - 1] === 1 }" />
                  </div>
                  <span class="qr-label">扫码验真</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部标尺收尾 -->
          <div class="ruler-band is-bottom" />
        </section>

        <!-- ===== 隐私安全提示卡 ===== -->
        <section class="st-card privacy-card">
          <div class="privacy-head">
            <div class="ph-left">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
                <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span class="ph-title">隐私安全提示</span>
              <span class="ph-count">（7 项）</span>
            </div>
            <span class="ph-chip">安全保护生效中</span>
          </div>
          <p class="privacy-text">
            请勿包含可揭示孩子可识别信息的截图、姓名、证件及就诊卡号；本长图已自动抹除真实姓名与定位信息。
          </p>
          <p class="privacy-scene caption">常见曝光：沟通交流中拍到的正脸与姓名标识、证件及就诊卡号。</p>
          <!-- 控制行：脸数计数 + 打码开关 -->
          <div class="privacy-ctrl">
            <span class="face-count">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="10" r="3.5" stroke="currentColor" stroke-width="1.6" />
                <path d="M6 19c.8-2.6 3.2-4 6-4s5.2 1.4 6 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
              </svg>
              已识别可识别面部：{{ faceCount }} 处
            </span>
            <label class="mask-switch">
              <span>打码保护</span>
              <el-switch v-model="maskOn" />
            </label>
          </div>
        </section>

        <!-- ===== 底部操作区 ===== -->
        <section class="action-area">
          <el-button type="primary" size="large" class="save-btn" @click="save">
            <svg class="btn-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 4v11m0 0 4.5-4.5M12 15l-4.5-4.5M5 19h14" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            保存报告
          </el-button>
          <div class="dual-btns">
            <button class="dual-btn" @click="share">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m22 3-11 11M22 3 15 21l-4-9-9-4 20-5Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              分享好友
            </button>
            <button class="dual-btn" @click="copyLink">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.2 1.2M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.2-1.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              复制链接
            </button>
          </div>
        </section>

        <!-- 底部合规说明：AI 免责 + 免责占比/次数 -->
        <footer class="img-foot">
          <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />
          <p v-if="imageMeta" class="ratio-note">
            本长图免责面积占比 {{ ratioPct }}%（≥15%），免责声明出现 {{ imageMeta.disclaimer_count }} 次（≥2）
          </p>
        </footer>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReportImage } from '@/api/client'
import { useUserStore } from '@/stores/user'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'
import GraduatedBand from '@/components/GraduatedBand.vue'

const route = useRoute()
const user = useUserStore()

/** 报告 uid（长图所属测评报告） */
const uid = computed(() => route.params.uid as string)

/** 加载态 */
const loading = ref(true)
/** 失败态 */
const loadFailed = ref(false)

/** 长图渲染数据（sections 仅免费区块 + 免责合规元数据） */
const imageMeta = ref<any>(null)

/** 打码保护开关（默认开启） */
const maskOn = ref(true)
/** 已识别可识别面部数（本地占位计数，真实识别由端侧能力提供） */
const faceCount = ref(0)

/** 二维码占位 4x4 图案（固定演示图案，非真实码） */
const QR_PATTERN = [1, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1]

/** 免责占比百分比（0.18 → 18） */
const ratioPct = computed(() =>
  imageMeta.value ? Math.round(Number(imageMeta.value.disclaimer_ratio || 0) * 100) : 0
)

/** 免责溯源编号（由报告 uid 派生的展示占位） */
const traceNo = computed(() => {
  const raw = String(imageMeta.value?.report_uid || uid.value || '').replace(/-/g, '')
  return raw ? `QS-${raw.slice(0, 4).toUpperCase()}-${raw.slice(4, 9).toUpperCase()}-TK` : 'QS-0000-00000-TK'
})

/* ===== SIM-20：免费态长图水印 ===== */
/** 是否渲染水印：非会员（前端已知会员态）展示，会员维持无水印 */
const showWatermark = computed(() => !user.isMember)

/** 水印文案：用户 uid 脱敏前缀 + 页面加载时间戳（到分钟） */
const watermarkText = computed(() => {
  const uidRaw = String(user.userUid || '').replace(/-/g, '')
  const masked = uidRaw ? `${uidRaw.slice(0, 4)}****` : '匿名'
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `小光景免费版 ${masked} ${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

/** 平铺水印瓦片（3 列 × 10 行重复填充，旋转由样式层控制） */
const watermarkTiles = computed<string[]>(() =>
  Array.from({ length: 30 }, () => watermarkText.value)
)

/** sections 按 key 索引（免费区块 map） */
const sectionMap = computed<Record<string, any>>(() => {
  const m: Record<string, any> = {}
  for (const s of imageMeta.value?.sections || []) {
    if (s?.key) m[s.key] = s
  }
  return m
})

/** 类型代码（type_conclusion） */
const typeCode = computed(() => sectionMap.value.type_conclusion?.content?.type_code || '')

/** 类型代码 → 对外类型名 */
const TYPE_NAMES: Record<string, string> = {
  easy: '随和型',
  active: '活跃型',
  sensitive: '敏感型',
  slow_warm: '慢热型'
}

/** 类型名（report_header.type_name 优先） */
const typeName = computed(
  () => sectionMap.value.report_header?.content?.type_name || TYPE_NAMES[typeCode.value] || '气质'
)

/** 测评孩子昵称（报告占位"宝宝A"） */
const nickname = computed(() => sectionMap.value.report_header?.content?.child_nickname || '宝宝A')

/** 类型描述（绿字描述/类型解读复用） */
const typeDesc = computed(
  () => sectionMap.value.type_conclusion?.content?.type_desc || '了解孩子近期的行为倾向，仅供养育参考。'
)

/** 维度代码 → 名称与副注 */
const DIM_META: Record<string, { name: string; sub: string }> = {
  ACT: { name: '活动水平', sub: '体能与节律动能' },
  APP: { name: '趋近-退缩', sub: '初遇生疏刺激' },
  ADP: { name: '适应性', sub: '环境变迁融入周期' },
  EMO: { name: '情绪强度', sub: '反应外显幅度' }
}

/** 档位刻度（低→高三档，无精确数值） */
const BAND_NAMES = ['低', '中', '高']
/** 档位展示名（游标读数） */
const BAND_LEVEL_LABELS = ['低倾向', '中等', '高倾向']
/** 档位 → 轨道归一位置（区域中心：1/6、1/2、5/6） */
const BAND_POS: Record<string, number> = { low: 1 / 6, middle: 1 / 2, high: 5 / 6 }

/** 四维刻度行渲染结构（GraduatedBand 入参） */
const dimRows = computed(() => {
  const bands: any[] = sectionMap.value.dimension_bands?.content?.bands || []
  return bands.map((b) => {
    const meta = DIM_META[b.dimension] || { name: b.dimension, sub: '' }
    return {
      dimension: b.dimension,
      name: meta.name,
      sub: meta.sub,
      partial: !!b.partial,
      value: BAND_POS[b.band] ?? 0.5
    }
  })
})

/** 适配养育方式（basic_advice.items 拼接） */
const adviceText = computed(() => {
  const items: string[] = sectionMap.value.basic_advice?.content?.items || []
  return items.length ? items.join('；') : '结合孩子的节奏安排日常活动，保持稳定的陪伴与回应。'
})

/** 沟通技巧（type_code 固定映射，与报告页一致） */
const talkText = computed(() => {
  const talks: Record<string, string> = {
    easy: '保持稳定的回应节奏即可；孩子表达需求时先确认再行动，例如「你想要这个对吗？我们一起来。」',
    active: '把指令变成游戏，例如「我们先跑一圈，再来搭积木好不好？」先共动、再引导。',
    sensitive: '避免"别害羞"等评价性词汇；代以"妈妈知道你在先看一看，随时可以告诉我"。',
    slow_warm: '避免"别害羞"等评价性词汇；代以"妈妈知道你在先看一看，随时可以告诉我"。'
  }
  return talks[typeCode.value] || talks.easy
})

/** 波动提示是否触发 */
const waveTriggered = computed(() => !!sectionMap.value.wave_notice?.content?.triggered)

/** 非宿命论补充文案 */
const nonFatalismText = computed(
  () => sectionMap.value.non_fatalism?.content?.text || '随着环境支持与语言发展，孩子的行为策略将产生弹性拓展与自我调节。'
)

/**
 * 拉取长图渲染数据
 * @throws 接口失败置失败态
 */
async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    imageMeta.value = await getReportImage(uid.value)
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

/**
 * 保存报告：演示环境提示长按保存（不实际生成图片文件）
 */
function save(): void {
  ElMessage.success('长图已就绪：请长按上方预览区或使用系统截图保存')
}

/**
 * 分享好友：复制长图链接
 * @throws 剪贴板不可用时提示
 */
async function share(): Promise<void> {
  const url = sectionMap.value.share_entry?.content?.share_url
    || `/app/assessment/report/${uid.value}/image`
  try {
    await navigator.clipboard.writeText(location.origin + url)
    ElMessage.success('长图链接已复制，可粘贴给好友')
  } catch {
    ElMessage.info('复制失败，请手动复制地址栏链接')
  }
}

/**
 * 复制链接（与分享同源：share_entry 链接）
 * @throws 剪贴板不可用时提示
 */
async function copyLink(): Promise<void> {
  await share()
}

onMounted(load)
</script>

<style lang="scss" scoped>
/* ===== 页面骨架 ===== */
.image-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

/* 页头 */
.img-head {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  height: 48px;
  padding: 0 var(--sp-4);
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);

  .head-back {
    width: 32px;
    height: 32px;
    margin-left: -8px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: var(--ink-1);
    border-radius: 50%;
    cursor: pointer;

    svg {
      width: 22px;
      height: 22px;
    }
  }

  .head-title {
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
  }
}

/* 顶部状态指示条 */
.status-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px var(--sp-4);
  background: var(--surface-2);
  border-bottom: 1px solid var(--line);
}

.strip-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);

  svg {
    width: 14px;
    height: 14px;
    color: var(--accent);
  }
}

.strip-right {
  color: var(--ink-3);
}

/* 主体滚动区 */
.img-main {
  flex: 1;
  padding: var(--sp-3) 14px var(--sp-8);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

/* 失败重试卡 */
.retry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  color: var(--ink-2);
}

/* ===== 长图画布卡 ===== */
.canvas-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-face);
  box-shadow: var(--shadow-e2);
  overflow: hidden;
}

/* SIM-20：免费态平铺水印层（绝对定位铺满画布，不拦截交互、不遮蔽阅读） */
.wm-layer {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  align-content: space-around;
  justify-items: center;
  gap: 26px 8px;
  padding: 18px 6px;
  pointer-events: none;
  overflow: hidden;
  transform: rotate(-18deg) scale(1.35);
  opacity: 0.07;
}

.wm-item {
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-1);
  white-space: nowrap;
  user-select: none;
}

/* 标尺装饰带（顶部/底部）：--art-line 刻度，两主题均 ≥3:1 */
.ruler-band {
  height: 8px;
  background: var(--surface-2);

  /* 细密刻度底纹 */
  &.is-top {
    border-bottom: 1px solid var(--line);
    background-image: repeating-linear-gradient(
      to right,
      var(--art-line) 0,
      var(--art-line) 1px,
      transparent 1px,
      transparent 8px
    );
  }

  &.is-bottom {
    border-top: 1px solid var(--line);
    background-image: repeating-linear-gradient(
      to right,
      var(--art-line) 0,
      var(--art-line) 1px,
      transparent 1px,
      transparent 8px
    );
  }
}

.canvas-body {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

/* 报告头 */
.img-report-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--line);
}

.irh-chip {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  margin-bottom: 4px;
}

.irh-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.4;
}

/* 类型徽章块 */
.irh-badge {
  flex: none;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-face);
  background: var(--surface-2);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  svg {
    width: 18px;
    height: 18px;
  }

  .badge-name {
    font-size: 9px;
    color: var(--ink-2);
    line-height: 1;
    margin-top: 2px;
  }
}

/* 绿字描述（四象趣味定标） */
.irh-desc {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);

  svg {
    flex: none;
    width: 18px;
    height: 18px;
    margin-top: 2px;
    color: var(--accent);
  }

  p {
    font-size: var(--fs-caption);
    line-height: 1.7;
    color: var(--ink-2);

    strong {
      color: var(--ink-1);
      font-weight: 600;
    }
  }
}

/* ===== 四维行为倾向刻度（GraduatedBand 承担刻度渲染） ===== */
.dims-block {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.dims-head {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .dims-mark {
    color: var(--ink-3);
  }
}

/* ===== 核心养育洞察集 ===== */
.insight-block {
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.insight-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line);
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);

  svg {
    width: 16px;
    height: 16px;
    color: var(--accent);
  }
}

.quote-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.quote {
  font-size: var(--fs-caption);
  line-height: 1.7;
  color: var(--ink-2);

  strong {
    color: var(--ink-1);
    font-weight: 600;
  }
}

/* ===== 波动提示黄条 ===== */
.wave-bar {
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 4px;

  .wave-title {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: var(--fs-caption);
    font-weight: 600;
    color: var(--warn);

    svg {
      width: 15px;
      height: 15px;
    }
  }

  p {
    font-size: var(--fs-caption);
    line-height: 1.7;
    color: var(--ink-2);

    strong {
      color: var(--warn);
    }
  }
}

/* ===== 法定免责卡（一）（二） ===== */
.legal-card {
  background: var(--sc-high);
  border: 2px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
}

.legal-title {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--danger);

  svg {
    width: 16px;
    height: 16px;
  }
}

.legal-mark {
  font-size: 11px;
  color: var(--ink-3);
}

.legal-body {
  font-size: 11px;
  line-height: 1.8;
  color: var(--ink-2);

  strong {
    color: var(--ink-1);
  }
}

/* 元数据栏：AI 标识 + 备案占位 + 编号 + 二维码 */
.legal-meta {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--sp-3);
  padding-top: var(--sp-2);
  border-top: 1px solid var(--line);
}

.meta-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.ai-line {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  padding: 1px 6px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 4px;
  font-size: 10px;
  color: var(--ink-2);

  .ai-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
  }
}

.meta-line {
  font-size: 10px;
  color: var(--ink-3);
}

/* 二维码占位方块 */
.qr-box {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.qr-grid {
  width: 44px;
  height: 44px;
  padding: 3px;
  background: var(--surface-2);
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: repeat(4, 1fr);
  gap: 2px;

  i {
    background: var(--surface);
    border-radius: 1px;

    /* 深色格（模拟码点） */
    &.dark {
      background: var(--ink-1);
    }
  }
}

.qr-label {
  font-size: 9px;
  color: var(--ink-3);
}

/* ===== 隐私安全提示卡 ===== */
.privacy-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-4);
}

.privacy-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ph-left {
  display: flex;
  align-items: center;
  gap: 6px;

  svg {
    width: 18px;
    height: 18px;
    color: var(--accent);
  }

  .ph-title {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }

  .ph-count {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }
}

.ph-chip {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
}

.privacy-text {
  padding: var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: var(--fs-caption);
  line-height: 1.7;
  color: var(--ink-2);
}

.privacy-scene {
  color: var(--ink-3);
}

/* 控制行：脸数计数 + 打码开关 */
.privacy-ctrl {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding-top: var(--sp-1, 4px);
}

.face-count {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-caption);
  color: var(--ink-2);

  svg {
    width: 15px;
    height: 15px;
    color: var(--ink-3);
  }
}

.mask-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-caption);
  font-weight: 500;
  color: var(--ink-1);
}

/* ===== 底部操作区 ===== */
.action-area {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.save-btn {
  width: 100%;
  height: 44px;
  font-size: var(--fs-sub);
}

.btn-ico {
  width: 20px;
  height: 20px;
  margin-right: 4px;
}

/* 分享好友 / 复制链接 双按钮 */
.dual-btns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}

.dual-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 44px;
  border-radius: var(--radius-face);
  border: 1px solid var(--line-strong);
  background: var(--surface);
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-1);
  cursor: pointer;
  transition: background 0.2s ease, transform 0.15s ease;

  svg {
    width: 18px;
    height: 18px;
    color: var(--accent);
  }

  &:active {
    transform: scale(0.98);
    background: var(--surface-2);
  }
}

/* 底部合规说明 */
.img-foot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-bottom: var(--sp-2);
}

.ratio-note {
  font-size: 10px;
  color: var(--outline);
}
</style>
