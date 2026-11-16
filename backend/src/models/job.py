from sqlalchemy import String, JSON, Double, ForeignKey, Boolean, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(1000), default='')
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    # 手动分析为空；订阅自动派发的分析回链到订阅明细，保证每批次一份订阅分析。
    # 部分唯一索引：仅约束非空值，数据库层兜底“一个订阅明细至多一个 Job”，并发/崩溃恢复都不重复。
    subscription_item_id: Mapped[int | None] = mapped_column(ForeignKey('subscription_items.id'), nullable=True)
    __table_args__ = (
        Index('uq_job_subscription_item', 'subscription_item_id', unique=True,
              postgresql_where=text('subscription_item_id IS NOT NULL'),
              sqlite_where=text('subscription_item_id IS NOT NULL')),
    )
