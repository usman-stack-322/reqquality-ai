"""One-time migration of legacy visual colors to shared semantic theme tokens."""
from pathlib import Path
import colorsys
import re

def token(value, prop):
    if value.startswith(('rgb',)):
        return 'var(--shadow-color)' if 'shadow' in prop else 'var(--overlay)' if prop.startswith('background') else 'var(--line)'
    if value in ('white', 'black'):
        value = '#ffffff' if value == 'white' else '#000000'
    value = value.lower()
    raw = value[1:]
    if len(raw) in (3, 4): raw = ''.join(c * 2 for c in raw)
    r, g, b = [int(raw[i:i+2], 16) / 255 for i in (0, 2, 4)]
    h, light, sat = colorsys.rgb_to_hls(r, g, b)
    accent = value in ('#173f35', '#285b4a', '#3f765f', '#0f766e', '#115e59', '#0d9488', '#245b50', '#35654d')
    semantic = 'danger' if sat > .22 and (h < .055 or h > .91) else 'warning' if sat > .3 and .055 <= h < .18 else 'success' if sat > .24 and .19 < h < .46 else None
    if 'shadow' in prop: return 'var(--shadow-color)'
    if prop.startswith(('border', 'outline')):
        return f'var(--{semantic})' if semantic and light < .65 else 'var(--accent)' if accent else 'var(--line)'
    if prop in ('color', 'fill', 'stroke', '-webkit-text-fill-color'):
        if light > .98: return 'var(--on-accent)'
        if accent: return 'var(--accent)'
        if semantic and light < .75: return f'var(--{semantic})'
        return 'var(--ink)' if light < .3 else 'var(--muted)'
    if accent: return 'var(--accent-strong)'
    if len(raw) == 8: return 'var(--overlay)'
    if semantic and light > .65: return f'var(--{semantic}-tint)'
    if light > .98: return 'var(--surface)'
    if sat > .35 and light < .65: return f'var(--{semantic or "accent"})'
    return 'var(--surface-alt)'

for filename in ('styles.css', 'manager.css'):
    path = Path('frontend/src') / filename
    text = path.read_text(encoding='utf-8')
    if filename == 'styles.css':
        text = re.sub(r'^:root\s*\{.*?\}', ':root { font-family: var(--font-body); color: var(--ink); background: var(--canvas); line-height: 1.6; }', text, count=1, flags=re.S)
    def declaration(match):
        prop, value = match.group(1), match.group(2)
        value = re.sub(r'#[a-fA-F0-9]{3,8}\b|rgba?\([^)]*\)|\bwhite\b|\bblack\b', lambda m: token(m.group(), prop), value)
        return prop + ':' + value
    text = re.sub(r'([\w-]+)\s*:([^;{}]+)', declaration, text)
    path.write_text(text, encoding='utf-8')
