#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从中原音韵 TSV 生成玉尺用的查询表（一次性构建步）。

输入：data/Zhongyuan_Yinyun.tsv（nk2028/zhongyuan-data，CC0-1.0，繁体）
输出：data/Zhongyuan_Rhyme.json —— {字(简): [[调, 韵部], …]}

要点：
  - 韵部 = 韻母列前两字（東鍾合/江陽開 → 東鍾/江陽），唯一性有 assert 把关
  - 声调保留原样：陰/陽/上/去 与 入作上/入作陽/入作去（北曲入派三声的原始标记）
  - 上游是繁体，用 zhconv 转简体（一个繁体转出同形简体时自然合并）
  - 输出 sort_keys + 排序列表，保证可复现

用法：python3 make_zhongyuan_data.py
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data", "Zhongyuan_Yinyun.tsv")
DST = os.path.join(HERE, "data", "Zhongyuan_Rhyme.json")

KNOWN_YUN = {
    "東鍾", "江陽", "支思", "齊微", "魚模", "皆來", "真文", "寒山", "桓歡", "先天",
    "蕭豪", "歌戈", "家麻", "車遮", "庚青", "尤侯", "侵尋", "監咸", "廉纖",
}
KNOWN_TONE_PREFIX = ("陰", "陽", "上", "去", "入")


def main() -> int:
    try:
        import zhconv
    except ImportError:
        print("缺 zhconv：python3 -m pip install zhconv")
        return 1

    table = {}
    bad_yun = 0
    multi = 0
    with open(SRC, encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    for r in rows[1:]:
        if len(r) < 5:
            continue
        ch_raw, yun_raw, tone = r[1].strip(), r[3].strip(), r[4].strip()
        if not ch_raw:
            continue
        yun_t = yun_raw[:2]
        if yun_t not in KNOWN_YUN:  # 先用繁体原名校验
            bad_yun += 1
            continue
        yun = zhconv.convert(yun_t, "zh-cn")  # 韵部名也转简，与玉尺其他模式口径一致
        if not tone.startswith(KNOWN_TONE_PREFIX):
            continue
        # 上游「字」列有时是并列异体（如「說説」），逐字拆开各自入表
        for c_raw in ch_raw:
            c = zhconv.convert(c_raw, "zh-cn")
            if len(c) != 1:  # 极罕见：转换后非单字
                multi += 1
                print("  跳过（转换后非单字）:", c_raw, "→", c)
                continue
            table.setdefault(c, set()).add((tone, yun))

    out = {k: [list(t) for t in sorted(v)] for k, v in sorted(table.items())}
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"已生成 {DST}")
    print(f"  字数 {len(out)}　韵部异常跳过 {bad_yun}　多字转换跳过 {multi}")
    # 抽查
    for ch in ("看", "行", "长", "涯", "鸦", "马"):
        print(f"  {ch} → {out.get(ch)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
