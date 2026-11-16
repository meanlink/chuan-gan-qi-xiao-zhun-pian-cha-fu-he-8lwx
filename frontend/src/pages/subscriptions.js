import {subscriptions,datasets} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {ItemStatus,SubscriptionStatus} from '../constants/enums.js';

const canWrite=()=>session.user.role!=='viewer';

export async function subscriptionsPage(){
 const [subs,allDatasets]=await Promise.all([subscriptions.list(),datasets.list()]);
 workspace.subscriptions=subs;workspace.datasets=allDatasets;
 const m=workspace.meta;
 const selected=subs[0]?await subscriptions.get(subs[0].id):null;
 workspace.selectedSubscription=selected?.subscription.id??null;
 return heading('06 / SOURCE WATCH','来源订阅自动复核','按数据来源建立订阅：启用即补齐历史批次并接续新批次，每个匹配批次恰有一份订阅分析；手动分析照常保留。')+
 '<div class="subscription-grid"><section class="panel"><div class="section-title"><h2>来源订阅</h2><span>'+subs.length+' 条</span></div><div class="batch-list">'+
 (subs.length?subs.map(s=>'<button class="batch-item" data-sub="'+s.id+'"><strong>'+esc(s.name)+'</strong><span>来源 '+esc(s.source)+'</span><small>'+esc(SubscriptionStatus[s.status]||s.status)+' · 更新 '+date(s.updated_at)+'</small></button>').join(''):'<p class="empty">尚未建立订阅。</p>')+
 '</div><div class="section-title"><h2>设置订阅</h2></div><form id="sub-form"><label>订阅名称<input name="name" required minlength="2" placeholder="例如：A 产线自动复核"></label><label>数据来源（精确匹配批次 source）<input name="source" required minlength="2" placeholder="例如：line-a.csv"></label><div class="parameter-grid">'+
 m.parameters.map(p=>'<label>'+esc(p.label)+(p.type==='select'?'<select name="param-'+esc(p.key)+'">'+p.options.map(o=>'<option value="'+esc(o.value)+'" '+(o.value==String(p.default)?'selected':'')+'>'+esc(o.label)+'</option>').join('')+'</select>':'<input type="number" step="any" name="param-'+esc(p.key)+'" value="'+esc(p.default)+'" min="'+esc(p.min??'')+'" max="'+esc(p.max??'')+'" required>')+'</label>').join('')+
 '</div><button type="submit" class="primary" '+(canWrite()?'':'disabled')+'>启用并补齐已有批次</button><p class="hint">订阅按来源精确匹配。启用后历史批次立即补齐，新接入批次由后台接续派发；观察员只读。</p></form></section>'+
 '<section class="panel" id="sub-detail">'+(selected?detailHtml(selected,m):emptyDetail())+'</section></div>';
}

function emptyDetail(){return '<div class="empty">选择左侧订阅查看覆盖缺口、失败原因与每份分析的参数依据。</div>';}

