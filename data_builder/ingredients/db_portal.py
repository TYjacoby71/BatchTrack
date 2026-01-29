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
        .badge-compiled { background: #d1fae5; color: #065f46; }
        
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
    
    <div class="stats" id="raw-stats">
        <div class="stats-grid">
            <div class="stat-box">
                <h3 id="stat-source-items">{{ stats.source_items }}</h3>
                <p>Source Items</p>
            </div>
            <div class="stat-box">
                <h3 id="stat-cosing-items">{{ stats.cosing_items }}</h3>
                <p>CosIng Items</p>
            </div>
            <div class="stat-box">
                <h3 id="stat-tgsc-items">{{ stats.tgsc_items }}</h3>
                <p>TGSC Items</p>
            </div>
            <div class="stat-box" style="border-left: 3px solid #7c3aed;">
                <h3 id="stat-total-merged">{{ stats.total_merged }}</h3>
                <p>Merged Items</p>
            </div>
            <div class="stat-box">
                <h3 id="stat-cosing-only">{{ stats.cosing_only }}</h3>
                <p>CosIng Only</p>
            </div>
            <div class="stat-box">
                <h3 id="stat-tgsc-only">{{ stats.tgsc_only }}</h3>
                <p>TGSC Only</p>
            </div>
            <div class="stat-box">
                <h3 id="stat-both-sources">{{ stats.both_sources }}</h3>
                <p>Both Sources</p>
            </div>
            <div class="stat-box" style="border-left: 3px solid #10b981;">
                <h3 id="stat-pubchem-enriched">{{ stats.pubchem_enriched }}</h3>
                <p>PubChem Enriched</p>
            </div>
            <div class="stat-box" style="border-left: 3px solid #2563eb;">
                <h3 id="stat-total-clusters">{{ stats.total_clusters }}</h3>
                <p>Clusters</p>
            </div>
            <div class="stat-box">
                <h3 id="stat-composites">{{ stats.composites }}</h3>
                <p>Composites</p>
            </div>
        </div>
    </div>
    
    <div class="stats" id="compiled-stats" style="display:none;">
        <div style="margin-bottom: 15px;">
            <div style="font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 10px;">Queue Overview</div>
            <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);">
                <div class="stat-box" style="border-left: 3px solid #7c3aed;">
                    <h3 id="cstat-queued-items">0</h3>
                    <p>Total Queued Items</p>
                </div>
                <div class="stat-box" style="border-left: 3px solid #2563eb;">
                    <h3 id="cstat-clusters">0</h3>
                    <p>Clusters</p>
                </div>
                <div class="stat-box" style="border-left: 3px solid #f59e0b;">
                    <h3 id="cstat-composites">0</h3>
                    <p>Composites</p>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 15px;">
            <div style="font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 10px;">Stage 1: Term Normalization (Clusters)</div>
            <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);">
                <div class="stat-box" style="background: #dcfce7;">
                    <h3 id="cstat-stage1-done" style="color: #166534;">0</h3>
                    <p>Normalized</p>
                </div>
                <div class="stat-box" style="background: #fef3c7;">
                    <h3 id="cstat-stage1-pending" style="color: #92400e;">0</h3>
                    <p>Pending</p>
                </div>
                <div class="stat-box">
                    <h3 id="cstat-stage1-pct" style="color: #2563eb;">0%</h3>
                    <p>Stage 1 Progress</p>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 15px;">
            <div style="font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 10px;">Stage 2: Item Compilation</div>
            <div class="stats-grid" style="grid-template-columns: repeat(4, 1fr);">
                <div class="stat-box" style="background: #dcfce7;">
                    <h3 id="cstat-stage2-done" style="color: #166534;">0</h3>
                    <p>Compiled</p>
                </div>
                <div class="stat-box" style="background: #fef3c7;">
                    <h3 id="cstat-stage2-batch-pending" style="color: #92400e;">0</h3>
                    <p>Batch Pending</p>
                </div>
                <div class="stat-box" style="background: #f3f4f6;">
                    <h3 id="cstat-stage2-pending" style="color: #6b7280;">0</h3>
                    <p>Pending</p>
                </div>
                <div class="stat-box">
                    <h3 id="cstat-stage2-pct" style="color: #2563eb;">0%</h3>
                    <p>Progress</p>
                </div>
            </div>
        </div>
        
        <div>
            <div style="font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 10px;">Cluster Distribution</div>
            <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);">
                <div class="stat-box">
                    <h3 id="cstat-zero-items" style="color: #dc2626;">0</h3>
                    <p>Zero Items</p>
                </div>
                <div class="stat-box">
                    <h3 id="cstat-single-item" style="color: #059669;">0</h3>
                    <p>Single Item</p>
                </div>
                <div class="stat-box">
                    <h3 id="cstat-multi-item" style="color: #7c3aed;">0</h3>
                    <p>Multi-Item</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="stats" id="refined-stats" style="display:none;">
        <div style="margin-bottom: 15px;">
            <div style="font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 10px;">Refined Ingredient Definitions</div>
            <div class="stats-grid" style="grid-template-columns: repeat(4, 1fr);">
                <div class="stat-box" style="border-left: 3px solid #8b5cf6;">
                    <h3 id="rstat-definitions">0</h3>
                    <p>Definitions</p>
                </div>
                <div class="stat-box" style="border-left: 3px solid #2563eb;">
                    <h3 id="rstat-source-clusters">0</h3>
                    <p>Source Clusters</p>
                </div>
                <div class="stat-box" style="border-left: 3px solid #10b981;">
                    <h3 id="rstat-total-items">0</h3>
                    <p>Total Items</p>
                </div>
                <div class="stat-box" style="border-left: 3px solid #f59e0b;">
                    <h3 id="rstat-enriched">0</h3>
                    <p>Enriched (SAP Data)</p>
                </div>
            </div>
        </div>
        <div>
            <div style="font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 10px;">Origin Distribution</div>
            <div class="stats-grid" style="grid-template-columns: repeat(4, 1fr);">
                <div class="stat-box">
                    <h3 id="rstat-plant">0</h3>
                    <p>Plant-Derived</p>
                </div>
                <div class="stat-box">
                    <h3 id="rstat-synthetic">0</h3>
                    <p>Synthetic</p>
                </div>
                <div class="stat-box">
                    <h3 id="rstat-mineral">0</h3>
                    <p>Mineral</p>
                </div>
                <div class="stat-box">
                    <h3 id="rstat-animal">0</h3>
                    <p>Animal</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="main-content">
        <div class="filter-row">
            <div class="filter-section">
                <div class="filter-label">Dataset</div>
                <div class="view-toggle">
                    <button class="view-btn active" data-dataset="raw" onclick="setDataset('raw')">Raw data</button>
                    <button class="view-btn" data-dataset="compiled" onclick="setDataset('compiled')">Compiled data</button>
                    <button class="view-btn" data-dataset="refined" onclick="setDataset('refined')" style="background:#8b5cf6; color:#fff;">Refined</button>
                </div>
            </div>
            <div class="filter-section" id="view-mode-section">
                <div class="filter-label">View Mode</div>
                <div class="view-toggle" id="view-mode-buttons">
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
            <div class="filter-section" id="status-filters" style="display:none;">
                <div class="filter-label">Compilation Status</div>
                <div class="venn-filters">
                    <button class="venn-btn active" data-filter="all" onclick="setFilter('all')">All</button>
                    <button class="venn-btn" data-filter="pending" onclick="setFilter('pending')" style="background:#fef3c7;color:#92400e;border-color:#fcd34d;">Pending</button>
                    <button class="venn-btn" data-filter="done" onclick="setFilter('done')" style="background:#dcfce7;color:#166534;border-color:#86efac;">Done</button>
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
        let currentDataset = 'raw'; // raw | compiled
        let searchTimeout = null;
        let expandedTerms = new Set();
        let sortField = 'rank';  // rank | name | priority
        let sortOrder = 'asc';   // asc | desc
        
        function loadCategories() {
            fetch(`/api/categories?dataset=${currentDataset}`)
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('category-filter');
                    // Clear existing options except the first "All Categories"
                    while (select.options.length > 1) {
                        select.remove(1);
                    }
                    select.value = '';
                    currentCategory = '';
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
            let info = currentDataset === 'compiled'
                ? `Showing compiled ${viewName}.`
                : filterDescriptions[currentFilter].replace('{view}', viewName);
            if (currentCategory) {
                info += ` Filtered to: ${currentCategory}`;
            }
            if (currentDataset === 'raw' && currentView === 'clusters') {
                info = 'Showing source item clusters - items grouped by what the system expects to merge together.';
            }
            document.getElementById('filter-info').textContent = info;
        }

        function setDataset(dataset) {
            currentDataset = dataset;
            currentPage = 1;
            expandedTerms.clear();
            document.querySelectorAll('[data-dataset]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.dataset === dataset);
            });

            const sourceFilters = document.querySelector('.filter-section:has([data-filter="cosing"])');
            const statusFilters = document.getElementById('status-filters');
            const viewModeSection = document.getElementById('view-mode-section');
            const clusterFilters = document.getElementById('cluster-filters');
            
            // Show/hide stats panels
            document.getElementById('raw-stats').style.display = (dataset === 'raw') ? 'block' : 'none';
            document.getElementById('compiled-stats').style.display = (dataset === 'compiled') ? 'block' : 'none';
            document.getElementById('refined-stats').style.display = (dataset === 'refined') ? 'block' : 'none';
            
            if (currentDataset === 'refined') {
                // Refined mode: hide view mode, show only refined definitions
                currentFilter = 'all';
                currentView = 'terms';  // Refined uses terms view internally
                if (viewModeSection) viewModeSection.style.display = 'none';
                if (sourceFilters) sourceFilters.style.display = 'none';
                if (statusFilters) statusFilters.style.display = 'none';
                if (clusterFilters) clusterFilters.style.display = 'none';
            } else if (currentDataset === 'compiled') {
                currentFilter = 'all';
                document.querySelectorAll('.venn-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.filter === 'all');
                });
                currentView = 'clusters';
                document.querySelectorAll('.view-btn[data-view]').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.view === currentView);
                });
                if (viewModeSection) viewModeSection.style.display = 'block';
                if (sourceFilters) sourceFilters.style.display = 'none';
                if (statusFilters) statusFilters.style.display = 'block';
                if (clusterFilters) clusterFilters.style.display = 'none';
            } else {
                // Raw mode
                if (viewModeSection) viewModeSection.style.display = 'block';
                if (sourceFilters) sourceFilters.style.display = 'block';
                if (statusFilters) statusFilters.style.display = 'none';
            }
            updateFilterInfo();
            updateTableHeaders();
            loadCategories();
            loadStats();
            loadData();
        }
        
        function setView(view) {
            currentView = view;
            currentPage = 1;
            expandedTerms.clear();
            document.querySelectorAll('.view-btn').forEach(btn => {
                if (btn.dataset.view) {
                    btn.classList.toggle('active', btn.dataset.view === view);
                }
            });
            document.getElementById('cluster-filters').style.display = (currentDataset === 'raw' && view === 'clusters') ? 'block' : 'none';
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
        
        function getSortIndicator(field) {
            if (sortField !== field) return '';
            return sortOrder === 'asc' ? ' ▲' : ' ▼';
        }
        
        function toggleSort(field) {
            if (sortField === field) {
                sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                sortField = field;
                sortOrder = field === 'priority' ? 'desc' : 'asc';  // Priority defaults to desc (high first)
            }
            currentPage = 1;
            updateTableHeaders();
            loadData();
        }
        
        function updateTableHeaders() {
            const thead = document.getElementById('table-head');
            if (currentDataset === 'refined') {
                thead.innerHTML = '<tr><th style="width:25%;">Ingredient Definition</th><th style="width:10%;">Items</th><th style="width:15%;">Origin</th><th style="width:20%;">Category</th><th style="width:15%;">Source Clusters</th><th style="width:15%;">Enrichment</th></tr>';
                return;
            }
            if (currentDataset === 'compiled') {
                if (currentView === 'clusters') {
                    thead.innerHTML = `<tr>
                        <th class="sortable" onclick="toggleSort('rank')" style="cursor:pointer;">#${getSortIndicator('rank')}</th>
                        <th>Cluster ID</th>
                        <th class="sortable" onclick="toggleSort('name')" style="cursor:pointer;">Common Name${getSortIndicator('name')}</th>
                        <th>Items</th>
                        <th>Term Status</th>
                        <th class="sortable" onclick="toggleSort('priority')" style="cursor:pointer;">Priority${getSortIndicator('priority')}</th>
                        <th>Items Compiled</th>
                    </tr>`;
                } else if (currentView === 'terms') {
                    thead.innerHTML = '<tr><th>Ingredient (term)</th><th>Items</th><th>Origin</th><th>Primary Category</th></tr>';
                } else if (currentView === 'refined') {
                    thead.innerHTML = '<tr><th>Term</th><th>Plant Part</th><th>Variation</th><th>Refinement</th><th>Form</th><th>Flag</th></tr>';
                } else {
                    thead.innerHTML = '<tr><th>Cluster</th><th>Variation</th><th>Form</th><th>Status</th><th>Raw Specs</th><th>Compiled</th></tr>';
                }
                return;
            }
            if (currentView === 'terms') {
                thead.innerHTML = '<tr><th>Derived Term</th><th>Items</th><th>Sources</th><th>Category</th></tr>';
            } else if (currentView === 'clusters') {
                thead.innerHTML = '<tr><th>Cluster ID</th><th>Canonical Term</th><th>Total Items</th><th>CosIng Only</th><th>TGSC Only</th><th>Both Sources</th></tr>';
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
            let colSpan = 6;
            if (currentDataset === 'refined') {
                colSpan = 6;
            } else if (currentDataset === 'compiled') {
                colSpan = (currentView === 'terms' ? 4 : (currentView === 'clusters' ? 7 : 6));
            } else {
                colSpan = (currentView === 'terms' ? 4 : (currentView === 'clusters' ? 6 : 6));
            }
            tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">Loading...</td></tr>`;
            
            let endpoint;
            if (currentDataset === 'refined') {
                endpoint = '/api/refined/definitions';
            } else if (currentDataset === 'compiled') {
                if (currentView === 'clusters') {
                    endpoint = '/api/compiled/clusters';
                } else if (currentView === 'terms') {
                    endpoint = '/api/compiled/ingredients';
                } else if (currentView === 'refined') {
                    endpoint = '/api/compiled/refined';
                } else {
                    endpoint = '/api/compiled/items';
                }
            } else {
                if (currentView === 'terms') {
                    endpoint = '/api/terms';
                } else if (currentView === 'clusters') {
                    endpoint = '/api/clusters';
                } else {
                    endpoint = '/api/merged-items';
                }
            }
            
            const sortParams = currentDataset === 'compiled' && currentView === 'clusters' 
                ? `&sort=${sortField}&order=${sortOrder}` : '';
            fetch(`${endpoint}?filter=${currentFilter}&page=${currentPage}&search=${encodeURIComponent(search)}&category=${encodeURIComponent(currentCategory)}&cluster_size=${currentClusterSize}${sortParams}`)
                .then(r => r.json())
                .then(data => {
                    totalPages = data.total_pages;
                    
                    if ((data.items || data.terms || data.clusters || data.ingredients || data.definitions || []).length === 0) {
                        tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">No items found</td></tr>`;
                    } else if (currentDataset === 'refined') {
                        renderRefinedDefinitionsView(data.definitions);
                    } else if (currentDataset === 'compiled') {
                        if (currentView === 'clusters') {
                            renderCompiledClustersView(data.clusters);
                        } else if (currentView === 'terms') {
                            renderCompiledIngredientsView(data.ingredients);
                        } else if (currentView === 'refined') {
                            renderRefinedItemsView(data.items);
                        } else {
                            renderCompiledItemsView(data.items);
                        }
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

        function renderRefinedDefinitionsView(definitions) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = (definitions || []).map(row => {
                const enrichmentBadge = row.has_sap_data 
                    ? '<span class="badge" style="background:#dcfce7;color:#166534;">SAP</span>' 
                    : '';
                const clusterCount = row.cluster_count || 0;
                const clusterBadge = clusterCount > 1 
                    ? `<span class="badge" style="background:#dbeafe;color:#1e40af;">${clusterCount} clusters</span>`
                    : `<span class="badge" style="background:#f3f4f6;color:#6b7280;">1 cluster</span>`;
                return `<tr class="item-row" onclick="showRefinedDefinition('${encodeURIComponent(row.derived_term || '')}')">
                    <td><strong style="color:#7c3aed;">${row.derived_term || '-'}</strong></td>
                    <td>${row.item_count || 0}</td>
                    <td>${row.origin || '-'}</td>
                    <td>${row.category || '-'}</td>
                    <td>${clusterBadge}</td>
                    <td>${enrichmentBadge}</td>
                </tr>`;
            }).join('');
        }

        function showRefinedDefinition(termEncoded) {
            const term = decodeURIComponent(termEncoded);
            fetch(`/api/refined/definition/${encodeURIComponent(term)}`)
                .then(r => r.json())
                .then(data => {
                    showRefinedDetailPanel(data);
                });
        }

        function showRefinedDetailPanel(data) {
            const overlay = document.getElementById('detail-overlay');
            const panel = document.getElementById('detail-panel');
            
            // Build items HTML - items housed under the derived term
            let itemsHtml = '';
            if (data.items && data.items.length > 0) {
                itemsHtml = '<div class="detail-section"><h3>Items Under This Definition</h3>';
                itemsHtml += '<div style="max-height:300px; overflow-y:auto;">';
                itemsHtml += data.items.map(item => 
                    `<div class="source-item" style="cursor:default;">
                        <div class="source-item-header">
                            <span class="source-item-name">${item.variation || item.plant_part || 'Base Form'}</span>
                            <span class="badge" style="background:#f3f4f6;color:#6b7280;">${item.form || '-'}</span>
                        </div>
                        <div class="source-item-details">
                            <span>Plant Part: ${item.plant_part || '-'}</span>
                            <span>Refinement: ${item.refinement || '-'}</span>
                        </div>
                    </div>`
                ).join('');
                itemsHtml += '</div></div>';
            }
            
            // Build SAP data HTML
            let sapHtml = '';
            if (data.sap_data) {
                sapHtml = `<div class="detail-section"><h3>Soapmaking Data</h3>
                    <div class="detail-grid">
                        <span class="detail-label">SAP NaOH:</span><span class="detail-value">${data.sap_data.sap_naoh || '-'}</span>
                        <span class="detail-label">SAP KOH:</span><span class="detail-value">${data.sap_data.sap_koh || '-'}</span>
                        <span class="detail-label">Iodine:</span><span class="detail-value">${data.sap_data.iodine_value || '-'}</span>
                        <span class="detail-label">INS:</span><span class="detail-value">${data.sap_data.ins_value || '-'}</span>
                    </div>
                </div>`;
            }
            
            // Build source clusters HTML - at bottom for traceability
            let clustersHtml = '';
            if (data.source_clusters && data.source_clusters.length > 0) {
                clustersHtml = '<div class="detail-section" style="margin-top:20px; padding-top:15px; border-top:2px solid #e5e7eb;"><h3 style="color:#6b7280; font-size:12px;">Source Clusters (Traceability)</h3>';
                clustersHtml += '<div style="display:flex; flex-wrap:wrap; gap:8px;">';
                clustersHtml += data.source_clusters.map(c => 
                    `<span class="badge" style="background:#f0f9ff; color:#0369a1; font-size:10px; padding:4px 8px; cursor:pointer;" onclick="showCompiledCluster('${(c.cluster_id || '').replace(/'/g, "\\'")}')">
                        ${c.cluster_id} (${c.item_count || 0})
                    </span>`
                ).join('');
                clustersHtml += '</div></div>';
            }
            
            panel.innerHTML = `
                <div class="detail-header" style="background:#7c3aed;">
                    <button class="detail-close" onclick="closeDetailPanel()">&times;</button>
                    <h2>${data.derived_term || '-'}</h2>
                    <p>${data.origin || '-'} | ${data.category || '-'} | ${data.item_count || 0} items from ${data.cluster_count || 0} clusters</p>
                </div>
                <div class="detail-body">
                    <div class="detail-section">
                        <h3>Ingredient Definition</h3>
                        <div class="detail-grid">
                            <span class="detail-label">Derived Term:</span><span class="detail-value" style="font-weight:600; color:#7c3aed;">${data.derived_term || '-'}</span>
                            <span class="detail-label">Origin:</span><span class="detail-value">${data.origin || '-'}</span>
                            <span class="detail-label">Category:</span><span class="detail-value">${data.category || '-'}</span>
                        </div>
                    </div>
                    ${sapHtml}
                    ${itemsHtml}
                    ${clustersHtml}
                </div>
            `;
            overlay.classList.add('active');
            panel.classList.add('active');
        }

        function renderCompiledIngredientsView(items) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = (items || []).map(row => {
                return `<tr class="item-row" onclick="showCompiledIngredient('${(row.term || '').replace(/'/g, "\\'")}')">
                    <td><strong>${row.term || '-'}</strong></td>
                    <td>${row.item_count || 0}</td>
                    <td>${row.origin || '-'}</td>
                    <td>${row.ingredient_category || '-'}</td>
                </tr>`;
            }).join('');
        }

        function renderCompiledClustersView(clusters) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = (clusters || []).map((row, idx) => {
                const itemsCompiled = `${row.items_done || 0}/${row.total_items || 0}`;
                const rank = row.rank !== null && row.rank !== undefined ? row.rank : '-';
                const commonName = row.common_name || row.compiled_term || row.raw_canonical_term || '-';
                const priority = row.priority || 0;
                const priorityColor = priority >= 80 ? '#22c55e' : priority >= 50 ? '#eab308' : '#6b7280';
                return `<tr class="item-row" onclick="showCompiledCluster('${(row.cluster_id || '').replace(/'/g, "\\'")}')">
                    <td style="font-weight:bold; color:#6366f1;">${rank}</td>
                    <td style="font-size:11px; max-width:250px; overflow:hidden; text-overflow:ellipsis;" title="${row.cluster_id}">${row.cluster_id}</td>
                    <td><strong>${commonName}</strong></td>
                    <td>${row.total_items || 0}</td>
                    <td>${row.term_status || '-'}</td>
                    <td style="color:${priorityColor}; font-weight:bold;">${priority}</td>
                    <td>${itemsCompiled}</td>
                </tr>`;
            }).join('');
        }

        function renderCompiledItemsView(items) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = (items || []).map(row => {
                const rawSpecs = row.has_raw_specs ? '<span class="badge badge-specs">Raw Specs</span>' : '-';
                const compiledBadge = row.has_compiled ? '<span class="badge badge-compiled">Compiled</span>' : '-';
                return `<tr class="item-row" onclick="showCompiledCluster('${(row.cluster_id || '').replace(/'/g, "\\'")}')">
                    <td style="font-size:11px;">${row.cluster_id || '-'}</td>
                    <td>${row.derived_variation || '-'}</td>
                    <td>${row.derived_physical_form || '-'}</td>
                    <td>${row.item_status || '-'}</td>
                    <td>${rawSpecs}</td>
                    <td>${compiledBadge}</td>
                </tr>`;
            }).join('');
        }
        
        function renderRefinedItemsView(items) {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = (items || []).map(row => {
                const partBadge = row.plant_part ? `<span class="badge" style="background:#dcfce7;color:#166534;">${row.plant_part}</span>` : '-';
                const refBadge = row.refinement ? `<span class="badge" style="background:#fef3c7;color:#92400e;">${row.refinement}</span>` : '-';
                const flagBadge = row.refinement_flag ? `<span class="badge" style="background:#fee2e2;color:#dc2626;">${row.refinement_flag}</span>` : '';
                return `<tr class="item-row" onclick="showCompiledCluster('${(row.cluster_id || '').replace(/'/g, "\\'")}')">
                    <td><strong>${row.derived_term || '-'}</strong></td>
                    <td>${partBadge}</td>
                    <td>${row.variation || '-'}</td>
                    <td>${refBadge}</td>
                    <td>${row.form || '-'}</td>
                    <td>${flagBadge}</td>
                </tr>`;
            }).join('');
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
                const fmtCount = (n) => n > 0 ? n : '<span style="color:#9ca3af;">0</span>';
                
                return `<tr class="item-row" onclick="showClusterDetail('${cluster.cluster_id.replace(/'/g, "\\'")}')">
                    <td style="font-size:11px; max-width:250px; overflow:hidden; text-overflow:ellipsis;" title="${cluster.cluster_id}">${cluster.cluster_id}</td>
                    <td><strong>${cluster.canonical_term || '-'}</strong></td>
                    <td><strong>${cluster.total_items}</strong></td>
                    <td>${fmtCount(cluster.cosing_only)}</td>
                    <td>${fmtCount(cluster.tgsc_only)}</td>
                    <td>${fmtCount(cluster.both_sources)}</td>
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
                    html += `<div class="detail-label">Derived Term</div><div class="detail-value">${data.derived_term || '-'}</div>`;
                    html += `<div class="detail-label">Common Name</div><div class="detail-value">${showValue(tc.canonical_term, rawName)}</div>`;
                    html += `<div class="detail-label">Botanical Key</div><div class="detail-value">${showValue(tc.botanical_key, null)}</div>`;
                    html += `<div class="detail-label">Derived Variation</div><div class="detail-value">${data.derived_variation || '-'}</div>`;
                    html += `<div class="detail-label">Physical Form</div><div class="detail-value">${data.derived_physical_form || '-'}</div>`;
                    html += `<div class="detail-label">Master Category</div><div class="detail-value"><span class="badge badge-compiled">${data.master_category || '-'}</span></div>`;
                    
                    // Refinement flags - patterns identified for future batch processing
                    const flags = data.refinement_flags || [];
                    if (flags.length > 0) {
                        html += `<div class="detail-label">Refinement Flags</div><div class="detail-value">`;
                        flags.forEach(f => {
                            html += `<span class="badge" style="background:#f59e0b;color:#000;margin-right:4px;">${f}</span>`;
                        });
                        html += `</div>`;
                    }
                    
                    html += `<div class="detail-label">CAS Numbers</div><div class="detail-value">${(data.cas_numbers || []).join(', ') || '-'}</div>`;
                    html += `<div class="detail-label">Term Master Categories</div><div class="detail-value">${(td.master_categories || []).join(', ') || '-'}</div>`;
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
                    
                    // Show TGSC-specific fields prominently
                    if (otherSpecs.odor_description) html += `<div class="detail-label">Odor</div><div class="detail-value">${fmt(otherSpecs.odor_description)}</div>`;
                    if (otherSpecs.flavor_description) html += `<div class="detail-label">Flavor</div><div class="detail-value">${fmt(otherSpecs.flavor_description)}</div>`;
                    if (otherSpecs.safety_notes) html += `<div class="detail-label">Safety Notes</div><div class="detail-value">${fmt(otherSpecs.safety_notes)}</div>`;
                    if (otherSpecs.cas_number) html += `<div class="detail-label">CAS (TGSC)</div><div class="detail-value" style="font-family:monospace;">${fmt(otherSpecs.cas_number)}</div>`;
                    if (otherSpecs.fema_number) html += `<div class="detail-label">FEMA Number</div><div class="detail-value">${fmt(otherSpecs.fema_number)}</div>`;
                    
                    // Show remaining other specs
                    const shownKeys = ['odor_description', 'flavor_description', 'safety_notes', 'cas_number', 'fema_number'];
                    for (const [key, val] of Object.entries(otherSpecs)) {
                        if (!pubchemOverlap.includes(key) && !shownKeys.includes(key)) {
                            html += `<div class="detail-label">${key}</div><div class="detail-value">${fmt(val)}</div>`;
                        }
                    }
                    
                    html += '</div></div>';
                    
                    // Descriptors section
                    const descs = data.merged_descriptors || {};
                    if (Object.keys(descs).length > 0) {
                        html += '<div class="detail-section"><h3>Descriptors</h3><div class="detail-grid">';
                        if (descs.category) html += `<div class="detail-label">Category</div><div class="detail-value">${fmt(descs.category)}</div>`;
                        if (descs.url) html += `<div class="detail-label">TGSC Link</div><div class="detail-value"><a href="${descs.url}" target="_blank" style="color:#3b82f6;">View on TGSC</a></div>`;
                        if (descs.synonyms && descs.synonyms.length) html += `<div class="detail-label">Synonyms</div><div class="detail-value">${descs.synonyms.join(', ')}</div>`;
                        if (descs.natural_occurrence && descs.natural_occurrence.length) html += `<div class="detail-label">Natural Occurrence</div><div class="detail-value">${descs.natural_occurrence.join(', ')}</div>`;
                        if (descs.botanical_name) html += `<div class="detail-label">Botanical Name</div><div class="detail-value" style="font-style:italic;">${descs.botanical_name}</div>`;
                        html += '</div></div>';
                    }
                    
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

        function showCompiledIngredient(term) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading...</div>';

            fetch(`/api/compiled/ingredient/${encodeURIComponent(term)}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('detail-title').textContent = data.term || term;
                    document.getElementById('detail-subtitle').textContent = `Compiled ingredient | items: ${(data.items || []).length}`;
                    let html = '<div class="detail-section"><h3>Compiled Base</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Term</div><div class="detail-value">${data.term || '-'}</div>`;
                    html += `<div class="detail-label">Origin</div><div class="detail-value">${data.origin || '-'}</div>`;
                    html += `<div class="detail-label">Primary Category</div><div class="detail-value">${data.ingredient_category || '-'}</div>`;
                    html += `<div class="detail-label">Refinement</div><div class="detail-value">${data.refinement_level || '-'}</div>`;
                    html += `<div class="detail-label">INCI</div><div class="detail-value">${data.inci_name || '-'}</div>`;
                    html += `<div class="detail-label">CAS</div><div class="detail-value">${data.cas_number || '-'}</div>`;
                    html += '</div></div>';
                    if (data.payload_json) {
                        html += `<div class="detail-section"><h3>payload_json</h3><div class="json-block"><pre>${JSON.stringify(data.payload_json, null, 2)}</pre></div></div>`;
                    }
                    if (data.items && data.items.length) {
                        html += `<div class="detail-section"><h3>Items (${data.items.length})</h3>`;
                        data.items.forEach(it => {
                            html += `<div class="source-item" onclick="showCompiledItem(${it.id})">
                                <div class="source-item-header">
                                    <span class="source-item-name">${it.item_name || '(no name)'}</span>
                                    <span class="badge" style="background:#e0f2fe;color:#0369a1;">${it.status || 'unknown'}</span>
                                </div>
                                <div class="source-item-details">
                                    <span>Variation: ${it.variation || '-'}</span>
                                    <span>Form: ${it.physical_form || '-'}</span>
                                </div>
                            </div>`;
                        });
                        html += '</div>';
                    }
                    document.getElementById('detail-body').innerHTML = html;
                });
        }

        function showCompiledCluster(clusterId) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading...</div>';

            fetch(`/api/compiled/cluster/${encodeURIComponent(clusterId)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('detail-title').textContent = 'Error';
                        document.getElementById('detail-body').innerHTML = `<div class="loading">${data.error}</div>`;
                        return;
                    }
                    document.getElementById('detail-title').textContent = data.compiled_term || data.raw_canonical_term || clusterId;
                    document.getElementById('detail-subtitle').textContent = `Compiled cluster | term: ${data.term_status || '-'} | items: ${(data.items_done || 0)}/${(data.total_items || 0)}`;
                    
                    // Identity section
                    let html = '<div class="detail-section"><h3>Identity</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Common Name</div><div class="detail-value"><strong style="font-size:16px;">${data.common_name || data.compiled_term || '<span style="color:#ef4444;">MISSING</span>'}</strong></div>`;
                    html += `<div class="detail-label">Botanical Name</div><div class="detail-value"><em>${data.botanical_name || '<span style="color:#ef4444;">MISSING</span>'}</em></div>`;
                    html += `<div class="detail-label">INCI Name</div><div class="detail-value">${data.inci_name || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">CAS Number</div><div class="detail-value" style="font-family:monospace;">${data.cas_number || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += '</div></div>';
                    
                    // Classification section
                    html += '<div class="detail-section"><h3>Classification</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Origin</div><div class="detail-value">${data.origin || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">Category</div><div class="detail-value">${data.ingredient_category || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">Base Refinement</div><div class="detail-value">${data.refinement_level || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">Derived From</div><div class="detail-value">${data.derived_from || '<span style="color:#9ca3af;">N/A</span>'}</div>`;
                    html += '</div></div>';
                    
                    // Descriptions section
                    html += '<div class="detail-section"><h3>Descriptions</h3>';
                    html += `<div class="detail-grid"><div class="detail-label">Short Description</div><div class="detail-value">${data.short_description || '<span style="color:#ef4444;">MISSING</span>'}</div></div>`;
                    html += `<div class="detail-grid"><div class="detail-label">Detailed Description</div><div class="detail-value">${data.detailed_description || '<span style="color:#ef4444;">MISSING</span>'}</div></div>`;
                    html += '</div>';
                    
                    // Metadata section
                    html += '<div class="detail-section"><h3>Metadata</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Cluster ID</div><div class="detail-value" style="font-size:10px;word-break:break-all;">${data.cluster_id || clusterId}</div>`;
                    html += `<div class="detail-label">Raw Source Term</div><div class="detail-value">${data.raw_canonical_term || '-'}</div>`;
                    html += `<div class="detail-label">Term Status</div><div class="detail-value">${data.term_status || '-'}</div>`;
                    html += '</div></div>';
                    if (data.items && data.items.length) {
                        html += `<div class="detail-section"><h3>Items (${data.items.length})</h3>`;
                        data.items.forEach(it => {
                            const rawBadge = it.has_raw_specs ? '<span class="badge badge-specs">Raw Specs</span>' : '';
                            const compBadge = it.has_compiled ? '<span class="badge badge-compiled">Compiled</span>' : '';
                            const statusColor = it.item_status === 'done' ? 'background:#d1fae5;color:#065f46;' : 'background:#e5e7eb;color:#111827;';
                            html += `<div class="source-item" onclick="showCompiledClusterItem('${data.cluster_id}', ${it.merged_item_form_id})">
                                <div class="source-item-header">
                                    <span class="source-item-name">${it.derived_variation || '(no variation)'} • ${it.derived_physical_form || '(no form)'}</span>
                                    <span class="badge" style="${statusColor}">${it.item_status || '-'}</span>
                                    ${rawBadge}
                                    ${compBadge}
                                </div>
                                <div class="source-item-details">
                                    <span>MIF ID: ${it.merged_item_form_id || '-'}</span>
                                </div>
                            </div>`;
                        });
                        html += '</div>';
                    }
                    document.getElementById('detail-body').innerHTML = html;
                });
        }
        
        function showCompiledClusterItem(clusterId, mifId) {
            document.getElementById('source-detail-panel').classList.add('active');
            document.getElementById('source-detail-body').innerHTML = '<div class="loading">Loading...</div>';
            
            fetch(`/api/compiled/cluster-item/${encodeURIComponent(clusterId)}/${mifId}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('source-detail-title').textContent = 'Error';
                        document.getElementById('source-detail-body').innerHTML = `<div class="loading">${data.error}</div>`;
                        return;
                    }
                    document.getElementById('source-detail-title').textContent = `${data.derived_variation || data.derived_term} • ${data.derived_physical_form || ''}`;
                    document.getElementById('source-detail-subtitle').textContent = `MIF ID: ${mifId} | Status: ${data.item_status || '-'}`;
                    
                    let html = '<div class="detail-section"><h3>Item Identity</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Compiled Term</div><div class="detail-value">${data.compiled_term || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">Variation</div><div class="detail-value">${data.derived_variation || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">Physical Form</div><div class="detail-value">${data.derived_physical_form || '<span style="color:#ef4444;">MISSING</span>'}</div>`;
                    html += `<div class="detail-label">Master Category</div><div class="detail-value"><span class="badge badge-compiled">${data.master_category || '-'}</span></div>`;
                    html += `<div class="detail-label">Status</div><div class="detail-value">${data.item_status || '-'}</div>`;
                    
                    // Refinement flags - patterns identified for future batch processing
                    const flags = data.refinement_flags || [];
                    if (flags.length > 0) {
                        html += `<div class="detail-label">Refinement Flags</div><div class="detail-value">`;
                        flags.forEach(f => {
                            html += `<span class="badge" style="background:#f59e0b;color:#000;margin-right:4px;">${f}</span>`;
                        });
                        html += `</div>`;
                    }
                    html += '</div></div>';
                    
                    // Source Data
                    if (data.source_data && Object.keys(data.source_data).length) {
                        html += '<div class="detail-section"><h3>Source Data</h3><div class="detail-grid">';
                        if (data.source_data.cas_numbers && data.source_data.cas_numbers.length) {
                            html += `<div class="detail-label">CAS Numbers</div><div class="detail-value" style="font-family:monospace;">${data.source_data.cas_numbers.join(', ')}</div>`;
                        }
                        html += `<div class="detail-label">Has CosIng</div><div class="detail-value">${data.source_data.has_cosing ? 'Yes' : 'No'}</div>`;
                        html += `<div class="detail-label">Has TGSC</div><div class="detail-value">${data.source_data.has_tgsc ? 'Yes' : 'No'}</div>`;
                        html += `<div class="detail-label">Has Seed</div><div class="detail-value">${data.source_data.has_seed ? 'Yes' : 'No'}</div>`;
                        // Show merged_specs as attributes
                        const specs = data.source_data.merged_specs || {};
                        if (specs.cas_number) html += `<div class="detail-label">CAS Number</div><div class="detail-value" style="font-family:monospace;">${specs.cas_number}</div>`;
                        if (specs.odor_description) html += `<div class="detail-label">Odor</div><div class="detail-value">${specs.odor_description}</div>`;
                        if (specs.flavor_description) html += `<div class="detail-label">Flavor</div><div class="detail-value">${specs.flavor_description}</div>`;
                        if (specs.safety_notes) html += `<div class="detail-label">Safety Notes</div><div class="detail-value">${specs.safety_notes}</div>`;
                        if (specs.solubility) html += `<div class="detail-label">Solubility</div><div class="detail-value">${specs.solubility}</div>`;
                        if (specs.boiling_point_c) html += `<div class="detail-label">Boiling Point</div><div class="detail-value">${specs.boiling_point_c}°C</div>`;
                        if (specs.melting_point_c) html += `<div class="detail-label">Melting Point</div><div class="detail-value">${specs.melting_point_c}°C</div>`;
                        if (specs.density) html += `<div class="detail-label">Density</div><div class="detail-value">${specs.density}</div>`;
                        if (specs.molecular_weight) html += `<div class="detail-label">Molecular Weight</div><div class="detail-value">${specs.molecular_weight}</div>`;
                        if (specs.molecular_formula) html += `<div class="detail-label">Molecular Formula</div><div class="detail-value" style="font-family:monospace;">${specs.molecular_formula}</div>`;
                        html += '</div></div>';
                    }
                    
                    // Compiled Item Data (AI-generated) - show as attributes
                    const cj = data.item_json || {};
                    if (Object.keys(cj).length) {
                        html += '<div class="detail-section"><h3>AI-Compiled Data</h3>';
                        // Description at the top
                        if (cj.description) html += `<div style="margin-bottom:12px;font-style:italic;color:#374151;">${cj.description}</div>`;
                        html += '<div class="detail-grid">';
                        if (cj.physical_form) html += `<div class="detail-label">Physical Form</div><div class="detail-value">${cj.physical_form}</div>`;
                        if (cj.processing_method) {
                            const pm = typeof cj.processing_method === 'object' ? (cj.processing_method.value || 'N/A') : cj.processing_method;
                            html += `<div class="detail-label">Processing Method</div><div class="detail-value">${pm}</div>`;
                        }
                        if (cj.color) html += `<div class="detail-label">Color</div><div class="detail-value">${cj.color}</div>`;
                        if (cj.odor_profile) html += `<div class="detail-label">Odor Profile</div><div class="detail-value">${cj.odor_profile}</div>`;
                        if (cj.flavor_profile) html += `<div class="detail-label">Flavor Profile</div><div class="detail-value">${cj.flavor_profile}</div>`;
                        if (cj.default_unit) html += `<div class="detail-label">Default Unit</div><div class="detail-value"><strong style="color:#059669;">${cj.default_unit}</strong></div>`;
                        if (cj.shelf_life_days) html += `<div class="detail-label">Shelf Life</div><div class="detail-value">${cj.shelf_life_days} days</div>`;
                        html += '</div>';
                        // Applications
                        if (cj.applications && cj.applications.length) {
                            html += `<div style="margin:8px 0;"><strong>Applications:</strong> ${cj.applications.map(a => '<span class="badge" style="background:#dbeafe;color:#1e40af;margin:2px;">' + a + '</span>').join(' ')}</div>`;
                        }
                        // Function Tags
                        if (cj.function_tags && cj.function_tags.length) {
                            html += `<div style="margin:8px 0;"><strong>Functions:</strong> ${cj.function_tags.map(t => '<span class="badge" style="background:#fef3c7;color:#92400e;margin:2px;">' + t + '</span>').join(' ')}</div>`;
                        }
                        // Safety Tags
                        if (cj.safety_tags && cj.safety_tags.length) {
                            html += `<div style="margin:8px 0;"><strong>Safety:</strong> ${cj.safety_tags.map(t => '<span class="badge" style="background:#fee2e2;color:#991b1b;margin:2px;">' + t + '</span>').join(' ')}</div>`;
                        }
                        // Storage
                        if (cj.storage) {
                            html += '<div class="detail-grid" style="margin-top:8px;">';
                            if (cj.storage.temperature_celsius) {
                                const temp = cj.storage.temperature_celsius;
                                html += `<div class="detail-label">Storage Temp</div><div class="detail-value">${temp.min || '?'}°C - ${temp.max || '?'}°C</div>`;
                            }
                            if (cj.storage.humidity_percent && cj.storage.humidity_percent.max) {
                                html += `<div class="detail-label">Max Humidity</div><div class="detail-value">${cj.storage.humidity_percent.max}%</div>`;
                            }
                            if (cj.storage.special_instructions) {
                                html += `<div class="detail-label">Storage Notes</div><div class="detail-value">${cj.storage.special_instructions}</div>`;
                            }
                            html += '</div>';
                        }
                        // Specifications - show ALL fields regardless of value
                        if (cj.specifications) {
                            html += '<div class="detail-grid" style="margin-top:8px;">';
                            const sp = cj.specifications;
                            html += `<div class="detail-label">SAP (NaOH)</div><div class="detail-value">${sp.sap_naoh ?? 'N/A'}</div>`;
                            html += `<div class="detail-label">SAP (KOH)</div><div class="detail-value">${sp.sap_koh ?? 'N/A'}</div>`;
                            html += `<div class="detail-label">Iodine Value</div><div class="detail-value">${sp.iodine_value ?? 'N/A'}</div>`;
                            html += `<div class="detail-label">Density</div><div class="detail-value">${sp.density_g_ml ?? 'N/A'}${sp.density_g_ml && sp.density_g_ml !== 'N/A' && sp.density_g_ml !== 'Not Found' ? ' g/mL' : ''}</div>`;
                            html += `<div class="detail-label">Flash Point</div><div class="detail-value">${sp.flash_point_celsius ?? 'N/A'}${typeof sp.flash_point_celsius === 'number' ? '°C' : ''}</div>`;
                            const mp = sp.melting_point_celsius || {};
                            html += `<div class="detail-label">Melting Point</div><div class="detail-value">${mp.min ?? '?'}°C - ${mp.max ?? '?'}°C</div>`;
                            const ph = sp.ph_range || {};
                            html += `<div class="detail-label">pH Range</div><div class="detail-value">${ph.min ?? '?'} - ${ph.max ?? '?'}</div>`;
                            html += `<div class="detail-label">Solubility</div><div class="detail-value">${sp.solubility ?? 'N/A'}</div>`;
                            html += `<div class="detail-label">Safety Notes</div><div class="detail-value">${sp.safety_notes ?? 'N/A'}</div>`;
                            const ur = sp.usage_rate_percent || {};
                            html += `<div class="detail-label">Leave-on Max</div><div class="detail-value">${ur.leave_on_max ?? 'N/A'}${typeof ur.leave_on_max === 'number' ? '%' : ''}</div>`;
                            html += `<div class="detail-label">Rinse-off Max</div><div class="detail-value">${ur.rinse_off_max ?? 'N/A'}${typeof ur.rinse_off_max === 'number' ? '%' : ''}</div>`;
                            html += '</div>';
                        }
                        // Sourcing
                        if (cj.sourcing) {
                            html += '<div class="detail-grid" style="margin-top:8px;">';
                            if (cj.sourcing.common_origins && cj.sourcing.common_origins.length) {
                                html += `<div class="detail-label">Common Origins</div><div class="detail-value">${cj.sourcing.common_origins.join(', ')}</div>`;
                            }
                            if (cj.sourcing.certifications && cj.sourcing.certifications.length) {
                                html += `<div class="detail-label">Certifications</div><div class="detail-value">${cj.sourcing.certifications.join(', ')}</div>`;
                            }
                            if (cj.sourcing.sustainability_notes) {
                                html += `<div class="detail-label">Sustainability</div><div class="detail-value">${cj.sourcing.sustainability_notes}</div>`;
                            }
                            html += '</div>';
                        }
                        html += '</div>';
                    }
                    
                    // Soapmaking Enrichment Data - ALWAYS show, even if empty
                    html += '<div class="detail-section" style="background:#fef3c7;border-radius:8px;padding:12px;margin-bottom:20px;"><h3 style="color:#92400e;margin-top:0;">Soapmaking Data</h3>';
                    html += '<div class="detail-grid">';
                    html += `<div class="detail-label">Protected</div><div class="detail-value">${data.protected_flag ? '<span style="color:#059669;font-weight:600;">Yes</span>' : '<span style="color:#9ca3af;">No</span>'}</div>`;
                    html += `<div class="detail-label">SAP (NaOH)</div><div class="detail-value">${data.sap_naoh ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">SAP (KOH)</div><div class="detail-value">${data.sap_koh ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Iodine Value</div><div class="detail-value">${data.iodine_value ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">INS Value</div><div class="detail-value">${data.ins_value ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Enrichment Source</div><div class="detail-value">${data.enrichment_source ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Enrichment Date</div><div class="detail-value">${data.enrichment_date ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += '</div>';
                    
                    // Fatty Acids
                    html += '<div style="margin-top:12px;"><strong style="color:#92400e;">Fatty Acid Profile:</strong></div>';
                    html += '<div class="detail-grid" style="margin-top:8px;">';
                    const fa = data.fatty_acids || {};
                    html += `<div class="detail-label">Lauric</div><div class="detail-value">${fa.lauric ?? '<span style="color:#9ca3af;">-</span>'}${fa.lauric ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Myristic</div><div class="detail-value">${fa.myristic ?? '<span style="color:#9ca3af;">-</span>'}${fa.myristic ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Palmitic</div><div class="detail-value">${fa.palmitic ?? '<span style="color:#9ca3af;">-</span>'}${fa.palmitic ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Stearic</div><div class="detail-value">${fa.stearic ?? '<span style="color:#9ca3af;">-</span>'}${fa.stearic ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Ricinoleic</div><div class="detail-value">${fa.ricinoleic ?? '<span style="color:#9ca3af;">-</span>'}${fa.ricinoleic ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Oleic</div><div class="detail-value">${fa.oleic ?? '<span style="color:#9ca3af;">-</span>'}${fa.oleic ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Linoleic</div><div class="detail-value">${fa.linoleic ?? '<span style="color:#9ca3af;">-</span>'}${fa.linoleic ? '%' : ''}</div>`;
                    html += `<div class="detail-label">Linolenic</div><div class="detail-value">${fa.linolenic ?? '<span style="color:#9ca3af;">-</span>'}${fa.linolenic ? '%' : ''}</div>`;
                    html += '</div>';
                    
                    // Soap Properties
                    html += '<div style="margin-top:12px;"><strong style="color:#92400e;">Soap Quality Properties:</strong></div>';
                    html += '<div class="detail-grid" style="margin-top:8px;">';
                    const sp = data.soap_properties || {};
                    html += `<div class="detail-label">Hardness</div><div class="detail-value">${sp.hardness ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Cleansing</div><div class="detail-value">${sp.cleansing ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Bubbly Lather</div><div class="detail-value">${sp.bubbly_lather ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Creamy Lather</div><div class="detail-value">${sp.creamy_lather ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += `<div class="detail-label">Conditioning</div><div class="detail-value">${sp.conditioning ?? '<span style="color:#9ca3af;">-</span>'}</div>`;
                    html += '</div>';
                    
                    // Use Case Tags
                    const useCases = data.use_case_tags || [];
                    html += `<div style="margin-top:12px;"><strong style="color:#92400e;">Use Cases:</strong> `;
                    if (useCases.length) {
                        useCases.forEach(t => { html += `<span class="badge" style="background:#fde68a;color:#92400e;margin:2px;">${t}</span>`; });
                    } else {
                        html += '<span style="color:#9ca3af;">None tagged</span>';
                    }
                    html += '</div></div>';
                    
                    // Raw pre-compilation data - show as attributes
                    const rj = data.raw_item_json || {};
                    if (Object.keys(rj).length) {
                        html += '<div class="detail-section"><h3>Pre-Compilation Data</h3><div class="detail-grid">';
                        if (rj.derived_term) html += `<div class="detail-label">Derived Term</div><div class="detail-value">${rj.derived_term}</div>`;
                        if (rj.derived_variation) html += `<div class="detail-label">Variation</div><div class="detail-value">${rj.derived_variation}</div>`;
                        if (rj.derived_physical_form) html += `<div class="detail-label">Physical Form</div><div class="detail-value">${rj.derived_physical_form}</div>`;
                        if (rj.cas_numbers && rj.cas_numbers.length) html += `<div class="detail-label">CAS Numbers</div><div class="detail-value">${rj.cas_numbers.join(', ')}</div>`;
                        if (rj.derived_parts && rj.derived_parts.length) html += `<div class="detail-label">Parts</div><div class="detail-value">${rj.derived_parts.join(', ')}</div>`;
                        // Merged specs
                        const ms = rj.merged_specs || {};
                        if (ms.cas_number) html += `<div class="detail-label">CAS Number</div><div class="detail-value" style="font-family:monospace;">${ms.cas_number}</div>`;
                        if (ms.odor_description) html += `<div class="detail-label">Odor</div><div class="detail-value">${ms.odor_description}</div>`;
                        if (ms.flavor_description) html += `<div class="detail-label">Flavor</div><div class="detail-value">${ms.flavor_description}</div>`;
                        if (ms.safety_notes) html += `<div class="detail-label">Safety Notes</div><div class="detail-value">${ms.safety_notes}</div>`;
                        if (ms.solubility) html += `<div class="detail-label">Solubility</div><div class="detail-value">${ms.solubility}</div>`;
                        if (ms.boiling_point_c) html += `<div class="detail-label">Boiling Point</div><div class="detail-value">${ms.boiling_point_c}°C</div>`;
                        if (ms.melting_point_c) html += `<div class="detail-label">Melting Point</div><div class="detail-value">${ms.melting_point_c}°C</div>`;
                        if (ms.density) html += `<div class="detail-label">Density</div><div class="detail-value">${ms.density}</div>`;
                        if (ms.molecular_weight) html += `<div class="detail-label">Molecular Weight</div><div class="detail-value">${ms.molecular_weight}</div>`;
                        if (ms.molecular_formula) html += `<div class="detail-label">Molecular Formula</div><div class="detail-value" style="font-family:monospace;">${ms.molecular_formula}</div>`;
                        html += '</div></div>';
                    }
                    
                    document.getElementById('source-detail-body').innerHTML = html;
                });
        }

        function showCompiledItem(id) {
            document.getElementById('detail-overlay').classList.add('active');
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-body').innerHTML = '<div class="loading">Loading...</div>';

            fetch(`/api/compiled/item/${id}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('detail-title').textContent = data.item_name || `Item #${id}`;
                    document.getElementById('detail-subtitle').textContent = `Ingredient: ${data.ingredient_term || '-'} | Status: ${data.status || '-'}`;
                    let html = '<div class="detail-section"><h3>Compiled Item</h3><div class="detail-grid">';
                    html += `<div class="detail-label">Ingredient</div><div class="detail-value">${data.ingredient_term || '-'}</div>`;
                    html += `<div class="detail-label">Item Name</div><div class="detail-value">${data.item_name || '-'}</div>`;
                    html += `<div class="detail-label">Variation</div><div class="detail-value">${data.variation || '-'}</div>`;
                    html += `<div class="detail-label">Form</div><div class="detail-value">${data.physical_form || '-'}</div>`;
                    html += `<div class="detail-label">Status</div><div class="detail-value">${data.status || '-'}</div>`;
                    html += '</div></div>';
                    if (data.item_json) {
                        html += `<div class="detail-section"><h3>item_json</h3><div class="json-block"><pre>${JSON.stringify(data.item_json, null, 2)}</pre></div></div>`;
                    }
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
            const dataset = currentDataset;
            window.location.href = `/api/export/${format}?dataset=${dataset}&filter=${currentFilter}&view=${currentView}&search=${encodeURIComponent(search)}`;
        }
        
        function exportAnalysis() {
            const search = document.getElementById('search').value;
            const category = document.getElementById('category-filter').value;
            window.location.href = `/api/export-analysis?filter=${currentFilter}&search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&cluster_size=${currentClusterSize}`;
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeDetail();
        });
        
        function loadStats() {
            fetch(`/api/stats?dataset=${currentDataset}`)
                .then(r => r.json())
                .then(stats => {
                    if (currentDataset === 'refined') {
                        document.getElementById('rstat-definitions').textContent = (stats.definitions || 0).toLocaleString();
                        document.getElementById('rstat-source-clusters').textContent = (stats.source_clusters || 0).toLocaleString();
                        document.getElementById('rstat-total-items').textContent = (stats.total_items || 0).toLocaleString();
                        document.getElementById('rstat-enriched').textContent = (stats.enriched || 0).toLocaleString();
                        document.getElementById('rstat-plant').textContent = (stats.plant || 0).toLocaleString();
                        document.getElementById('rstat-synthetic').textContent = (stats.synthetic || 0).toLocaleString();
                        document.getElementById('rstat-mineral').textContent = (stats.mineral || 0).toLocaleString();
                        document.getElementById('rstat-animal').textContent = (stats.animal || 0).toLocaleString();
                    } else if (currentDataset === 'compiled') {
                        document.getElementById('cstat-queued-items').textContent = (stats.queued_items || 0).toLocaleString();
                        document.getElementById('cstat-clusters').textContent = (stats.clusters || 0).toLocaleString();
                        document.getElementById('cstat-composites').textContent = (stats.composites || 0).toLocaleString();
                        document.getElementById('cstat-stage1-done').textContent = (stats.stage1_done || 0).toLocaleString();
                        document.getElementById('cstat-stage1-pending').textContent = (stats.stage1_pending || 0).toLocaleString();
                        const stage1Total = (stats.stage1_done || 0) + (stats.stage1_pending || 0);
                        const stage1Pct = stage1Total > 0 ? Math.round((stats.stage1_done || 0) / stage1Total * 100) : 0;
                        document.getElementById('cstat-stage1-pct').textContent = stage1Pct + '%';
                        document.getElementById('cstat-stage2-done').textContent = (stats.stage2_done || 0).toLocaleString();
                        document.getElementById('cstat-stage2-batch-pending').textContent = (stats.stage2_batch_pending || 0).toLocaleString();
                        document.getElementById('cstat-stage2-pending').textContent = (stats.stage2_pending || 0).toLocaleString();
                        const stage2Total = (stats.stage2_done || 0) + (stats.stage2_batch_pending || 0) + (stats.stage2_pending || 0);
                        const stage2Pct = stage2Total > 0 ? Math.round((stats.stage2_done || 0) / stage2Total * 100) : 0;
                        document.getElementById('cstat-stage2-pct').textContent = stage2Pct + '%';
                        document.getElementById('cstat-zero-items').textContent = (stats.zero_items || 0).toLocaleString();
                        document.getElementById('cstat-single-item').textContent = (stats.single_item || 0).toLocaleString();
                        document.getElementById('cstat-multi-item').textContent = (stats.multi_item || 0).toLocaleString();
                    } else {
                        document.getElementById('stat-source-items').textContent = (stats.source_items || 0).toLocaleString();
                        document.getElementById('stat-cosing-items').textContent = (stats.cosing_items || 0).toLocaleString();
                        document.getElementById('stat-tgsc-items').textContent = (stats.tgsc_items || 0).toLocaleString();
                        document.getElementById('stat-total-merged').textContent = (stats.total_merged || 0).toLocaleString();
                        document.getElementById('stat-cosing-only').textContent = (stats.cosing_only || 0).toLocaleString();
                        document.getElementById('stat-tgsc-only').textContent = (stats.tgsc_only || 0).toLocaleString();
                        document.getElementById('stat-both-sources').textContent = (stats.both_sources || 0).toLocaleString();
                        document.getElementById('stat-pubchem-enriched').textContent = (stats.pubchem_enriched || 0).toLocaleString();
                        document.getElementById('stat-total-clusters').textContent = (stats.total_clusters || 0).toLocaleString();
                        document.getElementById('stat-composites').textContent = (stats.composites || 0).toLocaleString();
                    }
                });
        }

        loadCategories();
        loadStats();
        loadData();
    </script>
</body>
</html>
"""

def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
        return cur.fetchone() is not None
    except Exception:
        return False

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
    
    cur.execute("SELECT COUNT(*) FROM source_items")
    stats['source_items'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM source_items WHERE source = 'cosing'")
    stats['cosing_items'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM source_items WHERE source = 'tgsc'")
    stats['tgsc_items'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms")
    stats['total_merged'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND has_tgsc = 0")
    stats['cosing_only'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1 AND has_cosing = 0")
    stats['tgsc_only'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND has_tgsc = 1")
    stats['both_sources'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE merged_specs_json LIKE '%pubchem%'")
    stats['pubchem_enriched'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM clusters")
    stats['total_clusters'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM source_items WHERE is_composite = 1")
    stats['composites'] = cur.fetchone()[0]
    
    conn.close()
    return render_template_string(HTML_TEMPLATE, stats=stats)


@app.route('/api/stats')
def api_stats():
    dataset = (request.args.get("dataset") or "raw").strip().lower()
    conn = get_db('final')
    cur = conn.cursor()
    stats = {
        "source_items": 0,
        "cosing_items": 0,
        "tgsc_items": 0,
        "total_merged": 0,
        "cosing_only": 0,
        "tgsc_only": 0,
        "both_sources": 0,
        "pubchem_enriched": 0,
        "total_clusters": 0,
        "composites": 0,
    }

    if dataset == "refined":
        refined_stats = {
            "definitions": 0,
            "source_clusters": 0,
            "total_items": 0,
            "enriched": 0,
            "plant": 0,
            "synthetic": 0,
            "mineral": 0,
            "animal": 0,
        }
        
        if _table_exists(conn, "compiled_cluster_items"):
            cur.execute("SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items")
            refined_stats["definitions"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT cluster_id) FROM compiled_cluster_items")
            refined_stats["source_clusters"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM compiled_cluster_items")
            refined_stats["total_items"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM compiled_cluster_items WHERE sap_naoh IS NOT NULL")
            refined_stats["enriched"] = cur.fetchone()[0]
            
            # Origin counts from compiled_clusters
            if _table_exists(conn, "compiled_clusters"):
                cur.execute("SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items i JOIN compiled_clusters c ON i.cluster_id = c.cluster_id WHERE LOWER(c.origin) LIKE '%plant%'")
                refined_stats["plant"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items i JOIN compiled_clusters c ON i.cluster_id = c.cluster_id WHERE LOWER(c.origin) LIKE '%synth%'")
                refined_stats["synthetic"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items i JOIN compiled_clusters c ON i.cluster_id = c.cluster_id WHERE LOWER(c.origin) LIKE '%mineral%'")
                refined_stats["mineral"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items i JOIN compiled_clusters c ON i.cluster_id = c.cluster_id WHERE LOWER(c.origin) LIKE '%animal%'")
                refined_stats["animal"] = cur.fetchone()[0]
        
        conn.close()
        return jsonify(refined_stats)

    if dataset == "compiled":
        compiled_stats = {
            "queued_items": 0,
            "clusters": 0,
            "composites": 0,
            "stage1_done": 0,
            "stage1_pending": 0,
            "stage2_done": 0,
            "stage2_pending": 0,
            "zero_items": 0,
            "single_item": 0,
            "multi_item": 0,
        }
        
        if _table_exists(conn, "compiled_cluster_items"):
            cur.execute("SELECT COUNT(*) FROM compiled_cluster_items")
            compiled_stats["queued_items"] = cur.fetchone()[0]
        
        if _table_exists(conn, "clusters"):
            cur.execute("SELECT COUNT(*) FROM clusters WHERE cluster_id NOT LIKE 'composite:%'")
            compiled_stats["clusters"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM clusters WHERE cluster_id LIKE 'composite:%'")
            compiled_stats["composites"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM clusters WHERE canonical_term IS NOT NULL AND canonical_term != ''")
            compiled_stats["stage1_done"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM clusters WHERE canonical_term IS NULL OR canonical_term = ''")
            compiled_stats["stage1_pending"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM clusters WHERE cluster_id NOT LIKE 'composite:%' AND item_count = 0")
            compiled_stats["zero_items"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM clusters WHERE cluster_id NOT LIKE 'composite:%' AND item_count = 1")
            compiled_stats["single_item"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM clusters WHERE cluster_id NOT LIKE 'composite:%' AND item_count > 1")
            compiled_stats["multi_item"] = cur.fetchone()[0]
        
        # Stage 2: Count from compiled_cluster_items if exists, else from merged_item_forms
        if _table_exists(conn, "compiled_cluster_items"):
            cur.execute("SELECT COUNT(*) FROM compiled_cluster_items WHERE item_status = 'done'")
            compiled_stats["stage2_done"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM compiled_cluster_items WHERE item_status = 'batch_pending'")
            compiled_stats["stage2_batch_pending"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM compiled_cluster_items WHERE item_status = 'pending'")
            compiled_stats["stage2_pending"] = cur.fetchone()[0]
        else:
            cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE compiled_specs_json IS NOT NULL AND compiled_specs_json != '{}'")
            compiled_stats["stage2_done"] = cur.fetchone()[0]
            compiled_stats["stage2_batch_pending"] = 0
            cur.execute("SELECT COUNT(*) FROM merged_item_forms")
            compiled_stats["stage2_pending"] = cur.fetchone()[0] - compiled_stats["stage2_done"]
        
        conn.close()
        return jsonify(compiled_stats)

    cur.execute("SELECT COUNT(*) FROM source_items")
    stats["source_items"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM source_items WHERE source = 'cosing'")
    stats["cosing_items"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM source_items WHERE source = 'tgsc'")
    stats["tgsc_items"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM merged_item_forms")
    stats["total_merged"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND has_tgsc = 0")
    stats["cosing_only"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_tgsc = 1 AND has_cosing = 0")
    stats["tgsc_only"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE has_cosing = 1 AND has_tgsc = 1")
    stats["both_sources"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM merged_item_forms WHERE merged_specs_json LIKE '%pubchem%'")
    stats["pubchem_enriched"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM clusters")
    stats["total_clusters"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM source_items WHERE is_composite = 1")
    stats["composites"] = cur.fetchone()[0]
    conn.close()
    return jsonify(stats)

@app.route('/api/categories')
def api_categories():
    dataset = (request.args.get("dataset") or "raw").strip().lower()
    conn = get_db('final')
    cur = conn.cursor()
    if dataset == "compiled":
        # Prefer cluster-mirror compiled categories when present; fallback to legacy ingredients.
        if _table_exists(conn, "compiled_clusters"):
            cur.execute("""
                SELECT ingredient_category, COUNT(*) as cnt
                FROM compiled_clusters
                WHERE ingredient_category IS NOT NULL AND ingredient_category != ''
                GROUP BY ingredient_category
                ORDER BY cnt DESC
            """)
            categories = [{'name': row[0], 'count': row[1]} for row in cur.fetchall()]
            conn.close()
            return jsonify({'categories': categories})
        if not _table_exists(conn, "ingredients"):
            conn.close()
            return jsonify({"categories": []})
        cur.execute("""
            SELECT ingredient_category, COUNT(*) as cnt
            FROM ingredients
            WHERE ingredient_category IS NOT NULL AND ingredient_category != ''
            GROUP BY ingredient_category
            ORDER BY cnt DESC
        """)
        categories = [{'name': row[0], 'count': row[1]} for row in cur.fetchall()]
        conn.close()
        return jsonify({'categories': categories})

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


@app.route("/api/compiled/ingredients")
def api_compiled_ingredients():
    page = int(request.args.get("page", 1))
    search = (request.args.get("search") or "").strip()
    category = (request.args.get("category") or "").strip()
    per_page = 50
    offset = (page - 1) * per_page

    conn = get_db("final")
    cur = conn.cursor()
    
    # Use compiled_cluster_items for terms view
    if _table_exists(conn, "compiled_cluster_items"):
        where_clauses = []
        params = []
        if search:
            where_clauses.append("derived_term LIKE ?")
            params.append(f"%{search}%")
        if category:
            where_clauses.append("json_extract(item_json, '$.master_category') = ?")
            params.append(category)
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count unique terms
        cur.execute(f"SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items {where_sql}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT derived_term, 
                   json_extract(item_json, '$.master_category') as category,
                   COUNT(*) as item_count,
                   GROUP_CONCAT(DISTINCT derived_variation) as variations
            FROM compiled_cluster_items
            {where_sql}
            GROUP BY derived_term
            ORDER BY derived_term
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        )
        rows = cur.fetchall()

        ingredients = [
            {
                "term": r[0], 
                "origin": "compiled", 
                "ingredient_category": r[1] or "N/A", 
                "item_count": int(r[2] or 0),
                "variations": r[3] or ""
            }
            for r in rows
        ]
        total_pages = max(1, (total + per_page - 1) // per_page)
        conn.close()
        return jsonify({"ingredients": ingredients, "total": total, "total_pages": total_pages, "page": page})
    
    # Fallback to legacy ingredients table
    if not _table_exists(conn, "ingredients"):
        conn.close()
        return jsonify({"ingredients": [], "total": 0, "total_pages": 1, "page": page})

    where_clauses = []
    params = []
    if search:
        where_clauses.append("term LIKE ?")
        params.append(f"%{search}%")
    if category:
        where_clauses.append("ingredient_category = ?")
        params.append(category)
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cur.execute(f"SELECT COUNT(*) FROM ingredients {where_sql}", params)
    total = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT term, origin, ingredient_category
        FROM ingredients
        {where_sql}
        ORDER BY term
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    )
    rows = cur.fetchall()

    item_counts = {}
    if _table_exists(conn, "ingredient_items"):
        terms = [r[0] for r in rows]
        if terms:
            placeholders = ",".join(["?"] * len(terms))
            cur.execute(
                f"SELECT ingredient_term, COUNT(*) FROM ingredient_items WHERE ingredient_term IN ({placeholders}) GROUP BY ingredient_term",
                terms,
            )
            item_counts = {r[0]: r[1] for r in cur.fetchall()}

    ingredients = [
        {"term": r[0], "origin": r[1], "ingredient_category": r[2], "item_count": int(item_counts.get(r[0], 0))}
        for r in rows
    ]
    total_pages = max(1, (total + per_page - 1) // per_page)
    conn.close()
    return jsonify({"ingredients": ingredients, "total": total, "total_pages": total_pages, "page": page})


@app.route("/api/compiled/items")
def api_compiled_items():
    page = int(request.args.get("page", 1))
    search = (request.args.get("search") or "").strip()
    per_page = 50
    offset = (page - 1) * per_page

    conn = get_db("final")
    cur = conn.cursor()
    # Prefer cluster-mirror compiled items when present; fallback to legacy ingredient_items.
    if _table_exists(conn, "compiled_cluster_items"):
        where_clauses = []
        params = []
        if search:
            where_clauses.append("(cluster_id LIKE ? OR derived_term LIKE ? OR derived_variation LIKE ? OR derived_physical_form LIKE ? OR derived_refinement LIKE ? OR refinement_flag LIKE ?)")
            s = f"%{search}%"
            params.extend([s, s, s, s, s, s])
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cur.execute(f"SELECT COUNT(*) FROM compiled_cluster_items {where_sql}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT cluster_id, merged_item_form_id, derived_term, derived_variation, derived_physical_form, item_status,
                   CASE WHEN raw_item_json IS NOT NULL AND raw_item_json != '{{}}' THEN 1 ELSE 0 END as has_raw_specs,
                   CASE WHEN item_json IS NOT NULL AND item_json != '{{}}' THEN 1 ELSE 0 END as has_compiled,
                   derived_refinement, refinement_flag
            FROM compiled_cluster_items
            {where_sql}
            ORDER BY cluster_id, merged_item_form_id
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        )
        items = [
            {
                "cluster_id": r[0],
                "merged_item_form_id": r[1],
                "derived_term": r[2],
                "derived_variation": r[3],
                "derived_physical_form": r[4],
                "item_status": r[5],
                "has_raw_specs": bool(r[6]),
                "has_compiled": bool(r[7]),
                "derived_refinement": r[8],
                "refinement_flag": r[9],
            }
            for r in cur.fetchall()
        ]
        total_pages = max(1, (total + per_page - 1) // per_page)
        conn.close()
        return jsonify({"items": items, "total": total, "total_pages": total_pages, "page": page})

    if not _table_exists(conn, "ingredient_items"):
        conn.close()
        return jsonify({"items": [], "total": 0, "total_pages": 1, "page": page})

    where_clauses = []
    params = []
    if search:
        where_clauses.append("(ingredient_term LIKE ? OR item_name LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s])
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cur.execute(f"SELECT COUNT(*) FROM ingredient_items {where_sql}", params)
    total = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT id, ingredient_term, item_name, variation, physical_form, status,
               CASE WHEN item_json IS NOT NULL AND item_json != '{{}}' THEN 1 ELSE 0 END as has_specs
        FROM ingredient_items
        {where_sql}
        ORDER BY ingredient_term, item_name
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    )
    items = [
        {
            "id": r[0],
            "ingredient_term": r[1],
            "item_name": r[2],
            "variation": r[3],
            "physical_form": r[4],
            "status": r[5],
            "has_specs": bool(r[6]),
        }
        for r in cur.fetchall()
    ]
    total_pages = max(1, (total + per_page - 1) // per_page)
    conn.close()
    return jsonify({"items": items, "total": total, "total_pages": total_pages, "page": page})


@app.route("/api/compiled/refined")
def api_compiled_refined():
    page = int(request.args.get("page", 1))
    search = (request.args.get("search") or "").strip()
    per_page = 50
    offset = (page - 1) * per_page

    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_cluster_items"):
        conn.close()
        return jsonify({"items": [], "total": 0, "total_pages": 1, "page": page})

    where_clauses = []
    params = []
    if search:
        where_clauses.append("(derived_term LIKE ? OR derived_plant_part LIKE ? OR derived_variation LIKE ? OR derived_refinement LIKE ? OR refinement_flag LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s, s, s])
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cur.execute(f"SELECT COUNT(*) FROM compiled_cluster_items {where_sql}", params)
    total = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT id, cluster_id, derived_term, derived_plant_part, derived_variation, 
               derived_refinement, derived_physical_form, refinement_flag
        FROM compiled_cluster_items
        {where_sql}
        ORDER BY derived_term, derived_plant_part, derived_variation
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    )
    items = [
        {
            "id": r[0],
            "cluster_id": r[1],
            "derived_term": r[2],
            "plant_part": r[3],
            "variation": r[4],
            "refinement": r[5],
            "form": r[6],
            "refinement_flag": r[7],
        }
        for r in cur.fetchall()
    ]
    total_pages = max(1, (total + per_page - 1) // per_page)
    conn.close()
    return jsonify({"items": items, "total": total, "total_pages": total_pages, "page": page})


@app.route("/api/refined/definitions")
def api_refined_definitions():
    """Get refined ingredient definitions - grouped by derived_term with source cluster info."""
    page = int(request.args.get("page", 1))
    search = (request.args.get("search") or "").strip()
    per_page = 50
    offset = (page - 1) * per_page

    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_cluster_items"):
        conn.close()
        return jsonify({"definitions": [], "total": 0, "total_pages": 1, "page": page})

    where_clauses = []
    params = []
    if search:
        where_clauses.append("derived_term LIKE ?")
        params.append(f"%{search}%")
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Count unique derived_terms
    cur.execute(f"SELECT COUNT(DISTINCT derived_term) FROM compiled_cluster_items {where_sql}", params)
    total = cur.fetchone()[0]

    # Get grouped definitions - use safe subquery that handles missing compiled_clusters table
    has_compiled_clusters = _table_exists(conn, "compiled_clusters")
    if has_compiled_clusters:
        origin_sql = "(SELECT origin FROM compiled_clusters WHERE cluster_id = (SELECT cluster_id FROM compiled_cluster_items WHERE derived_term = i.derived_term LIMIT 1))"
        category_sql = "(SELECT ingredient_category FROM compiled_clusters WHERE cluster_id = (SELECT cluster_id FROM compiled_cluster_items WHERE derived_term = i.derived_term LIMIT 1))"
    else:
        origin_sql = "NULL"
        category_sql = "NULL"
    
    cur.execute(
        f"""
        SELECT 
            derived_term,
            COUNT(*) as item_count,
            COUNT(DISTINCT cluster_id) as cluster_count,
            MAX(CASE WHEN sap_naoh IS NOT NULL THEN 1 ELSE 0 END) as has_sap_data,
            {origin_sql} as origin,
            {category_sql} as category
        FROM compiled_cluster_items i
        {where_sql}
        GROUP BY derived_term
        ORDER BY derived_term
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    )
    definitions = [
        {
            "derived_term": r[0],
            "item_count": r[1],
            "cluster_count": r[2],
            "has_sap_data": bool(r[3]),
            "origin": r[4] or "-",
            "category": r[5] or "-",
        }
        for r in cur.fetchall()
    ]
    total_pages = max(1, (total + per_page - 1) // per_page)
    conn.close()
    return jsonify({"definitions": definitions, "total": total, "total_pages": total_pages, "page": page})


@app.route("/api/refined/definition/<path:term>")
def api_refined_definition_detail(term: str):
    """Get detailed info for a single refined definition with items housed under term."""
    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_cluster_items"):
        conn.close()
        return jsonify({"error": "No data available"})

    # Get aggregate info for this derived_term
    cur.execute(
        """
        SELECT 
            derived_term,
            COUNT(*) as item_count,
            COUNT(DISTINCT cluster_id) as cluster_count,
            MAX(sap_naoh) as sap_naoh,
            MAX(sap_koh) as sap_koh,
            MAX(iodine_value) as iodine_value,
            MAX(ins_value) as ins_value
        FROM compiled_cluster_items
        WHERE derived_term = ?
        GROUP BY derived_term
        """,
        (term,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Term not found"})

    # Get all items under this derived_term - these are "housed under the refined term"
    cur.execute(
        """
        SELECT id, cluster_id, derived_plant_part, derived_variation, derived_refinement, derived_physical_form
        FROM compiled_cluster_items
        WHERE derived_term = ?
        ORDER BY derived_plant_part, derived_variation
        LIMIT 100
        """,
        (term,),
    )
    items = [
        {
            "id": r[0],
            "cluster_id": r[1],
            "plant_part": r[2] or "-",
            "variation": r[3] or "-",
            "refinement": r[4] or "-",
            "form": r[5] or "-",
        }
        for r in cur.fetchall()
    ]

    # Get origin/category from compiled_clusters (with fallback if table missing)
    source_clusters = []
    origin = "-"
    category = "-"
    if _table_exists(conn, "compiled_clusters"):
        cur.execute(
            """
            SELECT DISTINCT c.cluster_id, c.origin, c.ingredient_category, c.common_name, c.term_status,
                   (SELECT COUNT(*) FROM compiled_cluster_items WHERE cluster_id = c.cluster_id) as item_count
            FROM compiled_clusters c
            WHERE c.cluster_id IN (
                SELECT DISTINCT cluster_id FROM compiled_cluster_items WHERE derived_term = ?
            )
            """,
            (term,),
        )
        source_clusters = [
            {
                "cluster_id": r[0],
                "origin": r[1] or "-",
                "category": r[2] or "-",
                "common_name": r[3] or "-",
                "term_status": r[4] or "-",
                "item_count": r[5] or 0,
            }
            for r in cur.fetchall()
        ]
        if source_clusters:
            origin = source_clusters[0]["origin"]
            category = source_clusters[0]["category"]

    sap_data = None
    if row[3]:  # sap_naoh exists
        sap_data = {
            "sap_naoh": row[3],
            "sap_koh": row[4],
            "iodine_value": row[5],
            "ins_value": row[6],
        }

    conn.close()
    return jsonify({
        "derived_term": row[0],
        "item_count": row[1],
        "cluster_count": row[2],
        "origin": origin,
        "category": category,
        "sap_data": sap_data,
        "items": items,
        "source_clusters": source_clusters,
    })


@app.route("/api/compiled/clusters")
def api_compiled_clusters():
    page = int(request.args.get("page", 1))
    search = (request.args.get("search") or "").strip()
    filter_type = (request.args.get("filter") or "all").strip().lower()
    sort_field = (request.args.get("sort") or "rank").strip().lower()
    sort_order = (request.args.get("order") or "asc").strip().lower()
    per_page = 50
    offset = (page - 1) * per_page

    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_clusters"):
        conn.close()
        return jsonify({"clusters": [], "total": 0, "total_pages": 1, "page": page})

    where_clauses = []
    params = []
    if filter_type == "pending":
        where_clauses.append("c.term_status = 'pending'")
    elif filter_type == "done":
        where_clauses.append("c.term_status = 'done'")
    if search:
        where_clauses.append("(c.cluster_id LIKE ? OR c.compiled_term LIKE ? OR c.raw_canonical_term LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s])
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cur.execute(f"SELECT COUNT(*) FROM compiled_clusters c {where_sql}", params)
    total = cur.fetchone()[0]

    # Build dynamic ORDER BY based on sort parameters
    order_dir = "DESC" if sort_order == "desc" else "ASC"
    if sort_field == "name":
        order_sql = f"COALESCE(c.common_name, c.compiled_term, c.raw_canonical_term) {order_dir}, c.cluster_id"
    elif sort_field == "priority":
        order_sql = f"c.priority {order_dir}, c.cluster_id"
    else:  # rank (default)
        null_order = "999999" if sort_order == "asc" else "0"
        order_sql = f"COALESCE(c.compilation_rank, {null_order}) {order_dir}, c.priority DESC, c.cluster_id"

    cur.execute(
        f"""
        SELECT c.cluster_id, c.raw_canonical_term, c.compiled_term, c.term_status,
               (SELECT COUNT(*) FROM compiled_cluster_items i WHERE i.cluster_id = c.cluster_id) as total_items,
               (SELECT COUNT(*) FROM compiled_cluster_items i WHERE i.cluster_id = c.cluster_id AND i.item_status = 'done') as items_done,
               c.common_name,
               c.priority,
               c.compilation_rank
        FROM compiled_clusters c
        {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    )
    clusters = [
        {
            "cluster_id": r[0],
            "raw_canonical_term": r[1],
            "compiled_term": r[2],
            "term_status": r[3],
            "total_items": int(r[4] or 0),
            "items_done": int(r[5] or 0),
            "common_name": r[6] or None,
            "priority": int(r[7] or 0),
            "rank": int(r[8]) if r[8] is not None else None,
        }
        for r in cur.fetchall()
    ]
    total_pages = max(1, (total + per_page - 1) // per_page)
    conn.close()
    return jsonify({"clusters": clusters, "total": total, "total_pages": total_pages, "page": page})


@app.route("/api/compiled/cluster/<path:cluster_id>")
def api_compiled_cluster_detail(cluster_id: str):
    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_clusters"):
        conn.close()
        return jsonify({"error": "Compiled cluster tables not found"})

    cur.execute(
        """
        SELECT cluster_id, raw_canonical_term, compiled_term, term_status, origin, ingredient_category,
               botanical_name, inci_name, cas_number, refinement_level, derived_from, 
               common_name, confidence_score, data_quality_notes, priority
        FROM compiled_clusters WHERE cluster_id = ?
        """,
        (cluster_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Compiled cluster not found"})

    common_name = row[11]
    confidence_score = row[12]
    data_quality_notes = row[13]
    priority = row[14]

    cur.execute(
        """
        SELECT merged_item_form_id, derived_term, derived_variation, derived_physical_form, item_status,
               raw_item_json, item_json
        FROM compiled_cluster_items
        WHERE cluster_id = ?
        ORDER BY merged_item_form_id
        """,
        (cluster_id,),
    )
    items = []
    done = 0
    for r in cur.fetchall():
        raw = parse_json(r[5]) if r[5] else {}
        raw_specs = (raw or {}).get("merged_specs") if isinstance((raw or {}).get("merged_specs"), dict) else {}
        has_raw_specs = bool(raw_specs)
        has_compiled = bool(r[6] and r[6] != "{}")
        items.append(
            {
                "merged_item_form_id": r[0],
                "derived_term": r[1],
                "derived_variation": r[2],
                "derived_physical_form": r[3],
                "item_status": r[4],
                "has_raw_specs": has_raw_specs,
                "has_compiled": has_compiled,
            }
        )
        if (r[4] or "").strip().lower() == "done":
            done += 1

    conn.close()
    return jsonify(
        {
            "cluster_id": row[0],
            "raw_canonical_term": row[1],
            "compiled_term": row[2],
            "common_name": common_name,
            "term_status": row[3],
            "origin": row[4],
            "ingredient_category": row[5],
            "botanical_name": row[6],
            "inci_name": row[7],
            "cas_number": row[8],
            "refinement_level": row[9],
            "derived_from": row[10],
            "priority": priority,
            "confidence_score": confidence_score,
            "data_quality_notes": data_quality_notes,
            "total_items": len(items),
            "items_done": done,
            "items": items,
        }
    )


@app.route("/api/compiled/ingredient/<path:term>")
def api_compiled_ingredient_detail(term):
    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "ingredients"):
        conn.close()
        return jsonify({"error": "Compiled tables not found"})

    cur.execute(
        """
        SELECT term, origin, ingredient_category, refinement_level, inci_name, cas_number, payload_json
        FROM ingredients WHERE term = ?
        """,
        (term,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Compiled ingredient not found"})

    payload = parse_json(row[6]) if row[6] else None
    items = []
    if _table_exists(conn, "ingredient_items"):
        cur.execute(
            """
            SELECT id, ingredient_term, item_name, variation, physical_form, status
            FROM ingredient_items
            WHERE ingredient_term = ?
            ORDER BY item_name
            """,
            (term,),
        )
        items = [
            {"id": r[0], "ingredient_term": r[1], "item_name": r[2], "variation": r[3], "physical_form": r[4], "status": r[5]}
            for r in cur.fetchall()
        ]

    conn.close()
    return jsonify(
        {
            "term": row[0],
            "origin": row[1],
            "ingredient_category": row[2],
            "refinement_level": row[3],
            "inci_name": row[4],
            "cas_number": row[5],
            "payload_json": payload,
            "items": items,
        }
    )


@app.route("/api/compiled/item/<int:item_id>")
def api_compiled_item_detail(item_id: int):
    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "ingredient_items"):
        conn.close()
        return jsonify({"error": "Compiled tables not found"})
    cur.execute(
        """
        SELECT id, ingredient_term, item_name, variation, physical_form, status, item_json
        FROM ingredient_items WHERE id = ?
        """,
        (item_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Compiled item not found"})
    return jsonify(
        {
            "id": row[0],
            "ingredient_term": row[1],
            "item_name": row[2],
            "variation": row[3],
            "physical_form": row[4],
            "status": row[5],
            "item_json": parse_json(row[6]),
        }
    )


@app.route("/api/compiled/cluster-item/<path:cluster_id>/<int:mif_id>")
def api_compiled_cluster_item_detail(cluster_id: str, mif_id: int):
    """Get detailed compiled cluster item with its raw and compiled JSON data."""
    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_cluster_items"):
        conn.close()
        return jsonify({"error": "Compiled cluster items table not found"})
    cur.execute(
        """
        SELECT cci.cluster_id, cci.merged_item_form_id, cci.derived_term, cci.derived_variation, 
               cci.derived_physical_form, cci.item_status, cci.raw_item_json, cci.item_json,
               cc.compiled_term, cci.refinement_flags,
               cci.sap_naoh, cci.sap_koh, cci.iodine_value, cci.ins_value,
               cci.fatty_acids_json, cci.soap_properties_json, cci.protected_flag,
               cci.use_case_tags, cci.enrichment_source, cci.enrichment_date
        FROM compiled_cluster_items cci
        LEFT JOIN compiled_clusters cc ON cc.cluster_id = cci.cluster_id
        WHERE cci.cluster_id = ? AND cci.merged_item_form_id = ?
        """,
        (cluster_id, mif_id),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Compiled cluster item not found"})
    
    # Also get source data from merged_item_forms
    cur.execute(
        """
        SELECT cas_numbers_json, merged_specs_json, sources_json, has_cosing, has_tgsc, has_seed
        FROM merged_item_forms WHERE id = ?
        """,
        (mif_id,),
    )
    mif_row = cur.fetchone()
    conn.close()
    
    mif_data = {}
    if mif_row:
        mif_data = {
            "cas_numbers": parse_json(mif_row[0]) if mif_row[0] else [],
            "merged_specs": parse_json(mif_row[1]) if mif_row[1] else {},
            "sources": parse_json(mif_row[2]) if mif_row[2] else {},
            "has_cosing": bool(mif_row[3]),
            "has_tgsc": bool(mif_row[4]),
            "has_seed": bool(mif_row[5]),
        }
    
    return jsonify(
        {
            "cluster_id": row[0],
            "merged_item_form_id": row[1],
            "derived_term": row[2],
            "derived_variation": row[3],
            "derived_physical_form": row[4],
            "item_status": row[5],
            "raw_item_json": parse_json(row[6]) if row[6] else {},
            "item_json": parse_json(row[7]) if row[7] else {},
            "compiled_term": row[8],
            "refinement_flags": row[9].split(",") if row[9] else [],
            "source_data": mif_data,
            "master_category": (parse_json(row[7]) or {}).get("master_category", ""),
            "sap_naoh": row[10],
            "sap_koh": row[11],
            "iodine_value": row[12],
            "ins_value": row[13],
            "fatty_acids": parse_json(row[14]) if row[14] else None,
            "soap_properties": parse_json(row[15]) if row[15] else None,
            "protected_flag": bool(row[16]) if row[16] else False,
            "use_case_tags": parse_json(row[17]) if row[17] else [],
            "enrichment_source": row[18],
            "enrichment_date": row[19],
        }
    )

@app.route("/api/compiled/cluster-item-by-id/<int:item_id>")
def api_compiled_cluster_item_by_id(item_id: int):
    """Get detailed compiled cluster item by its primary ID."""
    conn = get_db("final")
    cur = conn.cursor()
    if not _table_exists(conn, "compiled_cluster_items"):
        conn.close()
        return jsonify({"error": "Compiled cluster items table not found"})
    cur.execute(
        """
        SELECT cci.cluster_id, cci.merged_item_form_id, cci.derived_term, cci.derived_variation, 
               cci.derived_physical_form, cci.item_status, cci.raw_item_json, cci.item_json,
               cc.compiled_term, cci.refinement_flags,
               cci.sap_naoh, cci.sap_koh, cci.iodine_value, cci.ins_value,
               cci.fatty_acids_json, cci.soap_properties_json, cci.protected_flag,
               cci.use_case_tags, cci.enrichment_source, cci.enrichment_date
        FROM compiled_cluster_items cci
        LEFT JOIN compiled_clusters cc ON cc.cluster_id = cci.cluster_id
        WHERE cci.id = ?
        """,
        (item_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Compiled cluster item not found"})
    
    mif_id = row[1]
    cur.execute(
        """
        SELECT cas_numbers_json, merged_specs_json, sources_json, has_cosing, has_tgsc, has_seed
        FROM merged_item_forms WHERE id = ?
        """,
        (mif_id,),
    )
    mif_row = cur.fetchone()
    conn.close()
    
    mif_data = {}
    if mif_row:
        mif_data = {
            "cas_numbers": parse_json(mif_row[0]) if mif_row[0] else [],
            "merged_specs": parse_json(mif_row[1]) if mif_row[1] else {},
            "sources": parse_json(mif_row[2]) if mif_row[2] else {},
            "has_cosing": bool(mif_row[3]),
            "has_tgsc": bool(mif_row[4]),
            "has_seed": bool(mif_row[5]),
        }
    
    return jsonify(
        {
            "id": item_id,
            "cluster_id": row[0],
            "merged_item_form_id": row[1],
            "derived_term": row[2],
            "derived_variation": row[3],
            "derived_physical_form": row[4],
            "item_status": row[5],
            "raw_item_json": parse_json(row[6]) if row[6] else {},
            "item_json": parse_json(row[7]) if row[7] else {},
            "compiled_term": row[8],
            "refinement_flags": row[9].split(",") if row[9] else [],
            "source_data": mif_data,
            "master_category": (parse_json(row[7]) or {}).get("master_category", ""),
            "sap_naoh": row[10],
            "sap_koh": row[11],
            "iodine_value": row[12],
            "ins_value": row[13],
            "fatty_acids": parse_json(row[14]) if row[14] else None,
            "soap_properties": parse_json(row[15]) if row[15] else None,
            "protected_flag": bool(row[16]) if row[16] else False,
            "use_case_tags": parse_json(row[17]) if row[17] else [],
            "enrichment_source": row[18],
            "enrichment_date": row[19],
        }
    )


@app.route('/api/clusters')
def api_clusters():
    """Show raw cluster data from clusters - no overlays, no aggregation."""
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
        where_clauses.append("(sd.canonical_term LIKE ? OR sd.cluster_id LIKE ?)")
        params.extend([search_param, search_param])
    
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
        having_clauses.append("total_items > 1")
    elif cluster_size == 'single':
        having_clauses.append("total_items = 1")
    
    if filter_type == 'cosing':
        having_clauses.append("cosing_only > 0")
    elif filter_type == 'tgsc':
        having_clauses.append("tgsc_only > 0")
    elif filter_type == 'both':
        having_clauses.append("both_sources > 0")
    
    having_sql = "HAVING " + " AND ".join(having_clauses) if having_clauses else ""
    
    # Query raw cluster data from clusters with item counts by source type
    # Items are counted from merged_item_forms: cosing_only, tgsc_only, or both (merged duplicates)
    cur.execute(f"""
        SELECT 
            sd.cluster_id,
            sd.canonical_term,
            (SELECT COUNT(DISTINCT mif.id) FROM merged_item_forms mif 
             JOIN source_items si ON si.merged_item_id = mif.id 
             WHERE si.definition_cluster_id = sd.cluster_id) as total_items,
            (SELECT COUNT(DISTINCT mif.id) FROM merged_item_forms mif 
             JOIN source_items si ON si.merged_item_id = mif.id 
             WHERE si.definition_cluster_id = sd.cluster_id AND mif.has_cosing = 1 AND mif.has_tgsc = 0) as cosing_only,
            (SELECT COUNT(DISTINCT mif.id) FROM merged_item_forms mif 
             JOIN source_items si ON si.merged_item_id = mif.id 
             WHERE si.definition_cluster_id = sd.cluster_id AND mif.has_cosing = 0 AND mif.has_tgsc = 1) as tgsc_only,
            (SELECT COUNT(DISTINCT mif.id) FROM merged_item_forms mif 
             JOIN source_items si ON si.merged_item_id = mif.id 
             WHERE si.definition_cluster_id = sd.cluster_id AND mif.has_cosing = 1 AND mif.has_tgsc = 1) as both_sources
        FROM clusters sd
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
            'total_items': row[2] or 0,
            'cosing_only': row[3] or 0,
            'tgsc_only': row[4] or 0,
            'both_sources': row[5] or 0,
        })
    
    # Get total count
    cur.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT sd.cluster_id,
                (SELECT COUNT(*) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id) as item_count,
                (SELECT COUNT(*) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.source = 'cosing') as cosing_count,
                (SELECT COUNT(*) FROM source_items si WHERE si.definition_cluster_id = sd.cluster_id AND si.source = 'tgsc') as tgsc_count
            FROM clusters sd
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
    
    # Get cluster info from clusters
    cur.execute("""
        SELECT reason, canonical_term, botanical_key, parent_cluster_id 
        FROM clusters WHERE cluster_id = ?
    """, (cluster_id,))
    def_row = cur.fetchone()
    reason = def_row[0] if def_row else None
    canonical_term = def_row[1] if def_row else None
    botanical_key = def_row[2] if def_row else None
    parent_cluster_id = def_row[3] if def_row else None
    
    # Get child derivatives (clusters that have this cluster as parent)
    # Also include siblings if this cluster itself has a parent
    cur.execute("""
        SELECT cluster_id, canonical_term 
        FROM clusters 
        WHERE parent_cluster_id = ?
           OR (? IS NOT NULL AND parent_cluster_id = ?)
        ORDER BY canonical_term
    """, (cluster_id, parent_cluster_id, parent_cluster_id))
    child_derivatives = [{'cluster_id': r[0], 'canonical_term': r[1]} for r in cur.fetchall() if r[0] != cluster_id]
    
    conn.close()
    return jsonify({
        'cluster_id': cluster_id,
        'reason': reason,
        'derived_term': derived_term,
        'canonical_term': canonical_term,
        'botanical_key': botanical_key,
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
               created_at, compiled_specs_json, app_seed_specs_json, merged_descriptors_json
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
            
            # Get canonical_term and botanical_key from clusters
            cur.execute(f"""
                SELECT canonical_term, botanical_key 
                FROM clusters 
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
        'merged_descriptors': parse_json(row[17]) if len(row) > 17 else {},
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
               is_composite, raw_name, inci_name, cas_number,
               derived_term, derived_variation, derived_physical_form, derived_part, derived_part_reason,
               origin, ingredient_category, refinement_level, status, needs_review_reason,
               definition_display_name, item_display_name,
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
    
    key = row[0]
    
    # Get CAS numbers from relational table
    cur2 = get_db('final').cursor()
    cur2.execute("SELECT cas_number FROM item_cas_numbers WHERE source_item_key = ?", (key,))
    cas_numbers = [r[0] for r in cur2.fetchall()]
    
    # Get function tags from relational table
    cur2.execute("SELECT function_tag FROM item_functions WHERE source_item_key = ?", (key,))
    function_tags = [r[0] for r in cur2.fetchall()]
    
    return jsonify({
        'key': key,
        'source': row[1],
        'source_row_id': row[2],
        'source_row_number': row[3],
        'source_ref': row[4],
        'content_hash': row[5],
        'is_composite': bool(row[6]),
        'raw_name': row[7],
        'inci_name': row[8],
        'cas_number': row[9],
        'cas_numbers': cas_numbers,
        'derived_term': row[10],
        'derived_variation': row[11],
        'derived_physical_form': row[12],
        'derived_part': row[13],
        'derived_part_reason': row[14],
        'origin': row[15],
        'ingredient_category': row[16],
        'refinement_level': row[17],
        'status': row[18],
        'needs_review_reason': row[19],
        'definition_display_name': row[20],
        'item_display_name': row[21],
        'function_tags': function_tags,
        'function_tag_entries': parse_json(row[22]) or [],
        'master_categories': parse_json(row[23]) or [],
        'variation_bypass': bool(row[24]),
        'variation_bypass_reason': row[25],
        'definition_cluster_id': row[26],
        'definition_cluster_confidence': row[27],
        'definition_cluster_reason': row[28],
        'specs': parse_json(row[29]),
        'specs_sources': parse_json(row[30]),
        'specs_notes': parse_json(row[31]),
        'merged_item_id': row[32],
        'ingested_at': row[33]
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
    dataset = (request.args.get("dataset") or "raw").strip().lower()
    
    conn = get_db('final')
    cur = conn.cursor()

    if dataset == "compiled":
        if view == "terms":
            if not _table_exists(conn, "ingredients"):
                conn.close()
                return Response("No compiled tables.", status=400, mimetype="text/plain; charset=utf-8")
            where = ""
            params = []
            if search:
                where = "WHERE term LIKE ?"
                params = [f"%{search}%"]
            cur.execute(f"SELECT term, origin, ingredient_category, payload_json FROM ingredients {where} ORDER BY term", params)
            rows = cur.fetchall()
            conn.close()
            if format == "json":
                data = [
                    {"term": r[0], "origin": r[1], "ingredient_category": r[2], "payload": parse_json(r[3])}
                    for r in rows
                ]
                return Response(
                    json.dumps(data, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment;filename=compiled_ingredients.json"},
                )
            output = io.StringIO()
            w = csv.writer(output)
            w.writerow(["term", "origin", "ingredient_category"])
            for r in rows:
                w.writerow([r[0], r[1], r[2]])
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment;filename=compiled_ingredients.csv"},
            )

        # compiled items export
        if not _table_exists(conn, "ingredient_items"):
            conn.close()
            return Response("No compiled tables.", status=400, mimetype="text/plain; charset=utf-8")
        where = ""
        params = []
        if search:
            where = "WHERE ingredient_term LIKE ? OR item_name LIKE ?"
            s = f"%{search}%"
            params = [s, s]
        cur.execute(
            f"SELECT id, ingredient_term, item_name, variation, physical_form, status, item_json FROM ingredient_items {where} ORDER BY ingredient_term, item_name",
            params,
        )
        rows = cur.fetchall()
        conn.close()
        if format == "json":
            data = [
                {
                    "id": r[0],
                    "ingredient_term": r[1],
                    "item_name": r[2],
                    "variation": r[3],
                    "physical_form": r[4],
                    "status": r[5],
                    "item_json": parse_json(r[6]),
                }
                for r in rows
            ]
            return Response(
                json.dumps(data, indent=2),
                mimetype="application/json",
                headers={"Content-Disposition": "attachment;filename=compiled_items.json"},
            )
        output = io.StringIO()
        w = csv.writer(output)
        w.writerow(["id", "ingredient_term", "item_name", "variation", "physical_form", "status"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5]])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=compiled_items.csv"},
        )
    
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
