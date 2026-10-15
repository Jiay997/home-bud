from app.agents.prompts import (
    CHILD_AGENT_SYSTEM_PROMPT,
    PET_AGENT_SYSTEM_PROMPT,
    SAFETY_AGENT_SYSTEM_PROMPT,
)


def test_user_visible_agent_copy_is_required_to_use_simplified_chinese():
    language_rule = "所有面向用户展示的标题与正文必须使用简体中文"

    assert language_rule in CHILD_AGENT_SYSTEM_PROMPT
    assert language_rule in PET_AGENT_SYSTEM_PROMPT
    assert language_rule in SAFETY_AGENT_SYSTEM_PROMPT
