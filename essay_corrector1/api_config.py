# -*- coding: utf-8 -*-
"""
api_config.py
API 接口配置管理：URL / Key / 模型名称等参数的保存、加载与校验。
配置以 JSON 文件形式持久化到本地。
"""
import json
import os
from dataclasses import dataclass, field, asdict


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, "api_config.json")

# 通用默认接口地址（OpenAI 兼容格式，用户可自行替换为任意兼容服务）
DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-3.5-turbo"


@dataclass
class ApiConfig:
    """API 配置数据模型，字段可由用户在界面上编辑。"""
    provider: str = "openai"
    api_url: str = DEFAULT_API_URL
    api_key: str = ""          # 默认留空，由用户自行填写
    model: str = DEFAULT_MODEL
    timeout: int = 120
    enabled: bool = False      # 默认关闭，填写 Key 并启用后才发起调用
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ApiConfig":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# 常见服务商预设（切换后自动填充对应的默认 URL 与模型）
PROVIDER_PRESETS = {
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-3.5-turbo",
    },
    "wenxin": {
        "label": "百度文心一言",
        "api_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro",
        "model": "ernie-bot-4",
    },
    "qwen": {
        "label": "阿里通义千问",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-plus",
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
    },
    "custom": {
        "label": "自定义 / 其他（OpenAI 兼容）",
        "api_url": "",
        "model": "",
    },
}


def load_config(path: str = DEFAULT_CONFIG_PATH) -> ApiConfig:
    """从 JSON 文件加载配置；文件不存在或损坏时返回默认配置。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return ApiConfig.from_dict(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ApiConfig()


def save_config(config: ApiConfig, path: str = DEFAULT_CONFIG_PATH) -> bool:
    """将配置保存到 JSON 文件。成功返回 True。"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def validate_config(config: ApiConfig) -> tuple:
    """
    校验配置是否可用来发起调用。
    返回 (是否通过, 提示信息)，仅做本地格式校验，不发起网络请求。
    """
    if not config.enabled:
        return True, "大模型点评当前为关闭状态，不会发起调用。"

    if not config.api_key.strip():
        return False, "未填写 API Key，无法调用。"
    if not config.api_url.strip():
        return False, "未填写接口地址（API URL）。"
    if not config.model.strip():
        return False, "未填写模型名称（Model）。"

    if not (config.api_url.startswith("http://") or config.api_url.startswith("https://")):
        return False, "接口地址（API URL）应以 http:// 或 https:// 开头。"

    try:
        int(config.timeout)
    except (TypeError, ValueError):
        return False, "超时时间应为正整数（秒）。"

    return True, "配置校验通过。"


def apply_preset(config: ApiConfig, provider: str) -> ApiConfig:
    """根据选择的服务商，自动填充默认 URL 与模型（保留已填的 Key）。"""
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])
    config.provider = provider
    config.api_url = preset["api_url"]
    config.model = preset["model"]
    return config
