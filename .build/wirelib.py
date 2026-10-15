# -*- coding: utf-8 -*-
"""等宽线框绘制库：按显示宽度（CJK=2，其余=1）补白，保证 box-drawing 对齐。

约定：所有 U+2500 区制表符在等宽正文字体下按宽度 1 计（east_asian_width='A'）。
"""
import unicodedata

WIDE = ('W', 'F')

WARNINGS = []

# 东亚宽度歧义字符（east_asian_width == 'A'）在等宽正文字体下宽度不确定，
# 会破坏线框对齐。除制表符外，统一归一化为 ASCII 等价写法。
NORM = {
    '①': '(1)', '②': '(2)', '③': '(3)', '④': '(4)', '⑤': '(5)',
    '⑥': '(6)', '⑦': '(7)', '⑧': '(8)', '⑨': '(9)', '⑩': '(10)',
    '⑪': '(11)', '⑫': '(12)', '⑬': '(13)', '⑭': '(14)', '⑮': '(15)',
    'ⓘ': '(i)', '⚠': '!!', '✓': 'OK', '✗': 'NG', '⏳': '..', '▒': '##',
    '●': '*', '○': 'o', '▮': '#', '■': '#', '□': '-',
    '≤': '<=', '≥': '>=', '×': 'x', '→': '->', '←': '<-', '↑': '^', '↓': 'v',
    '·': '-', '—': '--', '–': '-', '「': '"', '」': '"', '『': '"', '』': '"',
    '【': '[', '】': ']', '〜': '~', '～': '~', '⋅': '-', '…': '...',
    '￥': 'RMB', '№': 'No.', '°': 'deg', '±': '+/-', '∞': 'inf',
}


def norm(s: str) -> str:
    return ''.join(NORM.get(c, c) for c in s)


def tbl(headers, rows):
    """构造 markdown 表格，避免手写分隔行出错"""
    out = ['| ' + ' | '.join(headers) + ' |',
           '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    for r in rows:
        assert len(r) == len(headers), '表格列数不匹配：%r' % (r,)
        out.append('| ' + ' | '.join(str(c) for c in r) + ' |')
    return '\n'.join(out)


def dw(s: str) -> int:
    """显示宽度"""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in WIDE else 1
    return w


def pad(s: str, width: int, align: str = 'l') -> str:
    d = width - dw(s)
    if d <= 0:
        return s
    if align == 'l':
        return s + ' ' * d
    if align == 'r':
        return ' ' * d + s
    left = d // 2
    return ' ' * left + s + ' ' * (d - left)


def box(rows, w: int, title: str = None):
    """rows 元素类型：
    ('t', 左对齐文本) / ('c', 居中) / ('b', 左文本, 右文本)
    ('kv', 键, 值) 点线连接 / ('sep',) 分隔线 / ('blank',) 空行
    ('btn', 文案) 居中按钮 / ('raw', 已排好的等宽行，按 w-2 宽度裁剪补白)
    ('cols', [行列表, ...]) 左右并排（各列以 2 空格间距拼接）
    """
    inner = w - 2
    out = []
    rows = [tuple(norm(x) if isinstance(x, str) else x for x in r) for r in rows]
    if title is not None:
        title = norm(title)
    for r in rows:
        if r[0] in ('t', 'raw', 'c'):
            if dw(r[1]) + (1 if r[0] == 't' else 0) > inner:
                WARNINGS.append('overflow(w=%d, dw=%d): %s' % (w, dw(r[1]), r[1]))
        elif r[0] in ('b', 'kv'):
            if dw(' ' + r[1]) + dw(r[2] + ' ') > inner:
                WARNINGS.append('overflow(w=%d): %s / %s' % (w, r[1], r[2]))
    if title is None:
        out.append('┌' + '─' * inner + '┐')
    else:
        t = ' ' + title + ' '
        out.append('┌' + pad(t + '─' * max(inner - dw(t) - 1, 0), inner) + '┐')
    for r in rows:
        k = r[0]
        if k == 't':
            out.append('│' + pad(' ' + r[1], inner) + '│')
        elif k == 'c':
            out.append('│' + pad(r[1], inner, 'c') + '│')
        elif k == 'b':
            left, right = ' ' + r[1], r[2] + ' '
            sp = inner - dw(left) - dw(right)
            out.append('│' + left + ' ' * max(sp, 1) + right + '│')
        elif k == 'kv':
            left, right = ' ' + r[1] + ' ', r[2] + ' '
            sp = inner - dw(left) - dw(right)
            out.append('│' + left + '.' * max(sp, 0) + right + '│')
        elif k == 'sep':
            out.append('├' + '─' * inner + '┤')
        elif k == 'blank':
            out.append('│' + ' ' * inner + '│')
        elif k == 'btn':
            out.append('│' + pad('[ ' + r[1] + ' ]', inner, 'c') + '│')
        elif k == 'raw':
            out.append('│' + pad(r[1], inner) + '│')
        elif k == 'cols':
            cols_lines = r[1]
            joined = []
            for i in range(max(len(c) for c in cols_lines)):
                parts = [c[i] if i < len(c) else ' ' * dw(c[0]) for c in cols_lines]
                joined.append('  '.join(parts))
            for line in joined:
                out.append('│' + pad(line, inner) + '│')
    out.append('└' + '─' * inner + '┘')
    return out


def side(lines_a, lines_b, gap: int = 2):
    """两栏并排（行列表）"""
    res = []
    wa = dw(lines_a[0]) if lines_a else 0
    for i in range(max(len(lines_a), len(lines_b))):
        a = lines_a[i] if i < len(lines_a) else ' ' * wa
        b = lines_b[i] if i < len(lines_b) else ''
        res.append(pad(a, wa) + ' ' * gap + b)
    return res


def hline(w: int):
    """整行横线（宽度 w）"""
    return '─' * w


def render_screen(sc: dict) -> str:
    """把单个页面 dict 渲染为 markdown 片段"""
    w = sc.get('w', 46)
    body = box(sc['rows'], w)
    title_line = sc['id'] + ' · ' + sc['title'] + ' · ' + sc.get('canvas', '')
    frame = box([('c', title_line)], w)
    out = []
    out.append('### ' + sc['id'] + ' · ' + sc['title'])
    out.append('')
    out.append('> **画布** ' + sc.get('canvas', '375×812（小程序）') +
               '　**优先级** ' + sc.get('pri', 'P0') +
               '　**对应需求** ' + sc.get('fr', '—'))
    out.append('')
    if sc.get('intro'):
        out.append('**页面目标**：' + sc['intro'])
        out.append('')
    out.append('```text')
    out.extend(frame)
    out.extend(body)
    out.append('```')
    out.append('')
    if sc.get('elems'):
        out.append('**元素说明**')
        out.append('')
        out.append(sc['elems'].strip())
        out.append('')
    if sc.get('states'):
        out.append('**状态与分支**')
        out.append('')
        out.append(sc['states'].strip())
        out.append('')
    if sc.get('events'):
        out.append('**埋点**：' + sc['events'])
        out.append('')
    if sc.get('note'):
        out.append('> **实现说明**：' + sc['note'])
        out.append('')
    # 页面内不保留「待确认」措辞：统一指向 UI 文档 §11 决策依赖索引
    deps = sc.get('deps') or '无未决项'
    out.append('- **决策依赖**：见 UI 文档 §11 决策依赖索引（编号：' + deps + '）')
    out.append('')
    return '\n'.join(out)
