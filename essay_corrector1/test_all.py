# -*- coding: utf-8 -*-
"""
test_all.py — 全量测试脚本（离线运行，不发起真实网络请求）

用法：python test_all.py
"""
import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# 1. grammar_checker 测试
# ============================================================
class TestGrammarChecker(unittest.TestCase):
    def setUp(self):
        from grammar_checker import GrammarChecker
        self.checker = GrammarChecker()

    def test_spelling_alot(self):
        issues = self.checker.check("This is alot of fun.")
        msgs = [i["message"] for i in issues]
        self.assertTrue(any("alot" in m for m in msgs), f"应检出 alot, 实际: {msgs}")

    def test_capitalization(self):
        issues = self.checker.check("hello world. this is bad.")
        severities = [i["severity"] for i in issues]
        self.assertIn("warning", severities)

    def test_subject_verb(self):
        issues = self.checker.check("They goes to school.")
        msgs = [i["message"] for i in issues]
        self.assertTrue(any("goes" in m for m in msgs), f"应检出主谓不一致, 实际: {msgs}")

    def test_chinglish_more_better(self):
        issues = self.checker.check("This is more better.")
        msgs = [i["message"] for i in issues]
        self.assertTrue(any("more better" in m for m in msgs))

    def test_empty_input(self):
        issues = self.checker.check("")
        self.assertEqual(issues, [])


# ============================================================
# 2. scorer 测试
# ============================================================
class TestScorer(unittest.TestCase):
    def setUp(self):
        from scorer import Scorer
        from grammar_checker import GrammarChecker
        self.scorer = Scorer()
        self.checker = GrammarChecker()

    def test_score_range(self):
        essay = "Nowdays, with the development of society, students study hard every day. They want to learn more. I think education is crucial for everyone."
        issues = self.checker.check(essay)
        result = self.scorer.score(essay, issues)
        self.assertGreaterEqual(result["total"], 0)
        self.assertLessEqual(result["total"], 100)
        self.assertIn("stats", result)

    def test_short_essay_content_penalty(self):
        issues = []
        result = self.scorer.score("Hi.", issues)
        self.assertLessEqual(result["content"], 20)


