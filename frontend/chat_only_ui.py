import streamlit as st
import requests
import os

# --- 配置 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
API_PREFIX = "/api/v1"
CHAT_ENDPOINT = f"{BACKEND_URL}{API_PREFIX}/chat/"

# --- Streamlit 页面配置 ---
st.set_page_config(page_title="FlyPay商户对接FAQ", page_icon="💬")
st.title("💬 FlyPay商户对接FAQ")
st.caption("🚀 方便日常对接过程中的通用性问题，当技术支持不在时，可以及时帮您解决日常问题")

collection_name = "RAG"  # 固定知识库集合

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("请输入您的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        with st.spinner("思考中..."):
            try:
                payload = {"question": prompt, "collection_name": collection_name}
                response = requests.post(CHAT_ENDPOINT, json=payload)
                if response.status_code == 200:
                    full_response = response.json().get("answer", "抱歉，我无法回答这个问题。")
                else:
                    full_response = f"请求错误: {response.text}"
            except requests.exceptions.RequestException as e:
                full_response = f"无法连接到后端服务: {e}"
        message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})

