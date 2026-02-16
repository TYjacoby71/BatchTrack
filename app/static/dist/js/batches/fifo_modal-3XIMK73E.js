(()=>{var v=null;function y(e,t){v=e;let n=new bootstrap.Modal(document.getElementById("fifoInsightModal"));document.getElementById("fifoModalTitle").textContent=`FIFO Details for Inventory ID: ${e}`,document.getElementById("fifoModalContent").innerHTML=`
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading FIFO details...</p>
        </div>
    `,n.show(),g(e,t)}function b(e){let t=new bootstrap.Modal(document.getElementById("fifoInsightModal"));document.getElementById("fifoModalTitle").textContent="Batch Inventory Summary",document.getElementById("fifoModalContent").innerHTML=`
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading batch inventory summary...</p>
        </div>
    `,t.show(),_(e)}async function g(e,t){try{let n=await fetch(`/api/fifo-details/${e}?batch_id=${t}`),s=await n.json();n.ok?$(s):f(s.error||"Failed to load FIFO details")}catch(n){console.error("Error fetching FIFO details:",n),f("Failed to load batch source list")}}async function _(e){try{let t=await fetch(`/batches/api/batch-inventory-summary/${e}`);if(!t.ok){let a=await t.text();throw new Error(`HTTP error! status: ${t.status}, message: ${a}`)}let n=t.headers.get("content-type");if(!n||!n.includes("application/json")){let a=await t.text();throw new Error(`Response is not JSON. Content: ${a}`)}let s=await t.json();w(s)}catch(t){console.error("Error fetching batch summary:",t),f(`Failed to load batch inventory summary: ${t.message}`)}}function $(e){let{inventory_item:t,batch_usage:n}=e,s=`
        <div class="mb-3">
            <h6>${t.name}</h6>
            <p class="text-muted">Current Stock: ${t.quantity} ${t.unit}</p>
        </div>
    `;n&&n.length>0?(s+=`
            <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead>
                        <tr>
                            <th>FIFO Source</th>
                            <th>Amount Used</th>
                            <th>Age</th>
                            <th>Freshness</th>
                            <th>Line Cost</th>
                        </tr>
                    </thead>
                    <tbody>
        `,n.forEach(a=>{let i=a.age_days?`${a.age_days} days`:"1 day",r=a.life_remaining_percent!==null?`<span class="badge ${d(a.life_remaining_percent)}">${a.life_remaining_percent}%</span>`:'<span class="text-muted">Non-perishable</span>',l=(a.quantity_used*(a.unit_cost||0)).toFixed(2);s+=`
                <tr>
                    <td>
                        <a href="/inventory/view/${t.id}#fifo-entry-${a.fifo_id}"
                           target="_blank" class="fifo-ingredient-link">
                            #${a.fifo_id}
                        </a>
                    </td>
                    <td><strong>${a.quantity_used} ${a.unit}</strong></td>
                    <td>${i}</td>
                    <td>${r}</td>
                    <td>$${l}</td>
                </tr>
            `}),s+=`
                    </tbody>
                </table>
            </div>
        `):s+='<div class="alert alert-info">No usage data available for this ingredient in this batch.</div>',document.getElementById("fifoModalContent").innerHTML=s}function w(e){let{batch:t,ingredient_summary:n,freshness_summary:s}=e,a=`
        <div class="mb-3">
            <h6>Batch: ${t.label_code}</h6>
            <p class="text-muted">Recipe: ${t.recipe_name} \u2022 Scale: ${t.scale}</p>
        </div>

        ${F(s)}

        <div class="mb-3">
            <h6>Inventory Summary</h6>
    `;n&&n.length>0?(a+=`
            <table class="table table-sm align-middle" id="batch-inv-summary">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Total Used</th>
                        <th>Weighted Freshness</th>
                    </tr>
                </thead>
                <tbody>
        `,n.forEach(i=>{let r=I(s,i.inventory_item_id),l=Array.isArray(i.fifo_usage)&&i.fifo_usage.length>1,m=l?`<button type="button" class="btn btn-link btn-sm p-0 me-1 align-baseline" data-item-id="${i.inventory_item_id}" aria-label="Toggle lots" onclick="toggleLotsRow(${i.inventory_item_id})">
                        <i id="caret-${i.inventory_item_id}" class="fas fa-chevron-right"></i>
                   </button>`:"";if(a+=`
                <tr id="item-row-${i.inventory_item_id}">
                    <td>${m}<span>${i.name}</span></td>
                    <td><strong>${i.total_used} ${i.unit}</strong></td>
                    <td>${r!==null?`<span class="badge ${d(r)}">${r}%</span>`:"&mdash;"}</td>
                </tr>
            `,l){let c=`
                    <tr id="lots-row-${i.inventory_item_id}" class="d-none">
                        <td colspan="3">
                            <div class="bg-light border rounded p-2">
                                <div class="d-flex text-muted small fw-semibold pb-1">
                                    <div class="flex-grow-1">Lot</div>
                                    <div class="text-end" style="width: 300px;">Used \u2022 Age \u2022 Life \u2022 Unit Cost</div>
                                </div>
                                <table class="table table-sm borderless m-0">
                                    <tbody>
                `;i.fifo_usage.forEach(o=>{let h=o.age_days?`${o.age_days} days`:"1 day",u=o.life_remaining_percent!==null&&o.life_remaining_percent!==void 0?`<span class="badge ${d(o.life_remaining_percent)}">${o.life_remaining_percent}%</span>`:'<span class="text-muted">Non-perishable</span>',p=typeof o.unit_cost=="number"?`$${Number(o.unit_cost).toFixed(2)}`:"&mdash;";c+=`
                        <div class="d-flex align-items-center py-1 border-top">
                            <div class="flex-grow-1">
                                <small class="text-muted">
                                    <a href="/inventory/view/${i.inventory_item_id}#fifo-entry-${o.fifo_id}"
                                       target="_blank" class="fifo-ingredient-link">
                                        #${o.fifo_id}
                                    </a>
                                </small>
                            </div>
                            <div class="text-end" style="width: 300px;">
                                <span class="me-3">${o.quantity_used} ${o.unit}</span>
                                <span class="me-3">${h}</span>
                                ${u}
                                <span class="ms-3">${p}</span>
                            </div>
                        </div>
                    `}),c+=`
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </td>
                    </tr>
                `,a+=c}}),a+=`
                </tbody>
            </table>
        `):a+='<div class="alert alert-info">No ingredient usage data available for this batch.</div>',a+="</div>",document.getElementById("fifoModalContent").innerHTML=a}function x(e){try{let t=document.getElementById(`lots-row-${e}`),n=document.getElementById(`caret-${e}`);if(!t||!n)return;t.classList.contains("d-none")?(t.classList.remove("d-none"),n.classList.remove("fa-chevron-right"),n.classList.add("fa-chevron-down")):(t.classList.add("d-none"),n.classList.remove("fa-chevron-down"),n.classList.add("fa-chevron-right"))}catch{}}function F(e){if(!e||e.overall_freshness_percent===null||e.overall_freshness_percent===void 0)return"";let t=e.overall_freshness_percent;return`
        <div class="alert alert-info mb-3">
            <strong>Overall Freshness:</strong> ${`<span class="badge ${d(t)}">${t}%</span>`}
        </div>
    `}function I(e,t){var n;try{if(!e||!e.items||!Array.isArray(e.items))return null;let s=e.items.find(a=>a.inventory_item_id===t);return s&&(n=s.weighted_freshness_percent)!=null?n:null}catch{return null}}function d(e){return e===null?"bg-secondary":e>=70?"bg-success":e>=30?"bg-warning":"bg-danger"}function f(e){document.getElementById("fifoModalContent").innerHTML=`
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-triangle"></i>
            <strong>Error:</strong> ${e}
        </div>
    `}typeof window!="undefined"&&Object.assign(window,{openFifoModal:y,openBatchInventorySummary:b,toggleLotsRow:x});})();
