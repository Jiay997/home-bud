# -*- coding: utf-8 -*-
"""组装《家伴-PRD_V1.2.md》。

做法：把所有来源文件按 `## x` / `### x.y` 标题切成键值块，然后按键号数值排序输出。
这样插入的新章节会自动落到正确位置，且不会重复或漏章。
"""
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(B)

SOURCES = [
    "prd-1.md", "gen-changes.md", "add-baseline.md",
    "prd-2.md", "gen-fr-status.md", "sec-617.md",
    "prd-3.md", "sec-71.md", "add-protocol.md", "sec-79.md",
    "prd-4.md", "add-compliance.md", "add-terms.md", "add-kb.md", "add-assess.md", "add-refund.md",
    "prd-5.md",
    "add-perm.md", "add-events.md", "add-api.md", "add-loop.md",
]

HEAD_RE = re.compile(r"^(#{2,3})\s+(\d+(?:\.\d+)?)(?!\.\d)(?:\.|\s)")


def read(p):
    return io.open(p, encoding="utf-8").read()


def key_of(num):
    return tuple(int(x) for x in num.split("."))


def main():
    blocks = {}
    preamble = None

    for name in SOURCES:
        p = os.path.join(B, name)
        if not os.path.exists(p):
            print("!! MISSING %s" % name)
            continue
        text = read(p)
        lines = text.split("\n")
        cur_key = None
        cur = []
        for ln in lines:
            m = HEAD_RE.match(ln)
            if m:
                if cur_key is None:
                    if preamble is None:
                        preamble = "\n".join(cur).strip("\n")
                else:
                    if cur_key in blocks:
                        print("!! DUPLICATE key %s (from %s)" % (cur_key, name))
                    blocks[cur_key] = "\n".join(cur).rstrip("\n")
                cur_key = m.group(2)
                cur = [ln]
            else:
                cur.append(ln)
        if cur_key is not None:
            if cur_key in blocks:
                print("!! DUPLICATE key %s (from %s)" % (cur_key, name))
            blocks[cur_key] = "\n".join(cur).rstrip("\n")

    order = sorted(blocks.keys(), key=key_of)

    # 第 20 章：用机器生成的附录 A/B/C 替换 prd-5 中手写的同名附录，保留附录 D/E
    gen = os.path.join(B, "gen-appendix.md")
    if "20" in blocks and os.path.exists(gen):
        gen_text = read(gen).rstrip("\n")
        cur20 = blocks["20"]
        cut = cur20.find("### 附录 D")
        if cut < 0:
            print("!! 附录 D not found in ch20; appending generated block instead")
            blocks["20"] = cur20.rstrip("\n") + "\n\n" + gen_text
        else:
            blocks["20"] = "## 20. 附录\n\n" + gen_text + "\n\n" + cur20[cut:]
        print("ch20 recomposed with generated appendix A/B/C")

    out = []
    out.append(preamble or "")
    for k in order:
        out.append(blocks[k])

    # 文末：机器生成的阻塞项摘要
    blk = os.path.join(B, "gen-blockers.md")
    if os.path.exists(blk):
        out.append("## 22. 当前阻塞项摘要（机器生成）\n\n" + read(blk).rstrip("\n"))
        print("appended ch22 blockers summary")

    doc = "\n\n".join(out).rstrip("\n") + "\n"

    dst = os.path.join(ROOT, "docs", "02-基线", "家伴-PRD_V1.2.md")
    io.open(dst, "w", encoding="utf-8", newline="\n").write(doc)
    print("wrote %s" % dst)
    print("blocks=%d  chars=%d  lines=%d" % (len(blocks), len(doc), doc.count("\n") + 1))
    print("chapters: " + ", ".join(k for k in order if "." not in k))


if __name__ == "__main__":
    main()