# legacy/ — 早期原型代码

这些是黑客松时期的旧方案，主应用（`main.py` + `pdf_segmenter.py` + `static/`）不再引用，仅作历史保留：

- `backend/main.py` — 最初的 OpenCV 投影切割服务（端口 8002，`/api/parse`）
- `frontend/app.py` — 配套的 Streamlit 客户端
- `parser.py` — 基于文本行规则的通用解析器（docx/pdf）
- `ocr_parser.py` + `test_ocr.py` — PaddleOCR 扫描版 PDF 方案
- `exam_parser.py` — 英语竞赛卷专项解析
- `science_parser.py` — 理科卷占位解析器

如需运行，需要自行安装对应依赖（见根目录 `requirements.txt` 注释），且 `parser.py`
等模块假设工作目录在项目根（import 路径未调整）。

当前方案为什么不走 OCR：文字识别在扫描质量差、排版复杂时不稳定；而 PDF 自带
版面坐标，题干与选项"天然规整"，按 bbox 截图即可，详见 `docs/说明文档.md`。
