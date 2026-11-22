import {createRoot} from 'react-dom/client';
import {ArrowDown, ArrowRight, ArrowUpRight, FileSearch, History, ShieldCheck} from 'lucide-react';
import CaseDemo from './CaseDemo';
import {sampleQuestion, sampleTitle, trend} from './sample';
import './showcase.css';

function Showcase() {
  return <div className="showcase">
    <a className="showcase-skip" href="#main">跳至正文</a>
    <header className="showcase-header">
      <div className="showcase-wrap showcase-bar">
        <a className="showcase-brand" href="./" aria-label="ResearchAtlas 产品首页">
          <img src="/favicon.svg?v=2" width="31" height="31" alt=""/>ResearchAtlas
        </a>
        <nav aria-label="产品导航">
          <a href="#demo">交互体验</a><a href="#workflow">产品能力</a>
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
            <p>从趋势中发现值得跟进的论文，核对原页，再把反证和缺口变成验证任务。交付后仍能追到当时的版本，知道哪条判断需要重审。</p>
            <div className="showcase-hero-actions">
              <a className="button primary" href="#demo">体验材料评审 <ArrowDown size={18} aria-hidden="true"/></a>
              <a className="showcase-secondary" href="#workflow">了解产品能力 <ArrowRight size={16} aria-hidden="true"/></a>
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
              <div><dt>研究线索</dt><dd>{trend.name}</dd></div>
              <div><dt>评审问题</dt><dd>候选 B 是否具备替换依据</dd></div>
              <div><dt>最后一步</dt><dd>交付归档与论文版本复核</dd></div>
            </dl>
          </div>
        </div>
      </section>
      <CaseDemo/>
      <section id="workflow" className="showcase-wrap showcase-section" aria-labelledby="workflow-title">
        <div className="showcase-section-heading">
          <div><h2 id="workflow-title">论文线索如何变成研发决定</h2><p>从发现、判断到交付，每一步都留下下一位评审人能核对的记录。</p></div>
        </div>
        <div className="workflow-grid">
          <article><FileSearch aria-hidden="true"/><h3>把趋势带进项目</h3><p>先判断一篇论文与工况是否匹配，再比较研究价值。收录后，项目里保留线索、论文版本和收录理由。</p></article>
          <article><ShieldCheck aria-hidden="true"/><h3>让反证影响下一步</h3><p>按标准核对支持与反对。人工采纳关键证据，将尚未解决的问题安排为有工况与验收条件的验证。</p></article>
          <article><History aria-hidden="true"/><h3>交付之后还能重审</h3><p>交付记录能回到当时的 PDF 版本。作者更新论文后，只复核依赖这个来源的判断，保留原档案。</p></article>
        </div>
      </section>
    </main>
    <footer className="showcase-footer">
      <div className="showcase-wrap"><strong>ResearchAtlas</strong><a href="../#page=projects">进入研发工作台 <ArrowUpRight size={16} aria-hidden="true"/></a></div>
    </footer>
  </div>;
}

createRoot(document.getElementById('showcase')!).render(<Showcase/>);
