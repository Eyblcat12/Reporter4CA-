import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

for skip in range(5):
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'samples', 'BAO_CAO_TOOL.xlsx'), header=skip, nrows=3)
    cols = [str(c) for c in df.columns]
    print(f'header={skip}: {cols[:10]}')
    if cols and 'Unnamed' not in cols[0]:
        break
