# -*- coding: utf-8 -*-
"""
prompt_dialog.py
提示词设置对话框：编辑「点评提示词」与「修改后范文提示词」（固定）。
配置持久化到 config/prompts.json，由 prompt_config.py 管理。
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from prompt_config import (
    PromptConfig, DEFAULT_PROMPTS,
    load_prompts, save_prompts, reset_prompts,
)


class PromptSettingsDialog(tk.Toplevel):
    """提示词设置窗口（模态对话框）。"""

    # 占位符说明文字（在界面底部展示，提示用户可用变量）
    PLACEHOLDER_HINT = (
        "可用占位符：  {role} = 角色设定   {essay} = 作文原文   "
        "{issues} = 本地已检出的问题摘要（点评模板用）\n"
        "修改提示词时可引用上述变量，程序会自动替换；若留空则回退为默认提示词。"
    )

    def __init__(self, master=None):
        super().__init__(master)
        self.title("📝 模型提示词设置")
        self.geometry("720x660")
        self.resizable(True, True)
        self.grab_set()  # 模态：打开时禁止操作主窗口

        # 加载已有配置（用深拷贝，取消时不污染原配置）
        self.prompts = load_prompts()

        self._build_ui()
        self._load_to_ui()

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # 标题
        ttk.Label(
            container, text="模型提示词配置",
            font=("Microsoft YaHei", 14, "bold")
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(
            container,
            text="在此自定义 AI 的「点评方式」与「修改后范文」提示词。"
                 "配置仅保存在本地 config/prompts.json，不会上传。",
            wraplength=680, foreground="#666666", justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # 用 Notebook 分成两个 Tab，避免界面过长
        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        # ---- Tab 1：点评提示词 ----
        fb_frame = ttk.Frame(notebook, padding=10)
        notebook.add(fb_frame, text="💬 点评提示词")
        self._build_feedback_tab(fb_frame)

        # ---- Tab 2：修改后范文提示词（固定提示词）----
        rw_frame = ttk.Frame(notebook, padding=10)
        notebook.add(rw_frame, text="✍️ 修改后范文（固定）")
        self._build_rewrite_tab(rw_frame)

        # 占位符说明
        ttk.Label(
            container, text=self.PLACEHOLDER_HINT,
            wraplength=680, foreground="#888888", font=("", 9), justify="left",
        ).pack(anchor="w", pady=(8, 5))

        # 校验提示区
        self.hint_var = tk.StringVar(value="")
        self.hint_label = ttk.Label(
            container, textvariable=self.hint_var,
            foreground="#d9534f", wraplength=680, justify="left",
        )
        self.hint_label.pack(anchor="w", pady=(5, 5))

        # 底部按钮区
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(
            btn_frame, text="♻️ 恢复默认", command=self._reset_defaults, width=14
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame, text="💾 保存", command=self._save, width=12
        ).pack(side="right", padx=5)

        ttk.Button(
            btn_frame, text="取消", command=self.destroy, width=10
        ).pack(side="right", padx=5)

    def _build_feedback_tab(self, parent):
        """点评提示词：角色设定 + system + user 模板。"""
        # 角色设定（共用）
        ttk.Label(
            parent, text="角色设定（role，点评与范文共用）：",
            font=("", 10, "bold")
        ).pack(anchor="w")
        self.role_text = scrolledtext.ScrolledText(
            parent, wrap="word", font=("Microsoft YaHei", 10), height=4
        )
        self.role_text.pack(fill="both", expand=False, pady=(3, 8))

        # 点评 system
        ttk.Label(
            parent, text="点评 System 提示词（{role} 自动替换）：",
            font=("", 10, "bold")
        ).pack(anchor="w")
        self.fb_system_text = scrolledtext.ScrolledText(
            parent, wrap="word", font=("Microsoft YaHei", 10), height=9
        )
        self.fb_system_text.pack(fill="both", expand=True, pady=(3, 8))

        # 点评 user 模板
        ttk.Label(
            parent, text="点评 User 模板（{essay}=原文，{issues}=问题摘要）：",
            font=("", 10, "bold")
        ).pack(anchor="w")
        self.fb_user_text = scrolledtext.ScrolledText(
            parent, wrap="word", font=("Consolas", 10), height=6
        )
        self.fb_user_text.pack(fill="both", expand=True, pady=(3, 0))

    def _build_rewrite_tab(self, parent):
        """修改后范文提示词（固定提示词）：system + user 模板。"""
        ttk.Label(
            parent,
            text="⚙️ 固定提示词：AI 在点评后会据此生成一篇修改后的范文。"
                 "你可调整措辞，但建议保留「修改说明 + 修改后的范文」两段结构。",
            wraplength=660, foreground="#c07000", justify="left",
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            parent, text="范文 System 提示词（{role} 自动替换）：",
            font=("", 10, "bold")
        ).pack(anchor="w")
        self.rw_system_text = scrolledtext.ScrolledText(
            parent, wrap="word", font=("Microsoft YaHei", 10), height=13
        )
        self.rw_system_text.pack(fill="both", expand=True, pady=(3, 8))

        ttk.Label(
            parent, text="范文 User 模板（{essay}=原文）：",
            font=("", 10, "bold")
        ).pack(anchor="w")
        self.rw_user_text = scrolledtext.ScrolledText(
            parent, wrap="word", font=("Consolas", 10), height=5
        )
        self.rw_user_text.pack(fill="both", expand=True, pady=(3, 0))

        # 生成参数
        param_frame = ttk.Frame(parent)
        param_frame.pack(fill="x", pady=(8, 0))

        ttk.Label(param_frame, text="temperature：").pack(side="left")
        self.temperature_var = tk.StringVar(value="0.7")
        ttk.Spinbox(
            param_frame, textvariable=self.temperature_var,
            from_=0.0, to=2.0, increment=0.1, width=8,
        ).pack(side="left", padx=5)

        # max_tokens 上限放开到 16000，默认范文生成给 6000，避免长文被截断；
        # 若接口上限更低（常见 2048/4096），以接口实际为准，届时可调小。
        ttk.Label(param_frame, text="max_tokens：").pack(side="left", padx=(15, 0))
        self.max_tokens_var = tk.StringVar(value="6000")
        ttk.Spinbox(
            param_frame, textvariable=self.max_tokens_var,
            from_=100, to=16000, increment=500, width=8,
        ).pack(side="left", padx=5)
        ttk.Label(
            param_frame, text="(范文生成，建议≥6000)", foreground="#888888", font=("", 8)
        ).pack(side="left", padx=(5, 0))

    # ---------------- 数据绑定 ----------------
    def _set_text(self, widget, text: str):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _get_text(self, widget) -> str:
        return widget.get("1.0", "end").strip()

    def _load_to_ui(self):
        """把配置对象的值填到界面控件。"""
        p = self.prompts
        self.role_text.insert("1.0", p.role)
        self._set_text(self.fb_system_text, p.feedback_system)
        self._set_text(self.fb_user_text, p.feedback_user)
        self._set_text(self.rw_system_text, p.rewrite_system)
        self._set_text(self.rw_user_text, p.rewrite_user)
        self.temperature_var.set(str(p.temperature))
        self.max_tokens_var.set(str(p.max_tokens))
        self._update_hint()

    def _ui_to_config(self) -> PromptConfig:
        """把界面控件的值读回配置对象（空值自动用默认兜底）。"""
        data = dict(DEFAULT_PROMPTS)  # 用默认值打底
        data["role"] = self._get_text(self.role_text) or DEFAULT_PROMPTS["role"]
        data["feedback_system"] = self._get_text(self.fb_system_text) or DEFAULT_PROMPTS["feedback_system"]
        data["feedback_user"] = self._get_text(self.fb_user_text) or DEFAULT_PROMPTS["feedback_user"]
        data["rewrite_system"] = self._get_text(self.rw_system_text) or DEFAULT_PROMPTS["rewrite_system"]
        data["rewrite_user"] = self._get_text(self.rw_user_text) or DEFAULT_PROMPTS["rewrite_user"]
        try:
            data["temperature"] = float(self.temperature_var.get())
        except (ValueError, TypeError):
            data["temperature"] = DEFAULT_PROMPTS["temperature"]
        try:
            data["max_tokens"] = int(float(self.max_tokens_var.get()))
        except (ValueError, TypeError):
            data["max_tokens"] = DEFAULT_PROMPTS["max_tokens"]
        return PromptConfig(**data)

    def _update_hint(self):
        """实时校验：检查必需占位符是否齐全。"""
        try:
            cfg = self._ui_to_config()
        except Exception as e:
            self.hint_var.set(f"⚠️ 参数格式有误：{e}")
            self.hint_label.config(foreground="#d9534f")
            return

        warnings = []
        # 必需占位符检查（仅警告，不阻止保存）
        if "{essay}" not in cfg.feedback_user:
            warnings.append("点评 User 模板缺少 {essay} 占位符")
        if "{essay}" not in cfg.rewrite_user:
            warnings.append("范文 User 模板缺少 {essay} 占位符")
        if "{role}" not in cfg.feedback_system or "{role}" not in cfg.rewrite_system:
            warnings.append("System 提示词建议保留 {role} 占位符")

        if warnings:
            self.hint_var.set("⚠️ " + "；".join(warnings))
            self.hint_label.config(foreground="#c07000")
        else:
            self.hint_var.set("✅ 提示词格式校验通过。")
            self.hint_label.config(foreground="#5cb85c")

    # ---------------- 按钮事件 ----------------
    def _reset_defaults(self):
        """恢复为内置默认提示词。"""
        if not messagebox.askyesno(
            "恢复默认", "确定要将所有提示词恢复为默认吗？", parent=self
        ):
            return
        self.prompts = reset_prompts()
        # 清空后重新填充
        for w in (self.role_text, self.fb_system_text, self.fb_user_text,
                  self.rw_system_text, self.rw_user_text):
            w.delete("1.0", "end")
        self._load_to_ui()
        messagebox.showinfo("已重置", "提示词已恢复为默认 ✅", parent=self)

    def _save(self):
        """保存配置到本地文件并关闭窗口（自动创建 config/ 目录，保存后回读校验）。"""
        cfg = self._ui_to_config()

        warnings = []
        if "{essay}" not in cfg.feedback_user:
            warnings.append("点评 User 模板缺少 {essay}")
        if "{essay}" not in cfg.rewrite_user:
            warnings.append("范文 User 模板缺少 {essay}")

        if save_prompts(cfg):
            # 回读校验：确认文件落盘成功
            try:
                from prompt_config import DEFAULT_PROMPTS_PATH
                reloaded = load_prompts(DEFAULT_PROMPTS_PATH)
                saved_tokens = int(reloaded.max_tokens)
                ok = True
            except Exception as e:
                ok = False
                saved_tokens = None
                print(f"[提示词回读校验失败] {e}")

            if ok:
                self.prompts = cfg
                msg = f"提示词配置已保存到本地 ✅\n(max_tokens = {saved_tokens})"
                if warnings:
                    msg += "\n\n⚠️ 注意：" + "；".join(warnings)
                messagebox.showinfo("已保存", msg, parent=self)
                self.destroy()
            else:
                messagebox.showerror(
                    "保存失败",
                    "配置已写入但回读校验失败，请检查 config/prompts.json 权限。",
                    parent=self,
                )
        else:
            messagebox.showerror(
                "保存失败",
                "无法写入配置文件。\n\n请检查：\n"
                "1. 程序目录是否有写入权限；\n"
                "2. config/ 目录是否被占用或设为只读。",
                parent=self,
            )


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    dlg = PromptSettingsDialog(root)
    root.mainloop()
