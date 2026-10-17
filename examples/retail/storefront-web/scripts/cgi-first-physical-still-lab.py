"""DUFYND CGI study: original analytic, layered glass/perfume ray tracing.
Local research asset, never auto-promote to storefront. No external models/textures.
"""
import math, os, argparse, time
import numpy as np
from numba import njit, prange
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# materials: 0 air, 1 optical glass, 2 perfumed fluid
# object surface: 1 outer shell, 2 inner shell, 3 liquid-air, 4 cap, 5 neck, 6 label, 7 cap gold, 8 atomizer
TINY=1.e-4

@njit

def vdot(a,b):return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
@njit
def vlen(a):return np.sqrt(vdot(a,a))
@njit
def vnorm(a):return a / max(1.e-12,vlen(a))
@njit
def vref(d,n):return d - 2.0*vdot(d,n)*n
@njit
def vrefract(d,n,eta):
    c=-vdot(d,n)
    k=1.0-eta*eta*(1.0-c*c)
    if k<0.0:return vref(d,n),False
    return vnorm(eta*d+(eta*c-np.sqrt(k))*n),True
@njit
def sdf_round3(x,y,z,ax,lo,hi,az,r):
    # Exact distance to a filleted 3D glass ingot: real curved shoulders/foot.
    qx=abs(x)-(ax-r)
    qy=abs(y-(lo+hi)*.5)-((hi-lo)*.5-r)
    qz=abs(z)-(az-r)
    return np.sqrt(max(qx,0.0)**2+max(qy,0.0)**2+max(qz,0.0)**2) + min(max(qx,qy,qz),0.)-r

@njit
def medium(x,y,z):
    if sdf_round3(x,y,z,1.08,.31,2.62,.57,.16)<0.0:
        if sdf_round3(x,y,z,.985,.48,2.46,.476,.102)<0.0:
            if y<=1.99:return 2
            return 0
        return 1
    return 0

@njit
def roundbox(x,z,ax,az,r):
    dx=abs(x)-(ax-r);dz=abs(z)-(az-r)
    return np.sqrt(max(dx,0.0)**2+max(dz,0.0)**2)+min(max(dx,dz),0.)-r

@njit
def hit_round3(o,d,ax,lo,hi,az,r):
    # A true 3D signed distance field provides a continuous optical normal.
    # Sphere tracing steps are conservative; no screen-space bottle tint.
    t=0.0
    for step in range(68):
        x=o[0]+d[0]*t;y=o[1]+d[1]*t;z=o[2]+d[2]*t
        dist=sdf_round3(x,y,z,ax,lo,hi,az,r)
        if abs(dist)<.0004 and t>.0002:
            eps=.0006
            dx=sdf_round3(x+eps,y,z,ax,lo,hi,az,r)-sdf_round3(x-eps,y,z,ax,lo,hi,az,r)
            dy=sdf_round3(x,y+eps,z,ax,lo,hi,az,r)-sdf_round3(x,y-eps,z,ax,lo,hi,az,r)
            dz=sdf_round3(x,y,z+eps,ax,lo,hi,az,r)-sdf_round3(x,y,z-eps,ax,lo,hi,az,r)
            return t,vnorm(np.array((dx,dy,dz)))
        t+=max(.00035,abs(dist)*.83)
        if t>25.:break
    return 1.e15,np.zeros(3)

@njit
def hit_cylinder(o,d,x,y,z,r,lo,hi):
    dx=o[0]-x;dz=o[2]-z
    a=d[0]*d[0]+d[2]*d[2];b=dx*d[0]+dz*d[2];c=dx*dx+dz*dz-r*r
    best=1.e15;N=np.zeros(3)
    if a>1.e-9:
        discr=b*b-a*c
        if discr>=0:
            sq=np.sqrt(discr)
            for t in ((-b-sq)/a,(-b+sq)/a):
                if t>1.e-4 and t<best and lo<=o[1]+d[1]*t<=hi:
                    best=t;N[0]=(dx+d[0]*t)/r;N[1]=0;N[2]=(dz+d[2]*t)/r
    if abs(d[1])>1.e-9:
        for yy,s in ((lo,-1.),(hi,1.)):
            t=(yy-o[1])/d[1]
            if t>1.e-4 and t<best and (dx+d[0]*t)**2+(dz+d[2]*t)**2<=r*r:
                best=t;N[0]=0.;N[1]=s;N[2]=0.
    return best,N

