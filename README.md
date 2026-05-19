# 英语学习助手

一个帮助孩子管理课本单词的 Web 应用。基于 FastAPI + spaCy + SQLite 构建。

## 功能

- 课本/单元/课程管理
- 课文录入，自动提取并统计生词
- 基于 spaCy 的词形还原（lemmatization）
- 生词表浏览与搜索
- 单词测验（随机/按课/错题重测）
- 排除词管理

## 安装

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 安装依赖
pip install fastapi uvicorn spacy pydantic

# 安装 spaCy 英语模型
pip install en_core_web_sm-3.8.0-py3-none-any.whl
```

## 运行

```bash
python run.py
```

浏览器访问 http://localhost:8000

## 项目结构

```
app/
  api.py          # FastAPI 路由
  analyzer.py     # NLP 分析与数据库操作
  db.py           # 数据库初始化与连接管理
  static/
    app.js        # 前端逻辑
    style.css     # 样式
  templates/
    index.html    # 主页面
run.py            # 启动入口
```
