#!/usr/bin/env python3
"""Portal view for Final DB - ingredient database viewer with hierarchical views and exports."""

import csv
import io
import json
import os
import sqlite3
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FINAL_DB_PATH = os.path.join(BASE_DIR, "output/Final DB.db")
BACKUP_DB_PATH = os.path.join(BASE_DIR, "output/Final DB backup.db")

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
        
        .item-row { cursor: pointer; }
        .item-row:hover { background: #e0f2fe !important; }
        
        .detail-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.3); z-index: 100; display: none; }
        .detail-overlay.active { display: block; }
        
        .detail-panel { position: fixed; top: 0; right: -600px; width: 600px; height: 100%; background: #fff; box-shadow: -4px 0 20px rgba(0,0,0,0.15); z-index: 101; transition: right 0.3s ease; overflow-y: auto; }
        .detail-panel.active { right: 0; }
        
        .detail-header { padding: 20px; background: #2563eb; color: #fff; position: sticky; top: 0; z-index: 10; }
        .detail-header h2 { margin: 0 0 5px; font-size: 18px; }
        .detail-header p { margin: 0; opacity: 0.8; font-size: 13px; }
        .detail-close { position: absolute; top: 15px; right: 15px; background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; padding: 5px 10px; }
        .detail-close:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }
        
        .detail-body { padding: 20px; }
        
        .detail-section { margin-bottom: 20px; }
        .detail-section h3 { font-size: 14px; color: #374151; margin: 0 0 10px; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; }
        
        .detail-grid { display: grid; grid-template-columns: 140px 1fr; gap: 8px; }
        .detail-label { font-size: 12px; color: #6b7280; font-weight: 500; }
        .detail-value { font-size: 13px; color: #111827; word-break: break-word; }
        
        .json-block { background: #f8f9fa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; margin-top: 8px; max-height: 300px; overflow-y: auto; }
        .json-block pre { margin: 0; font-size: 11px; white-space: pre-wrap; word-break: break-all; font-family: 'Monaco', 'Menlo', monospace; }
        
        .json-toggle { background: #f3f4f6; border: 1px solid #d1d5db; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; width: 100%; text-align: left; margin-top: 8px; }
        .json-toggle:hover { background: #e5e7eb; }
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
            <div class="stat-box">
                <h3>{{ stats.from_seed }}</h3>
                <p>Seed Source</p>
            </div>
        </div>
    </div>
    
    <div class="section-tabs">
        <button class="section-tab active" onclick="switchSection('raw')">Raw Data</button>
        <button class="section-tab" onclick="switchSection('compiled')">Post-Compilation</button>
    </div>
    
    <div class="section-content">
        <div id="raw-section">
            <div class="view-tabs">
                <button class="view-tab active" onclick="loadFilter('all')">All Terms</button>
                <button class="view-tab" onclick="loadFilter('with_specs')">With Specs</button>
                <button class="view-tab" onclick="loadFilter('cosing')">CosIng Only</button>
                <button class="view-tab" onclick="loadFilter('tgsc')">TGSC Only</button>
                <button class="view-tab" onclick="loadFilter('merged')">Multi-Source</button>
            </div>
        </div>
        
        <div id="compiled-section" class="hidden">
            <div class="view-tabs">
                <button class="view-tab active" onclick="loadFilter('all')">All Compiled</button>
                <button class="view-tab" onclick="loadFilter('with_specs')">With Specs</button>
            </div>
        </div>
        
        <div class="controls">
            <div class="search-box">
                <input type="text" id="search" placeholder="Search terms..." onkeyup="debounceSearch()">
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
    
    <div class="detail-overlay" id="detail-overlay" onclick="closeDetail()"></div>
    <div class="detail-panel" id="detail-panel">
        <div class="detail-header">
            <button class="detail-close" onclick="closeDetail()">&times;</button>
            <h2 id="detail-title">Item Details</h2>
            <p id="detail-subtitle">Loading...</p>
        </div>
        <div class="detail-body" id="detail-body">
            <div class="loading">Loading item details...</div>
        </div>
    </div>
    
    <script>
        let currentSection = 'raw';
        let currentFilter = 'all';
        let currentPage = 1;
        let totalPages = 1;
        let totalItems = 0;
        let searchTimeout;
        let expandedTerms = new Set();
        
        function switchSection(section) {
            currentSection = section;
            currentFilter = 'all';
            currentPage = 1;
            expandedTerms.clear();
            
            document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('raw-section').classList.toggle('hidden', section !== 'raw');
            document.getElementById('compiled-section').classList.toggle('hidden', section !== 'compiled');
            
            document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`#${section}-section .view-tab`).classList.add('active');
            
            loadData();
        }
        
        function loadFilter(filter) {
            currentFilter = filter;
            currentPage = 1;
            expandedTerms.clear();
            
            document.querySelectorAll(`#${currentSection}-section .view-tab`).forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
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
            
            fetch(`/api/data?section=${currentSection}&filter=${currentFilter}&page=${currentPage}&search=${encodeURIComponent(search)}`)
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
                    
                    renderHierarchical(data.rows);
                });
        }
        
        function renderHierarchical(rows) {
            const tbody = document.getElementById('table-body');
            let html = '';
            
            rows.forEach((row, idx) => {
                const termKey = row[0];
                const safeId = 'term-' + idx;
                const isExpanded = expandedTerms.has(termKey);
                const expandIcon = isExpanded ? '▼' : '▶';
                
                html += `<tr class="expandable" data-term="${encodeURIComponent(termKey)}" data-idx="${idx}">`;
                html += `<td><span class="expand-icon">${expandIcon}</span> ${formatCell(row[0])}</td>`;
                for (let i = 1; i < row.length; i++) {
                    html += `<td>${formatCell(row[i])}</td>`;
                }
                html += '</tr>';
                
                html += `<tr class="child-row ${isExpanded ? '' : 'hidden'}" id="${safeId}">`;
                html += `<td colspan="${row.length}"><div class="loading">Loading items...</div></td>`;
                html += '</tr>';
            });
            
            tbody.innerHTML = html;
            
            tbody.querySelectorAll('.expandable').forEach(row => {
                row.addEventListener('click', function() {
                    const term = decodeURIComponent(this.dataset.term);
                    const idx = this.dataset.idx;
                    toggleTermByIdx(term, idx, this);
                });
            });
            
            expandedTerms.forEach(term => {
                const row = tbody.querySelector(`[data-term="${encodeURIComponent(term)}"]`);
                if (row) loadTermItemsByIdx(term, row.dataset.idx);
            });
        }
        
        function toggleTermByIdx(term, idx, rowEl) {
            const safeId = 'term-' + idx;
            if (expandedTerms.has(term)) {
                expandedTerms.delete(term);
                document.getElementById(safeId).classList.add('hidden');
                rowEl.querySelector('.expand-icon').textContent = '▶';
            } else {
                expandedTerms.add(term);
                document.getElementById(safeId).classList.remove('hidden');
                rowEl.querySelector('.expand-icon').textContent = '▼';
                loadTermItemsByIdx(term, idx);
            }
        }
        
        function loadTermItemsByIdx(term, idx) {
            const safeId = 'term-' + idx;
            fetch(`/api/term-items?section=${currentSection}&term=${encodeURIComponent(term)}`)
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById(safeId);
                    if (!container) return;
                    if (data.items.length === 0) {
                        container.innerHTML = '<td colspan="10" style="padding-left: 40px; color: #666; font-style: italic;">No items found</td>';
                    } else {
                        let html = '<td colspan="10"><table style="width: 100%; margin-left: 20px;">';
                        if (currentSection === 'compiled') {
                            html += '<tr style="background: #e5e7eb;"><th>Derived Term</th><th>Variation</th><th>Form</th><th>Sources</th><th>Specs</th></tr>';
                        } else {
                            html += '<tr style="background: #e5e7eb;"><th>Raw Name</th><th>Variation</th><th>Form</th><th>Category</th><th>Origin</th><th>Specs</th></tr>';
                        }
                        data.items.forEach(item => {
                            const hasId = item.id !== undefined;
                            const dataAttr = hasId ? `data-id="${item.id}"` : (item.key ? `data-key="${item.key}"` : '');
                            if (currentSection === 'compiled') {
                                html += `<tr class="item-row" ${dataAttr} style="cursor:pointer;">
                                    <td>${escapeHtml(item.raw_name || item.term)}</td>
                                    <td>${escapeHtml(item.variation) || '-'}</td>
                                    <td>${escapeHtml(item.form) || '-'}</td>
                                    <td>${item.source_count || '-'}</td>
                                    <td>${item.has_specs ? '<span class="badge badge-purple">Yes</span>' : '-'}</td>
                                </tr>`;
                            } else {
                                html += `<tr class="item-row" ${dataAttr} style="cursor:pointer;">
                                    <td>${escapeHtml(item.raw_name || item.term)}</td>
                                    <td>${escapeHtml(item.variation) || '-'}</td>
                                    <td>${escapeHtml(item.form) || '-'}</td>
                                    <td>${escapeHtml(item.category) || '-'}</td>
                                    <td>${escapeHtml(item.origin) || '-'}</td>
                                    <td>${item.has_specs ? '<span class="badge badge-purple">Yes</span>' : '-'}</td>
                                </tr>`;
                            }
                        });
                        html += '</table></td>';
                        container.innerHTML = html;
                        
                        container.querySelectorAll('.item-row').forEach(row => {
                            row.addEventListener('click', function(e) {
                                e.stopPropagation();
                                const id = this.dataset.id;
                                const key = this.dataset.key;
                                if (id) showItemDetail(id);
                                else if (key) showSourceItemDetail(key);
                            });
                        });
                    }
                });
        }
        
        function escapeHtml(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
        
        function showItemDetail(itemId) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading item details...</div>';
            document.getElementById('detail-title').textContent = 'Item #' + itemId;
            document.getElementById('detail-subtitle').textContent = 'Loading...';
            
            fetch(`/api/item/${itemId}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('detail-body').innerHTML = '<p style="color: red;">Error: ' + data.error + '</p>';
                        return;
                    }
                    
                    document.getElementById('detail-title').textContent = data.derived_term || 'Item #' + itemId;
                    document.getElementById('detail-subtitle').textContent = `ID: ${itemId} | Form: ${data.derived_physical_form || 'N/A'}`;
                    
                    let html = '';
                    
                    html += '<div class="detail-section"><h3>Basic Info</h3><div class="detail-grid">';
                    html += `<div class="detail-label">ID</div><div class="detail-value">${data.id}</div>`;
                    html += `<div class="detail-label">Term</div><div class="detail-value">${data.derived_term || '-'}</div>`;
                    html += `<div class="detail-label">Variation</div><div class="detail-value">${data.derived_variation || '-'}</div>`;
                    html += `<div class="detail-label">Physical Form</div><div class="detail-value">${data.derived_physical_form || '-'}</div>`;
                    html += `<div class="detail-label">Source Count</div><div class="detail-value">${data.source_row_count}</div>`;
                    html += `<div class="detail-label">Has CosIng</div><div class="detail-value">${data.has_cosing ? 'Yes' : 'No'}</div>`;
                    html += `<div class="detail-label">Has TGSC</div><div class="detail-value">${data.has_tgsc ? 'Yes' : 'No'}</div>`;
                    html += `<div class="detail-label">Created</div><div class="detail-value">${data.created_at || '-'}</div>`;
                    html += '</div></div>';
                    
                    if (data.cas_numbers && data.cas_numbers.length > 0) {
                        html += '<div class="detail-section"><h3>CAS Numbers</h3>';
                        html += '<div class="detail-value">' + data.cas_numbers.join(', ') + '</div></div>';
                    }
                    
                    if (data.app_seed_specs) {
                        html += '<div class="detail-section"><h3>Seed Specs</h3>';
                        html += renderJsonSection(data.app_seed_specs);
                        html += '</div>';
                    }
                    
                    if (data.compiled_specs) {
                        html += renderCompiledSpecs(data.compiled_specs);
                    }
                    
                    if (data.merged_specs) {
                        html += '<div class="detail-section"><h3>Merged Specs</h3>';
                        html += renderJsonSection(data.merged_specs);
                        html += '</div>';
                    }
                    
                    if (data.derived_parts && data.derived_parts.length > 0) {
                        html += '<div class="detail-section"><h3>Derived Parts</h3>';
                        html += '<div class="detail-value">' + data.derived_parts.join(', ') + '</div></div>';
                    }
                    
                    if (data.sources && data.sources.length > 0) {
                        html += '<div class="detail-section"><h3>Sources</h3>';
                        html += '<div class="detail-value">' + data.sources.join(', ') + '</div></div>';
                    }
                    
                    if (data.member_source_item_keys && data.member_source_item_keys.length > 0) {
                        html += '<div class="detail-section"><h3>Source Item Keys</h3>';
                        html += '<div class="json-block"><pre>' + data.member_source_item_keys.join('\\n') + '</pre></div></div>';
                    }
                    
                    document.getElementById('detail-body').innerHTML = html;
                });
        }
        
        function renderJsonSection(obj) {
            if (!obj || Object.keys(obj).length === 0) return '<div class="detail-value">-</div>';
            let html = '<div class="detail-grid">';
            for (const [key, value] of Object.entries(obj)) {
                html += `<div class="detail-label">${key}</div>`;
                if (typeof value === 'object' && value !== null) {
                    html += `<div class="detail-value"><pre style="margin:0;font-size:11px;">${JSON.stringify(value, null, 2)}</pre></div>`;
                } else {
                    html += `<div class="detail-value">${value ?? '-'}</div>`;
                }
            }
            html += '</div>';
            return html;
        }
        
        function renderCompiledSpecs(specs) {
            if (!specs) return '';
            let html = '';
            
            const ing = specs.ingredient || specs;
            
            html += '<div class="detail-section"><h3>Compiled Ingredient</h3><div class="detail-grid">';
            html += `<div class="detail-label">Common Name</div><div class="detail-value">${ing.common_name || '-'}</div>`;
            html += `<div class="detail-label">Category</div><div class="detail-value">${ing.category || '-'}</div>`;
            html += `<div class="detail-label">Botanical Name</div><div class="detail-value">${ing.botanical_name || '-'}</div>`;
            html += `<div class="detail-label">INCI Name</div><div class="detail-value">${ing.inci_name || '-'}</div>`;
            html += `<div class="detail-label">CAS Number</div><div class="detail-value">${ing.cas_number || '-'}</div>`;
            html += '</div></div>';
            
            if (ing.short_description) {
                html += '<div class="detail-section"><h3>Description</h3>';
                html += `<div class="detail-value">${ing.short_description}</div>`;
                if (ing.detailed_description) {
                    html += `<div class="detail-value" style="margin-top:8px;font-size:12px;color:#666;">${ing.detailed_description}</div>`;
                }
                html += '</div>';
            }
            
            if (ing.primary_functions && ing.primary_functions.length > 0) {
                html += '<div class="detail-section"><h3>Primary Functions</h3>';
                html += '<div class="detail-value">' + ing.primary_functions.map(f => `<span class="badge badge-green">${f}</span>`).join(' ') + '</div></div>';
            }
            
            if (ing.items && ing.items.length > 0) {
                html += '<div class="detail-section"><h3>Items (' + ing.items.length + ')</h3>';
                for (const item of ing.items) {
                    html += '<div style="border:1px solid #eee;padding:8px;margin:4px 0;border-radius:4px;">';
                    html += `<strong>${item.item_name || '-'}</strong>`;
                    if (item.variation) html += ` <span class="badge badge-gray">${item.variation}</span>`;
                    if (item.physical_form) html += ` <span class="badge badge-gray">${item.physical_form}</span>`;
                    if (item.variation_bypass) html += ` <span class="badge badge-green">Bypass</span>`;
                    if (item.function_tags && item.function_tags.length > 0) {
                        html += '<div style="margin-top:4px;">' + item.function_tags.map(t => `<span class="badge badge-green" style="font-size:10px;">${t}</span>`).join(' ') + '</div>';
                    }
                    if (item.applications && item.applications.length > 0) {
                        html += '<div style="margin-top:4px;font-size:11px;color:#666;">Applications: ' + item.applications.join(', ') + '</div>';
                    }
                    html += '</div>';
                }
                html += '</div>';
            }
            
            if (ing.taxonomy) {
                html += '<div class="detail-section"><h3>Taxonomy</h3><div class="detail-grid">';
                if (ing.taxonomy.color_profile && ing.taxonomy.color_profile.length > 0) {
                    html += `<div class="detail-label">Color</div><div class="detail-value">${ing.taxonomy.color_profile.join(', ')}</div>`;
                }
                if (ing.taxonomy.scent_profile && ing.taxonomy.scent_profile.length > 0) {
                    html += `<div class="detail-label">Scent</div><div class="detail-value">${ing.taxonomy.scent_profile.join(', ')}</div>`;
                }
                if (ing.taxonomy.texture_profile && ing.taxonomy.texture_profile.length > 0) {
                    html += `<div class="detail-label">Texture</div><div class="detail-value">${ing.taxonomy.texture_profile.join(', ')}</div>`;
                }
                html += '</div></div>';
            }
            
            if (specs.data_quality) {
                html += '<div class="detail-section"><h3>Data Quality</h3><div class="detail-grid">';
                html += `<div class="detail-label">Confidence</div><div class="detail-value">${(specs.data_quality.confidence * 100).toFixed(0)}%</div>`;
                if (specs.data_quality.caveats && specs.data_quality.caveats.length > 0) {
                    html += `<div class="detail-label">Notes</div><div class="detail-value">${specs.data_quality.caveats.join('; ')}</div>`;
                }
                html += '</div></div>';
            }
            
            return html;
        }
        
        function closeDetail() {
            document.getElementById('detail-overlay').classList.remove('active');
            document.getElementById('detail-panel').classList.remove('active');
        }
        
        function showSourceItemDetail(key) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading source item details...</div>';
            document.getElementById('detail-title').textContent = 'Source Item';
            document.getElementById('detail-subtitle').textContent = 'Loading...';
            
            fetch(`/api/source-item/${encodeURIComponent(key)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('detail-body').innerHTML = '<p style="color: red;">Error: ' + data.error + '</p>';
                        return;
                    }
                    
                    document.getElementById('detail-title').textContent = data.raw_name || 'Source Item';
                    document.getElementById('detail-subtitle').textContent = `Source: ${data.source} | Status: ${data.status}`;
                    
                    let html = '';
                    
                    html += '<div class="detail-section"><h3>Identity</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Key</div><div class="detail-value" style="font-size:10px;word-break:break-all;">${data.key}</div>`;
                    html += `<div class="detail-label">Source</div><div class="detail-value">${data.source}</div>`;
                    html += `<div class="detail-label">Raw Name</div><div class="detail-value">${data.raw_name || '-'}</div>`;
                    html += `<div class="detail-label">INCI Name</div><div class="detail-value">${data.inci_name || '-'}</div>`;
                    html += `<div class="detail-label">CAS Number</div><div class="detail-value">${data.cas_number || '-'}</div>`;
                    html += `<div class="detail-label">Display Name</div><div class="detail-value">${data.item_display_name || '-'}</div>`;
                    html += '</div></div>';
                    
                    html += '<div class="detail-section"><h3>Derivation</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Derived Term</div><div class="detail-value">${data.derived_term || '-'}</div>`;
                    html += `<div class="detail-label">Derived Variation</div><div class="detail-value">${data.derived_variation || '-'}</div>`;
                    html += `<div class="detail-label">Physical Form</div><div class="detail-value">${data.derived_physical_form || '-'}</div>`;
                    html += `<div class="detail-label">Derived Part</div><div class="detail-value">${data.derived_part || '-'}</div>`;
                    html += `<div class="detail-label">Part Reason</div><div class="detail-value">${data.derived_part_reason || '-'}</div>`;
                    html += '</div></div>';
                    
                    html += '<div class="detail-section"><h3>Classification</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Category</div><div class="detail-value">${data.ingredient_category || '-'}</div>`;
                    html += `<div class="detail-label">Origin</div><div class="detail-value">${data.origin || '-'}</div>`;
                    html += `<div class="detail-label">Refinement</div><div class="detail-value">${data.refinement_level || '-'}</div>`;
                    html += `<div class="detail-label">Status</div><div class="detail-value">${data.status || '-'}</div>`;
                    html += `<div class="detail-label">Review Reason</div><div class="detail-value">${data.needs_review_reason || '-'}</div>`;
                    html += '</div></div>';
                    
                    html += '<div class="detail-section"><h3>Bypass Flags</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Variation Bypass</div><div class="detail-value">${data.variation_bypass ? 'Yes' : 'No'}</div>`;
                    html += `<div class="detail-label">Bypass Reason</div><div class="detail-value">${data.variation_bypass_reason || '-'}</div>`;
                    html += `<div class="detail-label">Is Composite</div><div class="detail-value">${data.is_composite ? 'Yes' : 'No'}</div>`;
                    html += '</div></div>';
                    
                    if (data.master_categories && data.master_categories.length > 0) {
                        html += '<div class="detail-section"><h3>Master Categories</h3>';
                        html += '<div class="detail-value">' + data.master_categories.join(', ') + '</div></div>';
                    }
                    
                    if (data.function_tags && data.function_tags.length > 0) {
                        html += '<div class="detail-section"><h3>Function Tags</h3>';
                        html += '<div class="detail-value">' + data.function_tags.join(', ') + '</div></div>';
                    }
                    
                    if (data.specs) {
                        html += '<div class="detail-section"><h3>Specifications (SAP, Iodine, Density, etc.)</h3>';
                        html += renderJsonSection(data.specs);
                        html += '</div>';
                    }
                    
                    html += '<div class="detail-section"><h3>Cluster Info</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Cluster ID</div><div class="detail-value" style="font-size:10px;">${data.definition_cluster_id || '-'}</div>`;
                    html += `<div class="detail-label">Cluster Confidence</div><div class="detail-value">${data.definition_cluster_confidence ?? '-'}</div>`;
                    html += `<div class="detail-label">Cluster Reason</div><div class="detail-value">${data.definition_cluster_reason || '-'}</div>`;
                    html += `<div class="detail-label">Merged Item ID</div><div class="detail-value">${data.merged_item_id ?? '-'}</div>`;
                    html += '</div></div>';
                    
                    html += '<div class="detail-section"><h3>Source Reference</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Source Row ID</div><div class="detail-value">${data.source_row_id || '-'}</div>`;
                    html += `<div class="detail-label">Source Row #</div><div class="detail-value">${data.source_row_number ?? '-'}</div>`;
                    html += `<div class="detail-label">Source Ref</div><div class="detail-value" style="word-break:break-all;">${data.source_ref || '-'}</div>`;
                    html += `<div class="detail-label">Content Hash</div><div class="detail-value" style="font-size:10px;">${data.content_hash || '-'}</div>`;
                    html += `<div class="detail-label">Ingested At</div><div class="detail-value">${data.ingested_at || '-'}</div>`;
                    html += '</div></div>';
                    
                    document.getElementById('detail-body').innerHTML = html;
                });
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeDetail();
        });
        
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
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_seed = 1")
    stats['from_seed'] = cur.fetchone()[0]
    
    conn.close()
    return render_template_string(HTML_TEMPLATE, stats=stats)