@njit
def hit_metal(o,d,opened):
    # caps/neck/atomizer, immutable studio geometry for self-contained render
    # returns t, material, normal
    tt=1.e15;kind=0;N=np.zeros(3)
    # Black cap: exploded in 'open' state but kept as a real 3D solid
    cap_y_shift=.74 if opened else 0.
    cap_x_shift=.27 if opened else 0.
    for x,z,r,y0,y1,k in (
        (cap_x_shift,.0,.487,2.87+cap_y_shift,3.48+cap_y_shift,4),
        (cap_x_shift,.0,.492,2.881+cap_y_shift,2.900+cap_y_shift,7),
        (0.,.0,.301,2.648,2.694,7),
        (0.,.0,.245,2.62,2.87,5),
        (0.,.0,.290,2.790,2.835,7),
        (0.,.0,.126,2.83,2.943,8),
    ):
        t,n=hit_cylinder(o,d,x,0.,z,r,y0,y1)
        if t<tt:
            tt=t;kind=k;N=n
    return tt,kind,N

@njit
def hit_scene(o,d,opened):
    tt=1.e15; N=np.zeros(3);kind=0
    t,n=hit_round3(o,d,1.08,.31,2.62,.57,.16)
    if t<tt:tt=t;kind=1;N=n
    t,n=hit_round3(o,d,.985,.48,2.46,.476,.102)
    if t<tt:tt=t;kind=2;N=n
    if abs(d[1])>1.e-8:
        t=(1.99-o[1])/d[1]
        if t>1.e-4 and t<tt and sdf_round3(o[0]+t*d[0],1.99,o[2]+t*d[2],.985,.48,2.46,.476,.102)<-1.e-6:
            tt=t;kind=3;N=np.array((0.,1.,0.))
    # A deeply embossed separate brand-label panel with 3D shadow edges.
    if abs(d[2])>1.e-7:
        t=(.588-o[2])/d[2]
        x=o[0]+d[0]*t;y=o[1]+d[1]*t
        if t>1.e-4 and t<tt and abs(x)<.635 and .97<y<1.925 and d[2]<0.:
            tt=t;kind=6;N=np.array((0.,0.,1.))
    t,k,n=hit_metal(o,d,opened)
    if t<tt:tt=t;kind=k;N=n
    return tt,kind,N

@njit
def rect_glow(d,center,spread_x,spread_y,intensity):
    # Smooth angular rectangular softbox, not an arbitrary bottle overlay.
    vec=vnorm(center)
    u=np.array((vec[2],0.,-vec[0]));u=vnorm(u)
    v=np.cross(u,vec)
    c=vdot(d,vec)
    if c<0.7:return 0.
    x=vdot(d,u)/c;y=vdot(d,v)/c
    # feathered area panel highlights
    aa=np.sqrt((x/max(.001,spread_x))**4+(y/max(.001,spread_y))**4)
    edge=max(0.,min(1.,(1.21-aa)*5.))
    return intensity*edge*edge*(3.-2.*edge)

@njit
def env(d,mask=1.0):
    # matte champaign backdrop in transmission, deep dark flags in reflection,
    # four physically directioned studio panels.
    horizon=min(1.0,max(.48,.86+.12*d[1]))
    C=np.array((1.03*horizon,.86*horizon,.70*horizon))
    # softboxes: intentional broad strips, amber bounce and opposing dark flag
    s=rect_glow(d,np.array((-3.5,2.2,5.0)),.14,.9,3.9)
    C+=s*np.array((1.,.88,.70))
    s=rect_glow(d,np.array((3.4,3.0,5.5)),.065,.76,4.8)
    C+=s*np.array((.83,.92,1.0))
    s=rect_glow(d,np.array((-1.4,7.,-3.0)),.49,.28,2.3)
    C+=s*np.array((1.0,.94,.83))
    s=rect_glow(d,np.array((2.2,3.0,-5.0)),.25,.85,2.5)
    C+=s*np.array((1.0,.60,.32))
    s=rect_glow(d,np.array((4.,.8,4.0)),.12,.85,.68)
    C-=s*np.array((.47,.42,.39))
    return np.maximum(.0,C)

