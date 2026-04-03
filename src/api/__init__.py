"""
HTTP API 层。

- 业务路由：`src.api.routes` → `router`，前缀见该模块。
- 任务路由：`src.api.task_routes` → `router`，前缀 `/api/v1/tasks`。

二者均在 `src.main` 中通过 `app.include_router(...)` 挂载。
"""
