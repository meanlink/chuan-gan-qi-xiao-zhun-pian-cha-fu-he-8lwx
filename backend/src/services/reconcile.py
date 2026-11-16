"""订阅自动复核的派发内核。

幂等保证（两道独立防线）：
- subscription_items 的 (subscription_id, dataset_id) 唯一约束 + SAVEPOINT：并发 reconcile
  或中断重试都不会为同一批次重复建明细；
- jobs 的部分唯一索引（subscription_item_id 非空时唯一）+ SAVEPOINT：并发下读到
  “明细已建、任务未落库”的中间态时，重复派发会被数据库拒绝并回读复用已有 Job；
- 中断遗留（明细已建但任务未建成）在下一轮补齐时复用原明细补发，不新建第二份；
- 失败重试原地重置同一个 Job，不产生第二份分析。
Postgres 另用事务级咨询锁串行化同一订阅的派发，进一步降低撞车概率。
"""
import logging
import time
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from src.models import Dataset, Job, Subscription, SubscriptionItem
from src.services import subscriptions as sub_service


def _advisory_lock(db, subscription_id):
    """Postgres：同一订阅的 reconcile 串行化；SQLite 等无咨询锁的库直接跳过。"""
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:key))'),
                   {'key': f'subscription-reconcile-{subscription_id}'})


def _job_name(sub, dataset):
    return f'订阅复核 · {sub.name} · {dataset.name}'


def _dispatch(db, sub, item):
    """为一个明细派发 Job，返回 (job, created)。

    参数版本按批次提交时间选取并快照到任务上；并发撞车时复用已存在的 Job。
    """
    existing_id = db.scalar(select(Job.id).where(Job.subscription_item_id == item.id))
    if existing_id is not None:
        existing = db.get(Job, existing_id)
        # 明细前向引用断裂（崩溃在回写 job_id 之前）：回挂原任务并重置为排队，由 worker 重跑
        if item.job_id is None:
            item.job_id = existing.id
            item.status = 'queued'
            item.last_error = ''
            item.updated_at = time.time()
            if existing.status == 'running':
                existing.status = 'queued'
        return existing, False
    dataset = db.get(Dataset, item.dataset_id)
    version = sub_service.resolve_params(db, sub.id, dataset.created_at)
    job = Job(name=_job_name(sub, dataset), dataset_id=dataset.id, params=dict(version.params),
              status='queued', created_by=sub.created_by, created_at=time.time(),
              subscription_item_id=item.id)
    sp = db.begin_nested()
    try:
        db.add(job)
        db.flush()
    except IntegrityError:
        # 并发流程已为该明细建成 Job：回退 SAVEPOINT 并回读复用，绝不产生第二份
        sp.rollback()
        db.expire_all()
        winner_id = db.scalar(select(Job.id).where(Job.subscription_item_id == item.id))
        winner = db.get(Job, winner_id)
        fresh_item = db.get(SubscriptionItem, item.id)
        if fresh_item.job_id is None and winner is not None:
            fresh_item.job_id = winner.id
            fresh_item.updated_at = time.time()
        return winner, False
    sp.commit()
    item.job_id = job.id
    item.param_version_id = version.id
    item.status = 'queued'
    item.updated_at = time.time()
    return job, True


def reconcile_subscription(db, subscription_id):
    """对单个启用订阅补齐所有匹配批次，返回本轮新建的 Job id 列表。

    调用方负责 commit；本函数内仅做 SAVEPOINT 级回滚，不污染外层事务。
    """
    created = []
    sub = db.get(Subscription, subscription_id)
    if not sub or sub.status != 'active':
        return created
    _advisory_lock(db, subscription_id)
    datasets = list(db.scalars(select(Dataset).where(Dataset.source == sub.source)
                               .order_by(Dataset.id.asc())))
    for dataset in datasets:
        item = db.scalar(select(SubscriptionItem).where(
            SubscriptionItem.subscription_id == sub.id,
            SubscriptionItem.dataset_id == dataset.id))
        if item is not None:
            # 派发中断遗留：明细在、任务不在。_dispatch 内部有唯一索引兜底，
            # 即使并发下另一个流程正在派发，也只会复用而不会重复
            if item.job_id is None:
                job, was_created = _dispatch(db, sub, item)
                if was_created:
                    created.append(job.id)
            continue
        # 先显式进入 SAVEPOINT 再 flush：唯一约束冲突在 savepoint 内被吸收，
        # 并发 reconcile 撞车时只回滚该批次，外层事务与其他批次不受影响
        sp = db.begin_nested()
        try:
            item = SubscriptionItem(subscription_id=sub.id, dataset_id=dataset.id,
                                    status='pending', attempts=0,
                                    created_at=time.time(), updated_at=time.time())
            db.add(item)
            db.flush()
        except IntegrityError:
            sp.rollback()
            logging.info('订阅 %s 批次 %s 的明细已由并发流程建立，跳过', sub.id, dataset.id)
            continue
        sp.commit()
        job, was_created = _dispatch(db, sub, item)
        if was_created:
            created.append(job.id)
    return created


def reconcile_all(db):
    """worker 周期入口：逐个启用订阅补齐，单订阅失败不阻断其余订阅。"""
    created = []
    subs = list(db.scalars(select(Subscription).where(Subscription.status == 'active')))
    for sub in subs:
        try:
            with db.begin_nested():
                created.extend(reconcile_subscription(db, sub.id))
        except Exception:
            logging.exception('订阅 %s 补齐失败，留待下轮重试', sub.id)
    return created


def sync_items(db):
    """把 Job 的最新状态镜像回订阅明细，覆盖 worker 崩溃恢复等场景。"""
    items = list(db.scalars(select(SubscriptionItem).where(SubscriptionItem.job_id.is_not(None))))
    for item in items:
        job = db.get(Job, item.job_id)
        if job and item.status != job.status:
            item.status = job.status
            item.updated_at = time.time()
        if job and item.last_error != job.error:
            item.last_error = job.error


def retry_item(db, item_id):
    """单批失败的单独重试：原地重置同一个 Job，不新建分析，不影响其他批次。"""
    item = db.get(SubscriptionItem, item_id)
    if not item:
        raise HTTPException(404, '订阅派发记录不存在')
    if item.status != 'failed':
        raise HTTPException(409, '仅执行失败的派发可以单独重试')
    job = db.get(Job, item.job_id) if item.job_id else None
    if not job:
        raise HTTPException(409, '关联分析任务缺失，请等待下轮自动补齐')
    job.status = 'queued'
    job.error = ''
    job.result = {}
    job.finished_at = None
    item.status = 'queued'
    item.last_error = ''
    item.updated_at = time.time()
    return job
