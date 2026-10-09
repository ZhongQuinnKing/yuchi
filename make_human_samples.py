#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真人语料抽取器 —— 为玉尺阈值校准生成高分侧语料

来源：拾级（自有原创项目）references/ 下的正文段落。
抽取规则：随机 20 篇，每篇随机取一个 250-450 汉字的正文段落
（跳过标题、列表、引用、表格、代码块）。
固定随机种子，可复现。
运行：python3 make_human_samples.py
"""
import os
import random
import re

random.seed(20261009)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/.claude/skills/shiji/references")
OUT = os.path.join(HERE, "samples", "human")


def hanzi_count(s):
    return len(re.findall(r"[一-鿿]", s))


def is_prose(p):
    p = p.strip()
    if not p or p[0] in "#-*>|`【（(":
        return False
    if re.match(r"^\d", p):
        return False
    return 120 <= hanzi_count(p) <= 500


def main():
    if not os.path.isdir(SRC):
        print(f"语料源不存在：{SRC}")
        return
    paths = []
    for root, _, files in os.walk(SRC):
        for f in files:
            if f.endswith(".md"):
                paths.append(os.path.join(root, f))
    random.shuffle(paths)

    pool = []
    for path in paths:
        text = open(path, encoding="utf-8").read()
        paras = [p.strip() for p in text.split("\n\n") if is_prose(p)]
        random.shuffle(paras)
        for p in paras[:3]:
            pool.append((path, p))
    random.shuffle(pool)
    picked = pool[:20]
    print(f"合格段池 {len(pool)} 段，取前 {len(picked)}")

    os.makedirs(OUT, exist_ok=True)
    for i, (path, p) in enumerate(picked, 1):
        rel = os.path.relpath(path, os.path.dirname(SRC))
        out = os.path.join(OUT, f"h_{i:02d}.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"# 来源：拾级 · {rel}（节选，自有原创内容）\n")
            f.write(p + "\n")
    made = len(picked)

    stats = []
    for f in sorted(os.listdir(OUT)):
        t = open(os.path.join(OUT, f), encoding="utf-8").read()
        stats.append(hanzi_count(t))
    print(f"抽取 {made} 段 → {OUT}")
    print(f"字数范围 {min(stats)}-{max(stats)}　平均 {sum(stats)//len(stats)}")


if __name__ == "__main__":
    main()
