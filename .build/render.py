# -*- coding: utf-8 -*-
"""把各屏幕模块渲染为 markdown 片段。用法：python render.py 输出文件 模块名..."""
import sys
import os
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from wirelib import render_screen  # noqa: E402


def main():
    out_path = sys.argv[1]
    mods = sys.argv[2:]
    chunks = []
    total = 0
    for m in mods:
        mod = importlib.import_module(m)
        for sc in mod.SCREENS:
            chunks.append(render_screen(sc))
            total += 1
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(chunks))
    print('screens=%d -> %s' % (total, out_path))
    import wirelib
    if wirelib.WARNINGS:
        print('WARNINGS (%d):' % len(wirelib.WARNINGS))
        for wmsg in wirelib.WARNINGS:
            print('  ' + wmsg)
    else:
        print('WARNINGS: none')


if __name__ == '__main__':
    main()
