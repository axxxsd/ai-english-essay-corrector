# -*- coding: utf-8 -*-
"""
test_timeout_fix.py
复现并验证 "tuple object cannot be interpreted as an integer" 的修复。

原理：用 unittest.mock 替换 urllib.request.urlopen，
检查 _post_json 传给它的 timeout 参数是「单个数字」还是「元组」。
- 若为元组 → 触发原报错（复现成功，修复失败）
- 若为数字 → 修复成功
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import patch, MagicMock


def make_fake_resp(payload):
    """构造一个模仿 urlopen 上下文管理器的假响应。"""
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    return resp


def test_timeout_is_number():
    from llm_feedback import _post_json

    captured = {}

    def fake_urlopen(req, timeout=None, **kwargs):
        captured["timeout"] = timeout
        # 返回一个上下文管理器（__enter__ 给出假响应）
        fake_resp = make_fake_resp({"choices": [{"message": {"content": "ok"}}]})
        ctx = MagicMock()
        ctx.__enter__.return_value = fake_resp
        ctx.__exit__.return_value = False
        return ctx

    with patch("llm_feedback.urllib.request.urlopen", side_effect=fake_urlopen):
        _post_json(
            "https://example.com/v1/chat/completions",
            {"model": "gpt-3.5-turbo", "messages": []},
            {"Content-Type": "application/json", "Authorization": "Bearer x"},
            timeout=120,
        )

    t = captured["timeout"]
    print(f"[debug] _post_json 传入 urlopen 的 timeout = {t!r}  (类型: {type(t).__name__})")

    # 核心断言：timeout 必须是 int / float，绝不能是个 tuple
    assert not isinstance(t, tuple), (
        f"❌ 修复失败：timeout 仍是元组 {t!r}，"
        "会触发 'tuple object cannot be interpreted as an integer'"
    )
    assert isinstance(t, (int, float)), f"❌ timeout 类型异常: {type(t).__name__}"
    assert t >= 120, f"❌ 超时时间应 ≥ 120，实际 {t}"
    print("✅ 测试通过：timeout 是单个数值，不会再触发 tuple 报错。")


if __name__ == "__main__":
    test_timeout_is_number()
