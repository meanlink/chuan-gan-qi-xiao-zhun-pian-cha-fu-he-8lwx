from sqlalchemy import String, JSON, Double, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class Subscription(Base):
    """按数据来源（Dataset.source 精确匹配）建立的自动复核订阅。"""
    __tablename__ = 'subscriptions'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='active')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    updated_at: Mapped[float] = mapped_column(Double)


class SubscriptionParamVersion(Base):
    """订阅参数版本：effective_at 为该版本生效的提交时刻，参数以批次提交时间为界选取。"""
    __tablename__ = 'subscription_param_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey('subscriptions.id'))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    effective_at: Mapped[float] = mapped_column(Double)
    note: Mapped[str] = mapped_column(String(200), default='')


class SubscriptionItem(Base):
    """订阅与匹配批次的 1:1 派发明细；唯一约束保证每个匹配批次恰有一份订阅分析。"""
    __tablename__ = 'subscription_items'
    __table_args__ = (UniqueConstraint('subscription_id', 'dataset_id', name='uq_subscription_dataset'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey('subscriptions.id'))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    # 应用层维护的任务回链（与 Job.subscription_item_id 对应）；避免与 jobs 表形成循环外键
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    param_version_id: Mapped[int | None] = mapped_column(ForeignKey('subscription_param_versions.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str] = mapped_column(String(1000), default='')
    created_at: Mapped[float] = mapped_column(Double)
    updated_at: Mapped[float] = mapped_column(Double)
