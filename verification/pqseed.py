import json,glob,os,sys
sid=sys.argv[1]; code=sys.argv[2]
base=os.path.expanduser('~/.claude/pending-questions/'+sid)
ds=[]
for f in glob.glob(base+'*.json'):
    try: ds.append(json.load(open(f)))
    except Exception: pass
d=max(ds,key=lambda x:x['seq'])
exec(code)
d['seq']+=1
open(f"{base}.{d['seq']%2}.json",'w').write(json.dumps(d,ensure_ascii=False))
print('seeded seq',d['seq'])
