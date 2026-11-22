import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {ExternalLink} from 'lucide-react';
import {api, params} from '../api';
import {stanceLabels} from './agentartsReviewData';
import type {Criterion, Evidence, Validation} from './projectApi';
import './project-delivery-reader.css';

type DeliverySnapshot = {
  manifest: {
    project: {question: string; recommendation: string; open_questions: string; criteria: Criterion[]};
    review: {reviewer: string; note: string};
    evidence: Pick<Evidence, 'id' | 'paper_id' | 'criterion_id' | 'stance' | 'context' | 'snapshot'>[];
    validations?: Validation[];
  };
};

export default function ProjectDeliveryReader({projectId, deliveryId}: {projectId: string; deliveryId: string}) {
  const [open, setOpen] = useState(false);
  const snapshot = useQuery({
    queryKey: ['project-delivery', projectId, deliveryId],
    enabled: open,
    staleTime: Infinity,
    queryFn: ({signal}) => api<DeliverySnapshot>(
      '/projects/' + encodeURIComponent(projectId) + '/deliveries/' + encodeURIComponent(deliveryId), {signal},
    ),
  });
  const manifest = snapshot.data?.manifest;

  return <details className="project-delivery-reader" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>查看归档证据</summary>
    {open && (snapshot.isPending ? <p role="status">正在读取归档快照…</p> :
      snapshot.error ? <p role="alert">无法读取归档。 <button type="button" className="text-button"
        onClick={() => void snapshot.refetch()}>重试</button></p> :
      manifest && <div className="project-delivery-content">
        <h4>当时的研发判断</h4>
        <p>{manifest.project.question}</p>
        <p>{manifest.project.recommendation}</p>
        {!!manifest.project.open_questions && <p>未解问题 · {manifest.project.open_questions}</p>}
        <p>人工评审 · {manifest.review.reviewer} · {manifest.review.note}</p>
        <ul>{manifest.evidence.map(evidence => {
          const source = evidence.snapshot;
          const criterion = manifest.project.criteria.find(item => item.id === evidence.criterion_id);
          const href = '/api/paper/pdf?' + params({id: evidence.paper_id, version: source.paper_version}) + '#page=' + source.page;
          return <li key={evidence.id}>
            <strong>{criterion?.label ?? evidence.criterion_id} · {stanceLabels[evidence.stance]}</strong>
            <p>{source.paper_title}</p>
            <blockquote>{source.quote}</blockquote>
            <p>{evidence.context}</p>
            <a className="text-button" href={href} target="_blank" rel="noreferrer">
              打开归档 PDF v{source.paper_version} · 第 {source.page} 页 <ExternalLink size={14} aria-hidden="true"/>
            </a>
          </li>;
        })}</ul>
        {!!manifest.validations?.length && <>
          <h4>归档时的验证记录</h4>
          <ul>{manifest.validations.map(record => <li key={record.id}>
            <strong>{record.title} · {record.status === 'planned' ? '待验证' : '已记录结果'}</strong>
            <p>{record.success_criteria}</p>
            {record.observation && <p>{record.observation}</p>}
          </li>)}</ul>
        </>}
      </div>)}
  </details>;
}
