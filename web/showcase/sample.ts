import type {Assessment, Review, Source} from '../product/agentartsReviewData';

export const sampleTitle = '电子封装导热材料替代';
export const sampleQuestion = '候选材料在共同工况下，是否具备替换依据？';
export const sampleTerms = [
  {id: 'thermal', label: '基准工况下的导热试验'},
  {id: 'aging', label: '长期热老化试验'},
] as const;
export type SampleTerm = typeof sampleTerms[number]['id'];

const sources: Source[] = [
  {
    evidence_id: 'e1', paper_id: 'panel-a', paper_version: 1, title: 'A 组 · 测试工况', pdf_page: 1,
    quote: 'Fictional test A measured thermal conductivity at the same sample thickness and reference temperature.',
  },
  {
    evidence_id: 'e2', paper_id: 'panel-b', paper_version: 1, title: 'B 组 · 导热测试结果', pdf_page: 1,
    quote: 'Fictional test B did not meet the thermal conductivity requirement under the reference test conditions.',
  },
];

const assessments: Assessment[] = [
  {
    criterion_id: 'conditions', label: '测试条件可比性', status: 'supported',
    next_step: '核对两组的样品制备与仪器误差。',
    findings: [{evidence_id: 'e1', stance: 'supports', reason: '样品厚度和测试温度一致，支持在共同基准下比较。'}],
  },
  {
    criterion_id: 'thermal', label: '导热性能达标', status: 'contradicted',
    next_step: '复核 B 组原始数据，并在相同测试条件下复测。',
    findings: [{evidence_id: 'e2', stance: 'contradicts', reason: 'B 组在基准工况下未达到导热要求，需保留这一反证。'}],
  },
  {
    criterion_id: 'insulation', label: '电绝缘验证', status: 'insufficient',
    next_step: '补充同一工况下的电绝缘试验数据。', findings: [],
  },
];

export function replaySample(term: SampleTerm): Review {
  const matched = term === 'thermal';
  return {
    id: matched ? 'sample-thermal-v1' : 'sample-aging-v1',
    state: matched ? 'ready' : 'no_evidence',
    query: sampleTerms.find(item => item.id === term)!.label,
    project_revision: 1,
    expected_revision: 1,
    stale: false,
    execution_id: null,
    error: '',
    sources: matched ? sources : [],
    assessments: matched ? assessments : [],
    bindings: {},
  };
}

export const sampleSourceHref = (source: Source) => './sources/' + source.paper_id + '.pdf#page=' + source.pdf_page;