@app.route('/api/data')
def api_data():
    section = request.args.get('section', 'raw')
    filter_type = request.args.get('filter', 'all')
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '').strip()
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db('final')
    cur = conn.cursor()
    
    columns = []
    rows = []
    total = 0
    
    search_param = f"%{search}%" if search else "%"
    
    if section == 'raw':
        base_query = "FROM normalized_terms WHERE term LIKE ?"
        extra_cond = ""
        
        if filter_type == 'with_specs':
            extra_cond = " AND EXISTS (SELECT 1 FROM source_items WHERE source_items.derived_term = normalized_terms.term AND derived_specs_json IS NOT NULL AND derived_specs_json != '{}')"
        elif filter_type == 'cosing':
            extra_cond = " AND EXISTS (SELECT 1 FROM source_items WHERE source_items.derived_term = normalized_terms.term AND source = 'cosing')"
        elif filter_type == 'tgsc':
            extra_cond = " AND EXISTS (SELECT 1 FROM source_items WHERE source_items.derived_term = normalized_terms.term AND source = 'tgsc')"
        elif filter_type == 'merged':
            extra_cond = " AND (SELECT COUNT(*) FROM source_items WHERE source_items.derived_term = normalized_terms.term) > 1"
        
        cur.execute(f"SELECT COUNT(*) {base_query}{extra_cond}", (search_param,))
        total = cur.fetchone()[0]
        
        cur.execute(f"""
            SELECT term, inci_name, botanical_name, ingredient_category, origin,
                   (SELECT COUNT(*) FROM source_items WHERE source_items.derived_term = normalized_terms.term) as item_count
            {base_query}{extra_cond}
            ORDER BY term LIMIT ? OFFSET ?
        """, (search_param, per_page, offset))
        columns = ['Term', 'INCI Name', 'Botanical', 'Category', 'Origin', 'Items']
    
    elif section == 'compiled':
        base_query = "FROM ingredients WHERE term LIKE ?"
        extra_cond = ""
        
        if filter_type == 'with_specs':
            extra_cond = " AND EXISTS (SELECT 1 FROM merged_item_forms WHERE merged_item_forms.derived_term = ingredients.term AND (app_seed_specs_json IS NOT NULL OR compiled_specs_json IS NOT NULL))"
        
        cur.execute(f"SELECT COUNT(*) {base_query}{extra_cond}", (search_param,))
        total = cur.fetchone()[0]
        
        cur.execute(f"""
            SELECT term, ingredient_category, origin, botanical_name, inci_name,
                   CASE WHEN prohibited_flag THEN 'Yes' ELSE 'No' END as prohibited,
                   (SELECT COUNT(*) FROM source_items WHERE source_items.derived_term = ingredients.term) as sources
            {base_query}{extra_cond}
            ORDER BY term LIMIT ? OFFSET ?
        """, (search_param, per_page, offset))
        columns = ['Term', 'Category', 'Origin', 'Botanical', 'INCI', 'Prohibited', 'Sources']
    
    rows = [list(row) for row in cur.fetchall()]
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    conn.close()
    return jsonify({
        'columns': columns, 
        'rows': rows, 
        'total_pages': total_pages,
        'total': total,
        'hierarchical': True
    })

