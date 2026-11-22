/* The task domains are locations, never a computed completion score. */
export type ProjectStage='decision'|'evidence'|'validation'|'review';
export const projectChapters:[ProjectStage,string,string][]=[['decision','01','定义决策'],['evidence','02','核对证据'],['validation','03','验证记录'],['review','04','评审归档']];
