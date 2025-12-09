(function(window){
  'use strict';

  function createBakingSkin(){
    let hostEl, infoEl;
    let state = {
      baseIngredient: { invId: '', giId: '', name: 'Flour' },
      baseGrams: '',
      moistureLossPct: '',
      targetFinalYieldG: '',
      percentRows: [ { name: 'Water', giId: '', pct: '' }, { name: 'Salt', giId: '', pct: '' }, { name: 'Yeast', giId: '', pct: '' } ],
      mode: 'percent' // 'percent' or 'grams'
    };

    function h(html){ const div=document.createElement('div'); div.innerHTML=html.trim(); return div.firstChild; }

    function render(){
      if (!hostEl) return;
      hostEl.innerHTML = '';
      const controls = h(`
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Base Ingredient</label>
            <div class="position-relative">
              <input type="text" class="form-control" id="bk_base_name" placeholder="Search (default Flour)" value="${state.baseIngredient.name||''}">
              <input type="hidden" id="bk_base_inv">
              <input type="hidden" id="bk_base_gi">
              <div class="list-group position-absolute w-100 d-none" data-role="suggestions"></div>
            </div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Base (g)</label>
            <input type="number" class="form-control" id="bk_base_g" step="0.01" min="0" value="${state.baseGrams||''}">
          </div>
          <div class="col-md-3">
            <label class="form-label">Moisture loss %</label>
            <input type="number" class="form-control" id="bk_moisture" step="0.1" min="0" max="100" value="${state.moistureLossPct||''}">
          </div>
          <div class="col-md-3">
            <label class="form-label">Target final yield (g)</label>
            <input type="number" class="form-control" id="bk_target_final" step="0.01" min="0" value="${state.targetFinalYieldG||''}">
          </div>
          <div class="col-md-3">
            <label class="form-label">Input mode</label>
            <select class="form-select" id="bk_mode">
              <option value="percent" ${state.mode==='percent'?'selected':''}>Percentages</option>
              <option value="grams" ${state.mode==='grams'?'selected':''}>Grams</option>
            </select>
          </div>
        </div>
        <div class="mt-3">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0">Ingredients</h6>
            <button class="btn btn-sm btn-outline-primary" id="bk_add_row">Add Row</button>
          </div>
          <div id="bk_rows"></div>
          <div class="mt-3 d-flex gap-2">
            <button class="btn btn-primary" id="bk_calculate">Calculate</button>
            <button class="btn btn-outline-secondary" id="bk_push_lines">Show as manual lines</button>
          </div>
        </div>
      `);
      hostEl.appendChild(controls);

      // attach typeahead to base
      (function(){
        const input = hostEl.querySelector('#bk_base_name');
        const giHidden = hostEl.querySelector('#bk_base_gi');
        const list = hostEl.querySelector('[data-role="suggestions"]');
        if (typeof window.attachMergedInventoryGlobalTypeahead === 'function'){
          window.attachMergedInventoryGlobalTypeahead({
            inputEl: input,
            giHiddenEl: giHidden,
            listEl: list,
            mode: 'recipe',
            ingredientFirst: true
          });
        }
      })();

      // rows
      renderRows();
      bind();
      renderInfo();
    }

    function renderRows(){
      const wrapper = hostEl.querySelector('#bk_rows');
      wrapper.innerHTML = '';
      state.percentRows.forEach((row, idx) => {
        const el = h(`
          <div class="row g-2 align-items-end mb-2" data-idx="${idx}">
            <div class="col-md-5">
              <label class="form-label">Name</label>
              <input type="text" class="form-control bk_name" value="${row.name||''}">
            </div>
            <div class="col-md-4">
              <label class="form-label">${state.mode==='percent' ? '% of base' : 'Amount (g)'}</label>
              <input type="number" class="form-control bk_val" step="0.01" min="0" value="${row.pct||row.grams||''}">
            </div>
            <div class="col-md-2 d-grid">
              <button type="button" class="btn btn-outline-danger bk_remove">Remove</button>
            </div>
          </div>
        `);
        wrapper.appendChild(el);
      });
    }

    function bind(){
      hostEl.querySelector('#bk_mode')?.addEventListener('change', (e)=>{ state.mode = e.target.value; renderRows(); });
      hostEl.querySelector('#bk_add_row')?.addEventListener('click', ()=>{ state.percentRows.push({ name: '', giId: '', pct: '' }); renderRows(); });
      hostEl.addEventListener('click', function(e){ if (e.target.classList.contains('bk_remove')){ const row=e.target.closest('[data-idx]'); const i=parseInt(row.getAttribute('data-idx'),10); state.percentRows.splice(i,1); renderRows(); } });
      hostEl.querySelector('#bk_calculate')?.addEventListener('click', commitToLines);
      hostEl.querySelector('#bk_push_lines')?.addEventListener('click', commitToLines);
    }

    function sumPercents(){
      return state.percentRows.reduce((s,r)=> s + (parseFloat(r.pct||'0')||0), 0);
    }

    function commitToLines(){
      // derive base and totals
      const baseG = parseFloat(hostEl.querySelector('#bk_base_g')?.value||state.baseGrams||'0') || 0;
      const moisture = parseFloat(hostEl.querySelector('#bk_moisture')?.value||state.moistureLossPct||'0') || 0;
      const targetFinal = parseFloat(hostEl.querySelector('#bk_target_final')?.value||state.targetFinalYieldG||'0') || 0;

      let computedBase = baseG;
      if (!computedBase && targetFinal>0){
        const preDry = targetFinal / (1 - (moisture/100));
        const pctSum = Math.max(0, sumPercents());
        // total = base + base * (pctSum/100)
        // base = total / (1 + pctSum/100)
        computedBase = preDry / (1 + (pctSum/100));
      }
      if (!(computedBase>0)) return;

      // Build ingredient lines
      const out = [];
      // Base line
      out.push({ name: hostEl.querySelector('#bk_base_name')?.value?.trim()||'Flour', grams: computedBase });
      // Other lines
      state.percentRows.forEach(r => {
        const val = parseFloat(hostEl.querySelector(`.row [data-idx] .bk_val`)?.value||r.pct||'0');
      });
      // recompute using state (not query)
      state.percentRows.forEach(r => {
        const v = parseFloat(r.pct||r.grams||'0')||0;
        const g = (state.mode==='percent') ? (computedBase * (v/100)) : v;
        out.push({ name: r.name||'', grams: g });
      });

      // Replace ingredient rows in the canonical form
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

      // Write metadata to info card (and allow persisting via form fields if needed)
      if (infoEl){
        const preDry = out.reduce((s,l)=> s + (l.grams||0), 0);
        const finalG = preDry * (1 - (moisture/100));
        infoEl.innerHTML = `
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label small">Moisture loss %</label><input class="form-control" name="category_data[moisture_loss_pct]" value="${moisture||''}"></div>
            <div class="col-md-3"><label class="form-label small">Derived pre-dry (g)</label><input class="form-control" name="category_data[derived_pre_dry_yield_g]" value="${Math.round(preDry*1000)/1000}"></div>
            <div class="col-md-3"><label class="form-label small">Derived final (g)</label><input class="form-control" name="category_data[derived_final_yield_g]" value="${Math.round(finalG*1000)/1000}"></div>
          </div>`;
      }
    }

    function renderInfo(){
      if (!infoEl) return;
      // initial blank; values fill on calculate
      infoEl.innerHTML = `
        <div class="text-muted small">Calculated values will appear here after you click Calculate.</div>
      `;
    }

    return {
      mount({ hostEl: hEl, infoEl: iEl }){ hostEl = hEl; infoEl = iEl; render(); },
      unmount(){ if (hostEl) hostEl.innerHTML=''; if (infoEl) infoEl.innerHTML=''; },
    };
  }

  if (window.CategorySkins){
    window.CategorySkins.register('baked goods', createBakingSkin);
    window.CategorySkins.register('baking', createBakingSkin);
  }
})(window);
