"""
智能文档解析器 - 核心解析引擎
支持：Word(.docx)、PDF(.pdf)
功能：题目识别、选项提取、状态机驱动、LaTeX 友好
"""
import re
from typing import List, Dict, Optional
from docx import Document
import pdfplumber

# ── 正则表达式 ──────────────────────────────────────────────

# 题号：1. / 1) / 1、/ (1) / Q1. / 【1】
# 增加约束：后面不紧跟长中文标题或竞赛信息
RE_QUESTION_START = re.compile(
    r'^(\d+|[一二三四五六七八九十]{1,3})[.、\s)]|^\(\d+\)|^Q\d+[.、\s]|^【\d+】', 
    re.IGNORECASE
)

# 常见的非题目开头（卷头、指令、页码）
RE_JUNK_START = re.compile(
    r'^(Section|Part|Reading|Directions|Instructions|Passage|Text|Total|Time|Marks|Page|\d{4}年|全国|竞赛|样题)',
    re.IGNORECASE
)

# 选项：A. / A) / (A) / A、 (支持一行多个选项，且兼容无空格粘连的情况)
# 这里的逻辑是：匹配 A. 到下一个 B. 或行尾
RE_OPTION_FINDALL = re.compile(
    r'([A-Fa-f])\s*[.、）\)]\s*(.*?)(?=\s*[A-Fa-f]\s*[.、）\)]|$)',
    re.DOTALL
)

# 判断题标识
RE_JUDGE_MARK = re.compile(r'[（(]\s*[√×✓✗]?\s*[）)]')

# 填空题标识
RE_FILL_MARK = re.compile(r'_{2,}|（\s*）|\(\s*\)|#{2,}')

# ── 解析类 ──────────────────────────────────────────────────

class QuestionParser:
    def __init__(self):
        self.questions = []
        self.current_q = None
        self.buffer = []

    def flush_current(self):
        """将当前缓冲区内容保存为题目"""
        if not self.current_q:
            return

        full_text = " ".join(self.buffer).strip()
        
        # 验证是否真的是题目（排除卷头标题、指令、长文本）
        if len(full_text) < 5 or RE_JUNK_START.match(full_text):
            # 记录为背景材料 (Passage) 而非题目
            self.current_q = None
            self.buffer = []
            return
        
        # 提取选项
        options = self.extract_options(full_text)
        
        if options:
            self.current_q["type"] = "选择"
            self.current_q["parsed"]["options"] = options
            # 题干是第一个选项之前的内容
            stem_text = full_text
            first_opt_match = re.search(r'[A-Fa-f]\s*[.、）\)]', full_text)
            if first_opt_match:
                stem_text = full_text[:first_opt_match.start()].strip()
            self.current_q["parsed"]["stem"] = RE_QUESTION_START.sub("", stem_text).strip()
        else:
            # --- 核心逻辑更新：无选项题目的分类处理 ---
            self.current_q["parsed"]["stem"] = RE_QUESTION_START.sub("", full_text).strip()
            
            # 1. 判断题 (包含括号或对错符号)
            if RE_JUDGE_MARK.search(full_text) or any(s in full_text for s in ["√", "×", "正确", "错误"]):
                self.current_q["type"] = "判断"
                # 规范化括号
                self.current_q["parsed"]["stem"] = RE_JUDGE_MARK.sub(" ( ) ", self.current_q["parsed"]["stem"])
            
            # 2. 填空题 (包含下划线或连续点)
            elif RE_FILL_MARK.search(full_text) or "____" in full_text:
                self.current_q["type"] = "填空"
                self.current_q["parsed"]["stem"] = RE_FILL_MARK.sub(" ______ ", self.current_q["parsed"]["stem"])
                
            # 3. 简答题 (以问号结尾或长度较长)
            elif "?" in full_text or "？" in full_text or len(full_text) > 40:
                self.current_q["type"] = "简答"
            
            # 4. 默认设为简答
            else:
                self.current_q["type"] = "简答"

        self.questions.append(self.current_q)
        self.current_q = None
        self.buffer = []

    def extract_options(self, text: str) -> Dict[str, str]:
        """从文本中提取所有选项"""
        matches = RE_OPTION_FINDALL.findall(text)
        if not matches:
            return {}
        
        options = {}
        for letter, content in matches:
            options[letter.upper()] = content.strip()
        
        # 如果只有1个选项且不是A，可能不是选择题
        if len(options) < 2 and "A" not in options:
            return {}
            
        return options

    def process_line(self, line: str):
        line = line.strip()
        if not line:
            return

        # 检查是否是新题目的开始
        if RE_QUESTION_START.match(line):
            self.flush_current()
            self.current_q = {
                "id": len(self.questions) + 1,
                "type": "未知",
                "raw": line,
                "parsed": {"stem": "", "options": {}, "answer": None}
            }
            self.buffer = [line]
        elif self.current_q:
            # 属于当前题目的延续
            self.buffer.append(line)
        else:
            # 孤立的行，可能是文章段落或卷首语，暂不处理
            pass

    def get_results(self):
        self.flush_current()
        return self.questions

# ── 导出接口 ────────────────────────────────────────────────

def parse_pdf(file_path: str) -> Dict:
    paragraphs = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                paragraphs.extend([l.strip() for l in text.split('\n') if l.strip()])
    
    parser = QuestionParser()
    for line in paragraphs:
        parser.process_line(line)
    
    questions = parser.get_results()
    return {
        "paragraphs": paragraphs,
        "questions": questions,
        "total": len(questions)
    }

def parse_docx(file_path: str) -> Dict:
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    
    parser = QuestionParser()
    for line in paragraphs:
        parser.process_line(line)
        
    questions = parser.get_results()
    return {
        "paragraphs": paragraphs,
        "questions": questions,
        "total": len(questions)
    }

def export_questions(questions: List[Dict]) -> List[Dict]:
    return questions
