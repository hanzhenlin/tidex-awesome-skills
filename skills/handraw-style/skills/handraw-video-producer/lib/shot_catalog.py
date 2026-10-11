"""The shared shot directory. No semantic or renderer-name fallback."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def catalog(kind='shot'):
    if kind != 'shot':
        raise ValueError('唯一目录选项是shot')
    return json.loads((ROOT/'catalog/shots.json').read_text(encoding='utf-8'))

def types():
    return {x['id']: x for x in catalog()['items']}
