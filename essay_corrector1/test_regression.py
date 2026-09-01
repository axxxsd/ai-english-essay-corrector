# -*- coding: utf-8 -*-
"""
回归测试：语法 + 导入 + 调用链 + 线程安全 + 主程序方法单例 + 对话框保存流程。
注意：GUI 模块（prompt_dialog / settings_dialog / desktop_app）依赖 tkinter，
      服务器沙盒通常没有，故源码层面的检查统一改为「读文件」，
      保证在无 GUI 环境也能完整校验逻辑；本地 Windows 官方 Python 自带 tkinter。
"""
import os
import re
import sys
import importlib.util

sys.path.insert(0, os.path.dirname(__file__))

ok = True
SKIPPED = []


def check(cond, msg):
    global ok
    print(f"  {'✅' if cond else '❌'} {msg}")
    ok = ok and cond


def load(mod, path):
    """导入模块；tkinter 缺失则记录跳过并返回 None（源码检查改用 read_src）。"""
    global ok
    spec = importlib.util.spec_from_file_location(mod, path)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except ModuleNotFoundError as e:
        if e.name == "tkinter":
            SKIPPED.append(mod)
            print(f"  ⏭️ {mod} 跳过导入（无 tkinter），源码检查改用文件读取")
            return None
        raise
    return m


def read_src(name):
    """读取模块源码（不导入，避免 tkinter 依赖）。"""
    path = os.path.join(os.path.dirname(__file__), name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
section = lambda t: print(f"\n=== {t} ===")
base = os.path.dirname(__file__)

# 1. 所有非 GUI 模块语法 + 导入
section("1. 非 GUI 模块语法 & 导入")
for f in ["grammar_checker.py", "scorer.py", "api_config.py", "prompt_config.py",
          "llm_feedback.py"]:
    try:
        load(f.replace(".py", ""), os.path.join(base, f))
        check(True, f"{f} 语法/导入 OK")
    except Exception as e:
        check(False, f"{f} 导入失败：{type(e).__name__}: {e}")

# 2. prompt_config 关键 API
section("2. prompt_config 关键 API")
pc = load("prompt_config", os.path.join(base, "prompt_config.py"))
cfg = pc.PromptConfig()
check(hasattr(cfg, "rewrite_system"), "有 rewrite_system（固定范文提示词）")
check("===== 修改后的范文 =====" in cfg.rewrite_system, "固定提示词含「修改后的范文」结构")
check(cfg.max_tokens == 6000, f"默认 max_tokens = {cfg.max_tokens}")
check("temperature" in cfg.generation_params(), "generation_params 含 temperature")
gp = cfg.generation_params(model="gpt-4o")
check(gp["max_tokens"] == 6000, f"gpt-4o cap=8192>请求6000，不裁剪，保持 {gp['max_tokens']}")
gp2 = cfg.generation_params(model="some-random-model")
check(gp2["max_tokens"] == 4096, f"未知模型 cap=4096，6000 裁剪为 {gp2['max_tokens']}（避免接口报错）")

# 3. llm_feedback 使用 model-aware 裁剪（源码检查，无 tkinter 依赖）
section("3. llm_feedback 调用链")
lf = load("llm_feedback", os.path.join(base, "llm_feedback.py"))
lf_src = read_src("llm_feedback.py")
import inspect
if lf is not None:
    lf_src = inspect.getsource(lf)
check("generation_params(model=config.model)" in lf_src,
      "generate_revised_essay / get_llm_feedback 使用 generation_params(model=...)")
check("def _format_revision(text: str, max_tokens" in lf_src,
      "_format_revision 接受 max_tokens 参数（结果标注生效值）")

# 4. 线程安全：无 self.after，有队列轮询（源码检查）
section("4. 线程安全（无 self.after 残留）")
da_src = read_src("desktop_app.py")
check("self.llm_queue = queue.Queue()" in da_src, "有 llm_queue 队列")
check("self.root.after(100, self._poll_queues)" in da_src, "主线程轮询 _poll_queues")
check("def _poll_queues" in da_src, "有 _poll_queues 方法")
cleaned = da_src.replace("self.root.after(100, self._poll_queues)", "")
check(".after(0," not in cleaned, "无 self.after(0, ...) 跨线程调用残留")

# 5. 关键：主程序方法单例检查（曾经有两个 _on_models_done 互相覆盖！）
section("5. 主程序方法单例（防覆盖回归）")
from collections import Counter
# 只匹配「类顶层方法」（缩进恰好 4 空格），排除嵌套函数（如各方法内的 worker）
methods = re.findall(r"^    def (\w+)\(", da_src, re.MULTILINE)
dupes = [m for m, c in Counter(methods).items() if c > 1]
# 重点防护：曾经 _on_models_done 被定义两次，后一个覆盖了前一个（前一个是 pass 空壳），
# 导致模型列表回调失效。此断言一旦再犯立即报警。
check(methods.count("_on_models_done") == 1,
      f"_on_models_done 唯一定义（回归防护，当前 {methods.count('_on_models_done')} 处）")
check(dupes == [], f"无重复定义的方法（当前重复项：{dupes}）")
check("_poll_queues" in methods, "有 _poll_queues")
check("_on_models_done" in methods, "有 _on_models_done（唯一）")

# 6. prompt_dialog 保存流程（源码检查）
section("6. 提示词对话框保存流程")
pd_src = read_src("prompt_dialog.py")
check("def _save(self)" in pd_src, "有 _save 方法（保存功能存在）")
check("save_prompts(cfg)" in pd_src, "调用 save_prompts 落盘")
check("load_prompts(DEFAULT_PROMPTS_PATH)" in pd_src, "保存后回读校验（确认落盘成功）")
check("to=16000" in pd_src, "max_tokens Spinbox 上限已放开到 16000")
check("max_tokens_var" in pd_src, "有 max_tokens 输入控件")

print("\n" + ("=" * 40))
if SKIPPED:
    print(f"⏭️ 跳过导入（环境无 tkinter，本地不受影响）：{SKIPPED}")
print("🎉 全部回归通过！" if ok else "❌ 存在失败项")
sys.exit(0 if ok else 1)
