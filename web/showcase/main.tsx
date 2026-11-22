import {useRef, useState, type FormEvent} from 'react';
import {createRoot} from 'react-dom/client';
import {
  ArrowDown, ArrowRight, ArrowUpRight, Check, ClipboardList, Download, FileSearch,
  ScanLine, Search, ShieldCheck, Workflow,
} from 'lucide-react';
import AgentArtsResults from '../product/AgentArtsResults';
import {downloadReviewBrief, type Review} from '../product/agentartsReviewData';
import {replaySample, sampleQuestion, sampleSourceHref, sampleTerms, sampleTitle, type SampleTerm} from './sample';
import './showcase.css';

const steps = [
  {id: 'retrieve', label: '检索材料', icon: Search, description: '按当前研发问题缩小证据范围。'},
  {id: 'verify', label: '核对原页', icon: ScanLine, description: '比较支持、反对与待补的依据。'},
  {id: 'deliver', label: '交付草稿', icon: ClipboardList, description: '汇总选择、引文和下一步。'},
] as const;
type Step = typeof steps[number]['id'];
const provenance = '样例回放 · 虚构材料与模拟评审输出';

function Demo() {
  const [term, setTerm] = useState<SampleTerm>('thermal');
  const [step, setStep] = useState<Step>('retrieve');
  const [review, setReview] = useState<Review | null>(null);
  const [downloaded, setDownloaded] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const adopted = Object.keys(review?.bindings ?? {}).length;
  const current = steps.find(item => item.id === step)!;

  function go(next: Step) {
    setStep(next);
    requestAnimationFrame(() => heading.current?.focus());
  }

  function retrieve(event: FormEvent) {
    event.preventDefault();
    setReview(replaySample(term));
    setDownloaded(false);
    go('verify');
  }

  function adopt(criterion: string, evidence: string) {
    setReview(value => value && {
      ...value, bindings: {...value.bindings, [criterion + ':' + evidence]: '样例采纳 · ' + evidence},
    });
    setDownloaded(false);
  }

  function reset() {
    setTerm('thermal');
    setReview(null);
    setDownloaded(false);
    go('retrieve');
  }

  return <section id="demo" className="showcase-wrap showcase-section" aria-labelledby="demo-title">
    <div className="showcase-section-heading">
      <div><h2 id="demo-title">亲手完成一轮评审</h2><p>{sampleTitle} · 虚构案例</p></div>
      <span className="demo-mode"><span/>样例回放</span>
    </div>
    <div className="demo-workspace">
      <aside className="demo-rail" aria-label="案例流程">
        <div className="demo-rail-context"><FileSearch size={20} aria-hidden="true"/><span>{sampleQuestion}</span></div>
        <ol>{steps.map(({id, label, icon: Icon}, index) =>
          <li key={id}><button type="button" aria-current={step === id ? 'step' : undefined}
            disabled={id !== 'retrieve' && (!review || (id === 'deliver' && review.state !== 'ready'))}
            onClick={() => go(id)}><Icon size={17} aria-hidden="true"/>{label}<span>0{index + 1}</span></button></li>)}</ol>
        {review && <button type="button" className="text-button demo-reset" onClick={reset}>重置体验</button>}
      </aside>
      <div className="demo-main">
        <div className="demo-heading">
          <h3 tabIndex={-1} ref={heading}>{current.label}</h3>
          <p>{current.description}</p>
        </div>
        {step === 'retrieve' && <form className="demo-search" onSubmit={retrieve}>
          <fieldset>
            <legend>选择本轮要找的证据</legend>
            {sampleTerms.map(entry => <label className="demo-option" key={entry.id}>
              <input type="radio" name="sample-term" value={entry.id} checked={term === entry.id}
                onChange={() => setTerm(entry.id)}/>
              {entry.label}
            </label>)}
          </fieldset>
          <button className="button primary" type="submit">检索样例语料 <ArrowRight size={17} aria-hidden="true"/></button>
        </form>}
        {step === 'verify' && review && (review.state === 'no_evidence' ?
          <div className="demo-empty">
            <FileSearch size={24} aria-hidden="true"/>
            <p><strong>未找到可核对的长期热老化证据</strong></p>
            <p>当前样例语料只包含基准工况下的导热试验。可以换一个检索主题。</p>
            <button type="button" className="button" onClick={() => go('retrieve')}>调整检索</button>
          </div> :
          <>
            <AgentArtsResults title={sampleTitle} review={review} sourceHref={sampleSourceHref} provenance={provenance}
              showExport={false} onAdopt={adopt}/>
            <div className="demo-next">
              <span role="status">本轮已采纳 {adopted} 条依据</span>
              <button type="button" className="button primary" onClick={() => go('deliver')}>
                查看交付草稿 <ArrowRight size={17} aria-hidden="true"/>
              </button>
            </div>
          </>
        )}
        {step === 'deliver' && review?.state === 'ready' && <div className="demo-delivery">
          <div className="demo-dossier">
            <ClipboardList size={27} aria-hidden="true"/>
            <div><strong>{sampleTitle}</strong><p>评审草稿 · 修订 {review.project_revision}</p></div>
          </div>
          <dl><div><dt>评审标准</dt><dd>{review.assessments.length}</dd></div>
            <div><dt>来源原页</dt><dd>{review.sources.length}</dd></div>
            <div><dt>已采纳依据</dt><dd>{adopted}</dd></div></dl>
          <p>草稿保留版本、页码、评审理由和待补验证。你的采纳结果仅保留在本次浏览器体验中。</p>
          <button type="button" className="button primary" onClick={() => {
            downloadReviewBrief(sampleTitle, review, false, sampleSourceHref, provenance);
            setDownloaded(true);
          }}><Download size={17} aria-hidden="true"/>下载 Markdown 草稿</button>
          {downloaded && <p role="status">下载已发起。</p>}
        </div>}
      </div>
    </div>
    <p className="demo-disclosure">体验使用两份虚构试验 PDF 和预设工作流输出。正式工作台以项目修订和获准的来源范围生成草稿，等待人工确认。</p>
  </section>;
}

