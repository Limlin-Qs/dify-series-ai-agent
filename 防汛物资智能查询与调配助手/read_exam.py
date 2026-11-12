import zipfile
import xml.etree.ElementTree as ET
import os
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包"

fname = "防汛物资智能查询与调配助手考试说明.docx"
path = os.path.join(base, fname)

print("FILE: 防汛物资智能查询与调配助手考试说明.docx")
print('='*80)

with zipfile.ZipFile(path, 'r') as z:
    with z.open('word/document.xml') as f:
        content = f.read().decode('utf-8')
        tree = ET.fromstring(content)
        ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        
        for para in tree.iter(f'{{{ns}}}p'):
            texts = []
            for t in para.iter(f'{{{ns}}}t'):
                if t.text:
                    texts.append(t.text)
            line = ''.join(texts).strip()
            if line:
                print(line)
        
        for ti, tbl in enumerate(tree.iter(f'{{{ns}}}tbl')):
            print(f"\n--- TABLE {ti+1} ---")
            for row in tbl.iter(f'{{{ns}}}tr'):
                cells = []
                for cell in row.iter(f'{{{ns}}}tc'):
                    cell_texts = []
                    for t in cell.iter(f'{{{ns}}}t'):
                        if t.text:
                            cell_texts.append(t.text)
                    cells.append(''.join(cell_texts).strip())
                print(" | ".join(cells))
