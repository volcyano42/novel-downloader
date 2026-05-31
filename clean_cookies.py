import os, re, sys

path = 'app_data/config/sites/fanqie.yaml'
if not os.path.exists(path):
    sys.exit(0)

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace cookie values after "cookies:" block — keep keys, blank values
# Match from "  cookies:" to the next top-level key (non-indented or less-indented)
lines = content.split('\n')
in_cookies = False
cookies_indent = None
new_lines = []

for line in lines:
    # Detect start of cookies block (2-space indent under requests:)
    if not in_cookies and line.startswith('  cookies:'):
        in_cookies = True
        cookies_indent = 4  # cookies entries are indented 4 spaces
        new_lines.append(line)
        continue

    if in_cookies:
        stripped = line.lstrip()
        # End of cookies block: line with indent <= 2 (not a cookie entry)
        if line and not line.startswith('    ') and not line.startswith('      '):
            in_cookies = False
            new_lines.append(line)
            continue
        # Blank line within cookies
        if stripped == '':
            new_lines.append(line)
            continue
        # Cookie entry: "    key: value" -> "    key: "
        if line.startswith('    ') and ':' in stripped:
            key_part = line[:line.index(':')]
            new_lines.append(f'{key_part}: ')
            continue
        # Multi-line continuation (indented more than 4 spaces)
        if line.startswith('      '):
            continue  # drop continuation lines

    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))
