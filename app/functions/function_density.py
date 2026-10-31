"""Spatial category density editing and isolated preview/save sessions. No GUI calls."""
import copy
import math
import random
from pathlib import Path
from collections import defaultdict
import app.backend.xml_backend as ET
from app.backend.patch_store import PATCH_STORE


def local_tag(node):
    return node.tag.rsplit('}', 1)[-1] if isinstance(node.tag, str) else ''


def child(node, name):
    return next((n for n in node if local_tag(n) == name), None)


def position(node):
    p = child(node, 'Position')
    try:
        values = tuple(float(v.replace(',', '.')) for v in (p.text or '').split())
    except (AttributeError, ValueError):
        return None
    return values if len(values) == 3 and all(math.isfinite(v) for v in values) else None


def change_density(document, index, percent, increase, progress=lambda *a: None, rng=None):
    """Return a copy, before/after counts, and total per-index usage.

    Removal cycles through spatial cells instead of XML order. Additions
    interpolate nearby existing positions, including Y. Terrain collision or
    surface heights cannot be established from instance positions alone.
    """
    percent = float(str(percent).replace(',', '.'))
    if not math.isfinite(percent) or not 0 < percent <= 100:
        raise ValueError('Density (%) must be greater than 0 and at most 100.')
    rng = rng or random.Random()
    tree = copy.deepcopy(document)
    grid = next((n for n in tree.getroot().iter() if local_tag(n) == 'PropGrid'), None)
    if grid is None:
        raise ValueError('PropGrid was not found.')
    instances = child(grid, 'Instances')
    names = child(grid, 'FileNames')
    if names is None or instances is None:
        raise ValueError('Invalid index or missing Instances.')
    def entry_index(n):
        try:
            return int(child(n, 'Index').text)
        except (AttributeError, ValueError, TypeError):
            return -1
    indices = {index} if isinstance(index, int) else set(index)
    if not indices or any(not isinstance(i, int) or not 0 <= i < len(names) for i in indices):
        raise ValueError("Invalid category indices.")
    selected = [n for n in instances if entry_index(n) in indices]
    before = len(selected)
    if not before:
        raise ValueError('This category has no instances. No position template is available.')
    points = [position(n) for n in selected]
    if any(p is None for p in points):
        raise ValueError('This category contains invalid Position data. No changes were made.')
    amount = max(1, math.floor(before * percent / 100 + .5))
    if increase and amount > 100000:
        raise ValueError('Too many new instances in one operation (maximum 100000).')
    xs, zs = [p[0] for p in points], [p[2] for p in points]
    minx, minz = min(xs), min(zs)
    spanx, spanz = max(xs)-minx, max(zs)-minz
    divisions = max(1, math.ceil(math.sqrt(before / 8)))
    def cell(p):
        return (min(divisions-1, int((p[0]-minx)/spanx*divisions)) if spanx else 0,
                min(divisions-1, int((p[2]-minz)/spanz*divisions)) if spanz else 0)
    cells = defaultdict(list)
    for i,p in enumerate(points):
        cells[cell(p)].append(i)
    keys = list(cells)
    rng.shuffle(keys)
    progress(0, amount)
    if not increase:
        # Largest-remainder apportionment: dense cells contribute more than
        # sparse cells. Integer arithmetic avoids floating-point quota errors.
        quotas = {}
        remainders = {}
        for key, bucket in cells.items():
            quotas[key], remainders[key] = divmod(len(bucket) * amount, before)
        remaining = amount - sum(quotas.values())
        # keys was shuffled above, so equal remainders have unbiased tie breaks.
        ranked = sorted(keys, key=lambda key: remainders[key], reverse=True)
        for key in ranked[:remaining]:
            quotas[key] += 1
        remove = set()
        for key in keys:
            quota = quotas[key]
            if quota:
                remove.update(rng.sample(cells[key], quota))
                progress(len(remove), amount)
        removed = {selected[i] for i in remove}
        instances[:] = [n for n in instances if n not in removed]
    else:
        occupied = set(points)
        if len(occupied) < 2:
            raise ValueError('At least two distinct positions are required for interpolation.')
        for step in range(amount):
            # Spread additions across occupied regions; find a nearby partner.
            key = keys[step % len(keys)]
            base = rng.choice(cells[key]); p = points[base]
            candidates = []
            for radius in range(divisions+1):
                for dx in range(-radius,radius+1):
                    for dz in range(-radius,radius+1):
                        if max(abs(dx),abs(dz)) != radius:
                            continue
                        candidates.extend(cells.get((key[0]+dx,key[1]+dz), ()))
                valid = [j for j in candidates if points[j] != p]
                if valid:
                    break
            partner = min(valid, key=lambda j: sum((points[j][k]-p[k])**2 for k in (0,2)))
            q = points[partner]
            for attempt in range(100):
                fraction = rng.uniform(.25,.75)
                new = tuple(round(p[k]+fraction*(q[k]-p[k]),8) for k in range(3))
                if new not in occupied:
                    break
            else:
                raise ValueError('Could not generate a distinct interpolated position.')
            occupied.add(new)
            node = copy.deepcopy(selected[base])
            child(node,'Position').text = ' '.join(format(v,'.8f').rstrip('0').rstrip('.').replace('.',',') if v else '0' for v in new)
            instances.append(node)
            if step % 100 == 0:
                progress(step+1,amount)
    usage = [0]*len(names)
    for node in instances:
        idx = entry_index(node)
        if 0 <= idx < len(usage):
            usage[idx] += 1
    progress(amount,amount)
    return tree, before, sum(usage[i] for i in indices), usage


