import re
TERM = re.compile(r'cdsTerm\(\s*"([^"]+)"\s*\)')
def terminals_from_labels(labels):
    out = []
    for _, expr in labels:
        if not expr:
            continue
        m = TERM.fullmatch(expr.strip())
        if m:
            out.append(m.group(1))
    return out
