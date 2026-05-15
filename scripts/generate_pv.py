"""
AI企業OS — PV動画生成スクリプト
出力: /workspaces/KATSUYA1225/static/pv.mp4  (60秒 / 1280x720 / 30fps)
"""

import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageSequenceClip

# ── 設定 ────────────────────────────────────────────
W, H = 1280, 720
FPS = 30
FONT_PATH = "/tmp/NotoSansJP.otf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
OUTPUT = "/workspaces/KATSUYA1225/static/pv.mp4"

# カラーパレット
BG       = (3, 10, 20)
CYAN     = (0, 212, 255)
VIOLET   = (124, 58, 237)
PINK     = (232, 121, 249)
AMBER    = (245, 158, 11)
WHITE    = (240, 244, 255)
GRAY     = (136, 153, 187)
DARKGRAY = (68, 85, 119)

random.seed(42)

def font(size, bold=False, mono=False):
    try:
        if mono:
            return ImageFont.truetype(FONT_MONO, size)
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def lerp(a, b, t):
    return a + (b - a) * t

def ease_out(t):
    return 1 - (1 - t) ** 3

def ease_in_out(t):
    return t * t * (3 - 2 * t)

def alpha_composite(base, overlay, alpha):
    """overlay colorをalpha合成"""
    return tuple(int(b * (1 - alpha) + o * alpha) for b, o in zip(base, overlay))

def gradient_text_color(t):
    """cyan→violet→pink のグラデーション（t: 0-1）"""
    if t < 0.5:
        t2 = t / 0.5
        return tuple(int(lerp(a, b, t2)) for a, b in zip(CYAN, VIOLET))
    else:
        t2 = (t - 0.5) / 0.5
        return tuple(int(lerp(a, b, t2)) for a, b in zip(VIOLET, PINK))

# ── パーティクルシステム ─────────────────────────────
class Particle:
    def __init__(self):
        self.x = random.uniform(0, W)
        self.y = random.uniform(0, H)
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-0.4, 0.4)
        self.hub = random.random() < 0.07
        self.r = random.uniform(2.5, 4.5) if self.hub else random.uniform(1.0, 2.2)
        col_t = random.random()
        if col_t < 0.5:
            self.col = CYAN
        elif col_t < 0.78:
            self.col = VIOLET
        else:
            self.col = PINK
        self.a = random.uniform(0.35, 0.85)
        self.ph = random.uniform(0, math.pi * 2)

    def update(self):
        self.x = (self.x + self.vx) % W
        self.y = (self.y + self.vy) % H
        self.ph += 0.025

    def draw(self, draw):
        pulse = 1 + 0.2 * math.sin(self.ph) if self.hub else 1.0
        r = self.r * pulse
        a = int(self.a * 255)
        col = self.col + (a,)
        draw.ellipse([self.x - r, self.y - r, self.x + r, self.y + r], fill=col)

particles = [Particle() for _ in range(120)]

def draw_network(img_array, t_global):
    """パーティクルネットワーク背景"""
    for p in particles:
        p.update()

    # PillowのRGBA画像に描画
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    MD = 110
    for i, a in enumerate(particles):
        for b in particles[i+1:]:
            dx, dy = a.x - b.x, a.y - b.y
            d = math.sqrt(dx*dx + dy*dy)
            if d < MD:
                op = int((1 - d/MD) * (180 if a.hub or b.hub else 55))
                col = CYAN if (a.hub or b.hub) else (100, 140, 220)
                draw.line([a.x, a.y, b.x, b.y], fill=col + (op,), width=1)

    for p in particles:
        p.draw(draw)

    bg = Image.fromarray(img_array, "RGB").convert("RGBA")
    bg = Image.alpha_composite(bg, overlay)
    return np.array(bg.convert("RGB"))

# ── テキスト描画ヘルパー ─────────────────────────────
def draw_centered_text(draw, text, y, size, color=WHITE, shadow=True):
    fnt = font(size)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    if shadow:
        draw.text((x+2, y+2), text, font=fnt, fill=(0, 0, 0, 120))
    draw.text((x, y), text, font=fnt, fill=color)
    return tw

