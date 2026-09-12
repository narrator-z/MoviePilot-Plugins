#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本一致性门禁（Repository_Guide §6.3 / Plugin_Development §11.1）：

- 三份索引条目必须有同名（小写）源码目录与 __init__.py
- 索引 version == 插件类 plugin_version；索引 author == plugin_author
- history 顶键（忽略 v 前缀）== 当前版本
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INDEX_MAP = [
    ("package.json", ["plugins", "plugins.v3", "plugins.v2"]),
    ("package.v2.json", ["plugins.v2"]),
    ("package.v3.json", ["plugins.v3"]),
]


def main() -> int:
    errs = []
    for idx, candidates in INDEX_MAP:
        path = os.path.join(ROOT, idx)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for pid, entry in data.items():
            init = None
            for cand in candidates:
                p = os.path.join(ROOT, cand, pid.lower(), "__init__.py")
                if os.path.isfile(p):
                    init = p
                    break
            if not init:
                errs.append(f"{idx}:{pid} 缺少源码目录/__init__.py（候选 {candidates}）")
                continue
            code = open(init, encoding="utf-8").read()
            m = re.search(r"^\s*plugin_version\s*=\s*[\"']([^\"']+)[\"']", code, re.M)
            if not m:
                errs.append(f"{init}: 未找到 plugin_version")
            elif m.group(1) != entry.get("version"):
                errs.append(f"{idx}:{pid} version={entry.get('version')} != plugin_version={m.group(1)}")
            ma = re.search(r"^\s*plugin_author\s*=\s*[\"']([^\"']+)[\"']", code, re.M)
            if ma and entry.get("author") and ma.group(1) != entry["author"]:
                errs.append(f"{idx}:{pid} author={entry['author']} != plugin_author={ma.group(1)}")
            hist = entry.get("history") or {}
            keys = list(hist.keys())
            if keys:
                top = keys[0].lstrip("vV")
                if top != str(entry.get("version")):
                    errs.append(f"{idx}:{pid} history 顶键 {keys[0]} != version {entry.get('version')}")
    if errs:
        print("\n".join(errs))
        return 1
    print("check_plugin_versions: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
