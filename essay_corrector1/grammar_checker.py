# -*- coding: utf-8 -*-
"""
语法/拼写/表达检查模块
不依赖任何第三方库，纯标准库实现
"""
import re


# 常见拼写错误词典
SPELL_CORRECTIONS = {
    "alot": "a lot",
    "nowdays": "nowadays",
    "recieve": "receive",
    "seperate": "separate",
    "definately": "definitely",
    "occured": "occurred",
    "untill": "until",
    "wether": "whether",
    "accomodate": "accommodate",
    "arguement": "argument",
    "basicly": "basically",
    "enviroment": "environment",
    "goverment": "government",
    "immediatly": "immediately",
    "neccessary": "necessary",
    "occassion": "occasion",
    "posession": "possession",
    "prefered": "preferred",
    "refered": "referred",
    "suprise": "surprise",
    "tendancy": "tendency",
    "therefor": "therefore",
    "thier": "their",
    "beleive": "believe",
    "teh": "the",
    "hte": "the",
    "fo": "of",
    "form": "from",
    " form ": " from ",
}

# 中式英语 / 冗余表达
CHINGLISH = [
    (r"\bmore\s+better\b", "better", "more better 语义重复，直接用 better"),
    (r"\bmost\s+important\b", "most important", "可考虑替换：crucial / essential"),
    (r"\bvery\s+very\b", "", "very very 重复使用，改为 extremely"),
    (r"\bwith\s+the\s+development\s+of\b", "", "模板化表达，建议改写"),
    (r"\bplay\s+an?\s+important\s+role\b", "", "高频模板句，建议替换具体动词"),
    (r"\bin\s+a\s+word\b", "", "表达生硬，可改为 In conclusion"),
    (r"\bcan\s+not\b", "cannot", "应写作一个词 cannot"),
]

# 主谓一致等规则
IRREGULAR_VERBS = {
    "go": "went",
    "goes": "go",
    "come": "came",
    "takes": "take",
    "make": "made",
    "took": "taken",
}


class GrammarChecker:
    def __init__(self):
        self.issues = []

    def check(self, text):
        self.issues = []
        if not text or not text.strip():
            return self.issues

        self._check_spelling(text)
        self._check_capitalization(text)
        self._check_punctuation(text)
        self._check_articles(text)
        self._check_subject_verb(text)
        self._check_chinglish(text)
        self._check_double_words(text)

        return self.issues

    def _add(self, severity, message, context, suggestion, start, end):
        self.issues.append({
            "severity": severity,
            "message": message,
            "context": context,
            "suggestion": suggestion,
            "start": start,
            "end": end,
        })

    def _check_spelling(self, text):
        tokens = re.finditer(r"\b[a-zA-Z]+\b", text)
        for m in tokens:
            word = m.group().lower()
            if word in SPELL_CORRECTIONS:
                self._add(
                    "error",
                    f"拼写错误：{m.group()} → {SPELL_CORRECTIONS[word]}",
                    m.group(),
                    f"改为 {SPELL_CORRECTIONS[word]}",
                    m.start(), m.end()
                )

    def _check_capitalization(self, text):
        # 句首应大写
        for m in re.finditer(r"(?:^|[.!?]\s+)([a-z])", text):
            idx = m.start(1)
            self._add(
                "warning",
                "句首字母应大写",
                text[idx:idx+1],
                text[idx:idx+1].upper(),
                idx, idx + 1
            )

    def _check_punctuation(self, text):
        # 句末无标点
        for m in re.finditer(r"[a-zA-Z0-9]\s*$", text):
            pass
        # 中文标点混入
        if re.search(r"[，。！？；：、]", text):
            m = re.search(r"[，。！？；：、]", text)
            self._add(
                "warning",
                "检测到中文字符混入，应使用英文标点",
                m.group(), "English punctuation",
                m.start(), m.end()
            )
        # 句末缺少标点
        sentences = re.findall(r"[^.!?]+[.!?]?", text)
        for sent in sentences:
            stripped = sent.strip()
            if len(stripped) > 3 and not stripped.endswith((".", "!", "?")):
                # 检查是否有中文标点结尾
                if stripped and not stripped[-1] in ".!?":
                    self._add(
                        "warning",
                        "句末建议添加标点 (. ! ?)",
                        stripped[-10:],
                        stripped.rstrip() + ".",
                        len(text) - len(stripped) + len(stripped.rstrip()),
                        len(text) - len(stripped) + len(stripped)
                    )
                    break

    def _check_articles(self, text):
        # a/an 误用
        for m in re.finditer(r"\ba\s+([aeiouAEIOU])", text):
            self._add(
                "error",
                "冠词误用：a → an（后面是元音开头）",
                m.group(), "an " + m.group(1),
                m.start(), m.end()
            )
        for m in re.finditer(r"\ban\s+([bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ])", text):
            self._add(
                "error",
                "冠词误用：an → a（后面是辅音开头）",
                m.group(), "a " + m.group(1),
                m.start(), m.end()
            )

    def _check_subject_verb(self, text):
        # 简单主谓一致：第三人称复数动词
        patterns = [
            (r"\bthey\s+goes\b", "they go"),
            (r"\bhe\s+go\b", "he goes"),
            (r"\bshe\s+go\b", "she goes"),
            (r"\bwe\s+goes\b", "we go"),
            (r"\bI\s+goes\b", "I go"),
            (r"\beveryone\s+are\b", "everyone is"),
            (r"\bevery\s+days?\b", "every day"),
        ]
        for pat, repl in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                self._add(
                    "error",
                    f"主谓不一致：{m.group()} → {repl}",
                    m.group(), f"改为 {repl}",
                    m.start(), m.end()
                )

    def _check_chinglish(self, text):
        for pat, repl, msg in CHINGLISH:
            for m in re.finditer(pat, text, re.IGNORECASE):
                self._add(
                    "warning",
                    f"表达优化：{msg}",
                    m.group(), repl if repl else "改写",
                    m.start(), m.end()
                )

    def _check_double_words(self, text):
        # 重复词
        for m in re.finditer(r"\b(\w+)\s+\1\b", text, re.IGNORECASE):
            self._add(
                "warning",
                f"重复用词：{m.group(1)} {m.group(1)}",
                m.group(), f"删除一个 {m.group(1)}",
                m.start(), m.end()
            )
