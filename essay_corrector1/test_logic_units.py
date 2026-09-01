# -*- coding: utf-8 -*-
"""纯逻辑测试（不依赖 tkinter），直接验证 llm_feedback 的格式化与参数裁剪"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from llm_feedback import _format_revision, _extract_content

ok = True
def check(c, m):
    global ok
    print(f"  {'✅' if c else '❌'} {m}")
    ok = ok and c


# _format_revision 标注 max_tokens
print("\n=== _format_revision 标注生效 token ===")
out = _format_revision("Hello revised essay", max_tokens=6000)
check("max_tokens = 6000" in out, f"结果含 'max_tokens = 6000'：{out.splitlines()[2]}")
check("Hello revised essay" in out, "正文保留")

out2 = _format_revision("no token info")
check("max_tokens" not in out2.split("\n")[2] if "\n" in out2 else True,
      "未传 max_tokens 时不强行标注")

# _extract_content
print("\n=== _extract_content ===")
check(_extract_content({"choices": [{"message": {"content": "hi"}}]}) == "hi",
      "标准响应提取 content")

print("\n" + ("=" * 40))
print("🎉 通过" if ok else "❌ 失败")
sys.exit(0 if ok else 1)
