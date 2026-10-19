import numpy as np, wave
SR=44100; DUR=20.8; n=int(SR*DUR); T=np.arange(n)/SR
rs=np.random.RandomState(11)
def env(t0,a,d,rel=0):  # pluck-ish envelope helper not used for pads
    pass
def pad(freqs,t0,t1,fade=1.0,gain=.05):
    out=np.zeros(n); m=(T>=t0-fade)&(T<=t1+fade)
    tt=T[m]
    w=np.clip((tt-(t0-fade))/(2*fade),0,1)*np.clip(((t1+fade)-tt)/(2*fade),0,1)
    w=np.sin(w*np.pi/2)
    sig=np.zeros_like(tt)
    for i,f in enumerate(freqs):
        for det in (-.12,0,.12):
            ph=rs.rand()*6.28
            for h,amp in ((1,1),(2,.35),(3,.15),(4,.07)):
                sig+=amp/ (1+0.0*h)*np.sin(2*np.pi*(f*h+det*h)*tt+ph)*(0.7 if f<150 else 1)
    sig*=1+0.08*np.sin(2*np.pi*.23*tt)
    out[m]=sig*w*gain/len(freqs)
    return out
def pluck(f,t0,gain=.2,dec=1.6):
    m=T>=t0; tt=T[m]-t0
    s=(np.sin(2*np.pi*f*tt)+.35*np.sin(2*np.pi*2*f*tt)*np.exp(-tt*5)+.12*np.sin(2*np.pi*3*f*tt)*np.exp(-tt*9))
    e=np.minimum(tt/.004,1)*np.exp(-tt/dec*3)
    o=np.zeros(n);o[m]=s*e*gain;return o
def sub(f,t0,gain=.28,dec=2.2):
    m=T>=t0; tt=T[m]-t0
    o=np.zeros(n);o[m]=np.sin(2*np.pi*f*tt*(1-.04*np.exp(-tt*3)))*np.exp(-tt/dec*3)*np.minimum(tt/.03,1)*gain;return o
def swell(t0,t1,gain=.07,lo=300,hi=3500):
    # ruido de banda filtrado por FFT, con envolvente en campana
    nz=rs.randn(n); F=np.fft.rfft(nz); fr=np.fft.rfftfreq(n,1/SR)
    c=lo*(hi/lo)**np.clip((fr-0)/6000,0,1)
    F*=np.exp(-((np.log(np.maximum(fr,1)/ 900))**2)/(2*.7**2))
    nz=np.fft.irfft(F,n)
    e=np.zeros(n);m=(T>=t0)&(T<=t1);x=(T[m]-t0)/(t1-t0);e[m]=np.sin(np.pi*x)**2
    return nz/np.max(np.abs(nz))*e*gain
Am=[110,164.8,220,261.6]; Fm=[87.3,130.8,220,329.6]; Cm=[130.8,196,246.9,329.6]; Gm=[98,146.8,246.9,293.7]; Cadd=[65.4,130.8,196,293.7,329.6]
dry=np.zeros(n)
dry+=pad(Am,0,3.4,1.0,.9)+pad(Fm,3.4,7.0,1.0,.9)+pad(Cm,7.0,11.0,1.0,.9)+pad(Gm,11.0,16.7,1.0,.9)+pad(Cadd,16.7,20.8,1.2,1.0)
dry+=swell(3.0,4.4,.10)+swell(6.4,7.6,.08)
dry+=sub(55,.15,.22)+sub(65.4,7.0,.30)+sub(65.4,16.7,.34,2.8)
# plucks: una por preferencia + cierre
for tt,f in ((11.3,659.3),(13.2,784.0),(15.1,880.0)): dry+=pluck(f,tt,.20,1.9)
dry+=pluck(1046.5,17.0,.18,2.6)+pluck(784,17.0,.10,2.6)
# ticks suaves al conectar nodos de la red (pentatónica, muy bajos)
pent=[1046.5,1174.7,1318.5,1568,1760]
for k in range(20): dry+=pluck(pent[k%5],4.2+k*.52+.05,.028,.5)
# reverb sintética
L=int(SR*2.6); tI=np.arange(L)/SR
def ir(seed):
    r=np.random.RandomState(seed).randn(L)*np.exp(-tI*2.4)
    F=np.fft.rfft(r);fr=np.fft.rfftfreq(L,1/SR);F*=1/(1+(fr/3500)**2);return np.fft.irfft(F,L)
def conv(x,h):
    N=1<<int(np.ceil(np.log2(len(x)+len(h))));return np.fft.irfft(np.fft.rfft(x,N)*np.fft.rfft(h,N),N)[:len(x)]
wetL=conv(dry,ir(1)); wetR=conv(dry,ir(2))
wetL/=np.max(np.abs(wetL))+1e-9; wetR/=np.max(np.abs(wetR))+1e-9
dn=dry/ (np.max(np.abs(dry))+1e-9)
sc=np.max(np.abs(dry))
L_=dn*.78+wetL*.20*(sc/ sc); R_=dn*.78+wetR*.20
# desfase estéreo leve
d=int(SR*.012); R_=np.concatenate([np.zeros(d),R_[:-d]])
st=np.stack([L_,R_],1)
fade=np.ones(n);fade[:int(.4*SR)]=np.linspace(0,1,int(.4*SR));fade[-int(1.4*SR):]=np.linspace(1,0,int(1.4*SR))
st*=fade[:,None]; st*=0.708/np.max(np.abs(st))  # -3 dBFS pico
with wave.open('audio.wav','wb') as w:
    w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes((st*32767).astype('<i2').tobytes())
print('ok')
