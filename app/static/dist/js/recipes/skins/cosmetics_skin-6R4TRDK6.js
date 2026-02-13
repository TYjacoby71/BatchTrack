(()=>{(function(r){"use strict";function u(){let e,s,l={batchG:"",emulsifierPct:"",preservativePct:"",oilPhasePct:"",waterPhasePct:"",coolDownPhasePct:"",percentRows:[]};function p(t){let a=document.createElement("div");return a.innerHTML=t.trim(),a.firstChild}function P(){if(!e)return;e.innerHTML="";let t=p(`
        <div class="row g-3">
          <div class="col-md-3"><label class="form-label">Batch size (g)</label><input type="number" class="form-control" id="cx_batch" step="0.01" min="0" value="${l.batchG||""}"></div>
          <div class="col-md-3"><label class="form-label">Emulsifier %</label><input type="number" class="form-control" id="cx_emul" step="0.1" min="0" value="${l.emulsifierPct||""}"></div>
          <div class="col-md-3"><label class="form-label">Preservative %</label><input type="number" class="form-control" id="cx_pres" step="0.1" min="0" value="${l.preservativePct||""}"></div>
          <div class="col-md-3"><label class="form-label">Oil phase %</label><input type="number" class="form-control" id="cx_oil" step="0.1" min="0" value="${l.oilPhasePct||""}"></div>
          <div class="col-md-3"><label class="form-label">Water phase %</label><input type="number" class="form-control" id="cx_water" step="0.1" min="0" value="${l.waterPhasePct||""}"></div>
          <div class="col-md-3"><label class="form-label">Cool-down %</label><input type="number" class="form-control" id="cx_cool" step="0.1" min="0" value="${l.coolDownPhasePct||""}"></div>
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
      `);e.appendChild(t),v(),w(),S()}function v(){let t=e.querySelector("#cx_rows");t.innerHTML="",l.percentRows.forEach((a,o)=>{let c=p(`
          <div class="row g-2 align-items-end mb-2" data-idx="${o}">
            <div class="col-md-6">
              <label class="form-label">Name</label>
              <input type="text" class="form-control cx_name" value="${a.name||""}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Percent</label>
              <input type="number" class="form-control cx_pct" step="0.01" min="0" value="${a.pct||""}">
            </div>
            <div class="col-md-2 d-grid">
              <button type="button" class="btn btn-outline-danger cx_remove">Remove</button>
            </div>
          </div>
        `);t.appendChild(c)})}function w(){var t,a,o;e.addEventListener("click",function(c){if(c.target.classList.contains("cx_remove")){let d=c.target.closest("[data-idx]"),m=parseInt(d.getAttribute("data-idx"),10);l.percentRows.splice(m,1),v()}}),(t=e.querySelector("#cx_add_row"))==null||t.addEventListener("click",()=>{l.percentRows.push({name:"",pct:""}),v()}),(a=e.querySelector("#cx_calculate"))==null||a.addEventListener("click",b),(o=e.querySelector("#cx_push_lines"))==null||o.addEventListener("click",b)}function b(){var c,d,m,f,_,h;let t=parseFloat(((c=e.querySelector("#cx_batch"))==null?void 0:c.value)||l.batchG||"0")||0;if(!(t>0))return;let a=[];l.percentRows.forEach(i=>{let n=parseFloat(i.pct||"0")||0;n>0&&a.push({name:i.name||"",grams:t*(n/100)})});let o=document.getElementById("ingredients-container");o.innerHTML="",a.forEach(i=>{let n=r.addIngredient(),y=n.querySelector("input.recipe-ingredient-typeahead"),g=n.querySelector('select[name="units[]"]'),x=n.querySelector('input[name="amounts[]"]');y&&(y.value=i.name||""),x&&(x.value=String(Math.round(i.grams*1e3)/1e3)),g&&(g.value="gram")}),s&&(s.innerHTML=`
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label small">Emulsifier %</label><input class="form-control" name="category_data[cosm_emulsifier_pct]" value="${parseFloat(((d=e.querySelector("#cx_emul"))==null?void 0:d.value)||l.emulsifierPct||"")||""}"></div>
            <div class="col-md-3"><label class="form-label small">Preservative %</label><input class="form-control" name="category_data[cosm_preservative_pct]" value="${parseFloat(((m=e.querySelector("#cx_pres"))==null?void 0:m.value)||l.preservativePct||"")||""}"></div>
            <div class="col-md-3"><label class="form-label small">Oil phase %</label><input class="form-control" name="category_data[oil_phase_pct]" value="${parseFloat(((f=e.querySelector("#cx_oil"))==null?void 0:f.value)||l.oilPhasePct||"")||""}"></div>
            <div class="col-md-3"><label class="form-label small">Water phase %</label><input class="form-control" name="category_data[water_phase_pct]" value="${parseFloat(((_=e.querySelector("#cx_water"))==null?void 0:_.value)||l.waterPhasePct||"")||""}"></div>
            <div class="col-md-3"><label class="form-label small">Cool-down %</label><input class="form-control" name="category_data[cool_down_phase_pct]" value="${parseFloat(((h=e.querySelector("#cx_cool"))==null?void 0:h.value)||l.coolDownPhasePct||"")||""}"></div>
          </div>`)}function S(){s&&(s.innerHTML='<div class="text-muted small">Calculated values and saved parameters appear here.</div>')}return{mount({hostEl:t,infoEl:a}){e=t,s=a,P()},unmount(){e&&(e.innerHTML=""),s&&(s.innerHTML="")}}}r.CategorySkins&&(r.CategorySkins.register("cosmetics",u),r.CategorySkins.register("lotions",u),r.CategorySkins.register("tallow",u))})(window);})();
