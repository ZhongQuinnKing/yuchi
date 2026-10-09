#!/bin/bash
# 玉尺发布/交付前检查——一条命令跑完全部门禁（任一失败即停）
# 用法：bash release_check.sh
set -e
cd "$(dirname "$0")"

echo "══ 玉尺发布检查 ══"

echo "── 0/4 清缓存（pyc 内含本机路径，隐私闸必命中；跑过 python 就会重生）──"
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
echo "已清"

echo "── 1/4 内容门禁 ──"
python3 check.py

echo "── 2/4 文字校对（提醒式，逐条人工看）──"
python3 check_typos.py | tail -2

echo "── 3/4 双端一致性 ──"
node test_web.js > /dev/null && echo "✓ 通过（明细跑 node test_web.js 看）"

echo "── 4/4 隐私闸 ──"
bash ~/.claude/tools/privacy_scan.sh .

echo "══ 全部完成，可发布 ══"
