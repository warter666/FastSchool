# FastSchool 项目日志

## 2026-09-19 更新：仓库整理 + 依赖瘦身

### 主要改动
- 旧原型（OpenCV 切割后端、Streamlit 前端、文本/OCR 解析器）整体移入 `legacy/`，主应用不再引用
- `main.py` 去掉 `parser.export_questions` 恒等导入：核心链路只依赖
  fastapi / uvicorn / python-multipart / pymupdf / Pillow，安装即跑
- 示例文件集中到 `samples/`（`demo_paper.pdf` 单题示例卷 + `answer_key.txt` 示例答案卡）
- 新增 `.gitignore`（日志/缓存/虚拟环境），清理 `app.log`
- README / 说明文档补齐 `/upload_answerkey` 接口与判分流程说明

### 验证
- WSL (Ubuntu 22.04) 下安装核心依赖，`uvicorn main:app` 正常启动，
  `/upload_screenshot` 对 `samples/demo_paper.pdf` 返回题干/选项截图，
  `/upload_answerkey` 解析示例答案卡通过

---

## 2026-03-30 更新：OCR 扫描题解析

### 问题背景
用户上传的英语竞赛试卷为**扫描版 PDF**（纯图片格式），无法直接提取文字。

### 解决方案
集成 **PaddleOCR** 进行图片文字识别。

### 新增文件
| 文件 | 说明 |
|------|------|
| `ocr_parser.py` | OCR 扫描处理模块 |
| `exam_parser.py` | 英语阅读理解专项解析器 |

### 安装依赖
```bash
pip3 install paddlepaddle paddleocr pymupdf
```

### 依赖说明
| 包 | 用途 |
|----|------|
| `paddlepaddle` | PaddlePaddle 核心框架 |
| `paddleocr` | OCR 识别库 |
| `pymupdf` | PDF 转图片 |

### 解析流程
1. **PDF 转图片** — PyMuPDF 将 PDF 每页转为高清图片（200 DPI）
2. **OCR 识别** — PaddleOCR 识别图片中的英文文字
3. **题目解析** — exam_parser.py 按行解析题目结构

### exam_parser.py 解析规则

#### 题目识别
- 题号格式：`1.` `2.` `3.`
- 选项格式：`A.` `B.` `C.` `D.`
- 判断格式：`Ture` `False` / `Yes` `No`

#### 选项归组
- 选项紧跟在题目后
- 最多 4 个选项（ABCD）
- 识别到新题号或空行超过 2 行则结束当前题

#### 阅读理解识别
- 识别 "Reading Comprehension" / "Section" 等标记
- 长段落（>100字符）归为文章原文，不拆分为题目

### 后续优化方向
- [ ] 表格题解析（连线题、配对题）
- [ ] 完形填空识别
- [ ] 主观题/翻译题识别
- [ ] 批量处理多个 PDF

---

## 2026-03-29 更新：PDF 支持 + 极简 UI

### 问题背景
原项目只支持 Word 格式，无法处理 PDF 试卷。

### 解决方案
集成 `pdfplumber` 支持 PDF 文本提取。

### 修改文件
| 文件 | 修改内容 |
|------|----------|
| `requirements.txt` | 新增 `pdfplumber==0.10.3` |
| `parser.py` | 新增 `parse_pdf()` 函数 |
| `main.py` | 统一处理 `.docx` 和 `.pdf` |
| `static/index.html` | 上传框支持 PDF、极简 UI、返回按钮 |

### 安装命令
```bash
pip3 install pdfplumber==0.10.3
```

### 已知问题
- 扫描版 PDF 无法解析（已解决 → PaddleOCR）

---

## 2026-03-22 项目初始化

### 项目介绍
FastSchool — 试卷答题系统

### 核心功能
- 上传 Word/PDF 格式试卷
- 自动识别题目类型（选择/判断/填空）
- 在线答题练习

### 技术栈
- **后端**：FastAPI + python-docx
- **前端**：HTML + CSS + JavaScript
- **服务器**：uvicorn

### 启动命令
```bash
cd ~/FastSchool
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 快捷脚本
```bash
bash ~/start_fs.sh
```
