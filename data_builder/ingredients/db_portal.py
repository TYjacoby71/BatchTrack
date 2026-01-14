#!/usr/bin/env python3
"""Portal view for Final DB - merged ingredient database viewer with Venn-style source filtering."""

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
        
        .stats { background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
        .stat-box { background: #f8f9fa; padding: 12px; border-radius: 6px; text-align: center; }
        .stat-box h3 { margin: 0; font-size: 24px; color: #2563eb; }
        .stat-box p { margin: 5px 0 0; color: #666; font-size: 12px; }
        
        .main-content { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        
        .filter-row { display: flex; gap: 20px; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; }
        .filter-section { }
        .filter-label { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 10px; }
        
        .view-toggle { display: flex; gap: 0; }
        .view-btn { padding: 10px 20px; background: #e5e7eb; border: 2px solid #d1d5db; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; }
        .view-btn:first-child { border-radius: 8px 0 0 8px; }
        .view-btn:last-child { border-radius: 0 8px 8px 0; }
        .view-btn.active { background: #7c3aed; color: #fff; border-color: #7c3aed; }
        .view-btn:hover:not(.active) { background: #d1d5db; }
        
        .venn-filters { display: flex; gap: 0; }
        .venn-btn { padding: 10px 20px; background: #e5e7eb; border: 2px solid #d1d5db; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; }
        .venn-btn:first-child { border-radius: 8px 0 0 8px; }
        .venn-btn:last-child { border-radius: 0 8px 8px 0; }
        .venn-btn.active { background: #2563eb; color: #fff; border-color: #2563eb; }
        .venn-btn:hover:not(.active) { background: #d1d5db; }
        .venn-btn .count { font-size: 11px; opacity: 0.8; margin-left: 4px; }
        
        .filter-info { font-size: 12px; color: #6b7280; margin-bottom: 15px; padding: 8px 12px; background: #f0f9ff; border-radius: 6px; border-left: 3px solid #2563eb; }
        
        .controls { display: flex; gap: 15px; margin-bottom: 15px; align-items: center; flex-wrap: wrap; }
        .search-box { flex: 1; min-width: 250px; }
        .search-box input { width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        
        .export-btns { display: flex; gap: 8px; }
        .export-btn { padding: 8px 14px; background: #059669; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
        .export-btn:hover { background: #047857; }
        
        table { width: 100%; border-collapse: collapse; background: #fff; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }
        th { background: #f8f9fa; font-weight: 600; color: #333; position: sticky; top: 0; }
        tr:hover { background: #f8f9fa; }
        
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-right: 4px; }
        .badge-cosing { background: #dbeafe; color: #1e40af; }
        .badge-tgsc { background: #fef3c7; color: #92400e; }
        .fallback { font-style: italic; color: #9ca3af; }
        .fallback::after { content: ' (not compiled)'; font-size: 10px; color: #d1d5db; }
        .curated { font-weight: 500; color: #1f2937; }
        .badge-both { background: #dcfce7; color: #166534; }
        .badge-specs { background: #ede9fe; color: #5b21b6; }
        
        .item-row { cursor: pointer; }
        .item-row:hover { background: #e0f2fe !important; }
        
        .term-row { cursor: pointer; }
        .term-row:hover { background: #f0fdf4 !important; }
        .expand-icon { display: inline-block; width: 20px; color: #7c3aed; font-weight: bold; }
        .child-row { background: #fafafa; }
        .child-row td:first-child { padding-left: 40px; }
        .child-row:hover { background: #e0f2fe !important; }
        
        .pagination { margin-top: 15px; display: flex; gap: 10px; align-items: center; }
        .pagination button { padding: 8px 16px; border: 1px solid #ddd; background: #fff; border-radius: 4px; cursor: pointer; }
        .pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .table-container { max-height: 600px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; }
        
        .loading { text-align: center; padding: 40px; color: #666; }
        
        .detail-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.3); z-index: 100; display: none; }
        .detail-overlay.active { display: block; }
        
        .detail-panel { position: fixed; top: 0; right: -650px; width: 650px; height: 100%; background: #fff; box-shadow: -4px 0 20px rgba(0,0,0,0.15); z-index: 101; transition: right 0.3s ease; overflow-y: auto; }
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
        
        .source-item { background: #f8f9fa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; margin-bottom: 10px; cursor: pointer; transition: all 0.2s; }
        .source-item:hover { background: #e0f2fe; border-color: #2563eb; }
        .source-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .source-item-name { font-weight: 600; font-size: 13px; }
        .source-item-details { font-size: 11px; color: #6b7280; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
        
        .json-block { background: #f8f9fa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; margin-top: 8px; max-height: 300px; overflow-y: auto; }
        .json-block pre { margin: 0; font-size: 11px; white-space: pre-wrap; word-break: break-all; font-family: 'Monaco', 'Menlo', monospace; }
        
        .source-detail-panel { position: fixed; top: 0; right: -500px; width: 500px; height: 100%; background: #fff; box-shadow: -4px 0 20px rgba(0,0,0,0.15); z-index: 102; transition: right 0.3s ease; overflow-y: auto; }
        .source-detail-panel.active { right: 0; }
        .source-detail-header { padding: 20px; background: #10b981; color: #fff; position: sticky; top: 0; z-index: 10; }
    </style>
</head>
<body>
    <h1>Final DB Portal</h1>
    
    <div class="stats">
        <div class="stats-grid">
            <div class="stat-box">
                <h3>{{ stats.total_terms }}</h3>
                <p>Terms</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.total_merged }}</h3>
                <p>Merged Items</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.cosing_only }}</h3>
                <p>CosIng Only</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.tgsc_only }}</h3>
                <p>TGSC Only</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.both_sources }}</h3>
                <p>Both Sources</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.with_specs }}</h3>
                <p>With Specs</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.total_clusters }}</h3>
                <p>Clusters</p>
            </div>
            <div class="stat-box">
                <h3>{{ stats.multi_item_clusters }}</h3>
                <p>Multi-Item Clusters</p>
            </div>
        </div>
    </div>
    
    <div class="main-content">
        <div class="filter-row">
            <div class="filter-section">
                <div class="filter-label">View Mode</div>
                <div class="view-toggle">
                    <button class="view-btn active" data-view="terms" onclick="setView('terms')">Terms</button>
                    <button class="view-btn" data-view="items" onclick="setView('items')">Items</button>
                    <button class="view-btn" data-view="clusters" onclick="setView('clusters')">Clusters</button>
                </div>
            </div>
            <div class="filter-section">
                <div class="filter-label">Source Filter (Venn Style)</div>
                <div class="venn-filters">
                    <button class="venn-btn active" data-filter="all" onclick="setFilter('all')">
                        All
                    </button>
                    <button class="venn-btn" data-filter="cosing" onclick="setFilter('cosing')">
                        CosIng
                    </button>
                    <button class="venn-btn" data-filter="tgsc" onclick="setFilter('tgsc')">
                        TGSC
                    </button>
                    <button class="venn-btn" data-filter="both" onclick="setFilter('both')">
                        Both
                    </button>
                    <button class="venn-btn" data-filter="pubchem" onclick="setFilter('pubchem')" style="margin-left:10px; background:#10b981; color:#fff; border-color:#10b981;">
                        PubChem
                    </button>
                </div>
            </div>
            <div class="filter-section" id="cluster-filters" style="display:none;">
                <div class="filter-label">Cluster Size</div>
                <div class="venn-filters">
                    <button class="venn-btn active" data-cluster="all" onclick="setClusterSize('all')">All</button>
                    <button class="venn-btn" data-cluster="multi" onclick="setClusterSize('multi')" style="background:#dcfce7;color:#166534;border-color:#86efac;">Multi-Item</button>
                    <button class="venn-btn" data-cluster="single" onclick="setClusterSize('single')" style="background:#fee2e2;color:#991b1b;border-color:#fca5a5;">Single-Item</button>
                </div>
            </div>
            <div class="filter-section">
                <div class="filter-label">Primary Category</div>
                <select id="category-filter" onchange="setCategoryFilter(this.value)" style="padding:10px 14px; border:2px solid #d1d5db; border-radius:8px; font-size:14px; min-width:200px; background:#fff;">
                    <option value="">All Categories</option>
                </select>
            </div>
        </div>
        
        <div class="filter-info" id="filter-info">
            Showing all terms from all sources.
        </div>
        
        <div class="controls">
            <div class="search-box">
                <input type="text" id="search" placeholder="Search terms, CAS numbers..." onkeyup="debounceSearch()">
            </div>
            <div class="export-btns">
                <button class="export-btn" onclick="exportData('csv')">Export CSV</button>
                <button class="export-btn" onclick="exportData('json')">Export JSON</button>
                <button class="export-btn" onclick="exportAnalysis()" style="background:#7c3aed;">Export Analysis CSV</button>
            </div>
        </div>
        
        <div class="table-container">
            <table>
                <thead id="table-head">
                    <tr>
                        <th>Term</th>
                        <th>Items</th>
                        <th>Sources</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                    <tr><td colspan="6" class="loading">Loading...</td></tr>
                </tbody>
            </table>
        </div>
        
        <div class="pagination">
            <button onclick="prevPage()" id="prev-btn" disabled>Previous</button>
            <span id="page-info">Page 1 of 1</span>
            <button onclick="nextPage()" id="next-btn" disabled>Next</button>
            <span id="total-info" style="margin-left: 20px; color: #666;"></span>
        </div>
    </div>
    
    <div class="detail-overlay" id="detail-overlay" onclick="closeDetail()"></div>
    <div class="detail-panel" id="detail-panel">
        <div class="detail-header">
            <button class="detail-close" onclick="closeDetail()">&times;</button>
            <h2 id="detail-title">Item Details</h2>
            <p id="detail-subtitle"></p>
        </div>
        <div class="detail-body" id="detail-body"></div>
    </div>
    
    <div class="source-detail-panel" id="source-detail-panel">
        <div class="source-detail-header">
            <button class="detail-close" onclick="closeSourceDetail()">&times;</button>
            <h2 id="source-detail-title">Source Item Details</h2>
            <p id="source-detail-subtitle"></p>
        </div>
        <div class="detail-body" id="source-detail-body"></div>
    </div>
    
    <script>
        let currentPage = 1;
        let totalPages = 1;
        let currentFilter = 'all';
        let currentCategory = '';
        let currentView = 'terms';
        let currentClusterSize = 'all';
        let searchTimeout = null;
        let expandedTerms = new Set();
        
        function loadCategories() {
            fetch('/api/categories')
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('category-filter');
                    data.categories.forEach(cat => {
                        const opt = document.createElement('option');
                        opt.value = cat.name;
                        opt.textContent = `${cat.name} (${cat.count})`;
                        select.appendChild(opt);
                    });
                });
        }
        
        function setCategoryFilter(category) {
            currentCategory = category;
            currentPage = 1;
            expandedTerms.clear();
            updateFilterInfo();
            loadData();
        }
        
        const filterDescriptions = {
            'all': 'Showing all {view} from all sources.',
            'cosing': 'Showing {view} that have CosIng as a source (may also have TGSC).',
            'tgsc': 'Showing {view} that have TGSC as a source (may also have CosIng).',
            'both': 'Showing only {view} that have BOTH CosIng AND TGSC sources (intersection).',
            'pubchem': 'Showing only {view} that have PubChem enrichment data.'
        };
        
        function updateFilterInfo() {
            const viewName = currentView === 'terms' ? 'terms' : (currentView === 'clusters' ? 'clusters' : 'items');
            let info = filterDescriptions[currentFilter].replace('{view}', viewName);
            if (currentCategory) {
                info += ` Filtered to: ${currentCategory}`;
            }
            if (currentView === 'clusters') {
                info = 'Showing source item clusters - items grouped by what the system expects to merge together.';
            }
            document.getElementById('filter-info').textContent = info;
        }
        
        function setView(view) {
            currentView = view;
            currentPage = 1;
            expandedTerms.clear();
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.view === view);
            });
            document.getElementById('cluster-filters').style.display = view === 'clusters' ? 'block' : 'none';
            updateFilterInfo();
            updateTableHeaders();
            loadData();
        }
        
        function setClusterSize(size) {
            currentClusterSize = size;
            currentPage = 1;
            document.querySelectorAll('[data-cluster]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.cluster === size);
            });
            loadData();
        }
        
        function setFilter(filter) {
            currentFilter = filter;
            currentPage = 1;
            expandedTerms.clear();
            document.querySelectorAll('.venn-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.filter === filter);
            });
            updateFilterInfo();
            loadData();
        }
        
        function updateTableHeaders() {
            const thead = document.getElementById('table-head');
            if (currentView === 'terms') {
                thead.innerHTML = '<tr><th>Derived Term</th><th>Items</th><th>Sources</th><th>Category</th></tr>';
            } else if (currentView === 'clusters') {
                thead.innerHTML = '<tr><th>Cluster ID</th><th>Canonical Term</th><th>Merged Items</th><th>Sources</th></tr>';
            } else {
                thead.innerHTML = '<tr><th>Derived Term</th><th>Variation</th><th>Form</th><th>Sources</th><th>CAS Numbers</th><th>Specs</th></tr>';
            }
        }
        
        function debounceSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentPage = 1;
                expandedTerms.clear();
                loadData();
            }, 300);
        }
        
        function loadData() {
            const search = document.getElementById('search').value;
            const tbody = document.getElementById('table-body');
            const colSpan = currentView === 'terms' ? 4 : (currentView === 'clusters' ? 5 : 6);
            tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">Loading...</td></tr>`;
            
            let endpoint;
            if (currentView === 'terms') {
                endpoint = '/api/terms';
            } else if (currentView === 'clusters') {
                endpoint = '/api/clusters';
            } else {
                endpoint = '/api/merged-items';
            }
            
            fetch(`${endpoint}?filter=${currentFilter}&page=${currentPage}&search=${encodeURIComponent(search)}&category=${encodeURIComponent(currentCategory)}&cluster_size=${currentClusterSize}`)
                .then(r => r.json())
                .then(data => {
                    totalPages = data.total_pages;
                    
                    if ((data.items || data.terms || data.clusters || []).length === 0) {
                        tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">No items found</td></tr>`;
                    } else if (currentView === 'terms') {
                        renderTermsView(data.terms);
                    } else if (currentView === 'clusters') {
                        renderClustersView(data.clusters);
                    } else {
                        renderItemsView(data.items);
                    }
                    
                    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
                    document.getElementById('total-info').textContent = `${data.total} total`;
                    document.getElementById('prev-btn').disabled = currentPage <= 1;
                    document.getElementById('next-btn').disabled = currentPage >= totalPages;
                });
        }
        
        function renderTermsView(terms) {
            const tbody = document.getElementById('table-body');
            let html = '';
            
            terms.forEach(term => {
                const isExpanded = expandedTerms.has(term.term);
                const sourceBadges = [];
                if (term.has_cosing && term.has_tgsc) {
                    sourceBadges.push('<span class="badge badge-both">Both</span>');
                } else if (term.has_cosing) {
                    sourceBadges.push('<span class="badge badge-cosing">CosIng</span>');
                } else if (term.has_tgsc) {
                    sourceBadges.push('<span class="badge badge-tgsc">TGSC</span>');
                }
                
                html += `<tr class="term-row" onclick="toggleTerm('${term.term.replace(/'/g, "\\'")}')">
                    <td><span class="expand-icon">${isExpanded ? '▼' : '▶'}</span> <strong>${term.term}</strong></td>
                    <td>${term.item_count}</td>
                    <td>${sourceBadges.join('')}</td>
                    <td>${term.category || '-'}</td>
                </tr>`;
                
                if (isExpanded && term.items) {
                    term.items.forEach(item => {
                        const itemSrcBadge = item.has_cosing && item.has_tgsc ? 
                            '<span class="badge badge-both">Both</span>' :
                            item.has_cosing ? '<span class="badge badge-cosing">CosIng</span>' : 
                            '<span class="badge badge-tgsc">TGSC</span>';
                        
                        html += `<tr class="child-row item-row" onclick="event.stopPropagation(); showDetail(${item.id})">
                            <td>${item.variation || item.term}</td>
                            <td>${item.form || '-'}</td>
                            <td>${itemSrcBadge}</td>
                            <td>${item.has_specs ? '<span class="badge badge-specs">Specs</span>' : '-'}</td>
                        </tr>`;
                    });
                }
            });
            
            tbody.innerHTML = html;
        }
        
        function renderItemsView(items) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = items.map(item => {
                const sourceBadges = [];
                if (item.has_cosing && item.has_tgsc) {
                    sourceBadges.push('<span class="badge badge-both">Both</span>');
                } else if (item.has_cosing) {
                    sourceBadges.push('<span class="badge badge-cosing">CosIng</span>');
                } else if (item.has_tgsc) {
                    sourceBadges.push('<span class="badge badge-tgsc">TGSC</span>');
                }
                
                const specsBadge = item.has_specs ? '<span class="badge badge-specs">Has Specs</span>' : '-';
                const casDisplay = item.cas_numbers ? item.cas_numbers.slice(0, 2).join(', ') + (item.cas_numbers.length > 2 ? '...' : '') : '-';
                
                return `<tr class="item-row" onclick="showDetail(${item.id})">
                    <td><strong>${item.term || '-'}</strong></td>
                    <td>${item.variation || '-'}</td>
                    <td>${item.form || '-'}</td>
                    <td>${sourceBadges.join('')} <small>(${item.source_count})</small></td>
                    <td style="font-size:11px;">${casDisplay}</td>
                    <td>${specsBadge}</td>
                </tr>`;
            }).join('');
        }
        
        function renderClustersView(clusters) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = clusters.map(cluster => {
                // Source badges
                const sourceBadges = [];
                if (cluster.cosing_count > 0 && cluster.tgsc_count > 0) {
                    sourceBadges.push(`<span class="badge badge-both">Both</span>`);
                } else if (cluster.cosing_count > 0) {
                    sourceBadges.push(`<span class="badge badge-cosing">CosIng</span>`);
                } else if (cluster.tgsc_count > 0) {
                    sourceBadges.push(`<span class="badge badge-tgsc">TGSC</span>`);
                } else {
                    sourceBadges.push('<span style="color:#9ca3af;">-</span>');
                }
                
                // Merged item count badge
                const countBadge = cluster.merged_item_count > 1 ? 
                    `<span class="badge badge-both">${cluster.merged_item_count}</span>` : 
                    cluster.merged_item_count > 0 ?
                    `<span class="badge" style="background:#fee2e2;color:#991b1b;">${cluster.merged_item_count}</span>` :
                    '<span style="color:#9ca3af;">0</span>';
                
                return `<tr class="item-row" onclick="showClusterDetail('${cluster.cluster_id.replace(/'/g, "\\'")}')">
                    <td style="font-size:11px; max-width:250px; overflow:hidden; text-overflow:ellipsis;" title="${cluster.cluster_id}">${cluster.cluster_id}</td>
                    <td><strong>${cluster.canonical_term || '-'}</strong></td>
                    <td>${countBadge}</td>
                    <td>${sourceBadges.join('')}</td>
                </tr>`;
            }).join('');
        }
        
        function showClusterDetail(clusterId) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading...</div>';
            
            fetch(`/api/cluster/${encodeURIComponent(clusterId)}`)
                .then(r => r.json())
                .then(data => {
                    // Helper to show curated vs fallback values
                    function showValue(curated, fallback, label) {
                        if (curated) {
                            return `<span class="curated">${curated}</span>`;
                        } else if (fallback) {
                            return `<span class="fallback">${fallback}</span>`;
                        }
                        return '-';
                    }
                    
                    document.getElementById('detail-title').textContent = data.canonical_term || data.derived_term || 'Cluster Details';
                    
                    let html = '<div class="detail-section"><h3>Cluster Info</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Cluster ID</div><div class="detail-value" style="font-size:11px;">${data.cluster_id}</div>`;
                    html += `<div class="detail-label">Reason</div><div class="detail-value">${data.reason || '-'}</div>`;
                    html += `<div class="detail-label">Common Name</div><div class="detail-value">${showValue(data.canonical_term, data.derived_term)}</div>`;
                    html += `<div class="detail-label">Botanical Key</div><div class="detail-value">${showValue(data.botanical_key, null)}</div>`;
                    if (data.reconciled_term) {
                        html += `<div class="detail-label">Reconciled Base</div><div class="detail-value"><span class="curated">${data.reconciled_term}</span></div>`;
                    }
                    if (data.reconciled_variation) {
                        html += `<div class="detail-label">Reconciled Variation</div><div class="detail-value"><span class="curated">${data.reconciled_variation}</span></div>`;
                    }
                    if (data.parent_cluster_id) {
                        html += `<div class="detail-label">Parent Cluster</div><div class="detail-value"><a href="#" onclick="event.preventDefault(); closeDetail(); showClusterDetail('${data.parent_cluster_id.replace(/'/g, "\\'")}')" style="color:#7c3aed;">${data.parent_cluster_id}</a></div>`;
                    }
                    html += `<div class="detail-label">Derived Term</div><div class="detail-value" style="font-size:11px;color:#6b7280;">${data.derived_term || '-'}</div>`;
                    html += '</div></div>';
                    
                    // Show child derivatives if any
                    if (data.child_derivatives && data.child_derivatives.length > 0) {
                        html += `<div class="detail-section"><h3>Derivatives (${data.child_derivatives.length})</h3>`;
                        html += '<p style="font-size:12px;color:#666;margin-bottom:10px;">Chemical/processed derivatives linked to this base ingredient:</p>';
                        data.child_derivatives.forEach(child => {
                            html += `<div class="source-item" onclick="closeDetail(); showClusterDetail('${child.cluster_id.replace(/'/g, "\\'")}')">
                                <div class="source-item-header">
                                    <span class="source-item-name">${child.canonical_term || child.cluster_id}</span>
                                    <span class="badge" style="background:#e0f2fe;color:#0369a1;">${child.variation || 'derivative'}</span>
                                </div>
                            </div>`;
                        });
                        html += '</div>';
                    }
                    
                    if (data.is_composite) {
                        // Composite clusters - show source items directly
                        document.getElementById('detail-subtitle').textContent = `Composite Cluster | ${data.source_items.length} source items`;
                        
                        html += '<div class="detail-section"><h3>Source Items (Composite)</h3>';
                        html += '<p style="font-size:12px;color:#666;margin-bottom:10px;">This is a composite ingredient blend:</p>';
                        
                        data.source_items.forEach(item => {
                            const srcBadge = item.source === 'cosing' ? 
                                '<span class="badge badge-cosing">CosIng</span>' : 
                                '<span class="badge badge-tgsc">TGSC</span>';
                            html += `<div class="source-item" onclick="showSourceDetail('${item.key.replace(/'/g, "\\'")}')">
                                <div class="source-item-header">
                                    <span class="source-item-name">${item.raw_name || item.key}</span>
                                    ${srcBadge}
                                </div>
                                <div class="source-item-details">
                                    <span>INCI: ${item.inci_name || '-'}</span>
                                    <span>CAS: ${item.cas_number || '-'}</span>
                                </div>
                            </div>`;
                        });
                        html += '</div>';
                    } else {
                        // Term clusters - show items categorized by source
                        document.getElementById('detail-subtitle').textContent = `${data.total_items} post-merge items`;
                        
                        // Helper to render item list
                        function renderItemList(items, badgeHtml) {
                            let itemHtml = '';
                            items.forEach(item => {
                                let displayName = item.derived_term || '';
                                if (item.derived_variation) displayName += `, ${item.derived_variation}`;
                                if (item.derived_physical_form) displayName += ` (${item.derived_physical_form})`;
                                
                                itemHtml += `<div class="source-item" onclick="showDetail(${item.id})">
                                    <div class="source-item-header">
                                        <span class="source-item-name">${displayName}</span>
                                        ${badgeHtml}
                                    </div>
                                    <div class="source-item-details">
                                        <span>INCI: ${item.inci_name || '-'}</span>
                                        <span>CAS: ${item.cas_number || '-'}</span>
                                    </div>
                                </div>`;
                            });
                            return itemHtml;
                        }
                        
                        // Deduplicated items (both sources)
                        if (data.both_sources && data.both_sources.length > 0) {
                            html += `<div class="detail-section"><h3>Deduplicated Items (${data.both_sources.length})</h3>`;
                            html += '<p style="font-size:12px;color:#666;margin-bottom:10px;">Items found in both CosIng and TGSC:</p>';
                            html += renderItemList(data.both_sources, '<span class="badge badge-cosing">CosIng</span> <span class="badge badge-tgsc">TGSC</span>');
                            html += '</div>';
                        }
                        
                        // CosIng-only items
                        if (data.cosing_only && data.cosing_only.length > 0) {
                            html += `<div class="detail-section"><h3>CosIng Only (${data.cosing_only.length})</h3>`;
                            html += '<p style="font-size:12px;color:#666;margin-bottom:10px;">Items only in CosIng database:</p>';
                            html += renderItemList(data.cosing_only, '<span class="badge badge-cosing">CosIng</span>');
                            html += '</div>';
                        }
                        
                        // TGSC-only items
                        if (data.tgsc_only && data.tgsc_only.length > 0) {
                            html += `<div class="detail-section"><h3>TGSC Only (${data.tgsc_only.length})</h3>`;
                            html += '<p style="font-size:12px;color:#666;margin-bottom:10px;">Items only in TGSC database:</p>';
                            html += renderItemList(data.tgsc_only, '<span class="badge badge-tgsc">TGSC</span>');
                            html += '</div>';
                        }
                    }
                    
                    document.getElementById('detail-body').innerHTML = html;
                });
        }
        
        function toggleTerm(term) {
            if (expandedTerms.has(term)) {
                expandedTerms.delete(term);
                loadData();
            } else {
                fetch(`/api/term-items?term=${encodeURIComponent(term)}&filter=${currentFilter}`)
                    .then(r => r.json())
                    .then(data => {
                        expandedTerms.add(term);
                        const search = document.getElementById('search').value;
                        fetch(`/api/terms?filter=${currentFilter}&page=${currentPage}&search=${encodeURIComponent(search)}`)
                            .then(r => r.json())
                            .then(termsData => {
                                const termObj = termsData.terms.find(t => t.term === term);
                                if (termObj) {
                                    termObj.items = data.items;
                                }
                                renderTermsView(termsData.terms);
                            });
                    });
            }
        }
        
        function prevPage() {
            if (currentPage > 1) {
                currentPage--;
                expandedTerms.clear();
                loadData();
            }
        }
        
        function nextPage() {
            if (currentPage < totalPages) {
                currentPage++;
                expandedTerms.clear();
                loadData();
            }
        }
        
        function showDetail(id) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading...</div>';
            
            fetch(`/api/merged-item/${id}`)
                .then(r => r.json())
                .then(data => {
                    // Helper to show curated vs fallback values
                    function showValue(curated, fallback) {
                        if (curated) {
                            return `<span class="curated">${curated}</span>`;
                        } else if (fallback) {
                            return `<span class="fallback">${fallback}</span>`;
                        }
                        return '-';
                    }
                    
                    document.getElementById('detail-title').textContent = data.derived_term || 'Unknown';
                    
                    const sources = [];
                    if (data.has_cosing) sources.push('CosIng');
                    if (data.has_tgsc) sources.push('TGSC');
                    document.getElementById('detail-subtitle').textContent = `Sources: ${sources.join(', ')} | ${data.source_row_count} source records`;
                    
                    let html = '';
                    const td = data.term_data || {};
                    const tc = data.term_cluster || {};
                    const rawName = (data.source_items && data.source_items.length > 0) ? data.source_items[0].raw_name : null;
                    
                    html += '<div class="detail-section"><h3>Item Info</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Term</div><div class="detail-value">${data.derived_term || '-'}</div>`;
                    html += `<div class="detail-label">Common Name</div><div class="detail-value">${showValue(tc.canonical_term, rawName)}</div>`;
                    html += `<div class="detail-label">Botanical Key</div><div class="detail-value">${showValue(tc.botanical_key, null)}</div>`;
                    html += `<div class="detail-label">Variation</div><div class="detail-value">${data.derived_variation || '-'}</div>`;
                    html += `<div class="detail-label">Physical Form</div><div class="detail-value">${data.derived_physical_form || '-'}</div>`;
                    html += `<div class="detail-label">CAS Numbers</div><div class="detail-value">${(data.cas_numbers || []).join(', ') || '-'}</div>`;
                    html += `<div class="detail-label">Master Categories</div><div class="detail-value">${(td.master_categories || []).join(', ') || '-'}</div>`;
                    html += '</div></div>';
                    
                    const specs = data.merged_specs || {};
                    const pubchem = specs.pubchem || {};
                    const otherSpecs = {};
                    for (const [k, v] of Object.entries(specs)) {
                        if (k !== 'pubchem') otherSpecs[k] = v;
                    }
                    
                    const fmt = (v) => {
                        if (v === null || v === undefined || v === '') return '-';
                        if (typeof v === 'object') return JSON.stringify(v);
                        return v;
                    };
                    
                    const pubchemOverlap = ['molecular_weight', 'molecular_weight_text', 'density', 'melting_point', 'boiling_point', 'flash_point', 'solubility'];
                    
                    html += '<div class="detail-section"><h3>Specifications</h3>';
                    html += '<div class="detail-grid">';
                    
                    html += `<div class="detail-label">PubChem CID</div><div class="detail-value">${pubchem.cid ? `<a href="https://pubchem.ncbi.nlm.nih.gov/compound/${pubchem.cid}" target="_blank">${pubchem.cid}</a>` : '-'}</div>`;
                    html += `<div class="detail-label">IUPAC Name</div><div class="detail-value">${fmt(pubchem.iupac_name)}</div>`;
                    html += `<div class="detail-label">Molecular Formula</div><div class="detail-value">${fmt(pubchem.molecular_formula)}</div>`;
                    html += `<div class="detail-label">Molecular Weight</div><div class="detail-value">${fmt(pubchem.molecular_weight || otherSpecs.molecular_weight)}</div>`;
                    html += `<div class="detail-label">InChI Key</div><div class="detail-value" style="font-size:10px;">${fmt(pubchem.inchi_key)}</div>`;
                    html += `<div class="detail-label">XLogP</div><div class="detail-value">${fmt(pubchem.xlogp)}</div>`;
                    html += `<div class="detail-label">TPSA</div><div class="detail-value">${fmt(pubchem.tpsa)}</div>`;
                    html += `<div class="detail-label">Density</div><div class="detail-value">${fmt(pubchem.density || otherSpecs.density)}</div>`;
                    html += `<div class="detail-label">Melting Point</div><div class="detail-value">${fmt(pubchem.melting_point || otherSpecs.melting_point)}</div>`;
                    html += `<div class="detail-label">Boiling Point</div><div class="detail-value">${fmt(pubchem.boiling_point || otherSpecs.boiling_point)}</div>`;
                    html += `<div class="detail-label">Flash Point</div><div class="detail-value">${fmt(pubchem.flash_point || otherSpecs.flash_point)}</div>`;
                    html += `<div class="detail-label">Solubility</div><div class="detail-value">${fmt(pubchem.solubility || otherSpecs.solubility)}</div>`;
                    html += `<div class="detail-label">Match Confidence</div><div class="detail-value">${pubchem.confidence ? pubchem.confidence + '%' : '-'}</div>`;
                    html += `<div class="detail-label">Matched By</div><div class="detail-value">${fmt(pubchem.matched_by)}</div>`;
                    
                    for (const [key, val] of Object.entries(otherSpecs)) {
                        if (!pubchemOverlap.includes(key)) {
                            html += `<div class="detail-label">${key}</div><div class="detail-value">${fmt(val)}</div>`;
                        }
                    }
                    
                    html += '</div></div>';
                    
                    html += '<div class="detail-section"><h3>Source Records</h3>';
                    html += '<p style="font-size:12px;color:#666;margin-bottom:10px;">Click to view pre-merge source data</p>';
                    
                    if (data.source_items && data.source_items.length > 0) {
                        data.source_items.forEach(src => {
                            const srcBadge = src.source === 'cosing' ? 
                                '<span class="badge badge-cosing">CosIng</span>' : 
                                '<span class="badge badge-tgsc">TGSC</span>';
                            html += `<div class="source-item" onclick="showSourceDetail('${src.key}')">
                                <div class="source-item-header">
                                    <span class="source-item-name">${src.raw_name || src.key}</span>
                                    ${srcBadge}
                                </div>
                                <div class="source-item-details">
                                    <span>INCI: ${src.inci_name || '-'}</span>
                                    <span>CAS: ${src.cas_number || '-'}</span>
                                </div>
                            </div>`;
                        });
                    } else {
                        html += '<p style="color:#999;">No source records available</p>';
                    }
                    html += '</div>';
                    
                    html += '<div class="detail-section"><h3>Term Data</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Origin</div><div class="detail-value">${td.origin || '-'}</div>`;
                    html += `<div class="detail-label">Primary Ingredient Category</div><div class="detail-value">${td.ingredient_category || '-'}</div>`;
                    html += `<div class="detail-label">INCI Name</div><div class="detail-value">${td.inci_name || '-'}</div>`;
                    const clusterIds = (tc.cluster_ids || []).filter(x => x);
                    const clusterTerms = (tc.cluster_terms || []).filter(x => x);
                    if (clusterIds.length > 0) {
                        html += `<div class="detail-label">Cluster ID</div><div class="detail-value" style="font-size:11px;">${clusterIds.join(', ')}</div>`;
                    }
                    if (clusterTerms.length > 0) {
                        const shown = clusterTerms.slice(0, 12);
                        const more = clusterTerms.length > shown.length ? ` (+${clusterTerms.length - shown.length} more)` : '';
                        html += `<div class="detail-label">Cluster Terms</div><div class="detail-value">${shown.join(', ')}${more}</div>`;
                    }
                    html += '</div></div>';
                    
                    document.getElementById('detail-body').innerHTML = html;
                });
        }
        
        function closeDetail() {
            document.getElementById('detail-overlay').classList.remove('active');
            document.getElementById('detail-panel').classList.remove('active');
            closeSourceDetail();
        }
        
        function showSourceDetail(key) {
            document.getElementById('source-detail-panel').classList.add('active');
            document.getElementById('source-detail-body').innerHTML = '<div class="loading">Loading...</div>';
            
            fetch(`/api/source-item/${encodeURIComponent(key)}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('source-detail-title').textContent = data.raw_name || key;
                    document.getElementById('source-detail-subtitle').textContent = `Source: ${data.source} | Row #${data.source_row_number || '-'}`;
                    
                    let html = '<div class="detail-section"><h3>Source Info</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Source</div><div class="detail-value">${data.source}</div>`;
                    html += `<div class="detail-label">Raw Name</div><div class="detail-value">${data.raw_name || '-'}</div>`;
                    html += `<div class="detail-label">INCI Name</div><div class="detail-value">${data.inci_name || '-'}</div>`;
                    html += `<div class="detail-label">CAS Number</div><div class="detail-value">${data.cas_number || '-'}</div>`;
                    html += `<div class="detail-label">Category</div><div class="detail-value">${data.ingredient_category || '-'}</div>`;
                    html += `<div class="detail-label">Origin</div><div class="detail-value">${data.origin || '-'}</div>`;
                    html += `<div class="detail-label">Source Ref</div><div class="detail-value" style="word-break:break-all;font-size:10px;">${data.source_ref || '-'}</div>`;
                    html += '</div></div>';
                    
                    if (data.function_tags && data.function_tags.length > 0) {
                        html += '<div class="detail-section"><h3>Function Tags</h3>';
                        html += '<div class="detail-value">' + data.function_tags.join(', ') + '</div></div>';
                    }
                    
                    if (data.master_categories && data.master_categories.length > 0) {
                        html += '<div class="detail-section"><h3>Master Categories</h3>';
                        html += '<div class="detail-value">' + data.master_categories.join(', ') + '</div></div>';
                    }
                    
                    if (data.specs && Object.keys(data.specs).length > 0) {
                        html += '<div class="detail-section"><h3>Specifications</h3><div class="detail-grid">';
                        for (const [key, val] of Object.entries(data.specs)) {
                            const displayVal = typeof val === 'object' ? JSON.stringify(val) : val;
                            html += `<div class="detail-label">${key}</div><div class="detail-value">${displayVal}</div>`;
                        }
                        html += '</div></div>';
                    }
                    
                    html += '<div class="detail-section"><h3>Cluster Info</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Derived Term</div><div class="detail-value"><strong>${data.derived_term || '-'}</strong></div>`;
                    html += `<div class="detail-label">Derived Variation</div><div class="detail-value">${data.derived_variation || '-'}</div>`;
                    html += `<div class="detail-label">Physical Form</div><div class="detail-value">${data.derived_physical_form || '-'}</div>`;
                    html += `<div class="detail-label">Cluster ID</div><div class="detail-value" style="font-size:10px;word-break:break-all;">${data.definition_cluster_id || '-'}</div>`;
                    html += `<div class="detail-label">Cluster Reason</div><div class="detail-value">${data.definition_cluster_reason || '-'}</div>`;
                    html += `<div class="detail-label">Cluster Confidence</div><div class="detail-value">${data.definition_cluster_confidence || '-'}</div>`;
                    html += '</div>';
                    if (data.definition_cluster_id) {
                        html += `<button onclick="event.stopPropagation(); closeSourceDetail(); closeDetail(); showClusterDetail('${data.definition_cluster_id.replace(/'/g, "\\'")}')" style="margin-top:10px; padding:8px 16px; background:#7c3aed; color:#fff; border:none; border-radius:6px; cursor:pointer;">View All Items in This Cluster</button>`;
                    }
                    html += '</div>';
                    
                    document.getElementById('source-detail-body').innerHTML = html;
                });
        }
        
        function closeSourceDetail() {
            document.getElementById('source-detail-panel').classList.remove('active');
        }
        
        function exportData(format) {
            const search = document.getElementById('search').value;
            window.location.href = `/api/export/${format}?filter=${currentFilter}&view=${currentView}&search=${encodeURIComponent(search)}`;
        }
        
        function exportAnalysis() {
            const search = document.getElementById('search').value;
            const category = document.getElementById('category-filter').value;
            window.location.href = `/api/export-analysis?filter=${currentFilter}&search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&cluster_size=${currentClusterSize}`;
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeDetail();
        });
        
        loadCategories();
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

def parse_json(val):
    if val:
        try:
            return json.loads(val)
        except:
            return val
    return None

@app.route('/')
def index():
    conn = get_db('final')
    cur = conn.cursor()
    
    stats = {}
    
    cur.execute("SELECT COUNT(DISTINCT derived_term) FROM merged_item_forms")
    stats['total_terms'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms")
    stats['total_merged'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND has_tgsc = 1")
    stats['both_sources'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND has_tgsc = 0")
    stats['cosing_only'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1 AND has_cosing = 0")
    stats['tgsc_only'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE merged_specs_json IS NOT NULL AND merged_specs_json != '{}'")
    stats['with_specs'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT definition_cluster_id) FROM source_items WHERE definition_cluster_id IS NOT NULL")
    stats['total_clusters'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM (SELECT definition_cluster_id FROM source_items WHERE definition_cluster_id IS NOT NULL GROUP BY definition_cluster_id HAVING COUNT(*) > 1)")
    stats['multi_item_clusters'] = cur.fetchone()[0]
    
    conn.close()
    return render_template_string(HTML_TEMPLATE, stats=stats)

@app.route('/api/categories')
def api_categories():
    conn = get_db('final')
    cur = conn.cursor()
    cur.execute("""
        SELECT ingredient_category, COUNT(*) as cnt 
        FROM source_items 
        WHERE ingredient_category IS NOT NULL AND ingredient_category != ''
        GROUP BY ingredient_category 
        ORDER BY cnt DESC
    """)
    categories = [{'name': row[0], 'count': row[1]} for row in cur.fetchall()]
    conn.close()
    return jsonify({'categories': categories})

@app.route('/api/clusters')
def api_clusters():
    """Show raw cluster data from source_definitions - no overlays, no aggregation."""
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '').strip()
    cluster_size = request.args.get('cluster_size', 'all')
    filter_type = request.args.get('filter', 'all')
    category = request.args.get('category', '').strip()
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db('final')
    cur = conn.cursor()
    
    # Simple search - no parent/child aggregation
    where_clauses = ["sd.cluster_id IS NOT NULL"]
    params = []
    
    if search:
        search_param = f"%{search}%"
        where_clauses.append("(sd.canonical_term LIKE ? OR sd.cluster_id LIKE ? OR sd.reconciled_term LIKE ?)")
        params.extend([search_param, search_param, search_param])
    
    if category:
        where_clauses.append("""EXISTS (
            SELECT 1 FROM source_items si 
            WHERE si.definition_cluster_id = sd.cluster_id 
            AND si.ingredient_category = ?
        )""")
        params.append(category)
    
    where_sql = "WHERE " + " AND ".join(where_clauses)
    
    # Build having clauses for source filters
    having_clauses = []
    if cluster_size == 'multi':
        having_clauses.append("merged_item_count > 1")
    elif cluster_size == 'single':
        having_clauses.append("merged_item_count = 1")
    
    if filter_type == 'cosing':
        having_clauses.append("cosing_count > 0")
    elif filter_type == 'tgsc':
        having_clauses.append("tgsc_count > 0")
    elif filter_type == 'both':
        having_clauses.append("cosing_count > 0 AND tgsc_count > 0")
    
    having_sql = "HAVING " + " AND ".join(having_clauses) if having_clauses else ""
    
    # Query raw cluster data from source_definitions with merged item counts
    cur.execute(f"""
        SELECT 
            sd.cluster_id,
            sd.canonical_term,
            (SELECT COUNT(DISTINCT si.merged_item_id) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.merged_item_id IS NOT NULL) as merged_item_count,
            (SELECT COUNT(DISTINCT si.merged_item_id) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.source = 'cosing' AND si.merged_item_id IS NOT NULL) as cosing_count,
            (SELECT COUNT(DISTINCT si.merged_item_id) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.source = 'tgsc' AND si.merged_item_id IS NOT NULL) as tgsc_count
        FROM source_definitions sd
        {where_sql}
        {having_sql}
        ORDER BY sd.canonical_term, sd.cluster_id
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    
    clusters = []
    for row in cur.fetchall():
        clusters.append({
            'cluster_id': row[0],
            'canonical_term': row[1],
            'merged_item_count': row[2] or 0,
            'cosing_count': row[3] or 0,
            'tgsc_count': row[4] or 0,
        })
    
    # Get total count
    cur.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT sd.cluster_id,
                (SELECT COUNT(*) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id) as item_count,
                (SELECT COUNT(*) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.source = 'cosing') as cosing_count,
                (SELECT COUNT(*) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.source = 'tgsc') as tgsc_count
            FROM source_definitions sd
            {where_sql}
            {having_sql}
        )
    """, params)
    total = cur.fetchone()[0]
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    conn.close()
    return jsonify({
        'clusters': clusters,
        'total': total,
        'total_pages': total_pages,
        'page': page
    })

@app.route('/api/cluster/<path:cluster_id>')
def api_cluster_detail(cluster_id):
    conn = get_db('final')
    cur = conn.cursor()
    
    is_composite = cluster_id.startswith('composite:')
    
    if is_composite:
        # For composites, show raw source items directly (no merged items exist)
        cur.execute("""
            SELECT key, source, raw_name, inci_name, cas_number, 
                   derived_term, derived_variation, derived_physical_form,
                   definition_cluster_reason
            FROM source_items 
            WHERE definition_cluster_id = ?
            ORDER BY source, raw_name
        """, (cluster_id,))
        
        source_items = []
        reason = None
        derived_term = None
        for row in cur.fetchall():
            if not reason:
                reason = row[8]
            if not derived_term:
                derived_term = row[5]
            source_items.append({
                'key': row[0],
                'source': row[1],
                'raw_name': row[2],
                'inci_name': row[3],
                'cas_number': row[4],
                'derived_term': row[5],
                'derived_variation': row[6],
                'derived_physical_form': row[7]
            })
        
        conn.close()
        return jsonify({
            'cluster_id': cluster_id,
            'reason': reason,
            'derived_term': derived_term,
            'is_composite': True,
            'source_items': source_items,
            'items': [],
            'raw_names': []
        })
    
    # For term clusters, get merged items categorized by source
    cur.execute("""
        SELECT DISTINCT m.id, m.derived_term, m.derived_variation, m.derived_physical_form,
               m.cas_numbers_json, m.has_cosing, m.has_tgsc,
               (SELECT s.inci_name FROM source_items s WHERE s.merged_item_id = m.id LIMIT 1) as inci_name
        FROM merged_item_forms m
        JOIN source_items s ON s.merged_item_id = m.id
        WHERE s.definition_cluster_id = ?
        ORDER BY m.derived_term, m.derived_variation, m.derived_physical_form
    """, (cluster_id,))
    
    cosing_only = []
    tgsc_only = []
    both_sources = []
    derived_term = None
    
    for row in cur.fetchall():
        if not derived_term:
            derived_term = row[1]
        
        has_cosing = row[5]
        has_tgsc = row[6]
        
        # Parse CAS numbers
        cas_numbers = ''
        try:
            import json
            cas_list = json.loads(row[4]) if row[4] else []
            cas_numbers = ', '.join(cas_list) if cas_list else ''
        except:
            pass
        
        item = {
            'id': row[0],
            'derived_term': row[1],
            'derived_variation': row[2] or '',
            'derived_physical_form': row[3] or '',
            'cas_number': cas_numbers,
            'inci_name': row[7] or ''
        }
        
        # Categorize by source presence
        if has_cosing and has_tgsc:
            both_sources.append(item)
        elif has_cosing:
            cosing_only.append(item)
        else:
            tgsc_only.append(item)
    
    # Get cluster info from source_definitions
    cur.execute("""
        SELECT reason, canonical_term, botanical_key, reconciled_term, reconciled_variation, parent_cluster_id 
        FROM source_definitions WHERE cluster_id = ?
    """, (cluster_id,))
    def_row = cur.fetchone()
    reason = def_row[0] if def_row else None
    canonical_term = def_row[1] if def_row else None
    botanical_key = def_row[2] if def_row else None
    reconciled_term = def_row[3] if def_row else None
    reconciled_variation = def_row[4] if def_row else None
    parent_cluster_id = def_row[5] if def_row else None
    
    # Get child derivatives (clusters that have this cluster as parent)
    # Also include siblings if this cluster itself has a parent
    cur.execute("""
        SELECT cluster_id, canonical_term, reconciled_variation 
        FROM source_definitions 
        WHERE parent_cluster_id = ?
           OR (? IS NOT NULL AND parent_cluster_id = ?)
        ORDER BY canonical_term
    """, (cluster_id, parent_cluster_id, parent_cluster_id))
    child_derivatives = [{'cluster_id': r[0], 'canonical_term': r[1], 'variation': r[2]} for r in cur.fetchall() if r[0] != cluster_id]
    
    conn.close()
    return jsonify({
        'cluster_id': cluster_id,
        'reason': reason,
        'derived_term': derived_term,
        'canonical_term': canonical_term,
        'botanical_key': botanical_key,
        'reconciled_term': reconciled_term,
        'reconciled_variation': reconciled_variation,
        'parent_cluster_id': parent_cluster_id,
        'child_derivatives': child_derivatives,
        'is_composite': False,
        'cosing_only': cosing_only,
        'tgsc_only': tgsc_only,
        'both_sources': both_sources,
        'total_items': len(cosing_only) + len(tgsc_only) + len(both_sources)
    })

@app.route('/api/terms')
def api_terms():
    filter_type = request.args.get('filter', 'all')
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db('final')
    cur = conn.cursor()
    
    where_clauses = []
    params = []
    
    if search:
        where_clauses.append("m.derived_term LIKE ?")
        params.append(f"%{search}%")
    
    if filter_type == 'cosing':
        where_clauses.append("m.has_cosing = 1")
    elif filter_type == 'tgsc':
        where_clauses.append("m.has_tgsc = 1")
    elif filter_type == 'both':
        where_clauses.append("m.has_cosing = 1 AND m.has_tgsc = 1")
    elif filter_type == 'pubchem':
        where_clauses.append("json_extract(m.merged_specs_json, '$.pubchem.cid') IS NOT NULL")
    
    if category:
        where_clauses.append("EXISTS (SELECT 1 FROM source_items s WHERE s.derived_term = m.derived_term AND s.ingredient_category = ?)")
        params.append(category)
    
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    cur.execute(f"""
        SELECT m.derived_term, COUNT(*) as item_count,
               MAX(m.has_cosing) as has_cosing, MAX(m.has_tgsc) as has_tgsc,
               (SELECT ingredient_category FROM source_items WHERE derived_term = m.derived_term LIMIT 1) as category
        FROM merged_item_forms m
        {where_sql}
        GROUP BY m.derived_term
        ORDER BY m.derived_term
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    
    terms = []
    for row in cur.fetchall():
        terms.append({
            'term': row[0],
            'item_count': row[1],
            'has_cosing': bool(row[2]),
            'has_tgsc': bool(row[3]),
            'category': row[4]
        })
    
    cur.execute(f"""
        SELECT COUNT(DISTINCT m.derived_term) FROM merged_item_forms m {where_sql}
    """, params)
    total = cur.fetchone()[0]
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    conn.close()
    return jsonify({
        'terms': terms,
        'total': total,
        'total_pages': total_pages,
        'page': page
    })

@app.route('/api/term-items')
def api_term_items():
    term = request.args.get('term', '')
    filter_type = request.args.get('filter', 'all')
    
    conn = get_db('final')
    cur = conn.cursor()
    
    where_clauses = ["derived_term = ?"]
    params = [term]
    
    if filter_type == 'cosing':
        where_clauses.append("has_cosing = 1")
    elif filter_type == 'tgsc':
        where_clauses.append("has_tgsc = 1")
    elif filter_type == 'both':
        where_clauses.append("has_cosing = 1 AND has_tgsc = 1")
    elif filter_type == 'pubchem':
        where_clauses.append("json_extract(merged_specs_json, '$.pubchem.cid') IS NOT NULL")
    
    where_sql = "WHERE " + " AND ".join(where_clauses)
    
    cur.execute(f"""
        SELECT id, derived_term, derived_variation, derived_physical_form,
               has_cosing, has_tgsc,
               CASE WHEN merged_specs_json IS NOT NULL AND merged_specs_json != '{{}}' THEN 1 ELSE 0 END as has_specs
        FROM merged_item_forms
        {where_sql}
        ORDER BY derived_variation, derived_physical_form
        LIMIT 50
    """, params)
    
    items = []
    for row in cur.fetchall():
        items.append({
            'id': row[0],
            'term': row[1],
            'variation': row[2],
            'form': row[3],
            'has_cosing': bool(row[4]),
            'has_tgsc': bool(row[5]),
            'has_specs': bool(row[6])
        })
    
    conn.close()
    return jsonify({'items': items})

@app.route('/api/merged-items')
def api_merged_items():
    filter_type = request.args.get('filter', 'all')
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db('final')
    cur = conn.cursor()
    
    where_clauses = []
    params = []
    
    if search:
        where_clauses.append("(m.derived_term LIKE ? OR m.cas_numbers_json LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    if filter_type == 'cosing':
        where_clauses.append("m.has_cosing = 1")
    elif filter_type == 'tgsc':
        where_clauses.append("m.has_tgsc = 1")
    elif filter_type == 'both':
        where_clauses.append("m.has_cosing = 1 AND m.has_tgsc = 1")
    elif filter_type == 'pubchem':
        where_clauses.append("json_extract(m.merged_specs_json, '$.pubchem.cid') IS NOT NULL")
    
    if category:
        where_clauses.append("EXISTS (SELECT 1 FROM source_items s WHERE s.derived_term = m.derived_term AND s.ingredient_category = ?)")
        params.append(category)
    
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    cur.execute(f"SELECT COUNT(*) FROM merged_item_forms m {where_sql}", params)
    total = cur.fetchone()[0]
    
    cur.execute(f"""
        SELECT m.id, m.derived_term, m.derived_variation, m.derived_physical_form,
               m.cas_numbers_json, m.has_cosing, m.has_tgsc, m.source_row_count,
               CASE WHEN m.merged_specs_json IS NOT NULL AND m.merged_specs_json != '{{}}' THEN 1 ELSE 0 END as has_specs
        FROM merged_item_forms m
        {where_sql}
        ORDER BY m.derived_term
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    
    items = []
    for row in cur.fetchall():
        items.append({
            'id': row[0],
            'term': row[1],
            'variation': row[2],
            'form': row[3],
            'cas_numbers': parse_json(row[4]) or [],
            'has_cosing': bool(row[5]),
            'has_tgsc': bool(row[6]),
            'source_count': row[7],
            'has_specs': bool(row[8])
        })
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    conn.close()
    return jsonify({
        'items': items,
        'total': total,
        'total_pages': total_pages,
        'page': page
    })

@app.route('/api/merged-item/<int:item_id>')
def api_merged_item_detail(item_id):
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
    if not row:
        conn.close()
        return jsonify({'error': 'Item not found'})
    
    member_keys = parse_json(row[6]) or []
    
    source_items = []
    term_data = {'origin': None, 'ingredient_category': None, 'inci_name': None, 'master_categories': []}
    cluster_ids = []
    cluster_terms = []
    if member_keys:
        keys_to_fetch = member_keys[:20]
        placeholders = ','.join(['?' for _ in keys_to_fetch])
        cur.execute(f"""
            SELECT key, source, raw_name, inci_name, cas_number, origin, ingredient_category, derived_master_categories_json,
                   definition_cluster_id, definition_cluster_confidence
            FROM source_items WHERE key IN ({placeholders})
        """, keys_to_fetch)
        
        for src_row in cur.fetchall():
            if src_row[8] and src_row[8] not in cluster_ids:
                cluster_ids.append(src_row[8])
            source_items.append({
                'key': src_row[0],
                'source': src_row[1],
                'raw_name': src_row[2],
                'inci_name': src_row[3],
                'cas_number': src_row[4],
                'origin': src_row[5],
                'ingredient_category': src_row[6],
                'master_categories': parse_json(src_row[7]) or [],
                'definition_cluster_id': src_row[8],
                'definition_cluster_confidence': src_row[9],
            })
            if src_row[5] and not term_data['origin']:
                term_data['origin'] = src_row[5]
            if src_row[6] and not term_data['ingredient_category']:
                term_data['ingredient_category'] = src_row[6]
            if src_row[3] and not term_data['inci_name']:
                term_data['inci_name'] = src_row[3]
            master_cats = parse_json(src_row[7]) or []
            for mc in master_cats:
                if mc and mc not in term_data['master_categories']:
                    term_data['master_categories'].append(mc)

        # Cluster terms: show other derived_term values that map to the same definition_cluster_id(s).
        canonical_term = None
        botanical_key = None
        if cluster_ids:
            placeholders = ','.join(['?' for _ in cluster_ids])
            cur.execute(f"""
                SELECT DISTINCT derived_term
                FROM source_items
                WHERE definition_cluster_id IN ({placeholders})
                  AND derived_term IS NOT NULL
                  AND TRIM(derived_term) != ''
                ORDER BY derived_term
                LIMIT 50
            """, cluster_ids)
            cluster_terms = [r[0] for r in cur.fetchall() if r and r[0]]
            # Keep the response small; UI will show truncated list if needed.
            cluster_terms = cluster_terms[:30]
            
            # Get canonical_term and botanical_key from source_definitions
            cur.execute(f"""
                SELECT canonical_term, botanical_key 
                FROM source_definitions 
                WHERE cluster_id IN ({placeholders})
                LIMIT 1
            """, cluster_ids)
            def_row = cur.fetchone()
            if def_row:
                canonical_term = def_row[0]
                botanical_key = def_row[1]
    
    conn.close()
    
    return jsonify({
        'id': row[0],
        'derived_term': row[1],
        'derived_variation': row[2],
        'derived_physical_form': row[3],
        'derived_parts': parse_json(row[4]) or [],
        'cas_numbers': parse_json(row[5]) or [],
        'member_source_item_keys': member_keys,
        'sources': parse_json(row[7]) or [],
        'merged_specs': parse_json(row[8]),
        'merged_specs_sources': parse_json(row[9]),
        'merged_specs_notes': parse_json(row[10]),
        'source_row_count': row[11],
        'has_cosing': bool(row[12]),
        'has_tgsc': bool(row[13]),
        'created_at': row[14],
        'compiled_specs': parse_json(row[15]),
        'app_seed_specs': parse_json(row[16]),
        'source_items': source_items,
        'term_data': term_data,
        'term_cluster': {
            'cluster_ids': cluster_ids,
            'cluster_terms': cluster_terms,
            'canonical_term': canonical_term,
            'botanical_key': botanical_key,
        },
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
               merged_item_id, ingested_at
        FROM source_items WHERE key = ?
    """, (key,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Source item not found'})
    
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
        'ingested_at': row[35]
    })

@app.route('/api/export-analysis')
def api_export_analysis():
    """Export comprehensive analysis CSV with cluster context for pre-AI data review."""
    filter_type = request.args.get('filter', 'all')
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    cluster_size = request.args.get('cluster_size', 'all')
    
    conn = get_db('final')
    cur = conn.cursor()
    
    where_clauses = ["s.definition_cluster_id IS NOT NULL"]
    params = []
    
    if search:
        where_clauses.append("(s.derived_term LIKE ? OR s.raw_name LIKE ? OR s.definition_cluster_id LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    if category:
        where_clauses.append("s.ingredient_category = ?")
        params.append(category)
    
    where_sql = "WHERE " + " AND ".join(where_clauses)
    
    having_clauses = []
    if cluster_size == 'multi':
        having_clauses.append("cluster_size > 1")
    elif cluster_size == 'single':
        having_clauses.append("cluster_size = 1")
    
    if filter_type == 'cosing':
        having_clauses.append("cosing_count > 0")
    elif filter_type == 'tgsc':
        having_clauses.append("tgsc_count > 0")
    elif filter_type == 'both':
        having_clauses.append("cosing_count > 0 AND tgsc_count > 0")
    elif filter_type == 'pubchem':
        having_clauses.append("has_pubchem > 0")
    
    having_sql = "HAVING " + " AND ".join(having_clauses) if having_clauses else ""
    
    cur.execute(f"""
        WITH cluster_stats AS (
            SELECT 
                s.definition_cluster_id,
                COUNT(*) as cluster_size,
                SUM(CASE WHEN s.source = 'cosing' THEN 1 ELSE 0 END) as cosing_count,
                SUM(CASE WHEN s.source = 'tgsc' THEN 1 ELSE 0 END) as tgsc_count,
                MAX(CASE WHEN json_extract(m.merged_specs_json, '$.pubchem.cid') IS NOT NULL THEN 1 ELSE 0 END) as has_pubchem,
                GROUP_CONCAT(DISTINCT s.source) as sources_in_cluster
            FROM source_items s
            LEFT JOIN merged_item_forms m ON s.merged_item_id = m.id
            {where_sql}
            GROUP BY s.definition_cluster_id
            {having_sql}
        )
        SELECT 
            s.key,
            s.source,
            s.raw_name,
            s.inci_name,
            s.cas_number,
            s.derived_term,
            s.derived_variation,
            s.derived_physical_form,
            s.ingredient_category,
            s.definition_display_name,
            s.definition_cluster_id,
            s.definition_cluster_reason,
            cs.cluster_size,
            cs.cosing_count,
            cs.tgsc_count,
            cs.sources_in_cluster
        FROM source_items s
        JOIN cluster_stats cs ON s.definition_cluster_id = cs.definition_cluster_id
        ORDER BY s.definition_cluster_id, s.source, s.raw_name
    """, params)
    
    rows = cur.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'key',
        'source',
        'raw_name',
        'inci_name',
        'cas_number',
        'derived_term',
        'derived_variation',
        'derived_physical_form',
        'ingredient_category',
        'definition_display_name',
        'cluster_id',
        'cluster_reason',
        'cluster_size',
        'cosing_items_in_cluster',
        'tgsc_items_in_cluster',
        'sources_in_cluster'
    ])
    
    for row in rows:
        writer.writerow(row)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=analysis_export.csv'}
    )

@app.route('/api/export/<format>')
def api_export(format):
    filter_type = request.args.get('filter', 'all')
    view = request.args.get('view', 'items')
    search = request.args.get('search', '').strip()
    
    conn = get_db('final')
    cur = conn.cursor()
    
    where_clauses = []
    params = []
    
    if search:
        where_clauses.append("(derived_term LIKE ? OR cas_numbers_json LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    if filter_type == 'cosing':
        where_clauses.append("has_cosing = 1")
    elif filter_type == 'tgsc':
        where_clauses.append("has_tgsc = 1")
    elif filter_type == 'both':
        where_clauses.append("has_cosing = 1 AND has_tgsc = 1")
    elif filter_type == 'pubchem':
        where_clauses.append("json_extract(merged_specs_json, '$.pubchem.cid') IS NOT NULL")
    
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    cur.execute(f"""
        SELECT id, derived_term, derived_variation, derived_physical_form,
               cas_numbers_json, has_cosing, has_tgsc, source_row_count, merged_specs_json
        FROM merged_item_forms
        {where_sql}
        ORDER BY derived_term
    """, params)
    
    rows = cur.fetchall()
    conn.close()
    
    if format == 'json':
        data = []
        for row in rows:
            data.append({
                'id': row[0],
                'term': row[1],
                'variation': row[2],
                'form': row[3],
                'cas_numbers': parse_json(row[4]) or [],
                'has_cosing': bool(row[5]),
                'has_tgsc': bool(row[6]),
                'source_count': row[7],
                'specs': parse_json(row[8])
            })
        return Response(
            json.dumps(data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment;filename=merged_items.json'}
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['id', 'term', 'variation', 'form', 'cas_numbers', 'has_cosing', 'has_tgsc', 'source_count'])
        for row in rows:
            cas = parse_json(row[4]) or []
            writer.writerow([row[0], row[1], row[2], row[3], ';'.join(cas), row[5], row[6], row[7]])
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=merged_items.csv'}
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
