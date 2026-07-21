# 使用官方 Python 镜像作为基础镜像
FROM harbor.inflyway.com/tools/python3.12-faq-tools:v260527

# 设置工作目录
WORKDIR /app
USER appuser

# 将依赖文件复制到工作目录
COPY requirements.txt ./

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将项目文件复制到工作目录
COPY --chown=appuser:appuser . /app/

# 暴露 FastAPI 和 Streamlit 的端口
EXPOSE 8000 8501

# 赋予启动脚本执行权限
RUN chmod +x ./scripts/start.sh

# 启动服务的命令
CMD ["./scripts/start.sh"]
