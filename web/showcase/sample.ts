import {formatReviewBrief, type Review, type Source} from '../product/agentartsReviewData';

export const sampleTitle = '电子封装导热材料替代';
export const sampleQuestion = '在现有装配压力、胶层厚度和测试温度下，候选 B 能否进入替换验证？';
export const provenance = '历史场景回放 · 公开论文与合成台架记录 · 模拟评审输出';
export const trend = {
  id: 'TIM-2026-03-24',
  name: '从材料导热率到装配工况',
  date: '2026-03-24',
  reason: '装配压力会改变传热表现。拟把界面热阻和压力一起纳入替换验证。',
  milestones: [
    {year: '2007', label: '测量材料导热率与界面热阻', href: 'https://arxiv.org/abs/0709.1849'},
    {year: '2023', label: '同时比较导热率、热阻与胶层厚度', href: 'https://doi.org/10.3390/polym15143083'},
    {year: '2026', label: '在受控压力下区分本体与界面热学参数', href: 'https://arxiv.org/abs/2603.22733v1'},
  ],
};

export const paperId = '2603.22733';
export const paperTitle = '压力依赖的导热界面测量';
export const paperSource: Source = {
  evidence_id: 'e1', paper_id: paperId, paper_version: 1, title: paperTitle + ' · Chen 等',
  pdf_page: 1, quote: 'strong pressure dependence of ITR, consistent with an interface-dominated response',
};
export const benchSource: Source = {
  evidence_id: 'e2', paper_id: 'panel-b', paper_version: 1, title: '候选 B · 台架记录（合成）',
  pdf_page: 1, quote: 'Fictional test B did not meet the thermal conductivity requirement under the reference test conditions.',
};

export const paperUrl = (version: 1 | 2) => `https://arxiv.org/pdf/${paperId}v${version}#page=1`;
export const sourceHref = (source: Source) => source.paper_id === paperId
  ? paperUrl(source.paper_version === 2 ? 2 : 1) : './sources/panel-b.pdf#page=1';

export const searchTerms = [
  {id: 'thermal', label: '装配压力与界面热阻'},
  {id: 'aging', label: '候选 B 的长期热老化结果'},
] as const;
export type SearchTerm = typeof searchTerms[number]['id'];

export const evidenceReview: Review = {
  id: 'tim-replay-v1',
  state: 'ready',
  query: searchTerms[0].label,
  project_revision: 1,
  expected_revision: 1,
  stale: false,
  execution_id: null,
  error: '',
  sources: [paperSource, benchSource],
  assessments: [
    {
      criterion_id: 'conditions', label: '装配工况可比性', status: 'supported',
      next_step: '复测时记录装配压力，并分别测量材料本体与界面。',
      findings: [{evidence_id: 'e1', stance: 'supports', reason: '该研究支持在受控压力下测界面热阻，用于设计测试，候选 B 的性能仍需单独核对。'}],
    },
    {
      criterion_id: 'thermal', label: '导热性能达标', status: 'contradicted',
      next_step: '在现有装配条件下复测候选 B，保留未达标的台架记录。',
      findings: [{evidence_id: 'e2', stance: 'contradicts', reason: '演示台架记录显示候选 B 在基准工况下未达到导热要求。'}],
    },
  ],
  bindings: {},
};

export const validation = {
  title: '候选 B 同工况导热与电绝缘复测',
  owner: '材料验证组（演示角色）',
  conditions: '固定装配压力、胶层厚度、测试温度与样品制备方式。',
  threshold: '在相同条件下，与现用料对照。导热和绝缘均满足现有项目验收要求后再复审。',
};

export const decision = '暂缓替换，安排同工况复测';
export const reviewer = '演示评审人';
export const reviewNote = '已核对测试方法与候选 B 的基准台架反证。电绝缘在完成复测前仍待验证。';
export const archiveId = 'RA-TIM-R04';
export const intakeId = 'TIM-L01';

export function archiveMarkdown(review: Review) {
  return [
    formatReviewBrief(sampleTitle, review, false, sourceHref, provenance),
    '## 归档交付记录', '',
    `- 交付档案 ${archiveId} · 项目修订 4`,
    `- 研发问题 ${sampleQuestion}`,
    `- 当前决定 ${decision}`,
    `- 评审署名 ${reviewer}`,
    `- 评审意见 ${reviewNote}`,
    `- 趋势线索 ${trend.name} · ${trend.id} · ${trend.date}`,
    `- 线索收录记录 ${intakeId} · arXiv:${paperId}v1`,
    `- 收录原因 ${trend.reason}`,
    '- 收录许可 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)',
    '- 验证状态 已安排，待录入结果',
    `- 验证事项 ${validation.title} · ${validation.owner}`,
    `- 对照工况 ${validation.conditions}`,
    `- 复审条件 ${validation.threshold}`, '',
    '历史回放获得的归档。候选试验与研发决策均为演示数据。', '',
  ].join('\n');
}
