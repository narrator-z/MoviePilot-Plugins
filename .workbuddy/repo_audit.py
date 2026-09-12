#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MoviePilot-Plugins 全仓体检（只读，不修改任何文件）。

校验维度：
  A. 清单条目 <-> 代码目录 双向对应
  B. 索引 version <-> 代码 plugin_version <-> history 最新 key
  C. 索引 author  <-> 代码 plugin_author
  D. v3-only 规则（package.v2.json 不应含 v3-only；package.json 中 v3-only 应带 v3:true + system_version）
  E. 图标文件存在性
  F. 全量 py_compile
  G. 插件自带 package.json 版本漂移
  H. 文件名规范（禁止版本号后缀）
  I. 必填字段（name/description/version/author/level/history）
  L. v2/v3 同名插件 __init__.py 逐行对齐（防「半截漏改」）
"""
import difflib
import json
import os
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDX_ALL = ROOT / "package.json"
IDX_V2 = ROOT / "package.v2.json"
IDX_V3 = ROOT / "package.v3.json"
DIR_V2 = ROOT / "plugins.v2"
DIR_V3 = ROOT / "plugins.v3"
ICONS = ROOT / "icons"

problems = []   # (级别, 维度, 插件, 说明)
notes = []


def add(level, dim, plugin, msg):
    problems.append((level, dim, plugin, msg))


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        add("P0", "解析", "-", f"{path.name} JSON 解析失败: {e}")
        return {}


def parse_code(pyfile):
    """从 __init__.py 提取 plugin_version / plugin_author（容忍缩进）。"""
    out = {"version": None, "author": None, "err": None}
    try:
        txt = pyfile.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        out["err"] = str(e)
        return out
    m = re.search(r"^\s*plugin_version\s*=\s*[\"']([^\"']+)[\"']", txt, re.M)
    if m:
        out["version"] = m.group(1)
    m = re.search(r"^\s*plugin_author\s*=\s*[\"']([^\"']+)[\"']", txt, re.M)
    if m:
        out["author"] = m.group(1)
    return out


def main():
    idx_all = read_json(IDX_ALL)
    idx_v2 = read_json(IDX_V2)
    idx_v3 = read_json(IDX_V3)

    dirs_v2 = sorted(d.name for d in DIR_V2.iterdir() if d.is_dir()) if DIR_V2.is_dir() else []
    dirs_v3 = sorted(d.name for d in DIR_V3.iterdir() if d.is_dir()) if DIR_V3.is_dir() else []
    # MP 约定：目录名 = 清单 ID 的小写形式，比较时统一小写
    low_v2 = {d.lower(): d for d in dirs_v2}
    low_v3 = {d.lower(): d for d in dirs_v3}

    print("=" * 78)
    print("A. 清单条目 <-> 代码目录 双向对应（大小写不敏感）")
    print("=" * 78)
    all_ids = set(idx_all)
    v2_ids = set(idx_v2)
    v3_ids = set(idx_v3)

    for pid in sorted(all_ids):
        d = low_v3.get(pid.lower())
        if d is None:
            add("P0", "A", pid, f"package.json 有条目但 plugins.v3/ 下无对应目录")
        elif d != pid:
            add("P2", "A", pid, f"目录名 {d} 与清单 ID 大小写不一致（MP 加载按 ID 小写，通常无害）")
    for d in dirs_v3:
        if d.lower() not in {p.lower() for p in all_ids}:
            add("P1", "A", d, f"plugins.v3/{d}/ 目录存在但 package.json 无条目")
    for pid in sorted(v2_ids):
        d = low_v2.get(pid.lower())
        if d is None:
            add("P0", "A", pid, "package.v2.json 有条目但 plugins.v2/ 下无对应目录")
    for d in dirs_v2:
        if d.lower() not in {p.lower() for p in v2_ids}:
            add("P1", "A", d, f"plugins.v2/{d}/ 目录存在但 package.v2.json 无条目")
    if {p.lower() for p in idx_v3} != {p.lower() for p in all_ids}:
        add("P1", "A", "-", f"package.v3.json 与 package.json 的 ID 集合不一致: "
                            f"v3独有={sorted(set(idx_v3)-all_ids)} all独有={sorted(all_ids-set(idx_v3))}")

    # v3-only 判定：在 package.json 中 v3:true 且不在 v2 清单
    v3_only = []
    for pid, meta in idx_all.items():
        if isinstance(meta, dict) and meta.get("v3") is True and pid not in v2_ids:
            v3_only.append(pid)
    print(f"v3-only 插件: {v3_only}")

    print()
    print("=" * 78)
    print("B/C/D. 版本 / 作者 / v3 标记一致性")
    print("=" * 78)
    for pid in sorted(all_ids | v2_ids | v3_ids):
        # 代码位置（大小写不敏感解析真实目录名）
        code_dir = None
        base = "package.json"
        if pid in all_ids:
            code_dir = DIR_V3 / low_v3.get(pid.lower(), pid)
        elif pid in v2_ids:
            code_dir = DIR_V2 / low_v2.get(pid.lower(), pid)
            base = "package.v2.json"
        pyfile = (code_dir / "__init__.py") if code_dir else None

        if not pyfile or not pyfile.exists():
            add("P0", "B", pid, "缺少 __init__.py")
            continue

        code = parse_code(pyfile)

        # 索引版本（三份都要能对上代码）
        for idx_name, idx in (("package.json", idx_all), ("package.v3.json", idx_v3), ("package.v2.json", idx_v2)):
            if pid not in idx:
                continue
            meta = idx[pid]
            iv = meta.get("version")
            if code["version"] and iv != code["version"]:
                lv = "P0" if idx_name != "package.v2.json" else "P1"
                add(lv, "B", pid, f"{idx_name} version={iv} != 代码 plugin_version={code['version']}")
            ia = meta.get("author")
            if code["author"] and ia is not None and ia != code["author"]:
                add("P0", "C", pid, f"{idx_name} author={ia} != 代码 plugin_author={code['author']}")
            # 必填字段
            for f in ("name", "description", "version", "author", "level", "history"):
                if f not in meta or meta.get(f) in (None, ""):
                    add("P1", "I", pid, f"{idx_name} 缺字段/为空: {f}")
            # history 最新版本
            h = meta.get("history")
            if isinstance(h, dict) and h and code["version"]:
                keys = [k.lstrip("v") for k in h]
                if code["version"] not in keys:
                    add("P1", "B", pid, f"{idx_name} history 无 {code['version']} 条目（现有最新 {sorted(keys)[-3:]}）")
            # v3-only 不应出现在 v2 清单
            if pid in v3_only and idx_name == "package.v2.json":
                add("P0", "D", pid, "v3-only 插件出现在 package.v2.json")
            # v3 标记
            if idx_name == "package.json":
                if pid not in v2_ids:
                    if meta.get("v3") is not True:
                        add("P1", "D", pid, "v3-only 但 package.json 缺 \"v3\": true")
                    sv = meta.get("system_version")
                    if not sv or not str(sv).startswith(">="):
                        add("P1", "D", pid, f"v3-only 但 system_version 异常: {sv!r}")

    print()
    print("=" * 78)
    print("E. 图标文件存在性")
    print("=" * 78)
    for idx_name, idx in (("package.json", idx_all), ("package.v2.json", idx_v2), ("package.v3.json", idx_v3)):
        for pid, meta in idx.items():
            if not isinstance(meta, dict):
                continue
            icon = meta.get("icon")
            if not icon:
                continue
            fname = icon.rsplit("/", 1)[-1]
            if not (ICONS / fname).exists():
                add("P2", "E", pid, f"{idx_name} icon={fname} 在 icons/ 下不存在")

    print()
    print("=" * 78)
    print("F. 全量 py_compile")
    print("=" * 78)
    py_count = 0
    for root in (DIR_V2, DIR_V3):
        if not root.is_dir():
            continue
        for py in root.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            py_count += 1
            try:
                src = py.read_text(encoding="utf-8", errors="replace")
                compile(src, str(py), "exec")
            except SyntaxError as e:
                add("P0", "F", py.relative_to(ROOT).as_posix(), f"语法错误: {e.msg} (line {e.lineno})")
            except Exception as e:
                add("P1", "F", py.relative_to(ROOT).as_posix(), f"读取/编译异常: {str(e)[:120]}")
    print(f"编译检查 {py_count} 个 .py 文件")

    print()
    print("=" * 78)
    print("G. 插件自带 package.json 版本漂移")
    print("=" * 78)
    low_all = {k.lower(): k for k in idx_all}
    for root in (DIR_V2, DIR_V3):
        if not root.is_dir():
            continue
        for pk in root.rglob("package.json"):
            if "__pycache__" in pk.parts or "node_modules" in pk.parts:
                continue
            sub = pk.relative_to(root)
            if len(sub.parts) != 2:
                continue  # 只看插件根级 package.json
            pid = sub.parts[0]
            try:
                pv = json.loads(pk.read_text(encoding="utf-8")).get("version")
            except Exception:
                continue
            real = low_all.get(pid.lower())
            idx_v = (idx_all.get(real) or {}).get("version")
            if pv and idx_v and pv != idx_v:
                add("P2", "G", real or pid, f"插件内 {root.name}/{pid}/package.json version={pv} 与索引 {idx_v} 不一致")
            if pv:
                print(f"  {root.name}/{pid}/package.json version={pv}  (索引 {idx_v})")

    print()
    print("=" * 78)
    print("H. 文件名规范（版本号后缀）")
    print("=" * 78)
    badname = re.compile(r"[-_]v?\d+(\.\d+){1,3}\.(py|json|js|md)$", re.I)
    for root in (DIR_V2, DIR_V3):
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts and badname.search(f.name):
                add("P2", "H", f.relative_to(ROOT).as_posix(), "文件名疑似带版本号后缀")

    print()
    print("=" * 78)
    print("J. 硬编码凭据/密钥字面量（排除明显的占位符）")
    print("=" * 78)
    cred = re.compile(
        r"(?i)(api_?key|apikey|token|secret|password|passwd|pwd)\s*[=:]\s*[\"']([^\"']{8,})[\"']"
    )
    allow = re.compile(r"(?i)^(your|xxx|<|placeholder|changeme|example|test|none|null|\$\{|%s)")
    jcount = 0
    for root in (DIR_V2, DIR_V3):
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix not in (".py", ".js", ".json"):
                continue
            if "__pycache__" in f.parts or "node_modules" in f.parts:
                continue
            if f.name in ("package.json",):
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in cred.finditer(txt):
                val = m.group(2)
                if allow.match(val):
                    continue
                line = txt[: m.start()].count("\n") + 1
                add("P1", "J", f.relative_to(ROOT).as_posix(), f"L{line} {m.group(1)} 疑似硬编码: {val[:12]}…")
                jcount += 1
    print(f"命中 {jcount} 处")

    print()
    print("=" * 78)
    print("K. 仓库卫生（工作区脏文件/意外入库产物）")
    print("=" * 78)
    for root in (DIR_V2, DIR_V3):
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if "__pycache__" in f.parts or "node_modules" in f.parts:
                continue
            if f.suffix in (".pyc", ".pyo", ".log", ".bak", ".tmp", ".orig"):
                add("P1", "K", f.relative_to(ROOT).as_posix(), "疑似构建/临时产物残留在插件目录")
            elif f.is_file() and f.stat().st_size > 20 * 1024 * 1024:
                add("P2", "K", f.relative_to(ROOT).as_posix(), f"大文件 {f.stat().st_size/1048576:.1f}MB")

    print()
    print("=" * 78)
    print("L. v2/v3 同名插件 __init__.py 逐行对齐（防「半截漏改」）")
    print("=" * 78)
    print("判据：同名插件的 v2/v3 代码应完全一致（v3 特有适配除外）。")
    print("背景：2028bf9 声称 v2/v3 同改，实际 v3 只改了签名与调用点、函数体漏改，三天无人发现。")
    common_names = sorted(set(low_v2) & set(low_v3))
    print(f"同名插件 {len(common_names)} 个: {[low_v3[n] for n in common_names]}")
    for name in common_names:
        f2 = DIR_V2 / low_v2[name] / "__init__.py"
        f3 = DIR_V3 / low_v3[name] / "__init__.py"
        if not f2.exists() or not f3.exists():
            add("P1", "L", low_v3[name], "同名插件缺 __init__.py，无法对齐")
            continue
        # CRLF 归一化：core.autocrlf 会让同一文件整份被判为差异
        t2 = f2.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        t3 = f3.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        if t2 == t3:
            print(f"  \u2713 {low_v3[name]}: 完全一致")
            continue
        diff = [
            ln for ln in difflib.unified_diff(
                t2.splitlines(), t3.splitlines(), "v2", "v3", lineterm="", n=0
            )
            if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
        ]
        first = diff[0][:110] if diff else "?"
        add("P0", "L", low_v3[name],
            f"v2/v3 __init__.py 不一致（{len(diff)} 行差异）—— 同名插件的共享修复必须两侧同改；首个差异: {first}")

    print()
    print("=" * 78)
    print("体检汇总")
    print("=" * 78)
    if not problems:
        print("未发现问题。")
    else:
        order = {"P0": 0, "P1": 1, "P2": 2}
        problems.sort(key=lambda x: (order.get(x[0], 9), x[1], x[2]))
        cnt = {}
        for lv, dim, p, msg in problems:
            cnt[lv] = cnt.get(lv, 0) + 1
            print(f"[{lv}] ({dim}) {p}: {msg}")
        print()
        print("计数:", ", ".join(f"{k}={v}" for k, v in sorted(cnt.items())))
    for n in notes:
        print("[note]", n)
    return 1 if any(p[0] == "P0" for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
