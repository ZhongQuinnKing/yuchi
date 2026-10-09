#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 腔样本合成器 —— 为玉尺的阈值校准生成对照语料

用途：用 AI 写作的公认高频特征（句长均匀、连接词铺路、总分总、泛化举例）
合成"典型 AI 腔"文本，作为校准语料的低分侧基线。
只用于标定玉尺评分阈值，不用于伪造人类写作或规避任何检测。

生成 60 段（每段 300 字以上），固定随机种子，可复现。
运行：python3 make_ai_samples.py
"""
import os
import random
import re
import statistics

random.seed(20261009)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples", "ai_gen")

PUNCT = set("，。！？；：、「」『』（）《》〈〉【】…—·～,.!?;:()\"'“”‘’ \t")

TOPICS = [
    "个人成长", "人际关系", "时间管理", "学习方法", "职业规划",
    "情绪管理", "健康生活", "团队协作", "沟通能力", "终身学习",
    "自我提升", "工作与生活的平衡", "理财意识", "阅读习惯", "独立思考能力",
    "适应能力", "创新思维", "责任与担当", "感恩之心", "自律",
]

OPENINGS = [
    "在当今{a}，{t}的重要性日益凸显。",
    "在日常生活的方方面面，{t}越来越受到人们的重视。",
    "随着{b}，{t}成为人们普遍关注的话题。",
    "近年来，随着{b}，{t}显得尤为重要。",
    "在{a}中，如何提升{t}成为每个人都需要面对的课题。",
]
OPEN_A = ["快速发展的社会", "竞争日益激烈的时代", "信息爆炸的时代", "不断变化的时代"]
OPEN_B = ["社会的不断进步", "生活节奏的加快", "人们生活水平的不断提高", "时代的快速发展"]

CONNECTORS = [
    "一方面，", "另一方面，", "首先，", "其次，", "再次，", "最后，",
    "此外，", "与此同时，", "更重要的是，", "除此之外，",
]
CLAIMS = [
    "良好的{t}能够为我们{p}。",
    "{t}不仅关乎个人的当前发展，更关乎长远的人生走向。",
    "提升{t}需要我们{u}。",
    "{t}对于每个人的成长都具有不容忽视的重要意义。",
    "在{t}的过程中，我们能够{p}。",
]
CLAIM_P = [
    "提供重要的支持和帮助", "带来意想不到的收获", "创造更多的可能性",
    "奠定坚实的基础", "注入源源不断的动力",
]
CLAIM_U = [
    "在日常生活中不断学习与实践", "保持足够的耐心与坚持",
    "注重日常的积累与总结", "主动进行反思和改进",
]
SUPPORTS = [
    "只有{q}，才能真正实现{g}。",
    "当我们能够{v}时，往往会发现生活变得更加美好。",
    "这不仅能够{p}，也有助于我们更好地面对未来的挑战。",
    "通过{v}，我们能够逐步接近自己理想的状态。",
]
SUPPORT_Q = ["持之以恒地付出努力", "保持正确的方法和方向", "不断调整和完善自己"]
SUPPORT_G = ["个人的全面发展", "理想的生活状态", "更好的自己"]
SUPPORT_V = [
    "用心对待身边的每一个人和每一件事", "以积极的态度面对生活中的各种挑战",
    "把学到的知识运用到实际生活中", "在忙碌中留出时间关照自己的内心",
]
ASIDES = [
    "值得注意的是，{t}并非一朝一夕之功。",
    "需要指出的是，{t}与我们的日常生活息息相关。",
    "不可否认，在{t}方面，每个人都会遇到各种各样的挑战。",
    "值得一提的是，{t}需要我们以长远的眼光来看待。",
]
CLOSINGS = [
    "综上所述，{t}是一门需要{a}的艺术。",
    "总而言之，只要我们{c}，就一定能够{r}。",
    "由此可见，{t}值得我们用一生去学习和实践。",
]
CLOSE_A = ["终身学习", "持续投入", "用心经营", "认真对待"]
CLOSE_C = ["保持积极乐观的心态，坚持不懈地努力", "从点滴做起，脚踏实地地积累"]
CLOSE_R = ["收获属于自己的美好人生", "在人生的道路上走得更远", "创造出更加美好的未来"]
URGES = [
    "让我们从今天开始，{u}。",
    "从现在开始，让我们一起{u}。",
]
URGE_U = ["用心经营生活的每一天", "关注自身的成长与进步", "努力成为更好的自己"]


def clean_len(s):
    return len([c for c in s if c not in PUNCT])


def sent_lens(text):
    sents = [p for p in re.split(r"(?<=[。！？；])", text) if p.strip()]
    return [clean_len(s) for s in sents if clean_len(s) > 0]


def make_segment(topic):
    t = topic
    sents = [random.choice(OPENINGS).format(t=t, a=random.choice(OPEN_A),
                                           b=random.choice(OPEN_B))]
    conns = random.sample(CONNECTORS, random.randint(4, 6))
    for c in conns:
        sents.append(c + random.choice(CLAIMS).format(
            t=t, p=random.choice(CLAIM_P), u=random.choice(CLAIM_U)))
        if random.random() < 0.75:
            sents.append(random.choice(SUPPORTS).format(
                p=random.choice(CLAIM_P), q=random.choice(SUPPORT_Q),
                g=random.choice(SUPPORT_G), v=random.choice(SUPPORT_V)))
    sents.append(random.choice(ASIDES).format(t=t))
    sents.append(random.choice(CLOSINGS).format(
        t=t, a=random.choice(CLOSE_A), c=random.choice(CLOSE_C),
        r=random.choice(CLOSE_R)))
    if random.random() < 0.6:
        sents.append(random.choice(URGES).format(u=random.choice(URGE_U)))
    return "".join(sents)


def is_good(text):
    ls = sent_lens(text)
    if len(ls) < 8 or sum(ls) < 280:
        return None
    cv = statistics.pstdev(ls) / statistics.mean(ls)
    if 0.08 <= cv <= 0.30:
        return cv
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    made, stats = 0, []
    for i in range(1, 61):
        topic = TOPICS[(i - 1) % len(TOPICS)]
        for _ in range(30):
            text = make_segment(topic)
            cv = is_good(text)
            if cv is not None:
                path = os.path.join(OUT, f"ai_{i:02d}.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
                ls = sent_lens(text)
                stats.append((i, len(ls), statistics.mean(ls), cv, sum(ls)))
                made += 1
                break
    print(f"生成 {made} 段 → {OUT}")
    if stats:
        cvs = [s[3] for s in stats]
        means = [s[2] for s in stats]
        print(f"句数范围 {min(s[1] for s in stats)}-{max(s[1] for s in stats)}"
              f"　平均句长 {min(means):.0f}-{max(means):.0f}"
              f"　变异系数 {min(cvs):.2f}-{max(cvs):.2f}"
              f"（均值 {statistics.mean(cvs):.2f}）")


if __name__ == "__main__":
    main()
