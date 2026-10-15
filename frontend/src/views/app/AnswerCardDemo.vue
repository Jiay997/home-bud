<!--
  AnswerCardDemo SC-11 回答卡元素全貌（静态规范页，演示数据固定）
  按 Stitch 稿重构：安全提示置顶卡 + 深度养育方案解锁卡（LockedBlock）+
  ▎建议要点（✓ 勾选行）/ ▎适用前提（绿块）/ ▎不建议做法（红块）/
  ▎观察指标（st-meter + 预期档）/ 何时咨询专业人士卡 / 了解更多 /
  冲突提示黄条（ConflictNote）/ 儿童宠物互动安全卡（仅安全建议 +
  基础防护须知 + 识别行动指南）/ 免责声明 / 底部操作栏 / 生成信息行。
  文案均已合规化（不使用稿中占位乱码），仅静态演示，不发请求。
-->
<template>
  <div class="page demo-page">
    <PageHeader title="回答卡元素全貌" sub="家庭综合回答 · 视觉规范演示（合成数据）" />

    <!-- 1 安全提示：绿底置顶卡 + 教学指导行 -->
    <SafetyBanner
      title="安全提示（置顶）"
      text="孩子与宠物共处时需全程成人陪护；本卡为回答卡各元素视觉规范，内容为演示数据，不构成真实建议。"
    />
    <p class="teach-line">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
      </svg>
      教学指导：以下小节按真实回答卡的顺序与样式呈现，供设计与验收对照。
    </p>

    <!-- 2-8 回答主卡：一张卡内多小节 -->
    <section class="demo-card">
      <!-- 2 深度养育方案解锁卡（LockedBlock） -->
      <LockedBlock
        title="深度养育方案"
        summary="解锁后将生成 1-3 岁适配的渐进喂养与睡眠引导计划：分阶段安排、每日清单与回访要点…"
        @unlock="$router.push('/app/member')"
      >
        <template #action>
          <button class="unlock-line touch-target" type="button" @click="$router.push('/app/member')">解锁会员</button>
        </template>
      </LockedBlock>

      <!-- 3 建议要点：4 条 ✓ 勾选行 -->
      <div class="sec">
        <h3 class="st-section-head">建议要点</h3>
        <p v-for="(p, i) in POINTS" :key="i" class="check-line">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" />
            <path d="m8 12.5 2.8 2.8L16.5 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>{{ p }}</span>
        </p>
      </div>

      <!-- 4 适用前提：绿块 -->
      <div class="sec">
        <h3 class="st-section-head">适用前提</h3>
        <div class="premise-block">6-12 月龄 · 已加辅食 · 无发热</div>
      </div>

      <!-- 5 不建议做法：红块 -->
      <div class="sec">
        <h3 class="st-section-head warn-head">不建议做法</h3>
        <div class="forbid-block">
          切忌频繁强行喂奶止哭，或使用摇晃等剧烈方式哄睡，以免形成不良睡眠依赖。
        </div>
      </div>

      <!-- 6 观察指标：st-meter 进度 + 预期档 -->
      <div class="sec">
        <div class="obs-row">
          <h3 class="st-section-head">观察指标</h3>
          <span class="obs-range caption">建议连续观察 3 晚</span>
        </div>
        <div class="st-meter obs-meter">
          <div class="st-meter__fill" style="width: 60%" />
        </div>
        <p class="expect-line">
          预期档：入睡时长趋稳，夜醒次数逐步减少、间隔拉长。
        </p>
      </div>

      <!-- 7 何时咨询专业人士卡 -->
      <div class="consult-card">
        <div class="cc-head">
          <svg class="cc-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4.5 13.5h15v5a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2v-5Zm3-6.5h9v6.5h-9V7Zm3.5 0V4.6A1.6 1.6 0 0 1 12.6 3h1.3" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          <strong>何时咨询专业人士</strong>
        </div>
        <p class="cc-body">如夜醒伴随发热、呼吸急促、进食明显减少或体重不增，请及时线下就医评估。</p>
        <button class="cc-btn" type="button" @click="demoTip">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 4h4l1.5 4.5L8 10a12 12 0 0 0 6 6l1.5-2.5L20 15v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
          </svg>
          咨询入口（演示占位）
        </button>
      </div>

      <!-- 8 了解更多行 -->
      <button class="more-line" type="button" @click="demoTip">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
        </svg>
        了解更多：睡眠引导专题与相关知识条目
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </section>

    <!-- 9 冲突提示黄条 -->
    <ConflictNote text="观点存在差异 · 建议多方参考：「渐进回应」与「立即安抚」两种建议结论不完全一致，请结合孩子状态甄别。" />

    <!-- 10 儿童宠物互动安全卡 -->
    <section class="interact-card">
      <header class="ic-head">
        <strong>儿童-宠物互动安全</strong>
        <span class="st-tag st-tag--green st-tag--plain">仅安全建议</span>
      </header>

      <h4 class="st-section-head">基础防护须知</h4>
      <p v-for="(g, i) in GUARDS" :key="i" class="guard-line">
        <i class="g-dot" aria-hidden="true" />
        <span>{{ g }}</span>
      </p>

      <!-- 识别行动指南：紧急情况红字 -->
      <div class="act-guide">
        <h4 class="ag-title">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          识别行动指南
        </h4>
        <p class="ag-line"><strong>紧急情况：</strong>被抓咬出血时，立即用流动清水冲洗伤口并就医，不可延误。</p>
        <p class="ag-line normal">猫哈气、低吼、甩尾幅度变大是明确的「停止接触」信号，应先隔离再安抚。</p>
        <button class="ag-feedback" type="button" @click="demoTip">该指引有帮助吗？反馈</button>
      </div>
    </section>

    <!-- 11 免责声明 -->
    <AiDisclaimer ai-label="内容由 AI 生成" disclaimer="仅供参考，不能替代专业医疗、心理或法律意见" />

    <!-- 12 底部操作栏 + 生成信息行 -->
    <div class="action-bar">
      <button class="ab-item" type="button" @click="demoTip">
        <svg class="ab-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5v6a2.5 2.5 0 0 1-2.5 2.5H12l-4.5 4v-4h-1A2.5 2.5 0 0 1 4 13.5v-6Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>咨询
      </button>
      <button class="ab-item" type="button" @click="demoTip">
        <svg class="ab-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.5 4h11a1 1 0 0 1 1 1v15.5l-6.5-4-6.5 4V5a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>保存
      </button>
      <button class="ab-item" type="button" @click="$router.push('/app/me/feedback')">
        <svg class="ab-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3.8 3.4 19.2A1.6 1.6 0 0 0 4.8 21.6h14.4a1.6 1.6 0 0 0 1.4-2.4L12 3.8ZM12 10v4m0 3v.3" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>反馈
      </button>
      <button class="ab-item" type="button" @click="$router.push('/app/me/feedback')">
        <svg class="ab-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 21V4m0 0h11l-2 3.5L17 11H6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>举报
      </button>
    </div>
    <p class="gen-line caption">生成信息：多 Agent 并行生成 · 已通过内容安全检查 · 演示数据</p>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SafetyBanner from '@/components/SafetyBanner.vue'
