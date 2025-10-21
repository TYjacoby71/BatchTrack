import re
import os
import glob
from collections import defaultdict, deque
from datetime import datetime

LOG_GLOB_PATTERNS = [
    os.path.join('attached_assets', 'Pasted-*upgrade*.txt'),
]

RUNNING_UPGRADE_REGEX = re.compile(
    r"\bRunning upgrade\s+([^\s]+)\s*->\s*([^,\s]+)\s*,\s*(.*)$",
    re.IGNORECASE,
)


def discover_log_files():
    files = []
    for pattern in LOG_GLOB_PATTERNS:
        files.extend(glob.glob(pattern))
    # Sort for deterministic processing
    files.sort()
    return files


def parse_upgrade_lines(file_path):
    entries = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m = RUNNING_UPGRADE_REGEX.search(line)
                if m:
                    from_rev = m.group(1).strip()
                    to_rev = m.group(2).strip()
                    desc = m.group(3).strip()
                    entries.append((from_rev, to_rev, desc, file_path))
    except Exception as e:
        # Best-effort; skip unreadable files
        pass
    return entries


def normalize_revision(rev):
    # Normalize common oddities, e.g., 2025090502 vs 2025..._02
    # Convert patterns like 2025090502 -> 20250905_02 if it looks like yyyymmddNN
    if re.fullmatch(r"\d{10}", rev):
        # yyyy mm dd nn (8 + 2)
        return f"{rev[:8]}_{rev[8:]}"
    return rev


def build_graph(entries):
    # Deduplicate identical edges but keep a representative description
    edge_desc = {}
    edge_sources = defaultdict(set)

    out_edges = defaultdict(list)  # from_rev -> list of to_rev
    in_degree = defaultdict(int)
    nodes = set()

    for from_rev, to_rev, desc, src in entries:
        from_norm = normalize_revision(from_rev)
        to_norm = normalize_revision(to_rev)
        key = (from_norm, to_norm)
        if key not in edge_desc:
            edge_desc[key] = desc
        # Track sources
        edge_sources[key].add(src)

        # Graph
        out_edges[from_norm].append(to_norm)
        in_degree[to_norm] += 1
        nodes.add(from_norm)
        nodes.add(to_norm)
        # Ensure all nodes are in in_degree
        in_degree.setdefault(from_norm, in_degree.get(from_norm, 0))

    return nodes, out_edges, in_degree, edge_desc, edge_sources


def topological_chains(nodes, out_edges, in_degree):
    # Find heads: nodes with in_degree 0 and with outgoing edges
    heads = [n for n in nodes if in_degree.get(n, 0) == 0 and out_edges.get(n)]

    # Build chains greedily by following single outgoing edges where possible
    visited_edges = set()
    chains = []

    for head in heads:
        current = head
        chain = [current]
        while True:
            outs = out_edges.get(current, [])
            # Prefer single-next; if multiple, we'll stop to avoid ambiguity
            next_nodes = [n for n in outs if (current, n) not in visited_edges]
            if len(next_nodes) != 1:
                break
            nxt = next_nodes[0]
            visited_edges.add((current, nxt))
            chain.append(nxt)
            current = nxt
        if len(chain) > 1:
            chains.append(chain)

    # Remaining edges not in chains
    remaining_edges = []
    for frm, outs in out_edges.items():
        for to in outs:
            if (frm, to) not in visited_edges:
                remaining_edges.append((frm, to))

    return chains, remaining_edges


def is_date_like(rev):
    return bool(re.match(r"^\d{8}(_\d+)?$", rev))


def chain_sort_key(chain):
    # Use first date-like rev if present, else fallback to lexicographic
    for rev in chain:
        if is_date_like(rev):
            return (0, rev)
    return (1, chain[0])


def render_markdown(chains, remaining_edges, edge_desc, edge_sources):
    lines = []
    lines.append("# Database Upgrade Log")
    lines.append("")
    lines.append(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} from attached migration logs.")
    lines.append("")
    lines.append("This is a consolidated, chronological reconstruction of Alembic upgrades from base to current. It was built by parsing `attached_assets/Pasted-*upgrade*.txt`.")
    lines.append("")

    # Sort chains for readability
    chains_sorted = sorted(chains, key=chain_sort_key)

    for idx, chain in enumerate(chains_sorted, start=1):
        lines.append(f"## Upgrade path {idx}")
        lines.append("")
        for i in range(len(chain) - 1):
            frm = chain[i]
            to = chain[i + 1]
            desc = edge_desc.get((frm, to), '')
            # Keep short descriptions to one line
            desc_short = desc.strip().rstrip('.')
            source_hint = ''
            # Optionally include one source file for traceability
            srcs = edge_sources.get((frm, to))
            if srcs:
                # pick one deterministic
                src = sorted(srcs)[0]
                source_hint = f" ({os.path.basename(src)})"
            lines.append(f"- {frm} -> {to}: {desc_short}{source_hint}")
        lines.append("")

    if remaining_edges:
        lines.append("## Unchained entries")
        lines.append("")
        lines.append("Entries that did not fit cleanly into a single sequential path (possibly due to branches or partial logs):")
        lines.append("")
        # Sort for stable output
        remaining_edges_sorted = sorted(remaining_edges)
        for frm, to in remaining_edges_sorted:
            desc = edge_desc.get((frm, to), '')
            desc_short = desc.strip().rstrip('.')
            srcs = edge_sources.get((frm, to))
            source_hint = ''
            if srcs:
                source_hint = f" ({os.path.basename(sorted(srcs)[0])})"
            lines.append(f"- {frm} -> {to}: {desc_short}{source_hint}")
        lines.append("")

    return "\n".join(lines)


def main():
    files = discover_log_files()
    all_entries = []
    for fp in files:
        all_entries.extend(parse_upgrade_lines(fp))

    if not all_entries:
        print("No upgrade entries found.")
        return

    nodes, out_edges, in_degree, edge_desc, edge_sources = build_graph(all_entries)
    chains, remaining_edges = topological_chains(nodes, out_edges, in_degree)

    md = render_markdown(chains, remaining_edges, edge_desc, edge_sources)
    os.makedirs('docs', exist_ok=True)
    out_path = os.path.join('docs', 'UPGRADE_LOG.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"Wrote consolidated upgrade log to {out_path} with {sum(len(c)-1 for c in chains)} chained entries and {len(remaining_edges)} unchained.")


if __name__ == '__main__':
    main()
