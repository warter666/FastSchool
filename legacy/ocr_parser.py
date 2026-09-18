"""
OCR 解析器 - 扫描版 PDF 识别
使用 Tesseract 提取图片中的文字，再交给 exam_parser.py 解析题目
"""
import os
import re
import tempfile
from typing import List, Dict

import pytesseract
from PIL import Image
import fitz  # PyMuPDF


def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[str]:
    """将 PDF 每页转为图片，提高 DPI 以改善文字粘连"""
    doc = fitz.open(pdf_path)
    image_paths = []
    tmp_dir = tempfile.mkdtemp(prefix="fastschool_ocr_")

    for i, page in enumerate(doc):
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(tmp_dir, f"page_{i+1:03d}.png")
        pix.save(img_path)
        image_paths.append(img_path)

    doc.close()
    return image_paths


def ocr_image(image_path: str, is_science: bool = False) -> List[str]:
    """对单张图片做 OCR，返回识别出的文字行列表"""
    # 打开图片
    img = Image.open(image_path)

    # 优化 Tesseract 参数以解决文字粘连问题
    # --oem 3: 使用 LSTM 模型
    # --psm 3: 自动页面分割，不假设文本块均匀
    custom_config = r'--oem 3 --psm 3'
    if is_science:
        custom_config = r'--oem 3 --psm 1' # 理科通常需要更强的布局分析

    # 尝试支持中英文
    try:
        text = pytesseract.image_to_string(img, lang='chi_sim+eng', config=custom_config)
    except Exception:
        text = pytesseract.image_to_string(img, lang='eng', config=custom_config)

    # 后处理：修复常见的 OCR 连字问题（启发式）
    # 1. 修复数字与字母粘连，例如 "10marks" -> "10 marks"
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
    
    # 2. 修复常见单词粘连 (扩展词库)
    common_merges = {
        r'Inthis': 'In this',
        r'youwill': 'you will',
        r'willbe': 'will be',
        r'eachconversation': 'each conversation',
        r'onequestion': 'one question',
        r'fourchoices': 'four choices',
        r'bestanswer': 'best answer',
        r'answersheet': 'answer sheet',
        r'fifteenseconds': 'fifteen seconds',
        r'longconversations': 'long conversations',
        r'shortconversations': 'short conversations',
        r'Inthissection': 'In this section',
        r'marksTime': 'marks Time',
        r'minutesPart': 'minutes Part',
        r'minutesSection': 'minutes Section',
        r'SectionA': 'Section A',
        r'SectionB': 'Section B',
        r'SectionC': 'Section C',
        r'PartI': 'Part I',
        r'PartII': 'Part II',
        r'PartIII': 'Part III',
        r'decidewhich': 'decide which',
        r'thebest': 'the best',
        r'thecorresponding': 'the corresponding',
        r'withasingle': 'with a single'
    }
    for pattern, replacement in common_merges.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 3. 修复驼峰式粘连 (例如 "wordWord" -> "word Word")
    # 这对英语 OCR 特别有效，因为 Tesseract 经常把两个词连在一起但首字母大写
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # 4. 修复选项前的粘连 (例如 "blueB." -> "blue B.")
    text = re.sub(r'([a-zA-Z])([A-Fa-f][.、）\)])', r'\1 \2', text)
    
    # 5. 激进修复：如果一行字母太长且没有空格，记录到日志以便 AI 重点关注
    if len(text) > 20 and ' ' not in text:
        print(f"🔍 发现严重粘连文本: {text[:30]}...")
    
    text = text.replace('—', '-').replace('—', '-')
    
    # 分割成行并清理
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)

    return lines


def parse_pdf_ocr(pdf_path: str, is_science: bool = False) -> Dict:
    """
    主入口：扫描版 PDF → OCR → 题目解析
    返回与 parse_docx / parse_pdf 相同格式的结果
    """
    from exam_parser import parse_english_exam
    from science_parser import parse_science_exam

    print(f"开始 OCR 解析 PDF (Mode: {'Science' if is_science else 'English'}): {pdf_path}")

    # 1. PDF 转图片
    image_paths = pdf_to_images(pdf_path)
    total_pages = len(image_paths)
    print(f"PDF 共 {total_pages} 页，已转为图片")

    # 2. 逐页 OCR
    all_lines = []
    page_results = []
    for i, img_path in enumerate(image_paths):
        print(f"正在识别第 {i+1}/{total_pages} 页...")
        lines = ocr_image(img_path, is_science=is_science)
        page_results.append({
            "page": i + 1,
            "lines": lines
        })
        all_lines.extend(lines)
        print(f"  第 {i+1} 页识别到 {len(lines)} 行文字")

    # 3. 清理临时图片
    for img_path in image_paths:
        try:
            os.remove(img_path)
        except Exception:
            pass

    # 4. 解析题目
    print("正在解析题目...")
    if is_science:
        questions = parse_science_exam(all_lines)
    else:
        questions = parse_english_exam(all_lines)

    return {
        "source": "ocr",
        "ocr_engine": "tesseract",
        "total_pages": total_pages,
        "paragraphs": all_lines,
        "questions": questions,
        "total": len(questions)
    }
