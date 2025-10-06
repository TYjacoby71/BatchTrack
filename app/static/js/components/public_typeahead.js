(function(window){
  'use strict';

  function debounce(fn, wait){ var t; return function(){ clearTimeout(t); var ctx=this,args=arguments; t=setTimeout(function(){ fn.apply(ctx,args); }, wait); }; }

  function attachPublicGlobalTypeahead(options){
    var inputEl = options && options.inputEl;
    var giHiddenEl = options && options.giHiddenEl;
    var listEl = options && options.listEl;
    if (!inputEl || !giHiddenEl) return;

    if (!listEl){
      listEl = document.createElement('div');
      listEl.className = 'list-group position-absolute w-100 d-none';
      if (inputEl.parentNode) inputEl.parentNode.appendChild(listEl);
    }

    function render(items){
      listEl.innerHTML='';
      var any=false;
      (items||[]).forEach(function(r){
        var a = document.createElement('a'); a.href='#'; a.className='list-group-item list-group-item-action'; a.textContent=r.text;
        a.addEventListener('click', function(e){ e.preventDefault(); inputEl.value=r.text; giHiddenEl.value=r.id; listEl.classList.add('d-none'); listEl.innerHTML=''; });
        listEl.appendChild(a); any=true;
      });
      listEl.classList.toggle('d-none', !any);
    }

    var search = debounce(function(){
      var q = (inputEl.value||'').trim();
      if (!q){ listEl.classList.add('d-none'); listEl.innerHTML=''; return; }
      fetch('/api/public/global-items/search?q=' + encodeURIComponent(q) + '&type=ingredient')
        .then(function(r){ return r.ok ? r.json() : { results: [] }; })
        .then(function(data){ render((data && data.results) || []); })
        .catch(function(){ listEl.classList.add('d-none'); listEl.innerHTML=''; });
    }, 250);

    inputEl.addEventListener('input', function(){ giHiddenEl.value=''; search(); });
    document.addEventListener('click', function(e){ if (!listEl.contains(e.target) && e.target!==inputEl){ listEl.classList.add('d-none'); } });
  }

  window.attachPublicGlobalTypeahead = attachPublicGlobalTypeahead;
})(window);
