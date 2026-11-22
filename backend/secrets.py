"""Windows DPAPI per-user protection; mode-0600 file on other platforms."""
import ctypes, os
from ctypes import wintypes
from .db import DATA

def _crypt(data: bytes, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_char))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError('无法访问当前用户的密钥存储')
    try: return ctypes.string_at(target.data, target.size)
    finally: ctypes.windll.kernel32.LocalFree(target.data)

def save_key(key: str):
    path = DATA / 'provider.key'
    payload = key.encode()
    path.write_bytes(_crypt(payload) if os.name == 'nt' else payload)
    if os.name != 'nt': path.chmod(0o600)

def get_key():
    env = os.environ.get('DEEPSEEK_API_KEY')
    if env: return env
    path = DATA / 'provider.key'
    if not path.exists(): return ''
    raw = path.read_bytes()
    return (_crypt(raw, True) if os.name == 'nt' else raw).decode()
