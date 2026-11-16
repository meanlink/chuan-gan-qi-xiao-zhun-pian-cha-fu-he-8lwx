# 传感器校准偏差复核

Bootstrap 区间估计的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
数据接入（JSON/CSV、字段验证、批次指纹）→ 参数化分析（异步 Python worker）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256）；另有业务总览和审计轨迹。
三个贯穿全栈的实体：Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Audit、Delivery。
按来源订阅自动复核：Subscription（来源订阅，每来源唯一）、SubscriptionParamVersion（参数版本留痕）、SubscriptionItem（订阅×批次 1:1 派发明细）。启用即补齐该来源已有批次并接续新批次，每个匹配批次恰有一份订阅分析；手动分析不受影响、与订阅分析并存。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18206；后端文档 http://localhost:19206/docs；数据库宿主端口 17706。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
|账号|密码|真实权限|
|---|---|---|
|admin@demo.local|Demo123!|接入、执行、批准、分发、暂停、读取与下载|
|analyst@demo.local|Demo123!|接入、执行、读取与下载；不能批准或安排分发|
|viewer@demo.local|Demo123!|只读与下载|

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；PostgreSQL 16；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；JobStatus：queued/running/completed/failed。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py；页面按相同角色控制操作入口。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=sensor-bootstrap；FRONTEND_PORT=18206；BACKEND_PORT=19206；DB_PORT=17706；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 来源订阅自动复核
- 订阅按 `Dataset.source` 精确匹配，每来源仅一条；admin/analyst 可写，viewer 只读。
- 启用时同事务补齐已有批次，worker 每轮 `tick` 先 reconcile 再接续新批次；接入回滚（未提交）不触发，先分配编号后晚提交的批次也会被接住。
- 幂等两道防线：`subscription_items (subscription_id, dataset_id)` 唯一约束、`jobs` 上 `subscription_item_id` 的部分唯一索引（仅约束非空值，手动 Job 为 NULL 不受影响），均配合 SAVEPOINT；并发补齐、派发中断恢复、重试都不会重复建分析。Postgres 另用事务级咨询锁串行化同订阅派发。
- 单批失败只把该明细置 failed 并记录原因，不挡后批；`POST /subscriptions/items/{id}/retry` 原地重置同一 Job 单独重试。
- 暂停期间新批次积压保留且不派发，恢复后补齐。
- 参数以「批次提交时间」为界选取：改参数生成新版本，已提交批次（含旧积压）的分析快照旧参数，之后提交的批次采用新参数；每份 Job 留存参数与参数版本依据。
- 接口：`GET/POST /subscriptions`、`GET/PATCH /subscriptions/{id}`、`/pause`、`/resume`、`/reconcile`、`POST /subscriptions/items/{item_id}/retry`；详情返回派发明细、参数版本、覆盖缺口与订阅 Job 列表。页面「来源订阅」可设置订阅并核对缺口、失败原因和参数依据。
- 迁移幂等：新库直接建表建索引；旧库自动补列与部分唯一索引，无需手工干预。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放 ../../test-artifacts/gb-1007/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。
