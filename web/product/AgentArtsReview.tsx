import {useRef, useState, type FormEvent} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {api} from '../api';
import AgentArtsResults from './AgentArtsResults';
import type {Review} from './agentartsReviewData';
import type {Project} from './projectApi';
import './agentarts-review.css';

type Status = {enabled: boolean; configured: boolean; review: Review | null};

export default function AgentArtsReview({project, disabled}: {project: Project; disabled: boolean}) {
  const client = useQueryClient();
  const path = '/projects/' + encodeURIComponent(project.id) + '/agentarts';
  const key = ['agentarts-review', project.id];
  const status = useQuery({
    queryKey: key,
    queryFn: ({signal}) => api<Status>(path, {signal}),
    refetchInterval: query => query.state.data?.review?.state === 'running' ? 2500 : false,
  });
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState<'review' | 'adopt' | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const inFlight = useRef(false);
  const result = status.data?.review;
  const queryInput = query ?? result?.query ?? '';
  const reviewing = active === 'review' || result?.state === 'running';
  const working = Boolean(active || reviewing);
  const unavailable = disabled || working || Boolean(status.error);
  const stale = !!result && (result.stale || result.expected_revision !== project.revision);

  async function run(endpoint: string, body: object, action: 'review' | 'adopt') {
    if (inFlight.current || unavailable) return;
    inFlight.current = true;
    setActive(action);
    setError('');
    setMessage('');
    try {
      const review = await api<Review>(endpoint, {method: 'POST', body: JSON.stringify(body)});
      await client.cancelQueries({queryKey: key});
      client.setQueryData<Status>(key, old => old ? {...old, review} : old);
      if (action === 'adopt') {
        await Promise.all([
          client.invalidateQueries({queryKey: ['project', project.id]}),
          client.invalidateQueries({queryKey: ['projects']}),
          client.invalidateQueries({queryKey: ['project-impacts']}),
        ]);
        setMessage('证据已写入项目。');
      } else if (review.state === 'ready') {
        setMessage('评审草稿已生成，可逐项核对来源。');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '评审请求未完成');
      await client.invalidateQueries({queryKey: key});
    } finally {
      setActive(null);
      inFlight.current = false;
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = queryInput.trim();
    if (value && status.data?.configured) void run(path, {revision: project.revision, query: value}, 'review');
  }

  if (!status.data?.enabled && !status.error) return null;
  return <section className="agentarts-review" aria-label="AgentArts 证据评审" aria-busy={working}>
    <header>
      <div className="eyebrow">AGENTARTS / EVIDENCE REVIEW</div>
      <h3>发起证据评审</h3>
      <p>将项目评价标准与获准的文献片段送入工作流，生成供人工核对的草稿。</p>
    </header>
    {status.error && <div className="notice error agentarts-result-heading">
      <p role="alert">暂时无法读取评审状态。{result && '当前显示上次读取的草稿。'}</p>
      <button type="button" className="button small" disabled={status.isFetching}
        onClick={() => void status.refetch()}>重新连接</button>
    </div>}
    {status.data?.enabled && <form className="agentarts-review-form" onSubmit={submit}>
      <label>检索关键词
        <input type="search" required maxLength={160} placeholder="例如：thermal conductivity" value={queryInput}
          onChange={event => setQuery(event.target.value)}/>
      </label>
      <button className="button primary" disabled={unavailable || !queryInput.trim() || !status.data.configured}>
        {reviewing ? '正在评审…' : result?.state === 'failed' ? '重新运行评审' : '运行 AgentArts 评审'}
      </button>
    </form>}
    {status.data?.enabled && !status.data.configured &&
      <p role="status">工作流尚未接通。已生成的草稿仍可核对与导出。</p>}
    {reviewing && <p role="status">正在等待工作流返回。离开页面后，可回到此处查看评审状态。</p>}
    {message && <p role="status">{message}</p>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {result?.state === 'failed' && <p className="notice error" role="alert">{result.error}</p>}
    {result?.state === 'no_evidence' &&
      <p className="notice" role="status">获准语料中未找到可核对的匹配片段，本次检查在本机结束。</p>}
    {result && <AgentArtsResults title={project.title} review={result} stale={stale} busy={unavailable}
      onAdopt={(criterion, evidence) => void run(path + '/' + result.id + '/bind', {
        revision: project.revision, criterion_id: criterion, evidence_id: evidence,
      }, 'adopt')}/>}
  </section>;
}