def draw_gradient_text(img, text, y, size):
    """文字ごとにグラデーション色をつける"""
    fnt = font(size, bold=True)
    draw_tmp = ImageDraw.Draw(img)
    bbox = draw_tmp.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2

    # 1文字ずつ描画
    cx = x
    for i, ch in enumerate(text):
        t = i / max(len(text) - 1, 1)
        col = gradient_text_color(t)
        draw_tmp.text((cx, y), ch, font=fnt, fill=col)
        cb = draw_tmp.textbbox((cx, 0), ch, font=fnt)
        cx += cb[2] - cb[0]

def draw_grid(draw, alpha=30):
    """背景グリッド"""
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=(0, 212, 255, alpha), width=1)
    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=(0, 212, 255, alpha), width=1)

def draw_scan_line(draw, t):
    """スキャンライン演出"""
    y = int((t % 1.0) * H)
    draw.line([(0, y), (W, y)], fill=(0, 212, 255, 25), width=2)

def draw_corner_hud(draw, t):
    """コーナーのHUD装飾"""
    size = 20
    col = CYAN + (100,)
    # 左上
    draw.line([(20, 20), (20+size, 20)], fill=col, width=2)
    draw.line([(20, 20), (20, 20+size)], fill=col, width=2)
    # 右上
    draw.line([(W-20, 20), (W-20-size, 20)], fill=col, width=2)
    draw.line([(W-20, 20), (W-20, 20+size)], fill=col, width=2)
    # 左下
    draw.line([(20, H-20), (20+size, H-20)], fill=col, width=2)
    draw.line([(20, H-20), (20, H-20-size)], fill=col, width=2)
    # 右下
    draw.line([(W-20, H-20), (W-20-size, H-20)], fill=col, width=2)
    draw.line([(W-20, H-20), (W-20, H-20-size)], fill=col, width=2)

    # タイムコード
    fnt = font(14, mono=True)
    tc = f"AI企業OS · PV · {int(t*60):02d}:{int((t*60%1)*60):02d}"
    draw.text((W-280, H-36), tc, font=fnt, fill=DARKGRAY + (200,))

# ── シーン定義 ──────────────────────────────────────

