#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玉尺内容门禁 —— 发布与提交前的自动检查

检查项：
1. 必需文件齐全
2. AI 腔/占位符（剥离引文后检查，讲反例的地方不误伤）
3. 红线危险词（对外不许出现的字眼）
4. 交叉引用断链（references/XX 引用目标存在）
5. SKILL.md frontmatter
运行：python3 check.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(HERE, "references")

REQUIRED = [
    "README.md", "SKILL.md", "LICENSE", "LICENSE-CODE", "CHANGELOG.md", "MAINTAINING.md",
    "web/index.html", "yuchi.py",
    "data/Word_Tune.json", "data/Pingshui_Rhyme.json",
    "data/Ci_Word_Tune.json", "data/Ci_Tunes.json",
    "references/01-节奏.md", "references/02-密度.md", "references/03-结构.md",
    "references/04-具体.md", "references/05-改稿流程.md", "references/06-自检清单.md",
    "references/07-验证与依据.md", "references/08-文体.md", "references/09-腔调.md",
    "references/10-AI协作.md", "references/11-开头与结尾.md", "references/12-练习.md",
]

AI_PATTERNS = ["一方面", "综上所述", "值得注意的是", "总而言之", "[待补充]", "TODO", "TBD"]
# 红线词：对外材料任何位置都不许出现（本项目红线声明自身按"不承诺检测数字"表述，不含下列直接字眼）
RED_WORDS = ["降 AI 率", "降AI率", "绕过检测", "骗过检测", "过检测", "过查重", "规避检测"]

QUOTE_STRIP = re.compile(
    "[“][^“”]*[”]|[「][^「」]*[」]|[『][^『』]*[』]|[\"][^\"]{1,120}[\"]"
)
QUOTE_BLOCK = re.compile(r"^[ \t]*> .*$", re.M)
REF_LINK = re.compile(r"references/(\d{2}-[^）\s、，。；\"”]+?)\.md|`(\d{2}-[^`]+?)`")


def strip_quotes(text):
    return QUOTE_BLOCK.sub("", QUOTE_STRIP.sub("", text))


def main():
    errors, warnings = [], []

    for rel in REQUIRED:
        if not os.path.exists(os.path.join(HERE, rel)):
            errors.append(f"[缺件] {rel}")

    docs = ["README.md", "SKILL.md", "MAINTAINING.md", "CHANGELOG.md",
            "提案-玉尺项目.md", "web/index.html"]
    if os.path.isdir(REFS):
        docs += [f"references/{f}" for f in sorted(os.listdir(REFS)) if f.endswith(".md")]

    for rel in docs:
        path = os.path.join(HERE, rel)
        if not os.path.exists(path):
            continue
        raw = open(path, encoding="utf-8").read()
        stat = strip_quotes(raw)
        # web/index.html 含词表定义与演示样本（功能性文本），只查红线词，不查 AI 腔
        if rel != "web/index.html":
            for pat in AI_PATTERNS:
                for i, line in enumerate(stat.splitlines(), 1):
                    if pat in line:
                        errors.append(f"[AI腔/占位符] {rel}:{i} 命中「{pat}」")
        for pat in RED_WORDS:
            if pat in raw:
                errors.append(f"[红线危险词] {rel} 命中「{pat}」")
        # 交叉引用断链
        have = {f for f in os.listdir(REFS) if f.endswith(".md")} if os.path.isdir(REFS) else set()
        for m in re.finditer(r"`(\d{2}-[^`]+?)(?:\.md)?`", raw):
            name = m.group(1)
            if name.endswith(".md"):
                name = name[:-3]
            if (name + ".md") not in have:
                warnings.append(f"[引用待查] {rel} → `{name}`（未匹配到篇目，可能为普通文字）")

    skill = os.path.join(HERE, "SKILL.md")
    if os.path.exists(skill):
        head = open(skill, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---\n", head, re.DOTALL)
        if not m:
            errors.append("[frontmatter] SKILL.md 缺少 frontmatter")
        else:
            fm = m.group(1)
            for key in ("name:", "description:"):
                if key not in fm:
                    errors.append(f"[frontmatter] SKILL.md 缺少 {key}")

    print(f"玉尺内容门禁：{len(docs)} 个文档，{len(REQUIRED)} 项必需文件")
    for w in warnings:
        print("  ⚠ " + w)
    if errors:
        for e in errors:
            print("  ✗ " + e)
        print(f"未通过（{len(errors)} 项）")
        sys.exit(1)
    print("✓ 全部通过（必需文件齐 / 无 AI 腔残留 / 无红线危险词 / frontmatter 完好）")


if __name__ == "__main__":
    main()
