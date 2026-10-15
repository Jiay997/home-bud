# -*- coding: utf-8 -*-
"""Realign all wireframe box lines after brand swap.

For each contiguous block of box-drawing lines, the reference width is the
mode (most common) cell width in that block; any line deviating by +/-2 is
repaired by adjusting its longest internal space run.
"""
import re
from collections import Counter

PATHS = [r"D:\HomeBud\docs\02-基线\家伴-UI原型描述_V1.3.md"]
BOX_CHARS = set("│┌└├─┐┘┤")


def cells(s):
    return sum(2 if ord(c) > 0x2E7F else 1 for c in s)


def fix_line_width(line, target):
    """Adjust line to target cell width by modifying its longest internal space run."""
    body = line.rstrip("\r\n")
    eol = line[len(body):]
    diff = cells(body) - target
    if diff == 0:
        return None
    runs = [m for m in re.finditer(r" {2,}", body)]
    if not runs:
        return None
    runs.sort(key=lambda m: m.end() - m.start(), reverse=True)
    m = runs[0]
    take = min(diff, m.end() - m.start() - 1) if diff > 0 else diff
    if diff > 0:
        # shrink: remove `take` spaces
        new = body[:m.end() - take] + body[m.end():]
    else:
        # widen: add spaces
        new = body[:m.start()] + " " * (-diff) + body[m.start():]
    return new + eol


def is_box_line(line):
    s = line.lstrip()
    return bool(s) and s[0] in BOX_CHARS


for path in PATHS:
    raw = open(path, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig" if has_bom else "utf-8")
    lines = text.splitlines(keepends=True)
    n = len(lines)

    # group into blocks
    blocks = []
    cur = []
    for i, ln in enumerate(lines):
        if is_box_line(ln):
            cur.append(i)
        else:
            if cur:
                blocks.append(cur)
                cur = []
    if cur:
        blocks.append(cur)

    fixed = 0
    for blk in blocks:
        widths = Counter(cells(lines[i].rstrip("\r\n")) for i in blk)
        target, _ = widths.most_common(1)[0]
        for i in blk:
            ln = lines[i]
            w = cells(ln.rstrip("\r\n"))
            if w != target:
                new = fix_line_width(ln, target)
                if new is not None and new != ln:
                    print("L%d: %d -> %d" % (i + 1, w, cells(new.rstrip("\r\n"))))
                    lines[i] = new
                    fixed += 1

    out = "".join(lines).encode("utf-8")
    if has_bom:
        out = b"\xef\xbb\xbf" + out
    open(path, "wb").write(out)
    print("%s: fixed=%d blocks=%d" % (path, fixed, len(blocks)))
