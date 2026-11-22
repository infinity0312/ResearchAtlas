import type {AnalysisQuality as Quality} from './api';
import './analysis-quality.css';

const evidenceLabels:Record<Quality['evidence'],string>={verified:'引文已核验',partial:'引文部分核验',unverified:'引文未核验'};
const semanticLabels:Record<Quality['semantic'],string>={not_reviewed:'语义未复核',model_reviewed:'语义经模型复核',human_reviewed:'语义经人工复核'};

function description(quality:Quality){
 return [evidenceLabels[quality.evidence],quality.grounding==='bound'?'结论已绑定依据':'结论绑定未核验',semanticLabels[quality.semantic],quality.freshness==='stale'?'结果待更新':'当前版本'].join(' · ');
}

/** Render only the API's canonical quality contract; older responses carry no status. */
export default function AnalysisQuality({quality,compact=false}:{quality?:Quality;compact?:boolean}){
 if(!quality||quality.contract_version!==1)return null;
 const evidence=evidenceLabels[quality.evidence];
 const semantic=semanticLabels[quality.semantic];
 if(compact)return <span className={'analysis-quality-compact '+quality.evidence} title={description(quality)} aria-label={description(quality)}>{evidence}{quality.freshness==='stale'?' · 待更新':''}{quality.semantic==='not_reviewed'?' · 语义未复核':''}</span>;
 return <details className="analysis-quality">
  <summary aria-label="分析质量与核验范围"><span className="analysis-quality-title">分析质量</span><span className={'analysis-quality-status '+quality.evidence}>{evidence}</span><span className="analysis-quality-status">{semantic}</span>{quality.freshness==='stale'&&<span className="analysis-quality-status stale">结果待更新</span>}<span className="analysis-quality-expand">查看核验范围</span></summary>
  <dl>
   <div><dt>分析来源</dt><dd>{quality.provenance==='evidence_pipeline'?'证据约束分析':'历史分析'}</dd></div>
   <div><dt>引文核验</dt><dd>{evidence}；被拒绝的依据 {quality.rejected_evidence} 条</dd></div>
   <div><dt>结论与依据</dt><dd>{quality.grounding==='bound'?'结论引用了已通过校验的依据':'历史结果尚未经过结论绑定校验'}</dd></div>
   <div><dt>语义复核</dt><dd>{semantic}</dd></div>
   <div><dt>结果时效</dt><dd>{quality.freshness==='stale'?'论文、分类版本或解析来源已变化，可重新分析':'与当前论文、分类及解析来源版本一致'}</dd></div>
  </dl>
  <p>引文核验检查原文片段，结论绑定检查依据引用。结论是否准确表达原文，由语义复核单独记录。</p>
 </details>;
}
