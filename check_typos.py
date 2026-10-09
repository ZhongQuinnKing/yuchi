#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺文字校对扫描（提醒式，只列不改）

七类：半角标点夹中文、重复标点、重复字、括号未配平、全角字母数字、
中文间多余空格、常见错字表。
范围：面向读者的文档（README/SKILL/references/docs/templates/提案）。
运行：python3 check_typos.py
"""
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))

COMMON_TYPO = {
    "的的": "多重“的”",
    "了了": "重复“了”",
    "是是": "重复“是”",
    "在在": "重复“在”",
    "不听得": "应为“听不懂”",
    "即然": "应为“既然”",
    "以经": "应为“已经”",
    "必需": "视语境（必须/必需）",
    "按耐": "应为“按捺”",
}

REPEAT_OK = set("人天年日时分秒月季家家户户说说看看试试想想慢慢渐渐"
                "文彬巴对长短前后常往好谢点件篇段句方步层条道遍遍次次")
HALF_WITH_CJK = re.compile(r"[一-鿿][,;!?]|[,;!?][一-鿿]")


def targets():
    out = ["README.md", "SKILL.md", "MAINTAINING.md", "CHANGELOG.md",
           "提案-玉尺项目.md", "templates/文风档案.md", "docs/诗-借鉴研究.md"]
    refs = os.path.join(ROOT, "references")
    if os.path.isdir(refs):
        out += [f"references/{f}" for f in sorted(os.listdir(refs)) if f.endswith(".md")]
    return [t for t in out if os.path.exists(os.path.join(ROOT, t))]


def scan(path):
    text = open(os.path.join(ROOT, path), encoding="utf-8").read()
    issues = []
    for i, line in enumerate(text.split("\n"), 1):
        s = line.rstrip()
        for m in HALF_WITH_CJK.finditer(s):
            issues.append((i, "半角标点夹中文", m.group()))
        for m in re.finditer(r"[，。、；：]{2,}", s):
            g = m.group()
            if g in ("……",) or "——" in g:
                continue
            issues.append((i, "重复标点", g))
        for m in re.finditer(r"([一-鿿])\1", s):
            ch = m.group(1)
            if ch not in REPEAT_OK:
                issues.append((i, "重复字", m.group()))
        if s.count("（") != s.count("）"):
            issues.append((i, "括号未配平", f"（×{s.count('（')} ）×{s.count('）')}"))
        for m in re.finditer(r"[Ａ-Ｚａ-ｚ０-９]", s):
            issues.append((i, "全角字母数字", m.group()))
        for m in re.finditer(r"[一-鿿] +[一-鿿]", s):
            issues.append((i, "中文间空格", m.group()))
        for bad, why in COMMON_TYPO.items():
            if bad in s:
                issues.append((i, f"疑似错字（{why}）", bad))
    return issues


def main():
    total = 0
    for t in targets():
        issues = scan(t)
        if issues:
            print(f"== {t} ==")
            for i, kind, ctx in issues[:15]:
                print(f"  L{i} [{kind}] {ctx}")
            if len(issues) > 15:
                print(f"  （另有 {len(issues)-15} 条）")
            total += len(issues)
    print(f"\n扫描 {len(targets())} 个文件，{total} 条待复核（提醒式，逐条人工看）")


if __name__ == "__main__":
    main()
