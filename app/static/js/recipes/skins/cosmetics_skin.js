(function(window){
  'use strict';

  function createCosmeticsSkin(){
    let hostEl, infoEl;
    let state = {
      batchG: '',
      emulsifierPct: '',
      preservativePct: '',
      oilPhasePct: '',
      waterPhasePct: '',
      coolDownPhasePct: '',
      percentRows: [ ]
    };

    function h(html){ const div=document.createElement('div'); div.innerHTML=html.trim(); return div.firstChild; }

    function render(){
      if (!hostEl) return;
      hostEl.innerHTML = '';
      const controls = h(`
        <div class="row g-3">
          <div class="col-md-3"><label class="form-label">Batch size (g)</label><input type="number" class="form-control" id="cx_batch" step="0.01" min="0" value="${state.batchG||''}"></div>
          <div class="col-md-3"><label class="form-label">Emulsifier %</label><input type="number" class="form-control" id="cx_emul" step="0.1" min="0" value="${state.emulsifierPct||''}"></div>
          <div class="col-md-3"><label class="form-label">Preservative %</label><input type="number" class="form-control" id="cx_pres" step="0.1" min="0" value="${state.preservativePct||''}"></div>
          <div class="col-md-3"><label class="form-label">Oil phase %</label><input type="number" class="form-control" id="cx_oil" step="0.1" min="0" value="${state.oilPhasePct||''}"></div>
          <div class="col-md-3"><label class="form-label">Water phase %</label><input type="number" class="form-control" id="cx_water" step="0.1" min="0" value="${state.waterPhasePct||''}"></div>
          <div class="col-md-3"><label class="form-label">Cool-down %</label><input type="number" class="form-control" id="cx_cool" step="0.1" min="0" value="${state.coolDownPhasePct||''}"></div>
        </div>
        <div class="mt-3">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0">Ingredients (optional % list)</h6>
            <button class="btn btn-sm btn-outline-primary" id="cx_add_row">Add Row</button>
          </div>
          <div id="cx_rows"></div>
          <div class="mt-3 d-flex gap-2">
            <button class="btn btn-primary" id="cx_calculate">Calculate</button>
            <button class="btn btn-outline-secondary" id="cx_push_lines">Show as manual lines</button>
          </div>
        </div>
      `);
      hostEl.appendChild(controls);
      renderRows();
      bind();
      renderInfo();
    }

    function renderRows(){
      const wrapper = hostEl.querySelector('#cx_rows');
      wrapper.innerHTML = '';
      state.percentRows.forEach((row, idx) => {
        const el = h(`
          <div class="row g-2 align-items-end mb-2" data-idx="${idx}">
            <div class="col-md-6">
              <label class="form-label">Name</label>
              <input type="text" class="form-control cx_name" value="${row.name||''}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Percent</label>
              <input type="number" class="form-control cx_pct" step="0.01" min="0" value="${row.pct||''}">
            </div>
            <div class="col-md-2 d-grid">
              <button type="button" class="btn btn-outline-danger cx_remove">Remove</button>
            </div>
          </div>
        `);
        wrapper.appendChild(el);
      });
    }

    function bind(){
      hostEl.addEventListener('click', function(e){ if (e.target.classList.contains('cx_remove')){ const row=e.target.closest('[data-idx]'); const i=parseInt(row.getAttribute('data-idx'),10); state.percentRows.splice(i,1); renderRows(); } });
      hostEl.querySelector('#cx_add_row')?.addEventListener('click', ()=>{ state.percentRows.push({ name: '', pct: '' }); renderRows(); });
      hostEl.querySelector('#cx_calculate')?.addEventListener('click', commitToLines);
      hostEl.querySelector('#cx_push_lines')?.addEventListener('click', commitToLines);
    }

    function commitToLines(){
      const batch = parseFloat(hostEl.querySelector('#cx_batch')?.value||state.batchG||'0') || 0;
      if (!(batch>0)) return;
      const out = [];

      // Optional percent rows become grams by batch * pct/100
      state.percentRows.forEach(r => {
        const pct = parseFloat(r.pct||'0')||0;
        if (pct>0){ out.push({ name: r.name||'', grams: batch*(pct/100) }); }
      });

      // Replace canonical ingredient lines
      const container = document.getElementById('ingredients-container');
      container.innerHTML = '';
      out.forEach(line => {
        const entry = window.addIngredient();
        const input = entry.querySelector('input.recipe-ingredient-typeahead');
        const unitSel = entry.querySelector('select[name="units[]"]');
        const amt = entry.querySelector('input[name="amounts[]"]');
        if (input) input.value = line.name || '';
        if (amt) amt.value = String(Math.round(line.grams*1000)/1000);
        if (unitSel) unitSel.value = 'gram';
      });

      // write metadata
      if (infoEl){
        infoEl.innerHTML = `
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label small">Emulsifier %</label><input class="form-control" name="category_data[cosm_emulsifier_pct]" value="${parseFloat(hostEl.querySelector('#cx_emul')?.value||state.emulsifierPct||'')||''}"></div>
            <div class="col-md-3"><label class="form-label small">Preservative %</label><input class="form-control" name="category_data[cosm_preservative_pct]" value="${parseFloat(hostEl.querySelector('#cx_pres')?.value||state.preservativePct||'')||''}"></div>
            <div class="col-md-3"><label class="form-label small">Oil phase %</label><input class="form-control" name="category_data[oil_phase_pct]" value="${parseFloat(hostEl.querySelector('#cx_oil')?.value||state.oilPhasePct||'')||''}"></div>
            <div class="col-md-3"><label class="form-label small">Water phase %</label><input class="form-control" name="category_data[water_phase_pct]" value="${parseFloat(hostEl.querySelector('#cx_water')?.value||state.waterPhasePct||'')||''}"></div>
            <div class="col-md-3"><label class="form-label small">Cool-down %</label><input class="form-control" name="category_data[cool_down_phase_pct]" value="${parseFloat(hostEl.querySelector('#cx_cool')?.value||state.coolDownPhasePct||'')||''}"></div>
          </div>`;
      }
    }

    function renderInfo(){
      if (!infoEl) return;
      infoEl.innerHTML = `<div class="text-muted small">Calculated values and saved parameters appear here.</div>`;
    }

    return {
      mount({ hostEl: hEl, infoEl: iEl }){ hostEl = hEl; infoEl = iEl; render(); },
      unmount(){ if (hostEl) hostEl.innerHTML=''; if (infoEl) infoEl.innerHTML=''; },
    };
  }

  if (window.CategorySkins){
    window.CategorySkins.register('cosmetics', createCosmeticsSkin);
    window.CategorySkins.register('lotions', createCosmeticsSkin);
    window.CategorySkins.register('tallow', createCosmeticsSkin);
  }
})(window);
