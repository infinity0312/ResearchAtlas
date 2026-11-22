import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,params,type AnalysisQuality} from './api';
import './research-workflow.css';

type Trace = {
 paper_version:number;
 pdf_available:boolean;
 parsed_pages:number|null;
 date_basis:string;
 first_seen:string;
 curation_reason:string|null;
 analysis:null|{
  id:number;created:string;taxonomy_version:number;
  recorded_model:string;editorial_edit:boolean;
  reviewers:{role:'independent'|'coordinator';model:string;pages:number[]}[];
  quality:AnalysisQuality;has_report:boolean;report_sections:string[];
  claim_count:number;quotes_located:number|null;analysis_page_count:number|null;
 };
};

export default function PaperResearchTrace({paperId,version,analysisId}:{paperId:string;version:number;analysisId?:number}){
 const [open,setOpen]=useState(false);
 const query=useQuery({
  queryKey:['paper-research-trace',paperId,version,analysisId],
  queryFn:()=>api<Trace>('/paper/research-trace?'+params({id:paperId,version,analysis_id:analysisId})),
  enabled:open,
 });
 const record=query.data, analysis=record?.analysis;
 return <details className="paper-research-trace" onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary>来源、研读记录与待核项</summary>
  {open&&query.isPending&&<p role="status">正在读取研读记录…</p>}
  {query.error&&<p role="alert">{query.error.message} <button className="text-button" onClick={()=>void query.refetch()}>重新读取</button></p>}
  {record&&<div className="paper-research-trace-body">
   <dl>
    <div><dt>收录</dt><dd>{paperId} · v{record.paper_version} · {record.date_basis==='imported'?'本地导入':record.date_basis==='announcement'?'公告日期口径':record.date_basis==='submitted'?'提交日期口径':record.date_basis}{record.first_seen&&<small>首次入库 {record.first_seen.slice(0,10)}</small>}{record.curation_reason&&<small>入选依据：{record.curation_reason}</small>}</dd></div>
    <div><dt>原文与解析</dt><dd>{record.pdf_available?'本地版本 PDF 可读':'待取得此版本 PDF'} · {record.parsed_pages!==null?`已找到 ${record.parsed_pages} 页解析记录`:'暂无可核对的解析快照'}</dd></div>
    <div><dt>生成与发布</dt><dd>{analysis?<>{analysis.recorded_model||'模型未记录'} · 分析 #{analysis.id} · 分类 v{analysis.taxonomy_version}{analysis.editorial_edit?' · 有人工编辑':''}<small>{analysis.has_report?`有全文报告 · 标准章节 ${analysis.report_sections.length}/5`:'已有结构化分析 · 待补全文报告'}</small></>:'待进行全文分析'}</dd></div>
    <div><dt>证据与复核</dt><dd>{analysis?<>{analysis.claim_count} 条主张 · {analysis.quotes_located===null?'等待解析快照以核对引文':`${analysis.quotes_located} 条可定位全部引文`}{analysis.reviewers.length?analysis.reviewers.map(r=><small key={r.role}>{r.role==='independent'?'独立复核':'协调复核'} · {r.model} · {r.pages.length} 页核查记录</small>):<small>当前分析暂无有效独立复核记录</small>}</>:'待生成来源主张'}</dd></div>
   </dl>
   {analysis?.quality.freshness==='stale'&&<p>待核对：论文、解析来源或分类已更新。</p>}
   {analysis&&analysis.quotes_located!==null&&analysis.quotes_located<analysis.claim_count&&<p>待核对：{analysis.claim_count-analysis.quotes_located} 条主张含无法定位的引文。</p>}
  </div>}
 </details>;
}
