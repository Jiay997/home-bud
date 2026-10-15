# -*- coding: utf-8 -*-
"""把插入章节的标题层级统一为 ### （章内小节）。"""
import io
import os

B = os.path.dirname(os.path.abspath(__file__))

FIX = {
    "sec-71.md": [("## 7.1 ", "### 7.1 "), ("## 7.9 ", "### 7.9 ")],
    "sec-79.md": [("## 7.9 ", "### 7.9 ")],
    "add-protocol.md": [("## 7.5 ", "### 7.5 "), ("## 7.7 ", "### 7.7 "), ("## 7.8 ", "### 7.8 ")],
}

for name, pairs in FIX.items():
    p = os.path.join(B, name)
    if not os.path.exists(p):
        print("skip", name)
        continue
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("leveled", name)