@app.route('/api/term-items')
def api_term_items():
    section = request.args.get('section', 'raw')
    term = request.args.get('term', '')
    
    conn = get_db('final')
    cur = conn.cursor()
    
    if section == 'compiled':
        # For compiled section, show merged_item_forms that match the ingredient term
        # Use case-insensitive LIKE since seed terms are title case and source terms are uppercase
        search_term = f"%{term}%"
        cur.execute("""
            SELECT id, derived_term, derived_variation, derived_physical_form,
                   source_row_count,
                   CASE WHEN app_seed_specs_json IS NOT NULL OR compiled_specs_json IS NOT NULL THEN 1 ELSE 0 END as has_specs
            FROM merged_item_forms 
            WHERE LOWER(derived_term) LIKE LOWER(?)
            ORDER BY derived_term
            LIMIT 100
        """, (search_term,))
        
        items = []
        for row in cur.fetchall():
            items.append({
                'id': row[0],
                'raw_name': row[1],  # Use term as display name
                'term': row[1],
                'variation': row[2],
                'form': row[3],
                'source_count': row[4],
                'has_specs': bool(row[5])
            })
    else:
        # Raw section - show source_items for exact term match
        cur.execute("""
            SELECT key, raw_name, derived_term, derived_variation, derived_physical_form,
                   ingredient_category, origin,
                   CASE WHEN derived_specs_json IS NOT NULL AND derived_specs_json != '{}' THEN 1 ELSE 0 END as has_specs
            FROM source_items 
            WHERE derived_term = ?
            ORDER BY raw_name
            LIMIT 100
        """, (term,))
        
        items = []
        for row in cur.fetchall():
            items.append({
                'key': row[0],
                'raw_name': row[1],
                'term': row[2],
                'variation': row[3],
                'form': row[4],
                'category': row[5],
                'origin': row[6],
                'has_specs': bool(row[7])
            })
    
    conn.close()
    return jsonify({'items': items})

