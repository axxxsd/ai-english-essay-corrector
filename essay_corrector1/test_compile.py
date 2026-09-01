# -*- coding: utf-8 -*-
"""全量语法编译检查：用 py_compile 校验所有 .py，无需 tkinter"""
import os
import py_compile

base = os.path.dirname(__file__)
files = [f for f in os.listdir(base) if f.endswith(".py") and not f.startswith("test_")]

ok = True
for f in sorted(files):
    path = os.path.join(base, f)
    try:
        py_compile.compile(path, doraise=True)
        print(f"  ✅ {f}")
    except py_compile.PyCompileError as e:
        ok = False
        print(f"  ❌ {f}: {e}")

print("\n🎉 全部语法通过" if ok else "❌ 存在语法错误")
raise SystemExit(0 if ok else 1)