function detailHtml(d,m){
 const s=d.subscription,items=d.items,jobs=d.jobs,gaps=d.coverage_gaps,versions=d.param_versions;
 const dsName=id=>(workspace.datasets.find(x=>x.id===id)?.name)||('#'+id);
 const jobOf=itemId=>jobs.find(j=>j.subscription_item_id===itemId);
 const verOf=vid=>versions.find(v=>v.id===vid);
 const failed=items.filter(i=>i.status==='failed');
 return '<div class="section-title"><h2>'+esc(s.name)+'</h2><span>'+esc(SubscriptionStatus[s.status]||s.status)+'</span></div>'+
 '<div class="sub-toolbar"><button class="button small" data-refresh="'+s.id+'">立即补齐 ↻</button>'+
 (s.status==='active'?'<button class="button small" data-pause="'+s.id+'" '+(canWrite()?'':'disabled')+'>暂停订阅</button>':'<button class="button small primary" data-resume="'+s.id+'" '+(canWrite()?'':'disabled')+'>恢复并补齐积压</button>')+
 '<button class="button small" data-param-edit="'+s.id+'" '+(canWrite()?'':'disabled')+'>调整参数</button></div>'+
 '<div class="sub-stats">'+[['匹配批次',items.length],['覆盖缺口',gaps.length],['执行失败',failed.length],['参数版本',versions.length]].map(([k,v])=>'<div><span>'+k+'</span><strong>'+v+'</strong></div>').join('')+'</div>'+
 (gaps.length?'<p class="warning">覆盖缺口：以下匹配批次尚无订阅分析，点“立即补齐”或等待后台下一轮。'+gaps.map(g=>esc(g.name)).join('、')+'</p>':'<p class="hint">无覆盖缺口：该来源所有批次均已派发。</p>')+
 '<form id="param-form" class="param-form hidden" data-sub="'+s.id+'"><div class="parameter-grid">'+m.parameters.map(p=>'<label>'+esc(p.label)+(p.type==='select'?'<select name="param-'+esc(p.key)+'">'+p.options.map(o=>'<option value="'+esc(o.value)+'">'+esc(o.label)+'</option>').join('')+'</select>':'<input type="number" step="any" name="param-'+esc(p.key)+'" min="'+esc(p.min??'')+'" max="'+esc(p.max??'')+'" required>')+'</label>').join('')+'</div><p class="hint">新参数立即生成新版本：已提交批次的旧分析沿用旧参数，之后提交的批次采用新参数。</p><button class="primary" type="submit">保存为新参数版本</button></form>'+
 '<div class="section-title" style="margin-top:24px"><h2>派发明细（每批恰一份）</h2><span>'+items.length+' 条</span></div><div class="table-wrap"><table><thead><tr><th>数据批次</th><th>状态</th><th>尝试</th><th>参数依据</th><th>失败原因 / 操作</th></tr></thead><tbody>'+
 items.map(i=>{const j=jobOf(i.id),v=verOf(i.param_version_id);return '<tr><td>'+esc(dsName(i.dataset_id))+'</td><td><span class="status '+esc(i.status)+'">'+esc(ItemStatus[i.status]||i.status)+'</span></td><td>'+i.attempts+'</td><td>'+(v?'<button class="text-button" data-params="'+esc(JSON.stringify(v.params))+'" data-note="'+esc(v.note)+' @ '+date(v.effective_at)+'">版本 #'+v.id+' ↗</button>':'—')+'</td><td>'+(i.status==='failed'?'<span class="fail-text">'+esc(i.last_error||'未知错误')+'</span> '+(canWrite()?'<button class="text-button" data-retry="'+i.id+'">单独重试</button>':''):(j?'<a class="text-button" href="#/results/'+j.id+'">查看分析 ↗</a>':'—'))+'</td></tr>';}).join('')+
 '</tbody></table></div>'+
 '<div class="section-title" style="margin-top:24px"><h2>参数版本留痕</h2><span>以批次提交时间为界</span></div><div class="version-list">'+versions.map(v=>'<div class="version-item"><strong>版本 #'+v.id+'</strong><span>'+esc(v.note)+' · 生效 '+date(v.effective_at)+'</span><button class="text-button" data-params="'+esc(JSON.stringify(v.params))+'" data-note="版本 #'+v.id+'">查看参数</button></div>').join('')+'</div>';
}

export function bindSubscriptions(refresh){
 const reload=async id=>{const d=await subscriptions.get(id);workspace.selectedSubscription=id;document.querySelector('#sub-detail').innerHTML=detailHtml(d,workspace.meta);bindDetail(refresh);};
 document.querySelectorAll('[data-sub]').forEach(b=>b.onclick=()=>reload(Number(b.dataset.sub)));
 submit(document.querySelector('#sub-form'),async f=>{
  const params={};for(const p of workspace.meta.parameters){const value=f.get('param-'+p.key);params[p.key]=p.type==='number'?Number(value):value;}
  await subscriptions.create({name:f.get('name'),source:f.get('source'),params});
  notify('订阅已启用，后台正在补齐已有批次');await refresh();
 });
 bindDetail(refresh);
}

function bindDetail(refresh){
 const id=workspace.selectedSubscription;
 document.querySelector('[data-refresh]')?.addEventListener('click',async e=>{
  try{const r=await subscriptions.reconcile(Number(e.currentTarget.dataset.refresh));notify(r.created_jobs.length?'已补齐 '+r.created_jobs.length+' 个批次':'无覆盖缺口，未新建分析');await refresh();}catch(err){notify(err.message,true);}
 });
 document.querySelector('[data-pause]')?.addEventListener('click',async e=>{try{await subscriptions.pause(Number(e.currentTarget.dataset.pause));notify('订阅已暂停，期间积压保留');await refresh();}catch(err){notify(err.message,true);}});
 document.querySelector('[data-resume]')?.addEventListener('click',async e=>{try{await subscriptions.resume(Number(e.currentTarget.dataset.resume));notify('订阅已恢复，暂停期间积压批次已补齐');await refresh();}catch(err){notify(err.message,true);}});
 document.querySelector('[data-param-edit]')?.addEventListener('click',()=>document.querySelector('#param-form').classList.toggle('hidden'));
 const pf=document.querySelector('#param-form');
 if(pf)submit(pf,async f=>{
  const params={};for(const p of workspace.meta.parameters){const value=f.get('param-'+p.key);params[p.key]=p.type==='number'?Number(value):value;}
  await subscriptions.update(Number(pf.dataset.sub),{params});notify('已生成新参数版本；旧批次分析不受影响');await refresh();
 });
 document.querySelectorAll('[data-retry]').forEach(b=>b.onclick=async()=>{try{await subscriptions.retryItem(Number(b.dataset.retry));notify('已重新排队该批次，不影响其他批次');await refresh();}catch(err){notify(err.message,true);}});
 document.querySelectorAll('[data-params]').forEach(b=>b.onclick=()=>notify((b.dataset.note||'参数')+'：'+b.dataset.params));
}
