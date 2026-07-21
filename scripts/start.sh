#!/bin/bash

# 切换到项目根目录
cd "$(dirname "$0")/.."

# 启动后端
echo "启动后端服务..."
python -m app.main &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端
echo "启动前端服务..."
streamlit run frontend/chat_ui.py &
FRONTEND_PID=$!

echo "后端 PID: $BACKEND_PID"
echo "前端 PID: $FRONTEND_PID"
echo "按 Ctrl+C 停止服务"

# 等待进程
wait
