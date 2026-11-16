from fastapi import APIRouter, Depends
from sqlalchemy import select
from src.config.database import get_db
from src.models import Dataset, Subscription, SubscriptionItem, SubscriptionParamVersion, Job
from src.schemas.subscription import SubscriptionInput, SubscriptionUpdate
from src.middlewares.auth import current_user, can_write
from src.services import subscriptions as sub_service
from src.services import reconcile
from src.services.audit import record
from src.services.jobs import enqueue
from src.utils.serialization import subscription_dict, param_version_dict, item_dict, job_dict, dataset_dict
router = APIRouter(prefix='/subscriptions')


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    return [subscription_dict(s) for s in db.scalars(select(Subscription).order_by(Subscription.id.desc()))]


@router.post('', status_code=201)
def create(data: SubscriptionInput, db=Depends(get_db), u=Depends(can_write)):
    sub, version = sub_service.create(db, data, u)
    # 启用即同步补齐已有批次（事务内幂等，唯一约束兜底）
    created = reconcile.reconcile_subscription(db, sub.id)
    record(db, u.email, 'subscription.create',
           {'id': sub.id, 'source': sub.source, 'param_version': version.id, 'jobs': created})
    db.commit()
    for job_id in created:
        enqueue(job_id)
    return subscription_dict(sub)


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    sub = sub_service.get(db, id)
    versions = [param_version_dict(v) for v in db.scalars(
        select(SubscriptionParamVersion).where(SubscriptionParamVersion.subscription_id == id)
        .order_by(SubscriptionParamVersion.effective_at.asc()))]
    items = [item_dict(i) for i in db.scalars(
        select(SubscriptionItem).where(SubscriptionItem.subscription_id == id)
        .order_by(SubscriptionItem.id.asc()))]
    # 核对覆盖缺口：该来源下尚无派发明细的批次
    covered = set(db.scalars(
        select(SubscriptionItem.dataset_id).where(SubscriptionItem.subscription_id == id)))
    datasets = [dataset_dict(d) for d in db.scalars(
        select(Dataset).where(Dataset.source == sub.source).order_by(Dataset.id.asc()))]
    gaps = [d for d in datasets if d['id'] not in covered]
    jobs = [job_dict(j) for j in db.scalars(
        select(Job).join(SubscriptionItem, Job.subscription_item_id == SubscriptionItem.id)
        .where(SubscriptionItem.subscription_id == id).order_by(Job.id.asc()))]
    return {'subscription': subscription_dict(sub), 'param_versions': versions,
            'items': items, 'coverage_gaps': gaps, 'jobs': jobs}


@router.patch('/{id}')
def update(id: int, data: SubscriptionUpdate, db=Depends(get_db), u=Depends(can_write)):
    sub = sub_service.get(db, id)
    sub_service.update(db, sub, data)
    # 改参数后对启用订阅再补齐一轮；旧明细保留旧参数，仅新批次/未派发批次按新参数派发
    created = reconcile.reconcile_subscription(db, sub.id)
    record(db, u.email, 'subscription.update', {'id': id, 'jobs': created})
    db.commit()
    for job_id in created:
        enqueue(job_id)
    return subscription_dict(sub)


@router.post('/{id}/pause')
def pause(id: int, db=Depends(get_db), u=Depends(can_write)):
    sub = sub_service.get(db, id)
    sub_service.set_status(db, sub, 'paused')
    record(db, u.email, 'subscription.pause', {'id': id})
    db.commit()
    return subscription_dict(sub)


@router.post('/{id}/resume')
def resume(id: int, db=Depends(get_db), u=Depends(can_write)):
    sub = sub_service.get(db, id)
    sub_service.set_status(db, sub, 'active')
    # 恢复后补齐暂停期间积压的新批次；已派发的旧批次不受影响
    created = reconcile.reconcile_subscription(db, sub.id)
    record(db, u.email, 'subscription.resume', {'id': id, 'jobs': created})
    db.commit()
    for job_id in created:
        enqueue(job_id)
    return subscription_dict(sub)


@router.post('/{id}/reconcile')
def manual_reconcile(id: int, db=Depends(get_db), u=Depends(can_write)):
    sub = sub_service.get(db, id)
    created = reconcile.reconcile_subscription(db, sub.id)
    record(db, u.email, 'subscription.reconcile', {'id': id, 'jobs': created})
    db.commit()
    for job_id in created:
        enqueue(job_id)
    return {'created_jobs': created}


@router.get('/items/{item_id}')
def item_detail(item_id: int, db=Depends(get_db), u=Depends(current_user)):
    item = db.get(SubscriptionItem, item_id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, '订阅派发记录不存在')
    return item_dict(item)


@router.post('/items/{item_id}/retry')
def retry_item(item_id: int, db=Depends(get_db), u=Depends(can_write)):
    job = reconcile.retry_item(db, item_id)
    record(db, u.email, 'subscription.retry', {'item': item_id, 'job': job.id})
    db.commit()
    enqueue(job.id)
    return {'job_id': job.id, 'status': job.status}
