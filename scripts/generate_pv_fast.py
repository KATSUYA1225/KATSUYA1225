"""
AI企業OS — PV動画 高速生成版
出力: /workspaces/KATSUYA1225/static/pv.mp4
解像度: 960x540 / 24fps / 30秒
"""

import math, random, numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageSequenceClip

W, H = 960, 540
FPS = 24
DURATION = 30
OUTPUT = "/workspaces/KATSUYA1225/static/pv.mp4"
FONT = "/tmp/NotoSansJP.otf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

BG=(3,10,20); CYAN=(0,212,255); VIO=(124,58,237); PINK=(232,121,249)
AMB=(245,158,11); WHITE=(240,244,255); GRAY=(136,153,187); DG=(68,85,119)

random.seed(7)

def fnt(size, mono=False):
    try:
        return ImageFont.truetype(MONO if mono else FONT, size)
    except Exception:
        return ImageFont.load_default()

def eo(t): return 1-(1-min(max(t,0),1))**3

def base_img():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 48):
        d.line([(x,0),(x,H)], fill=(0,50,80), width=1)
    for y in range(0, H, 48):
        d.line([(0,y),(W,y)], fill=(0,50,80), width=1)
    return img

def ctxt(draw, text, y, size, col=WHITE, alpha=255):
    f = fnt(size)
    bb = draw.textbbox((0,0), text, font=f)
    x = (W-(bb[2]-bb[0]))//2
    draw.text((x,y), text, font=f, fill=col+(alpha,))

def gtxt(img, text, y, size):
    """グラデーションテキスト"""
    d = ImageDraw.Draw(img)
    f = fnt(size)
    bb = d.textbbox((0,0), text, font=f)
    x = (W-(bb[2]-bb[0]))//2
    cx = x
    colors = [CYAN, VIO, PINK]
    for i, ch in enumerate(text):
        t2 = i/max(len(text)-1,1)
        idx = t2*(len(colors)-1)
        ci = int(idx); cr = idx-ci
        ci = min(ci, len(colors)-2)
        col = tuple(int(colors[ci][j]*(1-cr)+colors[ci+1][j]*cr) for j in range(3))
        d.text((cx, y), ch, font=f, fill=col+(255,))
        cb = d.textbbox((cx,0), ch, font=f)
        cx += cb[2]-cb[0]

def hud(draw, t):
    f = fnt(13, mono=True)
    draw.text((W-260, H-28), f"AI企業OS · PV · {int(t):02d}s", font=f, fill=DG+(180,))
    sz=14
    c=CYAN+(80,)
    draw.line([(14,14),(14+sz,14)],fill=c,width=2); draw.line([(14,14),(14,14+sz)],fill=c,width=2)
    draw.line([(W-14,14),(W-14-sz,14)],fill=c,width=2); draw.line([(W-14,14),(W-14,14+sz)],fill=c,width=2)


