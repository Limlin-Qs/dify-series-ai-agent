import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    from docx import Document
except ImportError:
    print("python-docx not installed, trying to install...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
    from docx import Document

import os

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包"

files = [
    "防汛物资智能查询与调配助手考试说明.docx",
    "防汛物资智能查询与调配助手-测试用例.docx",
]

for f in files:
    path = os.path.join(base, f)
    print(f"\n{'='*80}")
    print(f"FILE: {f}")
    print('='*80)
    try:
        doc = Document(path)
        for i, para in enumerate(doc.paragraphs):
            if para.text.strip():
                print(para.text)
        
        # Also read tables
        for ti, table in enumerate(doc.tables):
            print(f"\n--- TABLE {ti+1} ---")
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                print(" | ".join(cells))
    except Exception as e:
        print(f"Error: {e}")
