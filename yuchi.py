#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺 v1 —— 中文文章的节奏诊断

定位：查结构层（句长节奏、句内呼吸、均匀度、套话密度、篇章结构），
不查词表层（不打词表）；依据：句长节奏是 AI 文本最强判别特征（多项研究共识），
有效改写必是结构重构（知网实测：同义词替换 55%→53% 无效，结构重排→11%）。

五层指标：大句节奏 / 小句呼吸 / 密度 / 结构 / 段落。
阈值集中在 CONFIG，用 calibrate.py 按语料校准（当前为先验值）。
用法：
    python3 yuchi.py <文件路径> [--title 标题]
    echo "文本" | python3 yuchi.py -
零依赖，纯标准库。
"""
import os
import re
import statistics
import sys

SENT_END = re.compile(r"(?<=[。！？；!?;])")
CLAUSE_SPLIT = re.compile(r"[，、,；;]+")
PUNCT = set("，。！？；：、「」『』（）《》〈〉【】…—·～,.!?;:()\"'“”‘’ \t")

# 连接词与套话
GLUE_WORDS = [
    "一方面", "另一方面", "综上所述", "值得注意的是", "总而言之", "总的来说",
    "首先", "其次", "最后", "此外", "因此", "然而", "但是", "而且",
    "不容忽视", "在当今", "随着", "让我们", "值得一提的是", "需要指出",
    "可以说", "无疑", "显而易见", "众所周知", "与此同时", "更重要的是",
]
# 结构词：列举式 / 总结式
ENUM_WORDS = ["首先", "其次", "再次", "最后，", "第一，", "第二，", "第三，",
              "其一", "其二", "一方面", "另一方面", "此外", "与此同时", "除此之外"]
SUM_WORDS = ["综上所述", "总而言之", "由此可见", "总的来说", "总之", "让我们"]
# 虚词与空夸词：程度副词、空动词、无刻度的夸赞（具体化的反面指标）
VAGUE_WORDS = [
    "非常", "十分", "极其", "相当", "格外", "尤为", "堪称", "备受", "深受",
    "无比", "深深", "大大", "充分", "高度", "至关重要", "意义重大",
    "进一步提升", "全面优化", "不断完善", "显著提升", "有效改善",
]
# 统计词频前先剥离"引文"：成对引号（含直引号）里的内容与 markdown 引用块行。
# 引用与教学举例是别人/别处的话，不是作者的口吻，不该计入。
QUOTE_STRIP = re.compile(
    "[“][^“”]*[”]"
    "|[「][^「」]*[」]"
    "|[『][^『』]*[』]"
    '|["][^"]{1,120}["]'
)
QUOTE_BLOCK = re.compile(r"^[ \t]*> .*$", re.M)

# 评分阈值（先验值，待 calibrate.py 按语料校准）：每项 [满分点, 零点]
CONFIG = {
    # 满分点≈人类语料 p75、零点≈AI 语料中位（2026-10-09 按分位数分布重标）
    "sent_cv": [0.55, 0.18],       # 大句变异系数：越高越好
    "clause_cv": [0.55, 0.30],     # 小句变异系数：越高越好
    "flat_run": [0.20, 0.55],      # 最长平滑段占比：越低越好
    "short_per200": [1.5, 0.2],    # 每 200 字短句数：越多越好
    "glue_density": [0.5, 3.0],    # 套话密度 / 百字：越低越好
    "dash_density": [0.6, 3.0],    # 破折号密度 / 百字：越低越好
    "vague_density": [0.2, 1.0],   # 虚词密度 / 百字：越低越好
    "struct_score": [0.0, 6.0],    # 列举词 + 2×总结词：越低越好
    "para_cv": [0.58, 0.20],       # 段落变异系数：越高越好
}

# 综合权重（四层）
WEIGHTS = {"rhythm": 0.40, "density": 0.25, "struct": 0.20, "para": 0.15}


def hanzi(s):
    return len([c for c in s if c not in PUNCT])


def split_paragraphs(text):
    # 中文写作与粘贴场景中，一行即一段；# 开头行视为注释（语料文件头）。
    return [l.strip() for l in text.split("\n")
            if l.strip() and not l.strip().startswith("#")]


def split_sentences(paras):
    out = []
    for p in paras:
        for line in p.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.extend(s for s in SENT_END.split(line) if s.strip())
    return out


STRUCT_ONLY = set(GLUE_WORDS) | set(ENUM_WORDS) | set(SUM_WORDS)


def split_clauses(sents):
    """切小句；纯结构词小句（「一方面」「首先」这类）剔除，
    它们是被逗号切出来的标记，不是句内的呼吸。"""
    out = []
    for s in sents:
        for c in CLAUSE_SPLIT.split(s):
            c = c.strip()
            if not c:
                continue
            bare = c.strip("。！？；：、，,.;: ")
            if bare in STRUCT_ONLY and hanzi(c) <= 5:
                continue
            out.append(c)
    return out


def soft(a, b, x):
    """x 在满分点 a 与零点 b 之间线性取值，返回 0~1（a 可大于或小于 b）。"""
    if a == b:
        return 1.0
    return max(0.0, min(1.0, (x - b) / (a - b)))


def cv(lst):
    if len(lst) < 2:
        return 0.0
    m = statistics.mean(lst)
    return statistics.pstdev(lst) / m if m else 0.0


def longest_flat_run(lens, spread=8):
    """最长的'平滑段'：连续长度极差 ≤ spread 的最长片段（占全长的比例）。"""
    n = len(lens)
    if n < 3:
        return 0, 0.0
    best_len, best_i = 0, 0
    for i in range(n):
        lo = hi = lens[i]
        j = i
        while j < n and max(hi, lens[j]) - min(lo, lens[j]) <= spread:
            hi, lo = max(hi, lens[j]), min(lo, lens[j])
            j += 1
        if j - i > best_len:
            best_len, best_i = j - i, i
    return best_len, best_len / n


def analyze(text):
    paras = split_paragraphs(text)
    all_text = "\n".join(paras)
    stat_text = QUOTE_BLOCK.sub("", QUOTE_STRIP.sub("", all_text))
    sents = split_sentences(paras)
    lens = [hanzi(s) for s in sents]
    pairs = [(s, n) for s, n in zip(sents, lens) if n > 0]
    sents = [p[0] for p in pairs]
    lens = [p[1] for p in pairs]

    clauses = split_clauses(sents)
    clens = [hanzi(c) for c in clauses]
    clens = [n for n in clens if n > 0]

    total = sum(lens)
    r = {"n": len(lens), "lens": lens, "sents": sents, "total": total,
         "n_clause": len(clens), "clens": clens}

    r["avg"] = statistics.mean(lens) if lens else 0
    r["std"] = statistics.pstdev(lens) if len(lens) >= 2 else 0
    r["cv"] = cv(lens)
    r["max"] = max(lens) if lens else 0
    r["min"] = min(lens) if lens else 0
    r["ratio"] = (r["max"] / r["min"]) if r["min"] else 0

    r["clause_cv"] = cv(clens)
    r["clause_avg"] = statistics.mean(clens) if clens else 0

    flat_n, flat_pct = longest_flat_run(lens)
    r["flat_n"] = flat_n
    r["flat_pct"] = flat_pct

    r["short_count"] = sum(1 for n in lens if n <= 12)
    r["short_per200"] = (r["short_count"] / total * 200) if total else 0

    glue_hits = [(w, stat_text.count(w)) for w in GLUE_WORDS if stat_text.count(w)]
    glue_total = sum(c for _, c in glue_hits)
    r["glue_density"] = (glue_total / total * 100) if total else 0
    r["glue_hits"] = sorted(glue_hits, key=lambda x: -x[1])

    # "十分"单独走正则：排除"四十分钟"这类跨词误匹配（词表法的已知假阳性）
    vague_total = sum(stat_text.count(w) for w in VAGUE_WORDS if w != "十分")
    vague_total += len(re.findall(r"十分(?!钟)", stat_text))
    r["vague_total"] = vague_total
    r["vague_density"] = (vague_total / total * 100) if total else 0

    enum_n = sum(stat_text.count(w) for w in ENUM_WORDS)
    sum_n = sum(stat_text.count(w) for w in SUM_WORDS)
    r["enum_n"], r["sum_n"] = enum_n, sum_n
    r["struct_raw"] = enum_n + 2 * sum_n
    if enum_n >= 2 and sum_n >= 1:
        r["struct"] = "总分总（清单式）"
    elif enum_n >= 2:
        r["struct"] = "清单式列举"
    elif sum_n >= 1:
        r["struct"] = "结尾总结式"
    else:
        r["struct"] = "自然推进"

    r["dash"] = stat_text.count("——")
    r["dash_density"] = (r["dash"] / total * 100) if total else 0
    r["semi"] = stat_text.count("；") + stat_text.count(";")

    plens = [hanzi(p) for p in paras]
    r["n_para"] = len(paras)
    r["para_lens"] = plens
    r["para_cv"] = cv(plens) if len(plens) >= 3 else None

    # 四层得分
    s_rhythm = (0.40 * soft(*CONFIG["sent_cv"], r["cv"])
                + 0.25 * soft(*CONFIG["clause_cv"], r["clause_cv"])
                + 0.15 * soft(CONFIG["flat_run"][0], CONFIG["flat_run"][1], r["flat_pct"])
                + 0.20 * soft(*CONFIG["short_per200"], r["short_per200"]))
    s_density = (0.45 * soft(*CONFIG["glue_density"], r["glue_density"])
                 + 0.20 * soft(*CONFIG["dash_density"], r["dash_density"])
                 + 0.35 * soft(*CONFIG["vague_density"], r["vague_density"]))
    s_struct = soft(*CONFIG["struct_score"], r["struct_raw"])
    s_para = soft(*CONFIG["para_cv"], r["para_cv"]) if r["para_cv"] is not None else 0.5

    r["s_rhythm"], r["s_density"] = s_rhythm, s_density
    r["s_struct"], r["s_para"] = s_struct, s_para
    score = round(100 * (WEIGHTS["rhythm"] * s_rhythm + WEIGHTS["density"] * s_density
                         + WEIGHTS["struct"] * s_struct + WEIGHTS["para"] * s_para))
    r["score"] = max(0, min(100, score))
    return r


def verdict(score):
    if score >= 80:
        return "「有气」——长短相间，读起来有呼吸。"
    if score >= 60:
        return "「气弱」——能读，但节奏偏平，缺短句的顿挫。"
    if score >= 40:
        return "「气滞」——句式均匀、套话偏多，有较重的机器感。"
    return "「无气」——句句等长、连接词铺路，是典型的生成腔。"


def bar(n, scale=2, cap=40):
    return "█" * min(cap, max(1, round(n / scale)))


def render(path, title):
    text = open(path, encoding="utf-8").read()
    r = analyze(text)
    out = []
    out.append(f"玉尺 · 文气诊断：{title}")
    out.append("=" * 46)
    out.append("")
    out.append(f"总评 {r['score']}/100　{verdict(r['score'])}")
    out.append("")
    out.append("【节奏层】")
    out.append(f"  大句 {r['n']} 句　平均 {r['avg']:.0f} 字　变异系数 {r['cv']:.2f}"
               f"　最长 {r['max']} / 最短 {r['min']}")
    out.append(f"  小句 {r['n_clause']} 句　平均 {r['clause_avg']:.0f} 字"
               f"　变异系数 {r['clause_cv']:.2f}（句内呼吸）")
    out.append(f"  最长平滑段 {r['flat_n']} 句（占 {r['flat_pct']*100:.0f}%，越短越好）")
    out.append(f"  短句（≤12 字）{r['short_count']} 句　每 200 字 {r['short_per200']:.1f} 句")
    out.append("")
    out.append("  句长节奏图（每格 2 字）")
    for i, (s, n) in enumerate(zip(r["sents"], r["lens"]), 1):
        head = s[:16] + ("…" if len(s) > 16 else "")
        out.append(f"  {i:>2} {bar(n):<40} {n:>3}  {head}")
    out.append("")
    out.append("【密度层】")
    out.append(f"  套话与连接词 {r['glue_density']:.1f} / 百字"
               f"（人类基准约 1.2，生成文本常见 4 以上）")
    if r["glue_hits"]:
        hits = "　".join(f"「{w}」×{c}" for w, c in r["glue_hits"][:8])
        out.append(f"  命中：{hits}")
    out.append(f"  破折号 {r['dash']} 处（{r['dash_density']:.1f}/百字）　分号 {r['semi']} 处")
    out.append(f"  虚词与空夸词 {r['vague_density']:.1f} / 百字"
               f"（程度副词与空动词，越多越虚）")
    out.append("")
    out.append("【结构层】")
    out.append(f"  列举词 {r['enum_n']} 处　总结词 {r['sum_n']} 处　"
               f"判定：{r['struct']}")
    out.append("")
    out.append("【段落层】")
    if r["para_cv"] is not None:
        out.append(f"  {r['n_para']} 段　段落长度变异系数 {r['para_cv']:.2f}"
                   f"（越参差越像人写）")
    else:
        out.append("  单段文本，段落层未测（多段文章才有此项）")
    out.append("")
    out.append("【改法（落到句，不给形容词）】")
    tips = []
    if r["flat_pct"] >= 0.4:
        tips.append(f"全篇有一段 {r['flat_n']} 句的平滑区，长度变化不到 8 字。"
                    "挑其中最长的两句动手：一句拆成两句，一句砍到十字以内。")
    if r["cv"] < 0.30:
        tips.append("大句长短太齐。在长句群中间安插短句，让读者有换气的地方。")
    if r["clause_cv"] < 0.35:
        tips.append("句内的逗号也走得均匀。长句内部掺进三五个字的短顿，"
                    "呼吸就有了起伏。")
    if r["glue_density"] > 3:
        tips.append("连接词在替读者铺路。「因此」「然而」删一半，"
                    "因果交给语序，转折交给短句。")
    if r["struct_raw"] >= 2:
        tips.append(f"结构的骨架露出来了（{r['struct']}）。把「首先其次最后」拆掉，"
                    "让每段接着上一段的意思往下走，而不是平铺开清单。")
    if r["dash_density"] > 1.5:
        tips.append("破折号在替你做语气的活。留最重的一处，其余改成句号。")
    if r["short_per200"] < 0.8:
        tips.append("短句太少。每 200 字安插一句十来个字的短句，让长句有落点。")
    if not tips:
        tips.append("节奏健康。真要说：把最好的句子往前提一句，开头会更峻峭。")
    for i, t in enumerate(tips, 1):
        out.append(f"  {i}. {t}")
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
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".stdin_tmp.txt")
        open(tmp, "w", encoding="utf-8").write(text)
        path = tmp
    print(render(path, title))


if __name__ == "__main__":
    main()
