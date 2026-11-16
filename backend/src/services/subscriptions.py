import time
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Subscription, SubscriptionParamVersion
from src.services.jobs import normalize_params


def resolve_params(db, subscription_id, committed_at):
    """参数以批次提交时间为界：取 effective_at <= 批次提交时间 的最新版本。

    订阅启用之前就已提交的批次使用首个（启用时的）版本；尚未提交的批次使用之后新参数。
    """
    versions = list(db.scalars(
        select(SubscriptionParamVersion)
        .where(SubscriptionParamVersion.subscription_id == subscription_id,
               SubscriptionParamVersion.effective_at <= committed_at)
        .order_by(SubscriptionParamVersion.effective_at.desc(), SubscriptionParamVersion.id.desc())
    ))
    if versions:
        return versions[0]
    # 启用前已提交的历史批次（首个参数版本晚于其提交时间）：回填按首个版本口径
    return db.scalar(
        select(SubscriptionParamVersion)
        .where(SubscriptionParamVersion.subscription_id == subscription_id)
        .order_by(SubscriptionParamVersion.effective_at.asc(), SubscriptionParamVersion.id.asc())
    )


def create(db, data, user):
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, '订阅名称去除空格后至少需要两个字符')
    source = data.source.strip()
    if len(source) < 2:
        raise HTTPException(422, '数据来源标识至少需要两个字符')
    if db.scalar(select(Subscription).where(Subscription.source == source)):
        raise HTTPException(409, '该来源已存在订阅，每个来源仅可建立一条订阅')
    now = time.time()
    params = normalize_params(data.params)
    sub = Subscription(name=name, source=source, status='active',
                       created_by=user.id, created_at=now, updated_at=now)
    db.add(sub); db.flush()
    version = SubscriptionParamVersion(subscription_id=sub.id, params=params,
                                       effective_at=now, note='订阅启用参数')
    db.add(version); db.flush()
    return sub, version


def update(db, sub, data, note='参数调整'):
    changed = False
    if data.name is not None:
        name = data.name.strip()
        if len(name) < 2:
            raise HTTPException(422, '订阅名称去除空格后至少需要两个字符')
        sub.name = name
        changed = True
    if data.params is not None:
        params = normalize_params(data.params)
        now = time.time()
        version = SubscriptionParamVersion(subscription_id=sub.id, params=params,
                                           effective_at=now, note=note)
        db.add(version); db.flush()
        sub.updated_at = now
        changed = True
    if changed:
        sub.updated_at = time.time()
    return sub


def set_status(db, sub, status):
    sub.status = status
    sub.updated_at = time.time()
    return sub


def get(db, subscription_id):
    sub = db.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(404, '订阅不存在')
    return sub
