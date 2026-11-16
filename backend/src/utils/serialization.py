import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at','subscription_item_id']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def subscription_dict(s):
    return {'id':s.id,'name':s.name,'source':s.source,'status':s.status,'created_by':s.created_by,'created_at':s.created_at,'updated_at':s.updated_at}
def param_version_dict(v):
    return {'id':v.id,'subscription_id':v.subscription_id,'params':v.params,'effective_at':v.effective_at,'note':v.note}
def item_dict(i):
    return {'id':i.id,'subscription_id':i.subscription_id,'dataset_id':i.dataset_id,'job_id':i.job_id,'param_version_id':i.param_version_id,'status':i.status,'attempts':i.attempts,'last_error':i.last_error,'created_at':i.created_at,'updated_at':i.updated_at}
