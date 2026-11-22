"""Editable local vault with three-way synchronization and immutable source snapshots."""
import hashlib,json,os,re,threading,uuid,sqlite3
from pathlib import Path
from fastapi import APIRouter,HTTPException
from sqlalchemy import select
from .db import DATA,Session,Note,Analysis,Paper,Setting,now,serialize
router=APIRouter(prefix='/api/workspace')
lock=threading.RLock()

def digest(value):return hashlib.sha256(value.encode('utf8')).hexdigest()
def safe(value):
    name=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',value).strip(' .')[:80] or 'untitled'
    return '_'+name if name.upper().split('.')[0] in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]} else name
def root():
    path=DATA/'workspace';path.mkdir(exist_ok=True);return path
def local_path(relative):
    base=root().resolve();p=(base/relative).resolve()
    if not p.is_relative_to(base):raise HTTPException(400,'路径超出数据工作区')
    return p
def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(text,encoding='utf8');tmp.replace(path)

def sync(notes_only=False):
    with lock,Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        row=s.get(Setting,'workspace-index');index=dict(row.value if row else {})
        report={'imported':0,'exported':0,'conflicts':[],'path':str(root())}
        notes=list(s.scalars(select(Note)))
        alive={n.id for n in notes}
        for key,entry in list(index.items()):
            if key.startswith('note:') and key[5:] not in alive:
                old=local_path(entry['path'])
                if old.exists():
                    target=local_path('回收站/'+old.name);target.parent.mkdir(exist_ok=True);old.replace(target)
                del index[key]
        for n in notes:
            key='note:'+n.id;entry=index.get(key)
            was_moved=False
            # Stable suffix lets Explorer rename/move a note without creating a duplicate.
            if entry and not local_path(entry['path']).exists():
                moved=list((root()/'笔记').rglob('*--'+n.id+'.md'))
                if len(moved)==1 and moved[0].resolve().is_relative_to(root().resolve()):
                    moved_path=moved[0];new_title=moved_path.stem.rsplit('--',1)[0]
                    new_series=moved_path.parent.relative_to(root()/'笔记').as_posix()
                    from .note_folders import FolderInput
                    new_series=FolderInput(path='随手记' if new_series=='.' else new_series).path
                    if n.revision!=entry['revision']:
                        report['conflicts'].append({'resource':key,'reason':'外部移动与应用修改发生冲突，请先合并'});continue
                    n.title=new_title[:160] or n.title;n.series=new_series
                    entry={**entry,'path':moved_path.relative_to(root()).as_posix()}
                    was_moved=True
            relative='笔记/'+('/'.join(safe(x) for x in n.series.split('/')))+'/'+safe(n.title)+'--'+n.id+'.md'
            target=local_path(relative);old=local_path(entry['path']) if entry else target
            base=entry.get('hash') if entry else None
            disk=old.read_text('utf8') if old.exists() else None
            dbhash=digest(n.content)
            if entry and disk is not None and digest(disk)!=base:
                if n.revision!=entry['revision'] and disk!=n.content:
                    report['conflicts'].append({'resource':key,'path':str(old),'reason':'文件与应用均有修改；两份内容均已保留'});continue
                if len(disk)>200000:
                    report['conflicts'].append({'resource':key,'reason':'文件超过 200000 字符'});continue
                if disk!=n.content:
                    n.content=disk;n.revision+=1;n.updated=now();dbhash=digest(disk);report['imported']+=1
            if disk!=n.content or old!=target or not target.exists():
                write(target,n.content);report['exported']+=1
                if old!=target and old.exists():old.unlink()
            if was_moved:n.revision+=1;n.updated=now();report['imported']+=1
            index[key]={'path':relative,'hash':dbhash,'revision':n.revision}
        # Unmanaged Markdown files become new notes. Never interpret a missing file as deletion.
        tracked={e['path'] for k,e in index.items() if k.startswith('note:')}
        notes_dir=root()/'笔记'
        if notes_dir.exists():
            for p in notes_dir.rglob('*.md'):
                rel=p.relative_to(root()).as_posix()
                if rel in tracked or p.is_symlink() or not p.resolve().is_relative_to(root().resolve()) or p.stat().st_size>800000:continue
                suffix=re.search(r'--([a-f0-9]{32})$',p.stem)
                if suffix and suffix.group(1) in alive:continue
                text=p.read_text('utf8')
                if len(text)>200000:continue
                title=re.sub(r'--[a-f0-9]{32}$','',p.stem)[:160] or '未命名笔记'
                folder=p.parent.relative_to(notes_dir).as_posix()
                from .note_folders import FolderInput
                folder=FolderInput(path='随手记' if folder=='.' else folder).path
                n=Note(id=uuid.uuid4().hex,title=title,series=folder,content=text);s.add(n);s.flush()
                index['note:'+n.id]={'path':rel,'hash':digest(text),'revision':n.revision};report['imported']+=1
        if not notes_only:
            latest={}
            for a in s.scalars(select(Analysis).order_by(Analysis.created.desc())):latest.setdefault(a.paper_id,a)
            for pid,a in latest.items():
                cache=DATA/'documents'/f'{a.content_hash}.json'
                if not cache.exists():continue
                # Work on a copy: evidence already published keeps its original content_hash.
                paper=s.get(Paper,pid)
                key='source:'+pid;entry=index.get(key);relative=entry['path'] if entry else '解析文本/'+safe(paper.title)+'--'+digest(pid)[:16]+'.json';target=local_path(relative)
                if entry and target.exists():
                    text=target.read_text('utf8')
                    if digest(text)!=entry['hash']:
                        if entry['analysis_id']!=a.id:
                            report['conflicts'].append({'resource':key,'reason':'分析版本已变化，解析文本草稿保留，需对照合并'});continue
                        try:
                            pages=json.loads(text)
                            if not isinstance(pages,list) or not pages or len(pages)>2000:raise ValueError('应为带 page/text 的非空数组')
                            nums=[]
                            for p in pages:
                                if type(p.get('page')) is not int or p['page']<1 or not isinstance(p.get('text'),str):raise ValueError('每页需要 page 正整数与 text 字符串')
                                nums.append(p['page'])
                            if len(set(nums))!=len(nums):raise ValueError('页码不能重复')
                            if len(text)>10000000:raise ValueError('文本过大')
                            revised=digest(text);write(DATA/'documents'/f'{revised}.json',text)
                            paper=s.get(Paper,pid);pdf=DATA/'documents'/f'{digest(pid)}v{paper.version}.pdf'
                            original=hashlib.sha256(pdf.read_bytes()).hexdigest()
                            previous=s.get(Setting,'source-edit:'+original)
                            predecessor=previous.value.get('digest') if previous else a.content_hash
                            redirect='source-redirect:'+predecessor
                            if predecessor!=revised and not s.get(Setting,redirect):
                                s.add(Setting(key=redirect,value={'digest':revised,'paper_id':pid,'paper_version':paper.version,'original':original,'updated':now()}))
                            s.merge(Setting(key='source-edit:'+original,value={'digest':revised,'paper_id':pid,'paper_version':paper.version,'previous':predecessor,'updated':now()}))
                            index[key]={**entry,'hash':revised};report['imported']+=1
                        except (ValueError,KeyError,AttributeError,OSError) as exc:report['conflicts'].append({'resource':key,'reason':str(exc)[:250]})
                        continue
                if not entry or entry['analysis_id']!=a.id or not target.exists():
                    text=cache.read_text('utf8');write(target,text)
                    index[key]={'path':relative,'hash':digest(text),'analysis_id':a.id,'paper_id':pid,'title':paper.title};report['exported']+=1
        s.merge(Setting(key='workspace-index',value=index));s.merge(Setting(key='workspace-status',value={**report,'updated':now()}))
        write(root()/'资源索引.json',json.dumps(index,ensure_ascii=False,indent=2))
        return report

