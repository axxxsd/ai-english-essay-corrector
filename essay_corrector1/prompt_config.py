# -*- coding: utf-8 -*-
"""
prompt_config.py
模型提示词配置管理：点评提示词 + 修改后范文提示词（固定）。

提示词与 API 配置（api_config.py）解耦：前者是"怎么问"，后者是"问谁"。
内置一套默认提示词；用户可在界面修改，保存到本地 prompts.json，留空则回退默认。
"""
import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DEFAULT_PROMPTS_PATH = os.path.join(CONFIG_DIR, "prompts.json")


# 默认 / 固定提示词模板
DEFAULT_PROMPTS = {
    # 角色设定（点评与范文共用）
    "role": (
        "你是一位资深的英语教师（English teacher & IELTS/TOEFL examiner），"
        "擅长英语写作批改、语法纠错与地道表达润色。"
    ),

    # 点评提示词（system）
    # {role} 会自动替换为上面的角色设定
    "feedback_system": (
        "{role}\n\n"
        "请按以下四个维度，对下面这篇英语作文进行专业、具体、可操作的点评，使用中文撰写：\n"
        "1. 【语法准确性】时态、主谓一致、冠词、拼写、句法错误；\n"
        "2. 【词汇丰富度】用词准确性、搭配、高级词汇与短语的使用；\n"
        "3. 【结构连贯性】段落结构、逻辑衔接、连接词运用；\n"
        "4. 【内容深度】论点展开、论证细节、立意与结论。\n\n"
        "在结尾请给出 1-2 句的【总体修改方向】。"
    ),

    # 点评提示词（user 模板）
    # {essay} = 原文，{issues} = 本地已检出的问题摘要（可选）
    "feedback_user": (
        "请点评以下英语作文：\n\n"
        "【作文原文】\n{essay}\n\n"
        "{issues}"
        "请按上述维度输出点评。"
    ),

    # 修改后范文提示词（固定提示词）
    # 无论用户如何修改点评提示词，都要求模型输出润色后的完整范文。
    # {essay} = 原文
    "rewrite_system": (
        "{role}\n\n"
        "请基于下面的英语作文，完成两件事（严格按以下顺序、用分隔符区分）：\n\n"
        "第一步【修改说明】：用中文逐条列出你做的主要修改（语法纠错、词汇升级、句式优化、结构调整等），"
        "每条一行，格式为 \"- 原文：... → 改为：...\"。\n\n"
        "第二步【修改后的范文】：在修改说明之后，另起一段，以英文输出一篇润色后的完整范文。"
        "要求：\n"
        "- 保留原文的核心观点与立意，仅做语言层面的优化；\n"
        "- 修正所有语法、拼写、搭配错误；\n"
        "- 升级词汇与句型，提升表达地道性与多样性；\n"
        "- 保持段落结构清晰、逻辑连贯；\n"
        "- 字数与原文字数大致相当，不要大幅扩写或删减。\n\n"
        "【输出格式，请严格遵守】\n"
        "===== 修改说明 =====\n"
        "（此处写中文修改说明）\n\n"
        "===== 修改后的范文 =====\n"
        "（此处写英文润色后的完整范文）"
    ),

    "rewrite_user": (
        "请对以下英语作文进行修改，并按上述格式输出【修改说明】与【修改后的范文】：\n\n{essay}"
    ),

    # 生成参数
    # 生成「修改后范文」属于长文本输出，默认给 6000，避免被截断；
    # 若接口本身上限更低（常见 2048/4096），以接口实际为准。
    "temperature": 0.7,
    "max_tokens": 6000,
}


class PromptConfig:
    """提示词配置对象。"""
    def __init__(self, **kwargs):
        # 先用默认值打底，再用传入值覆盖，保证字段完整、向前兼容
        defaults = {k: v for k, v in DEFAULT_PROMPTS.items()}
        defaults.update({k: v for k, v in kwargs.items() if k in DEFAULT_PROMPTS})
        for k, v in defaults.items():
            setattr(self, k, v)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in DEFAULT_PROMPTS}

    @classmethod
    def from_dict(cls, data: dict) -> "PromptConfig":
        known = {k: v for k, v in data.items() if k in DEFAULT_PROMPTS}
        return cls(**known)

    def render_role(self) -> str:
        return self.role

    def build_feedback_messages(self, essay: str, issues: str = "") -> list:
        """构造「点评」请求用的 messages（OpenAI 兼容格式）。"""
        issues_block = issues.strip()
        user = self.feedback_user.format(
            essay=essay,
            issues=(issues_block + "\n\n") if issues_block else "",
        )
        return [
            {"role": "system", "content": self.feedback_system.format(role=self.role)},
            {"role": "user", "content": user},
        ]

    def build_rewrite_messages(self, essay: str) -> list:
        """构造「修改后范文」请求用的 messages（固定提示词生效处）。"""
        user = self.rewrite_user.format(essay=essay)
        return [
            {"role": "system", "content": self.rewrite_system.format(role=self.role)},
            {"role": "user", "content": user},
        ]

    def generation_params(self, model: str = "") -> dict:
        """
        返回生成参数（temperature / max_tokens）。
        多数模型对 max_tokens 有上限（常见 2048/4096，少数长文本模型达 8192+），
        这里按模型名做保守裁剪，避免盲目设 6000+ 触发接口报错。
        """
        requested = int(self.max_tokens)
        cap = _infer_max_tokens_cap(model or "") or 4096
        safe_tokens = min(requested, cap)
        return {
            "temperature": float(self.temperature),
            "max_tokens": safe_tokens,
        }


def _infer_max_tokens_cap(model: str) -> int:
    """
    根据模型名推断其 max_tokens 输出上限（保守估计）。
    返回 0 表示无法识别（调用方按默认 4096 处理）。
    """
    m = (model or "").lower()
    if not m:
        return 0
    if any(k in m for k in ("gpt-4", "gpt-4o", "deepseek", "qwen-max", "qwen-plus", "long")):
        return 8192
    if "16k" in m or "32k" in m or "128k" in m or "turbo-16" in m:
        return 8192
    if any(k in m for k in ("gpt-3.5-turbo-instruct", "curie", "babbage", "ada")):
        return 2048
    return 4096


def load_prompts(path: str = DEFAULT_PROMPTS_PATH) -> PromptConfig:
    """从 JSON 加载提示词配置；文件不存在或损坏时返回默认配置。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PromptConfig.from_dict(data)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return PromptConfig()


def save_prompts(prompts: PromptConfig, path: str = DEFAULT_PROMPTS_PATH) -> bool:
    """将提示词配置保存到 JSON。成功返回 True。"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prompts.to_dict(), f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def reset_prompts() -> PromptConfig:
    """返回一套全新的默认提示词（用于"恢复默认"）。"""
    return PromptConfig()
