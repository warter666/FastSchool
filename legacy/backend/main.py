from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from PIL import Image
import io
import base64
from pdf2image import convert_from_bytes
import tempfile
import os

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def image_to_base64(img):
    """将图像转换为base64字符串"""
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    buffer = io.BytesIO()
    pil_img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def split_paper(image):
    """基于OpenCV的试卷切割逻辑"""
    # 1. 转灰度与二值化
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # 2. 膨胀处理，让文字连成块
    kernel = np.ones((5, 100), np.uint8)  # 水平长方体核
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # 3. 找轮廓
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    questions = []
    for cnt in sorted(contours, key=lambda x: cv2.boundingRect(x)[1]):
        x, y, w, h = cv2.boundingRect(cnt)
        if h > 20:  # 过滤掉小的噪点
            roi = image[y:y+h, x:x+w]
            questions.append(roi)
    return questions

def process_pdf(file):
    """处理PDF文件，转换为图片并切割"""
    # 将PDF转换为图片
    images = convert_from_bytes(file.read(), dpi=300)
    all_questions = []
    
    for img in images:
        # 转换为OpenCV格式
        open_cv_image = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        # 切割题目
        questions = split_paper(open_cv_image)
        all_questions.extend(questions)
    
    return all_questions

def process_image(file):
    """处理图片文件并切割"""
    # 读取图片
    img = Image.open(file)
    open_cv_image = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    # 切割题目
    questions = split_paper(open_cv_image)
    return questions

@app.post("/api/parse")
async def parse_document(file: UploadFile = File(...)):
    try:
        # 根据文件类型处理
        if file.filename.endswith('.pdf'):
            questions = process_pdf(file.file)
        elif file.filename.endswith(('.png', '.jpg', '.jpeg')):
            questions = process_image(file.file)
        else:
            return JSONResponse(status_code=400, content={"error": "Unsupported file type. Please upload PDF or image."})
        
        # 将切割后的题目转换为base64
        questions_base64 = []
        for i, q in enumerate(questions):
            b64 = image_to_base64(q)
            questions_base64.append({
                "id": i + 1,
                "image": b64
            })
        
        return {"questions": questions_base64}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)