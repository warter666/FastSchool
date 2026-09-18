"""
FastSchool - 试卷答题系统
支持上传 Word(.docx) 和 PDF(.pdf) 文档，在线答题练习
支持 OCR 扫描版 PDF
"""
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import uuid
import re

app = FastAPI(title="FastSchool", version="1.2.0")

_answer_uploads = {}


def _parse_answerkey_text(text: str) -> dict:
    answers = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(\d{1,4})\s*[:：.、-]?\s*([A-Da-d])\b", line)
        if not m:
            continue
        qid = int(m.group(1))
        ans = m.group(2).upper()
        answers[qid] = ans
    return answers

# CORS 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    """首页"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


def try_parse_with_ocr(tmp_path: str) -> dict:
    """截图分割解析 PDF"""
    from pdf_segmenter import segment_pdf_questions

    try:
        return segment_pdf_questions(tmp_path)
    except Exception as e:
        return {"error": f"截图分割失败: {str(e)}", "total": 0, "source": "failed"}


@app.post("/upload")
async def upload_file_legacy():
    return {
        "success": False,
        "error": "旧接口已废弃：请刷新页面或改用 /upload_screenshot",
    }


@app.post("/upload_screenshot")
async def upload_file(file: UploadFile = File(...)):
    """上传并解析文档（截图分割模式，仅支持 PDF）"""
    filename = (file.filename or "").lower()

    if filename.endswith('.pdf'):
        suffix = '.pdf'
    else:
        return {"success": False, "error": "当前仅支持 PDF（截图分割模式）"}

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = try_parse_with_ocr(tmp_path)

        questions = result.get("questions", [])

        # 检查解析结果是否有错
        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "source": result.get("source", "error")
            }

        return {
            "success": True,
            "filename": file.filename,
            "filetype": suffix.lstrip('.').upper(),
            "total": result.get("total", 0),
            "source": result.get("source", "unknown"),
            "questions": questions
        }
    except Exception as e:
        return {"success": False, "error": f"解析失败: {str(e)}"}
    finally:
        os.unlink(tmp_path)


@app.post("/upload_answerkey")
async def upload_answerkey(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    allowed = ('.pdf', '.png', '.jpg', '.jpeg', '.txt')
    if not filename.endswith(allowed):
        return {
            "success": False,
            "error": "答案文件仅支持 .pdf/.png/.jpg/.jpeg/.txt",
        }

    suffix = os.path.splitext(filename)[1]
    upload_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    _answer_uploads[upload_id] = {
        "filename": file.filename,
        "path": tmp_path,
        "size": len(content),
    }

    answers = {}
    parsed = False
    if suffix == ".txt":
        try:
            answers = _parse_answerkey_text(content.decode("utf-8", errors="ignore"))
            parsed = True
        except Exception:
            parsed = False

    _answer_uploads[upload_id]["parsed"] = parsed
    _answer_uploads[upload_id]["answers"] = answers

    return {
        "success": True,
        "id": upload_id,
        "filename": file.filename,
        "size": len(content),
        "parsed": parsed,
        "count": len(answers),
        "answers": answers,
    }


@app.get("/answerkey/{answer_id}")
async def get_answerkey(answer_id: str):
    item = _answer_uploads.get(answer_id)
    if not item:
        return {"success": False, "error": "答案不存在或已过期"}
    return {
        "success": True,
        "id": answer_id,
        "filename": item.get("filename"),
        "parsed": bool(item.get("parsed")),
        "count": len(item.get("answers") or {}),
        "answers": item.get("answers") or {},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
