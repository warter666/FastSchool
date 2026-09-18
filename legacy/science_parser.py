"""理科试题解析器 (占位版)
目前仅保留基础的规则解析能力，后续可以替换为截图分割/公式 OCR。
"""

from typing import List, Dict

from parser import QuestionParser


def parse_science_exam(lines: List[str]) -> List[Dict]:
    parser = QuestionParser()
    for line in lines:
        parser.process_line(line)
    return parser.get_results()

