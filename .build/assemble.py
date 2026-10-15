# -*- coding: utf-8 -*-
"""合并 UI 文档：ui-1（规范+页面清单） + 各批线框片段 + ui-2（状态/时序/文案/组件/交付）"""
import os

B = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(B)

HEAD = 'ui-1.md'
FRAGS = ['frag-sc0106.md', 'frag-sc0712.md', 'frag-sc1319.md', 'frag-sc2026.md',
         'frag-pa_a.md', 'frag-pa_b.md']
TAIL = 'ui-2.md'


def read(name):
    with open(os.path.join(B, name), encoding='utf-8') as f:
        return f.read().rstrip('\n')


def main():
    missing = [f for f in FRAGS if not os.path.exists(os.path.join(B, f))]
    if missing:
        raise SystemExit('缺少片段文件: %s' % missing)
    parts = [read(HEAD)] + [read(f) for f in FRAGS] + [read(TAIL)]
    text = '\n\n'.join(parts) + '\n'
    out = os.path.join(ROOT, 'docs', '02-基线', '家伴-UI原型描述_V1.2.md')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('written: %s (%d chars, %d lines)' % (out, len(text), text.count('\n') + 1))


if __name__ == '__main__':
    main()
