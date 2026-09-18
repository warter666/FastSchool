#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/tbtb/projects/FastSchool')
from ocr_parser import parse_pdf_ocr

path = '/mnt/c/Users/Y9000p/.openclaw/qqbot/downloads/2022年5月大学生英语竞赛C类初赛真题及解析_-163751365_202603301308_24300_1774847327947.pdf'

print('开始 OCR 解析...')
result = parse_pdf_ocr(path)
print(f'解析完成，共 {result["total"]} 道题')
print(f'OCR 来源: {result.get("source", "unknown")}')
print(f'总页数: {result.get("total_pages", 0)}')

for q in result['questions'][:5]:
    print()
    print(f'--- 题 {q["id"]} ---')
    stem = q.get('stem', '')
    if len(stem) > 80:
        print(f'题干: {stem[:80]}...')
    else:
        print(f'题干: {stem}')
    print(f'选项: {q.get("options", {})}')
    print(f'答案: {q.get("answer", "未找到")}')
