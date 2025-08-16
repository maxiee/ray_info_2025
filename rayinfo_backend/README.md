# RayInfo Backend Core Skeleton

## 运行

使用 uvicorn（开发模式）：

```
poetry install  # 首次
poetry run uvicorn rayinfo_backend.app:app --reload
```

访问：http://127.0.0.1:8000/

查看调度器日志：控制台应周期打印 `[demo_job] heartbeat`。

## 结构

```
rayinfo_backend/
	src/rayinfo_backend/app.py  # 应用入口 & 调度器集成
```

后续可在 `app.py` 拆分：

- `core/scheduler.py` 放置调度封装
- `routers/` 目录放置业务路由
- `services/` 放抓取与业务逻辑

当前版本故意保持最小化，便于快速扩展。

