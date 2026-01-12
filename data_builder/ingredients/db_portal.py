#!/usr/bin/env python3
"""Portal view for Final DB - ingredient database viewer."""

import json
import sqlite3
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)
DB_PATH = "data_builder/ingredients/output/Final DB.db"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Final DB Portal</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; margin-bottom: 10px; }
        .stats { background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }
        .stat-box { background: #f8f9fa; padding: 15px; border-radius: 6px; text-align: center; }
        .stat-box h3 { margin: 0; font-size: 28px; color: #2563eb; }
        .stat-box p { margin: 5px 0 0; color: #666; font-size: 14px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .tab { padding: 10px 20px; background: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
        .tab.active { background: #2563eb; color: #fff; }
        .search-box { margin-bottom: 15px; }
        .search-box input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; }
        table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; color: #333; position: sticky; top: 0; }
        tr:hover { background: #f8f9fa; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
        .badge-green { background: #dcfce7; color: #166534; }
        .badge-blue { background: #dbeafe; color: #1e40af; }
        .badge-yellow { background: #fef3c7; color: #92400e; }
        .badge-gray { background: #f3f4f6; color: #374151; }
        .specs { font-size: 12px; color: #666; max-width: 400px; }
        .pagination { margin-top: 15px; display: flex; gap: 10px; align-items: center; }
        .pagination button { padding: 8px 16px; border: 1px solid #ddd; background: #fff; border-radius: 4px; cursor: pointer; }
        .pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
        .table-container { max-height: 600px; overflow-y: auto; }
    </style>
</head>
<body>
    <h1>Final DB Portal</h1>
    
    <div class="stats">
        <div class="stats-grid">
            <div class="stat-box">
                <h3>{{ stats.total_items }}</h3>
                <p>Total Items</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_specs }}</h3>
                <p>With Seed Specs</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_compiled }}</h3>
                <p>With Compiled Data</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_cosing }}</h3>
                <p>From CosIng</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_tgsc }}</h3>
                <p>From TGSC</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.total_terms }}</h3>
                <p>Normalized Terms</p>
            </div>
        </div>
    </div>
    
    <div class="tabs">
        <button class="tab active" onclick="loadTable('items')">All Items</button>
        <button class="tab" onclick="loadTable('terms')">Terms</button>
        <button class="tab" onclick="loadTable('specs')">With Specs</button>
        <button class="tab" onclick="loadTable('compiled')">Compiled</button>
        <button class="tab" onclick="loadTable('cosing')">CosIng</button>
        <button class="tab" onclick="loadTable('tgsc')">TGSC</button>
    </div>
    
    <div class="search-box">
        <input type="text" id="search" placeholder="Search..." onkeyup="debounceSearch()">
    </div>
    
    <div class="table-container">
        <table id="data-table">
            <thead id="table-head"></thead>
            <tbody id="table-body"></tbody>
        </table>
    </div>
    
    <div class="pagination">
        <button onclick="prevPage()" id="prev-btn">Previous</button>
        <span id="page-info">Page 1</span>
        <button onclick="nextPage()" id="next-btn">Next</button>
    </div>
    
    <script>
        let currentView = 'items';
        let currentPage = 1;
        let totalPages = 1;
        let searchTimeout;
        
        function debounceSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => { currentPage = 1; loadTable(currentView); }, 300);
        }
        
        function loadTable(view) {
            currentView = view;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event?.target?.classList.add('active');
            
            const search = document.getElementById('search').value;
            fetch(`/api/data?view=${view}&page=${currentPage}&search=${encodeURIComponent(search)}`)
                .then(r => r.json())
                .then(data => {
                    totalPages = data.total_pages;
                    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
                    document.getElementById('prev-btn').disabled = currentPage <= 1;
                    document.getElementById('next-btn').disabled = currentPage >= totalPages;
                    
                    const thead = document.getElementById('table-head');
                    const tbody = document.getElementById('table-body');
                    thead.innerHTML = '<tr>' + data.columns.map(c => `<th>${c}</th>`).join('') + '</tr>';
                    tbody.innerHTML = data.rows.map(row => 
                        '<tr>' + row.map(cell => `<td>${formatCell(cell)}</td>`).join('') + '</tr>'
                    ).join('');
                });
        }
        
        function formatCell(val) {
            if (val === null || val === '') return '<span class="badge badge-gray">-</span>';
            if (typeof val === 'string' && val.startsWith('{')) {
                try {
                    const obj = JSON.parse(val);
                    return '<span class="specs">' + Object.entries(obj).slice(0, 5).map(([k,v]) => `${k}: ${typeof v === 'object' ? '...' : v}`).join(', ') + '</span>';
                } catch { return val; }
            }
            if (val === 'Yes') return '<span class="badge badge-green">Yes</span>';
            if (val === 1 || val === true) return '<span class="badge badge-green">Yes</span>';
            if (val === 0 || val === false) return '<span class="badge badge-gray">No</span>';
            return val;
        }
        
        function prevPage() { if (currentPage > 1) { currentPage--; loadTable(currentView); } }
        function nextPage() { if (currentPage < totalPages) { currentPage++; loadTable(currentView); } }
        
        loadTable('items');
    </script>
