#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺检查器 v0 —— 中文文章的节奏诊断

定位：查结构层（句长节奏、均匀度、连接词密度），不查词表层（打词表）。
依据：句长方差是 AI 文本最强判别特征（多项研究共识）；有效改写必是结构重构，
换词无效（知网实测：同义词替换 55%→53%，结构重排→11%）。

用法：
    python3 wenqi.py <文件路径> [--title 标题]
    echo "文本" | python3 wenqi.py -

零依赖，纯标准库。
"""
import re
import sys
import statistics

# 句末标点（分句用），含中文顿挫
SENT_END = re.compile(r"(?<=[。！？；!?;])")
# 标点集合（算字数时剔除）
PUNCT = set("，。！？；：、「」『』（）《》〈〉【】…—·～,.!?;:()\"'“”‘’ \t")

# 连接词与套话（结构层密度的量化变量）
GLUE_WORDS = [
    "一方面", "另一方面", "综上所述", "值得注意的是", "总而言之", "总的来说",
    "首先", "其次", "最后", "此外", "因此", "然而", "但是", "而且",
    "不容忽视", "在当今", "随着", "让我们", "值得一提的是", "需要指出",
    "可以说", "无疑", "显而易见", "众所周知", "与此同时", "更重要的是",
]

# 评分阈值（v0 启发式，明确标注为粗版；绝对值待大样本校准）
STD_GOOD = 0.60   # 句长变异系数（标准差/平均）≥0.60 记满（文学级波动）
STD_BAD = 0.15    # ≤0.15 记零
GLUE_GOOD = 1.0   # 连接词密度 ≤1.0/百字 记满
GLUE_BAD = 4.0    # ≥4 记零


def split_sentences(text):
    parts = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts.extend(p for p in SENT_END.split(line) if p.strip())
    return parts


def clean_len(s):
    return len([c for c in s if c not in PUNCT])


def bar(n, scale=2, cap=40):
    return "█" * min(cap, max(1, round(n / scale)))


def soft(a, b, x):
    """x 在 a(满分) 与 b(零分) 之间的线性得分 0~1（a 可大于或小于 b）"""
    if a == b:
        return 1.0
    t = (x - b) / (a - b)
    return max(0.0, min(1.0, t))


def analyze(text):
    sents = split_sentences(text)
    lens = [clean_len(s) for s in sents]
    pairs = [(s, n) for s, n in zip(sents, lens) if n > 0]
    sents = [p[0] for p in pairs]
    lens = [p[1] for p in pairs]

    total_chars = sum(lens)
    r = {"n": len(lens), "lens": lens, "sents": sents, "total": total_chars}

    if len(lens) >= 2:
        r["avg"] = statistics.mean(lens)
        r["std"] = statistics.pstdev(lens)
        r["max"] = max(lens)
        r["min"] = min(lens)
        r["ratio"] = (r["max"] / r["min"]) if r["min"] > 0 else float("inf")
    else:
        r["avg"] = r["std"] = r["max"] = r["min"] = r["ratio"] = 0

    # 连续 5 句最平的一段（极差最小）
    r["flat"] = None
    if len(lens) >= 5:
        best = None
        for i in range(len(lens) - 4):
            w = lens[i:i + 5]
            spread = max(w) - min(w)
            if best is None or spread < best[0]:
                best = (spread, i, w)
        r["flat"] = best

    # 连接词密度（每百字）
    glue_hits = []
    for w in GLUE_WORDS:
        c = text.count(w)
        if c:
            glue_hits.append((w, c))
    glue_total = sum(c for _, c in glue_hits)
    r["glue_density"] = glue_total / total_chars * 100 if total_chars else 0
    r["glue_hits"] = sorted(glue_hits, key=lambda x: -x[1])

    # 破折号与分号密度
    r["dash"] = text.count("——")
    r["semi"] = text.count("；") + text.count(";")
    r["dash_den"] = r["dash"] / total_chars * 100 if total_chars else 0

    # 综合分（0-100，四项加权；v0 粗糙版）
    r["cv"] = (r["std"] / r["avg"]) if r["avg"] else 0
    s_std = soft(STD_GOOD, STD_BAD, r["cv"])
    short_count = sum(1 for n in lens if n <= 12)
    short_per200 = (short_count / total_chars * 200) if total_chars else 0
    s_short = min(1.0, short_per200)               # 每 200 字 ≥1 句短句 记满
    s_glue = soft(GLUE_GOOD, GLUE_BAD, r["glue_density"])
    s_flat = soft(10.0, 4.0, r["flat"][0]) if r["flat"] else 1.0  # 最平段极差 ≥10 记满、≤4 记零
    score = round(100 * (0.40 * s_std + 0.20 * s_short + 0.25 * s_glue + 0.15 * s_flat))
    r["score"] = score
    r["short_count"] = short_count
    r["short_per200"] = short_per200
    return r


def verdict(score, r):
    if score >= 80:
        return "「有气」——长短相间，读起来有呼吸。"
    if score >= 60:
        return "「气弱」——能读，但节奏偏平，缺短句的顿挫。"
    if score >= 40:
        return "「气滞」——句式均匀、套话偏多，有较重的机器感。"
    return "「无气」——句句等长、连接词铺路，是典型的生成腔。"


def render(path, title):
    text = open(path, encoding="utf-8").read()
    r = analyze(text)
    out = []
    out.append(f"玉尺 · 文气诊断：{title}")
    out.append("=" * 46)
    out.append("")
    out.append(f"总评 {r['score']}/100　{verdict(r['score'], r)}")
    out.append("")
    out.append(f"句数 {r['n']}　平均 {r['avg']:.0f} 字　标准差 {r['std']:.1f}"
               f"（变异系数 {r['cv']:.2f}）　最长 {r['max']} / 最短 {r['min']}"
               f"（比 {r['ratio']:.1f}）")
    if r["flat"]:
        sp, i, w = r["flat"]
        out.append(f"最平的五连句：第 {i+1} 到 {i+5} 句（长度 {min(w)}-{max(w)}，"
                   f"极差 {sp} 字）" + ("　← 机器感来源" if sp <= 8 else ""))
    out.append(f"短句（≤12 字）{r['short_count']} 句，每 200 字 {r['short_per200']:.1f} 句"
               "（研究基准：至少 1 句）")
    out.append("")
    out.append("句长节奏图（每格 2 字）")
    out.append("-" * 46)
    for i, (s, n) in enumerate(zip(r["sents"], r["lens"]), 1):
        head = s[:16] + ("…" if len(s) > 16 else "")
        out.append(f"{i:>2} {bar(n):<40} {n:>3}  {head}")
    out.append("-" * 46)
    out.append("")
    out.append(f"连接词/套话密度 {r['glue_density']:.1f} / 百字"
               f"（人类基准约 1.2，生成文本常见 4-5 以上）")
    if r["glue_hits"]:
        hits = "　".join(f"「{w}」×{c}" for w, c in r["glue_hits"][:8])
        out.append(f"命中：{hits}")
    out.append(f"破折号 {r['dash']} 处（{r['dash_den']:.1f}/百字）　分号 {r['semi']} 处")
    out.append("")
    out.append("怎么改（落到句，不给形容词）")
    out.append("-" * 46)
    tips = []
    if r["flat"] and r["flat"][0] <= 8:
        sp, i, w = r["flat"]
        j = i + w.index(max(w)) + 1
        tips.append(f"{i+1} 到 {i+5} 句长度都在 {min(w)}-{max(w)} 之间，"
                    f"挑第 {j} 句（最长那句）拆成两句，中间那句短到 10 字以内。")
    if r["short_per200"] < 0.8:
        tips.append("全篇短句太少。每 200 字里安插一句十来个字的短句，"
                    "让长句有落点。")
    if r["glue_density"] > 3:
        tips.append("连接词在替读者铺路。「因此」「然而」能删一半："
                    "把因果交给语序，把转折交给短句。")
    if r["dash_den"] > 1.5:
        tips.append("破折号密度偏高，它在替你做语气的活。"
                    "留最重的那一处，其余改成句号断句。")
    if not tips:
        tips.append("节奏健康。真要说：把最好的句子往前提一句，开头会更峻峭。")
    for i, t in enumerate(tips, 1):
        out.append(f"{i}. {t}")
    out.append("")
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    title = "样本"
    if "--title" in args:
        i = args.index("--title")
        title = args[i + 1]
        del args[i:i + 2]
    path = args[0]
    if path == "-":
        text = sys.stdin.read()
        tmp = "/tmp/wenqi_stdin.txt"
        open(tmp, "w", encoding="utf-8").write(text)
        path = tmp
    print(render(path, title))


if __name__ == "__main__":
    main()
