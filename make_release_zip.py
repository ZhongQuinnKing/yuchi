#!/usr/bin/env python3
"""玉尺 · 发布包打包（零依赖）

把仓库打成可分发的 zip，给 GitHub Release 用（豆包拖拽安装 / 离线留存）。

两个要点（照拾级实战修过的成熟版）：
  1. 排除 .git / __pycache__ / .DS_Store —— 不留私货
  2. 文件名写 UTF-8 标志 —— macOS 的 zip 命令不写该标志，
     Windows 用户解压会把中文文件名解成乱码；python zipfile 会自动写
  3. 输出包自身排除在遍历之外 —— 输出到仓库内时不会把自己卷进去（死循环）

用法：
  python3 make_release_zip.py v1.8              # → 上级目录/玉尺-v1.8.zip
  python3 make_release_zip.py v1.8 -o /tmp/x.zip
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE_ANY = {".git", "__pycache__", ".DS_Store", ".pytest_cache", ".mypy_cache"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="版本号，如 v1.8")
    ap.add_argument(
        "-o", "--output", default=None, help="输出路径（默认：仓库上级目录/玉尺-版本.zip）"
    )
    args = ap.parse_args()

    out = Path(args.output) if args.output else ROOT.parent / f"玉尺-{args.version}.zip"
    if out.exists():
        out.unlink()

    out_res = out.resolve()
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            if p.resolve() == out_res:
                continue  # 不把输出包自己卷进去：读写同一文件会读到 EOF 前一直增长（死循环）
            rel = Path("yuchi") / p.relative_to(ROOT)  # 顶层目录名用英文（Windows 解压更稳）
            if any(part in EXCLUDE_ANY for part in p.relative_to(ROOT).parts):
                continue
            if p.is_dir():
                z.write(p, arcname=str(rel) + "/")
            else:
                z.write(p, arcname=str(rel))
                count += 1

    size = out.stat().st_size
    print(f"已打包：{out}")
    print(f"  {count} 个文件，{size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
