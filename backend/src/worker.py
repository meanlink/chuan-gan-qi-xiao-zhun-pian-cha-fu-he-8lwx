import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report, SubscriptionItem
from src.services.business import analyze
from src.services.reports import deliver
from src.services import reconcile
from src.services.audit import record
logging.basicConfig(level=logging.INFO)
def execute(job_id):
    with Session() as db:
        j=db.get(Job,job_id)
        if not j or j.status!='queued':return
        j.status='running'; db.commit()
        item=db.get(SubscriptionItem,j.subscription_item_id) if j.subscription_item_id else None
        if item:
            item.attempts+=1; item.status='running'; item.updated_at=time.time()
            db.commit()
        try:
            d=db.get(Dataset,j.dataset_id)
            result=analyze(d.records,j.params)
            json.dumps(result,allow_nan=False)
            j.result=result;j.status='completed';j.finished_at=time.time()
            if item:item.status='completed';item.updated_at=time.time()
            record(db,'worker','job.completed',{'id':j.id})
        except Exception as e:
            logging.exception('Analysis failed')
            j.status='failed';j.error=str(e)[:990];j.finished_at=time.time()
            if item:item.status='failed';item.last_error=j.error;item.updated_at=time.time()
            record(db,'worker','job.failed',{'id':j.id,'error':j.error})
        db.commit()
def tick():
    with Session() as db:
        # 先补齐订阅：启用即回填历史批次并接续新批次，SQL 状态是 Redis 队列的持久兜底
        try:
            created=reconcile.reconcile_all(db)
            reconcile.sync_items(db)
            if created:record(db,'worker','subscription.dispatched',{'jobs':created})
            db.commit()
            for job_id in created:reconcile_enqueue(job_id)
        except Exception:
            logging.exception('Subscription reconcile failed');db.rollback()
        queued=list(db.scalars(select(Job.id).where(Job.status=='queued').limit(3)))
    for job_id in queued:execute(job_id)
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled==True,Report.next_run<=time.time())):
            d=deliver(db,r)
            if d:record(db,'worker','report.delivered',{'id':r.id,'delivery':d.id})
        db.commit()
def reconcile_enqueue(job_id):
    try:
        r=Redis.from_url(REDIS_URL);r.rpush('analysis:queue',job_id);r.close()
    except Exception:
        pass
def main():
    r=Redis.from_url(REDIS_URL,socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status=='running')):
            j.status='queued';record(db,'worker','job.recovered',{'id':j.id})
        db.commit()
        # 崩溃恢复后重新镜像明细状态（running 已回退为 queued）
        reconcile.sync_items(db);db.commit()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item=r.blpop('analysis:queue',timeout=1)
            if item:execute(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry');time.sleep(2)
if __name__=='__main__':main()