@njit
def refraction_env(o,d):
    # Finite studio diffusion plane BEHIND the object, not a painted color
    # on its silhouette. Refracted rays actually travel to this field.
    # Gaussian softbox/negative-fill profiles avoid hard rectangular shapes.
    C=env(d)
    if d[2] < -.035:
        t=(-3.5-o[2])/d[2]
        if t>0.0 and t<70.0:
            x=o[0]+d[0]*t
            y=o[1]+d[1]*t
            key=np.exp(-.5*((x+.71)/.34)**2)*np.exp(-.5*((y-1.65)/2.7)**2)
            broad=np.exp(-.5*((x-.25)/.84)**2)*np.exp(-.5*((y-1.55)/2.25)**2)
            rim=np.exp(-.5*((x-1.39)/.19)**2)*np.exp(-.5*((y-1.65)/2.5)**2)
            neg=np.exp(-.5*((x-.84)/.33)**2)*np.exp(-.5*((y-1.62)/2.65)**2)
            C+=key*np.array((1.75,1.50,1.15))
            C+=broad*np.array((.34,.24,.19))
            C+=rim*np.array((.89,1.03,1.10))
            C-=neg*np.array((.67,.62,.56))
    return np.maximum(C,.02)

@njit
def fresnel(n1,n2,cosi):
    r=((n1-n2)/(n1+n2))**2
    return r+(1.-r)*(1.-cosi)**5

@njit
def label_sample(x,y,tex):
    u=(x+.635)/1.27;v=(1.925-y)/.955
    col=min(tex.shape[1]-1,max(0,int(u*(tex.shape[1]-1))))
    row=min(tex.shape[0]-1,max(0,int(v*(tex.shape[0]-1))))
    color=np.array((tex[row,col,0],tex[row,col,1],tex[row,col,2]))/255.
    # seam lighting and gold foil variation / slight raised stamping
    illum=.78+.18*max(0.,min(1.,(x+.635)/1.27))
    return color*illum

@njit
def shade_metal(kind,n,d,p):
    # dark metallic PBR with Fresnel reflection of the softboxes
    r=vnorm(vref(d,n))
    rr=env(r)
    nd=max(0.,-vdot(d,n))
    if kind==4:
        # dark brushed anodised cap, bright metallic edge and warm highlights
        base=np.array((.016,.014,.013))
        color=base*.55+rr*.095
        stripe=.5+.5*np.sin(p[1]*610.)
        color+=np.array((.013,.01,.006))*stripe
    elif kind==7:
        base=np.array((.27,.16,.060))
        color=base*.20+rr*np.array((.80,.61,.28))*.46
    else:
        base=np.array((.055,.04,.027))
        color=base*.25+rr*np.array((.62,.53,.38))*.35
    # bevel appearance through axial location-based Fresnel
    return color*(.86+.14*(1.-nd)**2)

@njit
def trace(o,d,tex,opened):
    # Iterative forward ray transport with Fresnel reflection highlights.
    # Weighted deterministic branch avoids Monte Carlo white noise in stills.
    result=np.zeros(3);throughput=np.ones(3);hit_any=0;fluid_distance=0.
    for bounce in range(11):
        t,kind,n=hit_scene(o,d,opened)
        if t>1.e12:
            result+=throughput*refraction_env(o,d)
            return result, max(0.,min(1.,.44+.58*fluid_distance)) if hit_any else 0.
        p=o+d*t
        hit_any=1
        if kind>=4 and kind!=6:
            result+=throughput*shade_metal(kind,n,d,p)
            return result,1
        if kind==6:
            texcol=label_sample(p[0],p[1],tex)
            r=vref(d,n)
            result+=throughput*(texcol*.57 + env(r)*.020)
            return result,1
        before=medium(o[0],o[1],o[2])
        after=medium(p[0]+d[0]*.0018,p[1]+d[1]*.0018,p[2]+d[2]*.0018)
        if before==after:
            o=p+d*.002;continue
        if before==2:
            absorption=np.array((.15,.92,2.05))
            throughput*=np.exp(-absorption*t)
            fluid_distance+=t
        if before==1 and after==2:n1=1.52;n2=1.339
        elif before==2 and after==1:n1=1.339;n2=1.52
        elif before==2 and after==0:n1=1.339;n2=1.
        elif before==0 and after==2:n1=1.;n2=1.339
        elif before==1 and after==0:n1=1.52;n2=1.
        elif before==0 and after==1:n1=1.;n2=1.52
        else:n1=1.;n2=1.
        nn=n if vdot(d,n)<0 else -n
        cosi=max(0.,min(1.,-vdot(d,nn)))
        refl=vnorm(vref(d,nn))
        F=fresnel(n1,n2,cosi)
        refr,possible=vrefract(d,nn,n1/n2)
        if not possible:
            d=refl;o=p+d*.002;continue
        # reflected studio highlights are real env specular, keep direction
        # behind camera and off-axis sources physically varied across surface
        result+=throughput*F*env(refl)
        throughput*=1.-F
        o=p+refr*.002
        d=refr
        if max(throughput)<.003:break
    result+=throughput*refraction_env(o,d)
    return result, max(0.,min(1.,.44+.58*fluid_distance))

