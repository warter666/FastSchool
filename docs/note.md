需要input: exam (pdf/doc)  & answer (pdf/doc)  
output: analysis (pdf)  maybe 错题本
文件识别不准确, 介入大模型或者实在不行进行截图 

明白你的思路了。作为产品经理，我非常支持这种**“奥卡姆剃刀”式**的简化：既然文字识别和语义分割太复杂，那就回归最直观的**视觉分割**。

既然题目和选项在排版上是规整的，我们可以利用**计算机视觉（OpenCV）**来做物理位置的切割。这种方式不关心内容，只关心“空隙”，开发效率极高。

以下是基于 **Python + OpenCV** 的最简落地闭环方案：

---

## 核心逻辑：基于投影法的“切片机”
由于试卷通常是白底黑字，且题目间、题目与选项间有明显的垂直/水平间距，我们可以通过统计像素分布来寻找切割线。

### 第一步：图像预处理 (Image Prep)
1. **转灰度与二值化：** 将图片变成纯黑白，过滤掉背景杂色。
2. **膨胀操作 (Dilation)：** 这是一个关键点。通过 OpenCV 将文字块向水平方向“涂抹”连接成一个长条矩形，这样每一行题目或每一个选项都会变成一个完整的黑块。

### 第二步：水平投影切割（划分题目）
1. **计算水平直方图：** 统计每一行像素的黑点数量。
2. **寻找空白行：** 连续像素为 0（全白）的区域就是题目之间的“分割线”。
3. **坐标切片：** 记录每一道题的 $y$ 坐标范围，将试卷切割成一个个“题目长条”。



### 第三步：垂直投影切割（划分选项）
1. **针对单个题目条：** 统计垂直方向的像素分布。
2. **识别间距：** 如果选项是 ABCD 横向排列，垂直投影图中会出现明显的波谷。
3. **二次切割：** 根据波谷位置，将题目条再次切割为 `Question_Stem`（题干）和 `Option_A/B/C/D`（选项图）。

---

## 落地开发步骤（FastSchool 重构计划）

### 1. 环境准备
只需要三个最基础的库：
```bash
pip install opencv-python numpy pillow
```

### 2. 最小可行性代码逻辑 (MVP Code Logic)
你可以按照这个伪代码逻辑在 `\home\tbtb\projects\fastschool` 下重构：

```python
import cv2
import numpy as np

def split_paper(image_path):
    # 1. 加载图片并二值化
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # 2. 膨胀处理，让文字连成块
    kernel = np.ones((5, 100), np.uint8) # 水平长方体核
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # 3. 找轮廓（或者用投影法）
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    questions = []
    for cnt in sorted(contours, key=lambda x: cv2.boundingRect(x)[1]):
        x, y, w, h = cv2.boundingRect(cnt)
        if h > 20: # 过滤掉小的噪点
            roi = img[y:y+h, x:x+w]
            questions.append(roi)
            # 这里可以进一步对 roi 做垂直切割分出选项
    return questions
```

### 3. 实现实时互动前端 (Streamlit 快速搭建)
黑客松演示最快的方式是使用 **Streamlit**：
* **上传组件：** `st.file_uploader` 接收 PDF/Docx（先转成图片）。
* **展示组件：** 循环展示切割好的 `Question_Stem` 图片。
* **交互组件：** 下方放四个 `st.button` (A, B, C, D)。
* **逻辑控制：** 点击按钮后，利用 `st.empty()` 刷新画面，加载下一组切割好的图片。

---

## 后续扩展到数理化学科的优势
这种**“视觉切割”**逻辑在处理理科题目时简直是降维打击：
1.  **公式兼容：** 不管是 $\sum_{i=1}^{n}$ 还是复杂的根号，在 OpenCV 眼里都只是一个“黑块”，切割逻辑完全不需要改动。
2.  **图形保留：** 物理的电路图、数学的几何图会随着题干一起被完整切下来，不会像 OCR 那样解析乱码。
3.  **零延迟：** 不需要联网请求 LLM，本地秒出结果，Demo 演示会非常流畅。

## 当前最紧要的任务
1.  **确定输入源：** 既然是 PDF/Docx，建议先用 `pdf2image` 库统一转成 **300 DPI** 的长图。
2.  **固定格式约束：** 在黑客松演示时，挑选排版最规整的试卷（例如单栏排版），这能保证你的切割准确率达到 95% 以上。

这个方案能在 2 小时内写出核心逻辑，非常符合黑客松的节奏！加油。