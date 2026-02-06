/* File: recipes/recipe_form.js
   Synopsis: Handles recipe form behaviors, auto-prefix generation, and UI helpers.
   Glossary: Prefix = label prefix derived from recipe name; Portion = discrete unit. */

// Recipe form handling
(function(window){
	'use strict';

	// --- Debounce ---
	// Purpose: Delay execution for bursty input events.
	function debounce(fn, wait){
		var t; return function(){ clearTimeout(t); var ctx=this, args=arguments; t=setTimeout(function(){ fn.apply(ctx,args); }, wait); };
	}

	// --- Build local prefix ---
	// Purpose: Generate a fast fallback prefix from a recipe name.
	function buildLocalPrefix(name){
		var cleaned = String(name || '')
			.replace(/[^A-Za-z0-9\s]+/g, ' ')
			.replace(/[_-]+/g, ' ');
		var words = cleaned.trim().split(/\s+/).filter(Boolean);
		if (!words.length){ return 'RCP'; }
		var upper = words.map(function(word){ return word.toUpperCase(); });
		var candidates = [];
		if (upper.length === 1){
			candidates.push(upper[0].slice(0, 3));
			candidates.push(upper[0].slice(0, 4));
		} else if (upper.length === 2){
			candidates.push(upper[0].slice(0, 2) + upper[1].slice(0, 1));
			candidates.push(upper[0].slice(0, 1) + upper[1].slice(0, 2));
		} else {
			candidates.push(upper[0].slice(0, 1) + upper[1].slice(0, 1) + upper[2].slice(0, 1));
			candidates.push(upper[0].slice(0, 1) + upper[1].slice(0, 2) + upper[2].slice(0, 1));
		}
		var candidate = '';
		for (var i = 0; i < candidates.length; i++){
			if (candidates[i]){
				candidate = candidates[i];
				break;
			}
		}
		candidate = (candidate || 'RCP').toUpperCase();
		return candidate.slice(0, 8);
	}

	// --- Attach auto label prefix ---
	// Purpose: Auto-fill the label prefix after name input changes.
	function attachAutoLabelPrefix(){
		var nameInput = document.querySelector('input[name="name"]');
		var prefixInput = document.getElementById('label_prefix');
		if (!nameInput || !prefixInput){ return; }
		if (prefixInput.dataset.autoPrefix !== 'true'){ return; }

		var endpoint = prefixInput.dataset.prefixEndpoint || '';
		prefixInput.readOnly = true;

		function updatePrefix(){
			var name = (nameInput.value || '').trim();
			if (!name){
				prefixInput.value = '';
				return;
			}
			var fallback = buildLocalPrefix(name);
			prefixInput.value = fallback;
			if (!endpoint){ return; }
			fetch(endpoint + '?name=' + encodeURIComponent(name), {
				headers: { 'X-Requested-With': 'XMLHttpRequest' }
			})
				.then(function(resp){ return resp.ok ? resp.json() : null; })
				.then(function(data){
					if (data && data.prefix){
						prefixInput.value = String(data.prefix || fallback).toUpperCase().slice(0, 8);
					}
				})
				.catch(function(){});
		}

		var debounced = debounce(updatePrefix, 300);
		nameInput.addEventListener('input', debounced);
		nameInput.addEventListener('blur', updatePrefix);
		if (nameInput.value && !prefixInput.value){
			updatePrefix();
		}
	}

	// --- Attach portion typeahead ---
	// Purpose: Provide count-unit suggestions for portion names.
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

	document.addEventListener('DOMContentLoaded', function(){
		attachPortionNameTypeahead();
		attachAutoLabelPrefix();
	});

})(window);
