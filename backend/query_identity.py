"""Conservative semantic identity; preserve field names, phrases and negation."""
import json
from functools import lru_cache
@lru_cache(maxsize=2048)
def query_identity(query):
 from .history import branches
 try:
  clauses=sorted(set(tuple(sorted(set((token,negative) for token,negative in branch))) for branch in branches(query)))
  return json.dumps(clauses,ensure_ascii=False,separators=(',',':'))
 except ValueError:return 'raw:'+query.strip()
def payload_identity(value):
 if isinstance(value,dict):return {k:query_identity(v) if k=='query' and isinstance(v,str) else payload_identity(v) for k,v in value.items()}
 if isinstance(value,list):return [payload_identity(v) for v in value]
 return value
