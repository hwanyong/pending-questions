import json,glob,os,sys
base=os.path.expanduser('~/.claude/pending-questions/')
def best(sid):
    out=[]
    for f in glob.glob(base+sid+'*.json'):
        try: out.append(json.load(open(f)))
        except Exception: pass
    return max(out,key=lambda d:d['seq']) if out else None
sid=sys.argv[1]
d=best(sid)
print('seq',d['seq'],'mode',d['mode'],'chain',d['autoChain'],'unread',len(d['unread']))
for i in d['items']:
    print(i['id'],i['answeredBy'] or 'open',repr(i['question'])[:46],'->',repr(i['answer'])[:70],'delivered' if i['isDelivered'] else 'undelivered')
