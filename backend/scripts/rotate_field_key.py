# -*- coding: utf-8 -*-
"""字段密钥轮换脚本：将全库密文字段重加密为当前版本密钥（spec D4）。

轮换操作步骤（先改 .env 再跑本脚本）：
1. 把旧 FIELD_ENC_KEY 移入 FIELD_ENC_KEYS_OLD 逗号分隔列表（保持版本顺序）
2. FIELD_ENC_KEY 写入新密钥
3. 运行本脚本：逐表逐列读取 → reencrypt → 写回（幂等，可重复执行）

覆盖表/列（全部 *_enc 密文列）：
app_user.wx_openid_enc / phone_enc / wx_session_key_enc、
child_profile.nickname_enc / birth_date_enc / allergy_enc、
feedback.content_enc、lexicon_term.term_enc、
qa_session.question_text_enc、risk_appeal.appeal_note_enc、
admin_user.phone_enc、consent_record（无密文列，跳过）。

Provider 兼容（finalize Task 3.3）：本脚本经 app.core.crypto 模块级
encrypt/decrypt/reencrypt 调用（内部按 CRYPTO_PROVIDER 分发 + 跨格式路由），
local / kms 两种通道配置下均可直接运行——kms 配置下解密侧自动兼容既有
v{N}: 本地密文、加密侧产出 kms1: 信封格式，切换配置后跑本脚本即完成
渐进迁移；无需修改本脚本。

用法：python scripts/rotate_field_key.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_  # noqa: E402

from app.core.crypto import decrypt_field, encrypt_field  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    AdminUser, AppUser, ChildProfile, Feedback, LexiconTerm,
    PetProfile, QaSession, RiskAppeal,
)


def rotate_all() -> None:
    """遍历全部密文列，将非当前版本密文重加密写回。

    判定"非当前版本"：密文前缀版本号 != 当前版本（或旧格式无前缀）。

    Raises:
        Exception: 任一行重加密失败（如密钥缺失）时中断并提示。
    """
    db = get_session_factory()()
    total = 0
    try:
        # app_user：openid/unionid/phone/session_key
        for u in db.query(AppUser).all():
            changed = False
            for col in ("wx_openid_enc", "wx_unionid_enc", "phone_enc", "wx_session_key_enc"):
                val = getattr(u, col)
                if val:
                    new = encrypt_field(decrypt_field(val))
                    if new != val:
                        setattr(u, col, new)
                        changed = True
            total += int(changed)

        # child_profile：昵称/出生日期/过敏项
        for c in db.query(ChildProfile).all():
            changed = False
            for col in ("nickname_enc", "birth_date_enc", "allergy_enc"):
                val = getattr(c, col)
                if val:
                    new = encrypt_field(decrypt_field(val))
                    if new != val:
                        setattr(c, col, new)
                        changed = True
            total += int(changed)

        # feedback 正文
        for fb in db.query(Feedback).all():
            new = encrypt_field(decrypt_field(fb.content_enc))
            if new != fb.content_enc:
                fb.content_enc = new
                total += 1

        # lexicon 词条
        for t in db.query(LexiconTerm).all():
            new = encrypt_field(decrypt_field(t.term_enc))
            if new != t.term_enc:
                t.term_enc = new
                total += 1

        # qa 问题原文
        for s in db.query(QaSession).all():
            new = encrypt_field(decrypt_field(s.question_text_enc))
            if new != s.question_text_enc:
                s.question_text_enc = new
                total += 1

        # 申诉补充说明
        for ap in db.query(RiskAppeal).all():
            if ap.appeal_note_enc:
                new = encrypt_field(decrypt_field(ap.appeal_note_enc))
                if new != ap.appeal_note_enc:
                    ap.appeal_note_enc = new
                    total += 1

        # 后台账号手机号
        for a in db.query(AdminUser).all():
            new = encrypt_field(decrypt_field(a.phone_enc))
            if new != a.phone_enc:
                a.phone_enc = new
                total += 1

        db.commit()
        print(f"[rotate_field_key] done: {total} rows re-encrypted to current version")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    rotate_all()
