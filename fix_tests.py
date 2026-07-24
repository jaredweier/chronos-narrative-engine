import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find `def complete(self, ...):` and add `def stream_complete` after it in the same class
    
    # We will just inject `    def stream_complete(self, *args, **kwargs):\n        yield "ok"\n` 
    # anywhere we see `def complete(self,` inside a mock class but we need correct indentation.
    
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        if "def complete(" in line and "def stream_complete(" not in "".join(lines[i:i+5]):
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(indent + "def stream_complete(self, *args, **kwargs):")
            new_lines.append(indent + "    yield 'ok'")

    # In test_new_features.py we also added stream_complete but we might have done it wrong
    # Let's just remove the ones we added from multi_replace_file_content earlier and rely on this simple injection.

    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines))

fix_file("tests/test_llm_fallback.py")
fix_file("tests/test_new_features.py")