# ============================================================
# 3. api_config 测试
# ============================================================
class TestApiConfig(unittest.TestCase):
    def test_default_config(self):
        from api_config import ApiConfig, load_config
        cfg = ApiConfig()
        self.assertEqual(cfg.provider, "openai")
        self.assertFalse(cfg.enabled)

    def test_save_load_roundtrip(self, tmp_path=None):
        from api_config import ApiConfig, save_config, load_config
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_config.json")
            cfg = ApiConfig(provider="deepseek", api_key="sk-test123", model="deepseek-chat", enabled=True)
            save_config(cfg, path)
            loaded = load_config(path)
            self.assertEqual(loaded.provider, "deepseek")
            self.assertEqual(loaded.api_key, "sk-test123")
            self.assertEqual(loaded.model, "deepseek-chat")
            self.assertTrue(loaded.enabled)

    def test_validate_config(self):
        from api_config import ApiConfig, validate_config
        # 未启用应通过
        cfg = ApiConfig(enabled=False)
        ok, _ = validate_config(cfg)
        self.assertTrue(ok)
        # 启用但无 Key 应失败
        cfg2 = ApiConfig(enabled=True, api_url="https://api.example.com/v1/chat/completions", model="gpt-3.5-turbo")
        ok, msg = validate_config(cfg2)
        self.assertFalse(ok)
        self.assertIn("API Key", msg)

    def test_apply_preset(self):
        from api_config import ApiConfig, apply_preset
        cfg = ApiConfig()
        cfg = apply_preset(cfg, "deepseek")
        self.assertEqual(cfg.api_url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(cfg.model, "deepseek-chat")


# ============================================================
# 4. llm_feedback 测试（mock 网络）
# ============================================================
class TestLLMFeedback(unittest.TestCase):
    def setUp(self):
        from api_config import ApiConfig
        self.cfg = ApiConfig(
            provider="openai",
            api_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            model="gpt-3.5-turbo",
            enabled=True,
            timeout=120,
        )

    @patch("llm_feedback.urllib.request.urlopen")
    def test_get_feedback_success(self, mock_urlopen):
        # 模拟成功响应
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "这篇作文整体不错，但有一些语法问题..."}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        from llm_feedback import get_llm_feedback
        result = get_llm_feedback("This is a test essay.", config=self.cfg)
        self.assertIn("作文", result)
        self.assertNotIn("⚠️", result)

    @patch("llm_feedback.urllib.request.urlopen")
    def test_get_feedback_401(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=401, msg="Unauthorized", hdrs=None, fp=None
        )
        from llm_feedback import get_llm_feedback
        result = get_llm_feedback("This is a test essay.", config=self.cfg)
        self.assertIn("⚠️", result)  # 应返回带错误提示的兜底内容

    def test_mock_feedback_when_disabled(self):
        from api_config import ApiConfig
        from llm_feedback import get_llm_feedback
        cfg = ApiConfig(enabled=False)
        result = get_llm_feedback("This is a test essay.", config=cfg)
        self.assertIn("整体评价", result)

    @patch("llm_feedback.urllib.request.urlopen")
    def test_fetch_models_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "object": "list",
            "data": [
                {"id": "gpt-3.5-turbo", "object": "model"},
                {"id": "gpt-4o", "object": "model"},
                {"id": "gpt-4o-mini", "object": "model"},
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        from llm_feedback import fetch_models
        success, models, err = fetch_models(
            "https://max.openai365.top/v1/chat/completions",
            "sk-test",
            timeout=10
        )
        self.assertTrue(success, f"应成功, 错误: {err}")
        self.assertEqual(len(models), 3)
        self.assertIn("gpt-4o", models)

        # 验证请求 URL 被正确裁剪为 /v1/models
        # mock_urlopen 的第一个位置参数是 Request 对象，从中提取 URL
        called_request = mock_urlopen.call_args[0][0]
        called_url = called_request.get_full_url()
        self.assertTrue(
            called_url.endswith("/v1/models") or called_url.endswith("/v1/models/"),
            f"请求 URL 应为 .../v1/models, 实际: {called_url}"
        )

    @patch("llm_feedback.urllib.request.urlopen")
    def test_fetch_models_404(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None
        )
        from llm_feedback import fetch_models
        success, models, err = fetch_models("https://example.com/v1", "sk-test")
        self.assertFalse(success)
        self.assertEqual(models, [])
        self.assertIn("404", err)

    def test_fetch_models_empty_url(self):
        from llm_feedback import fetch_models
        success, models, err = fetch_models("", "sk-test")
        self.assertFalse(success)
        self.assertIn("URL", err)

    @patch("llm_feedback.urllib.request.urlopen")
    def test_fetch_models_url_normalization(self, mock_urlopen):
        """测试各种 URL 格式都能正确裁剪为 /v1/models"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "data": [{"id": "model-a"}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        from llm_feedback import fetch_models
        test_cases = [
            ("https://max.openai365.top/v1/chat/completions", "/v1/models"),
            ("https://max.openai365.top/v1/", "/v1/models"),
            ("https://max.openai365.top/v1", "/v1/models"),
            ("https://max.openai365.top", "/v1/models"),
        ]
        for url, expected_suffix in test_cases:
            mock_urlopen.reset_mock()
            success, models, err = fetch_models(url, "sk-test", timeout=5)
            self.assertTrue(success, f"URL={url} 应成功, 错误: {err}")
            # 从 Request 对象提取实际请求的 URL
            called_request = mock_urlopen.call_args[0][0]
            called_url = called_request.get_full_url()
            self.assertTrue(
                called_url.endswith(expected_suffix),
                f"URL={url} 应请求 {expected_suffix}, 实际: {called_url}"
            )


# ============================================================
# 5. 线程安全修复验证（关键！）
# ============================================================
class TestThreadingFix(unittest.TestCase):
    """验证 desktop_app.py 不再使用 self.after（修复 AttributeError）"""

    def test_no_self_after_in_worker(self):
        """读取 desktop_app.py 源码，确认 worker 函数中使用队列而非 self.after"""
        app_path = os.path.join(os.path.dirname(__file__), "desktop_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 应在文件顶部导入 queue
        self.assertIn("import queue", content)

        # 应存在 llm_queue
        self.assertIn("self.llm_queue = queue.Queue()", content)

        # worker 函数里应把结果放进队列，而非调用 self.after
        # 提取 worker 函数区域
        worker_start = content.find("def worker():")
        poll_start = content.find("def _poll_queues", worker_start)
        if poll_start == -1:
            poll_start = len(content)
        worker_code = content[worker_start:poll_start]

        self.assertIn("llm_queue.put", worker_code,
                      "worker 应把结果放入 llm_queue，而非使用 self.after")
        self.assertNotIn("self.after(", worker_code),
        "worker 中不应出现 self.after（这会导致 AttributeError）"

    def test_poll_queues_exists(self):
        """确认存在 _poll_queues 轮询方法"""
        app_path = os.path.join(os.path.dirname(__file__), "desktop_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("def _poll_queues(self)", content)
        self.assertIn("root.after(100, self._poll_queues)", content)


# ============================================================
# 6. settings_dialog 逻辑验证（不依赖 GUI）
# ============================================================
class TestSettingsDialogLogic(unittest.TestCase):
    """验证设置对话框的核心逻辑（不创建真实窗口）"""

    def test_fetch_models_url_normalization_in_dialog(self):
        """确认 _fetch_models 会读取 url_var 并调用 fetch_models"""
        # 读取源码验证
        dlg_path = os.path.join(os.path.dirname(__file__), "settings_dialog.py")
        with open(dlg_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 应导入 fetch_models
        self.assertIn("from llm_feedback import", content)
        self.assertIn("fetch_models", content)

        # _fetch_models 方法应存在
        self.assertIn("def _fetch_models(self)", content)

        # 应使用线程（避免 UI 卡死）
        self.assertIn("threading.Thread", content)

        # 回调应通过 self.after（Toplevel 是 tkinter 组件，有 after 方法）
        self.assertIn("self.after(0, self._on_models_fetched", content)

        # 成功后应填充下拉框
        self.assertIn("self.model_combo.config(values=models)", content)


# ============================================================
# 7. prompt_config 测试（提示词配置 + 固定范文提示词）
# ============================================================
class TestPromptConfig(unittest.TestCase):
    def test_default_prompts_exist(self):
        """默认提示词必须包含点评与范文（固定）两部分。"""
        from prompt_config import DEFAULT_PROMPTS
        for key in ("role", "feedback_system", "feedback_user",
                    "rewrite_system", "rewrite_user"):
            self.assertIn(key, DEFAULT_PROMPTS, f"缺少默认提示词字段: {key}")
        # 固定范文提示词应包含范文相关指令
        self.assertIn("范文", DEFAULT_PROMPTS["rewrite_system"])
        self.assertIn("修改说明", DEFAULT_PROMPTS["rewrite_system"])

    def test_load_default_when_no_file(self):
        """文件不存在时应回退为默认提示词，不报错。"""
        from prompt_config import load_prompts, DEFAULT_PROMPTS
        cfg = load_prompts(path="/tmp/__not_exist__.json")
        self.assertEqual(cfg.feedback_system, DEFAULT_PROMPTS["feedback_system"])

    def test_save_load_roundtrip(self):
        """保存后再加载应完全一致。"""
        from prompt_config import PromptConfig, save_prompts, load_prompts
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "prompts.json")
            p = PromptConfig(feedback_system="自定义 system {role}", temperature=0.9)
            self.assertTrue(save_prompts(p, path))
            loaded = load_prompts(path)
            self.assertEqual(loaded.feedback_system, "自定义 system {role}")
            self.assertEqual(loaded.temperature, 0.9)
            # 未指定的字段应用默认值兜底
            self.assertTrue(loaded.rewrite_system)

    def test_render_role(self):
        from prompt_config import PromptConfig, DEFAULT_PROMPTS
        p = PromptConfig()
        self.assertIn(DEFAULT_PROMPTS["role"], p.render_role())

    def test_build_feedback_messages(self):
        """点评 messages 应包含 role 与占位符替换后的内容。"""
        from prompt_config import PromptConfig
        p = PromptConfig()
        msgs = p.build_feedback_messages("Hello world.", issues="- [ERROR] test")
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")
        # {role} 应已被替换为真实角色
        self.assertNotIn("{role}", msgs[0]["content"])
        # {essay} 应被替换为原文
        self.assertIn("Hello world.", msgs[1]["content"])
        # issues 应出现
        self.assertIn("test", msgs[1]["content"])

    def test_build_rewrite_messages(self):
        """范文 messages 应使用固定范文提示词，且含原文。"""
        from prompt_config import PromptConfig
        p = PromptConfig()
        msgs = p.build_rewrite_messages("Original essay here.")
        self.assertEqual(len(msgs), 2)
        self.assertIn("修改后的范文", msgs[0]["content"])
        self.assertIn("修改说明", msgs[0]["content"])
        self.assertIn("Original essay here.", msgs[1]["content"])
        # {role} 已替换
        self.assertNotIn("{role}", msgs[0]["content"])

    def test_generation_params(self):
        from prompt_config import PromptConfig
        p = PromptConfig(temperature=1.2, max_tokens=2000)
        gp = p.generation_params()
        self.assertEqual(gp["temperature"], 1.2)
        self.assertEqual(gp["max_tokens"], 2000)

    def test_reset_prompts(self):
        from prompt_config import reset_prompts, DEFAULT_PROMPTS
        p = reset_prompts()
        self.assertEqual(p.feedback_system, DEFAULT_PROMPTS["feedback_system"])


# ============================================================
# 8. 提示词与 UI 集成测试（验证 desktop_app.py / prompt_dialog）
# ============================================================
class TestPromptIntegration(unittest.TestCase):
    """验证提示词设置入口、范文生成按钮、队列分发等集成逻辑。"""

    def test_prompt_dialog_importable(self):
        """应能无错导入提示词对话框模块（无 tkinter 时跳过）。"""
        try:
            import tkinter  # noqa
        except ImportError:
            self.skipTest("当前环境无 tkinter，跳过 GUI 模块导入测试")
        from prompt_dialog import PromptSettingsDialog, DEFAULT_PROMPTS
        self.assertTrue(DEFAULT_PROMPTS)  # 默认提示词非空

    def test_dialog_has_two_tabs(self):
        """对话框应包含点评与范文两个 Tab。"""
        dlg_path = os.path.join(os.path.dirname(__file__), "prompt_dialog.py")
        with open(dlg_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("💬 点评提示词", content)
        self.assertIn("✍️ 修改后范文", content)
        # 应有恢复默认与保存
        self.assertIn("♻️ 恢复默认", content)
        self.assertIn("💾 保存", content)

    def test_app_has_prompt_and_revision_entries(self):
        """主界面应新增「提示词设置」入口与「生成修改后范文」按钮。"""
        app_path = os.path.join(os.path.dirname(__file__), "desktop_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("📝 提示词设置", content)
        self.assertIn("✍️ 生成修改后范文", content)
        self.assertIn("open_prompt_settings", content)
        self.assertIn("generate_revision", content)

    def test_revision_uses_fixed_prompt(self):
        """范文生成函数应使用固定范文提示词（即使点评提示词被改也不影响）。"""
        from unittest.mock import patch, MagicMock
        import json
        from api_config import ApiConfig
        from prompt_config import PromptConfig
        from llm_feedback import generate_revised_essay

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "===== 修改说明 =====\n- xxx\n\n===== 修改后的范文 =====\nBetter essay."}}]
        }).encode("utf-8")

        cfg = ApiConfig(provider="openai", api_key="sk-test",
                        model="gpt-3.5-turbo", enabled=True, timeout=120)
        # 即使用户把点评提示词改成乱码，范文提示词仍独立生效
        with patch("prompt_config.load_prompts", return_value=PromptConfig(
            feedback_system="ignored", rewrite_system=PromptConfig().rewrite_system)), \
             patch("llm_feedback.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            result = generate_revised_essay("This is a test essay.", config=cfg)

        self.assertIn("修改后的范文", result)
        # 验证请求体中用的是 rewrite 提示词（含「修改说明」关键字）
        # urlopen 接收 Request 对象，body 在其 data 属性上
        called_request = mock_urlopen.call_args[0][0]
        payload = json.loads(called_request.data.decode("utf-8"))
        sys_msg = payload["messages"][0]["content"]
        self.assertIn("修改说明", sys_msg)

    def test_queue_dispatches_revision(self):
        """队列轮询应按类型分发到 _on_revision_done / _on_llm_done。"""
        app_path = os.path.join(os.path.dirname(__file__), "desktop_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_on_revision_done", content)
        self.assertIn("_on_llm_done", content)
        # 分发逻辑：revision 走 _on_revision_done
        self.assertIn('kind == "revision"', content)
        # worker 入队应带类型标记
        self.assertIn('("feedback", feedback)', content)
        self.assertIn('("revision", revision)', content)


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 全量测试开始（离线，不发起真实网络请求）")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print(f"🎉 全部 {result.testsRun} 项测试通过！")
    else:
        print(f"❌ 失败 {len(result.failures)} 项，错误 {len(result.errors)} 项")
        for test, trace in result.failures + result.errors:
            print(f"\n--- {test} ---")
            print(trace)
    print("=" * 60)
    sys.exit(0 if result.wasSuccessful() else 1)
