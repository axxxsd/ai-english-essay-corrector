# -*- coding: utf-8 -*-
"""
智能英语作文批改系统 - 桌面版 (Tkinter)
仅依赖 Python 标准库，无需安装第三方包。
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import re
import threading
import queue

from grammar_checker import GrammarChecker
from scorer import Scorer
from api_config import load_config, validate_config, ApiConfig
from llm_feedback import get_llm_feedback, fetch_models, generate_revised_essay
from prompt_dialog import PromptSettingsDialog


class EssayCorrectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("智能英语作文批改系统")
        self.root.geometry("1000x780")

        self.checker = GrammarChecker()
        self.scorer = Scorer()

        # 线程安全队列：子线程把结果放进这里，主线程轮询取出
        self.llm_queue = queue.Queue()
        self.model_queue = queue.Queue()

        self._build_ui()

        # 启动队列轮询（必须在主线程执行，tkinter 操作才安全）
        self.root.after(100, self._poll_queues)

    # ============================================================
    # UI 构建
    # ============================================================
    def _build_ui(self):
        # 顶部标题
        title = tk.Label(
            self.root, text="✍️  智能英语作文批改系统",
            font=("Microsoft YaHei", 18, "bold"), fg="#2c3e50"
        )
        title.pack(pady=10)

        # 输入区
        input_frame = ttk.LabelFrame(self.root, text="📝 请输入英语作文", padding=10)
        input_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.text_input = scrolledtext.ScrolledText(
            input_frame, wrap="word", font=("Consolas", 12), height=12
        )
        self.text_input.pack(fill="both", expand=True)

        # 按钮区
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=8)

        ttk.Button(btn_frame, text="🔍 开始批改", command=self.analyze, width=15).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="🧹 清空", command=self.clear, width=12).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="📋 示例作文", command=self.load_sample, width=13).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="⚙️ API 设置", command=self.open_api_settings, width=14).pack(side="right", padx=8)

        # 结果区（标签页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=10)

        # ---- 评分结果 ----
        self.score_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.score_frame, text="📊 评分结果")
        self.score_label = tk.Label(
            self.score_frame, text="等待批改...",
            font=("Microsoft YaHei", 14), justify="left", anchor="nw", padx=15, pady=15
        )
        self.score_label.pack(fill="both", expand=True)

        # ---- 问题清单 ----
        self.issue_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.issue_frame, text="⚠️ 问题清单")
        self.issue_text = scrolledtext.ScrolledText(
            self.issue_frame, wrap="word", font=("Consolas", 11)
        )
        self.issue_text.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 原文高亮 ----
        self.highlight_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.highlight_frame, text="🎨 原文标注")
        self.highlight_text = scrolledtext.ScrolledText(
            self.highlight_frame, wrap="word", font=("Consolas", 12)
        )
        self.highlight_text.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 大模型点评 ----
        self.llm_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.llm_frame, text="🤖 大模型点评")

        llm_toolbar = ttk.Frame(self.llm_frame)
        llm_toolbar.pack(fill="x", padx=5, pady=(5, 0))

        self.llm_fetch_btn = ttk.Button(
            llm_toolbar, text="🚀 获取大模型点评", command=self.fetch_llm_feedback, width=20
        )
        self.llm_fetch_btn.pack(side="left", padx=5)

        self.revise_btn = ttk.Button(
            llm_toolbar, text="✍️ 生成修改后范文", command=self.generate_revision, width=20
        )
        self.revise_btn.pack(side="left", padx=5)

        ttk.Separator(llm_toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(
            llm_toolbar, text="📝 提示词设置", command=self.open_prompt_settings, width=14
        ).pack(side="left", padx=5)

        self.llm_status_var = tk.StringVar(value="")
        ttk.Label(
            llm_toolbar, textvariable=self.llm_status_var, foreground="#888888"
        ).pack(side="left", padx=10)

        self.llm_text = scrolledtext.ScrolledText(
            self.llm_frame, wrap="word", font=("Microsoft YaHei", 11)
        )
        self.llm_text.pack(fill="both", expand=True, padx=5, pady=5)
        self._refresh_llm_status()

    # ============================================================
    # 基础功能
    # ============================================================
    def load_sample(self):
        sample = (
            "Nowdays, with the development of society, more and more students "
            "choose to study abroad. It is a important decision for they. "
            "Some people think that study abroad can help them get a better job. "
            "But other people worry about the cost becuase it is alot of money. "
            "In my opinion, the advantages are more better than disadvantages. "
            "Students can learn a new language and experience different culture. "
            "they also become more independent. I think every student should has "
            "a chance to go oversea if they want."
        )
        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", sample)

    def clear(self):
        self.text_input.delete("1.0", "end")
        self.score_label.config(text="等待批改...")
        self.issue_text.delete("1.0", "end")
        self.highlight_text.delete("1.0", "end")

    def analyze(self):
        essay = self.text_input.get("1.0", "end").strip()
        if not essay:
            messagebox.showwarning("提示", "请先输入或粘贴英语作文！")
            return

        issues = self.checker.check(essay)
        scores = self.scorer.score(essay, issues)
        total = scores["total"]

        grade = self._grade(total)
        score_str = (
            f"总  分：{total:.0f} / 100   [{grade}]\n\n"
            f"语法准确性：{scores['grammar']:.0f} / 30\n"
            f"词汇丰富度：{scores['vocab']:.0f} / 25\n"
            f"结构连贯性：{scores['structure']:.0f} / 25\n"
            f"内容切题度：{scores['content']:.0f} / 20\n\n"
            f"词数：{scores['stats']['words']}   句数：{scores['stats']['sentences']}   "
            f"平均句长：{scores['stats']['avg_sentence_len']:.1f}"
        )
        self.score_label.config(text=score_str)

        self.issue_text.delete("1.0", "end")
        if not issues:
            self.issue_text.insert("end", "🎉 未发现明显问题，写得很棒！")
        else:
            for i, iss in enumerate(issues, 1):
                text = (
                    f"{i}. [{iss['severity'].upper()}] {iss['message']}\n"
                    f"   原文片段：\"{iss['context']}\"\n"
                    f"   建议修改：{iss['suggestion']}\n\n"
                )
                self.issue_text.insert("end", text)

        self._highlight(essay, issues)
        self.notebook.select(0)

    def _highlight(self, essay, issues):
        self.highlight_text.delete("1.0", "end")
        self.highlight_text.insert("end", essay)

        markers = sorted(
            [(iss["start"], iss["end"], iss["severity"]) for iss in issues],
            key=lambda x: x[0], reverse=True
        )
        for start, end, severity in markers:
            start_idx = self._char_to_index(start)
            end_idx = self._char_to_index(end)
            tag = "error" if severity == "error" else "warning"
            self.highlight_text.tag_add(tag, start_idx, end_idx)

        self.highlight_text.tag_config("error", background="#ffcccc", underline=True)
        self.highlight_text.tag_config("warning", background="#fff3cd")

    def _char_to_index(self, char_pos):
        content = self.highlight_text.get("1.0", "end-1c")
        lines = content[:char_pos].split("\n")
        line = len(lines)
        col = len(lines[-1])
        return f"{line}.{col}"

    def _grade(self, total):
        if total >= 90:
            return "A+ 优秀"
        elif total >= 80:
            return "A 良好"
        elif total >= 70:
            return "B 中等"
        elif total >= 60:
            return "C 及格"
        else:
            return "D 需改进"

    # ============================================================
    # API 设置
    # ============================================================
    def open_api_settings(self):
        from settings_dialog import ApiSettingsDialog
        ApiSettingsDialog(self.root)
        # 设置窗口关闭后刷新状态
        self.root.after(200, self._refresh_llm_status)

    # ============================================================
    # 提示词设置
    # ============================================================
    def open_prompt_settings(self):
        """打开「📝 提示词设置」对话框。"""
        PromptSettingsDialog(self.root)

    def _refresh_llm_status(self):
        self.llm_text.delete("1.0", "end")
        cfg = load_config()
        ok, msg = validate_config(cfg)
        if cfg.enabled and ok:
            status = (
                "🟢 大模型深度点评已启用\n\n"
                f"服务商：{cfg.provider}\n"
                f"模型：{cfg.model}\n"
                f"接口：{cfg.api_url}\n\n"
                "点击上方「🚀 获取大模型点评」按钮，"
                "即可调用接口生成 AI 深度点评。"
            )
            self.llm_status_var.set("就绪")
            self.llm_fetch_btn.config(state="normal")
        elif cfg.enabled and not ok:
            status = (
                "🟡 已启用大模型点评，但配置不完整：\n\n"
                f"{msg}\n\n"
                "请点击右上角「⚙️ API 设置」补全接口信息。"
            )
            self.llm_status_var.set("配置不完整")
            self.llm_fetch_btn.config(state="disabled")
        else:
            status = (
                "⚪ 大模型深度点评当前未启用。\n\n"
                "如需使用 AI 深度点评功能，请点击右上角「⚙️ API 设置」，"
                "填写接口地址与 API Key 后启用。"
            )
            self.llm_status_var.set("未启用")
            self.llm_fetch_btn.config(state="disabled")
        self.llm_text.insert("1.0", status)

    # ============================================================
    # 大模型点评（子线程 + 队列）
    # ============================================================
    def fetch_llm_feedback(self):
        essay = self.text_input.get("1.0", "end").strip()
        if not essay:
            messagebox.showwarning("提示", "请先输入或粘贴英语作文！")
            return

        cfg = load_config()
        ok, msg = validate_config(cfg)
        if not (cfg.enabled and ok):
            messagebox.showwarning(
                "无法调用",
                "大模型点评未就绪：\n" + msg + "\n\n请先在「⚙️ API 设置」中配置并启用。",
            )
            return

        # 构造问题摘要，作为附加上下文
        issues = self.checker.check(essay)
        issue_summary = "\n".join(
            f"- [{i['severity'].upper()}] {i['message']}（原文：{i['context']}）"
            for i in issues[:15]
        )
        extra = f"\n\n【本地已检出的问题参考】\n{issue_summary}" if issue_summary else ""

        self.llm_fetch_btn.config(state="disabled", text="⏳ 点评中...")
        self.llm_status_var.set("正在调用接口，请稍候...")
        self.llm_text.delete("1.0", "end")
        self.llm_text.insert("1.0", "⏳ 正在请求大模型接口，预计数秒...\n\n" + essay)

        def worker():
            try:
                feedback = get_llm_feedback(essay + extra, config=cfg)
            except Exception as e:
                feedback = f"⚠️ 调用异常：{e}"
            self.llm_queue.put(("feedback", feedback))

        threading.Thread(target=worker, daemon=True).start()

    def _on_llm_done(self, feedback: str):
        """点评完成回调（始终在主线程执行）。"""
        self.llm_fetch_btn.config(state="normal", text="🚀 获取大模型点评")
        self.llm_text.delete("1.0", "end")
        self.llm_text.insert("1.0", feedback)
        self.notebook.select(self.notebook.index(self.llm_frame))
        if feedback.startswith("⚠️"):
            self.llm_status_var.set("调用失败（见上文）")
        else:
            self.llm_status_var.set("点评完成")

    # ============================================================
    # 生成修改后范文
    # ============================================================
    def generate_revision(self):
        """点击「✍️ 生成修改后范文」：使用固定范文提示词生成修改后的完整范文。"""
        essay = self.text_input.get("1.0", "end").strip()
        if not essay:
            messagebox.showwarning("提示", "请先输入或粘贴英语作文！")
            return

        cfg = load_config()
        if not (cfg.enabled and cfg.api_key.strip()):
            # 未配置 API 时走本地兜底
            pass

        self.revise_btn.config(state="disabled", text="⏳ 生成中...")
        self.llm_status_var.set("正在生成修改后范文，请稍候...")
        self.llm_text.delete("1.0", "end")
        self.llm_text.insert("1.0", "⏳ 正在请求大模型生成修改后的范文，预计数十秒...\n\n" + essay)
        self.notebook.select(self.notebook.index(self.llm_frame))

        def worker():
            try:
                revision = generate_revised_essay(essay, config=cfg)
            except Exception as e:
                revision = f"⚠️ 生成异常：{e}"
            self.llm_queue.put(("revision", revision))

        threading.Thread(target=worker, daemon=True).start()

    def _on_revision_done(self, revision: str):
        """范文生成完成回调（始终在主线程执行）。"""
        self.revise_btn.config(state="normal", text="✍️ 生成修改后范文")
        self.llm_text.delete("1.0", "end")
        self.llm_text.insert("1.0", revision)
        self.notebook.select(self.notebook.index(self.llm_frame))
        if revision.startswith("⚠️"):
            self.llm_status_var.set("范文生成失败（见上文）")
        else:
            self.llm_status_var.set("范文已生成")

    # ============================================================
    # 队列轮询（主线程安全更新 UI）
    # ============================================================
    def _poll_queues(self):
        """定期检查队列，把子线程的结果安全地更新到界面上。"""
        try:
            while True:
                item = self.llm_queue.get_nowait()
                # 兼容旧格式（纯字符串）与新格式（type, content）元组
                if isinstance(item, tuple) and len(item) == 2:
                    kind, content = item
                    if kind == "revision":
                        self._on_revision_done(content)
                    else:
                        self._on_llm_done(content)
                else:
                    self._on_llm_done(item)
        except queue.Empty:
            pass

        try:
            while True:
                result = self.model_queue.get_nowait()
                self._on_models_done(result)
        except queue.Empty:
            pass

        self.root.after(100, self._poll_queues)

    # ============================================================
    # 供 settings_dialog 使用的模型获取入口
    # ============================================================
    def fetch_models_async(self, base_url: str, api_key: str, timeout: int, callback):
        """异步获取模型列表，callback(success, models, error_msg) 在主线程被调用。"""
        def worker():
            try:
                success, models, err = fetch_models(base_url, api_key, timeout)
                self.model_queue.put((callback, success, models, err))
            except Exception as e:
                self.model_queue.put((callback, False, [], str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_models_done(self, result):
        """分发模型列表结果到对应的 callback（主线程执行）。"""
        callback, success, models, err = result
        try:
            callback(success, models, err)
        except Exception as e:
            print(f"[模型列表回调错误] {e}")


def main():
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.333)
    except Exception:
        pass
    app = EssayCorrectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
