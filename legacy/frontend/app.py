import streamlit as st
import requests
import base64
from PIL import Image
import io

# 设置页面配置
st.set_page_config(
    page_title="FastSchool - 智能试题解析",
    page_icon="📚",
    layout="wide"
)

# 苹果风格的CSS
st.markdown("""
<style>
/* 全局样式 */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #f5f5f7;
    color: #1d1d1f;
}

/* 标题样式 */
h1, h2, h3 {
    font-weight: 600;
    color: #1d1d1f;
}

/* 卡片样式 */
.st-emotion-cache-1wrcr25 {
    background-color: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    padding: 20px;
    margin-bottom: 20px;
}

/* 按钮样式 */
.stButton > button {
    background-color: #0071e3;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    background-color: #0077ed;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 113, 227, 0.3);
}

.stButton > button:active {
    transform: translateY(0);
}

/* 进度条样式 */
.stProgress > div > div {
    background-color: #0071e3;
    border-radius: 4px;
}

/* 文件上传器样式 */
.stFileUploader > div {
    border: 2px dashed #d1d1d6;
    border-radius: 12px;
    padding: 20px;
    background-color: #f9f9f9;
}

/* 图片样式 */
.stImage > img {
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 分割线 */
hr {
    border: none;
    height: 1px;
    background-color: #d1d1d6;
    margin: 20px 0;
}

/* 页脚 */
footer {
    text-align: center;
    color: #86868b;
    font-size: 14px;
    margin-top: 40px;
}
</style>
""", unsafe_allow_html=True)

# 标题
st.title("📚 FastSchool - 智能试题解析")

# 文件上传区域
st.header("上传试题文件")
uploaded_file = st.file_uploader("选择 PDF 或图片文件", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    st.success(f"文件上传成功: {uploaded_file.name}")
    
    # 解析按钮
    if st.button("开始解析"):
        with st.spinner("正在解析文件..."):
            # 调用后端API
            files = {"file": uploaded_file.getvalue()}
            response = requests.post("http://localhost:8002/api/parse", files=files)
            
            if response.status_code == 200:
                result = response.json()
                st.success("解析成功！")
                
                # 存储解析结果到会话状态
                st.session_state['questions'] = result.get('questions', [])
                st.session_state['current_question'] = 0
                st.session_state['answers'] = {}
            else:
                st.error(f"解析失败: {response.json().get('error', '未知错误')}")

# 答题区域
if 'questions' in st.session_state:
    questions = st.session_state['questions']
    current_idx = st.session_state.get('current_question', 0)
    
    if questions:
        st.header("📝 答题环节")
        
        # 进度条
        st.progress((current_idx + 1) / len(questions))
        st.write(f"第 {current_idx + 1} 题 / 共 {len(questions)} 题")
        
        # 当前题目
        question = questions[current_idx]
        st.subheader(f"题目 {question['id']}")
        
        # 显示题目图片
        image_data = base64.b64decode(question['image'])
        image = Image.open(io.BytesIO(image_data))
        st.image(image, use_column_width=True)
        
        # 选项按钮
        col1, col2, col3, col4 = st.columns(4)
        selected_option = None
        
        with col1:
            if st.button("A"):
                selected_option = "A"
        with col2:
            if st.button("B"):
                selected_option = "B"
        with col3:
            if st.button("C"):
                selected_option = "C"
        with col4:
            if st.button("D"):
                selected_option = "D"
        
        # 处理选项选择
        if selected_option:
            st.session_state['answers'][current_idx] = selected_option
            st.success(f"已选择: {selected_option}")
            
            # 自动进入下一题
            if current_idx < len(questions) - 1:
                st.session_state['current_question'] = current_idx + 1
                # 刷新页面
                st.experimental_rerun()
            else:
                st.success("🎉 答题完成！")
                # 显示答题结果
                st.subheader("📊 答题结果")
                st.write(f"共完成 {len(questions)} 题")
                st.write("答题记录:")
                for i, q in enumerate(questions):
                    answer = st.session_state['answers'].get(i, "未作答")
                    st.write(f"- 题目 {q['id']}: 选择了 {answer}")

# 页脚
st.markdown("---")
st.markdown("<center>FastSchool - 智能教育解决方案</center>", unsafe_allow_html=True)