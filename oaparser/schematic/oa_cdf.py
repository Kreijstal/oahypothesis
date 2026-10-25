#!/usr/bin/env python3
"""oa_cdf.py -- read a cell's CDF parameter defaults from data.dm.

Virtuoso symbol labels like cdsParam(1) are NOT data in the .oa file: they
evaluate against the cell's CDF.  The CDF lives next to the cellview in
`<cell>/data.dm` (a text file), e.g. analogLib/xfmr:

    propList (paramLabelSet "k" ... hspiceD (... instParameters (k pi si) ...))
    parameters ((... name "k" ... defValue "0" ...))

so cdsParam(1) -> instParameters[0] = k, default "0" -> displayed "k:0".
"""
import os
import re

DEF_VALUE = re.compile(r'defValue\s+"([^"]*)"')
PARAM_NAME = re.compile(r'name\s+"([^"]*)"')
INST_PARAMS = re.compile(r'instParameters\s+\(([^)]*)\)')
LABEL_SET = re.compile(r'paramLabelSet\s+"([^"]*)"')


def read_cell(cell_dir):
    """{'defaults': {name: defValue}, 'instParameters': [names], 'label': str}"""
    path = os.path.join(cell_dir, "data.dm")
    if not os.path.exists(path):
        return None
    text = open(path, errors="replace").read()
    # one record per parameter; the display value contains ")" so we cannot use
    # a bracket-balanced regex
    defaults = {}
    for chunk in text.split("(storeDefault")[1:]:
        dv = DEF_VALUE.search(chunk)
        nm = PARAM_NAME.search(chunk)
        if dv and nm:
            defaults[nm.group(1)] = dv.group(1)
    m = INST_PARAMS.search(text)
    inst = m.group(1).replace("\\", "").split() if m else []
    lm = LABEL_SET.search(text)
    return {"defaults": defaults, "instParameters": inst,
            "label": lm.group(1) if lm else None}


def param_display(cdf, index):
    """Rendered text for cdsParam(index) (1-based), or None."""
    if not cdf:
        return None
    names = cdf.get("instParameters") or []
    if not (1 <= index <= len(names)):
        return None
    name = names[index - 1]
    value = cdf["defaults"].get(name, "")
    if value == "":
        return None          # nothing to show, like Cadence (only k:0 appears)
    return f"{name}:{value}"
