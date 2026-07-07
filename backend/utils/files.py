import re


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name.strip() or 'arquivo'


def unique_filename(name, used_names):
    if name not in used_names:
        used_names.add(name)
        return name

    base, dot, ext = name.rpartition('.')
    if not dot:
        base = name
        ext = ''

    counter = 2
    while True:
        candidate = f"{base} ({counter})"
        if ext:
            candidate = f"{candidate}.{ext}"

        if candidate not in used_names:
            used_names.add(candidate)
            return candidate

        counter += 1
