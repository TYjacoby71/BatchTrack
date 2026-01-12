#!/usr/bin/env python3
"""Portal view for Final DB - ingredient database viewer with hierarchical views and exports."""

import csv
import io
import json
import sqlite3
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)
FINAL_DB_PATH = "data_builder/ingredients/output/Final DB.db"
BACKUP_DB_PATH = "data_builder/ingredients/output/Final DB backup.db"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Final DB Portal</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; margin-bottom: 5px; }
        h2 { color: #555; margin: 20px 0 10px; font-size: 18px; border-bottom: 2px solid #2563eb; padding-bottom: 5px; }
        .stats { background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
        .stat-box { background: #f8f9fa; padding: 12px; border-radius: 6px; text-align: center; }
        .stat-box h3 { margin: 0; font-size: 24px; color: #2563eb; }
        .stat-box p { margin: 5px 0 0; color: #666; font-size: 12px; }
        
        .section-tabs { display: flex; gap: 0; margin-bottom: 0; }
        .section-tab { padding: 12px 24px; background: #e5e7eb; border: none; cursor: pointer; font-size: 15px; font-weight: 600; border-radius: 8px 8px 0 0; }
        .section-tab.active { background: #2563eb; color: #fff; }
        
        .section-content { background: #fff; padding: 20px; border-radius: 0 8px 8px 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        
        .view-tabs { display: flex; gap: 8px; margin-bottom: 15px; flex-wrap: wrap; }
        .view-tab { padding: 8px 16px; background: #f3f4f6; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .view-tab.active { background: #10b981; color: #fff; }
        
        .controls { display: flex; gap: 15px; margin-bottom: 15px; align-items: center; flex-wrap: wrap; }
        .search-box { flex: 1; min-width: 250px; }
        .search-box input { width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        
        .export-btns { display: flex; gap: 8px; }
        .export-btn { padding: 8px 14px; background: #059669; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .export-btn:hover { background: #047857; }
        
        .view-toggle { display: flex; gap: 0; }
        .view-toggle button { padding: 8px 14px; background: #e5e7eb; border: none; cursor: pointer; font-size: 13px; }
        .view-toggle button:first-child { border-radius: 6px 0 0 6px; }
        .view-toggle button:last-child { border-radius: 0 6px 6px 0; }
        .view-toggle button.active { background: #6366f1; color: #fff; }
        
        table { width: 100%; border-collapse: collapse; background: #fff; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }
        th { background: #f8f9fa; font-weight: 600; color: #333; position: sticky; top: 0; }
        tr:hover { background: #f8f9fa; }
        
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .badge-green { background: #dcfce7; color: #166534; }
        .badge-blue { background: #dbeafe; color: #1e40af; }
        .badge-yellow { background: #fef3c7; color: #92400e; }
        .badge-gray { background: #f3f4f6; color: #374151; }
        .badge-purple { background: #ede9fe; color: #5b21b6; }
        
        .expandable { cursor: pointer; }
        .expandable:hover { background: #e0f2fe; }
        .expand-icon { display: inline-block; width: 20px; color: #2563eb; font-weight: bold; }
        .child-row { background: #fafafa; }
        .child-row td:first-child { padding-left: 40px; }
        .hidden { display: none; }
        
        .specs { font-size: 11px; color: #666; max-width: 350px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .pagination { margin-top: 15px; display: flex; gap: 10px; align-items: center; }
        .pagination button { padding: 8px 16px; border: 1px solid #ddd; background: #fff; border-radius: 4px; cursor: pointer; }
        .pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .table-container { max-height: 550px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; }
        
        .loading { text-align: center; padding: 40px; color: #666; }
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
                <h3>{{ stats.total_terms }}</h3>
                <p>Normalized Terms</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.compiled_terms }}</h3>
                <p>Compiled Terms</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_specs }}</h3>
                <p>With Seed Specs</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_compiled }}</h3>
                <p>With Compiled Specs</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.from_cosing }}</h3>
                <p>CosIng Source</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.from_tgsc }}</h3>
                <p>TGSC Source</p>
            </div>
        </div>
    </div>
    
    <div class="section-tabs">
        <button class="section-tab active" onclick="switchSection('raw')">Raw Data</button>
        <button class="section-tab" onclick="switchSection('compiled')">Post-Compilation</button>
    </div>
    
    <div class="section-content">
        <div id="raw-section">
            <div class="view-tabs" id="raw-tabs">
                <button class="view-tab active" onclick="loadView('raw', 'terms')">Terms (Clusters)</button>
                <button class="view-tab" onclick="loadView('raw', 'items')">All Items</button>
                <button class="view-tab" onclick="loadView('raw', 'merged')">Merged Items</button>
                <button class="view-tab" onclick="loadView('raw', 'source_items')">Source Items</button>
                <button class="view-tab" onclick="loadView('raw', 'cosing')">CosIng</button>
                <button class="view-tab" onclick="loadView('raw', 'tgsc')">TGSC</button>
            </div>
        </div>
        
        <div id="compiled-section" class="hidden">
            <div class="view-tabs" id="compiled-tabs">
                <button class="view-tab active" onclick="loadView('compiled', 'terms')">Compiled Terms</button>
                <button class="view-tab" onclick="loadView('compiled', 'items')">Compiled Items</button>
                <button class="view-tab" onclick="loadView('compiled', 'with_specs')">With Seed Specs</button>
            </div>
        </div>
        
        <div class="controls">
            <div class="search-box">
                <input type="text" id="search" placeholder="Search terms or items..." onkeyup="debounceSearch()">
            </div>
            <div class="view-toggle">
                <button id="toggle-terms" class="active" onclick="setViewMode('terms')">Terms View</button>
                <button id="toggle-items" onclick="setViewMode('items')">Items View</button>
            </div>
            <div class="export-btns">
                <button class="export-btn" onclick="exportCSV()">Export CSV</button>
                <button class="export-btn" onclick="exportJSON()">Export JSON</button>
            </div>
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
            <span id="total-info" style="margin-left: 20px; color: #666;"></span>
        </div>
    </div>
    
    <script>
        let currentSection = 'raw';
        let currentView = 'terms';
        let viewMode = 'terms';
        let currentPage = 1;
        let totalPages = 1;
        let totalItems = 0;
        let searchTimeout;
        let expandedTerms = new Set();
        
        function switchSection(section) {
            currentSection = section;
            currentPage = 1;
            expandedTerms.clear();
            
            document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('raw-section').classList.toggle('hidden', section !== 'raw');
            document.getElementById('compiled-section').classList.toggle('hidden', section !== 'compiled');
            
            currentView = 'terms';
            document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`#${section}-section .view-tab`).classList.add('active');
            
            loadData();
        }
        
        function loadView(section, view) {
            currentView = view;
            currentPage = 1;
            expandedTerms.clear();
            
            document.querySelectorAll(`#${section}-section .view-tab`).forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            loadData();
        }
        
        function setViewMode(mode) {
            viewMode = mode;
            currentPage = 1;
            expandedTerms.clear();
            
            document.getElementById('toggle-terms').classList.toggle('active', mode === 'terms');
            document.getElementById('toggle-items').classList.toggle('active', mode === 'items');
            
            loadData();
        }
        
        function debounceSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => { currentPage = 1; loadData(); }, 300);
        }
        
        function loadData() {
            const search = document.getElementById('search').value;
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '<tr><td colspan="10" class="loading">Loading...</td></tr>';
            
            fetch(`/api/data?section=${currentSection}&view=${currentView}&mode=${viewMode}&page=${currentPage}&search=${encodeURIComponent(search)}`)
                .then(r => r.json())
                .then(data => {
                    totalPages = data.total_pages;
                    totalItems = data.total;
                    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
                    document.getElementById('total-info').textContent = `${totalItems.toLocaleString()} total`;
                    document.getElementById('prev-btn').disabled = currentPage <= 1;
                    document.getElementById('next-btn').disabled = currentPage >= totalPages;
                    
                    const thead = document.getElementById('table-head');
                    thead.innerHTML = '<tr>' + data.columns.map(c => `<th>${c}</th>`).join('') + '</tr>';
                    
                    if (data.hierarchical) {
                        renderHierarchical(data.rows);
                    } else {
                        tbody.innerHTML = data.rows.map(row => 
                            '<tr>' + row.map(cell => `<td>${formatCell(cell)}</td>`).join('') + '</tr>'
                        ).join('');
                    }
                });
        }
        
        function renderHierarchical(rows) {
            const tbody = document.getElementById('table-body');
            let html = '';
            
            rows.forEach(row => {
                const termKey = row[0];
                const isExpanded = expandedTerms.has(termKey);
                const expandIcon = isExpanded ? '▼' : '▶';
                
                html += `<tr class="expandable" onclick="toggleTerm('${termKey}')">`;
                html += `<td><span class="expand-icon">${expandIcon}</span> ${formatCell(row[0])}</td>`;
                for (let i = 1; i < row.length; i++) {
                    html += `<td>${formatCell(row[i])}</td>`;
                }
                html += '</tr>';
                
                html += `<tr class="child-row ${isExpanded ? '' : 'hidden'}" id="items-${termKey}">`;
                html += `<td colspan="${row.length}"><div class="loading">Loading items...</div></td>`;
                html += '</tr>';
            });
            
            tbody.innerHTML = html;
            
            expandedTerms.forEach(term => {
                loadTermItems(term);
            });
        }
        
        function toggleTerm(term) {
            event.stopPropagation();
            
            if (expandedTerms.has(term)) {
                expandedTerms.delete(term);
                document.getElementById(`items-${term}`).classList.add('hidden');
                const row = event.currentTarget;
                row.querySelector('.expand-icon').textContent = '▶';
            } else {
                expandedTerms.add(term);
                document.getElementById(`items-${term}`).classList.remove('hidden');
                const row = event.currentTarget;
                row.querySelector('.expand-icon').textContent = '▼';
                loadTermItems(term);
            }
        }
        
        function loadTermItems(term) {
            fetch(`/api/term-items?section=${currentSection}&term=${encodeURIComponent(term)}`)
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById(`items-${term}`);
                    if (data.items.length === 0) {
                        container.innerHTML = '<td colspan="10" style="padding-left: 40px; color: #666; font-style: italic;">No items assigned</td>';
                    } else {
                        let html = '<td colspan="10"><table style="width: 100%; margin-left: 20px;">';
                        html += '<tr style="background: #e5e7eb;"><th>Item</th><th>Form</th><th>CosIng</th><th>TGSC</th><th>Specs</th></tr>';
                        data.items.forEach(item => {
                            html += `<tr>
                                <td>${item.term}</td>
                                <td>${item.form || '-'}</td>
                                <td>${item.has_cosing ? '<span class="badge badge-green">Yes</span>' : '-'}</td>
                                <td>${item.has_tgsc ? '<span class="badge badge-blue">Yes</span>' : '-'}</td>
                                <td>${item.has_specs ? '<span class="badge badge-purple">Yes</span>' : '-'}</td>
                            </tr>`;
                        });
                        html += '</table></td>';
                        container.innerHTML = html;
                    }
                });
        }
        
        function formatCell(val) {
            if (val === null || val === '' || val === undefined) return '<span class="badge badge-gray">-</span>';
            if (typeof val === 'string' && val.startsWith('{')) {
                try {
                    const obj = JSON.parse(val);
                    const preview = Object.entries(obj).slice(0, 3).map(([k,v]) => `${k}: ${typeof v === 'object' ? '...' : v}`).join(', ');
                    return `<span class="specs" title="${val.replace(/"/g, '&quot;')}">${preview}</span>`;
                } catch { return val; }
            }
            if (val === 'Yes' || val === 1 || val === true) return '<span class="badge badge-green">Yes</span>';
            if (val === 'No' || val === 0 || val === false) return '<span class="badge badge-gray">No</span>';
            return val;
        }
        
        function prevPage() { if (currentPage > 1) { currentPage--; loadData(); } }
        function nextPage() { if (currentPage < totalPages) { currentPage++; loadData(); } }
        
        function exportCSV() {
            const search = document.getElementById('search').value;
            window.location.href = `/api/export/csv?section=${currentSection}&view=${currentView}&mode=${viewMode}&search=${encodeURIComponent(search)}`;
        }
        
        function exportJSON() {
            const search = document.getElementById('search').value;
            window.location.href = `/api/export/json?section=${currentSection}&view=${currentView}&mode=${viewMode}&search=${encodeURIComponent(search)}`;
        }
        
        loadData();
    </script>
</body>
</html>
"""

def get_db(db_type='final'):
    path = FINAL_DB_PATH if db_type == 'final' else BACKUP_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db('final')
    cur = conn.cursor()
    
    stats = {}
    cur.execute("SELECT COUNT(*) FROM merged_item_forms")
    stats['total_items'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM normalized_terms")
    stats['total_terms'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM ingredients")
    stats['compiled_terms'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE app_seed_specs_json IS NOT NULL")
    stats['with_specs'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL")
    stats['with_compiled'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1")
    stats['from_cosing'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1")
    stats['from_tgsc'] = cur.fetchone()[0]
    
    conn.close()
    return render_template_string(HTML_TEMPLATE, stats=stats)

@app.route('/api/data')
def api_data():
    section = request.args.get('section', 'raw')
    view = request.args.get('view', 'terms')
    mode = request.args.get('mode', 'terms')
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '').strip()
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db('final')
    cur = conn.cursor()
    
    hierarchical = False
    columns = []
    rows = []
    total = 0
    
    search_param = f"%{search}%" if search else "%"
    
    if section == 'raw':
        if mode == 'items' and view == 'terms':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, has_cosing, has_tgsc,
                       CASE WHEN app_seed_specs_json IS NOT NULL THEN 'Yes' ELSE '-' END,
                       CASE WHEN compiled_specs_json IS NOT NULL THEN 'Yes' ELSE '-' END
                FROM merged_item_forms WHERE derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'CosIng', 'TGSC', 'Specs', 'Compiled']
            
        elif view == 'terms':
            hierarchical = True
            cur.execute("SELECT COUNT(*) FROM normalized_terms WHERE term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT term, inci_name, botanical_name, ingredient_category, origin,
                       (SELECT COUNT(*) FROM merged_item_forms WHERE derived_term = normalized_terms.term) as item_count
                FROM normalized_terms WHERE term LIKE ?
                ORDER BY term LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['Term', 'INCI Name', 'Botanical', 'Category', 'Origin', 'Items']
            
        elif view == 'items':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, has_cosing, has_tgsc,
                       CASE WHEN app_seed_specs_json IS NOT NULL THEN 'Yes' ELSE '-' END,
                       CASE WHEN compiled_specs_json IS NOT NULL THEN 'Yes' ELSE '-' END
                FROM merged_item_forms WHERE derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'CosIng', 'TGSC', 'Specs', 'Compiled']
            
        elif view == 'merged':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE source_row_count > 1 AND derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, source_row_count, has_cosing, has_tgsc
                FROM merged_item_forms WHERE source_row_count > 1 AND derived_term LIKE ?
                ORDER BY source_row_count DESC LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'Sources Merged', 'CosIng', 'TGSC']
            
        elif view == 'source_items':
            cur.execute("SELECT COUNT(*) FROM source_items WHERE key LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT key, source, source_row_id, is_composite
                FROM source_items WHERE key LIKE ?
                ORDER BY key LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['Key', 'Source', 'Row ID', 'Composite']
            
        elif view == 'cosing':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, cas_numbers_json, source_row_count
                FROM merged_item_forms WHERE has_cosing = 1 AND derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'CAS Numbers', 'Row Count']
            
        elif view == 'tgsc':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1 AND derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, cas_numbers_json, source_row_count
                FROM merged_item_forms WHERE has_tgsc = 1 AND derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'CAS Numbers', 'Row Count']
    
    elif section == 'compiled':
        if mode == 'items' and view == 'terms':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL AND derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, compiled_specs_json
                FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL AND derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'Compiled Specs']
            
        elif view == 'terms':
            hierarchical = True
            cur.execute("SELECT COUNT(*) FROM ingredients WHERE term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT term, ingredient_category, origin, botanical_name, inci_name,
                       CASE WHEN prohibited_flag THEN 'Yes' ELSE 'No' END
                FROM ingredients WHERE term LIKE ?
                ORDER BY term LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['Term', 'Category', 'Origin', 'Botanical', 'INCI', 'Prohibited']
            
        elif view == 'items':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL AND derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, compiled_specs_json
                FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL AND derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'Compiled Specs']
            
        elif view == 'with_specs':
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE app_seed_specs_json IS NOT NULL AND derived_term LIKE ?", (search_param,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, app_seed_specs_json
                FROM merged_item_forms WHERE app_seed_specs_json IS NOT NULL AND derived_term LIKE ?
                ORDER BY id LIMIT ? OFFSET ?
            """, (search_param, per_page, offset))
            columns = ['ID', 'Term', 'Form', 'Seed Specs']
    
    rows = [list(row) for row in cur.fetchall()]
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    conn.close()
    return jsonify({
        'columns': columns, 
        'rows': rows, 
        'total_pages': total_pages,
        'total': total,
        'hierarchical': hierarchical
    })

@app.route('/api/term-items')
def api_term_items():
    section = request.args.get('section', 'raw')
    term = request.args.get('term', '')
    
    conn = get_db('final')
    cur = conn.cursor()
    
    if section == 'compiled':
        cur.execute("""
            SELECT derived_term, derived_physical_form, has_cosing, has_tgsc,
                   CASE WHEN app_seed_specs_json IS NOT NULL THEN 1 ELSE 0 END
            FROM merged_item_forms 
            WHERE derived_term = ? OR derived_term LIKE ?
            LIMIT 100
        """, (term, f"{term} %"))
    else:
        cur.execute("""
            SELECT derived_term, derived_physical_form, has_cosing, has_tgsc,
                   CASE WHEN app_seed_specs_json IS NOT NULL THEN 1 ELSE 0 END
            FROM merged_item_forms 
            WHERE derived_term = ?
            LIMIT 100
        """, (term,))
    
    items = []
    for row in cur.fetchall():
        items.append({
            'term': row[0],
            'form': row[1],
            'has_cosing': bool(row[2]),
            'has_tgsc': bool(row[3]),
            'has_specs': bool(row[4])
        })
    
    conn.close()
    return jsonify({'items': items})

@app.route('/api/export/<format>')
def api_export(format):
    section = request.args.get('section', 'raw')
    view = request.args.get('view', 'terms')
    mode = request.args.get('mode', 'terms')
    search = request.args.get('search', '').strip()
    
    conn = get_db('final')
    cur = conn.cursor()
    
    search_param = f"%{search}%" if search else "%"
    export_type = 'items' if mode == 'items' else view
    
    if section == 'raw':
        if export_type == 'terms':
            cur.execute("""
                SELECT term, inci_name, botanical_name, ingredient_category, origin, cas_number, description
                FROM normalized_terms WHERE term LIKE ? ORDER BY term
            """, (search_param,))
            columns = ['term', 'inci_name', 'botanical_name', 'ingredient_category', 'origin', 'cas_number', 'description']
        else:
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, has_cosing, has_tgsc, 
                       cas_numbers_json, source_row_count
                FROM merged_item_forms WHERE derived_term LIKE ? ORDER BY id
            """, (search_param,))
            columns = ['id', 'derived_term', 'derived_physical_form', 'has_cosing', 'has_tgsc', 'cas_numbers_json', 'source_row_count']
    else:
        if export_type == 'terms':
            cur.execute("""
                SELECT term, ingredient_category, origin, botanical_name, inci_name, cas_number,
                       short_description, prohibited_flag, gras_status
                FROM ingredients WHERE term LIKE ? ORDER BY term
            """, (search_param,))
            columns = ['term', 'ingredient_category', 'origin', 'botanical_name', 'inci_name', 'cas_number', 'short_description', 'prohibited_flag', 'gras_status']
        else:
            cur.execute("""
                SELECT id, derived_term, derived_physical_form, app_seed_specs_json, compiled_specs_json
                FROM merged_item_forms WHERE (app_seed_specs_json IS NOT NULL OR compiled_specs_json IS NOT NULL) AND derived_term LIKE ? ORDER BY id
            """, (search_param,))
            columns = ['id', 'derived_term', 'derived_physical_form', 'app_seed_specs_json', 'compiled_specs_json']
    
    rows = cur.fetchall()
    conn.close()
    
    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(list(row))
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={section}_{view}_export.csv'}
        )
    
    elif format == 'json':
        data = []
        for row in rows:
            data.append(dict(zip(columns, list(row))))
        
        return Response(
            json.dumps(data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={section}_{view}_export.json'}
        )
    
    return jsonify({'error': 'Invalid format'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
