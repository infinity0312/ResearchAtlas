import re
from fastapi import APIRouter,Query
from pydantic import BaseModel,Field
from sqlalchemy import select
from .db import Session,Setting,Analysis,Paper,Domain,Membership
router=APIRouter(prefix='/api')
# Ordered, bounded families. A metric or implementation detail is not a method family.
EXCLUDED='实验指标 / 工具（不计入家族）'
RULES=[
 ('自监督 / 对比学习',r'掩码自编码|masked.autoencod|\bMoCo\b|SimCLR|NT-Xent|CLIP|对比学习|自监督|masked.patch|掩码语言|下一句预测|\bMLM\b|Skip.gram|CBOW'),
 (EXCLUDED,r'评测|评估|benchmark|Bench\b|\bMAE\b|\bDIQR\b|Focal Loss|负对照|交叉验证|对照控制|标签置换|工具集|学习契约|EIS|SEM-EDS|ABAQUS|证据分类|证据四分类|基准|数据集|pretraining corpus|过滤|数据污染|去重|准确率|置信度头|置信度预测头|分数$|距离度量|相似度度量|复杂度度量|膜分量|模分量|测试$|SAD|BayesElo|MoleculeNet'),
 ('量化 / 低精度计算',r'量化|Quant|GPTQ|\bOBQ\b|\bOBC\b|\bLDLQ\b|BlockLDLQ|BRECQ|NF4|FP8|8位浮点|INT[48]|E8P|BitNet|BitLinear|BinaryConnect|Binary.Weight|XNOR|低精度|低比特|直通估计|straight.through|随机二值化|符号.*二值化|确定性.*二值化|Hadamard|非相干|Incoherence|\bLWC\b|\bLET\b|4-bit|8 位定点'),
 ('模型压缩 / 蒸馏',r'剪枝|稀疏化|知识蒸馏|自蒸馏|跨蒸馏|cross.distill|Optimal Brain Damage|deep compression|权重共享|Huffman 编码|渐进式有损压缩'),
 ('强化学习 / 决策搜索',r'强化|\bRLHF\b|\bPPO\b|\bDQN\b|\bDDPG\b|Actor.Critic|actor.critic|Q.learning|Q.functions|Q 函数|Q 学习|Soft Policy|策略迭代|策略优化|策略熵|策略熵|优势函数|优势估计|GAE|Sarsa|时序差分|时间差分|TD\(|TD Learning|经验回放|动作重放|目标网络|Target Value|奖励|MCTS|蒙特卡洛树|PUCT|AlphaGo|AlphaZero|epsilon.greedy|对弈|潜在世界模型|Dreamer|Adaptive Heuristic Critic|二价强化|LCLIP|探索噪声|极小极大搜索'),
 ('等变神经网络',r'equivari|equiformer|e3nn|等变|SO\(3\)|NequIP|Tensor Field Networks|张量场网络'),
 ('图神经网络',r'GNN|GCNN|GATv2|\bGCN\b|CHGNet|GemNet|SchNet|DimeNet|GraphSAGE|PhysNet|ProteinMPNN|MPNN|DTNN|GINE|图神经|图卷积|图编码器|图消息|消息传递|message passing|message function|neural graph|graph neural|graph convolution|邻居采样|邻居向量|邻域均值|均值聚合|set2set|边更新|多体.*消息'),
 ('扩散与流模型',r'diffusion|flow matching|扩散|流匹配|\bEDM\b|噪声调度|去噪分数|score.matching|SDE|归一化流|normalizing flow|planar flow|radial flow|重加权变分下界|噪声退火|Lsimple|ε预测'),
 ('Transformer / 注意力',r'transformer|attention|attentive|BERT|ELECTRA|Electra|XLNet|\bT5\b|Performer|注意力|Evoformer|Enformer|pairformer|Q-Former'),
 ('卷积 / 循环神经网络',r'卷积|ConvNet|\bCNN\b|\bRNN\b|LSTM|GRU|GoogLeNet|Inception|ResNet|U-Net|Basset|DeepBind|VGG|RNNsearch|HyenaDNA|门控循环|恒定误差回传'),
 ('概率模型 / 变分推断',r'变分|Variational|AEVB|\bVAE\b|scVI|scvi.tools|ADVI|重参数化技巧|Reparameterization|隐马尔可夫|\bHMM\b|\bEM\b|Baum.Welch|Viterbi|最大后验|Dirichlet 先验|\bMAP\b|概率|似然|零膨胀|ZINB|Bayesian(?! optim)|贝叶斯推断|贝叶斯学习|蒙特卡洛随机|Metropolis|期望步|最大化步'),
 ('对抗 / 能量生成模型',r'\b(?:GAN|DCGAN|WGAN|MolGAN)\b|生成对抗|对抗式|玻尔兹曼|\bDBN\b'),
 ('迁移与残差学习',r'delta learning|Δ.learning|迁移|残差学习|LoRA|适配器|微调|fine.tun|fine-tun|域适应|线性探测'),
 ('主动学习 / 贝叶斯优化',r'active learning|bayesian optim|主动学习|贝叶斯优化|高斯过程隐空间优化'),
 ('语言模型与智能体',r'language model|\bLLM\b|agent|智能体|语言模型|大模型|蛋白质语言|RNA语言|ESM|条件语言|上下文学习|指令|工具调用|RAG|检索增强|提示模板|Chinchilla'),
 ('联邦 / 隐私学习',r'联邦|FedAvg|差分隐私|DP-SGD'),
 ('持续 / 元学习',r'元学习|MAML|弹性权重|EWC|持续学习'),
 ('因果 / 可解释学习',r'因果|SHAP|Shapley|归因|Integrated Gradients'),
 ('数值优化 / 组合优化',r'CP-SAT|BFGS|Adam|AdaMax|Adagrad|SGD|RMSProp|LARS|优化|贪心|整数规划|约束求解|组合优化|多目标|coordinate descent|梯度下降|随机逼近|学习率|矩估计|OPDiv|模拟退火|动态调整|软松弛|乘性权重'),
 ('统计学习 / 核与树模型',r'回归|支持向量|软间隔|Ridge|kNN|k-NN|最近邻|TabPFN|随机森林|Forest-R|bagging|集成|ensembl|AdaBoost|\bID3\b|信息增益|增益比|核方法|高斯过程|高斯近似势|Gaussian Approximation|sGDML|k近邻|高斯核|核岭|投票'),
 ('学习理论 / 信息论',r'Kolmogorov|复杂度|互信息|充分统计|统计量|信息瓶颈|VC 维|风险界|损失界|定理|证明|泛化|缩放定律|Scaling Law|Blahut|通用分布|通用半测度|通用预测|最优知情|AI µ|AI ξ|Λρ|智能序|Hedge|相对熵|统计可分|隐式与显式描述|典型性|有限样本'),
 ('科学计算 / 机理模型',r'DFPT|DFTB|DFT-D3|xTB|\bODE\b|LSODA|平衡点|稳态|代谢模型|Rietveld|分子动力学|Langevin|库仑|静电|波函数|PauliNet|FermiNet|哈密顿|力场|神经网络势|DeePMD|DeepPot|\bANI\b|NeuroChem|Neural Electronic|晶体结构|PhiGen|phasing|Superflip|再生数|ART|疗效|本征模态|简正模式|Gō模型|Go模型|高斯网络模型|拓扑基珠子|正则模态|自由能|热与|半巨正则|R0|LSODA|分子.*能量|手性势|扭转角势|外部势|总能量'),
 ('科学表征 / 不变量',r'\bACE\b|Clebsch.Gordan|invariant|不变量|GTO|晶格|图表示|NBO|SOAP|Smooth Overlap|Parrinello|对称函数|球谐|贝塞尔|Bessel|傅里叶|Fourier|径向基|勒让德|TensorProduct|原子环境|原子邻域|独热编码|AEV|RBF|Steinhardt|角.*级数|晶体图|原子响应场'),
 ('降维 / 聚类',r't-SNE|\bSNE\b|Stochastic Neighbor|UMAP|聚类|CPDiv|PROCSE|邻域图|最近邻搜索|谱初始化|力导向|早期夸张'),
 ('不确定性 / 统计检验',r'不确定|Fisher|敏感性|辨识|identifi|校准|假设检验|卡方|置信|轮廓似然'),
 ('训练 / 推理系统',r'GPU|CUDA|CPU|GEMM|SIMD|SWAR|CUTLASS|内核|分布式|并行|DistBelief|allreduce|rabit|Paged Optimizers|存储|KV cache|缓存|整数推理|权重合并部署|位卷积核|权重打包'),
 ('实验自动化',r'自主实验|合成策略|A-Lab|执行器|工作流|VirtualCellPack|虚拟实验|执行环境|证据感知'),
 ('深度网络 / 表示学习',r'\bMLP\b|AugNet|TripletsNet|深度网络|Deep Learning|深度神经|神经网络|感知机|多模态|表示|表征|嵌入|残差|池化|骨干|编码器|编码.*解码|预训练|pre.train|单元块|隐藏状态|patch embedding|胶囊|routing|动态路由|投影头|maxout|ReLU|SubLN|门控|潜在空间|GEPC|GEP|MADRIGAL'),
 ('推断 / 生成策略',r'重采样|无分类器|CFG|稀疏去噪|测试时|beam search|束搜索|top-k|采样器|搜索解码|rollout|重打分|排序策略|预测-校正'),
]
# Low-level terms stay searchable in the paper, but do not inflate the family axis.
RULES.append((EXCLUDED,r'损失|正则|dropout|归一化|Normalization|\bBN\b|反向传播|前向传播|自动微分|Autograd|链式法则|裁剪|初始化|训练流程|数据增强|数据类型|线性变换|缩放|编码$|编码策略|位置编码|one.hot|均值|平均|权重衰减|辅助分类|训练目标|联合训练|端到端训练|从零训练|mini.batch|小批量|长度均衡|计算预算|有效调度|累积梯度|token|噪声训练|数据.*清洗|过滤|输入门|输出门|softmax|softplus|sigmoid|非线性层|消融|采样$|corpus|数据集|指标|对照|度量|统计量归一化'))