def usage_counts(document):
    grid = next(n for n in document.getroot().iter() if local_tag(n) == 'PropGrid')
    names, instances = child(grid, 'FileNames'), child(grid, 'Instances')
    counts = [0] * len(names)
    if instances is not None:
        for node in instances:
            try:
                index = int(child(node, 'Index').text)
            except (AttributeError, ValueError, TypeError):
                continue
            if 0 <= index < len(counts):
                counts[index] += 1
    return counts


class DensitySession:
    """Isolated preview; Restore reloads original Instances without replacing other settings."""
    def __init__(self, cache):
        self.cache = cache
        self.signature = cache.signature
        self.baseline = copy.deepcopy(cache.working)
        self.tree = copy.deepcopy(self.baseline)
        self.usage = usage_counts(self.tree)
        self.dirty = False

    def change(self, indices, percent, increase, progress):
        tree, before, after, counts = change_density(self.tree, indices, percent, increase, progress)
        self.tree, self.usage, self.dirty = tree, counts, True
        return before, after

    def restore(self):
        """Remove only the saved density/instance scope and rebuild the preview."""
        PATCH_STORE.reset_scope("rd3d", self.cache.path, "rd3d_instances")
        current = PATCH_STORE.view("rd3d", self.cache.path)
        self.cache.working = copy.deepcopy(current)
        self.cache.signature = self.cache._signature()
        self.cache.usage = usage_counts(current)
        self.signature = self.cache.signature
        self.baseline = copy.deepcopy(current)
        self.tree = copy.deepcopy(current)
        self.usage = list(self.cache.usage)
        self.dirty = False

    def save(self, progress):
        """Save only PropGrid/Instances to rd3d_patch.json."""
        progress(0, 3)
        if not self.dirty:
            progress(3, 3)
            return
        grid = next((node for node in self.tree.getroot().iter()
                     if local_tag(node) == "PropGrid"), None)
        instances = child(grid, "Instances") if grid is not None else None
        if instances is None:
            raise ValueError("PropGrid/Instances was not found. No density patch was saved.")
        payload = {
            "parent_tag": "PropGrid",
            "child_tag": "Instances",
            "xml": ET.tostring(instances, encoding="unicode"),
        }
        progress(1, 3)
        reloaded = PATCH_STORE.save_scope(
            "rd3d", self.cache.path, "rd3d_instances", payload)
        progress(2, 3)
        self.cache.working = copy.deepcopy(reloaded)
        self.cache.signature = self.cache._signature()
        self.cache.usage = usage_counts(reloaded)
        self.signature = self.cache.signature
        self.baseline = copy.deepcopy(reloaded)
        self.tree = copy.deepcopy(reloaded)
        self.usage = list(self.cache.usage)
        self.dirty = False
        progress(3, 3)

    def map_points(self, categories):
        grid = next(n for n in self.tree.getroot().iter() if local_tag(n) == 'PropGrid')
        instances = child(grid, 'Instances')
        result = []
        if instances is None:
            return result
        for node in instances:
            try:
                index = int(child(node, 'Index').text)
            except (AttributeError, ValueError, TypeError):
                continue
            p = position(node)
            if p is not None:
                x,y,z = p
                result.append((index,x,z,y,child(node,'Position').text,categories.get(index,'Unknown')))
        return result