# ─── シーン 0: タイトル (0-5s) ────────────────────────
def s0(lt):
    img = base_img().convert("RGBA")
    d = ImageDraw.Draw(img)
    a1 = eo(lt/1.5)
    a2 = eo((lt-1.5)/1.5)
    a3 = eo((lt-3.0)/1.2)
    f1 = fnt(22); q="あなたの会社に、AI経営チームがいたら——"
    bb=d.textbbox((0,0),q,font=f1); d.text(((W-(bb[2]-bb[0]))//2,180),q,font=f1,fill=GRAY+(int(210*a1),))
    # タイトル
    f2 = fnt(76)
    title="AI企業OS"
    bb2=d.textbbox((0,0),title,font=f2); d.text(((W-(bb2[2]-bb2[0]))//2,220),title,font=f2,fill=WHITE+(int(255*a2),))
    f3 = fnt(20)
    sub="Future Share Collective"
    bb3=d.textbbox((0,0),sub,font=f3); d.text(((W-(bb3[2]-bb3[0]))//2,318),sub,font=f3,fill=CYAN+(int(200*a3),))
    # 軌道リング
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(ov)
    cx2,cy2=W//2,270
    for ri,rcol in enumerate([CYAN,VIO,PINK]):
        r=120+ri*50; op=int(30*a2)
        od.ellipse([cx2-r,cy2-r//3,cx2+r,cy2+r//3],outline=rcol+(op,),width=1)
        angle=lt*(1.2-ri*0.3)*(-1 if ri%2 else 1)
        px3=cx2+int(math.cos(angle)*r); py3=cy2+int(math.sin(angle)*r//3)
        od.ellipse([px3-5,py3-5,px3+5,py3+5],fill=rcol+(int(180*a2),))
    img=Image.alpha_composite(img,ov); d=ImageDraw.Draw(img)
    hud(d, lt)
    return np.array(img.convert("RGB"))


# ─── シーン 1: 課題 (5-12s) ──────────────────────────
def s1(lt):
    img = base_img().convert("RGBA")
    d = ImageDraw.Draw(img)
    a0=eo(lt/0.8)
    f_lbl=fnt(14,mono=True)
    d.text((W//2-60,30),"THE PROBLEM",font=f_lbl,fill=CYAN+(int(190*a0),))
    ctxt(d,"「全部自分でやる」の限界",68,36,WHITE,int(255*a0))
    pains=[
        ("PAIN 01","経営コンサルは高すぎる","¥50万〜/月"),
        ("PAIN 02","意思決定が遅い",    "数週間かかる"),
        ("PAIN 03","専門家が雇えない",   "財務・法務・マーケ…"),
        ("PAIN 04","AIツールがバラバラ", "「組織」にならない"),
    ]
    pos=[(40,130),(510,130),(40,310),(510,310)]
    for i,((px,py),(num,tit,desc)) in enumerate(zip(pos,pains)):
        a=eo((lt-0.4-i*1.1)/0.8)
        ov=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(ov)
        od.rounded_rectangle([px,py,px+390,py+140],radius=8,
                              fill=(8,15,32,int(200*a)),outline=VIO+(int(80*a),),width=1)
        img=Image.alpha_composite(img,ov); d=ImageDraw.Draw(img)
        d.text((px+16,py+14),num,font=fnt(12,mono=True),fill=PINK+(int(200*a),))
        d.text((px+16,py+36),tit,font=fnt(22),fill=WHITE+(int(240*a),))
        d.text((px+16,py+78),desc,font=fnt(18),fill=GRAY+(int(180*a),))
    hud(d,lt+5)
    return np.array(img.convert("RGB"))


# ─── シーン 2: ソリューション (12-20s) ───────────────
def s2(lt):
    img = base_img().convert("RGBA")
    d = ImageDraw.Draw(img)
    a0=eo(lt/0.8)
    f_lbl=fnt(14,mono=True)
    d.text((W//2-90,22),"THE SOLUTION",font=f_lbl,fill=CYAN+(int(190*a0),))
    ctxt(d,"AI社長が、組織を指揮する",52,34,WHITE,int(255*a0))

    cx2,cy2=W//2,148
    a1=eo((lt-0.5)/1.0)
    # AI社長ボックス
    bov=Image.new("RGBA",(W,H),(0,0,0,0)); bd=ImageDraw.Draw(bov)
    glow=50+int(8*math.sin(lt*2))
    bd.ellipse([cx2-glow,cy2-glow//2,cx2+glow,cy2+glow//2],fill=CYAN+(int(15*a1),))
    bd.rounded_rectangle([cx2-200,cy2-28,cx2+200,cy2+28],radius=8,
                          fill=CYAN+(int(18*a1),),outline=CYAN+(int(200*a1),),width=2)
    img=Image.alpha_composite(img,bov); d=ImageDraw.Draw(img)
    f_p=fnt(22); pt="👑 AI社長（President Agent）"
    bb=d.textbbox((0,0),pt,font=f_p); d.text((cx2-(bb[2]-bb[0])//2,cy2-14),pt,font=f_p,fill=CYAN+(int(255*a1),))

    depts=[("📊","マーケ",CYAN),("💼","営業",VIO),("💰","財務",CYAN),
           ("⚖️","法務",PINK),("🎯","戦略",AMB),("📱","SNS",VIO)]
    n=len(depts); sp=W//(n+1)
    dy2=360
    for i,(icon,name,col) in enumerate(depts):
        delay=1.0+i*0.8
        a2=eo((lt-delay)/0.7)
        dx2=sp*(i+1)
        lov=Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lov)
        prog=max(0,min((lt-delay+0.2)/0.5,1))
        ex=int(cx2+(dx2-cx2)*prog); ey=int(cy2+28+(dy2-40-(cy2+28))*prog)
        ld.line([(cx2,cy2+28),(ex,ey)],fill=col+(int(100*a2),),width=2)
        if prog>0.5:
            pt2=(lt*2.5+i*0.5)%1.0
            ppx=int(cx2+(dx2-cx2)*pt2); ppy=int(cy2+28+(dy2-40-(cy2+28))*pt2)
            ld.ellipse([ppx-4,ppy-4,ppx+4,ppy+4],fill=col+(200,))
        dov=Image.new("RGBA",(W,H),(0,0,0,0)); dd=ImageDraw.Draw(dov)
        dov2=Image.alpha_composite(lov,dov)
        img=Image.alpha_composite(Image.alpha_composite(img,lov),dov)
        d=ImageDraw.Draw(img)
        dep_ov=Image.new("RGBA",(W,H),(0,0,0,0)); depd=ImageDraw.Draw(dep_ov)
        depd.rounded_rectangle([dx2-48,dy2-36,dx2+48,dy2+36],radius=8,
                                fill=col+(int(15*a2),),outline=col+(int(130*a2),),width=1)
        img=Image.alpha_composite(img,dep_ov); d=ImageDraw.Draw(img)
        d.text((dx2-12,dy2-28),icon,font=fnt(24),fill=WHITE+(int(230*a2),))
        bb2=d.textbbox((0,0),name,font=fnt(17)); d.text((dx2-(bb2[2]-bb2[0])//2,dy2+10),name,font=fnt(17),fill=col+(int(210*a2),))

    a3=eo((lt-7.0)/1.0)
    ctxt(d,"一言で、6部門が並列実行する",456,24,WHITE,int(200*a3))
    hud(d,lt+12)
    return np.array(img.convert("RGB"))


# ─── シーン 3: ターミナル (20-27s) ───────────────────
def s3(lt):
    img = base_img().convert("RGBA")
    d = ImageDraw.Draw(img)
    a0=eo(lt/0.7)
    ctxt(d,"一言で38秒後に経営判断が出る",28,28,WHITE,int(255*a0))

    tx,ty,tw2,th2=60,65,W-120,390
    tov=Image.new("RGBA",(W,H),(0,0,0,0)); td=ImageDraw.Draw(tov)
    td.rounded_rectangle([tx,ty,tx+tw2,ty+th2],radius=10,fill=(1,8,16,225),outline=CYAN+(70,),width=1)
    td.rounded_rectangle([tx,ty,tx+tw2,ty+32],radius=10,fill=CYAN+(12,))
    for xi,col in enumerate([(255,95,87),(255,189,46),(40,200,64)]):
        td.ellipse([tx+12+xi*18-5,ty+10,tx+12+xi*18+5,ty+20],fill=col+(210,))
    img=Image.alpha_composite(img,tov); d=ImageDraw.Draw(img)
    d.text((tx+70,ty+8),"AI企業OS — Terminal",font=fnt(13,mono=True),fill=GRAY+(160,))

    lines=[
        (0.3,"p","CEO > 新規事業を立案して。ターゲットは30代の個人事業主。"),
        (1.2,"a","👑 AI社長 → 6部門に指示を分配中..."),
        (2.0,"d","📊 マーケ  → 市場調査・ペルソナ分析  実行中"),
        (2.8,"d","💼 営業    → 競合分析・セールスシナリオ  実行中"),
        (3.5,"d","💰 財務    → 収益モデル・ROI  実行中"),
        (4.2,"d","🎯 戦略    → GTM戦略・差別化  実行中"),
        (5.5,"o","✓  完了 — 処理時間  38秒"),
        (6.2,"a","👑 AI社長 → 統合レポート生成完了。即実行可能です。"),
    ]
    cm={"p":(*WHITE,215),"a":(*CYAN,225),"d":(*VIO,195),"o":(16,200,120,235)}
    f_m=fnt(16,mono=True)
    for i,(delay,kind,text) in enumerate(lines):
        if lt<delay: break
        al=eo((lt-delay)/0.4)
        lx=tx+18; ly=ty+44+i*42
        d.text((lx,ly),text,font=f_m,fill=cm[kind][:3]+(int(cm[kind][3]*al),))
    hud(d,lt+20)
    return np.array(img.convert("RGB"))


# ─── シーン 4: CTA (27-30s) ──────────────────────────
def s4(lt):
    img = base_img().convert("RGBA")
    d = ImageDraw.Draw(img)
    # グロー
    gov=Image.new("RGBA",(W,H),(0,0,0,0)); gd2=ImageDraw.Draw(gov)
    gr=300+int(15*math.sin(lt*1.5))
    gd2.ellipse([W//2-gr,H//2-gr//2,W//2+gr,H//2+gr//2],fill=CYAN+(8,))
    img=Image.alpha_composite(img,gov); d=ImageDraw.Draw(img)

    a0=eo(lt/1.0); a1=eo((lt-0.8)/0.8); a2=eo((lt-1.6)/0.8); a3=eo((lt-2.4)/0.7)
    ctxt(d,"AI経営の最前線へ。",100,56,WHITE,int(255*a0))

    img2=img.copy()
    gtxt(img2,"先着30社 — 先行登録受付中",178,32)
    img=img2; d=ImageDraw.Draw(img)

    ctxt(d,"✓  初月50%オフ  (最大 ¥14,900 割引)",248,20,GRAY,int(190*a1))
    ctxt(d,"✓  セットアップ完全サポート  無料",280,20,GRAY,int(190*a1))
    ctxt(d,"✓  正式ローンチ時に最優先でご案内",312,20,GRAY,int(190*a1))

    bov=Image.new("RGBA",(W,H),(0,0,0,0)); bd=ImageDraw.Draw(bov)
    bx,by,bw,bh=W//2-190,368,380,50
    bd.rounded_rectangle([bx,by,bx+bw,by+bh],radius=9,fill=CYAN+(int(230*a2),))
    img=Image.alpha_composite(img,bov); d=ImageDraw.Draw(img)
    f_btn=fnt(20); url="your-domain.com/register"
    bb=d.textbbox((0,0),url,font=f_btn)
    d.text((bx+(bw-(bb[2]-bb[0]))//2,by+12),url,font=f_btn,fill=(3,10,20,int(255*a2)))

    ctxt(d,"AI企業OS · Future Share Collective",450,16,GRAY,int(140*a3))
    hud(d,lt+27)
    return np.array(img.convert("RGB"))


SCENES=[(0,5,s0),(5,12,s1),(12,20,s2),(20,27,s3),(27,30,s4)]

def make_frame(t):
    for s,e,fn in SCENES:
        if s<=t<e:
            return fn(t-s)
    return s4(t-27)

if __name__=="__main__":
    total=DURATION*FPS
    print(f"レンダリング開始: {total}フレーム ({DURATION}秒 @ {FPS}fps) → {OUTPUT}")
    frames=[]
    for fi in range(total):
        if fi%(FPS*5)==0: print(f"  {fi//FPS}秒目 / {DURATION}秒...")
        frames.append(make_frame(fi/FPS))
    print("書き出し中...")
    ImageSequenceClip(frames, fps=FPS).write_videofile(
        OUTPUT, codec="libx264", fps=FPS, bitrate="3000k", logger=None)
    print(f"✓ 完成: {OUTPUT}")