@router.post('/sync')
def synchronize():return sync()
@router.get('')
def status():
    with Session() as s:
        row=s.get(Setting,'workspace-status');return {**(row.value if row else {'conflicts':[]}), 'path':str(DATA),'editable_path':str(root())}
@router.post('/open')
def open_folder():
    if os.name=='nt':os.startfile(str(DATA))
    return {'path':str(DATA),'editable_path':str(root()),'imported':0,'exported':0,'conflicts':[]}

@router.post('/snapshot')
def export_snapshot():
    """Export all tables from a coherent SQLite backup; no decrypted credentials."""
    from .db import Base
    folder=DATA/'exports'/('snapshot-'+now().replace(':','').replace('+','-')+'-'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    db=folder/'atlas.db'
    with sqlite3.connect(DATA/'atlas.db') as source,sqlite3.connect(db) as target:source.backup(target)
    def redact(value):
        if isinstance(value,dict):return {k:('[已隐藏]' if k.lower() in {'api_key','lease_token','authorization','password','token'} else redact(v)) for k,v in value.items()}
        if isinstance(value,list):return [redact(v) for v in value]
        return value
    tables=[]
    with sqlite3.connect(db) as snapshot:
        snapshot.row_factory=sqlite3.Row
        for table in Base.metadata.sorted_tables:
            json_columns={c.name for c in table.columns if c.type.__class__.__name__=='JSON'}
            rows=[]
            for row in snapshot.execute('SELECT * FROM "'+table.name+'"'):
                item=dict(row)
                for k in json_columns:
                    if isinstance(item.get(k),str):item[k]=json.loads(item[k])
                rows.append(redact(item))
            write(folder/(table.name+'.json'),json.dumps(rows,ensure_ascii=False,indent=2))
            tables.append({'table':table.name,'rows':len(rows),'columns':[c.name for c in table.columns]})
    manifest={'created':now(),'tables':tables,'database':str(db),'raw_data':str(DATA),'editable_workspace':str(root()),'notes':'数据库与 JSON 为一致性快照；原 PDF、上传、缓存、日志仍在原始数据目录。JSON 隐藏令牌字段；不解密密钥。修改请使用支持版本校验的工作区或 API。'}
    write(folder/'index.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return {'path':str(folder),'tables':len(tables),'rows':sum(t['rows'] for t in tables)}
