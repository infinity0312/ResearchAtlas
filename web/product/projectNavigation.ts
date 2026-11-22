export type ProjectFocus={id:string;evidenceId?:string;candidateId?:string;trendLeadId?:string};
export type TrendFocus={id:string;start:string;end:string;interval:'year'|'month';period?:string};
export function projectHref(target:ProjectFocus){const p=new URLSearchParams({page:'projects',project_id:target.id});if(target.evidenceId)p.set('evidence_id',target.evidenceId);if(target.candidateId)p.set('candidate_id',target.candidateId);if(target.trendLeadId)p.set('trend_lead_id',target.trendLeadId);return '#'+p}
export function trendHref(target:TrendFocus){const p=new URLSearchParams({page:'trends',trend_id:target.id,trend_start:target.start,trend_end:target.end,trend_interval:target.interval});if(target.period)p.set('trend_period',target.period);return '#'+p}
