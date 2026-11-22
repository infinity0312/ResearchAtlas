import {useLayoutEffect, useRef, useState, type FormEvent} from 'react';
import {
  ArrowRight, ArrowUpRight, ClipboardList, Download, FileSearch, History, ScanLine, Search, TestTubeDiagonal,
} from 'lucide-react';
import AgentArtsResults from '../product/AgentArtsResults';
import {downloadMarkdown, type Review} from '../product/agentartsReviewData';
import {
  archiveId, archiveMarkdown, decision, evidenceReview, intakeId, paperId, paperTitle, paperUrl, provenance, reviewer, reviewNote,
  sampleQuestion, sampleTitle, searchTerms, sourceHref, trend, validation, type SearchTerm,
} from './sample';

const steps = [
  {id: 'discover', label: '发现线索', icon: Search, description: '先看论文为何匹配，再把值得追踪的来源带入项目。'},
  {id: 'verify', label: '核对原页', icon: ScanLine, description: '分别核对方法依据、台架反证和缺失验证。'},
  {id: 'validate', label: '安排验证', icon: TestTubeDiagonal, description: '将反证和缺口变成研发决定及下一项验证。'},
  {id: 'archive', label: '归档交付', icon: ClipboardList, description: '冻结这次判断，让下一位评审人能从记录找到原页。'},
  {id: 'monitor', label: '来源复核', icon: History, description: '回放同一篇论文的正式版本更新，定位受影响的判断。'},
] as const;
type Step = typeof steps[number]['id'];

function Discover({linked, onLink, onReview}: {linked: boolean; onLink: () => void; onReview: () => void}) {
  const [term, setTerm] = useState<SearchTerm>('thermal');
  const [searched, setSearched] = useState<SearchTerm | null>(null);
  const queryRef = useRef<HTMLFieldSetElement>(null);

  function find(event: FormEvent) {
    event.preventDefault();
    setSearched(term);
  }

  return <>
    <article className="case-record">
      <h4>研发问题</h4>
      <p>{sampleQuestion}</p>
      <p className="case-meta">本轮标准 · 装配工况可比性 · 导热性能　|　替换前待验证 · 电绝缘</p>
    </article>
    <form className="demo-search case-search" onSubmit={find}>
      <fieldset ref={queryRef}>
        <legend>选一个检索主题</legend>
        {searchTerms.map(entry => <label className="demo-option" key={entry.id}>
          <input type="radio" name="sample-term" value={entry.id} checked={term === entry.id}
            onChange={() => {setTerm(entry.id); setSearched(null);}}/>
          {entry.label}
        </label>)}
      </fieldset>
      <button className="button primary" type="submit">检索样例语料 <ArrowRight size={17} aria-hidden="true"/></button>
    </form>
    {searched === 'aging' && <div className="demo-empty">
      <p role="status"><strong>未找到候选 B 的长期热老化证据</strong></p>
      <p>相近材料的试验无法补足候选 B 的数据。试试装配压力与界面热阻。</p>
      <button type="button" className="button" onClick={() => {
        setTerm('thermal');
        setSearched(null);
        queryRef.current?.querySelector('input')?.focus();
      }}>调整检索</button>
    </div>}
    {searched === 'thermal' && <section className="case-results" aria-label="检索结果">
      <h4>匹配结果</h4>
      <p className="case-meta">限定在样例候选中。先匹配压力与界面热阻，再以是否提供受控测量作为案例内排序依据。</p>
      <ol className="case-rank">
        <li><strong>{paperTitle}</strong><small>直接匹配 · 受控压力测量 · arXiv:{paperId}v1</small></li>
        <li><strong>封装用导热胶的孔隙率与导热性能</strong><small>相关研究 · 比较厚度与热阻 · Polymers 2023</small></li>
      </ol>
      <details className="case-trend">
        <summary>展开趋势线索 · {trend.name}</summary>
        <p className="case-meta">历史窗口截至 {trend.date}，时间脉络来自三项公开研究。</p>
        <ol>{trend.milestones.map(item => <li key={item.year}>
          <time>{item.year}</time><a href={item.href} target="_blank" rel="noreferrer">{item.label} <ArrowUpRight size={13} aria-hidden="true"/></a>
        </li>)}</ol>
        <p>{trend.reason}</p>
      </details>
      <div className="demo-next">
        <span role="status">{linked ? `已关联 · ${intakeId} · ${paperId}v1 · 保留原趋势与收录理由` : '第一篇论文尚未入项目'}</span>
        {!linked ? <button type="button" className="button primary" onClick={onLink}>收录并关联 v1</button> :
          <button type="button" className="button primary" onClick={onReview}>进入证据评审 <ArrowRight size={17} aria-hidden="true"/></button>}
      </div>
    </section>}
  </>;
}

