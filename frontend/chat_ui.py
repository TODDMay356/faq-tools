import streamlit as st
import requests
import os

# --- 配置 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
API_PREFIX = "/api/v1"
CHAT_ENDPOINT = f"{BACKEND_URL}{API_PREFIX}/chat/"

# --- Streamlit 页面配置 ---
st.set_page_config(page_title="跨境支付 FAQ", page_icon="💬")
st.title("💬 跨境支付 FAQ 问答")
st.caption("🚀 一个由 LangChain 和 Streamlit 驱动的 RAG 应用")

# --- 聊天界面 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# 创建消息容器
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("请输入您的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 立即显示用户消息
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)
    
    # 显示助手回复（不使用 spinner）
    with chat_container:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("思考中...")
            
            try:
                payload = {"question": prompt}
                response = requests.post(CHAT_ENDPOINT, json=payload)
                if response.status_code == 200:
                    full_response = response.json().get("answer", "抱歉，我无法回答这个问题。")
                else:
                    full_response = f"请求错误: {response.text}"
            except requests.exceptions.RequestException as e:
                full_response = f"无法连接到后端服务: {e}"
            
            message_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.rerun()







