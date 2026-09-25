"""Literal dictionary/list paths, shared by mapping validation and rendering."""
import ast


def path_parts(path):
    try:
        node = ast.parse(path, mode="eval").body
    except (SyntaxError, TypeError):
        raise ValueError("Use a field name with dotted keys or literal bracket indexes.") from None

    def walk(node):
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            return walk(node.value) + [node.attr]
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            key = node.slice.value
            if type(key) in (str, int) and (not isinstance(key, int) or 0 <= key < 1000):
                return walk(node.value) + [key]
        raise ValueError("Only dictionary keys and list indexes from 0 to 999 are supported.")

    parts = walk(node)
    if len(parts) > 16 or any(isinstance(p, str) and p.startswith("_") for p in parts):
        raise ValueError("Private names and paths deeper than 16 keys are not supported.")
    return parts


def canonical_path(path):
    parts = path_parts(path)
    return str(parts[0]) + "".join(f"[{p}]" if isinstance(p, int) else f"[{p!r}]" for p in parts[1:])


def read_path(data, path):
    value = data
    for part in path_parts(path):
        if isinstance(value, dict) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and isinstance(part, int) and part < len(value):
            value = value[part]
        else:
            raise ValueError(f"No value at {path}")
    return value


def write_path(data, path, value):
    parts = path_parts(path)
    current = data
    for index, part in enumerate(parts):
        if isinstance(current, list) and isinstance(part, int):
            while len(current) <= part:
                current.append(None)
        elif not (isinstance(current, dict) and isinstance(part, str)):
            raise ValueError(f"Conflicting field paths: {path}")
        if index == len(parts) - 1:
            current[part] = value
        else:
            child = current[part] if isinstance(current, list) else current.get(part)
            if child is None:
                child = [] if isinstance(parts[index + 1], int) else {}
                current[part] = child
            current = child
