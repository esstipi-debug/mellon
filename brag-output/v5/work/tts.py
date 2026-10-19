import json, re, sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
D='/tmp/claude-0/-home-user-mytra-fde/c0e0ecd8-06b2-5546-8e96-1e1b741b3ab5/scratchpad/tts/'
k=Kokoro(D+'kokoro.onnx',D+'voices.bin')
VOICE,SPEED='am_michael',1.12
script=json.load(open('work/script.json'))
SR=24000; t=0.0; scenes=[]; cues=[]
HEAD={'s0':0.6}; TAIL={'s7':5.2}
for s in script:
    a,sr=k.create(s['text'],voice=VOICE,speed=SPEED,lang='en-us')
    # recorta silencio inicial/final
    nz=np.where(np.abs(a)>0.01)[0]; a=a[nz[0]:nz[-1]+1]
    sf.write(f"work/voice/{s['id']}.wav",a,sr)
    dur=len(a)/sr; head=HEAD.get(s['id'],0.35); tail=TAIL.get(s['id'],0.4)
    sc=dict(id=s['id'],start=round(t,3),voice_at=round(t+head,3),voice_dur=round(dur,3),dur=round(head+dur+tail,3))
    scenes.append(sc)
    # subtítulos: frases cortas, tiempo proporcional a caracteres
    parts=[p.strip() for p in re.split(r'(?<=[.:?])\s+',s['text']) if p.strip()]
    chunks=[]
    for p in parts:
        if len(p)>62:
            sub=[x.strip() for x in re.split(r'(?<=,)\s+',p) if x.strip()]
            cur=''
            for x in sub:
                if cur and len(cur)+len(x)>62: chunks.append(cur);cur=x
                else: cur=(cur+' '+x).strip()
            if cur: chunks.append(cur)
        else: chunks.append(p)
    # une frases muy cortas ("One.", "Two.") con la siguiente
    m=[]
    for c in chunks:
        if m and len(m[-1])<8: m[-1]=m[-1]+' '+c
        else: m.append(c)
    tot=sum(len(c) for c in m); x=sc['voice_at']
    for c in m:
        d=dur*len(c)/tot; cues.append(dict(t0=round(x,3),t1=round(x+d,3),text=c)); x+=d
    t+=sc['dur']
json.dump(dict(total=round(t,3),scenes=scenes,cues=cues),open('work/timeline.json','w'),indent=1)
print('total',round(t,1),[ (s['id'],s['dur']) for s in scenes])