function Showcase() {
  return <div className="showcase">
    <a className="showcase-skip" href="#main">跳至正文</a>
    <header className="showcase-header">
      <div className="showcase-wrap showcase-bar">
        <a className="showcase-brand" href="./" aria-label="ResearchAtlas 产品首页">
          <img src="/favicon.svg?v=2" width="31" height="31" alt=""/>ResearchAtlas
        </a>
        <nav aria-label="产品导航">
          <a href="#demo">交互体验</a><a href="#workflow">工作方式</a>
        </nav>
        <a className="button" href="../#page=projects">打开工作台 <ArrowUpRight size={16} aria-hidden="true"/></a>
      </div>
    </header>
    <main id="main">
      <section className="showcase-hero">
        <div className="showcase-wrap showcase-hero-grid">
          <div className="showcase-intro">
            <p className="showcase-overline">研发证据工作台</p>
            <h1>把研究证据<br/>带进研发决策</h1>
            <p>从论文检索到原页核对，把支持、反对和待验证的依据整理进同一个项目。每项判断都能回到原文版本与页码。</p>
            <div className="showcase-hero-actions">
              <a className="button primary" href="#demo">体验材料评审 <ArrowDown size={18} aria-hidden="true"/></a>
              <a className="showcase-secondary" href="#workflow">了解工作方式 <ArrowRight size={16} aria-hidden="true"/></a>
            </div>
          </div>
          <div className="showcase-plate">
            <div className="plate-header"><span>案例导览</span><span>电子封装研发</span></div>
            <div className="plate-body">
              <div className="plate-map" aria-hidden="true"><i/><i/><i/><i/><b/></div>
              <div className="plate-caption">
                <span>研发决策</span><h2>{sampleTitle}</h2>
                <p>{sampleQuestion}</p>
              </div>
            </div>
            <dl className="plate-outcomes">
              <div><dt>测试条件可比性</dt><dd><Check size={15} aria-hidden="true"/> 有支持依据</dd></div>
              <div><dt>导热性能达标</dt><dd><ScanLine size={15} aria-hidden="true"/> 有反对依据</dd></div>
              <div><dt>电绝缘验证</dt><dd><Search size={15} aria-hidden="true"/> 证据不足</dd></div>
            </dl>
          </div>
        </div>
      </section>
      <Demo/>
      <section id="workflow" className="showcase-wrap showcase-section" aria-labelledby="workflow-title">
        <div className="showcase-section-heading">
          <div><h2 id="workflow-title">让每项判断都有出处</h2><p>从发现研究线索，到沉淀团队可复核的结论。</p></div>
        </div>
        <div className="workflow-grid">
          <article><FileSearch aria-hidden="true"/><h3>找到相关工作</h3><p>先按研究问题匹配论文，再比较重要性。可把趋势线索和关联论文直接收录到研发项目。</p></article>
          <article><Workflow aria-hidden="true"/><h3>逐项核对证据</h3><p>按工况和标准记录支持、反证及缺口。将判断定位到对应版本、PDF 页码和引文。</p></article>
          <article><ShieldCheck aria-hidden="true"/><h3>确认并交付</h3><p>由评审人决定采纳哪些依据。导出草稿，或在工作台记录验证、保留项目修订与交付记录。</p></article>
        </div>
      </section>
    </main>
    <footer className="showcase-footer">
      <div className="showcase-wrap"><strong>ResearchAtlas</strong><a href="../#page=projects">进入研发工作台 <ArrowUpRight size={16} aria-hidden="true"/></a></div>
    </footer>
  </div>;
}

createRoot(document.getElementById('showcase')!).render(<Showcase/>);
