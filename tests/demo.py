from pymilvus import connections

connections.connect("default", host="127.0.0.1", port="19530")
print("✅ Milvus Lite 已成功连接！")
