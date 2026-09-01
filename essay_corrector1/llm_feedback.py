# -*- coding: utf-8 -*-
"""
llm_feedback.py
调用大语言模型 API 获取作文深度点评。

说明：
- 仅使用 Python 标准库（urllib），无需安装第三方依赖。
- OpenAI / DeepSeek / 通义千问等采用「OpenAI 兼容」接口 + Bearer Token 鉴权，
  统一处理；百度文心一言采用 access_token 鉴权，单独处理。
- 提示词集中在 prompt_config.py，用户可在界面编辑。
"""
import json
import urllib.request
import urllib.error
import urllib.parse

from api_config import ApiConfig
from prompt_config import PromptConfig, load_prompts


def _get_prompts() -> PromptConfig:
    return load_prompts()


def _build_prompt(essay: str, issues: str = "") -> tuple:
    prompts = _get_prompts()
    msgs = prompts.build_feedback_messages(essay, issues)
    return msgs[0]["content"], msgs[1]["content"]


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    """
    发送 POST 请求（JSON），返回解析后的 dict。
    urlopen 的 timeout 为单一数值（秒）；大模型推理较慢，取较大值。
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    total_timeout = max(int(timeout), 120)
    with urllib.request.urlopen(req, timeout=total_timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_content(resp: dict) -> str:
    return resp["choices"][0]["message"]["content"]


def _get_wenxin_access_token(api_key: str, timeout: int) -> str:
    """
    文心一言使用 client_id/client_secret 换取 access_token。
    界面上的 api_key 建议填写为 "client_id:client_secret" 形式。
    """
    if ":" in api_key:
        client_id, client_secret = api_key.split(":", 1)
    else:
        if api_key.startswith("24.") or len(api_key) > 40:
            return api_key
        client_id, client_secret = api_key, ""

    token_url = (
        "https://aip.baidubce.com/oauth/2.0/token"
        f"?grant_type=client_credentials&client_id={urllib.parse.quote(client_id)}"
        f"&client_secret={urllib.parse.quote(client_secret)}"
    )
    req = urllib.request.Request(token_url, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "access_token" not in data:
        raise RuntimeError(f"获取文心 access_token 失败：{data}")
    return data["access_token"]


def get_llm_feedback(essay: str, config: ApiConfig = None, issues: str = "") -> str:
    """
    调用大模型 API，返回对作文的深度点评（字符串）。
    - config 为 None、未启用或无 api_key 时，返回本地模拟点评。
    - 网络 / 鉴权出错时，在末尾附上模拟点评作为兜底。
    """
    if not essay or not essay.strip():
        return "⚠️ 请先输入作文内容。"

    if config is None:
        from api_config import load_config
        config = load_config()

    if not config.enabled or not config.api_key.strip():
        return _mock_feedback(essay)

    prompts = _get_prompts()
    gen_params = prompts.generation_params(model=config.model)
    system, user = _build_prompt(essay, issues)
    timeout = int(config.timeout)

    try:
        if config.provider == "wenxin":
            token = _get_wenxin_access_token(config.api_key, timeout)
            url = f"{config.api_url}?access_token={token}"
            payload = {
                "messages": [{"role": "user", "content": system + "\n\n" + user}],
                "model": config.model,
                "temperature": gen_params.get("temperature", 0.7),
            }
            headers = {"Content-Type": "application/json"}
            resp = _post_json(url, payload, headers, timeout)
            result = resp.get("result") or _extract_content(resp)
            return _format_feedback(result)

        else:
            payload = {
                "model": config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": gen_params.get("temperature", 0.7),
                "max_tokens": gen_params.get("max_tokens", 1500),
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            }
            resp = _post_json(config.api_url, payload, headers, timeout)
            return _format_feedback(_extract_content(resp))

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            err_msg = err_body.get("error", {}).get("message") or err_body
        except Exception:
            err_msg = str(e)
        return (
            f"⚠️ API 调用失败（HTTP {e.code}）：\n{err_msg}\n\n"
            "以下为本地模拟点评（仅供参考）：\n" + _mock_feedback(essay)
        )
    except Exception as e:
        return (
            f"⚠️ 调用大模型时出错：{e}\n\n"
            "以下为本地模拟点评（仅供参考）：\n" + _mock_feedback(essay)
        )


def _format_feedback(text: str) -> str:
    return "🤖 大模型深度点评\n\n" + text.strip()


def generate_revised_essay(essay: str, config: ApiConfig = None) -> str:
    """
    调用大模型生成「修改后的范文」。
    使用固定的 rewrite_system / rewrite_user 提示词，保证输出「修改说明 + 范文」。
    未启用 / 无 Key 时返回本地简单润色（兜底）。
    """
    if not essay or not essay.strip():
        return "⚠️ 请先输入作文内容。"

    if config is None:
        config = load_config()

    prompts = _get_prompts()
    messages = prompts.build_rewrite_messages(essay)
    gen_params = prompts.generation_params(model=config.model)
    timeout = int(config.timeout)

    if not config.enabled or not config.api_key.strip():
        return _format_revision(_local_rewrite(essay))

    try:
        if config.provider == "wenxin":
            token = _get_wenxin_access_token(config.api_key, timeout)
            url = f"{config.api_url}?access_token={token}"
            payload = {
                "messages": [{"role": "user",
                               "content": messages[0]["content"] + "\n\n" + messages[1]["content"]}],
                "model": config.model,
            }
            headers = {"Content-Type": "application/json"}
            resp = _post_json(url, payload, headers, timeout)
            result = resp.get("result") or _extract_content(resp)
            return _format_revision(result, gen_params.get("max_tokens"))
        else:
            payload = {
                "model": config.model,
                "messages": messages,
                "temperature": gen_params.get("temperature", 0.7),
                "max_tokens": gen_params.get("max_tokens", 1500),
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            }
            resp = _post_json(config.api_url, payload, headers, timeout)
            return _format_revision(_extract_content(resp), gen_params.get("max_tokens"))

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            err_msg = err_body.get("error", {}).get("message") or err_body
        except Exception:
            err_msg = str(e)
        return (
            f"⚠️ 生成范文失败（HTTP {e.code}）：{err_msg}\n\n"
            "以下为本地简单润色（仅供参考）：\n" + _format_revision(_local_rewrite(essay))
        )
    except Exception as e:
        return (
            f"⚠️ 生成范文时出错：{e}\n\n"
            "以下为本地简单润色（仅供参考）：\n" + _format_revision(_local_rewrite(essay))
        )


def _format_revision(text: str, max_tokens: int = None) -> str:
    cap_note = f"（本次 max_tokens = {int(max_tokens)})" if max_tokens else ""
    header = (
        "✍️ 修改后的范文\n"
        "（含【修改说明】与【修改后的范文】两部分）\n"
    )
    if cap_note:
        header += cap_note + "\n\n"
    else:
        header += "\n"
    return header + text.strip()


def _local_rewrite(essay: str) -> str:
    """无 API 时的本地兜底：基于规则给出修改说明。"""
    from grammar_checker import GrammarChecker
    checker = GrammarChecker()
    issues = checker.check(essay)
    lines = ["===== 修改说明 ====="]
    if issues:
        seen = set()
        for i in issues:
            key = i["message"]
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- 原文：{i['context']} → 建议：{i['suggestion']}")
    else:
        lines.append("- 未发现明显问题，表达基本正确。")
    lines.append("\n===== 修改后的范文 =====")
    lines.append("（未配置 API，暂无法生成 AI 润色范文；请在「⚙️ API 设置」中启用大模型后重试。）")
    return "\n".join(lines)


def test_connection(config: ApiConfig) -> tuple:
    """
    用一条最小请求测试接口连通性（不点评完整作文，省 token）。
    返回 (是否成功: bool, 提示信息: str)。
    """
    if not config or not config.enabled:
        return False, "大模型点评未启用。"
    if not config.api_key.strip():
        return False, "未填写 API Key。"
    if not config.api_url.strip():
        return False, "未填写接口地址（API URL）。"

    system = "你是英语教师。"
    user = "请只回复一个英文单词：ok"
    timeout = min(int(config.timeout), 15)

    try:
        if config.provider == "wenxin":
            token = _get_wenxin_access_token(config.api_key, timeout)
            url = f"{config.api_url}?access_token={token}"
            payload = {"messages": [{"role": "user", "content": user}], "model": config.model}
            headers = {"Content-Type": "application/json"}
            resp = _post_json(url, payload, headers, timeout)
            if resp.get("result") or resp.get("choices"):
                return True, "连接成功，接口可正常访问。"
            return False, f"接口返回异常：{resp}"
        else:
            payload = {
                "model": config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 5,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            }
            resp = _post_json(config.api_url, payload, headers, timeout)
            if resp.get("choices"):
                return True, "连接成功，接口可正常访问。"
            return False, f"接口返回异常：{resp}"

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            err_msg = err_body.get("error", {}).get("message") or err_body
        except Exception:
            err_msg = str(e)
        return False, f"连接失败（HTTP {e.code}）：{err_msg}"
    except Exception as e:
        return False, f"连接失败：{e}"


def _mock_feedback(essay: str) -> str:
    """配置不完整或未启用时，基于简单规则生成模拟点评。"""
    feedback = []
    word_count = len(essay.split())

    feedback.append("📌 整体评价")
    if word_count < 80:
        feedback.append("- 文章篇幅偏短，建议扩展论点，增加论证细节。")
    elif word_count > 250:
        feedback.append("- 文章篇幅充实，注意避免冗余表达。")
    else:
        feedback.append("- 篇幅适中，结构较为完整。")

    feedback.append("\n📌 优点")
    feedback.append("- 观点表达清晰，能够围绕主题展开。")
    feedback.append("- 使用了一定的连接词，行文有一定连贯性。")

    feedback.append("\n📌 改进建议")
    feedback.append("- 部分句子存在语法瑕疵，建议注意主谓一致和时态统一。")
    feedback.append("- 可适当引入更高级的词汇和多样化句型（如从句、倒装）。")
    feedback.append("- 结论段可进一步升华，避免简单重复前文。")

    feedback.append("\n📌 示例改写")
    feedback.append("> 如 more better 可优化为 better / much better。")
    feedback.append("> 长句可拆分为短句，提升可读性。")

    return "\n".join(feedback)


def fetch_models(base_url: str, api_key: str, timeout: int = 10) -> tuple:
    """
    自动获取接口地址下所有可用模型名称（OpenAI 兼容的 GET /v1/models 端点）。

    参数:
        base_url: 接口基地址，如 https://api.openai.com/v1（也接受完整地址，会自动裁剪）
        api_key:  API 密钥
        timeout:  请求超时（秒），默认 10 秒

    返回:
        (success: bool, models: list[str], error_msg: str)
    """
    if not base_url or not base_url.strip():
        return False, [], "未填写接口地址（API URL）。"
    if not api_key or not api_key.strip():
        return False, [], "未填写 API Key。"

    # 规范化 base_url：截取到 /v1
    base = base_url.strip().rstrip("/")
    if "/chat/completions" in base:
        base = base.split("/chat/completions")[0].rstrip("/")
    if not base.endswith("/v1"):
        if not base.endswith("/v1/models"):
            base = base + "/v1"

    models_url = base + "/models"

    try:
        req = urllib.request.Request(models_url)
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if isinstance(data, dict) and "data" in data:
            models = []
            for item in data["data"]:
                mid = item.get("id") or item.get("name") or ""
                if mid:
                    models.append(mid)
            if models:
                models.sort()
                return True, models, ""
            return False, [], "接口返回的模型列表为空。"
        else:
            return False, [], f"响应格式异常（非标准 /v1/models）：{json.dumps(data, ensure_ascii=False)[:200]}"

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            err_msg = err_body.get("error", {}).get("message") or err_body
        except Exception:
            err_msg = str(e)
        if e.code == 404:
            return False, [], f"该接口不支持 /v1/models 自动获取（HTTP 404），可手动输入模型名。"
        return False, [], f"HTTP {e.code}：{err_msg}"

    except urllib.error.URLError as e:
        return False, [], f"网络连接失败：{e.reason}（请检查地址是否正确、网络是否畅通）"

    except Exception as e:
        return False, [], f"获取失败：{type(e).__name__}：{e}"


if __name__ == "__main__":
    # 直接运行本文件可做离线测试，不发起网络请求
    sample = "Nowdays, with the development of society, students use alot of time on phone."
    print(get_llm_feedback(sample))
