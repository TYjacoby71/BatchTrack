(()=>{(function(u){"use strict";function g(){let e,d,a={baseIngredient:{invId:"",giId:"",name:"Flour"},baseGrams:"",moistureLossPct:"",targetFinalYieldG:"",percentRows:[{name:"Water",giId:"",pct:""},{name:"Salt",giId:"",pct:""},{name:"Yeast",giId:"",pct:""}],mode:"percent"};function f(l){let t=document.createElement("div");return t.innerHTML=l.trim(),t.firstChild}function L(){if(!e)return;e.innerHTML="";let l=f(`
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Base Ingredient</label>
            <div class="position-relative">
              <input type="text" class="form-control" id="bk_base_name" placeholder="Search (default Flour)" value="${a.baseIngredient.name||""}">
              <input type="hidden" id="bk_base_inv">
              <input type="hidden" id="bk_base_gi">
              <div class="list-group position-absolute w-100 d-none" data-role="suggestions"></div>
            </div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Base (g)</label>
            <input type="number" class="form-control" id="bk_base_g" step="0.01" min="0" value="${a.baseGrams||""}">
          </div>
          <div class="col-md-3">
            <label class="form-label">Moisture loss %</label>
            <input type="number" class="form-control" id="bk_moisture" step="0.1" min="0" max="100" value="${a.moistureLossPct||""}">
          </div>
          <div class="col-md-3">
            <label class="form-label">Target final yield (g)</label>
            <input type="number" class="form-control" id="bk_target_final" step="0.01" min="0" value="${a.targetFinalYieldG||""}">
          </div>
          <div class="col-md-3">
            <label class="form-label">Input mode</label>
            <select class="form-select" id="bk_mode">
              <option value="percent" ${a.mode==="percent"?"selected":""}>Percentages</option>
              <option value="grams" ${a.mode==="grams"?"selected":""}>Grams</option>
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
      `);e.appendChild(l),(function(){let t=e.querySelector("#bk_base_name"),i=e.querySelector("#bk_base_gi"),s=e.querySelector('[data-role="suggestions"]');typeof u.attachMergedInventoryGlobalTypeahead=="function"&&u.attachMergedInventoryGlobalTypeahead({inputEl:t,giHiddenEl:i,listEl:s,mode:"recipe",ingredientFirst:!0})})(),m(),I(),M()}function m(){let l=e.querySelector("#bk_rows");l.innerHTML="",a.percentRows.forEach((t,i)=>{let s=f(`
          <div class="row g-2 align-items-end mb-2" data-idx="${i}">
            <div class="col-md-5">
              <label class="form-label">Name</label>
              <input type="text" class="form-control bk_name" value="${t.name||""}">
            </div>
            <div class="col-md-4">
              <label class="form-label">${a.mode==="percent"?"% of base":"Amount (g)"}</label>
              <input type="number" class="form-control bk_val" step="0.01" min="0" value="${t.pct||t.grams||""}">
            </div>
            <div class="col-md-2 d-grid">
              <button type="button" class="btn btn-outline-danger bk_remove">Remove</button>
            </div>
          </div>
        `);l.appendChild(s)})}function I(){var l,t,i,s;(l=e.querySelector("#bk_mode"))==null||l.addEventListener("change",o=>{a.mode=o.target.value,m()}),(t=e.querySelector("#bk_add_row"))==null||t.addEventListener("click",()=>{a.percentRows.push({name:"",giId:"",pct:""}),m()}),e.addEventListener("click",function(o){if(o.target.classList.contains("bk_remove")){let v=o.target.closest("[data-idx]"),b=parseInt(v.getAttribute("data-idx"),10);a.percentRows.splice(b,1),m()}}),(i=e.querySelector("#bk_calculate"))==null||i.addEventListener("click",_),(s=e.querySelector("#bk_push_lines"))==null||s.addEventListener("click",_)}function q(){return a.percentRows.reduce((l,t)=>l+(parseFloat(t.pct||"0")||0),0)}function _(){var b,y,k,h,S;let l=parseFloat(((b=e.querySelector("#bk_base_g"))==null?void 0:b.value)||a.baseGrams||"0")||0,t=parseFloat(((y=e.querySelector("#bk_moisture"))==null?void 0:y.value)||a.moistureLossPct||"0")||0,i=parseFloat(((k=e.querySelector("#bk_target_final"))==null?void 0:k.value)||a.targetFinalYieldG||"0")||0,s=l;if(!s&&i>0){let n=i/(1-t/100),r=Math.max(0,q());s=n/(1+r/100)}if(!(s>0))return;let o=[];o.push({name:((S=(h=e.querySelector("#bk_base_name"))==null?void 0:h.value)==null?void 0:S.trim())||"Flour",grams:s}),a.percentRows.forEach(n=>{var c;let r=parseFloat(((c=e.querySelector(".row [data-idx] .bk_val"))==null?void 0:c.value)||n.pct||"0")}),a.percentRows.forEach(n=>{let r=parseFloat(n.pct||n.grams||"0")||0,c=a.mode==="percent"?s*(r/100):r;o.push({name:n.name||"",grams:c})});let v=document.getElementById("ingredients-container");if(v.innerHTML="",o.forEach(n=>{let r=u.addIngredient(),c=r.querySelector("input.recipe-ingredient-typeahead"),p=r.querySelector('select[name="units[]"]'),E=r.querySelector('input[name="amounts[]"]');c&&(c.value=n.name||""),E&&(E.value=String(Math.round(n.grams*1e3)/1e3)),p&&(p.value="gram")}),d){let n=o.reduce((c,p)=>c+(p.grams||0),0),r=n*(1-t/100);d.innerHTML=`
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label small">Moisture loss %</label><input class="form-control" name="category_data[moisture_loss_pct]" value="${t||""}"></div>
            <div class="col-md-3"><label class="form-label small">Derived pre-dry (g)</label><input class="form-control" name="category_data[derived_pre_dry_yield_g]" value="${Math.round(n*1e3)/1e3}"></div>
            <div class="col-md-3"><label class="form-label small">Derived final (g)</label><input class="form-control" name="category_data[derived_final_yield_g]" value="${Math.round(r*1e3)/1e3}"></div>
          </div>`}}function M(){d&&(d.innerHTML=`
        <div class="text-muted small">Calculated values will appear here after you click Calculate.</div>
      `)}return{mount({hostEl:l,infoEl:t}){e=l,d=t,L()},unmount(){e&&(e.innerHTML=""),d&&(d.innerHTML="")}}}u.CategorySkins&&(u.CategorySkins.register("baked goods",g),u.CategorySkins.register("baking",g))})(window);})();