import ConflictNote from '@/components/ConflictNote.vue'
import LockedBlock from '@/components/LockedBlock.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'
import PageHeader from '@/components/PageHeader.vue'

const router = useRouter()

/** 建议要点（4 条演示） */
const POINTS = [
  '固定睡前程序：洗澡-抚触-调暗灯光-轻声陪伴',
  '白天小睡保持规律，避免傍晚补觉过长',
  '夜醒后先等待 3-5 分钟，观察是否自行接觉',
  '逐步减少奶睡与抱睡依赖，改为床上轻拍安抚'
]

/** 基础防护须知（4 条演示） */
const GUARDS = [
  '婴儿与宠物不单独共处一室',
  '不让孩子追逐、抓拽宠物尾巴与耳朵',
  '接触宠物或其用品后及时洗手',
  '宠物疫苗与驱虫按计划接种'
]

/**
 * 静态演示占位交互（咨询/保存等轻提示）
 */
function demoTip(): void {
  ElMessage.info('演示数据，仅供视觉规范参考')
}
</script>

<style lang="scss" scoped>
.demo-page {
  padding-bottom: 140px;
}

/* 教学指导行 */
.teach-line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.6;

  svg { width: 14px; height: 14px; flex: none; margin-top: 3px; color: var(--accent); }
}

/* 回答主卡 */
.demo-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  box-shadow: var(--shadow-e1);
  margin-bottom: var(--sp-4);
}

/* 小节 */
.sec {
  margin-top: var(--sp-6);

  .st-section-head {
    margin-bottom: var(--sp-3);
  }
}

