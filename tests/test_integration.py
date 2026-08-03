import urllib.request

# Test frontend page loads
res = urllib.request.urlopen('http://localhost:5173')
html = res.read().decode()
has_root = 'id="root"' in html
has_title = 'Reporter Pro' in html
has_fonts = 'Inter' in html or 'fonts.googleapis' in html
print(f'HTML loaded: {len(html)} bytes')
print(f'Has root div: {has_root}')
print(f'Has title: {has_title}')
print(f'Has Google Fonts: {has_fonts}')

# Test API proxy from frontend port
res2 = urllib.request.urlopen('http://localhost:5173/api/health')
import json
health = json.loads(res2.read())
print(f'API proxy: {health["status"]}')

# Test column-preview with BAO_CAO_TOOL.xlsx
import base64, os
xlsx_path = os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'samples', 'BAO_CAO_TOOL.xlsx')
if os.path.exists(xlsx_path):
    with open(xlsx_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    body = json.dumps({'filename': 'BAO_CAO_TOOL.xlsx', 'contentBase64': content}).encode()
    req = urllib.request.Request(
        'http://localhost:5173/api/column-preview',
        data=body,
        headers={'Content-Type': 'application/json'}
    )
    res3 = urllib.request.urlopen(req)
    preview = json.loads(res3.read())
    print(f'Column preview: {len(preview.get("columns", []))} columns detected')
    print(f'Sheets: {preview.get("sheets", [])}')
    print(f'Sample rows: {len(preview.get("sampleRows", []))}')
    print(f'Suggested mapping: {preview.get("suggestedMapping", {})}')
else:
    print(f'BAO_CAO_TOOL.xlsx not found at {xlsx_path}')
