# -*- coding: utf-8 -*-
"""临时脚本：品牌名批量替换 家伴 -> 小光景（保护文件名引用）。任务完成后删除。）

规则：
1. 先保护 `家伴-*` 文档文件名引用前缀（替换为占位符）；
2. 替换 家伴 -> 小光景、家庭养育多智能体助手 -> 一家人的养育参考；
   线框中的 家<全角空格>伴 -> 小光景（等宽保留）；
3. 还原占位符；
4. 保持原文件的 BOM 与换行符（二进制读写 + 无换行转换）；
5. 编辑前将全部目标文件打包备份到 .build/_brand_backup_pre.zip。
"""
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\HomeBud"
TARGETS = [
    r"README.md",
    r"CONTEXT.md",
    r"PROJECT_PROGRESS.html",
    r"docs\02-基线\家伴-PRD_V1.5.md",
    r"docs\02-基线\家伴-UI原型描述_V1.3.md",
    r"docs\03-设计\PRODUCT.md",
    r"docs\03-设计\DESIGN.md",
    r"docs\03-设计\家伴-设计系统样式瓦片.html",
    r"docs\03-设计\Stitch提示词包_家伴_V1.md",
    r"docs\04-工程\家伴-架构设计文档_V1.1.md",
    r"docs\04-工程\家伴-数据模型文档_V1.1.md",
    r"docs\04-工程\微信小程序术语表.md",
    r"docs\04-工程\独立向量库接入方案_Milvus_2026-10-12.md",
    r"docs\04-工程\RAG检索层改造方案_LlamaIndex_2026-10-12.md",
    r"docs\06-机构方向\机构工作台方向-收敛与验证方案_V0.1.md",
    r"docs\07-竞品调研\README.md",
    r"docs\07-竞品调研\开源竞品调研_宠物方向.md",
    r"docs\07-竞品调研\开源竞品调研_多智能体与安全护栏.md",
    r"docs\07-竞品调研\上市竞品调研_育儿与宠物.md",
    r"docs\API.md",
    r"docs\RESTful审查_2026-10-11.md",
    r"docs\微信小程序接入判定与准备清单_2026-10-12.md",
    r"docs\性能压测报告_close-module-gaps.md",
    r"docs\性能基线_2026-10-11.md",
    r"docs\测试报告_全面模拟测试_2026-10-09.md",
    r"docs\测试报告_全面模拟测试_2026-10-10.md",
    r"docs\测试报告_全面模拟测试_2026-10-12.md",
    r"项目进度评估报告_2026-10-12.md",
    r"项目核心功能清单与完成度评估_2026-10-11.md",
    r"frontend\index.html",
    r"frontend\src\views\app\StartPage.vue",
    r"frontend\src\views\app\HomePage.vue",
    r"frontend\src\views\app\MePage.vue",
    r"frontend\src\views\app\RiskBlockPage.vue",
    r"frontend\src\views\app\ReportImagePage.vue",
    r"frontend\src\views\app\FeedbackPage.vue",
    r"frontend\src\views\admin\AdminLayout.vue",
    r"frontend\src\views\admin\AdminLoginPage.vue",
    r"frontend\src\views\admin\FeedbackPage.vue",
    r"frontend\src\router\index.ts",
    r"frontend\src\api\admin.ts",
    r"frontend\src\styles\tokens.scss",
    r"wechat-miniapp\src\manifest.json",
    r"wechat-miniapp\src\components\MiniPageHeader.vue",
    r"wechat-miniapp\src\pages\qa\index.vue",
    r"wechat-miniapp\src\pages\report\index.vue",
    r"wechat-miniapp\src\pages\index\index.vue",
    r"wechat-miniapp\src\pages\assessment\index.vue",
    r"wechat-miniapp\README.md",
    r"backend\app\main.py",
    r"backend\scripts\seed_data.py",
    r"backend\scripts\smoke_test.py",
    r"backend\scripts\load_test.py",
    r"backend\scripts\export_api_doc.py",
    r"backend\requirements.txt",
    r"deploy\nginx.conf",
    r"deploy\frontend.dockerfile",
    r"deploy\backend.Dockerfile",
    r"deploy\docker-compose.yml",
    r"deploy\README.md",
    r"deploy\.env.example",
    r"scripts\ci_gate.ps1",
    r"scripts\backup_db.ps1",
    r"scripts\restore_db.ps1",
    r"scripts\start.ps1",
    r"scripts\status.ps1",
    r"scripts\stop.ps1",
    r".github\workflows\ci.yml",
    r".gitignore",
]

# 需要保持原样的文档文件名前缀（先保护，替换后还原）
PROTECT = [
    "家伴-家庭养育多智能体助手",
    "家伴-PRD",
    "家伴-UI原型描述",
    "家伴-架构设计文档",
    "家伴-数据模型文档",
    "家伴-设计系统样式瓦片",
    "家伴-需求文档",
    "家伴需求评审材料",
    "家伴需求文档_审核意见",
    "家伴-V1.2审核报告",
    "家伴-V1.3_S1问题修法清单",
    "家伴-UI审计与优化清单",
    "Stitch提示词包_家伴",
]


def read_text(raw):
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig" if bom else "utf-8"), bom


def transform(text):
    for i, p in enumerate(PROTECT):
        text = text.replace(p, "\x00%d\x00" % i)
    text = text.replace("家　伴", "小光景")
    text = text.replace("家伴", "小光景")
    text = text.replace("家庭养育多智能体助手", "一家人的养育参考")
    for i, p in enumerate(PROTECT):
        text = text.replace("\x00%d\x00" % i, p)
    return text


def main():
    missing = [t for t in TARGETS if not os.path.exists(os.path.join(ROOT, t))]
    if missing:
        print("MISSING %d:" % len(missing))
        for m in missing:
            print("  " + m)
        sys.exit(2)

    backup = os.path.join(ROOT, ".build", "_brand_backup_pre.zip")
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as z:
        for t in TARGETS:
            z.write(os.path.join(ROOT, t), t)
    print("backup ok -> .build/_brand_backup_pre.zip")

    log = []
    changed = skipped = 0
    for idx, t in enumerate(TARGETS, 1):
        full = os.path.join(ROOT, t)
        raw = open(full, "rb").read()
        text, bom = read_text(raw)
        new = transform(text)
        if new == text:
            skipped += 1
            log.append("SKIP    #%02d %s" % (idx, t))
            continue
        n_old = text.count("家伴") + text.count("家　伴")
        n_new = new.count("家伴") + new.count("家　伴")
        n_sub = text.count("家庭养育多智能体助手") - new.count("家庭养育多智能体助手")
        out = new.encode("utf-8-sig" if bom else "utf-8")
        open(full, "wb").write(out)
        changed += 1
        log.append("CHANGED #%02d %s  [主名×%d, 副标题×%d]"
                   % (idx, t, n_old - n_new, n_sub))

    with open(os.path.join(ROOT, ".build", "_brand_changes.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\nchanged=%d skipped=%d total=%d\n"
                % (changed, skipped, len(TARGETS)))
    print("changed=%d skipped=%d" % (changed, skipped))


if __name__ == "__main__":
    main()
