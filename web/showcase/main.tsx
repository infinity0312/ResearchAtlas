import {createRoot} from 'react-dom/client';
import {ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight} from 'lucide-react';
import CaseDemo from './CaseDemo';
import './showcase.css';

const readerGallery = [
  {
    title: '把一篇论文拆成可以核对的问题',
    body: '快速看清作者要解决什么、实验怎样设置、结论能用到哪里。公式、实验对照表和原页索引留在同一份全文报告里。',
    file: 'paper-report.png',
    width: 1550, height: 1175,
    alt: '论文全文研读报告，显示研究问题、三频拟合方法、带页码的实验对照表和适用边界。',
    caption: '全文研读 · 研究问题、实验对照与适用边界',
  },
  {
    title: '点开结论，核对原句和实验图',
    body: '从结论旁的来源进入对应版本的 PDF，查看原段落和曲线。核对完，可以带着同一条证据回到分析上下文。',
    file: 'paper-pdf.png',
    width: 1550, height: 1175,
    alt: '论文阅读器的 PDF v1 第 9 页显示导热凝胶实验曲线，右侧保留结论、原句和返回分析的入口。',
    caption: '原文联动 · arXiv 论文 v1 · PDF 第 9 页',
  },
  {
    title: '读到疑问，就对着这篇论文问',
    body: '选中 PDF 段落或直接提问。示例回答分别引用第 9、14 页，解释为什么选替代材料时还要考虑界面热阻。',
    file: 'paper-qa.png',
    width: 1550, height: 1175,
    alt: '针对标称导热率的提问，Codex 示例答案对比凝胶与真空脂，并展开两条带页码的原文引用。',
    caption: '论文问答 · 回答、引文与 PDF 跳转',
  },
];

const libraryGallery = [
  {
    title: '先判断这篇值不值得细读',
    body: '按题录匹配找到论文，再结合重要性线索排序。在列表原位展开作者摘要与 AI 概要，先看方法和适用性，随时进入阅读全文。',
    file: 'paper-discovery.png',
    width: 1530, height: 616,
    alt: '论文列表中的原位展开卡片，分别显示作者摘要节选、AI 分析概要、方法和全文阅读入口。',
    caption: '论文库 · 作者摘要与 AI 概要分开展示',
  },
];

const projectGallery = [
  {
    title: '把值得跟进的论文带进项目',
    body: '将趋势发现存为研发线索。回到项目时，仍看得见原来的研究窗口、论文版本和保留理由。',
    file: 'trend-lead.png',
    width: 1208, height: 995,
    alt: '研发项目的趋势线索显示统计范围、研究样本和候选论文来源。',
    caption: '研发项目 · 趋势线索与候选论文',
  },
  {
    title: '围绕同一份证据做技术评审',
    body: '对照论文原页讨论结论是否适用于装配工况，把理由、反证和待做的验证留在项目里。',
    file: 'evidence-workspace.png',
    width: 1900, height: 1200,
    alt: '研发工作台左侧显示证据主张与适用性，右侧打开对应版本的论文 PDF。',
    caption: '研发评审 · 主张、适用性与原文同屏',
  },
  {
    title: '保留评审时做决定的依据',
    body: '冻结交付后，评审结论、反证、原页和待验证项可以一起回看。来源发布新版本时，变化提醒会指向对应的评审标准。',
    file: 'frozen-delivery.png',
    width: 1210, height: 1158,
    alt: '归档交付展开后显示人工评审、版本原页链接及待验证计划。',
    caption: '评审归档 · 决定、原页与验证记录',
  },
];

type GalleryImage = {file: string; caption: string; alt: string; width: number; height: number};
type Feature = GalleryImage & {title: string; body: string};

function ProductImage({file, caption, alt, width, height, featured = false}: GalleryImage & {featured?: boolean}) {
  const image = './media/' + file;
  return <figure className={'showcase-product-image' + (featured ? ' is-featured' : '')}>
    <a href={image} target="_blank" rel="noreferrer" aria-label={`查看原尺寸截图，${caption}`}>
      <img src={image} alt={alt} width={width} height={height}
        fetchPriority={featured ? 'high' : undefined} loading={featured ? 'eager' : 'lazy'} decoding="async"/>
    </a>
    <figcaption>{caption}<ArrowUpRight size={14} aria-hidden="true"/></figcaption>
  </figure>;
}

function FeatureGallery({items}: {items: Feature[]}) {
  return items.map(({title, body, ...shot}) => <article className="showcase-feature" key={shot.file}>
    <div className="showcase-feature-copy"><h3>{title}</h3><p>{body}</p></div>
    <ProductImage {...shot}/>
  </article>);
}

const demoHref = './?view=demo#demo';
const workspaceHref = '../#page=projects';
const libraryHref = '../#page=papers&days=0';
const sourceHref = 'https://arxiv.org/pdf/2603.22733v1#page=9';

