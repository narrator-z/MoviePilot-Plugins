#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AST 扫描：函数声明了参数但在函数体内从未被引用（unused argument）。

用于发现类型 jackettextend v3 那种「签名收了 cookies/headers，函数体却丢弃不用」
的半截子改动。只读，不修改文件。

排除项：
  - self / cls
  - 以 _ 开头的占位参数
  - 被 **kwargs / *args 吞掉的
  - 装饰器包装（@xxx.setter 等）中常见的约定参数
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT / "plugins.v2", ROOT / "plugins.v3"]


def used_names(node):
    """收集函数体内实际引用到的名字（含嵌套作用域）。"""
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            pass
        elif isinstance(n, ast.arg):
            # 嵌套函数的参数名也算被"声明"，但不代表外层参数被用
            pass
    return names


def check_file(py):
    src = py.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, str(py))
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        a = node.args
        declared = [x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs)]
        # 被 *args/**kwargs 覆盖的调用方式无法静态判定，跳过带它们的函数
        has_varargs = bool(a.vararg or a.kwarg)
        body_used = used_names(node)
        # 函数体里作为属性名的（self.x）不算参数被使用；这里只看普通 Name
        for p in declared:
            if p in ("self", "cls") or p.startswith("_"):
                continue
            if p in body_used:
                continue
            hits.append((node.lineno, node.name, p, has_varargs))
    return hits


def main():
    total = 0
    for root in TARGETS:
        if not root.is_dir():
            continue
        for py in sorted(root.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            try:
                hits = check_file(py)
            except SyntaxError as e:
                print(f"[语法错误] {py}: {e}")
                continue
            for lineno, fn, param, varargs in hits:
                # 有 *args/**kwargs 的函数存在"动态消费"可能，降级为提示
                tag = "[可能误报]" if varargs else "[未使用]"
                print(f"{tag} {py.relative_to(ROOT).as_posix()}:{lineno} "
                      f"def {fn}(... {param} ...) —— 参数未在函数体被引用")
                total += 1
    print()
    print(f"合计 {total} 处")


if __name__ == "__main__":
    sys.exit(main())
