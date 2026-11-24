import {createRoot} from 'react-dom/client';
import {ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight} from 'lucide-react';
import CaseDemo from './CaseDemo';
import './showcase.css';

const gallery = [
  {
    title: '把值得跟进的论文带进项目',
    body: '把趋势里的论文存为研发线索。几周后回到项目，仍然能看到当时的研究窗口、论文版本和保留理由。',
    file: 'trend-lead.png',
    width: 1208, height: 995,
    alt: '真实工作台的项目线索，显示导热界面趋势、统计范围、研究样本和候选论文来源。',
    caption: '研发项目 · 趋势线索与候选论文',
  },
  {
    title: '交付时保留当时的依据',
    body: '交付保存评审时的判断、反证和验证计划。展开归档，直接回到当时引用的 PDF，第几版、第几页一目了然。',
    file: 'frozen-delivery.png',
    width: 1210, height: 1158,
    alt: '真实工作台的已冻结交付，展开后显示人工评审、版本原页链接及待验证记录。',
    caption: '评审归档 · 决定、原页与验证记录',
  },
  {
    title: '论文更新时，知道哪项判断要复核',
    body: '从更新提醒进入受影响的标准，例如装配工况可比性。原交付继续引用旧版本，评审人可以逐项对照。',
    file: 'source-impact.png',
    width: 1210, height: 404,
    alt: '真实工作台的证据变化收件箱，显示论文从第一版更新至第二版及其影响的评审标准。',
    caption: '研发项目 · 证据变化与受影响标准',
  },
];

function ProductImage({
  file, caption, alt, width, height, featured = false,
}: {file: string; caption: string; alt: string; width: number; height: number; featured?: boolean}) {
  const image = './media/' + file;
  return <figure className={'showcase-product-image' + (featured ? ' is-featured' : '')}>
    <a href={image} target="_blank" rel="noreferrer" aria-label={`查看原尺寸截图，${caption}`}>
      <img src={image} alt={alt} width={width} height={height}
        fetchPriority={featured ? 'high' : undefined} loading={featured ? 'eager' : 'lazy'} decoding="async"/>
    </a>
    <figcaption>{caption}<ArrowUpRight size={14} aria-hidden="true"/></figcaption>
  </figure>;
}

const demoHref = './?view=demo#demo';
const workspaceHref = '../#page=projects';

function Product() {
  return <main id="main">
    <section className="showcase-hero">
      <div className="showcase-wrap">
        <div className="showcase-intro">
          <p className="showcase-overline">研发证据工作台</p>
          <h1>把研究证据<br className="showcase-mobile-break"/>带进研发决策</h1>
          <p>把论文、原文、反证和验证计划整理进同一份研发评审。每项判断都能回到当时的证据。</p>
          <div className="showcase-hero-actions">
            <a className="button primary" href={demoHref}>体验材料评审 <ArrowRight size={18} aria-hidden="true"/></a>
            <a className="showcase-secondary" href="#workflow">浏览产品能力 <ArrowDown size={16} aria-hidden="true"/></a>
          </div>
        </div>
        <ProductImage featured file="evidence-workspace.png" width={1900} height={1200}
          caption="ResearchAtlas 工作台 · 同屏核对主张与指定版本原页"
          alt="真实 ResearchAtlas 研发工作台，左侧是研究证据与适用性，右侧打开指定版本的论文 PDF 原页。"/>
      </div>
    </section>

    <section id="workflow" className="showcase-wrap showcase-gallery" aria-labelledby="workflow-title">
      <div className="showcase-section-heading">
        <div><h2 id="workflow-title">论文留下来，判断也留下来</h2><p>用同一个材料替换项目，看到从发现线索到交付复核的产品界面。</p></div>
      </div>
      {gallery.map(item => <article className="showcase-feature" key={item.file}>
        <div className="showcase-feature-copy"><h3>{item.title}</h3><p>{item.body}</p></div>
        <ProductImage file={item.file} caption={item.caption} alt={item.alt} width={item.width} height={item.height}/>
      </article>)}
      <p className="showcase-gallery-note">截图来自实际工作台的隔离演示项目。论文原页来自公开资料，候选材料和台架结果为合成样例。</p>
    </section>
    <section className="showcase-cta">
      <div className="showcase-wrap">
        <div><h2>看看反证如何改变一个研发决定</h2><p>亲手核对候选材料的依据，试着归档并复核。</p></div>
        <a className="button primary" href={demoHref}>打开案例体验 <ArrowRight size={18} aria-hidden="true"/></a>
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
          <a href="./#workflow">产品能力</a><a href={demoHref} aria-current={isDemo ? 'page' : undefined}>案例体验</a>
        </nav>
        <a className="button" href={workspaceHref}>打开工作台 <ArrowUpRight size={16} aria-hidden="true"/></a>
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
