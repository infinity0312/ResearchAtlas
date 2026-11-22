import pytest
from backend import sources

@pytest.mark.parametrize('size,valid',[(26,True),(81,False)])
def test_large_scientific_pdf_streaming_is_bounded_and_atomic(tmp_path,monkeypatch,size,valid):
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def raise_for_status(self): pass
        def iter_bytes(self):
            yield b'%PDF-1.7\n'
            for _ in range(size): yield b'0'*(1024*1024)
    class Client(Response):
        def __init__(self,**kwargs): pass
        def stream(self,*args): return Response()
    monkeypatch.setattr(sources.httpx,'Client',Client)
    monkeypatch.setattr(sources,'arxiv_wait',lambda:None)
    target=tmp_path/'paper.pdf'
    if valid:
        sources.download_pdf('2609.29344',1,target)
        assert target.stat().st_size>25*1024*1024
    else:
        with pytest.raises(ValueError,match='80MB'):sources.download_pdf('2609.29344',1,target)
        assert not target.exists()
    assert not target.with_suffix('.pdf.part').exists()
