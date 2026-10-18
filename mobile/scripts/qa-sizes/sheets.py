# sheets.py <shots dir> [labels...] — one image per pair of steps: rows = steps, columns = devices.
# Writes <shots dir>/sheets/sheet_NN.jpg.
import os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = sys.argv[1]
out = os.path.join(ROOT, 'sheets'); os.makedirs(out, exist_ok=True)
labels = sys.argv[2:] or ['se', 'mini', 'e17', 'pro', 'max']
names = {'se': 'SE 375×667', 'mini': '13 mini 375×812', 'e17': '17e 390×844', 'pro': '17 Pro 402×874', 'max': '17 Pro Max 440×956'}
steps = sorted({f for l in labels for f in os.listdir(os.path.join(ROOT, l)) if f.endswith('.png')})
H = 620; PAD = 14; TOP = 34
try:
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 18)
except Exception:
    font = ImageFont.load_default()
def tile(path):
    if not os.path.exists(path):
        im = Image.new('RGB', (300, H), (240, 200, 200)); ImageDraw.Draw(im).text((20, H // 2), 'missing', fill='black', font=font); return im
    im = Image.open(path).convert('RGB'); w = round(im.width * H / im.height)
    return im.resize((w, H), Image.LANCZOS)
for k in range(0, len(steps), 2):
    rows = steps[k:k + 2]
    tiles = [[tile(os.path.join(ROOT, l, st)) for l in labels] for st in rows]
    W = max(sum(t.width for t in r) + PAD * (len(r) + 1) for r in tiles)
    img = Image.new('RGB', (W, (H + TOP + PAD) * len(rows) + PAD), 'white'); d = ImageDraw.Draw(img)
    y = PAD
    for st, r in zip(rows, tiles):
        x = PAD
        for l, t in zip(labels, r):
            d.text((x, y), f"{st[:-4]} · {names.get(l, l)}", fill='black', font=font)
            img.paste(t, (x, y + TOP)); x += t.width + PAD
        y += H + TOP + PAD
    img.save(os.path.join(out, f"sheet_{k // 2 + 1:02d}.jpg"), quality=82)
print(len(steps), 'steps')