function Product() {
  return <main id="main">
    <section className="showcase-hero">
      <div className="showcase-wrap">
        <div className="showcase-intro">
          <h1>用 AI 读懂论文，<br className="showcase-mobile-break"/>回到原文核对</h1>
          <p>从全文提炼方法、实验和局限。对着论文提问，按引用回到对应版本的 PDF。</p>
          <div className="showcase-hero-actions">
            <a className="button primary" href="#reading">看 AI 研读 <ArrowDown size={18} aria-hidden="true"/></a>
            <a className="showcase-secondary" href={libraryHref}>打开论文库 <ArrowUpRight size={16} aria-hidden="true"/></a>
          </div>
        </div>
        <ProductImage featured file="paper-evidence.png" width={1550} height={1175}
          caption="工作台实拍 · AI 提炼贡献、方法和局限 · 结论旁显示来源"
          alt="ResearchAtlas 分析阅读器左侧展示贡献、方法与局限，右侧展开所选结论在论文 v1 第 9 页的引文。"/>
      </div>
    </section>

    <section id="reading" className="showcase-wrap showcase-gallery" aria-labelledby="reading-title">
      <div className="showcase-section-heading">
        <div><h2 id="reading-title">一篇论文怎样读深</h2><p>用导热界面材料的公开论文，看分析、原文和问答怎样在同一阅读器里衔接。</p></div>
      </div>
      <FeatureGallery items={readerGallery}/>
      <p className="showcase-gallery-note">分析与问答为 Codex 预生成示例。原文摘自 Chen、Qian 与 Jiang 的论文 arXiv 2603.22733v1。 <a href={sourceHref} target="_blank" rel="noreferrer">论文原页</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a></p>
    </section>

    <div className="showcase-library">
      <section id="discovery" className="showcase-wrap showcase-gallery" aria-labelledby="discovery-title">
        <div className="showcase-section-heading">
          <div><h2 id="discovery-title">从单篇阅读扩展到研究方向</h2><p>在文献库筛选论文，在领域地图和趋势页比较一组研究。</p></div>
        </div>
        <FeatureGallery items={libraryGallery}/>
        <div className="showcase-workspace-links">
          <a href="../#page=map&days=0"><strong>领域地图 <ArrowUpRight size={15} aria-hidden="true"/></strong><span>从关系网络追溯引用，按分类相似性和时间脉络浏览。</span></a>
          <a href="../#page=trends&days=0"><strong>领域趋势 <ArrowUpRight size={15} aria-hidden="true"/></strong><span>看发文量、采样论文与研究信号，保留可跟进的方向。</span></a>
        </div>
      </section>
    </div>

    <section id="workflow" className="showcase-wrap showcase-gallery" aria-labelledby="workflow-title">
      <div className="showcase-section-heading">
        <div><h2 id="workflow-title">把研读证据带进研发评审</h2><p>沿用同一个材料主题，看到论文如何进入项目、影响判断并随交付留存。</p></div>
      </div>
      <FeatureGallery items={projectGallery}/>
      <article className="showcase-feature">
        <div className="showcase-feature-copy"><h3>论文换版，知道该复核哪一项</h3><p>变化提醒标出受影响的「装配工况可比性」。打开旧交付仍能看见当时使用的 v1。</p></div>
        <ProductImage file="source-impact.png" width={1210} height={404}
          caption="证据变化 · 版本差异与受影响标准"
          alt="证据变化卡片显示来源论文从 v1 更新至 v2，并定位到待复核的装配工况可比性标准。"/>
      </article>
      <p className="showcase-gallery-note">截图取自隔离演示工作台。候选材料、台架结果与评审记录为合成案例数据。</p>
    </section>
    <section className="showcase-cta">
      <div className="showcase-wrap">
        <div><h2>看看反证如何改变一个研发决定</h2><p>亲手核对候选材料的依据，试着归档并复核。</p></div>
        <a className="button primary" href={demoHref}>体验材料评审 <ArrowRight size={18} aria-hidden="true"/></a>
      </div>
    </section>
  </main>;
}

function Showcase() {
  const isDemo = new URLSearchParams(location.search).get('view') === 'demo' || location.hash === '#demo';
  return <div className="showcase">
    <a className="showcase-skip" href="#main">跳至正文</a>
    <header className="showcase-header">
      <div className="showcase-wrap showcase-bar">
        <a className="showcase-brand" href="./" aria-label="ResearchAtlas 产品首页">
          <img src="/favicon.svg?v=2" width="31" height="31" alt=""/>ResearchAtlas
        </a>
        <nav aria-label="产品导航">
          <a href="./#reading">AI 研读</a><a href="./#discovery">文献探索</a><a href="./#workflow">研发评审</a>
          <a href={demoHref} aria-current={isDemo ? 'page' : undefined}>案例体验</a>
        </nav>
        <a className="button" href={libraryHref}>打开工作台 <ArrowUpRight size={16} aria-hidden="true"/></a>
      </div>
    </header>
    {isDemo ? <main id="main" className="showcase-demo-page">
      <div className="showcase-wrap"><a className="showcase-secondary" href="./"><ArrowLeft size={16} aria-hidden="true"/>返回产品展示</a></div>
      <CaseDemo/>
    </main> : <Product/>}
    <footer className="showcase-footer">
      <div className="showcase-wrap"><strong>ResearchAtlas</strong><a href={workspaceHref}>进入研发工作台 <ArrowUpRight size={16} aria-hidden="true"/></a></div>
    </footer>
  </div>;
}

createRoot(document.getElementById('showcase')!).render(<Showcase/>);
