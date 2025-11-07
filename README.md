# Ulreaman Local

本地轻量级管理面板，用 Flask 搭建。目标是整合常用的信息和操作，比如：

- 系统信息（CPU、内存、磁盘…）
- 网络信息（所有网卡 IP、公网 IP）
- 本地文件管理器（浏览、上传、创建目录）
- 为后续添加更多小工具预留接口

项目目前是基础架构阶段，先搭好骨架，再一点点扩展功能。

## 技术栈
- Python 3
- Flask
- Jinja2 模板
- Bootstrap 5（前端样式）

## 启动项目
```bash
pip install -r requirements.txt
python app.py
