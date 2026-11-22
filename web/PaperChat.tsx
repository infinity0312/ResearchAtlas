import {useState,useEffect,useRef} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {MessageSquare,Send,LoaderCircle,ArrowUpRight,Trash2,RotateCcw,X} from 'lucide-react';
import {api} from './api';
import Markdown from './Markdown';
import './paper-chat.css';
import type {SelectedPassage} from './SelectionAsk';
import {legacyMath} from './legacyMath';
type Turn={id:string;version:number;question:string;selected_text?:string;selected_page?:number;answer:string;status:string;error:string;scope:string;model:string;sources:{index:number;page:number;text:string}[]};
export default function PaperChat({id,hasPdf,pdfVersion,onSource,passage,onPassageUsed}:{passage?:SelectedPassage|null;onPassageUsed?:()=>void;id:string;hasPdf:boolean;pdfVersion:number;onSource:(page:number)=>void}){
 const qc=useQueryClient(),[question,setQuestion]=useState(''),[sending,setSending]=useState(false),[error,setError]=useState(''),[draft,setDraft]=useState<{id:string;question:string}|null>(null);
 const [quote,setQuote]=useState<SelectedPassage|null>(passage||null),[deleted,setDeleted]=useState(false);
 const input=useRef<HTMLTextAreaElement>(null),scroll=useRef<HTMLDivElement>(null);
 useEffect(()=>{if(passage){setQuote(passage);setDeleted(false);input.current?.focus()}},[passage?.token]);
 const query=useQuery({queryKey:['paper-chat',id,deleted],queryFn:()=>api<Turn[]>('/paper/chat?id='+encodeURIComponent(id)+'&deleted='+deleted),refetchInterval:q=>sending||q.state.data?.some(t=>t.status==='pending')?2000:false});
 useEffect(()=>{if(scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight},[query.data?.length,sending,deleted]);
 async function changeRecord(t:Turn){try{await api('/paper/chat/'+t.id+(deleted?'/restore':'')+'?id='+encodeURIComponent(id),{method:deleted?'POST':'DELETE'});await qc.invalidateQueries({queryKey:['paper-chat',id]})}catch(e){setError((e as Error).message)}}
 const pending=sending||query.data?.some(t=>t.status==='pending');
 async function send(){
  const text=question.trim();if(!text||pending)return;
  const request_id=crypto.randomUUID();setSending(true);setError('');setDraft({id:request_id,question:text});setQuestion('');
  try{await api('/paper/chat?id='+encodeURIComponent(id),{method:'POST',body:JSON.stringify({question:text,request_id,selected_text:quote?.text||'',selected_page:quote?.page||0})});await qc.invalidateQueries({queryKey:['paper-chat',id]});setQuote(null);onPassageUsed?.()}
  catch(e){setError((e as Error).message);setQuestion(text)}finally{setSending(false);setDraft(null)}
 }
 return <section className="paper-chat"><header><div><span className="eyebrow">ASK THIS PAPER · DEEPSEEK</span><h3><MessageSquare size={19}/>提问记录</h3></div><div className="chat-header-actions"><span className="tag">AI 生成</span><button className="text-button" onClick={()=>setDeleted(!deleted)}>{deleted?'返回对话':'已删除记录'}</button></div></header><p className="chat-scope">优先使用当前版本已解析原文；未解析时使用摘要。对话按论文保存在本机。</p>
 {query.isLoading&&<p role="status">正在载入对话…</p>}
 {!deleted&&!query.data?.length&&!draft&&<div className="chat-starters">{['这篇论文解决了什么问题，关键创新在哪里？','请推导核心方法的数学公式，并解释每个符号。','实验结论有哪些局限？下一步可以如何改进？'].map(text=><button key={text} onClick={()=>setQuestion(text)}>{text}<ArrowUpRight size={14}/></button>)}</div>}
 <div className="chat-turns" ref={scroll} role="log" aria-label="论文提问记录">{query.data?.map(t=><article key={t.id}><div className="chat-question"><small>我的问题 · v{t.version}<button className="icon-button" aria-label={deleted?'恢复提问记录':'删除提问记录'} disabled={t.status==='pending'} onClick={()=>changeRecord(t)}>{deleted?<RotateCcw size={14}/>:<Trash2 size={14}/>}</button></small>{t.selected_text&&<blockquote className="chat-quoted"><small>选中内容{t.selected_page?` · 第 ${t.selected_page} 页`:''}</small><Markdown text={legacyMath(t.selected_text)}/></blockquote>}<p>{t.question}</p></div><div className="chat-answer"><div className="chat-answer-meta">DeepSeek · {t.scope}{t.model?' · '+t.model:''}</div>{t.status==='pending'?<p className="chat-wait" role="status"><LoaderCircle size={16} className="spin"/>正在阅读与回答，可切换页面，稍后回来查看。</p>:t.status==='failed'?<div role="alert"><p>{t.error}</p><button className="text-button" onClick={()=>setQuestion(t.question)}>重新编辑此问题</button></div>:<><Markdown text={legacyMath(t.answer)}/>{!!t.sources.length&&<details className="chat-sources"><summary>查看回答引用的原文片段（{t.sources.length}）</summary>{t.sources.map(s=><div key={s.index}><strong>片段 {s.index} · {s.page?'第 '+s.page+' 页':'原文摘要'}</strong><blockquote>{s.text}</blockquote>{s.page>0&&hasPdf&&t.version===pdfVersion&&<button className="text-button" onClick={()=>onSource(s.page)}>在 PDF 中查看 <ArrowUpRight size={13}/></button>}</div>)}</details>}</>}</div></article>)}</div>
 {draft&&!query.data?.some(t=>t.id===draft.id)&&<div className="chat-question"><small>我的问题</small><p>{draft.question}</p><p role="status" className="chat-wait"><LoaderCircle size={16} className="spin"/>正在提交…</p></div>}
 {(error||query.error)&&<p role="alert" className="notice error">{error||query.error?.message}</p>}
 {!deleted&&<form className="chat-composer" onSubmit={e=>{e.preventDefault();void send()}}><label htmlFor="paper-question">{query.data?.length?'继续提问':'针对本文提问'}</label>{quote&&<div className="chat-quote-draft"><div><strong>围绕选中内容提问{quote.page?` · 第 ${quote.page} 页`:''}</strong><button type="button" className="icon-button" aria-label="取消引用选中文本" onClick={()=>{setQuote(null);onPassageUsed?.()}}><X size={14}/></button></div><blockquote>{quote.text}</blockquote></div>}<textarea ref={input} id="paper-question" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="例如：公式中的量化误差如何传播？请结合原文推导。" maxLength={4000} rows={3} onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();void send()}}}/><footer><small>Ctrl / ⌘ + Enter 发送 · 使用已配置的 DeepSeek API</small><button className="button primary" disabled={!!pending||!question.trim()}>{pending?<LoaderCircle className="spin" size={15}/>:<Send size={15}/>} {pending?'回答中':'发送问题'}</button></footer></form>}{deleted&&!query.data?.length&&<p className="empty">暂无已删除记录</p>}</section>
}
