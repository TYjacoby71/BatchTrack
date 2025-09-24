
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
			if (!items || !items.length){ list.classList.add('d-none'); return; }
			items.forEach(function(u){
				var a = document.createElement('a');
				a.href = '#';
				a.className = 'list-group-item list-group-item-action';
				a.textContent = u.name;
				a.addEventListener('click', function(ev){ ev.preventDefault(); input.value = u.name; list.classList.add('d-none'); });
				list.appendChild(a);
			});
			list.classList.remove('d-none');
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
