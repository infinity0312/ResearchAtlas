from backend import parser

def test_pdf_with_broken_cmap_keeps_pages_and_valid_unicode(monkeypatch):
    class Page:
        def get_contents(self): return None
        def extract_text(self): return 'Scientific text '*40+'\ud800 formula \udfff \ud835\udc00'
    class Reader:
        is_encrypted=False
        pages=[Page(),Page()]
    monkeypatch.setattr(parser,'PdfReader',lambda _:Reader())
    pages=parser.parse('fixture.pdf')
    assert [p['page'] for p in pages]==[1,2]
    assert '\ufffd formula \ufffd' in pages[0]['text']
    assert '\U0001d400' in pages[0]['text']
    assert pages[0]['text'].encode('utf-8')
