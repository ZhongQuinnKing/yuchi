#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把平水韵表注入网页（一次性构建步：改完 data/Pingshui_Rhyme.json 或网页占位后重跑）。

用法：python3 embed_rhyme.py
效果：web/index.html 中 `/*RHYME_TABLE_DATA*/null` 替换为压缩韵表（韵部→字串）。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(HERE, "web", "index.html")
data_path = os.path.join(HERE, "data", "Pingshui_Rhyme.json")

d = json.load(open(data_path, encoding="utf-8"))
compact = {}
for _sheng, bu in d.items():
    for yun, chars in bu.items():
        seen = set()
        uniq = []
        for c in chars:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        compact[yun] = "".join(uniq)

data = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
html = open(html_path, encoding="utf-8").read()

placeholder = "/*RHYME_TABLE_DATA*/null"
if placeholder not in html:
    if "RHYME_TABLE = {" in html:
        print("已注入过（占位符不在，数据在）——如需重注，先把数据换回占位符再跑。")
    else:
        print("未找到占位符 /*RHYME_TABLE_DATA*/null")
    raise SystemExit(1)

html = html.replace(placeholder, data, 1)
open(html_path, "w", encoding="utf-8").write(html)
print(f"已注入韵表（{len(data)} 字节，{len(compact)} 韵部）→ web/index.html")
