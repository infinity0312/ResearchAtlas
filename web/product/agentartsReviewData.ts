import {params} from '../api';

export type Finding = {evidence_id: string; stance: 'supports' | 'contradicts' | 'uncertain'; reason: string};
export type Assessment = {
  criterion_id: string; label: string; status: 'supported' | 'contradicted' | 'mixed' | 'insufficient';
  findings: Finding[]; next_step: string;
};
export type Source = {evidence_id: string; paper_id: string; paper_version: number; title: string; pdf_page: number; quote: string};
export type Review = {
  id: string; state: 'running' | 'ready' | 'failed' | 'no_evidence'; query: string; project_revision: number;
  expected_revision: number; stale: boolean; execution_id: string | null; error: string; created?: string;
  sources: Source[]; assessments: Assessment[]; bindings: Record<string, string>;
};

export const assessmentLabels = {
  supported: '有支持依据', contradicted: '有反对依据', mixed: '正反依据并存', insufficient: '证据不足',
};
export const stanceLabels = {supports: '支持', contradicts: '反对', uncertain: '待核'};

export const reviewSourceHref = (source: Source) =>
  '/api/paper/pdf?' + params({id: source.paper_id, version: source.paper_version}) + '#page=' + source.pdf_page;

const plain = (value: string) => value.replace(/\s+/g, ' ').trim().replace(/[\\`*_{}\[\]<>#+.!|~&-]/g, '\\$&');

export function downloadReviewBrief(
  title: string, review: Review, stale: boolean,
  sourceHref = reviewSourceHref, provenance = 'AgentArts 证据评审',
) {
  const lines = [
    '# ' + plain(title), '',
    '证据评审草稿 · ' + plain(provenance), '',
    '- 草稿编号 ' + plain(review.id),
    '- 项目修订 ' + review.project_revision,
    '- 检索词 ' + plain(review.query),
  ];
  if (review.created) lines.push('- 生成时间 ' + plain(review.created));
  if (review.execution_id) lines.push('- 执行记录 ' + plain(review.execution_id));
  if (stale) lines.push('', '**项目已更新。以下内容仅供回溯。**');
  if (review.state === 'no_evidence') lines.push('', '本轮无符合要求的来源，未调用工作流。');
  for (const assessment of review.assessments) {
    lines.push('', '## ' + plain(assessment.label), '', assessmentLabels[assessment.status], '',
      '下一步 · ' + plain(assessment.next_step));
    for (const finding of assessment.findings) {
      const source = review.sources.find(item => item.evidence_id === finding.evidence_id);
      if (!source) continue;
      const binding = review.bindings[assessment.criterion_id + ':' + finding.evidence_id];
      const url = new URL(sourceHref(source), window.location.href).href;
      lines.push('', '### ' + stanceLabels[finding.stance] + ' · ' + plain(source.title), '',
        '来源标识 · ' + plain(source.paper_id),
        `[v${source.paper_version} · 第 ${source.pdf_page} 页](${url})`, '', '> ' + plain(source.quote), '',
        '判断依据 · ' + plain(finding.reason), '',
        binding ? '采纳记录 · ' + plain(binding) : '采纳记录 · 尚未采纳');
    }
  }
  const handle = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], {type: 'text/markdown;charset=utf-8'}));
  const link = document.createElement('a');
  link.download = 'ResearchAtlas-' + review.id.replace(/[^a-zA-Z0-9_-]/g, '') + '.md';
  link.href = handle;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(handle), 1000);
}
