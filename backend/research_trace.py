"""Read-only research trace for the specific analysis shown in the reader."""

import hashlib
import json
import re

from .analysis_pipeline import verified_claims
from .analysis_repository import read_analysis, review_certificates, source_updates
from .db import DATA, Domain, Version
from .evidence_packet import HEADINGS
from .independent_review import certificate_result


def parsed_source(content_hash):
    if not re.fullmatch(r'[a-fA-F0-9]{64}', content_hash or ''):
        return None
    path = DATA / 'documents' / f'{content_hash}.json'
    try:
        if path.stat().st_size > 24 * 1024 * 1024:
            return None
        rows = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(rows, list) or not rows or not all(
        isinstance(row, dict) and type(row.get('page')) is int and row['page'] > 0
        and isinstance(row.get('text'), str) for row in rows
    ):
        return None
    if len({row['page'] for row in rows}) != len(rows):
        return None
    return rows


def trace(s, paper, analysis):
    version = analysis.version if analysis else paper.version
    name = f'{hashlib.sha256(paper.id.encode()).hexdigest()}v{version}.pdf'
    has_pdf = (DATA / 'documents' / name).is_file()
    rows = parsed_source(analysis.content_hash) if analysis else None
    metadata = s.get(Version, (paper.id, version))
    curated = (metadata.metadata_json or {}).get('historical_curation') if metadata else None
    reason = curated.get('reason') if isinstance(curated, dict) else None
    content = {'paper_version': version, 'pdf_available': has_pdf,
               'parsed_pages': len(rows) if rows else None, 'date_basis': paper.date_basis,
               'first_seen': paper.first_seen, 'curation_reason': reason[:200] if isinstance(reason, str) else None,
               'analysis': None}
    if analysis is None:
        return content

    certificate = review_certificates(s, [analysis.id]).get(analysis.id)
    reviewed = certificate_result(analysis, certificate)
    view = read_analysis(analysis, paper, s.get(Domain, analysis.domain_id),
                         source_updates(s, [paper.id]), full=True, independent_review=certificate)
    result = view['result']
    claims = result.get('claims') if isinstance(result.get('claims'), list) else []
    valid_claims = [claim for claim in claims if isinstance(claim, dict)
                    and isinstance(claim.get('supporting_evidence', []), list)]
    source_checks = len(verified_claims(valid_claims, rows)) if rows else None
    markdown = result.get('fulltext_markdown')
    headings = set(re.findall(r'^##\s+(.+?)\s*$', markdown, re.M)) if isinstance(markdown, str) else set()
    generation_model = analysis.model
    reviewers = []
    if reviewed is not None:
        # Model labels outside approved receipts must not imply independent review.
        generation_model = analysis.model.removesuffix(' · codex reviewed')
        for role in ('independent', 'coordinator'):
            receipt = certificate.get(role)
            if isinstance(receipt, dict):
                model = receipt.get('reviewer_model')
                if isinstance(model, str) and model.strip():
                    pages = receipt.get('reviewed_pages')
                    checked_pages = sorted({p for p in pages if type(p) is int and p > 0}) if isinstance(pages, list) else []
                    reviewers.append({'role': role, 'model': model, 'pages': checked_pages})
    content['analysis'] = {
        'id': analysis.id, 'created': analysis.created, 'domain_id': analysis.domain_id,
        'taxonomy_version': analysis.taxonomy_version, 'content_hash': analysis.content_hash,
        'recorded_model': generation_model, 'editorial_edit': isinstance(result.get('editorial_edit'), dict),
        'reviewers': reviewers, 'quality': view['quality'], 'has_report': bool(markdown),
        'report_sections': [heading for heading in HEADINGS if heading in headings],
        'claim_count': len(claims), 'quotes_located': source_checks,
        'analysis_page_count': result.get('pages') if type(result.get('pages')) is int else None,
    }
    return content
