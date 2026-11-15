"""Render an extruded pixel retro-terminal (screen shows `>Y_`) spinning in 3D.
Ray-marched voxel slab, hard edges (no AA), grayscale palette, scanlines, transparent bg."""
import sys, math
import numpy as np
from PIL import Image

OUT = sys.argv[1]
SIZE, CELL = 267, 2.0          # canvas px, px per mask cell
FRAMES, DUR, TILT = 120, 20, math.radians(14)
DEPTH = 22                      # extrusion thickness in cells

# ---- mask (labels: 0 empty, 1 body, 2 screen, 3 glyph, 4 led) -------------------
W, H = 92, 82
M = np.zeros((H, W), np.uint8)
def rect(x0, y0, x1, y1, v, cut=0):
    for y in range(y0, y1 + 1):
        d = min(y - y0, y1 - y)
        c = max(0, cut - d)
        M[y, x0 + c:x1 + 1 - c] = v
rect(0, 0, 91, 65, 1, cut=3)            # monitor body
rect(7, 7, 84, 56, 2, cut=2)            # screen
rect(79, 59, 83, 61, 4)                 # power led
rect(38, 66, 53, 73, 1)                 # neck
rect(22, 74, 69, 81, 1, cut=2)          # base
FONT = {'>': ["10000","01000","00100","00010","00100","01000","10000"],
        'Y': ["10001","10001","01010","00100","00100","00100","00100"],
        '_': ["00000","00000","00000","00000","00000","00000","11111"]}
GS = 3
def glyph(ch, gx, gy, v=3):
    for r, row in enumerate(FONT[ch]):
        for c, b in enumerate(row):
            if b == '1':
                M[gy + r*GS: gy + (r+1)*GS, gx + c*GS: gx + (c+1)*GS] = v
text_w = 3*5*GS + 2*4
gx0, gy0 = 7 + (78 - text_w)//2, 7 + (50 - 7*GS)//2
glyph('>', gx0, gy0); glyph('Y', gx0 + 5*GS + 4, gy0)
CURSOR = (gx0 + 2*(5*GS + 4), gy0)
M_on = M.copy(); glyph('_', *CURSOR); M_on, M = M, M_on   # M_on has cursor
SOLID = M > 0

# back face decoration: vent slits
BACK = np.where(SOLID, 1, 0).astype(np.uint8)
for y in range(18, 46, 5):
    BACK[y:y+2, 22:70] = 2

# ---- palette ----------------------------------------------------------------------
# keys: cap_hi, cap_lo (scanline), scr_hi, scr_lo, side_hi, side_lo
THEMES = {
  'dark':  dict(cap=(240, 222), scr=(34, 26), side=(58, 46), led=(150, 150)),
  'light': dict(cap=(14, 34),   scr=(226, 214), side=(196, 184), led=(110, 110)),
}

def render(theta, theme, cursor):
    mask = M_on if cursor else M
    t = THEMES[theme]
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    sx = (xs + 0.5 - SIZE/2) / CELL
    sy = (ys + 0.5 - SIZE/2 + 4) / CELL
    sx, sy = sx.ravel(), sy.ravel()
    cy, sy_ = math.cos(theta), math.sin(theta)
    ct, st = math.cos(TILT), math.sin(TILT)
    # world = Rx(tilt) * Ry(theta) * obj ;  obj = Ry^T Rx^T world
    def to_obj(wx, wy, wz):
        # Rx^T
        x1 = wx; y1 = ct*wy + st*wz; z1 = -st*wy + ct*wz
        # Ry^T
        return cy*x1 - sy_*z1, y1, sy_*x1 + cy*z1
    n = sx.size
    hit = np.zeros(n, bool); shade = np.zeros(n, np.uint8)
    R, step = 62.0, 0.2
    prev_in_z = None; prev_in_xy = None
    for tz in np.arange(R, -R, -step):
        ox, oy, oz = to_obj(sx, sy, np.full(n, tz))
        ix = np.floor(ox + W/2).astype(int); iy = np.floor(oy + H/2).astype(int)
        inb = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
        ixc, iyc = np.clip(ix, 0, W-1), np.clip(iy, 0, H-1)
        in_xy = inb & SOLID[iyc, ixc]
        in_z = np.abs(oz) <= DEPTH/2
        inside = in_xy & in_z & ~hit
        if prev_in_z is not None and inside.any():
            cap = inside & ~prev_in_z          # entered through front/back face
            front = cap & (oz > 0)
            back = cap & (oz <= 0)
            side = inside & ~cap
            lab = mask[iyc, ixc]
            shade[front & (lab == 1)] = 1
            shade[front & (lab == 3)] = 1
            shade[front & (lab == 2)] = 2
            shade[front & (lab == 4)] = 4
            bl = BACK[iyc, ixc]
            shade[back & (bl == 1)] = 1
            shade[back & (bl == 2)] = 2
            shade[side] = 3
            hit |= inside
        prev_in_z = in_z
    shade = shade.reshape(SIZE, SIZE)
    # palette indices: 0 transparent; 1/2 cap; 3/4 screen; 5/6 side; 7 led
    out = np.zeros((SIZE, SIZE), np.uint8)
    odd = (np.arange(SIZE) % 2 == 1)[:, None]
    for s, (a, b) in {1: (1, 2), 2: (3, 4), 3: (5, 6), 4: (7, 7)}.items():
        out[(shade == s) & ~odd] = a
        out[(shade == s) & odd] = b
    return out

def build(theme):
    t = THEMES[theme]
    grays = [0, t['cap'][0], t['cap'][1], t['scr'][0], t['scr'][1], t['side'][0], t['side'][1], t['led'][0]]
    pal = []
    for g in grays: pal += [g, g, g]
    pal += [0, 0, 0] * (256 - len(grays))
    frames = []
    for i in range(FRAMES):
        th = 2*math.pi*i/FRAMES
        cur = (i // 30) % 2 == 0
        im = Image.fromarray(render(th, theme, cur), 'P'); im.putpalette(pal)
        im.info['transparency'] = 0
        frames.append(im)
    return frames

theme = sys.argv[2]
fr = build(theme)
fr[0].save(OUT, save_all=True, append_images=fr[1:], duration=DUR, loop=0,
           disposal=2, transparency=0, optimize=False, background=0)
print('saved', OUT)
