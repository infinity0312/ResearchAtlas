import {api} from '../api';
export type TrendScope={start:string;end:string;interval:'year'|'month';period:string|null};
export type TrendSourcePaper={id:string;title:string;quote:string;bottleneck:string;relevant?:boolean;exclusion_reason?:string;headroom_quote?:string;headroom_source?:{url:string;section:string};local_version:number|null;local_title:string|null};
export type TrendSnapshot={version:1;series_id:string;name:string;query:string;scope:TrendScope;focus_paper_id:string|null;source:string;date_basis:string;points:{period:string;count:number|null;fetched:string|null;source?:string|null;partial:boolean}[];growth:number|null;signal:{x:number|null;y:number|null;status:string;rebound:boolean;sample?:number;supported_sample?:number;population?:number;opportunity?:number|null};papers:TrendSourcePaper[]};
export type TrendLead={id:string;project_id:string;source_key:string;snapshot:TrendSnapshot;reason:string;status:'pending'|'kept'|'excluded';revision:number;created:string;updated:string;candidate_ids:{paper_id:string;candidate_id:string}[];source_changed:boolean;current_source_available:boolean};
export type TrendCaptureTarget={seriesId:string;start:string;end:string;interval:'year'|'month';period?:string;paperId?:string};
export type TrendPreview={source_key:string;snapshot:TrendSnapshot};
const json=(method:string,body:unknown)=>({method,body:JSON.stringify(body)});
export const trendLeadApi={
 preview:(target:TrendCaptureTarget)=>{const p=new URLSearchParams({series_id:target.seriesId,start:target.start,end:target.end,interval:target.interval});if(target.period)p.set('period',target.period);if(target.paperId)p.set('paper_id',target.paperId);return api<TrendPreview>('/projects/trend-preview?'+p)},
 capture:(pid:string,target:TrendCaptureTarget,sourceKey:string,reason:string,paperIds:string[])=>api<TrendLead>(`/projects/${encodeURIComponent(pid)}/trend-leads`,json('POST',{series_id:target.seriesId,start:target.start,end:target.end,interval:target.interval,...(target.period?{period:target.period}:{}),...(target.paperId?{focus_paper_id:target.paperId}:{}),source_key:sourceKey,reason,paper_ids:paperIds})),
 list:(pid:string)=>api<{items:TrendLead[];total:number}>(`/projects/${encodeURIComponent(pid)}/trend-leads`),
 update:(pid:string,lid:string,body:{revision:number;status:TrendLead['status'];reason:string})=>api<TrendLead>(`/projects/${encodeURIComponent(pid)}/trend-leads/${encodeURIComponent(lid)}`,json('PUT',body))
};
