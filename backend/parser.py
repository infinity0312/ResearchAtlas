"""Runs in a subprocess so malformed / slow PDFs cannot block API or worker forever."""
import json, sys
from pathlib import Path
from pypdf import PdfReader

def parse(path):
    reader=PdfReader(path)
    if reader.is_encrypted: raise ValueError('暂不支持加密 PDF')
    if len(reader.pages)>150: raise ValueError('超过 150 页，请分卷导入；未执行截断分析')
    sections=[]
    for i,page in enumerate(reader.pages):
        stream=page.get_contents()
        if stream and len(stream.get_data())>12*1024*1024: raise ValueError('页面过大，需使用专用解析服务')
        # Broken PDF CMaps can expose lone UTF-16 surrogates. Keep the page and
        # explicitly mark those undecodable glyphs instead of crashing JSON IO.
        text=(page.extract_text() or '').encode('utf-16-le','surrogatepass').decode('utf-16-le','replace')
        sections.append({'page':i+1,'text':text})
    if sum(len(p['text']) for p in sections)<400: raise ValueError('无法提取足够文本，可能是扫描件；需要 OCR 解析器')
    return sections

if __name__=='__main__':
    try:
        result=parse(sys.argv[1])
        target=Path(sys.argv[2]);temporary=target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        temporary.replace(target)
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)
