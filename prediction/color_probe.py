"""
PROTOTYPE: extract Ind 1-5 / Pos / Extreme arrow-cell STATES from PDF cell colors.
Validated that pdfplumber exposes per-cell fill colors. This maps fill RGB -> state.
Extend by binding each colored rect to its column via x-position, like parse_mm does.
"""
import pdfplumber, sys

# Observed fills (RGB 0-1). Tune by sampling more cells.
GREEN = (0.776, 0.878, 0.706)   # bullish
BLUE  = (0.867, 0.922, 0.969)   # neutral / light
HEADER= (0.357, 0.608, 0.835)   # header band

def classify(rgb):
    if rgb is None: return 'none'
    if isinstance(rgb, (int, float)):      # grayscale scalar
        v = float(rgb)
        return 'neutral' if v > 0.9 else ('bear' if v < 0.1 else 'other')
    if len(rgb) == 1:
        v = float(rgb[0])
        return 'neutral' if v > 0.9 else ('bear' if v < 0.1 else 'other')
    r, g, b = rgb[:3]
    # crude: green if g dominant & r moderate; red if r dominant; blue if b dominant
    if g > r and g > b and r < 0.85: return 'bull'
    if r > g and r > b: return 'bear'
    if b >= g and b > r: return 'neutral'
    return 'other'

if __name__=='__main__':
    f=sys.argv[1]
    with pdfplumber.open(f) as pdf:
        p=pdf.pages[0]
        from collections import Counter
        c=Counter(classify(r.get('non_stroking_color')) for r in p.rects)
        print('cell-state histogram page1:',dict(c))