@njit
def tonemap(c):
    # ACES-inspired HDR map followed by perceptual transfer
    x=c*.82
    v=(x*(2.51*x+.03))/(x*(2.43*x+.59)+.14)
    v=np.maximum(0.,np.minimum(1.,v))
    return np.power(v,1./2.2)

@njit(parallel=True)
def render(width,height,samples,opened,tex):
    out=np.empty((height,width,3),dtype=np.uint8)
    mask=np.empty((height,width),dtype=np.uint8)
    aspect=width/height
    campos=np.array((3.70,3.45,9.30)) if opened else np.array((3.3,3.05,8.2))
    center=np.array((0.,2.06,0.)) if opened else np.array((0.,1.82,0.))
    fw=vnorm(center-campos)
    right=vnorm(np.cross(fw,np.array((0.,1.,0.))))
    up=vnorm(np.cross(right,fw))
    size=math.tan(math.radians(26.8)/2.)
    for py in prange(height):
      for px in range(width):
        col=np.zeros(3);hit=0
        for sy in range(samples):
          ix=px+(sy*0.61803398875)%1.
          iy=py+(sy*0.75487766625)%1.
          u=(ix/width-.5)*2*size*aspect
          v=(.5-iy/height)*2*size
          direction=vnorm(fw+u*right+v*up)
          c,h=trace(campos,direction,tex,opened)
          col+=c
          hit+=h
        col=tonemap(col/samples)
        for ch in range(3):out[py,px,ch]=int(max(0,min(255,col[ch]*255)))
        mask[py,px]=round(hit*255/samples)
    return out,mask

def make_label():
    w,h=920,690
    a=Image.new('RGB',(w,h),(19,18,16));draw=ImageDraw.Draw(a)
    draw.rectangle((16,16,w-17,h-17),outline=(164,122,67),width=7)
    draw.rectangle((26,26,w-27,h-27),outline=(72,57,37),width=2)
    serif='/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
    sans='/usr/share/fonts/truetype/lato/Lato-Semibold.ttf'
    light='/usr/share/fonts/truetype/lato/Lato-Regular.ttf'
    def centered(y,txt,font,color):
        l,t,r,b=draw.textbbox((0,0),txt,font=font)
        draw.text(((w-(r-l))/2,y),txt,font=font,fill=color)
    centered(110,'D U F Y N D',ImageFont.truetype(sans,40),(199,152,86))
    draw.line((w*.34,206,w*.66,206),fill=(140,103,61),width=2)
    centered(230,'n° 01',ImageFont.truetype(serif,170),(221,177,114))
    centered(514,'MAISON DE PARFUM',ImageFont.truetype(light,27),(157,116,71))
    draw.line((w*.41,577,w*.59,577),fill=(113,87,53),width=2)
    return np.asarray(a,dtype=np.uint8)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--width',type=int,default=560)
    parser.add_argument('--height',type=int,default=620)
    parser.add_argument('--samples',type=int,default=2)
    parser.add_argument('--out',default='.cgi-lab/perfume-study-closed.png')
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    if not (240 <= args.width <= 1600 and 240 <= args.height <= 1600 and 1 <= args.samples <= 20):
        parser.error('lab render limits: 240..1600 px, 1..20 samples')
    out=os.path.abspath(args.out)
    if not out.lower().endswith('.png') or '/public/' in out.replace('\\','/'):
        parser.error('internal lab output must be a PNG outside storefront public/')
    os.makedirs(os.path.dirname(out),exist_ok=True)
    tex=make_label()
    started=time.monotonic()
    img,mask=render(args.width,args.height,args.samples,args.open,tex)
    rgba=np.dstack((img,mask)).astype(np.uint8)
    Image.fromarray(rgba,'RGBA').save(out)
    # Light beige page color and rgba matte. Display against final editorial background.
    bg=Image.new('RGB',(args.width,args.height),(235,225,209))
    bg.paste(Image.fromarray(rgba,'RGBA'),(0,0),Image.fromarray(rgba,'RGBA'))
    bg.save(out[:-4]+'-preview.jpg',quality=93)
    print('CGI-first internal reference:',out,'seconds',round(time.monotonic()-started,2))
if __name__=='__main__': main()