import {useMemo} from 'react';
import {useAppearance} from '../ui/Appearance';
import CoverageDial from '../ui/industrial/CoverageDial';
import type {ProjectDetail} from './projectApi';
import ProjectEvidenceComparison from './ProjectEvidenceComparison';

type Props={
 data:ProjectDetail;
 disabled:boolean;
 onBind:(id:string)=>void;
 onEvidence:(id:string)=>void;
 onValidation:()=>void;
};

export default function ProjectCoverage({data,disabled,onBind,onEvidence,onValidation}:Props){
 const {appearance}=useAppearance();
 const rows=useMemo(()=>data.project.criteria.map(criterion=>{
  const evidence=data.evidence.filter(item=>item.criterion_id===criterion.id);
  const valid=evidence.filter(item=>item.health.eligible&&item.stance!=='uncertain');
  const supports=valid.filter(item=>item.stance==='supports');
  const opposes=valid.filter(item=>item.stance==='contradicts');
  const pending=evidence.filter(item=>!item.health.eligible||item.stance==='uncertain');
  const tasks=(data.validations||[]).filter(item=>item.criterion_id===criterion.id);
  const done=tasks.filter(item=>item.status==='completed');
  return {criterion,evidence,supports,opposes,pending,tasks,done};
 }),[data.project.criteria,data.evidence,data.validations]);

 return <section className="project-coverage" aria-label="评价标准证据覆盖">
  <h3>按标准核对覆盖</h3>
  <p>只有来源健康且立场明确的绑定计入有效正反证。待核、不适用或来源变化单列。验证是内部记录，不替代论文证据。</p>
  {rows.length?<>
   {appearance.edition==='industrial'&&<CoverageDial rows={rows}/>}
   <p className="project-coverage-scroll-hint">左右滑动查看反证、待核与处理操作 →</p>
   <div className="project-coverage-scroll" tabIndex={0} aria-label="标准证据覆盖表，可左右滚动">
    <table>
     <thead><tr><th>评价标准</th><th>有效支持</th><th>有效反证</th><th>无效 / 待核</th><th>内部验证</th><th>处理</th></tr></thead>
     <tbody>{rows.map(({criterion,evidence,supports,opposes,pending,tasks,done})=><tr key={criterion.id} data-criterion-id={criterion.id} tabIndex={-1}>
      <th scope="row">{criterion.label}</th><td>{supports.length}</td><td>{opposes.length}</td><td>{pending.length}</td>
      <td>{tasks.length?`${done.length}/${tasks.length} 已记录结果`:'未安排'}
       {done.some(item=>item.outcome==='contradicts')&&<small>含内部反例</small>}
       {done.some(item=>item.outcome==='inconclusive')&&<small>含不确定结果</small>}
      </td>
      <td><div className="project-coverage-actions">
       <button className="text-button" disabled={disabled} onClick={()=>onBind(criterion.id)}>补充此标准证据</button>
       {evidence.length>0&&<button className="text-button" onClick={()=>onEvidence((pending[0]||evidence[0]).id)}>定位{pending.length?'待核':'已有'}证据</button>}
       {tasks.length>0&&<button className="text-button" onClick={onValidation}>查看验证</button>}
      </div></td>
     </tr>)}</tbody>
    </table>
   </div>
   <ProjectEvidenceComparison criteria={data.project.criteria} evidence={data.evidence} onEvidence={onEvidence}/>
  </>:<p className="projects-inline-empty">先在决策简报定义评价标准，再组织证据。</p>}
 </section>;
}