</body>
</html>
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()
    
    stats = {}
    cur.execute("SELECT COUNT(*) FROM merged_item_forms")
    stats['total_items'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE app_seed_specs_json IS NOT NULL")
    stats['with_specs'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL")
    stats['with_compiled'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1")
    stats['with_cosing'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1")
    stats['with_tgsc'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM normalized_terms")
    stats['total_terms'] = cur.fetchone()[0]
    
    conn.close()
    return render_template_string(HTML_TEMPLATE, stats=stats)

@app.route('/api/data')
def api_data():
    view = request.args.get('view', 'items')
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '').strip()
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db()
    cur = conn.cursor()
    
    if view == 'items':
        where = f"WHERE derived_term LIKE '%{search}%'" if search else ""
        cur.execute(f"SELECT COUNT(*) FROM merged_item_forms {where}")
        total = cur.fetchone()[0]
        cur.execute(f"""
            SELECT id, derived_term, derived_physical_form, has_cosing, has_tgsc,
                   CASE WHEN app_seed_specs_json IS NOT NULL THEN 'Yes' ELSE '-' END as has_specs,
                   CASE WHEN compiled_specs_json IS NOT NULL THEN 'Yes' ELSE '-' END as has_compiled
            FROM merged_item_forms {where}
            ORDER BY id LIMIT {per_page} OFFSET {offset}
        """)
        columns = ['ID', 'Term', 'Form', 'CosIng', 'TGSC', 'Specs', 'Compiled']
        
    elif view == 'terms':
        where = f"WHERE term LIKE '%{search}%'" if search else ""
        cur.execute(f"SELECT COUNT(*) FROM normalized_terms {where}")
        total = cur.fetchone()[0]
        cur.execute(f"""
            SELECT term, inci_name, botanical_name, ingredient_category, origin
            FROM normalized_terms {where}
            ORDER BY term LIMIT {per_page} OFFSET {offset}
        """)
        columns = ['Term', 'INCI Name', 'Botanical Name', 'Category', 'Origin']
        
    elif view == 'specs':
        where = f"AND derived_term LIKE '%{search}%'" if search else ""
        cur.execute(f"SELECT COUNT(*) FROM merged_item_forms WHERE app_seed_specs_json IS NOT NULL {where}")
        total = cur.fetchone()[0]
        cur.execute(f"""
            SELECT id, derived_term, derived_physical_form, app_seed_specs_json
            FROM merged_item_forms 
            WHERE app_seed_specs_json IS NOT NULL {where}
            ORDER BY id LIMIT {per_page} OFFSET {offset}
        """)
        columns = ['ID', 'Term', 'Form', 'Specs']
        
    elif view == 'compiled':
        where = f"AND derived_term LIKE '%{search}%'" if search else ""
        cur.execute(f"SELECT COUNT(*) FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL {where}")
        total = cur.fetchone()[0]
        cur.execute(f"""
            SELECT id, derived_term, derived_physical_form, compiled_specs_json
            FROM merged_item_forms 
            WHERE compiled_specs_json IS NOT NULL {where}
            ORDER BY id LIMIT {per_page} OFFSET {offset}
        """)
        columns = ['ID', 'Term', 'Form', 'Compiled Specs']
        
    elif view == 'cosing':
        where = f"AND derived_term LIKE '%{search}%'" if search else ""
        cur.execute(f"SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 {where}")
        total = cur.fetchone()[0]
        cur.execute(f"""
            SELECT id, derived_term, derived_physical_form, cas_numbers_json, source_row_count
            FROM merged_item_forms 
            WHERE has_cosing = 1 {where}
            ORDER BY id LIMIT {per_page} OFFSET {offset}
        """)
        columns = ['ID', 'Term', 'Form', 'CAS Numbers', 'Source Rows']
        
    elif view == 'tgsc':
        where = f"AND derived_term LIKE '%{search}%'" if search else ""
        cur.execute(f"SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1 {where}")
        total = cur.fetchone()[0]
        cur.execute(f"""
            SELECT id, derived_term, derived_physical_form, cas_numbers_json, source_row_count
            FROM merged_item_forms 
            WHERE has_tgsc = 1 {where}
            ORDER BY id LIMIT {per_page} OFFSET {offset}
        """)
        columns = ['ID', 'Term', 'Form', 'CAS Numbers', 'Source Rows']
    
    else:
        total = 0
        columns = []
    
    rows = [list(row) for row in cur.fetchall()]
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    conn.close()
    return jsonify({'columns': columns, 'rows': rows, 'total_pages': total_pages})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
