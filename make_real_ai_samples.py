#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成真实 AI 输出样本（复验用）

用本机已配置的模型端点，以普通用户口吻让模型写作，存 samples/ai_real/。
两组：
  general —— 10 篇通用主题文章（r_01…）：散文/记叙/议论/书评/文案等
  work    —— 10 篇事务与限定文体（o_01…）：总结/通知/道歉信/述职/JD 等
每篇落盘即保存；单篇失败跳过继续。
运行：python3 make_real_ai_samples.py [general|work]
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples", "ai_real")

BASE = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
TOKEN = os.environ["ANTHROPIC_AUTH_TOKEN"]
# 默认用环境配置的模型；复量别的模型：YUCHI_SAMPLE_MODEL=xxx python3 本脚本 general c_
MODEL = os.environ.get("YUCHI_SAMPLE_MODEL") or os.environ["ANTHROPIC_MODEL"]

SETS = {
    # 通用主题：散文/记叙/议论/书评/商业文案/写人 —— 普通人会让 AI 写的文章
    "general": ("r_", [
        "写一篇 800 字左右的中文文章，主题：秋天的公园",
        "写一篇 800 字左右的中文文章，主题：一次难忘的旅行",
        "写一篇 800 字左右的中文文章，主题：手机依赖这件事",
        "写一篇 800 字左右的中文文章，主题：怎么给家人做一顿简单的晚饭",
        "写一篇 800 字左右的中文文章，主题：我最喜欢的一本书",
        "写一篇 800 字左右的中文文章，主题：一款保温杯的产品介绍",
        "写一篇 800 字左右的中文文章，主题：远程办公的利与弊",
        "写一篇 800 字左右的中文文章，主题：我记忆里的一位长辈",
        "写一篇 800 字左右的中文文章，主题：一座小城的清晨",
        "写一篇 800 字左右的中文文章，主题：为什么要学一门乐器",
    ]),
    # 事务与限定文体：职场 AI 代写的重灾区（预期“典型腔”更明显）
    "work": ("o_", [
        "写一份部门季度工作总结，800 字左右",
        "写一份公司年会通知，时间地点流程齐全",
        "写一封给客户的道歉信：一批订单延迟发货了一周",
        "写一段智能手表的推广文案，发朋友圈用",
        "写一份员工消防安全培训通知",
        "写一份年度述职报告，800 字左右",
        "写一段保温杯的电商详情页文案",
        "写一份项目启动会的会议纪要",
        "写一份新媒体运营岗位的招聘描述（JD）",
        "写一份关于调整公司办公时间的通知",
    ]),
}


def gen(prompt_phrase: str) -> str:
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 2500,
        "messages": [{
            "role": "user",
            "content": f"请{prompt_phrase}。直接输出正文。",
        }],
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in d.get("content", []))


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "general"
    if which not in SETS:
        print(f"组名须为 {'/'.join(SETS)}")
        return 1
    prefix, prompts = SETS[which]
    if len(sys.argv) > 2:  # 可选覆盖文件名前缀（复量别的模型时区分）
        prefix = sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for i, p in enumerate(prompts, 1):
        path = os.path.join(OUT, f"{prefix}{i:02d}.txt")
        if os.path.exists(path):
            print(f"[{i}/{len(prompts)}] 已存在，跳过：{p[:24]}…")
            ok += 1
            continue
        try:
            text = gen(p).strip()
        except Exception as e:  # 单篇失败不拖累其余
            print(f"[{i}/{len(prompts)}] 失败：{p[:24]}… —— {e}")
            continue
        if len(text) < 100:
            print(f"[{i}/{len(prompts)}] 返回过短，未存：{p[:24]}…")
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[{i}/{len(prompts)}] {p[:24]}… → {len(text)} 字符，已存盘")
        ok += 1
    print(f"\n[{which}] 完成 {ok}/{len(prompts)} 篇 → {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
