# -*- coding: utf-8 -*-
"""种子数据脚本：初始化业务运行所需的基础数据（幂等）。

覆盖 spec「首次初始化」Scenario：
- 后台账号 5 个（admin/operator/support/expert_child/expert_pet）
- 词库条目（高危/敏感 + 药名剂量正则配置）
- 危机渠道占位（除 110 外号码留空，不编造号码）
- 知识库样例条目（育儿/宠物各 ≥6 条 published）
- 气质测评 16 题（4 维×4 题，04/08/12/16 反向，双题干变体，合成演示数据）
- 商品（会员月卡 19.9 元 = 19_900_000 micro，platform_scope 排除 ios）
- 文案 ID（DISCLAIMER_V1 等 11 个）
- 系统开关（5 个入口紧急下线）

用法：python scripts/seed_data.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.crypto import encrypt_field, sha256_hex  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    AdminUser,
    AppUser,
    ConfigVersion,
    ConsentRecord,
    CrisisChannel,
    KbEntry,
    LexiconTerm,
    Product,
    RiskRuleConfig,
    TextVersion,
)

NOW = datetime.now(timezone.utc)

# ---------- 文案 ID 清单（UI 文档 §8：11 个文案 ID） ----------
TEXTS = [
    ("DISCLAIMER_V1", "本内容由 AI 生成，仅作养育参考，不构成医疗建议，不能替代医生、心理咨询师、学校教师或执业兽医的判断。如有疑问请咨询专业人士。"),
    ("AI_GEN_LABEL_V1", "AI 生成内容"),
    ("REFUSAL_AGE_V1", "该问题超出 0-6 岁育儿与猫狗饲养范围，建议咨询相关专业机构。"),
    ("CRISIS_CHANNELS_V1", "如果您或孩子正处于危险中，请立即联系以下渠道获得帮助。"),
    ("QUOTA_RULE_V1", "免费用户每日可用 {limit} 次问答，次日 0 点恢复；会员不受限制。"),
    ("REFUND_NOTICE_V1", "虚拟内容一经解锁，非质量问题不支持退款。购买前请确认。"),
    ("CHILD_CONSENT_V1", "我们将收集儿童的昵称、出生日期、过敏项等信息，仅用于提供分龄养育建议，加密存储、不用于训练模型，您可随时撤回同意。"),
    ("GUARDIAN_DECLARATION_V1", "我确认我是该儿童的监护人，所填写信息真实、必要。"),
    ("RISK_BLOCK_V1", "已停止生成回答。"),
    ("APPEAL_NOTICE_V1", "如认为本次拦截属于误判，可提交申诉，我们将在 24 小时内复核。"),
    ("READONLY_V1", "会员已到期，历史内容转为只读。"),
]

# ---------- 危机渠道占位（号码除 110 外留空：不得编造号码，PRD 红线） ----------
CRISIS_CHANNELS = [
    ("police", "报警求助", "110", ["child_abuse", "child_selfharm"]),
    ("minor_protection", "未成年人保护热线", "", ["child_abuse", "harmful_to_minor"]),
    ("psych_hotline", "心理援助热线", "", ["child_selfharm", "depression"]),
    ("fever_emergency", "儿科急症就诊", "", ["high_fever"]),
    ("pet_emergency", "宠物急症就诊", "", ["pet_poison", "pet_bleeding"]),
    ("rabies_clinic", "犬伤处置门诊/疾控中心", "", ["animal_bite"]),
]

# ---------- 词库种子（高危/敏感；词条密文存储） ----------
LEXICON = [
    # (词, 类型, 策略, 类别码)
    ("虐待儿童", "risk", "block", "child_abuse"),
    ("打孩子打到出血", "risk", "block", "child_abuse"),
    ("自杀", "risk", "block", "child_selfharm"),
    ("自残", "risk", "block", "child_selfharm"),
    ("高烧惊厥", "risk", "block", "high_fever"),
    ("热性惊厥", "risk", "block", "high_fever"),
    ("被狗咬了出血", "risk", "block", "animal_bite"),
    ("被猫抓伤出血", "risk", "block", "animal_bite"),
    ("狂犬病暴露", "risk", "block", "animal_bite"),
    ("宠物中毒", "risk", "block", "pet_poison"),
    ("大出血", "risk", "block", "pet_bleeding"),
    ("严重抑郁", "risk", "block", "depression"),
    ("想死", "risk", "block", "child_selfharm"),
    ("退烧药剂量", "sensitive", "rewrite", "medicine_dosage"),
    ("抗生素用量", "sensitive", "rewrite", "medicine_dosage"),
    ("确诊", "sensitive", "rewrite", "diagnosis"),
    ("治愈", "sensitive", "rewrite", "efficacy"),
    ("包治百病", "sensitive", "rewrite", "efficacy"),
    ("算命", "sensitive", "rewrite", "fortune"),
    ("天生注定", "sensitive", "rewrite", "fortune"),
]

# ---------- 风险规则配置（双阈值 + 模式正则） ----------
RISK_CONFIGS = [
    ("two_level_threshold", {"gray_low": 0.5, "gray_high": 0.8}),
    ("medicine_dosage_pattern", {
        "pattern": r"(布洛芬|对乙酰氨基酚|阿莫西林|头孢|退烧药|抗生素)[^。]{0,10}(剂量|用量|mg|毫升|ml|片)",
        "action": "block_or_rewrite",
    }),
    ("diagnosis_pattern", {
        "pattern": r"(确诊|诊断为)[^。]{0,20}(自闭|多动|抑郁|焦虑)",
        "action": "rewrite",
    }),
    ("efficacy_pattern", {
        "pattern": r"(保证|包治|根治|治愈)[^。]{0,10}(病|症|障碍)",
        "action": "rewrite",
    }),
]

# ---------- 知识库样例条目（育儿/宠物各 6 条 published；内容为演示性科普） ----------
KB_ENTRIES = [
    # 育儿 6 条
    ("kb_child_sleep_01", "child", "育儿", "sleep_training", "睡眠", "1-3y", None, None,
     "1-3 岁幼儿睡眠引导要点",
     "固定睡前程序（洗澡-抚触-讲故事-关灯）有助于建立睡眠联想；就寝时间建议在 20:30-21:30 之间；白天小睡 1-2 次，总时长 1.5-3 小时。夜醒时先观察 1-2 分钟再介入，避免立即抱起形成依赖。",
     "适用于 12-36 月龄、无发热等急性症状的幼儿", [], "support"),
    ("kb_child_sleep_02", "child", "育儿", "sleep_training", "睡眠", "0-6m", None, None,
     "0-6 月婴儿夜醒应对",
     "此阶段夜醒属正常生理现象，胃容量小需要夜间喂养；建议识别饥饿性哭声与不适性哭声；白天光线充足、夜间暗光，帮助建立昼夜节律。",
     "适用于 0-6 月龄健康新生儿；早产儿按矫正月龄", [], "support"),
    ("kb_child_feed_01", "child", "育儿", "feeding", "喂养与辅食", "6-12m", None, None,
     "辅食添加基本原则",
     "满 6 月龄起添加辅食，首选强化铁米粉；每次只引入一种新食物，观察 2-3 天有无过敏；由稀到稠、由少到多循序渐进；1 岁前不建议添加盐、糖与蜂蜜。",
     "适用于满 6 月龄、已排除食物过敏史的婴儿", [], "support"),
    ("kb_child_safety_01", "child", "育儿", "safety_prevention", "安全与意外预防", "1-3y", None, None,
     "家庭环境安全隐患排查",
     "1-3 岁是跌落、误吞高发期：家具边角加装防撞条、抽屉上锁、小物件（纽扣电池、药片）放置于 1.5 米以上；浴室地面防滑；插座加保护盖。",
     "适用于已学会爬行或行走的幼儿家庭", [], "support"),
    ("kb_child_emotion_01", "child", "育儿", "emotion", "情绪与社交", "3-6y", None, None,
     "幼儿情绪 tantrum 应对",
     "3-6 岁幼儿情绪爆发常见于需求未满足：先共情命名情绪（你现在很生气），再设定边界（打人不可以），最后给选择权（先收积木还是先洗手）。",
     "适用于 3-6 岁典型发展幼儿；频繁自伤或伤人请咨询专业人士", [], "support"),
    ("kb_child_health_01", "child", "育儿", "health_monitor", "生长发育", "0-6m", None, None,
     "婴儿体温观察区间",
     "腋温 36.0-37.2 ℃ 为常见区间；3 月龄以下婴儿体温 ≥38.0 ℃ 属于需及时就医的情形；观察精神状态比单次体温更重要。",
     "适用于 0-6 月龄婴儿的日常体温观察", [], "conditional"),
    # 宠物 6 条
    ("kb_pet_cat_feed_01", "pet", "宠物", "cat_feeding", "喂养", None, "adult", "cat",
     "成年猫喂养频次与体重管理",
     "成年猫建议每日定时喂食 2-3 次；以体重 4kg 成猫为例，干粮每日总量约 50-60g（以包装推荐为准）；肥胖猫需在兽医指导下减重；随时提供清洁饮水。",
     "适用于 1-7 岁已绝育或未绝育家养猫", [], "support"),
    ("kb_pet_cat_behavior_01", "pet", "宠物", "cat_behavior", "行为解读", None, "adult", "cat",
     "猫哈气与低吼的含义",
     "哈气、低吼、飞机耳是猫的防御信号，表示感到威胁需要空间；此时不建议强行抚摸或惩罚；应移除刺激源、给予躲避空间，待其放松后再互动。",
     "适用于应激初期；若伴随拒食超过 24 小时请就医", [], "support"),
    ("kb_pet_dog_feed_01", "pet", "宠物", "dog_feeding", "喂养", None, "adult", "dog",
     "成年犬喂养要点",
     "成年犬每日喂食 1-2 次，避免剧烈运动前后 1 小时进食（降低胃扭转风险）；巧克力、葡萄、洋葱、木糖醇对犬有毒，务必收好；饮水常备。",
     "适用于 1-7 岁健康成年犬", [], "support"),
    ("kb_pet_dog_behavior_01", "pet", "宠物", "dog_behavior", "行为解读", None, "adult", "dog",
     "犬护食行为解读",
     "护食是犬的资源保护本能：进食时低吼是警告信号，不应打骂（会加剧焦虑）；可通过（进餐时保持距离-逐步脱敏-交换高价值零食）的方式改善。",
     "适用于无攻击史的家养犬；出现咬人请咨询专业训犬师", [], "conditional"),
    ("kb_pet_child_01", "pet", "宠物", "child_pet_interaction", "儿童与宠物共处", None, "adult", None,
     "幼儿与猫狗同处的安全边界",
     "学步期幼儿与宠物互动必须全程有成人监护；不给宠物喂食、不拉尾巴、不打扰进食与睡觉的宠物；观察宠物回避信号（哈气、甩尾、躲闪）并及时分开；抓咬伤后立即就医处理。",
     "适用于有 0-6 岁儿童且饲养猫/狗的家庭", [], "support"),
    ("kb_pet_health_01", "pet", "宠物", "health_monitor", "健康观察", None, "junior", None,
     "幼宠疫苗接种区间参考",
     "幼猫幼犬首针疫苗通常在 6-8 周龄，之后按兽医安排间隔接种；疫苗未完成前避免外出接触陌生动物；驱虫方案请遵兽医建议。",
     "适用于 <1 岁幼猫幼犬；具体接种计划以执业兽医意见为准", [], "conditional"),
]

# ---------- 气质测评 16 题（合成演示数据！PRD §12.2 冻结结构，题目内容为占位） ----------
# 维度代码：ACT 活动水平 / APP 趋近-退缩 / ADP 适应性 / EMO 情绪强度
ASSESSMENT_QUESTIONS = [
    # (q_no, dimension, is_reverse, stem_0_12m, stem_1_6y)
    (1, "ACT", False, "宝宝醒着时手脚不停挥舞踢动", "孩子跑跳活动时很难安静下来"),
    (2, "ACT", False, "换尿布时宝宝总是扭动不停", "孩子坐着吃饭时也常常扭来扭去"),
    (3, "ACT", False, "宝宝吃奶时动作幅度很大", "孩子走路总是一路小跑"),
    (4, "ACT", True, "宝宝安静地躺着看东西能持续一阵", "孩子能安静坐着听完一个短故事"),
    (5, "APP", False, "陌生人靠近时宝宝会哭闹退缩", "见到陌生大人时孩子会躲到家长身后"),
    (6, "APP", False, "宝宝对新玩具要先观察很久才碰", "孩子进新环境要先抱一会儿才肯下地"),
    (7, "APP", False, "宝宝对新的声音光线表现敏感抗拒", "孩子拒绝尝试没见过的食物"),
    (8, "APP", True, "宝宝能较快接受新的洗澡流程", "孩子到新游乐场能很快开始玩"),
    (9, "ADP", False, "更换喂养方式后宝宝要哭闹好几天", "换新奶粉或新餐具孩子要闹好几天"),
    (10, "ADP", False, "作息打乱后宝宝要很久才恢复规律", "旅行回来后孩子作息要乱好几天"),
    (11, "ADP", False, "换新环境睡觉宝宝明显不安", "搬家或换床后孩子入睡明显变难"),
    (12, "ADP", True, "宝宝对日常小变化没什么反应", "临时改变计划孩子也能接受"),
    (13, "EMO", False, "宝宝饿或困时哭声激烈很难安抚", "需求没被满足时孩子大哭大闹很难哄"),
    (14, "EMO", False, "宝宝高兴时手舞足蹈反应强烈", "孩子开心时又蹦又叫特别兴奋"),
    (15, "EMO", False, "宝宝不适时的哭闹声特别响亮", "孩子生气时会摔东西或大声喊叫"),
    (16, "EMO", True, "宝宝大部分时间情绪平和", "孩子平时情绪比较平稳温和"),
]

# 5 点李克特选项（1=完全不符合 ... 5=完全符合）
LIKERT_OPTIONS = ["完全不符合", "比较不符合", "不确定", "比较符合", "完全符合"]


def seed(db: Session) -> None:
    """执行种子数据写入（幂等：按唯一键判重跳过）。

    Args:
        db: 数据库会话。

    Raises:
        Exception: 种子写入失败时抛出（事务回滚）。
    """
    # 1. 文案版本
    for text_id, content in TEXTS:
        exists = db.query(TextVersion).filter_by(text_id=text_id, version="V1").first()
        if not exists:
            db.add(TextVersion(
                text_id=text_id, version="V1", content=content,
                effective_at=NOW, requires_reconsent=False,
            ))

    # 2. 危机渠道（police 有公开号码 110；其余一律留空占位）
    for code, name, phone, scope in CRISIS_CHANNELS:
        exists = db.query(CrisisChannel).filter_by(channel_code=code).first()
        if not exists:
            db.add(CrisisChannel(
                channel_code=code, channel_name=name,
                phone_number=phone if phone else None,  # 未确认号码留空
                script="请告知对方您的位置与当前情况。",
                category_scope=scope, status="placeholder" if not phone else "active",
                next_review_due_at=NOW + timedelta(days=90),
            ))

    # 3. 词库（term_hash 去重；词条密文存储）
    for term, ltype, strategy, category in LEXICON:
        th = sha256_hex(term)
        exists = db.query(LexiconTerm).filter_by(term_hash=th).first()
        if not exists:
            db.add(LexiconTerm(
                term_hash=th, term_enc=encrypt_field(term),
                lexicon_type=ltype, strategy=strategy, category_code=category,
            ))

    # 4. 风险规则配置
    for key, value in RISK_CONFIGS:
        exists = db.query(RiskRuleConfig).filter_by(config_key=key).first()
        if not exists:
            db.add(RiskRuleConfig(config_key=key, config_value=value, effective_at=NOW))

    # 5. 知识库条目
    for row in KB_ENTRIES:
        (kb_id, kind, domain, topic_key, topic_cat, age_band, pet_stage, species,
         title, content, preconditions, contra, stance) = row
        exists = db.query(KbEntry).filter_by(kb_id=kb_id).first()
        if not exists:
            db.add(KbEntry(
                kb_id=kb_id, kb_kind=kind, domain=domain, topic_key=topic_key,
                topic_category=topic_cat, age_band=age_band, pet_stage=pet_stage,
                species=species, title=title, content=content,
                preconditions=preconditions, contraindications=contra, stance=stance,
                source_type="literature_rewrite", source_ref="demo://seed-data",
                status="published", version=1, published_at=NOW,
                next_review_due_at=NOW + timedelta(days=365),
            ))

    # 6. 气质测评题库（题干存 assessment_pool 类 kb_entry，content 为 JSON 字符串）
    for q_no, dim, reverse, stem_baby, stem_child in ASSESSMENT_QUESTIONS:
        kb_id = f"kb_question_{q_no:02d}"
        exists = db.query(KbEntry).filter_by(kb_id=kb_id).first()
        if not exists:
            import json

            db.add(KbEntry(
                kb_id=kb_id, kb_kind="assessment_pool", domain="育儿",
                topic_key=f"temperament_{dim.lower()}",
                topic_category="气质测评题库",
                title=f"气质测评题 {q_no:02d}（{dim} 维度）",
                content=json.dumps({
                    "q_no": q_no, "dimension": dim, "reverse": reverse,
                    "stem_0_12m": stem_baby, "stem_1_6y": stem_child,
                    "options": LIKERT_OPTIONS,
                }, ensure_ascii=False),
                preconditions="合成演示数据：真实题库未定稿（PRD Q-08），仅用于联调",
                source_type="expert_original", source_ref="demo://question-bank-synthetic",
                status="published", version=1, published_at=NOW,
            ))

    # 7. 商品（19.9 元 = 19_900_000 micro；platform_scope 不含 ios）
    if not db.query(Product).filter_by(product_code="member_monthly").first():
        db.add(Product(
            product_code="member_monthly", name="小光景会员月卡",
            price_micro=19_900_000, duration_days=30,
            platform_scope=["android", "web"],
            entitlements=["深度养育方案", "月度养育计划", "宠物长期规划", "家庭复合方案"],
        ))

    # 8. 系统开关（5 个入口紧急下线，默认全部开）
    entry_switches = [
        ("switch.entry.child", "育儿问答入口"),
        ("switch.entry.pet", "宠物问答入口"),
        ("switch.entry.family", "家庭综合问答入口"),
        ("switch.entry.assessment", "气质测评入口"),
        ("switch.entry.member", "会员购买入口"),
    ]
    for key, name in entry_switches:
        exists = db.query(ConfigVersion).filter_by(
            config_type="switch", config_key=key, version=1
        ).first()
        if not exists:
            db.add(ConfigVersion(
                config_type="switch", config_key=key,
                snapshot={"enabled": True, "name": name},
                effective_at=NOW, reason="seed: init entries",
            ))

    # 9. 演示 C 端用户（openid 为占位密文；uid 必须是合法 UUID）
    demo_uid = "00000000-0000-0000-0000-000000000001"
    if not db.query(AppUser).filter_by(user_uid=demo_uid).first():
        db.add(AppUser(user_uid=demo_uid, wx_openid_enc=encrypt_field("demo-openid")))
        db.flush()
        demo_user = db.query(AppUser).filter_by(user_uid=demo_uid).first()
        # 基础同意默认已签（方便演示直接进入）
        db.add(ConsentRecord(
            user_id=demo_user.id, consent_type="base", consent_version="V1",
            guardian_verified=False,
        ))

    db.commit()

    # 10. 混合检索向量补算（幂等）：为 published 育儿/宠物条目补 hashing embedding
    try:
        from app.services.retriever import Retriever

        patched = Retriever().ensure_embeddings(db)
        print(f"[seed_data] embeddings ensured: {patched} entries")
        # 10.1 Milvus 向量索引重建（best-effort）：主通道就绪时全量重灌
        # jiaban_kb_entries 集合（真实/确定性嵌入经 embed_client 分发）；
        # 不可用静默跳过
        from app.services import rag_index

        if rag_index.available():
            written = rag_index.reindex_all(db)
            print(f"[seed_data] rag index reindexed: {written} entries to Milvus")
        else:
            print("[seed_data] Milvus unavailable, retrieval falls back to hashing path")
    except Exception as exc:  # noqa: BLE001 — 向量补算失败不阻断种子流程
        print(f"[seed_data] ensure_embeddings skipped: {exc}")


def seed_admins(db: Session) -> None:
    """写入后台账号种子（幂等；密码统一 Admin@123456，生产必须修改）。

    Args:
        db: 数据库会话。

    Raises:
        Exception: 写入失败抛出。
    """
    admins = [
        ("admin", "系统超管", "super_admin", None),
        ("operator", "内容运营", "operator", None),
        ("support", "客服专员", "support", None),
        ("expert_child", "育儿专家", "expert_child", "child"),
        ("expert_pet", "宠物专家", "expert_pet", "pet"),
    ]
    for username, display, role, scope in admins:
        if not db.query(AdminUser).filter_by(username=username).first():
            db.add(AdminUser(
                username=username, display_name=display, role=role,
                password_hash=hash_password("Admin@123456"),
                phone_enc=encrypt_field("13800000000"),
                domain_scope=scope,
                temp_auth_expire_at=NOW + timedelta(days=3650),  # 专家授权 10 年（演示）
            ))
    db.commit()
    print("[seed_data] admin accounts ready (password: Admin@123456)")


if __name__ == "__main__":
    session = get_session_factory()()
    try:
        seed_admins(session)
        seed(session)
    finally:
        session.close()
