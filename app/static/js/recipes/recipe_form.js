
// Recipe form handling
(function(window){
	'use strict';

	function debounce(fn, wait){
		var t; return function(){ clearTimeout(t); var ctx=this, args=arguments; t=setTimeout(function(){ fn.apply(ctx,args); }, wait); };
	}

	function attachPortionNameTypeahead(){
		var input = document.getElementById('portion_name');
		if (!input) return;
		var container = input.parentNode;
		var list = document.createElement('div');
		list.className = 'list-group position-absolute w-100 d-none';
		container.style.position = 'relative';
		container.appendChild(list);

        function render(items){
			list.innerHTML='';
			var any = false;
			if (items && items.length){
				items.forEach(function(u){
					var a = document.createElement('a');
					a.href = '#';
					a.className = 'list-group-item list-group-item-action';
                    a.textContent = u.name;
					a.addEventListener('click', function(ev){ ev.preventDefault(); input.value = u.name; list.classList.add('d-none'); });
					list.appendChild(a);
				});
				any = true;
			}
			// Add create-new action
			var q = (input.value||'').trim();
			if (q){
				var create = document.createElement('a');
				create.href = '#';
				create.className = 'list-group-item list-group-item-action text-primary';
				create.textContent = 'Create "' + q + '"';
				create.addEventListener('click', function(ev){
					ev.preventDefault();
                    fetch('/recipes/units/quick-add', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name:q, type:'count'})})
                    .then(function(r){return r.json();})
                    .then(function(data){ if (data && !data.error){ input.value = data.name || q; list.classList.add('d-none'); }});
				});
				list.appendChild(create);
				any = true;
			}
			list.classList.toggle('d-none', !any);
		}

		var search = debounce(function(){
			var q = (input.value||'').trim();
			if (!q){ list.classList.add('d-none'); list.innerHTML=''; return; }
            fetch('/api/unit-search?type=count&q=' + encodeURIComponent(q), { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
                .then(function(r){ return r.ok ? r.json() : { data: [] }; })
                .then(function(data){ render((data && data.data) || []); })
				.catch(function(){ list.classList.add('d-none'); });
		}, 200);

		input.addEventListener('input', search);
		document.addEventListener('click', function(e){ if (!list.contains(e.target) && e.target !== input){ list.classList.add('d-none'); } });
	}

	document.addEventListener('DOMContentLoaded', function(){ attachPortionNameTypeahead(); });

})(window);