# Reviewed aliases from the library: keep implementation terms out of the family axis.
# These exact matches avoid interpreting arbitrary future acronyms out of context.
REVIEWED_GROUPS={
 '量化 / 低精度计算': 'SpQR|adaptive rounding with linear feedback|可学习旋转矩阵 R1, R2|块级重建（block reconstruction）|基于 Cholesky 的数值稳定重表述|基于激活幅度的搜索空间 s=sX^α 与网格搜索|基于遗传算法与查找表的混合精度搜索|定点整数点积|实值权重累积更新|对角 Hessian 近似|损失感知的旋转优化|惰性批量列更新（B=128）|旋转矩阵合并吸收进权重|离群值分离|稀疏感知算法|逐层重建|自适应舍入（AdaRound）与可学习激活步长|混合精度训练|混合精度分解（mixed-precision decomposition）|Dense-and-Sparse 分解|Kronecker product random orthogonal matrices|二阶误差补偿|二阶误差/块对角 Hessian 近似分析',
 '模型压缩 / 蒸馏': '二阶导数显著性',
 '科学计算 / 机理模型': 'AIDEN|TECE|AIRSS 随机结构搜索|DREAM|Rosetta Vscore2_smooth范德华项|Rosetta-RelaxBB构象能量分析|pyRosetta 全原子建模|三体相互作用|均方位移与理论B因子计算|基于天然态拓扑的精确可解模型|对称寡聚体设计|对称感知部分取代（SAPS）|强度泛函 Δ 最小化|氧化态平衡松弛约束|温度依赖的自洽有效相互作用|五房室宿主内HIV动力学ODE模型|原子能量分解|成对能量分解',
 '科学表征 / 不变量': 'alignment-based features (PSSM, HHblits)|MACCS 键子结构修改|局部参考坐标系|密度技巧|低秩张量交互|循环张量收缩算法|属性几何图与参数化马蹄形曲梁扩展|局部二值模式|可微蛋白质几何模型 x = G(φ,ψ)',
 '强化学习 / 决策搜索': 'AWESOME|Maximum Entropy Reinforcement Learning Objective|expectimax 递归信用最大化|保守Q学习（CQL）|局面记忆|退回预计算均衡策略|评价函数学习|Reward Modeling (RM)',
 '图神经网络': 'Edge inference module φ_inf|virtual edges|两层GCN模型|受生物形态发生启发的图生成框架（跨层与层内生长）|带树消息增强的子图组装与化学兼容性打分|树解码器与图解码器两阶段生成|逐层传播规则|图增强扰动预测（GEARS）|master node|树分解算法（提取简单环与边作为簇并构造簇图的最大生成树）',
 '统计学习 / 核与树模型': 'ASSISTANT 子集准则|未知属性值比例分配|近似分割点查找框架|加权分位数草图|对称核|梯度域机器学习',
 '降维 / 聚类': 'FinReal/FinSing 伴随函子对|最小生成树传递闭包|模糊集交叉熵代价函数|随机游走扩展',
 '学习理论 / 信息论': 'Mp* 算法|一般更新函数 U_β|函数最小化 FM µ/ξ 模型|有向三角不等式|条件风险分解',
 '数值优化 / 组合优化': 'CASS聚合代价函数框架|Widrow-Hoff 规则|交叉熵方法求解 QUBO|切比雪夫多项式近似|指定变形形状的拓扑—几何逆向设计|确定性退火|神经引导逆合成搜索（Retro*）|稀疏线性求解|多轮反馈引导自适应搜索',
 '深度网络 / 表示学习': 'Latent Dynamics Model (LDM)|BIT|α/β/γ价值动态系统|共享基因载荷的因子化基因程序解码|医学通用分割（MedSAM）|多任务学习（结构相似性 + 残基接触预测）|对齐模型（前馈网络）|折叠头（folding head）|混合专家|瓶颈结构|端到端蛋白质复合物建模|级联网络|结构模块（残基气体/全局刚体框架）|缺失模态学习|自相互作用层|求和判别系统（S-system）|长程调控建模|高效双线性层|恒等捷径连接|投影捷径|滑动窗口MSA拼接distogram|软对称对齐 (SSA)',
 '卷积 / 循环神经网络': 'Faster R-CNN目标检测',
 '概率模型 / 变分推断': 'Student-t 分布|权重矩阵（WM）建模与超单纯形积分|批次效应建模|簇WM重建与上游序列扫描|识别模型（recognition model）|神经比例风险模型（DeepSurv）',
 '推断 / 生成策略': '电子路径生成（ELECTRO）|recycling 迭代精修|自条件化',
 '训练 / 推理系统': '均衡混合稀疏核|外存块压缩与分片|稀疏-稠密矩阵乘法|非线性与取整融合',
 '实验自动化': 'BaseCamp|人在回路',
 '不确定性 / 统计检验': '贝叶斯因子差异表达检验|Decoder sensitivity diagnostic (Hutchinson-style estimator)',
 '迁移与残差学习': r'低秩分解矩阵 \(\Delta W=BA\)',
 '因果 / 可解释学习': 'in silico饱和突变|袋外变量置换重要性',
 '对抗 / 能量生成模型': '快速对抗扰动（FGSM）',
 EXCLUDED: 'Hamming noise injection in latent space|13残基滑动窗口输入|AMix-2.1|BN网络训练推断算法|BSR退化管道（LDM-BSR）|Grassmann 距离子空间相似度|HIV-1蛋白酶关键位点识别|KL 惩罚|Koopman-inspired latent dynamics constraint|LORO|Momentum / velocity-type input variant|PICS|RampUp 引导调度|multiple towers|squash 非线性|tabula rasa 学习|偏差校正|内部协变量偏移建模|分布偏移（留出切片/队列/器官）|分数-多样性曲线|列块结构|加权线性组合相似度模型|医学基础模型综述|参考分布校正|基线层级 BoB/PRE/PRE+A/BoE|多尺度训练与尺度抖动|对称/重复/多态位置绑定|局部连通性约束|帧跳跃|平滑截断权重函数|指数近期加权|描述符重建实验|放大因子分析|无监督接触图线性投影|标签平滑|梯度范数硬约束|模型手术启发式|深度异常检测综述|源句词序反转|特征基方法（拼接顶部若干层）|球形插值（slerp）|线性时间雅可比行列式计算|编码特征矩阵|自适应 KL 惩罚|色编码接触图分析|袋外（OOB）估计|词向量代数运算（类比推理）|轮廓敏感投影区域|重参数化约束|零样本适应度选择|零重心子空间KL散度计算|Dynamics model input noise injection|SSGSEA 通路活性目标构建|切片身份捷径线性探针|自适应蛋白口袋扰动'
}
# Source-reviewed macro samples use the same vocabulary as the local library.
for label,terms in {
 '图神经网络':'几何深度学习',
 '量子计算':'量子机器学习',
 '模型压缩 / 蒸馏':'模型压缩',
 '对抗 / 能量生成模型':'能量模型|神经活动解码',
 '科学计算 / 机理模型':'神经随机微分方程|随机神经动力学',
 '深度网络 / 表示学习':'多实例学习|噪声鲁棒分类|空间蛋白组基础模型',
 '因果 / 可解释学习':'可解释统计建模',
 '统计学习 / 核与树模型':'哈希检索与树模型',
 '降维 / 聚类':'流形学习',
 EXCLUDED:'机制推断综述',
}.items():
    REVIEWED_GROUPS[label]='|'.join(filter(None,[REVIEWED_GROUPS.get(label,''),terms]))
