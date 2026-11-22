import {Download, ExternalLink} from 'lucide-react';
import {assessmentLabels, downloadReviewBrief, reviewSourceHref, stanceLabels, type Review, type Source} from './agentartsReviewData';
import './agentarts-review.css';

type Props = {
  title: string;
  review: Review;
  stale?: boolean;
  busy?: boolean;
  provenance?: string;
  showExport?: boolean;
  sourceHref?: (source: Source) => string;
  onAdopt: (criterion: string, evidence: string) => void;
};

export default function AgentArtsResults({
  title, review, stale = false, busy = false, provenance, showExport = true, sourceHref = reviewSourceHref, onAdopt,
}: Props) {
  if (!review.assessments.length) return null;
  return <div className="agentarts-assessments">
    <div className="agentarts-result-heading">
      <p className="muted">基于项目修订 {review.project_revision} 的草稿
        {review.execution_id && <> · 执行记录 <code>{review.execution_id}</code></>}
      </p>
      {showExport && <button type="button" className="button small"
        onClick={() => downloadReviewBrief(title, review, stale, sourceHref, provenance)}>
        <Download size={15} aria-hidden="true"/> 导出草稿
      </button>}
    </div>
    {stale && <p className="notice" role="status">项目修订已变化。可回看这份草稿，采纳前需重新评审。</p>}
    {review.assessments.map(row => <article key={row.criterion_id}>
      <h4>{row.label} <span className="tag" data-evidence-status={row.status}>{assessmentLabels[row.status]}</span></h4>
      <p>{row.next_step}</p>
      {row.findings.map(finding => {
        const source = review.sources.find(item => item.evidence_id === finding.evidence_id);
        if (!source) return null;
        const bound = review.bindings[row.criterion_id + ':' + source.evidence_id];
        return <details key={source.evidence_id} className="agentarts-finding">
          <summary><strong>{stanceLabels[finding.stance]}</strong> {source.title} · v{source.paper_version} / 第 {source.pdf_page} 页</summary>
          <blockquote lang={provenance ? 'en' : undefined}>{source.quote}</blockquote>
          <p>{finding.reason}</p>
          <div className="agentarts-finding-actions">
            <a className="text-button" href={sourceHref(source)} target="_blank" rel="noreferrer">
              查看该版本原页 <ExternalLink size={13} aria-hidden="true"/>
            </a>
            {bound ? <span className="tag" role="status">已采纳</span> :
              <button type="button" className="button small" disabled={busy || stale || finding.stance === 'uncertain'}
                onClick={() => onAdopt(row.criterion_id, source.evidence_id)}>采纳此证据</button>}
          </div>
        </details>;
      })}
    </article>)}
  </div>;
}
