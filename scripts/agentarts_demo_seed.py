"""Create an isolated fictional materials review for AgentArts development."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, DecodedStreamObject, NameObject


EXAMPLES = [
    ('local-agentarts-a', 'Demonstration panel A thermal conductivity',
     'Fictional test A measured thermal conductivity at the same sample thickness and reference temperature.'),
    ('local-agentarts-b', 'Demonstration panel B thermal conductivity',
     'Fictional test B did not meet the thermal conductivity requirement under the reference test conditions.'),
]


def write_pdf(path, quote):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/F1'): DictionaryObject({
            NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/Helvetica'),
        }),
    })})
    stream = DecodedStreamObject()
    stream.set_data(f'BT /F1 10 Tf 38 720 Td ({quote}) Tj ET'.encode('ascii'))
    page[NameObject('/Contents')] = stream
    writer.write(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='New directory for the isolated sample')
    args = parser.parse_args()
    target = args.data.resolve()
    try:
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error('The demo data directory must not already exist.')

    os.environ['ATLAS_DATA'] = str(target)
    os.environ.pop('ATLAS_DATABASE_URL', None)
    from backend.db import Analysis, Session, init_db, now
    from backend.product.models import ResearchProject
    from backend.services import upsert_papers

    init_db()
    documents = target / 'documents'
    documents.mkdir(exist_ok=True)
    upsert_papers('molecules', [
        {'id': pid, 'title': title, 'abstract': quote, 'version': 1,
         'authors': ['ResearchAtlas synthetic fixture'], 'categories': [],
         'published': now(), 'updated': now()} for pid, title, quote in EXAMPLES
    ])
    with Session.begin() as s:
        project = ResearchProject(
            title='导热材料替代 · 合成演示',
            scenario='material_substitution',
            question='在共同基准下，候选材料是否有足够的导热与绝缘验证依据？',
            constraints='本案例完全虚构，只用于核对流程。比较基准温度和试样厚度。',
            criteria=[{'id': 'thermal', 'label': '导热表现'},
                      {'id': 'insulation', 'label': '电绝缘验证'}],
        )
        s.add(project)
        s.flush()
        scope = {'projects': [project.id], 'sources': []}
        for pid, _, quote in EXAMPLES:
            path = documents / f'{hashlib.sha256(pid.encode()).hexdigest()}v1.pdf'
            write_pdf(path, quote)
            pdf_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            parsed = json.dumps([{'page': 1, 'text': quote}]).encode('utf-8')
            (documents / f'{pdf_hash}.json').write_bytes(parsed)
            row = Analysis(paper_id=pid, domain_id='molecules', version=1,
                           taxonomy_version=1, model='synthetic-demo', content_hash=pdf_hash,
                           result={'summary': quote, 'coverage': 'synthetic-demo',
                                   'topics': [], 'methods': [], 'problems': [],
                                   'claims': [{'kind': 'contribution', 'text': quote, 'page': 1, 'quote': quote}]})
            s.add(row)
            s.flush()
            scope['sources'].append({
                'analysis_id': row.id, 'pdf_sha256': pdf_hash,
                'parsed_sha256': hashlib.sha256(parsed).hexdigest(),
            })
    path = target / 'agentarts-scope.json'
    path.write_text(json.dumps(scope, indent=2), encoding='utf-8')
    print(json.dumps({'data': str(target), 'scope': str(path), 'project_id': scope['projects'][0],
                      'query': 'thermal conductivity'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
