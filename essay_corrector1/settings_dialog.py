# -*- coding: utf-8 -*-
"""
settings_dialog.py
API 设置对话框：编辑接口 URL、API Key、模型等参数，支持自动获取模型列表。
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading

from api_config import ApiConfig, PROVIDER_PRESETS, load_config, save_config, validate_config
from llm_feedback import test_connection, fetch_models  # 真实调用 + 模型列表获取


class ApiSettingsDialog(tk.Toplevel):
    """API 设置窗口（模态对话框）。"""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("⚙️ API 接口设置")
        self.geometry("580x560")
        self.resizable(False, False)
        self.grab_set()  # 模态：打开时禁止操作主窗口

        # 加载已有配置
        self.config_obj = load_config()

        self._build_ui()
        self._load_to_ui()

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # 标题
        ttk.Label(
            container, text="大语言模型接口配置",
            font=("Microsoft YaHei", 14, "bold")
        ).pack(anchor="w", pady=(0, 10))

        # 说明文字
        ttk.Label(
            container,
            text="在此填写你自己的接口信息。配置仅保存在本地 config/api_config.json，不会上传。",
            wraplength=540, foreground="#666666",
        ).pack(anchor="w", pady=(0, 12))

        # 1. 服务商选择
        row1 = ttk.Frame(container)
        row1.pack(fill="x", pady=5)
        ttk.Label(row1, text="服务商：", width=14).pack(side="left")
        self.provider_var = tk.StringVar()
        presets = PROVIDER_PRESETS
        self.provider_combo = ttk.Combobox(
            row1, textvariable=self.provider_var,
            values=[p["label"] for p in presets.values()],
            state="readonly", width=36,
        )
        self.provider_combo.pack(side="left", padx=5)
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        # 2. 接口地址 URL
        row2 = ttk.Frame(container)
        row2.pack(fill="x", pady=5)
        ttk.Label(row2, text="接口地址 (URL)：", width=14).pack(side="left")
        self.url_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.url_var, width=54).pack(side="left", padx=5)

        # 3. API Key（密文显示，可切换可见）
        row3 = ttk.Frame(container)
        row3.pack(fill="x", pady=5)
        ttk.Label(row3, text="API Key：", width=14).pack(side="left")
        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(
            row3, textvariable=self.key_var, width=40, show="●"
        )
        self.key_entry.pack(side="left", padx=5)
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            row3, text="显示", variable=self.show_key_var,
            command=self._toggle_key_visibility, width=6,
        ).pack(side="left", padx=2)

        # 4. 模型名称（下拉框 + 手动输入 + 获取按钮）
        row4 = ttk.Frame(container)
        row4.pack(fill="x", pady=5)
        ttk.Label(row4, text="模型名称：", width=14).pack(side="left")

        self.model_var = tk.StringVar()
        # Combobox：既可下拉选择，也可手动输入
        self.model_combo = ttk.Combobox(
            row4, textvariable=self.model_var, width=30
        )
        self.model_combo.pack(side="left", padx=5)

        self.fetch_model_btn = ttk.Button(
            row4, text="🔄 获取模型列表", command=self._fetch_models, width=16
        )
        self.fetch_model_btn.pack(side="left", padx=5)

        # 模型列表获取状态提示
        self.model_hint_var = tk.StringVar(value="")
        self.model_hint_label = ttk.Label(
            container, textvariable=self.model_hint_var,
            foreground="#888888", wraplength=540, justify="left", font=("", 9),
        )
        self.model_hint_label.pack(anchor="w", padx=(90, 0), pady=(0, 5))

        # 5. 超时时间
        row5 = ttk.Frame(container)
        row5.pack(fill="x", pady=5)
        ttk.Label(row5, text="超时时间(秒)：", width=14).pack(side="left")
        self.timeout_var = tk.StringVar(value="120")
        ttk.Spinbox(
            row5, textvariable=self.timeout_var, from_=10, to=300, increment=10, width=10
        ).pack(side="left", padx=5)
        ttk.Label(
            row5, text="（大模型推理较慢，建议 ≥ 120）",
            foreground="#999999", font=("", 9)
        ).pack(side="left", padx=5)

        # 6. 启用开关
        row6 = ttk.Frame(container)
        row6.pack(fill="x", pady=8)
        self.enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            row6, text="启用大模型深度点评（开启后批改时将调用上述接口）",
            variable=self.enabled_var,
        ).pack(side="left")

        # 校验提示区（红字/绿字）
        self.hint_var = tk.StringVar(value="")
        self.hint_label = ttk.Label(
            container, textvariable=self.hint_var,
            foreground="#d9534f", wraplength=540, justify="left",
        )
        self.hint_label.pack(anchor="w", pady=(10, 5))

        # 底部按钮区
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(5, 0))

        self.test_btn = ttk.Button(
            btn_frame, text="🔌 测试连接", command=self._test_connection, width=14
        )
        self.test_btn.pack(side="left", padx=5)

        ttk.Button(
            btn_frame, text="♻️ 恢复默认", command=self._reset_defaults, width=14
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame, text="💾 保存", command=self._save, width=12
        ).pack(side="right", padx=5)

        ttk.Button(
            btn_frame, text="取消", command=self.destroy, width=10
        ).pack(side="right", padx=5)

    # ---------------- 事件处理 ----------------
    def _provider_key(self) -> str:
        """根据下拉框选中的 label 反查 provider key。"""
        label = self.provider_var.get()
        for key, preset in PROVIDER_PRESETS.items():
            if preset["label"] == label:
                return key
        return "custom"

    def _on_provider_change(self, event=None):
        """切换服务商时，自动填充对应的默认 URL 与模型（保留已填的 Key）。"""
        provider = self._provider_key()
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])
        self.url_var.set(preset["api_url"])
        self.model_var.set(preset["model"])
        # 清空已获取的模型列表
        self.model_combo.config(values=[])
        self.model_hint_var.set("")

    def _toggle_key_visibility(self):
        """切换 API Key 的明文/密文显示。"""
        self.key_entry.config(show="" if self.show_key_var.get() else "●")

    def _load_to_ui(self):
        """把配置对象的值填到界面控件上。"""
        cfg = self.config_obj
        self.provider_var.set(PROVIDER_PRESETS.get(cfg.provider, PROVIDER_PRESETS["custom"])["label"])
        self.url_var.set(cfg.api_url)
        self.key_var.set(cfg.api_key)
        self.model_var.set(cfg.model)
        self.timeout_var.set(str(cfg.timeout))
        self.enabled_var.set(cfg.enabled)
        # 把当前模型名放入下拉选项（即使只有一个）
        if cfg.model:
            self.model_combo.config(values=[cfg.model])
        self._update_hint()

    def _ui_to_config(self) -> ApiConfig:
        """把界面控件的值读回配置对象。"""
        self.config_obj.provider = self._provider_key()
        self.config_obj.api_url = self.url_var.get().strip()
        self.config_obj.api_key = self.key_var.get().strip()
        self.config_obj.model = self.model_var.get().strip()
        try:
            self.config_obj.timeout = int(float(self.timeout_var.get()))
        except (ValueError, TypeError):
            self.config_obj.timeout = 120
        self.config_obj.enabled = self.enabled_var.get()
        return self.config_obj

    def _update_hint(self):
        """实时校验并在界面上给出提示（不弹窗，更友好）。"""
        cfg = self._ui_to_config()
        ok, msg = validate_config(cfg)
        self.hint_label.config(
            foreground="#5cb85c" if ok else "#d9534f",
            text=("✅ " + msg) if ok else ("⚠️ " + msg),
        )

    def _reset_defaults(self):
        self.config_obj = ApiConfig()
        self._load_to_ui()

    # ============================================================
    # 获取模型列表（核心新增功能）
    # ============================================================
    def _fetch_models(self):
        """点击「🔄 获取模型列表」：本地校验后发起 GET /v1/models 请求（子线程），结果填充下拉框。"""
        # 临时读取当前 UI 值（不覆盖配置对象的其他字段）
        base_url = self.url_var.get().strip()
        api_key = self.key_var.get().strip()
        try:
            timeout = int(float(self.timeout_var.get()))
        except (ValueError, TypeError):
            timeout = 10

        if not base_url:
            messagebox.showwarning("无法获取", "请先填写接口地址（URL）。", parent=self)
            return
        if not api_key:
            messagebox.showwarning("无法获取", "请先填写 API Key。", parent=self)
            return

        # UI 进入加载状态
        self.fetch_model_btn.config(state="disabled", text="⏳ 获取中...")
        self.model_hint_var.set("⏳ 正在请求模型列表，请稍候（若超时请检查地址/Key）...")
        self.model_hint_label.config(foreground="#888888")

        def worker():
            try:
                success, models, err = fetch_models(base_url, api_key, timeout=timeout)
                self.after(0, self._on_models_fetched, success, models, err)
            except Exception as e:
                self.after(0, self._on_models_fetched, False, [], str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_models_fetched(self, success: bool, models: list, err: str):
        """模型列表获取完成回调（主线程执行）。成功填充下拉框，失败给出提示。"""
        self.fetch_model_btn.config(state="normal", text="🔄 获取模型列表")

        if success and models:
            # 填充下拉选项
            self.model_combo.config(values=models)
            # 自动选中第一个（优先保留当前已选的，如果它在列表里）
            current = self.model_var.get()
            if current and current in models:
                self.model_combo.set(current)
            else:
                self.model_combo.set(models[0])
                self.model_var.set(models[0])

            self.model_hint_var.set(
                f"✅ 成功获取 {len(models)} 个可用模型，已自动填充下拉框。"
            )
            self.model_hint_label.config(foreground="#5cb85c")
        else:
            self.model_hint_var.set(
                f"⚠️ 无法自动获取模型列表：{err}\n"
                f"💡 请手动输入模型名称（可联系服务商获取支持的模型清单）。"
            )
            self.model_hint_label.config(foreground="#d9534f")

    # ============================================================
    # 测试连接
    # ============================================================
    def _test_connection(self):
        """测试连接：本地校验通过后发起一次最小请求（子线程），结果回到主线程弹窗。"""
        self._update_hint()
        cfg = self._ui_to_config()
        ok, msg = validate_config(cfg)
        if not ok:
            messagebox.showwarning("无法测试", msg, parent=self)
            return

        # 按钮置灰 + 提示正在测试
        self.test_btn.config(state="disabled", text="⏳ 测试中...")
        self.hint_var.set("⏳ 正在连接接口，请稍候...")

        def worker():
            try:
                success, result = test_connection(cfg)
            except Exception as e:
                success, result = False, f"连接异常：{e}"
            self.after(0, self._on_test_done, success, result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, success: bool, msg: str):
        """测试完成后的回调（运行在主线程）。"""
        self.test_btn.config(state="normal", text="🔌 测试连接")
        self.hint_var.set(("✅ " + msg) if success else ("⚠️ " + msg))
        if success:
            messagebox.showinfo("连接成功", msg, parent=self)
        else:
            messagebox.showerror("连接失败", msg, parent=self)

    # ============================================================
    # 保存
    # ============================================================
    def _save(self):
        """保存配置到本地文件并关闭窗口。"""
        self._update_hint()
        cfg = self._ui_to_config()
        ok, msg = validate_config(cfg)
        if not ok:
            # 配置有误时给出提示，但仍允许用户保存（便于调试）
            if not messagebox.askyesno(
                "配置有误", msg + "\n\n是否仍要保存当前内容？", parent=self
            ):
                return
        if save_config(cfg):
            messagebox.showinfo("已保存", "API 配置已保存到本地 ✅", parent=self)
            self.destroy()
        else:
            messagebox.showerror("保存失败", "无法写入配置文件，请检查权限。", parent=self)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    dlg = ApiSettingsDialog(root)
    root.mainloop()
