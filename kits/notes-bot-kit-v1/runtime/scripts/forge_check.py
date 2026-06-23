# -*- coding: utf-8 -*-
import json
import sys
import io

# Force utf-8 output for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = r'C:\Users\Admin\.openclaw\workspace\memory\notes.jsonl'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
print('Total lines:', len(lines))
print('=== Last 15 with content > 30 OR is_idea ===')
for line in lines[-15:]:
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
        c = o.get('content') or ''
        if len(c) > 30 or o.get('is_idea'):
            print('---')
            print('ts:', o.get('ts'))
            print('user:', o.get('username'), 'id:', o.get('user_id'))
            print('kind:', o.get('kind'), 'is_idea:', o.get('is_idea'))
            print('len:', len(c))
            print('content:', c)
    except Exception as e:
        print('err:', e)