export default function CaseDemo() {
  const [step, setStep] = useState<Step>('discover');
  const [linked, setLinked] = useState(false);
  const [review, setReview] = useState<Review>(evidenceReview);
  const [planned, setPlanned] = useState(false);
  const [signed, setSigned] = useState(false);
  const [archived, setArchived] = useState<Review | null>(null);
  const [latest, setLatest] = useState<1 | 2>(1);
  const [queued, setQueued] = useState(false);
  const [session, setSession] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const focusAfterNavigation = useRef(false);
  const current = steps.find(item => item.id === step)!;
  const reviewed = Boolean(review.bindings['conditions:e1'] && review.bindings['thermal:e2']);
  const accessible = {discover: true, verify: linked, validate: reviewed, archive: planned, monitor: Boolean(archived)};

  function go(next: Step) {
    if (next === step) return;
    focusAfterNavigation.current = true;
    setStep(next);
  }

  useLayoutEffect(() => {
    if (!focusAfterNavigation.current) return;
    focusAfterNavigation.current = false;
    heading.current?.focus();
  }, [step, session]);

  function reset() {
    setLinked(false);
    setReview(evidenceReview);
    setPlanned(false);
    setSigned(false);
    setArchived(null);
    setLatest(1);
    setQueued(false);
    setSession(value => value + 1);
    focusAfterNavigation.current = true;
    setStep('discover');
  }

  return <section id="demo" className="showcase-wrap showcase-section" aria-labelledby="demo-title">
    <div className="showcase-section-heading">
      <div><h2 id="demo-title">走完一项研发决策</h2><p>{sampleTitle} · 从研究线索到来源复核</p></div>
      <span className="demo-mode"><span/>历史场景回放</span>
    </div>
    <div className="demo-workspace">
      <aside className="demo-rail" aria-label="案例流程">
        <div className="demo-rail-context"><FileSearch size={20} aria-hidden="true"/><span>{sampleQuestion}</span></div>
        <ol>{steps.map(({id, label, icon: Icon}, index) =>
          <li key={id}><button type="button" aria-current={step === id ? 'step' : undefined}
            disabled={!accessible[id]} onClick={() => go(id)}>
            <Icon size={17} aria-hidden="true"/>{label}<span>0{index + 1}</span>
          </button></li>)}</ol>
        {linked && <button type="button" className="text-button demo-reset" onClick={reset}>重置体验</button>}
      </aside>
      <div className="demo-main">
        <div className="demo-heading"><h3 tabIndex={-1} ref={heading}>{current.label}</h3><p>{current.description}</p></div>
        {step === 'discover' && <Discover key={session} linked={linked} onLink={() => setLinked(true)} onReview={() => go('verify')}/>}
        {step === 'verify' && <>
          <AgentArtsResults title={sampleTitle} review={review} sourceHref={sourceHref} provenance={provenance}
            showExport={false} busy={Boolean(archived)} onAdopt={(criterion, evidence) => {
              setReview(currentReview => ({
                ...currentReview,
                bindings: {...currentReview.bindings, [criterion + ':' + evidence]: '样例采纳 · ' + evidence},
              }));
            }}/>
          <div className="case-record">
            <h4>替换前待验证 · 电绝缘</h4>
            <p>当前记录缺少候选 B 在相同装配工况下的绝缘试验。将这一缺口带入验证计划。</p>
          </div>
          <div className="demo-next">
            <span role="status">{reviewed ? '方法依据和反证均已采纳' : '打开原页，核对并采纳方法依据与反证'}</span>
            <button type="button" className="button primary" disabled={!reviewed}
              onClick={() => go('validate')}>进入验证计划 <ArrowRight size={17} aria-hidden="true"/></button>
          </div>
        </>}
        {step === 'validate' && <>
          <div className="case-decision">
            <div><span>评审前</span><strong>候选 B 等待替换评审</strong></div>
            <ArrowRight size={19} aria-hidden="true"/>
            <div><span>{planned ? '已记录的决定' : '拟定决定'}</span><strong>{decision}</strong></div>
          </div>
          <div className="case-record">
            <h4>{validation.title}</h4>
            <p>{validation.conditions}</p><p>{validation.threshold}</p>
            <p className="case-meta">{validation.owner} · {planned ? '已安排，待录入结果' : '待安排'}</p>
          </div>
          <div className="demo-next">
            <span>台架反证与电绝缘缺口均进入验证计划。</span>
            {!planned ? <button type="button" className="button primary" onClick={() => setPlanned(true)}>记录决定与验证计划</button> :
              <button type="button" className="button primary" onClick={() => go('archive')}>进入交付 <ArrowRight size={17} aria-hidden="true"/></button>}
          </div>
        </>}
        {step === 'archive' && <>
          <div className="case-record">
            <h4>本轮人工评审</h4>
            <p>{reviewNote}</p>
            <p className="case-meta">{signed ? `已记录 · ${reviewer}` : '待记录评审意见'}</p>
          </div>
          <div className="case-record case-deliverable">
            <h4>{sampleTitle}</h4>
            <p><strong>{decision}</strong></p>
            <p>{archived ? `档案 ${archiveId} · 项目修订 4 · 已冻结` : '待归档 · 已采纳两条证据，已安排一项验证'}</p>
            {archived && <p className="case-meta">收录记录 {intakeId} · 公开论文 v1 · 台架记录 v1 · 验证待录入结果</p>}
          </div>
          {archived && <p className="case-archive-source">
            <a href={paperUrl(1)} target="_blank" rel="noreferrer">回到归档引用的论文 v1 第 1 页 <ArrowUpRight size={15} aria-hidden="true"/></a>
          </p>}
          <div className="demo-next">
            {!signed ? <button type="button" className="button primary" onClick={() => setSigned(true)}>记录人工复核</button> :
              !archived ? <button type="button" className="button primary" onClick={() => setArchived(review)}>冻结评审交付</button> : <>
              <button type="button" className="button" onClick={() => downloadMarkdown(archiveId, archiveMarkdown(archived))}>
                <Download size={17} aria-hidden="true"/>下载归档 Markdown
              </button>
              <button type="button" className="button primary" onClick={() => go('monitor')}>检查来源更新 <ArrowRight size={17} aria-hidden="true"/></button>
            </>}
          </div>
        </>}
        {step === 'monitor' && <>
          <div className="case-record"><h4>{paperTitle}</h4>
            <p>归档引用 v1 · 2026-03-24。arXiv 随后于 2026-03-30 发布 v2。</p>
            <button type="button" className="button primary" disabled={latest === 2} onClick={() => setLatest(2)}>
              {latest === 2 ? '已发现 v2' : '回放 v2 发布事件'}
            </button>
          </div>
          {latest === 2 && <>
            <div className="case-decision case-versions" role="group" aria-label="论文版本对照">
              <div><a href={paperUrl(1)} target="_blank" rel="noreferrer">归档版本 v1 · 第 1 页 <ArrowUpRight size={15} aria-hidden="true"/></a>
                <p>摘要将脂类材料本体热学性质描述为接近不随压力变化。</p></div>
              <ArrowRight size={19} aria-hidden="true"/>
              <div><a href={paperUrl(2)} target="_blank" rel="noreferrer">新版本 v2 · 第 1 页 <ArrowUpRight size={15} aria-hidden="true"/></a>
                <p>摘要加入测量不确定度的限定。界面热阻对压力的依赖仍然明显。</p></div>
            </div>
            <div className="case-record">
              <h4>受影响的评审标准 · 装配工况可比性</h4>
              <p>复核压力和测量不确定度能否用于本项目。候选 B 的台架反证和电绝缘待验证项仍按各自来源处理。</p>
              <p className="case-meta">档案 {archiveId} 仍保留 v1 引用。</p>
            </div>
            <div className="demo-next">
              <span role="status">{queued ? '已加入复核清单 · 装配工况可比性' : '当前状态 · 需人工复核'}</span>
              <button type="button" className="button" disabled={queued} onClick={() => setQueued(true)}>加入复核清单</button>
            </div>
          </>}
        </>}
      </div>
    </div>
    <p className="demo-disclosure">公开论文与发布日期来自原始来源。候选 B、台架试验和评审输出用于模拟。记录只保留在本次体验中，打开公开原页需要网络。</p>
  </section>;
}
