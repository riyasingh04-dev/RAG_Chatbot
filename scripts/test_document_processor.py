import os
import sys
import json
import nbformat
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from app.services.document_processor import document_processor


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def create_csv(path):
    df = pd.DataFrame({"id": [1, 2, 3], "name": ["alice", "bob", "carol"]})
    df.to_csv(path, index=False)


def create_excel(path):
    df1 = pd.DataFrame({"col1": [10, 20], "col2": ["x", "y"]})
    df2 = pd.DataFrame({"a": [1], "b": [2]})
    with pd.ExcelWriter(path) as writer:
        df1.to_excel(writer, sheet_name="Sheet1", index=False)
        df2.to_excel(writer, sheet_name="Another", index=False)


def create_json(path):
    obj = {"users": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}], "meta": {"source": "test"}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def create_ipynb(path):
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Sample Notebook\nThis is a markdown cell."),
        nbformat.v4.new_code_cell("print('hello from code cell')")
    ]
    with open(path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)


def create_py(path):
    src = """
def hello(name):
    return f'hello {name}'

if __name__ == '__main__':
    print(hello('world'))
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def run_tests(tmp_dir):
    ensure_dir(tmp_dir)

    files = {}
    files['csv'] = os.path.join(tmp_dir, 'sample.csv')
    files['xlsx'] = os.path.join(tmp_dir, 'sample.xlsx')
    files['json'] = os.path.join(tmp_dir, 'sample.json')
    files['ipynb'] = os.path.join(tmp_dir, 'sample.ipynb')
    files['py'] = os.path.join(tmp_dir, 'sample.py')

    create_csv(files['csv'])
    create_excel(files['xlsx'])
    create_json(files['json'])
    create_ipynb(files['ipynb'])
    create_py(files['py'])

    for k, path in files.items():
        print('=' * 40)
        print(f"Loading {k}: {path}")
        try:
            docs = document_processor.load_document(path)
            if not docs:
                print(f"No documents returned for {path}")
                continue

            print(f"Returned {len(docs)} document(s) for {k}")
            for i, doc in enumerate(docs[:3]):
                print(f"--- doc {i} metadata: {doc.metadata}")
                preview = doc.page_content[:400].replace('\n', ' ') if doc.page_content else ''
                print(f"--- doc {i} preview: {preview}\n")

        except Exception as e:
            print(f"Error loading {path}: {e}")


if __name__ == '__main__':
    tmp = os.path.join(ROOT, 'scripts', 'tmp_samples')
    run_tests(tmp)
