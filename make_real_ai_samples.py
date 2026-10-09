#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成真实 AI 输出样本（v1.1 复验用）

用本机已配置的模型端点，以普通用户口吻让模型写 10 篇通用主题文章，
存 samples/ai_real/ —— 这是"真实 AI 输出"而非特征合成样本。
每篇落盘即保存；单篇失败跳过继续。
运行：python3 make_real_ai_samples.py
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples", "ai_real")

BASE = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
TOKEN = os.environ["ANTHROPIC_AUTH_TOKEN"]
MODEL = os.environ["ANTHROPIC_MODEL"]

# 通用主题，覆盖不同文体、无任何隐私内容；就是普通人会问 AI 的那种题
TOPICS = [
    "秋天的公园",                      # 写景散文
    "一次难忘的旅行",                  # 记叙
    "手机依赖这件事",                  # 议论
    "怎么给家人做一顿简单的晚饭",      # 说明·生活
    "我最喜欢的一本书",                # 书评随笔
    "一款保温杯的产品介绍",            # 商业文案
    "远程办公的利与弊",                # 观点
    "我记忆里的一位长辈",              # 写人
    "一座小城的清晨",                  # 城市·写景
    "为什么要学一门乐器",              # 议论·文化
]


def gen(topic: str) -> str:
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 2500,
        "messages": [{
            "role": "user",
            "content": f"请写一篇 800 字左右的中文文章，主题：{topic}。直接输出正文。",
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
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for i, topic in enumerate(TOPICS, 1):
        path = os.path.join(OUT, f"r_{i:02d}.txt")
        if os.path.exists(path):
            print(f"[{i}/{len(TOPICS)}] 已存在，跳过：{topic}")
            ok += 1
            continue
        try:
            text = gen(topic).strip()
        except Exception as e:  # 单篇失败不拖累其余
            print(f"[{i}/{len(TOPICS)}] 失败：{topic} —— {e}")
            continue
        if len(text) < 100:
            print(f"[{i}/{len(TOPICS)}] 返回过短，未存：{topic}")
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[{i}/{len(TOPICS)}] {topic} → {len(text)} 字符，已存盘")
        ok += 1
    print(f"\n完成 {ok}/{len(TOPICS)} 篇 → {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
