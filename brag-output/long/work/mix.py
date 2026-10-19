import json,wave,subprocess,numpy as np,soundfile as sf
TL=json.load(open('timeline.json')); SR=44100; DUR=TL['total']; n=int(SR*DUR); T=np.arange(n)/SR
rs=np.random.RandomState(11)
# ---- voz ----
voice=np.zeros(n)
for sc in TL['scenes']:
    a,sr=sf.read(f"voice/{sc['id']}.wav")
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',f"voice/{sc['id']}.wav",'-ar',str(SR),'-ac','1','_v.wav'],check=True)
    a,_=sf.read('_v.wav'); a=a/ (np.sqrt(np.mean(a**2))+1e-9)*0.075
    # fundido corto para evitar clics
    f=int(.01*SR); a[:f]*=np.linspace(0,1,f); a[-f:]*=np.linspace(1,0,f)
    i=int(sc['voice_at']*SR); voice[i:i+len(a)]+=a[:max(0,n-i)]
# ---- música ----
def pad(freqs,t0,t1,fade=1.2,gain=.05):
    out=np.zeros(n); m=(T>=t0-fade)&(T<=t1+fade); tt=T[m]
    w=np.clip((tt-(t0-fade))/(2*fade),0,1)*np.clip(((t1+fade)-tt)/(2*fade),0,1); w=np.sin(w*np.pi/2)
    sig=np.zeros_like(tt)
    for f in freqs:
        for det in (-.12,0,.12):
            ph=rs.rand()*6.28
            for h,amp in ((1,1),(2,.35),(3,.15),(4,.07)): sig+=amp*np.sin(2*np.pi*(f*h+det*h)*tt+ph)*(0.7 if f<150 else 1)
    sig*=1+0.08*np.sin(2*np.pi*.23*tt)
    out[m]=sig*w*gain/len(freqs); return out
def pluck(f,t0,gain=.2,dec=1.6):
    m=T>=t0; tt=T[m]-t0
    s=np.sin(2*np.pi*f*tt)+.35*np.sin(2*np.pi*2*f*tt)*np.exp(-tt*5)+.12*np.sin(2*np.pi*3*f*tt)*np.exp(-tt*9)
    o=np.zeros(n);o[m]=s*np.minimum(tt/.004,1)*np.exp(-tt/dec*3)*gain;return o
def sub(f,t0,gain=.28,dec=2.2):
    m=T>=t0; tt=T[m]-t0; o=np.zeros(n); o[m]=np.sin(2*np.pi*f*tt*(1-.04*np.exp(-tt*3)))*np.exp(-tt/dec*3)*np.minimum(tt/.03,1)*gain; return o
def swell(t0,t1,gain=.08):
    nz=rs.randn(n);F=np.fft.rfft(nz);fr=np.fft.rfftfreq(n,1/SR);F*=np.exp(-((np.log(np.maximum(fr,1)/900))**2)/(2*.7**2));nz=np.fft.irfft(F,n)
    e=np.zeros(n);m=(T>=t0)&(T<=t1);x=(T[m]-t0)/(t1-t0);e[m]=np.sin(np.pi*x)**2;return nz/np.max(np.abs(nz))*e*gain
CH={'Am':[110,164.8,220,261.6],'F':[87.3,130.8,220,329.6],'C':[130.8,196,246.9,329.6],'G':[98,146.8,246.9,293.7],'Cadd':[65.4,130.8,196,293.7,329.6]}
NOTES={'Am':[440,523.3,659.3,880],'F':[440,523.3,698.5,880],'C':[392,523.3,659.3,784],'G':[392,493.9,587.3,784],'Cadd':[523.3,659.3,784,1046.5]}
prog=['Am','Am','F','C','G','Am','F','C','G','Am','F','C','G','Cadd']
mus=np.zeros(n)
for sc,ch in zip(TL['scenes'],prog):
    t0,t1=sc['start'],sc['start']+sc['dur']
    mus+=pad(CH[ch],t0,t1,1.2,1.0 if ch!='Cadd' else 1.2)
    mus+=sub(CH[ch][0]/2 if CH[ch][0]>80 else CH[ch][0],t0+.15,.18,2.0)
    k=0;tt=t0+.9
    while tt<t1-.6:
        mus+=pluck(NOTES[ch][k%4],tt,.05,1.4);k+=1;tt+=1.2
mus+=swell(6.4,8.0,.10)+pluck(1046.5,TL['scenes'][13]['start']+3.9,.16,3.0)+sub(65.4,TL['scenes'][13]['start']+3.9,.3,3.0)
# reverb
L=int(SR*2.6);tI=np.arange(L)/SR
def ir(seed):
    r=np.random.RandomState(seed).randn(L)*np.exp(-tI*2.4);F=np.fft.rfft(r);fr=np.fft.rfftfreq(L,1/SR);F*=1/(1+(fr/3500)**2);return np.fft.irfft(F,L)
def conv(x,h):
    N=1<<int(np.ceil(np.log2(len(x)+len(h))));return np.fft.irfft(np.fft.rfft(x,N)*np.fft.rfft(h,N),N)[:len(x)]
mus/=np.max(np.abs(mus))
wl=conv(mus,ir(1));wr=conv(mus,ir(2));wl/=np.max(np.abs(wl));wr/=np.max(np.abs(wr))
ml=mus*.78+wl*.2;mr=mus*.78+wr*.2;d=int(SR*.012);mr=np.concatenate([np.zeros(d),mr[:-d]])
# ducking según envolvente de voz
w=int(.15*SR);env=np.convolve(np.abs(voice),np.ones(w)/w,mode='same');env=np.clip(env/0.09,0,1)
duck=1-.6*np.clip(np.convolve(env,np.ones(int(.25*SR))/int(.25*SR),mode='same')*1.6,0,1)
base=0.06/ (np.sqrt(np.mean(ml**2))+1e-9)*0.075/0.075   # música ~ -21 dBFS RMS
ml*=base*duck; mr*=base*duck
# voz centrada + un toque de sala
vw=conv(voice,ir(3))[:n]; vw/=np.max(np.abs(vw))+1e-9
vL=voice+vw*0.02*np.sqrt(np.mean(voice**2))/ (np.sqrt(np.mean(vw**2))+1e-9)*8
st=np.stack([ml+vL,mr+vL],1)
fade=np.ones(n);fade[:int(.3*SR)]=np.linspace(0,1,int(.3*SR));fade[-int(1.5*SR):]=np.linspace(1,0,int(1.5*SR));st*=fade[:,None]
st*=0.78/np.max(np.abs(st))
sf.write('audio.wav',st.astype('float32'),SR,subtype='PCM_16');print('ok',DUR)
