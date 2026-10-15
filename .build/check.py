# -*- coding: utf-8 -*-
"""一致性自检：线框中引用的 FR/AS 是否在 PRD 中定义；SC/PA 页号是否与页面清单一致。"""
import os
import re

B = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(B)


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


prd_all = read(os.path.join(ROOT, 'docs', '99-归档', '家伴-PRD_V1.1.md'))
prd_ch6 = read(os.path.join(B, 'prd-2.md'))
prd_apx = read(os.path.join(B, 'prd-5.md'))
ui_head = read(os.path.join(B, 'ui-1.md'))
ui_tail = read(os.path.join(B, 'ui-2.md'))

frags = ''.join(read(os.path.join(B, n)) for n in sorted(os.listdir(B)) if n.startswith('frag-'))

defined_fr = set(re.findall(r'^\| (FR-[A-Z]\d+) \|', prd_ch6, re.M))
defined_as = set(re.findall(r'^\| (AS-\d+) \|', prd_apx, re.M))
defined_cg = set(re.findall(r'^\| (CG\d+) \|', prd_apx, re.M))

used_fr = set(re.findall(r'FR-[A-Z]\d+', frags))
used_as = set(re.findall(r'AS-\d+', frags))
used_cg = set(re.findall(r'CG\d+', frags))

print('FR defined=%d used_in_wireframes=%d' % (len(defined_fr), len(used_fr)))
print('  未定义的 FR 引用:', sorted(used_fr - defined_fr) or '无')
print('  未被线框引用的 FR:', sorted(defined_fr - used_fr) or '无')
print('AS defined=%d used_in_wireframes=%d' % (len(defined_as), len(used_as)))
print('  未定义的 AS 引用:', sorted(used_as - defined_as, key=lambda x: int(x.split('-')[1])) or '无')
print('CG defined=%d used_in_wireframes=%d' % (len(defined_cg), len(used_cg)))
print('  未定义的 CG 引用:', sorted(used_cg - defined_cg, key=lambda x: int(x[2:])) or '无')

# 页面编号
head_ids = set(re.findall(r'\| (S?P?A?-?\d\d) \|', ui_head))
pages = set(re.findall(r'^### (SC-\d\d|PA-\d\d) ', frags, re.M))
listed = set(re.findall(r'\| (SC-\d\d|PA-\d\d) \|', ui_head))
print('页面清单=%d 已绘制线框=%d' % (len(listed), len(pages)))
print('  清单中缺线框:', sorted(listed - pages) or '无')
print('  线框中未列入清单:', sorted(pages - listed) or '无')

# 关键词密度与规模
print('PRD 字符数=%d 行数=%d' % (len(prd_all), prd_all.count('\n') + 1))
print('UI 字符数=%d' % (len(ui_head) + len(ui_tail) + len(frags)))

# 用词规范抽检（禁用词出现在正文中的位置）
banned = ['心理诊断', '包提分', '算命', '天生注定', '代做作业', '性格永久判定']
for w in banned:
    hits = [m.start() for m in re.finditer(w, prd_all + ui_head + ui_tail + frags)]
    if hits:
        print('  禁用词命中（需人工确认是否为"禁止用词"示例）: %s x%d' % (w, len(hits)))
