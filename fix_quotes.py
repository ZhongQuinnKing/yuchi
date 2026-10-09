#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性工具：把中文 md 文档里成对的半角直引号 " 转为全角引号“”（按出现顺序配对）。

用于把历史文档的引号统一到全角规范。转换后请抽查成对是否正确。
用法：python3 fix_quotes.py 文件1.md 文件2.md ...
"""
import sys


def fix(path):
    t = open(path, encoding="utf-8").read()
    out, n = [], 0
    for ch in t:
        if ch == '"':
            out.append("“" if n % 2 == 0 else "”")
            n += 1
        else:
            out.append(ch)
    open(path, "w", encoding="utf-8").write("".join(out))
    flag = "成对" if n % 2 == 0 else "⚠ 奇数个（有落单，需人工查）"
    print(f"{path}: {n} 个直引号已转换（{flag}）")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        fix(p)
