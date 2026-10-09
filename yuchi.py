#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺 v1 —— 中文文章的节奏诊断

定位：查结构层（句长节奏、句内呼吸、均匀度、套话密度、篇章结构），
不查词表层（不打词表）；依据：句长节奏是 AI 文本最强判别特征（多项研究共识），
有效改写必是结构重构（知网实测：同义词替换 55%→53% 无效，结构重排→11%）。

五层指标：大句节奏 / 小句呼吸 / 密度 / 结构 / 段落。
阈值集中在 CONFIG，用 calibrate.py 按语料校准（当前为先验值）。
用法：
    python3 yuchi.py <文件路径> [--title 标题] [--poem]
        （--poem 走诗模式；--ci 词牌名 走词模式：给谱并对谱，文件可省略）
    echo "文本" | python3 yuchi.py -
零依赖，纯标准库。
"""
import json
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
    """数汉字（标点、数字、英文字母都不计）。"""
    return sum(1 for c in s if "一" <= c <= "鿿")


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


PARA_END = set("。！？；…”’」』）)")


def split_paragraphs(text):
    # 一行即一段；但行尾没有句末标点的行与下一行接续——
    # 网页复制来的硬换行（同一段被折成多行）不该被数成多个段落。
    lines = [l.strip() for l in text.split("\n")
             if l.strip() and not l.strip().startswith("#")]
    paras, buf = [], ""
    for l in lines:
        buf = buf + l if buf else l
        if l[-1] in PARA_END:
            paras.append(buf)
            buf = ""
    if buf:
        paras.append(buf)
    return paras


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


# ================= 诗模式 =================
# 诗按行读：行就是它的句子。诗模式给“体检单”为主、不打总分——
# 诗的评判太主观，尺子只报数，判断留给读者。

HERE = os.path.dirname(os.path.abspath(__file__))
_TONE_TABLE = None
_RHYME_INDEX = None


def load_tone_table():
    """字→平仄（平水韵体系）。数据来源：chinese_word_rhyme（MIT），见 data/README.md"""
    global _TONE_TABLE
    if _TONE_TABLE is None:
        try:
            _TONE_TABLE = json.loads(read_text(os.path.join(HERE, "data", "Word_Tune.json")))
        except Exception:
            _TONE_TABLE = {}
    return _TONE_TABLE


def load_rhyme_index():
    """字→平水韵韵部的反向索引"""
    global _RHYME_INDEX
    if _RHYME_INDEX is None:
        idx = {}
        try:
            d = json.loads(read_text(os.path.join(HERE, "data", "Pingshui_Rhyme.json")))
            for _sheng, bu in d.items():
                for yun, chars in bu.items():
                    for ch in chars:
                        idx.setdefault(ch, set()).add(yun)
        except Exception:
            idx = {}
        _RHYME_INDEX = idx
    return _RHYME_INDEX


def tone_of(ch):
    t = load_tone_table().get(ch)
    if t == "平":
        return "平"
    if t == "仄":
        return "仄"
    if t == "多":
        return "通"
    return "？"


def is_regulated(lens):
    """疑似近体诗：全 5 言或全 7 言，且行数为 4 的倍数"""
    return bool(lens) and len(set(lens)) == 1 and lens[0] in (5, 7) and len(lens) % 4 == 0


def annotate_tones(lines):
    out = []
    for l in lines:
        out.append("".join(tone_of(c) for c in l if "一" <= c <= "鿿"))
    return out


def tone_notes(seq):
    """读感提示：连续四个以上的同声调"""
    notes = []
    n, i = len(seq), 0
    while i < n:
        j = i
        while j < n and seq[j] == seq[i]:
            j += 1
        run, ch = j - i, seq[i]
        if ch in "平仄" and run >= 4:
            notes.append(f"第 {i+1} 到 {j} 字连着 {run} 个{ch}声"
                         + ("，念起来发紧" if ch == "仄" else "，念起来发飘"))
        i = j
    return notes


def analyze_poem(text):
    lines = [l.strip() for l in text.split("\n")
             if l.strip() and not l.strip().startswith("#")]
    lens = [hanzi(l) for l in lines]
    pairs = [(l, n) for l, n in zip(lines, lens) if n > 0]
    lines = [p[0] for p in pairs]
    lens = [p[1] for p in pairs]

    r = {"n": len(lens), "lens": lens, "lines": lines}
    r["avg"] = statistics.mean(lens) if lens else 0
    r["cv"] = cv(lens)
    r["max"] = max(lens) if lens else 0
    r["min"] = min(lens) if lens else 0

    flat_run, cur = 1, 1
    for i in range(1, len(lens)):
        cur = cur + 1 if abs(lens[i] - lens[i - 1]) <= 1 else 1
        flat_run = max(flat_run, cur)
    r["flat_run"] = flat_run if lens else 0

    r["short"] = sum(1 for n in lens if n <= 6)

    tails = []
    for l in lines:
        s = l.rstrip("，。！？；：、,.!?;:…— ")
        if s:
            tails.append(s[-1])
    r["tails"] = tails
    r["adj_rep"] = sum(1 for i in range(1, len(tails)) if tails[i] == tails[i - 1])

    sections = []
    for sec in re.split(r"\n\s*\n", text):
        n = len([l for l in sec.split("\n")
                 if l.strip() and not l.strip().startswith("#")])
        if n:
            sections.append(n)
    r["sections"] = sections

    issues = []
    reg = is_regulated(lens)  # 近体诗每句等长是格律使然，豆腐块与“行长太平”不适用
    if r["flat_run"] >= 3 and not reg:
        issues.append(f"连续 {r['flat_run']} 行长度几乎一样，像豆腐块。"
                      "挑一行动手：要么砍掉一半，要么拉长。")
    if r["n"] >= 5 and r["cv"] < 0.28 and not reg:
        issues.append("行长太平，全诗缺少起伏。自由诗的自由，一半在行长上。")
    if r["adj_rep"] >= 2:
        issues.append(f"有 {r['adj_rep']} 处相邻行行尾同字，读起来像打嗝；"
                      "除非是刻意的复沓，改掉。")
    if r["n"] >= 6 and r["short"] == 0:
        issues.append("没有一行短过七字。给诗留几口气短的。")
    r["issues"] = issues
    return r


def render_poem(path, title):
    text = read_text(path)
    r = analyze_poem(text)
    out = []
    out.append(f"玉尺 · 诗诊：{title}")
    out.append("=" * 46)
    out.append("")
    out.append(f"行数 {r['n']}　节 {len(r['sections'])}（各节行数 {'/'.join(map(str, r['sections']))}）")
    out.append(f"平均行长 {r['avg']:.0f} 字　变异系数 {r['cv']:.2f}"
               f"　最长 {r['max']} / 最短 {r['min']}　短行（≤6 字）{r['short']} 行")
    out.append("")
    out.append("行长图（每格 1 字）")
    out.append("-" * 46)
    for i, (l, n) in enumerate(zip(r["lines"], r["lens"]), 1):
        head = l[:20] + ("…" if len(l) > 20 else "")
        out.append(f"{i:>2} {bar(n, scale=1):<40} {n:>3}  {head}")
    out.append("-" * 46)
    out.append("")
    out.append(f"行尾：{'／'.join(r['tails'])}")
    out.append(f"相邻同尾 {r['adj_rep']} 处")
    out.append("")

    extra_notes = []
    if is_regulated(r["lens"]):
        seqs = annotate_tones(r["lines"])
        out.append("平仄标注（平／仄／通＝多音；？＝韵表未收）")
        out.append("-" * 46)
        for i, (l, seq) in enumerate(zip(r["lines"], seqs), 1):
            out.append(f"{i:>2} {seq}  {l}")
        out.append("")
        for i, seq in enumerate(seqs, 1):
            for nt in tone_notes(seq):
                extra_notes.append(f"第 {i} 行：{nt}")
        rhyme_idx = load_rhyme_index()
        yun_list = []
        for i in range(2, len(r["lines"]) + 1, 2):
            lastch = r["lines"][i - 1][-1]
            yuns = sorted(rhyme_idx.get(lastch, []))
            yun_list.append((i, lastch, "／".join(yuns) if yuns else "韵表未收"))
        out.append("韵脚（偶数句）")
        out.append("-" * 46)
        for i, ch, yun in yun_list:
            out.append(f"第 {i} 句尾「{ch}」：{yun}")
        same = {yun for _, _, yun in yun_list if yun != "韵表未收"}
        if len(same) > 1:
            extra_notes.append("偶数句的韵脚不在同一韵部。近体诗偶句要押韵，看看要不要调。")
        out.append("")
    out.append("体检（诗的判断留给你，尺子只报数）")
    out.append("-" * 46)
    all_notes = r["issues"] + extra_notes
    if all_notes:
        for i, t in enumerate(all_notes, 1):
            out.append(f"{i}. {t}")
    else:
        out.append("没查出明显的问题。真要说：把最重的那一行往前提一提，看看气顺不顺。")
    out.append("")
    return "\n".join(out)


# ================= 词模式 =================
# 词是照谱填的：先给谱（逐字平仄与句读韵位），再对谱（逐字核对）。
# 谱与韵书数据来自开源词谱（见 data/README.md）。

_CI_TUNES = None
_CI_WORD = None


def load_ci_tunes():
    global _CI_TUNES
    if _CI_TUNES is None:
        try:
            _CI_TUNES = json.loads(read_text(os.path.join(HERE, "data", "Ci_Tunes.json")))
        except Exception:
            _CI_TUNES = {}
    return _CI_TUNES


def load_ci_word():
    global _CI_WORD
    if _CI_WORD is None:
        try:
            _CI_WORD = json.loads(read_text(os.path.join(HERE, "data", "Ci_Word_Tune.json")))
        except Exception:
            _CI_WORD = {}
    return _CI_WORD


def ci_tone_of(ch):
    w = load_ci_word().get(ch)
    if not w:
        return "？", None
    return {"平": "平", "仄": "仄", "多": "通"}.get(w.get("tune"), "？"), w.get("rhyme")


def render_ci(path, title, ci_name):
    tunes = load_ci_tunes()
    if not tunes:
        return "词谱数据未就位（data/Ci_Tunes.json，见 data/README.md）。"
    if ci_name not in tunes:
        cand = [k for k in tunes if ci_name in k or k in ci_name]
        if cand:
            return f"没有「{ci_name}」这个词牌。是不是想找：{'、'.join(cand[:8])}？"
        return f"词谱库里没有「{ci_name}」（共 {len(tunes)} 个词牌）。"

    entry = tunes[ci_name]
    formats = entry["formats"]
    text = read_text(path) if path else ""
    text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("#"))
    user_han = [c for c in text if "一" <= c <= "鿿"]

    out = []
    out.append(f"玉尺 · 词诊：{title}（词牌：{ci_name}）")
    out.append("=" * 46)
    out.append("")
    out.append(f"该词牌共 {len(formats)} 体。")

    match = None
    for idx, f in enumerate(formats, 1):
        if user_han and len(f["tunes"]) == len(user_han):
            match = (idx, f)
            break

    if match:
        idx, f = match
        out.append(f"你的词 {len(user_han)} 字，对上第 {idx} 体：「{f['sketch']}」"
                   f"（例作：{f.get('author', '前人')}）")
    elif user_han:
        sizes = "、".join(str(len(f["tunes"])) + "字" for f in formats[:8])
        out.append(f"你的词 {len(user_han)} 字，没对上现成的体（各体字数：{sizes}"
                   + ("…" if len(formats) > 8 else "") + "）。")
    out.append("")

    spec = (match[1] if match else formats[0])["tunes"]
    # 谱
    out.append("谱（平／仄／中＝可平可仄；行末为句读与韵位）")
    out.append("-" * 46)
    seg = []
    for i, sp in enumerate(spec, 1):
        seg.append(sp["tune"])
        if sp.get("rhythm") in ("句", "韵") or i == len(spec):
            out.append("".join(seg))
            seg = []
    out.append("")

    if match:
        # 对谱
        out.append("对谱（你的字＋核对：✓合 ✗不合 ·可平可仄）")
        out.append("-" * 46)
        rows, bad, seg = [], 0, []
        for i, (sp, ch) in enumerate(zip(spec, user_han), 1):
            expect = sp["tune"]
            actual, _r = ci_tone_of(ch)
            ok = expect == "中" or actual == "通" or actual == expect
            if not ok:
                bad += 1
            mark = "·" if expect == "中" else ("✓" if ok else "✗")
            rows.append((i, ch, expect, actual, mark))
            seg.append(f"{ch}{mark}")
            if sp.get("rhythm") in ("句", "韵") or i == len(rows) == len(spec):
                out.append("".join(seg))
                seg = []
        out.append("")
        out.append(f"合计 {len(rows)} 字，不合 {bad} 处（谱标“中”或你的字为多音时不计）。")
        # 逐处列出不合
        bads = [(i, ch, e, a) for i, ch, e, a, m in rows if m == "✗"]
        if bads:
            out.append("")
            out.append("不合处逐条：")
            for i, ch, e, a in bads[:12]:
                out.append(f"  第 {i} 字「{ch}」：谱要{e}声，字是{a}声。")
            if len(bads) > 12:
                out.append(f"  （另有 {len(bads) - 12} 处，同上自行核对。）")
        # 韵脚（谱标“韵”位）
        yun_pos = [i for i, sp in enumerate(spec, 1) if sp.get("rhythm") == "韵"]
        if yun_pos:
            out.append("")
            out.append("韵脚（谱标“韵”位的字）")
            out.append("-" * 46)
            yl = []
            for p in yun_pos:
                if p <= len(user_han):
                    ch = user_han[p - 1]
                    _t, rhyme = ci_tone_of(ch)
                    yl.append((p, ch, rhyme or "词韵表未收"))
            for p, ch, rhyme in yl:
                out.append(f"第 {p} 字「{ch}」：{rhyme}")
            same = {r for _, _, r in yl if r != "词韵表未收"}
            if len(same) > 1:
                out.append("韵脚不在同一部（词林正韵）。词要按词牌的韵位押韵，看看要不要调。")
    out.append("")
    desc = entry.get("desc", "")
    if desc:
        out.append("词牌小记（节选自开源词谱）")
        out.append("-" * 46)
        out.append(desc[:180] + ("…" if len(desc) > 180 else ""))
    out.append("")
    return "\n".join(out)


# ================= 联模式 =================
# 对联验三样：字数相等、仄起平收、逐位平仄相反（同位同字另记）。

def render_lian(path, title):
    text = read_text(path) if path else ""
    text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("#"))
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2:
        return "联诊要两行：第一行上联，第二行下联。"

    up, down = lines[0], lines[1]
    cu = [c for c in up if "一" <= c <= "鿿"]
    cd = [c for c in down if "一" <= c <= "鿿"]
    out = []
    out.append(f"玉尺 · 联诊：{title}")
    out.append("=" * 46)
    out.append("")

    ok_all = True
    if len(cu) != len(cd):
        ok_all = False
        out.append(f"① 字数：上联 {len(cu)} 字，下联 {len(cd)} 字——对联要求相等。")
    else:
        out.append(f"① 字数：各 {len(cu)} 字，相等。")

    tu = tone_of(cu[-1]) if cu else "？"
    td = tone_of(cd[-1]) if cd else "？"
    if tu == "仄" and td == "平":
        out.append(f"② 仄起平收：上联尾「{cu[-1]}」{tu}，下联尾「{cd[-1]}」{td}，合格。")
    else:
        ok_all = False
        out.append(f"② 仄起平收：上联尾「{cu[-1]}」{tu}、下联尾「{cd[-1]}」{td}"
                   f"——规矩是上联收仄、下联收平，看看要不要调。")

    n = min(len(cu), len(cd))
    bad, rows = [], []
    for i in range(n):
        t1, t2 = tone_of(cu[i]), tone_of(cd[i])
        same_char = cu[i] == cd[i]
        if t1 in "平仄" and t2 in "平仄":
            opposite = t1 != t2
        else:
            opposite = None  # 有"通"或"？"，不计
        if same_char:
            mark = "＝"
            bad.append((i + 1, cu[i], t1, cd[i], t2, "同位同字"))
        elif opposite is False:
            mark = "✗"
            bad.append((i + 1, cu[i], t1, cd[i], t2, "平仄未相反"))
        elif opposite is True:
            mark = "✓"
        else:
            mark = "·"
        rows.append(f"{cu[i] if i < len(cu) else '·'}{t1} {cd[i] if i < len(cd) else '·'}{t2} {mark}")
    out.append(f"③ 逐位相反（✓对 ✗未反 ＝同位同字 ·未计）")
    out.append("-" * 46)
    seg = []
    for r in rows:
        seg.append(r)
        if len(seg) == 4:
            out.append("　".join(seg))
            seg = []
    if seg:
        out.append("　".join(seg))
    if bad:
        ok_all = False
        out.append("")
        out.append("待看处：")
        for i, a, ta, b, tb, why in bad[:10]:
            out.append(f"  第 {i} 位：「{a}」（{ta}）对「{b}」（{tb}）——{why}")
    out.append("")
    if ok_all:
        out.append("三条都过。真要说：对仗的讲究（词性相对、结构相称）在笔墨里，玉尺只验平仄这一层。")
    else:
        out.append("上面对应处逐条看。联的门道一半在平仄，一半在词性相对——平仄过了，再读一遍词性。")
    out.append("")
    return "\n".join(out)


# 人类参考样本的分数分布（升序，20 段真人语料；语料或阈值变动后跑 calibrate.py 重取）
PERCENTILE_TABLE = [53, 54, 58, 58, 66, 71, 72, 74, 75, 76,
                    77, 79, 79, 79, 80, 86, 87, 92, 92, 97]


def percentile_of(score):
    below = sum(1 for v in PERCENTILE_TABLE if v < score)
    equal = sum(1 for v in PERCENTILE_TABLE if v == score)
    return round((below + 0.5 * equal) / len(PERCENTILE_TABLE) * 100)


def render_json(r):
    out = {
        "score": r["score"],
        "percentile": percentile_of(r["score"]),
        "verdict": verdict(r["score"]),
        "layers": {
            "rhythm": round(r["s_rhythm"], 3),
            "density": round(r["s_density"], 3),
            "struct": round(r["s_struct"], 3),
            "para": round(r["s_para"], 3),
        },
        "metrics": {
            "sents": r["n"], "avg_len": round(r["avg"], 1),
            "sent_cv": round(r["cv"], 3), "clause_cv": round(r["clause_cv"], 3),
            "flat_n": r["flat_n"], "flat_pct": round(r["flat_pct"], 3),
            "short_per200": round(r["short_per200"], 2),
            "glue_density": round(r["glue_density"], 2),
            "vague_density": round(r["vague_density"], 2),
            "dash": r["dash"], "struct_raw": r["struct_raw"], "struct": r["struct"],
            "n_para": r["n_para"],
            "para_cv": round(r["para_cv"], 3) if r["para_cv"] is not None else None,
        },
        "glue_hits": [{"word": w, "count": c} for w, c in r["glue_hits"]],
        "sentences": [{"text": s, "len": n} for s, n in zip(r["sents"], r["lens"])],
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


def render_batch(files):
    """批量对照表：多文件一屏对照（改前/改后最常用）。"""
    heads = ("文件", "分数", "句数", "大句CV", "套话/百字", "结构")
    rows = []
    for f in files:
        try:
            r = analyze(read_text(f))
            rows.append((os.path.basename(f), str(r["score"]), str(r["n"]),
                         f"{r['cv']:.2f}", f"{r['glue_density']:.1f}", r["struct"]))
        except Exception:
            rows.append((os.path.basename(f), "读取失败", "—", "—", "—", "—"))

    def w(s):
        return sum(2 if "一" <= c <= "鿿" else 1 for c in str(s))

    widths = [max([w(heads[i])] + [w(r[i]) for r in rows]) for i in range(len(heads))]

    def fmt(row):
        return "  ".join(str(c) + " " * (widths[i] - w(c)) for i, c in enumerate(row))

    lines = [fmt(heads), "-" * (sum(widths) + 2 * (len(widths) - 1))]
    lines += [fmt(r) for r in rows]
    return "\n".join(lines)


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
    text = read_text(path)
    n_hz = hanzi(text)
    if n_hz < 50:
        return "文本太短（不足五十个汉字），节奏量不出来——多写几段再量。"
    small_sample = n_hz < 100
    r = analyze(text)
    out = []
    out.append(f"玉尺 · 文气诊断：{title}")
    out.append("=" * 46)
    out.append("")
    out.append(f"总评 {r['score']}/100（约超过 {percentile_of(r['score'])}% 人类样本）"
               f"　{verdict(r['score'])}")
    if small_sample:
        out.append("（样本量偏小——不足百字，分数只作参考）")
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
    poem = "--poem" in args
    if poem:
        args.remove("--poem")
    ci = None
    if "--ci" in args:
        i = args.index("--ci")
        ci = args[i + 1]
        del args[i:i + 2]
    lian = "--lian" in args
    if lian:
        args.remove("--lian")
    json_out = "--json" in args
    if json_out:
        args.remove("--json")
    if not args and not ci:
        print(__doc__)
        sys.exit(1)
    path = args[0] if args else ""
    if path == "-":
        text = sys.stdin.read()
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".stdin_tmp.txt")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        path = tmp
    if "--batch" in args:
        args.remove("--batch")
        targets = []
        for a in args:
            if os.path.isdir(a):
                targets += [os.path.join(a, x) for x in sorted(os.listdir(a))
                            if x.endswith(".txt") and not x.startswith("_")]
            elif a:
                targets.append(a)
        print(render_batch(targets))
        return
    if ci:
        print(render_ci(path, title, ci))
    elif lian:
        print(render_lian(path, title))
    elif poem:
        print(render_poem(path, title))
    elif json_out:
        text = read_text(path)
        if hanzi(text) < 50:
            print(json.dumps({"error": "文本太短（不足五十个汉字），节奏量不出来"},
                             ensure_ascii=False))
        else:
            print(render_json(analyze(text)))
    else:
        print(render(path, title))


if __name__ == "__main__":
    main()
