# RayInfo 2025

RayInfo 是一个信息聚合器，作者是 Maxiee（Maeiee），是他对抗算法投喂、夺回注意力主权的宣言。

RayInfo 由前后端两部分组成：

- 后端：使用 Python 编写，基于 FastAPI + APScheduler，通过 Playwright 实现自动化抓取。
- 前端：使用 Flutter 编写，支持 Android、iOS、Web 和桌面端。

## RayInfo 后端

技术栈：

- 语言： Python 3.11+
- Web框架： FastAPI
- 调度器： APScheduler (AsyncIOScheduler)
- 浏览器自动化： Playwright
- 数据库： SQLite
- 运行环境： Mac Mini M4 (通过uvicorn长期运行)，通过 tailscale 组成内网 + 公网暴露



