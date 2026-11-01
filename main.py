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


def _parse_answer_text(text: str) -> dict:
    """解析纯文本答案格式：123:A / 456. B"""
    return {int(m[1]): m[2].upper() 
            for line in (text or "").splitlines()
            if (m := re.match(r"^(\d{1,4})\s*[:：.、-]?\s*([A-Da-d])", line.strip()))}

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
    """答案卡上传接口：pdf/png/jpg 存临时目录（tmp_*），txt 直接解析"""
    filename = (file.filename or "").lower()
    suffix = os.path.splitext(filename)[1]
    
    allowed = ('.pdf', '.png', '.jpg', '.jpeg')
    if not filename.endswith(allowed) and suffix != '.txt':
        return {"success": False, "error": "仅支持 .pdf/.png/.jpg/.jpeg/.txt"}
    
    content = await file.read()
    answers = {}
    parsed = suffix == '.txt'
    
    if suffix == '.txt':
        try:
            answers = _parse_answer_text(content.decode("utf-8", errors="ignore"))
        except Exception:
            pass
    
    upload_id = str(uuid.uuid4())
    if suffix != '.txt':
        tmp_path = f"tmp_{upload_id}{suffix}"
        with open(tmp_path, "wb") as f:
            f.write(content)
    
    return {"success": True, "id": upload_id, "filename": file.filename,
            "size": len(content), "parsed": parsed, 
            "count": len(answers), "answers": answers}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
