#!/bin/bash
# 如果尚未安装依赖，则安装
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi
# 启动 Gunicorn WSGI 服务器
exec gunicorn --bind 0.0.0.0:$PORT app:app