@app.route('/api/item/<int:item_id>')
def api_item_detail(item_id):
    conn = get_db('final')
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, derived_term, derived_variation, derived_physical_form,
               derived_parts_json, cas_numbers_json, member_source_item_keys_json,
               sources_json, merged_specs_json, merged_specs_sources_json,
               merged_specs_notes_json, source_row_count, has_cosing, has_tgsc,
               created_at, compiled_specs_json, app_seed_specs_json
        FROM merged_item_forms WHERE id = ?
    """, (item_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Item not found'})
    
    def parse_json(val):
        if val:
            try:
                return json.loads(val)
            except:
                return None
        return None
    
    return jsonify({
        'id': row[0],
        'derived_term': row[1],
        'derived_variation': row[2],
        'derived_physical_form': row[3],
        'derived_parts': parse_json(row[4]) or [],
        'cas_numbers': parse_json(row[5]) or [],
        'member_source_item_keys': parse_json(row[6]) or [],
        'sources': parse_json(row[7]) or [],
        'merged_specs': parse_json(row[8]),
        'merged_specs_sources': parse_json(row[9]),
        'merged_specs_notes': parse_json(row[10]),
        'source_row_count': row[11],
        'has_cosing': bool(row[12]),
        'has_tgsc': bool(row[13]),
        'created_at': row[14],
        'compiled_specs': parse_json(row[15]),
        'app_seed_specs': parse_json(row[16])
    })

@app.route('/api/source-item/<key>')
def api_source_item_detail(key):
    conn = get_db('final')
    cur = conn.cursor()
    
    cur.execute("""
        SELECT key, source, source_row_id, source_row_number, source_ref, content_hash,
               is_composite, raw_name, inci_name, cas_number, cas_numbers_json,
               derived_term, derived_variation, derived_physical_form, derived_part, derived_part_reason,
               origin, ingredient_category, refinement_level, status, needs_review_reason,
               definition_display_name, item_display_name, derived_function_tags_json,
               derived_function_tag_entries_json, derived_master_categories_json,
               variation_bypass, variation_bypass_reason, definition_cluster_id,
               definition_cluster_confidence, definition_cluster_reason,
               derived_specs_json, derived_specs_sources_json, derived_specs_notes_json,
               merged_item_id, payload_json, ingested_at
        FROM source_items WHERE key = ?
    """, (key,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Source item not found'})
    
    def parse_json(val):
        if val:
            try:
                return json.loads(val)
            except:
                return val
        return None
    
    return jsonify({
        'key': row[0],
        'source': row[1],
        'source_row_id': row[2],
        'source_row_number': row[3],
        'source_ref': row[4],
        'content_hash': row[5],
        'is_composite': bool(row[6]),
        'raw_name': row[7],
        'inci_name': row[8],
        'cas_number': row[9],
        'cas_numbers': parse_json(row[10]) or [],
        'derived_term': row[11],
        'derived_variation': row[12],
        'derived_physical_form': row[13],
        'derived_part': row[14],
        'derived_part_reason': row[15],
        'origin': row[16],
        'ingredient_category': row[17],
        'refinement_level': row[18],
        'status': row[19],
        'needs_review_reason': row[20],
        'definition_display_name': row[21],
        'item_display_name': row[22],
        'function_tags': parse_json(row[23]) or [],
        'function_tag_entries': parse_json(row[24]) or [],
        'master_categories': parse_json(row[25]) or [],
        'variation_bypass': bool(row[26]),
        'variation_bypass_reason': row[27],
        'definition_cluster_id': row[28],
        'definition_cluster_confidence': row[29],
        'definition_cluster_reason': row[30],
        'specs': parse_json(row[31]),
        'specs_sources': parse_json(row[32]),
        'specs_notes': parse_json(row[33]),
        'merged_item_id': row[34],
        'payload': parse_json(row[35]),
        'ingested_at': row[36]
    })

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
