import './graph-view-heading.css';
const views = {
 network:{title:'沿引用追溯来源',description:'选择一篇论文，分别查看它引用了谁、谁引用了它，以及关系的原文出处。'},
 similarity:{title:'查找分类相近的论文',description:'从论文索引选一篇，再检视邻近论文的共享标签和差异。'},
 timeline:{title:'按时间浏览一个研究时期',description:'按年份定位论文并核对日期口径。'},
};

export default function GraphViewHeading({mode='network'}:{mode?:keyof typeof views}){
 const view=views[mode];
 return <header className="graph-view-heading"><h3>{view.title}</h3><p>{view.description}</p></header>;
}
