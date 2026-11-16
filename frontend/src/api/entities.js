import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const subscriptions={
 list:()=>api('/subscriptions'),
 get:id=>api('/subscriptions/'+id),
 create:data=>api('/subscriptions',{method:'POST',body:JSON.stringify(data)}),
 update:(id,data)=>api('/subscriptions/'+id,{method:'PATCH',body:JSON.stringify(data)}),
 pause:id=>api('/subscriptions/'+id+'/pause',{method:'POST'}),
 resume:id=>api('/subscriptions/'+id+'/resume',{method:'POST'}),
 reconcile:id=>api('/subscriptions/'+id+'/reconcile',{method:'POST'}),
 retryItem:itemId=>api('/subscriptions/items/'+itemId+'/retry',{method:'POST'})
};
