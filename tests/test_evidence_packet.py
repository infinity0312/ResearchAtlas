import pytest
from backend.evidence_packet import source_blocks,resolve,EvidenceReview,HEADINGS
from backend.analysis import verified_claims

def test_blocks_keep_verbatim_text_and_page_breaks():
    pages=[{'page':1,'text':('An exact source sentence.\n'*120)+'end'},{'page':2,'text':'A separate page with Unicode eﬀects.'}]
    blocks=source_blocks(pages)
    for page in pages:assert ''.join(b['text'] for b in blocks.values() if b['page']==page['page'])==page['text']
    claims=[dict(kind='method',text='Supported claim',basis='author',evidence_id='p1b1') for _ in range(8)]
    r=EvidenceReview(summary='Summary',topics=['T'],methods=['M'],claims=claims,fulltext_markdown='\n'.join('## '+h+'\n'+('Detailed source explanation. '*28) for h in HEADINGS))
    result=resolve(r,blocks,['T']);assert len(verified_claims(result['claims'],pages))==8
    r.claims[0].evidence_id='p9b9'
    with pytest.raises(ValueError,match='unknown'):resolve(r,blocks,['T'])

def test_taxonomy_and_chapters_cannot_be_silently_normalized():
    r=EvidenceReview(summary='S',topics=['T'],methods=['M'],claims=[dict(kind='method',text='Claim',evidence_id='p1b1')]*8,fulltext_markdown='x'*3000)
    with pytest.raises(ValueError,match='taxonomy'):resolve(r,{},['Other'])
    with pytest.raises(ValueError,match='chapters'):resolve(r,{},['T'])


def test_cross_page_table_context_is_preserved_and_every_quote_checked():
    from backend.evidence_packet import ClaimRef,claim_row
    from backend.contracts import Claim
    blocks={'p1b1':{'page':1,'text':'Table 3. Model A, Model B. Error in meV.'},
            'p2b1':{'page':2,'text':'600 K energy error: 6.2 and 4.6.'}}
    ref=ClaimRef(kind='contribution',text='Model B has lower error at 600 K.',evidence_id='p2b1',context_evidence_ids=['p1b1'])
    row=Claim.model_validate(claim_row(ref,blocks)).model_dump()
    pages=[{'page':v['page'],'text':v['text']} for v in blocks.values()]
    assert verified_claims([row],pages)==[row]
    assert row['quote']==blocks['p2b1']['text']
    assert row['supporting_evidence'][0]['page']==1
    row['supporting_evidence'][0]['quote']='Invented table header and unit'
    assert verified_claims([row],pages)==[]
    ref.context_evidence_ids=['p9b1']
    with pytest.raises(ValueError,match='unknown'):claim_row(ref,blocks)
