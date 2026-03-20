(()=>{(function(){function r(){let n=document.getElementById("quickCreateUnitClientModal");if(n)return n;let l=document.createElement("div");l.innerHTML=`
<div class="modal fade" id="quickCreateUnitClientModal" tabindex="-1" aria-labelledby="quickCreateUnitClientModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="quickCreateUnitClientModalLabel">Quick Create Unit</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div class="mb-2">
          <label class="form-label" for="quickCreateUnitClientName">Name</label>
          <input id="quickCreateUnitClientName" class="form-control" type="text" maxlength="64" placeholder="e.g., bar, bottle, packet" />
        </div>
        <div class="mb-2">
          <label class="form-label" for="quickCreateUnitClientType">Type</label>
          <select id="quickCreateUnitClientType" class="form-select">
            <option value="count" selected>Count</option>
            <option value="weight">Weight</option>
            <option value="volume">Volume</option>
            <option value="length">Length</option>
            <option value="area">Area</option>
            <option value="time">Time</option>
          </select>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-primary" id="quickCreateUnitClientSubmit">
          <i class="fas fa-save"></i> Create
        </button>
      </div>
    </div>
  </div>
</div>
    `,document.body.appendChild(l),n=document.getElementById("quickCreateUnitClientModal");let e=document.getElementById("quickCreateUnitClientSubmit"),i=document.getElementById("quickCreateUnitClientName"),d=document.getElementById("quickCreateUnitClientType");return e.addEventListener("click",async function(){let s=(i.value||"").trim();if(!s){typeof window.showAlert=="function"&&window.showAlert("warning","Unit name is required");return}let c=e.innerHTML;e.disabled=!0,e.innerHTML='<i class="fas fa-spinner fa-spin"></i> Creating...';try{let a=await fetch("/api/units",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:s,unit_type:d.value||"count"})}),t=await a.json(),o=t&&t.data?t.data:t;if(!a.ok||t&&t.success===!1||o&&o.error)throw new Error(t&&t.error||o&&o.error||"Failed to create unit");window.dispatchEvent(new CustomEvent("unit.created",{detail:{unit:o}})),bootstrap.Modal.getOrCreateInstance(n).hide()}catch(a){typeof window.showAlert=="function"?window.showAlert("danger",a.message||"Failed to create unit"):console.error(a)}finally{e.disabled=!1,e.innerHTML=c}}),n}window.openUnitQuickCreateModal=function(l=""){let e=r(),i=document.getElementById("quickCreateUnitClientName");i&&(i.value=l||"",setTimeout(()=>i.focus(),30)),bootstrap.Modal.getOrCreateInstance(e).show()}})();})();
