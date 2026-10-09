#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺校准器 —— 用两侧语料标定 CONFIG 阈值

读 samples/human（真人侧，拾级自有语料 20 段 + 文学锚单列）
与 samples/ai_gen（AI 侧，特征合成 60 段），
对每项指标算两组分布，给出建议阈值（满分点 / 零点）。
运行：python3 calibrate.py
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuchi  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

METRICS = [
    ("cv", "大句变异系数", True),
    ("clause_cv", "小句变异系数", True),
    ("flat_n", "最长平滑段句数", False),
    ("short_per200", "短句密度/200字", True),
    ("glue_density", "套话密度/百字", False),
    ("dash_density", "破折号密度/百字", False),
    ("struct_raw", "结构词分", False),
]


def load(dirname):
    d = os.path.join(HERE, "samples", dirname)
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.endswith(".txt") and not f.startswith("_"):
            t = open(os.path.join(d, f), encoding="utf-8").read()
            out.append((f, yuchi.analyze(t)))
    return out


def q(vals, p):
    vals = sorted(vals)
    k = (len(vals) - 1) * p
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[f] + (vals[c] - vals[f]) * (k - f)


def main():
    human = load("human")
    prose = load("human_prose")   # 公版散文锚（v1.4 起，参照表按此 + human 散文型标）
    ai = load("ai_gen")
    real = load("ai_real")        # 真实 AI 输出（v1.1 起）
    anchor = yuchi.analyze(
        open(os.path.join(HERE, "samples", "luxun_qiuye.txt"), encoding="utf-8").read())

    print(f"真人样本 {len(human)} 段　散文锚 {len(prose)} 段　AI 合成 {len(ai)} 段　"
          f"AI 真实 {len(real)} 段（另有文学锚：秋夜）")
    print()
    head = (f"{'指标':<14}{'人类中位':>10}{'人类范围':>16}"
            f"{'AI中位':>10}{'AI范围':>16}{'建议阈值[满,零]':>20}")
    print(head)
    print("-" * len(head.encode("gbk", "ignore")))
    for key, name, higher_better in METRICS:
        h = [r[key] for _, r in human]
        a = [r[key] for _, r in ai]
        if higher_better:
            full, zero = q(h, 0.25), q(a, 0.75)
        else:
            full, zero = q(h, 0.75), q(a, 0.25)
        print(f"{name:<14}{statistics.median(h):>10.2f}"
              f"{f'[{min(h):.2f},{max(h):.2f}]':>16}"
              f"{statistics.median(a):>10.2f}"
              f"{f'[{min(a):.2f},{max(a):.2f}]':>16}"
              f"{f'[{full:.2f},{zero:.2f}]':>20}")
    print()
    hs = [r["score"] for _, r in human]
    as_ = [r["score"] for _, r in ai]
    print(f"当前评分：人类 {min(hs)} 到 {max(hs)}（中位 {statistics.median(hs):.0f}）")
    print(f"　　　　　AI {min(as_)} 到 {max(as_)}（中位 {statistics.median(as_):.0f}）")
    rs = [r["score"] for _, r in real]
    if rs:
        print(f"　　　　　AI 真实 {min(rs)} 到 {max(rs)}（中位 {statistics.median(rs):.0f}）")
    print(f"　　　　　文学锚（秋夜）{anchor['score']}")
    lo, hi = max(min(hs), min(as_)), min(max(hs), max(as_))
    if lo <= hi:
        print(f"⚠ 两群重叠区间 {lo}-{hi}，需调权重或指标")
    else:
        print("✓ 两群分数无重叠，分离干净")


if __name__ == "__main__":
    main()