def scene_00_intro(t):
    """0-4s: タイトル登場"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    # グリッド
    grid_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grid_ov)
    draw_grid(gd, alpha=int(20 * min(t/2, 1)))
    img = Image.alpha_composite(img, grid_ov)
    draw = ImageDraw.Draw(img)

    # パーティクル
    net_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    net_draw = ImageDraw.Draw(net_ov)
    for p in particles:
        p.update()
        p.draw(net_draw)
    img = Image.alpha_composite(img, net_ov)
    draw = ImageDraw.Draw(img)

    # キャッチコピー フェードイン
    a1 = ease_out(min(t / 1.5, 1))
    fnt = font(28)
    q = "あなたの会社に、AI経営チームがいたら——"
    bbox = draw.textbbox((0,0), q, font=fnt)
    tw = bbox[2]-bbox[0]
    x = (W - tw)//2
    draw.text((x, 240), q, font=fnt, fill=(*GRAY, int(220*a1)))

    # ロゴ
    a2 = ease_out(max(0, (t-1.0)/1.5))
    draw_centered_text(draw, "AI企業OS", 300, 96, color=(*WHITE, int(255*a2)))

    a3 = ease_out(max(0, (t-2.0)/1.2))
    fnt2 = font(22)
    sub = "Future Share Collective"
    bbox2 = draw.textbbox((0,0), sub, font=fnt2)
    x2 = (W - (bbox2[2]-bbox2[0]))//2
    draw.text((x2, 420), sub, font=fnt2, fill=(*CYAN, int(180*a3)))

    draw_corner_hud(draw, t/60)
    draw_scan_line(draw, t * 0.3)
    return np.array(img.convert("RGB"))


def scene_01_pain(t):
    """4-14s: 課題提示 4つのPAIN"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    grid_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grid_ov)
    draw_grid(gd, 15)
    img = Image.alpha_composite(img, grid_ov)
    draw = ImageDraw.Draw(img)

    # ヘッダー
    a0 = ease_out(min(t/0.8, 1))
    fnt_label = font(16, mono=True)
    draw.text((W//2 - 80, 60), "THE PROBLEM", font=fnt_label, fill=(*CYAN, int(200*a0)))
    draw_centered_text(draw, "「全部自分でやる」の限界", 90, 44, color=(*WHITE, int(255*a0)))

    pains = [
        ("PAIN 01", "経営コンサルは高すぎる",   "¥50万〜/月、手が届かない"),
        ("PAIN 02", "意思決定が遅くなる",        "情報収集〜実行まで数週間"),
        ("PAIN 03", "全領域の専門家は雇えない",  "財務・法務・HR・マーケ…"),
        ("PAIN 04", "AIツールがバラバラ",         "連携しない、「組織」にならない"),
    ]

    positions = [(80, 220), (680, 220), (80, 430), (680, 430)]
    for i, ((px, py), (num, title, desc)) in enumerate(zip(positions, pains)):
        delay = 0.5 + i * 1.8
        a = ease_out(max(0, min((t - delay) / 1.0, 1)))

        # カード背景
        card_ov = Image.new("RGBA", (W, H), (0,0,0,0))
        cd = ImageDraw.Draw(card_ov)
        cd.rounded_rectangle([px, py, px+520, py+160], radius=10,
                              fill=(8, 15, 32, int(200*a)),
                              outline=(*VIOLET, int(60*a)), width=1)
        img = Image.alpha_composite(img, card_ov)
        draw = ImageDraw.Draw(img)

        # テキスト
        fnt_num = font(13, mono=True)
        fnt_title = font(22)
        fnt_desc = font(17)
        draw.text((px+20, py+18), num, font=fnt_num, fill=(*PINK, int(200*a)))
        draw.text((px+20, py+44), title, font=fnt_title, fill=(*WHITE, int(255*a)))
        draw.text((px+20, py+88), desc, font=fnt_desc, fill=(*GRAY, int(200*a)))

    draw_corner_hud(draw, (t+4)/60)
    draw_scan_line(draw, (t+4) * 0.3)
    return np.array(img.convert("RGB"))


def scene_02_solution(t):
    """14-28s: AI企業OS 組織図アニメーション"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    grid_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grid_ov)
    draw_grid(gd, 12)
    img = Image.alpha_composite(img, grid_ov)
    draw = ImageDraw.Draw(img)

    a0 = ease_out(min(t/1.0, 1))
    fnt_label = font(16, mono=True)
    draw.text((W//2-110, 40), "THE SOLUTION", font=fnt_label, fill=(*CYAN, int(200*a0)))

    # AI社長ノード
    cx, cy = W//2, 155
    a1 = ease_out(min(t/1.2, 1))

    # 光輪
    glow_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd2 = ImageDraw.Draw(glow_ov)
    gr = 70 + int(8 * math.sin(t * 2))
    gd2.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*CYAN, int(20*a1)))
    img = Image.alpha_composite(img, glow_ov)
    draw = ImageDraw.Draw(img)

    box_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    bd = ImageDraw.Draw(box_ov)
    bd.rounded_rectangle([cx-170, cy-36, cx+170, cy+36], radius=8,
                          fill=(0, 212, 255, int(18*a1)),
                          outline=(*CYAN, int(200*a1)), width=2)
    img = Image.alpha_composite(img, box_ov)
    draw = ImageDraw.Draw(img)

    fnt_pres = font(24)
    draw.text((cx-145, cy-15), "👑 AI社長（President Agent）", font=fnt_pres, fill=(*CYAN, int(255*a1)))

    # 部門ノード
    depts = [
        ("📊", "マーケ",  CYAN),
        ("💼", "営業",    VIOLET),
        ("💰", "財務",    CYAN),
        ("⚖️", "法務",   PINK),
        ("🎯", "戦略",    AMBER),
        ("📱", "SNS広報", VIOLET),
    ]
    n = len(depts)
    dept_y = 360
    spacing = W // (n + 1)

    for i, (icon, name, col) in enumerate(depts):
        delay = 1.0 + i * 0.7
        a2 = ease_out(max(0, min((t - delay) / 0.8, 1)))
        dx = spacing * (i + 1)
        dy = dept_y

        # 接続線（AI社長 → 部門）
        line_ov = Image.new("RGBA", (W, H), (0,0,0,0))
        ld = ImageDraw.Draw(line_ov)
        # アニメーション付き線
        prog = max(0, min((t - delay + 0.2) / 0.5, 1))
        ex = int(cx + (dx - cx) * prog)
        ey = int(cy + 36 + (dy - 40 - (cy + 36)) * prog)
        ld.line([(cx, cy+36), (ex, ey)],
                fill=(*col, int(120*a2)), width=2)
        # 電流パルス
        if prog > 0.5:
            pt = (t * 2.5 + i * 0.4) % 1.0
            px2 = int(cx + (dx - cx) * pt)
            py2 = int(cy + 36 + (dy - 40 - (cy + 36)) * pt)
            ld.ellipse([px2-5, py2-5, px2+5, py2+5], fill=(*col, 200))
        img = Image.alpha_composite(img, line_ov)
        draw = ImageDraw.Draw(img)

        # 部門ボックス
        dep_ov = Image.new("RGBA", (W, H), (0,0,0,0))
        dd = ImageDraw.Draw(dep_ov)
        dd.rounded_rectangle([dx-54, dy-44, dx+54, dy+44], radius=8,
                              fill=(*col, int(16*a2)),
                              outline=(*col, int(140*a2)), width=1)
        img = Image.alpha_composite(img, dep_ov)
        draw = ImageDraw.Draw(img)

        fnt_icon = font(28)
        fnt_name = font(18)
        draw.text((dx-14, dy-36), icon, font=fnt_icon, fill=(*WHITE, int(240*a2)))
        bbox_n = draw.textbbox((0,0), name, font=fnt_name)
        nw = bbox_n[2]-bbox_n[0]
        draw.text((dx - nw//2, dy+10), name, font=fnt_name, fill=(*col, int(220*a2)))

    # 下部メッセージ
    a3 = ease_out(max(0, min((t - 8) / 1.5, 1)))
    draw_centered_text(draw, "一言の指示で、6部門が並列実行する", 540, 30, color=(*WHITE, int(200*a3)))
    draw_centered_text(draw, "AI社長が組織をリアルタイムで指揮", 584, 22, color=(*GRAY, int(160*a3)))

    draw_corner_hud(draw, (t+14)/60)
    draw_scan_line(draw, (t+14) * 0.3)
    return np.array(img.convert("RGB"))


def scene_03_terminal(t):
    """28-42s: ターミナルデモ"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    # 暗めグリッド
    grid_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grid_ov)
    draw_grid(gd, 8)
    img = Image.alpha_composite(img, grid_ov)
    draw = ImageDraw.Draw(img)

    a0 = ease_out(min(t/0.8, 1))
    fnt_label = font(16, mono=True)
    draw.text((W//2-70, 30), "LIVE DEMO", font=fnt_label, fill=(*CYAN, int(200*a0)))
    draw_centered_text(draw, "一言で、38秒後に経営判断が出る", 60, 36, color=(*WHITE, int(255*a0)))

    # ターミナルウィンドウ
    tx, ty, tw_box, th_box = 80, 120, W-160, 440
    term_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    td = ImageDraw.Draw(term_ov)
    td.rounded_rectangle([tx, ty, tx+tw_box, ty+th_box], radius=12,
                          fill=(1, 8, 16, 230),
                          outline=(*CYAN, 80), width=1)
    # ターミナルバー
    td.rounded_rectangle([tx, ty, tx+tw_box, ty+36], radius=12,
                          fill=(*CYAN, 15))
    # ドット
    for xi, col in enumerate([(255,95,87),(255,189,46),(40,200,64)]):
        td.ellipse([tx+14+xi*20-6, ty+12, tx+14+xi*20+6, ty+24], fill=col+(220,))
    img = Image.alpha_composite(img, term_ov)
    draw = ImageDraw.Draw(img)

    fnt_mono = font(15, mono=True)
    fnt_m = font(18, mono=True)
    label_txt = "AI企業OS — Terminal"
    draw.text((tx+80, ty+10), label_txt, font=fnt_mono, fill=(*GRAY, 180))

    lines = [
        (0.3,  "prompt", "CEO > 新規事業を立案して。ターゲットは30代の個人事業主。"),
        (1.4,  "agent",  "👑 AI社長 → 6部門に指示を分配中..."),
        (2.5,  "dept",   "📊 マーケ  → 市場調査・ペルソナ分析  実行中"),
        (3.5,  "dept",   "💼 営業    → 競合分析・セールスシナリオ  実行中"),
        (4.5,  "dept",   "💰 財務    → 収益モデル・ROIシミュレーション  実行中"),
        (5.5,  "dept",   "🎯 戦略    → GTM戦略・差別化ポイント  実行中"),
        (6.5,  "dept",   "📱 SNS広報 → バズるコンテンツ戦略  実行中"),
        (8.5,  "ok",     "✓  完了 — 処理時間  38秒"),
        (9.5,  "agent",  "👑 AI社長 → 統合レポートを生成しました。"),
        (10.5, "result", "   戦略書・財務計画・マーケプラン  即実行可能"),
    ]

    col_map = {
        "prompt": (*WHITE, 220),
        "agent":  (*CYAN, 230),
        "dept":   (*VIOLET, 200),
        "ok":     (16, 200, 120, 240),
        "result": (*AMBER, 220),
    }

    for i, (delay, kind, text) in enumerate(lines):
        if t < delay:
            break
        a_line = ease_out(min((t - delay) / 0.4, 1))
        lx = tx + 24
        ly = ty + 50 + i * 36
        draw.text((lx, ly), text, font=fnt_m, fill=(*col_map[kind][:3], int(col_map[kind][3]*a_line)))

        # カーソル（最後の行）
        if i == len([l for l in lines if t >= l[0]]) - 1 and t < 12:
            bbox = draw.textbbox((lx,0), text, font=fnt_m)
            cx2 = lx + (bbox[2]-bbox[0]) + 4
            if int(t*4) % 2 == 0:
                draw.rectangle([cx2, ly+2, cx2+8, ly+20], fill=(*CYAN, 200))

    draw_corner_hud(draw, (t+28)/60)
    draw_scan_line(draw, (t+28) * 0.3)
    return np.array(img.convert("RGB"))


def scene_04_pricing(t):
    """42-52s: 料金・価値"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    grid_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grid_ov)
    draw_grid(gd, 10)
    img = Image.alpha_composite(img, grid_ov)
    draw = ImageDraw.Draw(img)

    a0 = ease_out(min(t/0.8, 1))
    draw_centered_text(draw, "経営チームを、圧倒的コストで。", 50, 44, color=(*WHITE, int(255*a0)))

    # 比較カード
    cards = [
        ("従来の経営チーム", "¥250万/月", "役員・コンサル・専門家", GRAY, DARKGRAY),
        ("AI企業OS Growth", "¥29,800/月", "23名のAI専門エージェント", CYAN, VIOLET),
    ]
    for i, (title, price, desc, col, outline_col) in enumerate(cards):
        delay = 0.5 + i * 1.5
        a = ease_out(max(0, min((t-delay)/0.9, 1)))
        cx2 = 220 + i * 560
        cy2 = 300

        c_ov = Image.new("RGBA", (W, H), (0,0,0,0))
        cd2 = ImageDraw.Draw(c_ov)
        cd2.rounded_rectangle([cx2-180, cy2-100, cx2+180, cy2+100], radius=14,
                               fill=(8, 15, 32, int(210*a)),
                               outline=(*col, int(150*a)), width=2)
        if i == 1:  # featured glow
            cd2.rounded_rectangle([cx2-184, cy2-104, cx2+184, cy2+104], radius=16,
                                   fill=(0,0,0,0), outline=(*CYAN, int(40*a)), width=4)
        img = Image.alpha_composite(img, c_ov)
        draw = ImageDraw.Draw(img)

        fnt_t = font(20)
        fnt_p = font(44)
        fnt_d = font(18)
        bbox_t = draw.textbbox((0,0), title, font=fnt_t)
        draw.text((cx2-(bbox_t[2]-bbox_t[0])//2, cy2-85), title, font=fnt_t, fill=(*GRAY, int(200*a)))
        bbox_p = draw.textbbox((0,0), price, font=fnt_p)
        col_p = col if i==1 else GRAY
        draw.text((cx2-(bbox_p[2]-bbox_p[0])//2, cy2-40), price, font=fnt_p, fill=(*col_p, int(255*a)))
        bbox_d = draw.textbbox((0,0), desc, font=fnt_d)
        draw.text((cx2-(bbox_d[2]-bbox_d[0])//2, cy2+52), desc, font=fnt_d, fill=(*col, int(180*a)))

    # VS
    a_vs = ease_out(max(0, min((t-2.0)/0.5, 1)))
    draw_centered_text(draw, "VS", 270, 48, color=(*PINK, int(220*a_vs)))

    # 削減率
    a3 = ease_out(max(0, min((t-4.5)/1.0, 1)))
    draw_centered_text(draw, "コストを 1/100 以下に。意思決定速度は 100倍以上に。", 490, 26, color=(*AMBER, int(220*a3)))

    # 月100万への言及
    a4 = ease_out(max(0, min((t-6.0)/1.0, 1)))
    draw_centered_text(draw, "34社の契約で、月100万円のMRRを達成できる。", 535, 22, color=(*GRAY, int(180*a4)))

    draw_corner_hud(draw, (t+42)/60)
    draw_scan_line(draw, (t+42) * 0.3)
    return np.array(img.convert("RGB"))


def scene_05_cta(t):
    """52-60s: CTA・先行登録"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    # 放射状グロー
    glow_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow_ov)
    gr = 400 + int(20 * math.sin(t * 1.5))
    gd.ellipse([W//2-gr, H//2-gr//2, W//2+gr, H//2+gr//2],
               fill=(*CYAN, 8))
    gd.ellipse([W//2-200, H//2-100, W//2+200, H//2+100],
               fill=(*VIOLET, 12))
    img = Image.alpha_composite(img, glow_ov)
    draw = ImageDraw.Draw(img)

    grid_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    gd2 = ImageDraw.Draw(grid_ov)
    draw_grid(gd2, 18)
    img = Image.alpha_composite(img, grid_ov)
    draw = ImageDraw.Draw(img)

    # パーティクル
    net_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    nd = ImageDraw.Draw(net_ov)
    for p in particles:
        p.update()
        p.draw(nd)
    img = Image.alpha_composite(img, net_ov)
    draw = ImageDraw.Draw(img)

    a0 = ease_out(min(t/1.2, 1))
    a1 = ease_out(max(0, min((t-1.0)/1.0, 1)))
    a2 = ease_out(max(0, min((t-2.2)/0.8, 1)))
    a3 = ease_out(max(0, min((t-3.5)/1.0, 1)))

    draw_centered_text(draw, "AI経営の最前線へ。", 170, 62, color=(*WHITE, int(255*a0)))
    draw_gradient_text(img, "先着30社 — 先行登録受付中", 264, 40)
    draw = ImageDraw.Draw(img)

    # 特典
    benefits = ["✓  初月50%オフ  （最大 ¥14,900 割引）",
                "✓  セットアップ完全サポート  無料",
                "✓  あなたのフィードバックが製品に反映される"]
    for i, b in enumerate(benefits):
        ab = ease_out(max(0, min((t-1.5-i*0.4)/0.7, 1)))
        draw_centered_text(draw, b, 340 + i*44, 20, color=(*GRAY, int(180*ab)))

    # URL ボタン風
    btn_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    bd = ImageDraw.Draw(btn_ov)
    bx, by, bw, bh = W//2-200, 540, 400, 56
    bd.rounded_rectangle([bx, by, bx+bw, by+bh], radius=10,
                          fill=(*CYAN, int(220*a2)),
                          outline=(*CYAN, int(80*a2)), width=1)
    img = Image.alpha_composite(img, btn_ov)
    draw = ImageDraw.Draw(img)
    fnt_btn = font(22)
    draw.text((bx+50, by+14), "your-domain.com/register", font=fnt_btn, fill=(3, 10, 20, int(255*a2)))

    # ロゴ
    draw_centered_text(draw, "AI企業OS · Future Share Collective", 622, 18, color=(*GRAY, int(160*a3)))

    draw_corner_hud(draw, (t+52)/60)
    draw_scan_line(draw, (t+52) * 0.3)
    return np.array(img.convert("RGB"))


# ── シーンタイムライン ───────────────────────────────
SCENES = [
    (0,  4,  scene_00_intro),
    (4,  14, scene_01_pain),
    (14, 28, scene_02_solution),
    (28, 42, scene_03_terminal),
    (42, 52, scene_04_pricing),
    (52, 60, scene_05_cta),
]

def make_frame(t_sec):
    for start, end, fn in SCENES:
        if start <= t_sec < end:
            local_t = t_sec - start
            return fn(local_t)
    return scene_05_cta(t_sec - 52)


# ── レンダリング ────────────────────────────────────
if __name__ == "__main__":
    DURATION = 60
    total_frames = DURATION * FPS
    print(f"レンダリング開始: {total_frames}フレーム ({DURATION}秒 @ {FPS}fps)")

    frames = []
    for fi in range(total_frames):
        t = fi / FPS
        if fi % (FPS * 5) == 0:
            print(f"  {fi//FPS}秒目 / {DURATION}秒...")
        frames.append(make_frame(t))

    print("動画を書き出し中...")
    clip = ImageSequenceClip(frames, fps=FPS)
    clip.write_videofile(OUTPUT, codec="libx264", fps=FPS,
                         bitrate="4000k", logger=None)
    print(f"完成: {OUTPUT}")
