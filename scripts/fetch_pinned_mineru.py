"""Range-resume the pinned public weights, accepting only the expected SHA256."""
from pathlib import Path
import hashlib
import shutil
import httpx

ROOT=Path('data/models/MinerU2.5-Pro-2605-1.2B')
URL='https://huggingface.co/opendatalab/MinerU2.5-Pro-2605-1.2B/resolve/bff20d4ae2bf202df9f45284b4d43681555a97ed/model.safetensors'
SIZE=2312126640
SHA='abf8681ca63b8dec7b67de257af47b821f179442f72998d0696ae2ed9232a5f0'


def main():
    final=ROOT/'model.safetensors';partial=ROOT/'model.safetensors.partial'
    if final.exists():return
    if not partial.exists():
        candidates=[p for p in ROOT.rglob('*.incomplete') if SHA in p.name and p.stat().st_size<SIZE]
        if candidates:shutil.copyfile(max(candidates,key=lambda p:p.stat().st_size),partial)
        else:partial.touch()
    with httpx.Client(timeout=httpx.Timeout(45,connect=15)) as client:
        while partial.stat().st_size<SIZE:
            start=partial.stat().st_size;end=min(start+16*1024*1024,SIZE)-1
            headers={'Range':f'bytes={start}-{end}'}
            redirect=client.get(URL,headers=headers,follow_redirects=False)
            if redirect.status_code not in (302,307):raise ValueError('Expected public weight redirect')
            with client.stream('GET',redirect.headers['location'],headers=headers) as response:
                if response.status_code!=206 or response.headers.get('content-range')!=f'bytes {start}-{end}/{SIZE}':
                    raise ValueError('Range mismatch; preserving existing partial bytes')
                with partial.open('ab') as output:
                    for block in response.iter_bytes():output.write(block)
            print('downloaded',partial.stat().st_size,'/',SIZE,flush=True)
    with partial.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=SHA:raise ValueError('Weight checksum mismatch; no model installed')
    partial.rename(final)
    print('Verified pinned weights',actual,flush=True)


if __name__=='__main__':main()
