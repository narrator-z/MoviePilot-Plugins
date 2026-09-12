#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 release 矩阵：仅索引中 release:true 且目录自上个 Tag 以来有变化的插件。

按 Repository_Guide §8：
- 索引文件严格映射 plugins/、plugins.v2/、plugins.v3/
- Tag 格式 插件ID_v插件版本号；zip 文件名 插件目录小写_v插件版本号.zip
- 目录自上个 Tag 无变化则跳过
"""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INDEX_MAP = [
    ("package.json", ["plugins", "plugins.v3", "plugins.v2"]),
    ("package.v2.json", ["plugins.v2"]),
    ("package.v3.json", ["plugins.v3"]),
]


def changed_since_last_tag(dirpath: str) -> bool:
    try:
        last = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        files = subprocess.run(
            ["git", "diff", "--name-only", last, "HEAD", "--", dirpath],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout.strip()
        return bool(files)
    except Exception:
        return True  # 无历史 Tag 时默认打包


def main() -> None:
    matrix = []
    for idx, candidates in INDEX_MAP:
        path = os.path.join(ROOT, idx)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for pid, entry in data.items():
            if not (isinstance(entry, dict) and entry.get("release")):
                continue
            dirpath = None
            for cand in candidates:
                d = os.path.join(cand, pid.lower())
                if os.path.isdir(os.path.join(ROOT, d)):
                    dirpath = d
                    break
            if not dirpath:
                continue
            if not changed_since_last_tag(dirpath):
                continue
            matrix.append({"id": pid, "version": entry.get("version", ""), "dir": dirpath})
    print(f"matrix={json.dumps(matrix)}")


if __name__ == "__main__":
    main()
