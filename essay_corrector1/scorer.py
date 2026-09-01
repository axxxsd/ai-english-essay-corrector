# -*- coding: utf-8 -*-
"""
评分模块：多维打分
不依赖任何第三方库
"""
import re
from collections import Counter


# 高级词汇表（命中可加分）
ADVANCED_VOCAB = {
    "crucial", "essential", "significant", "nevertheless", "moreover",
    "consequently", "therefore", "although", "whereas", "furthermore",
    "beneficial", "detrimental", "controversial", "phenomenon", "perspective",
    "comprehensive", "indispensable", "profound", "advocate", "alleviate",
    "deteriorate", "flourish", "implement", "integral", "perpetuate",
}

# 连接词（结构分）
CONNECTIVES = {
    "however", "therefore", "moreover", "furthermore", "in addition",
    "on the other hand", "consequently", "as a result", "in contrast",
    "for example", "for instance", "in conclusion", "to sum up",
    "firstly", "secondly", "finally", "in my opinion", "from my perspective",
}


class Scorer:
    def __init__(self):
        pass

    def score(self, text, issues):
        stats = self._stats(text)

        # --- 语法 (30) ---
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        grammar = 30 - error_count * 3 - warning_count * 1
        grammar = max(0, grammar)

        # --- 词汇 (25) ---
        words_lower = re.findall(r"\b[a-z]+\b", text.lower())
        unique = set(words_lower)
        vocab_richness = len(unique) / max(1, len(words_lower))
        advanced_count = len(unique & ADVANCED_VOCAB)
        vocab = 25 * vocab_richness + advanced_count * 2
        vocab = min(25, max(0, vocab))

        # --- 结构 (25) ---
        sentence_count = stats["sentences"]
        avg_len = stats["avg_sentence_len"]
        connective_count = sum(
            1 for c in CONNECTIVES if c in text.lower()
        )
        structure = 10  # 基础分
        # 句长适中 (10-25词) 加分
        if 10 <= avg_len <= 25:
            structure += 7
        elif 5 <= avg_len < 10 or 25 < avg_len <= 35:
            structure += 4
        else:
            structure += 1
        # 连接词
        structure += min(8, connective_count * 2)
        structure = min(25, max(0, structure))

        # --- 内容 (20) ---
        content = 20
        if stats["words"] < 50:
            content -= 8  # 太短
        elif stats["words"] < 100:
            content -= 4
        if sentence_count < 3:
            content -= 5
        content = min(20, max(0, content))

        total = grammar + vocab + structure + content

        return {
            "total": total,
            "grammar": grammar,
            "vocab": vocab,
            "structure": structure,
            "content": content,
            "stats": stats,
        }

    def _stats(self, text):
        words = re.findall(r"\b[a-zA-Z]+\b", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        word_count = len(words)
        sentence_count = len(sentences)
        avg_len = word_count / max(1, sentence_count)
        return {
            "words": word_count,
            "sentences": sentence_count,
            "avg_sentence_len": avg_len,
        }