ALIASES={term:label for label,terms in REVIEWED_GROUPS.items() for term in terms.split('|')}

def family(name,overrides):
    if name in overrides:return overrides[name]
    if name in {label for label,_ in RULES} or name in REVIEWED_GROUPS or name==EXCLUDED:return name
    if name in ALIASES:return ALIASES[name]
    for label,pattern in RULES:
        if re.search(pattern,name,re.I):return label
    return '待归类'
class Mapping(BaseModel):
    method:str=Field(min_length=1,max_length=200)
    family:str=Field(min_length=1,max_length=80)
@router.put('/method-families')
def set_mapping(data:Mapping):
    with Session.begin() as s:
        row=s.get(Setting,'method_families');value=dict(row.value) if row else {}
        value[data.method]=data.family.strip() or '待归类'
        if row:row.value=value
        else:s.add(Setting(key='method_families',value=value))
    return {'ok':True}
@router.get('/method-matrix')
def matrix(domain_id:str|None=None,domain_ids:list[str]=Query(default=[],max_length=100),days:int=Query(30,ge=0,le=365)):
    from .app import paper_query
    with Session() as s:
        row=s.get(Setting,'method_families');overrides=row.value if row else {}
        scope=domain_ids or ([domain_id] if domain_id else [])
        base_query=paper_query(days=days)
        if scope:base_query=base_query.where(Paper.id.in_(select(Membership.paper_id).where(Membership.domain_id.in_(scope))))
        base=base_query.subquery()
        q=select(Analysis,Paper.title,Domain.topics).join(base,(base.c.id==Analysis.paper_id)&(base.c.version==Analysis.version)).join(Paper,Paper.id==Analysis.paper_id).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc())
        if scope:q=q.where(Analysis.domain_id.in_(scope))
        seen=set();papers={};methods={}
        for a,title,allowed_topics in s.execute(q):
            if (a.paper_id,a.domain_id) in seen:continue
            seen.add((a.paper_id,a.domain_id))
            p=papers.setdefault(a.paper_id,{'id':a.paper_id,'title':title,'topics':set(),'methods':set(),'families':set()})
            p['topics'].update([t for t in a.result.get('topics',[]) if t in allowed_topics] or ['分类未匹配' if a.result.get('topics') else '分析未提取分类'])
            if not a.result.get('methods'):
                p['methods'].add('尚未提取核心方法');p['families'].add('尚未提取核心方法')
            for m in a.result.get('methods',[]):
                f=family(m,overrides);methods[m]=f;p['methods'].add(m)
                if f not in (EXCLUDED,'待归类'):p['families'].add(f)
        for p in papers.values():
            if not p['families']:
                unresolved=any(methods.get(m)=='待归类' for m in p['methods'])
                p['families'].add('待归类' if unresolved else '综述 / 评测 / 数据资源')
        return {'unmapped_terms':sum(f=='待归类' for f in methods.values()),'papers_without_family':sum(p['families']=={'待归类'} for p in papers.values()),'papers':[{**p,'topics':sorted(p['topics']),'methods':sorted(p['methods']),'families':sorted(p['families'])} for p in papers.values()], 'mapping':[{'method':m,'family':f,'manual':m in overrides} for m,f in sorted(methods.items(),key=lambda item:(item[1]!='待归类',item[0]))],'families':list(dict.fromkeys([r[0] for r in RULES]+list(REVIEWED_GROUPS)+list(overrides.values())+['待归类']))}
