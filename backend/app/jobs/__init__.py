# -*- coding: utf-8 -*-
"""后台定时任务包。

包含 APScheduler 调度器装配（scheduler）与各周期任务：
对账（reconcile）、测评断点清理（assessment_draft_cleanup）、
危机渠道复核提醒（channel_review_remind）。
"""
