import zipfile
import xml.etree.ElementTree as ET
import os
import re

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包"

files = [
    "防汛物资智能查询与调配助手考试说明.docx",
    "防汛物资智能查询与调配助手-测试用例.docx",
]

for fname in files:
    path = os.path.join(base, fname)
    print(f"\n{'='*80}")
    print(f"FILE: {fname}")
    print('='*80)
    try:
        with zipfile.ZipFile(path, 'r') as z:
            # Read document.xml
            with z.open('word/document.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                
                for para in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = []
                    for t in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                        if t.text:
                            texts.append(t.text)
                    line = ''.join(texts).strip()
                    if line:
                        print(line)
                
                # Read tables
                for ti, tbl in enumerate(root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl')):
                    print(f"\n--- TABLE {ti+1} ---")
                    for row in tbl.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr'):
                        cells = []
                        for cell in row.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
                            cell_texts = []
                            for t in cell.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                                if t.text:
                                    cell_texts.append(t.text)
                            cells.append(''.join(cell_texts).strip())
                        print(" | ".join(cells))
    except Exception as e:
        print(f"Error: {e}")