/* 不建议做法：红头 */
.warn-head {
  color: var(--danger);

  &::before { background: var(--danger); }
}

/* ✓ 勾选行 */
.check-line {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  font-size: var(--fs-sub);
  line-height: 1.7;
  color: var(--ink-2);

  svg {
    width: 17px;
    height: 17px;
    flex: none;
    margin-top: 3px;
    color: var(--accent);
  }
}

/* 适用前提：绿块 */
.premise-block {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  font-size: var(--fs-sub);
  font-weight: 600;
}

/* 不建议做法：红块 */
.forbid-block {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--danger-soft);
  border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent);
  color: var(--ink-1);
  font-size: var(--fs-sub);
  line-height: 1.7;
}

/* 观察指标 */
.obs-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}

.obs-meter {
  margin-bottom: var(--sp-2);
}

.expect-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.7;

  .arr { flex: none; width: 12px; height: 12px; }
}

/* 何时咨询专业人士卡 */
.consult-card {
  margin-top: var(--sp-6);
  padding: var(--sp-4);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);

  .cc-head {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-sub);
    color: var(--ink-1);

    .cc-ico { width: 17px; height: 17px; color: var(--ink-2); flex: none; }
  }

  .cc-body {
    margin-top: var(--sp-2);
    font-size: var(--fs-caption);
    color: var(--ink-2);
    line-height: 1.7;
  }

  .cc-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: var(--sp-3);
    padding: 7px 14px;
    border: 1px solid var(--accent);
    border-radius: var(--radius-ctl);
    background: var(--surface);
    color: var(--accent);
    font-size: var(--fs-caption);
    font-weight: 600;
    cursor: pointer;

    svg { width: 14px; height: 14px; }

    &:active { background: var(--accent-soft); }
  }
}

/* 了解更多行 */
.more-line {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  margin-top: var(--sp-5, 18px);
  padding: var(--sp-3) 0 var(--sp-2);
  border: none;
  border-top: 1px solid var(--line);
  background: none;
  color: var(--accent);
  font-size: var(--fs-caption);
  cursor: pointer;
  text-align: left;

  svg { width: 15px; height: 15px; flex: none; }

  .chev { margin-left: auto; }
}

/* 互动安全卡 */
.interact-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  box-shadow: var(--shadow-e1);
  margin-bottom: var(--sp-4);

  .ic-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--sp-3);
    padding-bottom: var(--sp-3);
    border-bottom: 1px solid var(--line);
    margin-bottom: var(--sp-3);

    strong {
      font-size: var(--fs-sub);
      color: var(--ink-1);
    }
  }

  .st-section-head {
    margin-bottom: var(--sp-2);
  }
}

/* 防护须知行 */
.guard-line {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: 4px 0;
  font-size: var(--fs-caption);
  line-height: 1.7;
  color: var(--ink-2);

  .g-dot {
    flex: none;
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
    margin-top: 8px;
  }
}

/* 识别行动指南 */
.act-guide {
  margin-top: var(--sp-4);
  padding: var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--danger-soft);
  border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent);

  .ag-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    font-weight: 700;
    color: var(--danger);

    svg { width: 15px; height: 15px; }
  }

  .ag-line {
    margin-top: var(--sp-2);
    font-size: var(--fs-caption);
    line-height: 1.7;
    color: var(--danger);
    font-weight: 600;

    &.normal {
      color: var(--ink-2);
      font-weight: 400;
    }
  }

  .ag-feedback {
    margin-top: var(--sp-3);
    border: none;
    background: none;
    color: var(--ink-3);
    font-size: var(--fs-caption);
    text-decoration: underline;
    cursor: pointer;
  }
}

/* 底部操作栏 */
.action-bar {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 430px;
  display: flex;
  background: var(--surface);
  border-top: 1px solid var(--line);
  padding: var(--sp-2) var(--sp-4) calc(var(--sp-2) + env(safe-area-inset-bottom));
  z-index: 90;
}

.ab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  border: none;
  background: none;
  color: var(--ink-2);
  font-size: var(--fs-caption);
  padding: var(--sp-1, 4px) 0;
  cursor: pointer;

  .ab-ico { width: 18px; height: 18px; flex: none; }

  &:active { color: var(--accent); }
}

/* 生成信息行 */
.gen-line {
  text-align: center;
  padding: var(--sp-2) 0;
  color: var(--ink-3);
}
</style>
