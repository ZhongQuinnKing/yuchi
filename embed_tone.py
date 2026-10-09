#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把平仄表注入网页（一次性构建步：改完 data/Word_Tune.json 或网页占位后重跑）。

用法：python3 embed_tone.py
效果：web/index.html 中 `/*TONE_TABLE_DATA*/null` 替换为 data/Word_Tune.json 的内容。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(HERE, "web", "index.html")
data_path = os.path.join(HERE, "data", "Word_Tune.json")

data = open(data_path, encoding="utf-8").read().strip()
html = open(html_path, encoding="utf-8").read()

placeholder = "/*TONE_TABLE_DATA*/null"
if placeholder not in html:
    if "let TONE_TABLE = {" in html:
        print("已注入过（占位符不在，数据在）——如需重注，先把数据换回占位符再跑。")
    else:
        print("未找到占位符 /*TONE_TABLE_DATA*/null")
    raise SystemExit(1)

html = html.replace(placeholder, data, 1)
open(html_path, "w", encoding="utf-8").write(html)
print(f"已注入平仄表（{len(data)} 字节）→ web/index.html")
