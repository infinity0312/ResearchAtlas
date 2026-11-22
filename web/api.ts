export type Domain={id:string;name:string;description:string;query:string;topics:string[];taxonomy_version:number;taxonomy_origin:string;color:string;count:number;auto_sync:boolean;last_sync:string|null;sync_note:string};
export type Claim={kind:'method'|'contribution'|'limitation';text:string;basis:string;page:number;quote:string;supporting_evidence?:{page:number;quote:string}[]};
export type AnalysisQuality={contract_version:1;provenance:'evidence_pipeline'|'legacy';evidence:'verified'|'partial'|'unverified';grounding:'bound'|'legacy';semantic:'not_reviewed'|'model_reviewed'|'human_reviewed';freshness:'current'|'stale';rejected_evidence:number};
export type ModelBudget={daily_tokens:number|null;task_tokens:number|null;task_calls:number|null;timezone:string};
export type ModelUsage={day:string;timezone:string;budget:Omit<ModelBudget,'timezone'>;totals:{attempts:number;settled_calls:number;pending_calls:number;unknown_calls:number;nonbillable_calls:number;known_tokens:number;reserved_tokens:number;committed_tokens:number}};
export type Result={editorial_edit?:{base_analysis_id:number;edited_at:string;editor:string;original_model:string};fulltext_markdown?:string;summary:string;topics:string[];methods:string[];claims:Claim[];rejected_evidence:number;pages:number;coverage:string;section_summaries:string[]};
export type SearchRank={exact_id:boolean;title_hits:number;terms:number;local_citations:number;curation_reason?:string|null};
export type Paper={search_rank?:SearchRank;id:string;version:number;title:string;abstract:string;authors:string[];categories:string[];published:string;updated:string;date_basis:string;saved:boolean;read:boolean;analysis:null|{topics:string[];methods:string[];summary:string;version:number;taxonomy_version:number;quality?:AnalysisQuality}};
export type Detail=Omit<Paper,'analysis'>&{domain_ids:string[];has_pdf:boolean;pdf_version:number;analysis:null|{id:number;result:Result;version:number;taxonomy_version:number;model:string;created:string;domain_id:string;quality?:AnalysisQuality}};
export type Job={id:string;kind:string;payload:{ids?:string[];interval?:string;quality?:boolean;analysis_id?:string;claim_index?:string;domain_id?:string;domain_ids?:string[];start?:string;end?:string};result?:{stage?:string;resume_after?:string;catalog_count?:number};status:string;progress:number;message:string;created:string};
export type Overview={total:number;saved:number;analyzed:number;announcements:number;daily:{date:string;count:number}[];topics:{name:string;value:number}[];methods:{name:string;value:number}[];categories:{name:string;value:number}[];matrix:{topic:string;method:string;value:number}[]};
export type Survey={id:string;domain_id:string;title:string;status:string;created:string;draft:{topics?:{name:string;definition:string;page:number;quote:string}[]}};
export class ApiError extends Error{constructor(message:string,public status:number){super(message);this.name='ApiError'}}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
 const response=await fetch('/api'+path,{...init,headers:{'X-Atlas-Client':'1',...(init.body instanceof FormData?{}:{'Content-Type':'application/json'}),...init.headers}});
 if(!response.ok){let message='请求失败，请稍后重试';try{const e=await response.json();message=typeof e.detail==='string'?e.detail:'输入内容不符合要求'}catch{}throw new ApiError(message,response.status)}
 return response.json();
}
export const params=(obj:Record<string,string|number|boolean|undefined>)=>new URLSearchParams(Object.entries(obj).filter(([,v])=>v!==undefined&&v!=='').map(([k,v])=>[k,String(v)])).toString();
export const date=(s:string)=>new Date(s).toLocaleDateString('zh-CN',{month:'short',day:'numeric'});
