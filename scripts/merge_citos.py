from collections import defaultdict


def merge_citos(cito_dicts):
    merged = defaultdict(set)
    for d in cito_dicts:
        for k, v in d.items():
            merged[k].update(v)
    return merged
