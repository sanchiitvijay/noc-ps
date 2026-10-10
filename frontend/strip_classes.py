import os
import re

def strip_classes_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match className="..."
    content = re.sub(r'\s*className="[^"]*"', '', content)
    # Match className={...}
    # This might have nested brackets or backticks, so we'll do a slightly smarter regex or just a loop.
    # Actually, a safer way to match className={...} is to just match up to the matching brace, but since JS can have complex expressions, a simple regex might fail.
    # Let's try an iterative approach for className={
    
    while 'className={' in content:
        start_idx = content.find('className={')
        if start_idx == -1:
            break
        
        # Find the matching closing brace
        brace_count = 0
        end_idx = -1
        in_string = False
        string_char = ''
        
        for i in range(start_idx + 10, len(content)):
            char = content[i]
            if not in_string:
                if char in ('"', "'", '`'):
                    in_string = True
                    string_char = char
                elif char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            else:
                if char == string_char and content[i-1] != '\\':
                    in_string = False
                    
        if end_idx != -1:
            # Also remove preceding space if possible
            remove_start = start_idx
            while remove_start > 0 and content[remove_start-1] == ' ':
                remove_start -= 1
            content = content[:remove_start] + content[end_idx + 1:]
        else:
            break
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# Process all jsx files in src
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.jsx'):
            strip_classes_from_file(os.path.join(root, file))
            
