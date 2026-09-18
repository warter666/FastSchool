"""
英语试题解析器 (增强版)
针对英语考试卷子的题目结构，解决选项错分、题目分割错误问题
支持文章段落与题目的关联
"""
import re
from typing import List, Dict

# ── 正则规则 ──────────────────────────────────────────────
# 题号：必须是行首的数字或Q开头，且后面跟着特定的分隔符
RE_QUESTION_NUM = re.compile(
    r'^(?:\(?\s*(\d{1,3})\s*[.)、）]\s*|Q\s*(\d{1,3})\s*[.)]\s*)',
    re.IGNORECASE
)

# 选项：A. / A) / (A) / A、 (支持一行多个)
RE_OPTION_SINGLE = re.compile(
    r'([A-Fa-f])\s*[.、）\)]\s*',
    re.IGNORECASE
)

# 章节标题/指令 (Directions)
RE_SECTION = re.compile(
    r'^(Section|Part|Reading\s+Comprehension|Passage|Text|Directions?|Instructions?|竞赛样题|年全国)',
    re.IGNORECASE
)

# ── 解析器类 ────────────────────────────────────────────────

class EnglishExamParser:
    def __init__(self):
        self.questions = []
        self.current_passage = ""
        self.passage_buffer = []
        self.current_q = None
        self.q_buffer = []

    def _is_valid_question_start(self, line: str) -> bool:
        """校验是否是真实的题目开始，排除卷头标题和指令"""
        if RE_SECTION.match(line):
            return False
        
        # 启发式规则：如果是新题号，但这一行特别长（>120字符）且没有选项标识，通常是卷头/指令
        if len(line) > 120 and not RE_OPTION_SINGLE.search(line):
            return False
            
        # 如果一行包含太多竞赛/年份关键字，通常是标题
        if any(kw in line for kw in ["竞赛", "样题", "Total", "marks", "Time", "minutes", "Sample", "Competition"]):
            return False
        return True

    def flush_passage(self):
        if self.passage_buffer:
            self.current_passage = " ".join(self.passage_buffer).strip()
            self.passage_buffer = []

    def flush_question(self):
        if not self.current_q:
            return

        full_text = " ".join(self.q_buffer).strip()
        
        # 提取选项
        options = {}
        # 寻找所有选项标识符的位置 (优化：不再强制要求前置空格，支持 A.redB.blue)
        # 逻辑：匹配 [A-F] 后面跟着 [.、）\)]
        markers = list(re.finditer(r'([A-Fa-f])\s*[.、）\)]\s*', full_text))
        
        if markers:
            # 题干是第一个选项之前的内容
            stem_end = markers[0].start()
            self.current_q["stem"] = full_text[:stem_end].strip()
            
            # 提取各个选项内容
            for i in range(len(markers)):
                start = markers[i].start()
                # 下一个选项的起点即为当前选项的终点
                end = markers[i+1].start() if i+1 < len(markers) else len(full_text)
                
                marker_text = full_text[start:end].strip()
                # 再次拆分字母和内容
                m = re.match(r'([A-Fa-f])\s*[.、）\)]\s*(.*)', marker_text)
                if m:
                    options[m.group(1).upper()] = m.group(2).strip()
        else:
            self.current_q["stem"] = full_text

        # 去掉题干开头的题号
        self.current_q["stem"] = RE_QUESTION_NUM.sub("", self.current_q["stem"]).strip()
        
        # --- 核心逻辑更新：无选项题目的分类处理 ---
        if not options:
            stem_lower = self.current_q["stem"].lower()
            if any(w in stem_lower for w in ["true", "false", "yes", "no"]) or "( )" in self.current_q["stem"]:
                self.current_q["type"] = "判断"
            elif "____" in stem_lower or "___" in stem_lower:
                self.current_q["type"] = "填空"
            else:
                self.current_q["type"] = "简答"
        else:
            self.current_q["type"] = "选择"

        self.current_q["options"] = options
        self.current_q["passage"] = self.current_passage
        
        # 统一格式：将 stem 和 options 放入 parsed
        self.current_q["parsed"] = {
            "stem": self.current_q["stem"],
            "options": self.current_q["options"],
            "answer": None
        }
        
        self.questions.append(self.current_q)
        self.current_q = None
        self.q_buffer = []

    def _detect_type(self, q: Dict) -> str:
        stem = q["stem"].lower()
        if q["options"]:
            return "选择"
        if any(w in stem for w in ["true", "false", "yes", "no"]):
            return "判断"
        if "____" in stem or "___" in stem:
            return "填空"
        return "简答"

    def parse(self, lines: List[str]) -> List[Dict]:
        for line in lines:
            line = line.strip()
            if not line: continue

            # 1. 章节/文章标识
            if RE_SECTION.match(line):
                self.flush_question()
                self.flush_passage()
                self.passage_buffer = [line]
                continue

            # 2. 题号标识 (新题目开始)
            if RE_QUESTION_NUM.match(line):
                # 额外校验：如果是卷头信息或长段落指令，归为 passage 而非题目
                if not self._is_valid_question_start(line):
                    self.passage_buffer.append(line)
                    continue

                # 检查这个“题号”是否其实是一个长句中的数字（比如年份 2024.）
                # 简单的启发式：如果当前已经在处理题目，且没有选项，且这行很长，可能不是新题目
                if self.current_q and not self.current_q.get("options") and len(line) > 50:
                    self.q_buffer.append(line)
                else:
                    self.flush_question()
                    self.current_q = {"id": len(self.questions)+1, "options": {}, "raw": line}
                    self.q_buffer = [line]
                continue

            # 3. 题目延续或文章延续
            if self.current_q:
                self.q_buffer.append(line)
            else:
                self.passage_buffer.append(line)
                # 如果累积太长，可能需要 flush 
                if len(self.passage_buffer) > 20: self.flush_passage()

        self.flush_question()
        return self.questions

def parse_english_exam(lines: List[str]) -> List[Dict]:
    parser = EnglishExamParser()
    return parser.parse(lines)
