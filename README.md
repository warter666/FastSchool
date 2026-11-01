# FastSchool 📚 - 截图分割版

> 将 PDF 试卷按版面结构"截图分割"为题干图片与选项图片，直接生成可交互答题界面。

核心目标：避免 OCR/分词/正则在排版混乱时的不稳定，利用 PDF 的版面坐标让题目与选项"天然规整分离"。

## ✨ 功能

- 📄 上传文字版 PDF，按版面坐标自动切分题干与选项（`1.` 定位题、`A./B./C./D.` 定位选项）
- 🖼️ 题干/选项以截图渲染，公式、电路图等复杂内容零损失
- ✅ 可选上传 txt 答案卡（每行 `题号 选项`），交卷时自动判分、汇总错题
- ⌨️ 拖拽上传、一键跳转错题重做

## 🚀 快速开始

以下命令均在 Linux (Python 3.10) 上实际验证过。

### 1. 安装

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

### 2. 命令行直接切分（不启服务）

```bash
.venv/bin/python -c "from pdf_segmenter import segment_pdf_questions as s; r = s('samples/demo_paper.pdf'); print('total:', r['total'], '| options:', sorted(r['questions'][0]['parsed']['options']))"
```

预期输出：

```
total: 1 | options: ['A', 'B']
```

`segment_pdf_questions` 返回每题的题干/选项 PNG（base64 data-url）。示例卷
`samples/demo_paper.pdf` 会切出 3 张图：1 张题干 + 2 张选项（A/B）。

### 3. 启动答题界面

```bash
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000`，把 `samples/demo_paper.pdf` 拖进上传区，
页面上会看到 1 道题、共 3 张切分图（题干 + 选项 A/B 各一张）。再上传
`samples/answer_key.txt`（每行 `题号 选项`）即可选答案、交卷判分。

也可以直接用 curl 验证接口：

```bash
curl -F "file=@samples/demo_paper.pdf" http://127.0.0.1:8000/upload_screenshot
```

预期返回 `"success":true`、`"total":1`，`questions[0].parsed` 里带 base64 图片。

如果本机端口被占用，换一个端口即可，例如：`--port 9800`。

注意：当前仅支持文字版 PDF（截图分割模式）。

## 🧠 工作原理

- 后端用 PyMuPDF 读取 PDF 的文本与坐标（bbox）。
- 通过题号（如 `1.`）与选项标记（`A.`/`B.`/`C.`/`D.`）定位题干区域、选项区域。
- 对这些 bbox 在页面渲染图上裁剪成 PNG（base64 data-url），返回给前端。
- 前端按图片渲染题干与选项，点击选项完成作答，交卷后按答案卡判分。

实现文件：
- [pdf_segmenter.py](pdf_segmenter.py)
- [main.py](main.py)
- [static/index.html](static/index.html)

## 📁 项目结构

```
FastSchool/
├── main.py            # FastAPI 入口（/upload_screenshot /upload_answerkey）
├── pdf_segmenter.py   # PDF 坐标分割 + 截图裁剪
├── static/
│   └── index.html     # 答题 UI（上传/答题/判分结果）
├── samples/           # 示例试卷与答案卡
├── legacy/            # 早期原型（OpenCV 切割、OCR、Streamlit），主应用不依赖
├── docs/              # 说明文档、开发笔记
└── README.md
```

## 📄 说明文档

详见 [docs/说明文档.md](docs/说明文档.md)

## 📝 License

MIT
