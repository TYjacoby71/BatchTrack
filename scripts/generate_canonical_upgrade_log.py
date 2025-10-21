import os
import re
import glob
import ast
from collections import defaultdict, deque
from datetime import datetime, timezone

MIGRATIONS_DIR = os.path.join('migrations', 'versions')
ATTACHED_LOGS_GLOB = os.path.join('attached_assets', 'Pasted-*upgrade*.txt')

REVISION_RE = re.compile(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
DOWN_REVISION_RE = re.compile(r"^down_revision\s*=\s*(.+)$", re.MULTILINE)
MESSAGE_RE = re.compile(r"^message\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
RUNNING_UPGRADE_REGEX = re.compile(r"\bRunning upgrade\s+([^\s]+)\s*->\s*([^,\s]+)\s*,\s*(.*)$", re.IGNORECASE)


def read_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def parse_down_revision(expr: str):
    # Strip inline comments
    expr = expr.split('#', 1)[0].strip()
    try:
        value = ast.literal_eval(expr)
    except Exception:
        # Fallback: try to parse simple quoted string
        m = re.match(r"['\"]([^'\"]+)['\"]", expr)
        if m:
            value = m.group(1)
        else:
            value = None
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def slugify_description_from_filename(filename: str, revision: str) -> str:
    name = os.path.splitext(os.path.basename(filename))[0]
    if name.startswith(revision + '_'):
        remainder = name[len(revision) + 1:]
    else:
        remainder = name
    remainder = remainder.replace('_', ' ').strip(' _-')
    # Clean trailing underscores
    while remainder.endswith('_'):
        remainder = remainder[:-1]
    return remainder if remainder else name


def discover_migrations():
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, '*.py')))
    migrations = {}
    edges = defaultdict(list)
    in_degree = defaultdict(int)
    file_for_revision = {}

    for fp in files:
        content = read_file(fp)
        rev_m = REVISION_RE.search(content)
        if not rev_m:
            continue
        revision = rev_m.group(1).strip()
        file_for_revision[revision] = fp

        down_m = DOWN_REVISION_RE.search(content)
        down_revs = []
        if down_m:
            down_revs = parse_down_revision(down_m.group(1))

        msg_m = MESSAGE_RE.search(content)
        if msg_m:
            description = msg_m.group(1).strip()
        else:
            description = slugify_description_from_filename(fp, revision)

        migrations[revision] = {
            'revision': revision,
            'down_revisions': down_revs,
            'description': description,
            'file': fp,
        }

    # Build graph edges
    nodes = set(migrations.keys())
    for rev, meta in migrations.items():
        if not meta['down_revisions']:
            in_degree.setdefault(rev, 0)
        for down in meta['down_revisions']:
            if down not in nodes:
                # Orphan link to missing migration; still record node
                nodes.add(down)
                in_degree.setdefault(down, 0)
            edges[down].append(rev)
            in_degree[rev] += 1

    return migrations, edges, in_degree


def is_date_like(rev: str) -> bool:
    return bool(re.match(r"^\d{8}(?:_\d+)?$", rev))


def topo_sort(migrations, edges, in_degree):
    # Stable topological sort: prefer date-like revisions ascending, else lexicographic
    def node_key(n):
        return (0, n) if is_date_like(n) else (1, n)

    zero_in = [n for n, deg in in_degree.items() if deg == 0]
    zero_in.sort(key=node_key)
    order = []

    local_in = dict(in_degree)
    local_edges = {k: list(v) for k, v in edges.items()}

    while zero_in:
        n = zero_in.pop(0)
        if n in migrations:
            order.append(n)
        for m in local_edges.get(n, []):
            local_in[m] -= 1
            if local_in[m] == 0:
                zero_in.append(m)
        # Keep stable ordering
        zero_in.sort(key=node_key)

    # Append any nodes we never saw (in case of cycles or missing in_degree entries)
    unseen = [n for n in migrations.keys() if n not in order]
    unseen.sort(key=node_key)
    order.extend(unseen)
    return order


def parse_observed_transitions():
    files = sorted(glob.glob(ATTACHED_LOGS_GLOB))
    transitions = {}
    sources = defaultdict(set)
    for fp in files:
        with open(fp, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m = RUNNING_UPGRADE_REGEX.search(line)
                if m:
                    a, b, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                    key = (a, b)
                    if key not in transitions:
                        transitions[key] = desc
                    sources[key].add(os.path.basename(fp))
    return transitions, sources


def render_markdown(migrations, order, transitions, sources):
    lines = []
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
    lines.append('# Database Upgrade Log')
    lines.append('')
    lines.append(f'Generated on {now} from Alembic migrations and observed runtime logs.')
    lines.append('')
    lines.append('## Canonical Alembic upgrade order (base ➜ head)')
    lines.append('')

    for rev in order:
        if rev not in migrations:
            # Skip orphan nodes not present as files
            continue
        meta = migrations[rev]
        downs = meta['down_revisions']
        if not downs:
            down_str = 'base'
        elif len(downs) == 1:
            down_str = downs[0]
        else:
            down_str = '[' + ', '.join(downs) + ']'
        desc = meta['description']
        file_name = os.path.basename(meta['file'])
        lines.append(f"- {down_str} -> {rev}: {desc} ({file_name})")

    if transitions:
        lines.append('')
        lines.append('## Observed runtime upgrade transitions')
        lines.append('')
        lines.append('Collapsed from `attached_assets/Pasted-*upgrade*.txt` and deduplicated.')
        lines.append('')
        for (a, b), desc in sorted(transitions.items()):
            srcs = ' | '.join(sorted(sources.get((a, b), [])))
            desc_short = desc.strip().rstrip('.')
            src_hint = f" ({srcs})" if srcs else ''
            lines.append(f"- {a} -> {b}: {desc_short}{src_hint}")

    return '\n'.join(lines)


def main():
    migrations, edges, in_degree = discover_migrations()
    order = topo_sort(migrations, edges, in_degree)
    transitions, sources = parse_observed_transitions()

    md = render_markdown(migrations, order, transitions, sources)

    os.makedirs('docs', exist_ok=True)
    out_path = os.path.join('docs', 'UPGRADE_LOG.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"Wrote canonical upgrade log to {out_path} with {len(order)} migrations and {len(transitions)} observed transitions.")


if __name__ == '__main__':
    main()
