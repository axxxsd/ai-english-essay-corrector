# -*- coding: utf-8 -*-
"""
smoke_test.py — 快速冒烟测试（语法检查 + 评分）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grammar_checker import GrammarChecker
from scorer import Scorer


def main():
    checker = GrammarChecker()
    scorer = Scorer()

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

    print("=" * 50)
    print("📝 示例作文:", sample[:60], "...")
    print("=" * 50)

    issues = checker.check(sample)
    print(f"\n✅ 检测到 {len(issues)} 个问题：\n")
    for i, iss in enumerate(issues, 1):
        print(f"  {i}. [{iss['severity'].upper()}] {iss['message']}")
        print(f"     片段: \"{iss['context']}\"  → 建议: {iss['suggestion']}")

    scores = scorer.score(sample, issues)
    print(f"\n📊 总  分: {scores['total']:.0f} / 100")
    print(f"   - 语法: {scores['grammar']:.0f}/30")
    print(f"   - 词汇: {scores['vocab']:.0f}/25")
    print(f"   - 结构: {scores['structure']:.0f}/25")
    print(f"   - 内容: {scores['content']:.0f}/20")
    print(f"   - 统计: {scores['stats']['words']}词 / {scores['stats']['sentences']}句")

    print("\n🎉 冒烟测试通过！")


if __name__ == "__main__":
    main()
