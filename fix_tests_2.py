import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find `def stream_complete` and fix its indentation and the line after it.
    # Actually, let's just use regex to replace it
    content = re.sub(r'(\s+)def stream_complete\(self, \*args, \*\*kwargs\):\n(\s+)yield \'ok\'', r'\1def stream_complete(self, *args, **kwargs):\n\1    yield "ok"', content)

    with open(filepath, 'w') as f:
        f.write(content)

fix_file("tests/test_llm_fallback.py")
fix_file("tests/test_new_features.py")
