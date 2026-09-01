# -*- coding: utf-8 -*-
"""专项测试：保存功能 + max_tokens(6000) + 模型上限裁剪 + 截断防护"""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(__file__))

from prompt_config import (
    DEFAULT_PROMPTS, PromptConfig,
    load_prompts, save_prompts, reset_prompts, _infer_max_tokens_cap,
)


def section(title):
    print(f"\n=== {title} ===")


ok = True
def check(cond, msg):
    global ok
    print(f"  {'✅' if cond else '❌'} {msg}")
    ok = ok and cond


# 1. 默认值：max_tokens 现在是 6000
section("1. 默认 max_tokens = 6000")
cfg = PromptConfig()
check(cfg.max_tokens == 6000, f"默认值 = {cfg.max_tokens}（期望 6000）")

# 2. 生成参数含模型上限裁剪
section("2. 模型上限裁剪 generation_params(model=...)")
cases = [
    ("gpt-4o", 8192),
    ("deepseek-chat", 8192),
    ("qwen-plus", 8192),
    ("gpt-3.5-turbo", 4096),
    ("some-unknown-model", 4096),  # 未知 → 保守 4096
    ("", 4096),
]
for model, expected_cap in cases:
    p = PromptConfig(max_tokens=16000)  # 用户设很大
    params = p.generation_params(model=model)
    got = params["max_tokens"]
    check(got == min(16000, expected_cap),
          f"model={model!r} → max_tokens 裁剪为 {got}（cap={expected_cap}）")

# 3. _infer_max_tokens_cap 独立逻辑
section("3. _infer_max_tokens_cap 推断")
check(_infer_max_tokens_cap("gpt-4o") == 8192, "gpt-4o → 8192")
check(_infer_max_tokens_cap("deepseek-chat-v2") == 8192, "deepseek-* → 8192")
check(_infer_max_tokens_cap("qwen-max") == 8192, "qwen-max → 8192")
check(_infer_max_tokens_cap("gpt-3.5-turbo-instruct") == 2048, "老款小模型 → 2048")
check(_infer_max_tokens_cap("random-xx") == 4096, "未知 → 4096")

# 4. 保存功能：写入 + 回读一致（核心！模拟对话框 _save 流程）
section("4. 保存功能：写盘 → 回读 → 值一致（max_tokens=6000 不丢）")
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "config", "prompts.json")
p1 = PromptConfig(max_tokens=6000, temperature=0.9)
saved = save_prompts(p1, path)
check(saved, "save_prompts 返回 True")
check(os.path.exists(path), f"文件已落盘：{path}")

reloaded = load_prompts(path)
check(reloaded.max_tokens == 6000, f"回读 max_tokens = {reloaded.max_tokens}（期望 6000）")
check(abs(reloaded.temperature - 0.9) < 1e-9, f"回读 temperature = {reloaded.temperature}")
check("rewrite_system" in reloaded.to_dict(), "rewrite_system（固定范文提示词）保留")
check("===== 修改后的范文 =====" in reloaded.rewrite_system, "固定提示词含「修改后的范文」结构")

# 5. 空文件 / 损坏文件 → 回退默认，不崩溃
section("5. 容错：空文件 / 损坏 JSON → 回退默认")
empty_path = os.path.join(tmp, "empty.json")
with open(empty_path, "w", encoding="utf-8") as f:
    f.write("")
check(isinstance(load_prompts(empty_path), PromptConfig), "空文件 → 返回默认 PromptConfig")
bad_path = os.path.join(tmp, "bad.json")
with open(bad_path, "w", encoding="utf-8") as f:
    f.write("{not valid json")
check(load_prompts(bad_path).max_tokens == 6000, "损坏 JSON → 回退默认 6000")

# 6. 字段缺失 → 用默认补齐（向前兼容）
section("6. 向前兼容：缺字段自动补默认")
partial_path = os.path.join(tmp, "partial.json")
with open(partial_path, "w", encoding="utf-8") as f:
    json.dump({"max_tokens": 8000}, f)
partial = load_prompts(partial_path)
check(partial.max_tokens == 8000, "已有字段保留（8000）")
check("rewrite_system" in partial.to_dict(), "缺失字段用默认补齐（rewrite_system 存在）")

# 7. 边界：max_tokens 取值区间
section("7. max_tokens 边界")
p_min = PromptConfig(max_tokens=100)
check(p_min.generation_params()["max_tokens"] == 100, "最小值 100 可设")
p_big = PromptConfig(max_tokens=16000)
check(p_big.generation_params("gpt-4o")["max_tokens"] == 8192, "16000 被裁剪到模型上限 8192")

# 8. 占位符校验（对话框实时提示逻辑）
section("8. 必需占位符校验（对话框 _update_hint 等价逻辑）")
def has_warnings(cfg):
    w = []
    if "{essay}" not in cfg.feedback_user:
        w.append("点评缺 essay")
    if "{essay}" not in cfg.rewrite_user:
        w.append("范文缺 essay")
    return w
normal = PromptConfig()
check(has_warnings(normal) == [], "默认提示词无警告")
bad = PromptConfig(rewrite_user="请修改这篇作文")  # 缺 {essay}
check("范文缺 essay" in has_warnings(bad), "范文模板缺 {essay} → 给出警告")

print("\n" + ("=" * 40))
print("🎉 全部测试通过！" if ok else "❌ 存在失败项")
sys.exit(0 if ok else 1)
