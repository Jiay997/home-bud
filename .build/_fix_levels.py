# -*- coding: utf-8 -*-
"""一次性规范化 Q 表的阻塞级别；执行后本文件可删除。"""
import io
import re

P = r"D:\HomeBud\.build\ledger.py"

LEVEL = {
    # B1 = 开工阻塞（未决策，不得开发）
    "Q-03": "B1", "Q-06": "B1", "Q-08": "B1", "Q-10": "B1", "Q-11": "B1",
    "Q-13": "B1", "Q-23": "B1", "Q-35": "B1", "Q-38": "B1",
    # B2 = 上线阻塞
    "Q-04": "B2", "Q-05": "B2", "Q-07": "B2", "Q-09": "B2", "Q-12": "B2",
    "Q-25": "B2", "Q-28": "B2", "Q-31": "B2", "Q-32": "B2", "Q-33": "B2",
    "Q-34": "B2", "Q-42": "B2", "Q-43": "B2", "Q-45": "B2",
    # B3 = 运营参数待定
    "Q-01": "B3", "Q-02": "B3", "Q-17": "B3", "Q-20": "B3", "Q-22": "B3",
    "Q-24": "B3", "Q-26": "B3", "Q-39": "B3",
    # 已关闭
    "Q-14": "已关闭", "Q-15": "已关闭", "Q-16": "已关闭", "Q-18": "已关闭",
    "Q-19": "已关闭", "Q-21": "已关闭", "Q-27": "已关闭", "Q-29": "已关闭",
    "Q-30": "已关闭", "Q-36": "已关闭", "Q-37": "已关闭", "Q-40": "已关闭",
    "Q-41": "已关闭",
}


def main():
    s = io.open(P, encoding="utf-8").read()
    s = s.replace('"**B1**"', '"B1"')
    misses = []
    for qid, level in LEVEL.items():
        pat = re.compile(r'\("' + re.escape(qid) + r'", ("(?:[^"\\]|\\.)*"), "(?:B1|B2|B3|已关闭)"')
        s, k = pat.subn(lambda m: '("' + qid + '", ' + m.group(1) + ', "' + level + '"', s)
        if k != 1:
            misses.append((qid, k))
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("misses:", misses or "none")


if __name__ == "__main__":
    main()