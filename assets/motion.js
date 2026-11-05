/* Doce Cesta — motion & interações (idempotente: pode rodar a cada rerun) */
(function(){
  var W = window, D = document;
  if (W.__dcBoot) { return; }
  var reduce = W.matchMedia && W.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var nf = function(v, dec){ return v.toLocaleString('pt-BR', {minimumFractionDigits: dec, maximumFractionDigits: dec}); };

  /* ---- count-up ---- */
  function countUp(el){
    if (el.__done) return; el.__done = true;
    var to = parseFloat(el.dataset.count), dec = parseInt(el.dataset.dec || '0', 10);
    var pre = el.dataset.pre || '', suf = el.dataset.suf || '';
    if (isNaN(to)) return;
    if (reduce) { el.textContent = pre + nf(to, dec) + suf; return; }
    var t0 = performance.now(), dur = 1100;
    (function tick(t){
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 4);
      el.textContent = pre + nf(to * e, dec) + suf;
      if (k < 1) requestAnimationFrame(tick);
    })(t0);
  }

  /* ---- revelar ao rolar ---- */
  var io = ('IntersectionObserver' in W) ? new IntersectionObserver(function(es){
    es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add('is-in'); io.unobserve(e.target); } });
  }, {threshold: .12, rootMargin: '0px 0px -40px 0px'}) : null;

  function scan(root){
    root = root || D;
    root.querySelectorAll('[data-count]').forEach(countUp);
    root.querySelectorAll('[data-reveal]:not(.is-in)').forEach(function(el){
      if (io && !el.__obs){ el.__obs = true; io.observe(el); } else if (!io){ el.classList.add('is-in'); }
    });
  }
  var pend = false;
  new MutationObserver(function(){
    if (pend) return; pend = true;
    requestAnimationFrame(function(){ pend = false; scan(); if (W.__dcAdmin) W.__dcAdmin(); });
  }).observe(D.body, {childList: true, subtree: true});

  /* ---- ripple nos botões ---- */
  D.addEventListener('click', function(ev){
    var b = ev.target.closest && ev.target.closest('.stApp button, .stApp a[data-testid^="stLinkButton"], .dc-ripple-host');
    if (!b || reduce) return;
    var r = b.getBoundingClientRect(), s = Math.max(r.width, r.height);
    var o = D.createElement('span'); o.className = 'dc-ripple';
    o.style.cssText = 'width:'+s+'px;height:'+s+'px;left:'+(ev.clientX - r.left - s/2)+'px;top:'+(ev.clientY - r.top - s/2)+'px';
    if (getComputedStyle(b).position === 'static') b.style.position = 'relative';
    b.appendChild(o); setTimeout(function(){ o.remove(); }, 650);
  }, true);

  /* ---- tilt 3D leve em cards .dc-tilt ---- */
  D.addEventListener('mousemove', function(ev){
    if (reduce) return;
    var c = ev.target.closest && ev.target.closest('.dc-tilt');
    if (!c) return;
    var r = c.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width - .5, y = (ev.clientY - r.top) / r.height - .5;
    c.style.transform = 'perspective(900px) rotateX('+(-y*5)+'deg) rotateY('+(x*6)+'deg) translateY(-4px)';
    c.style.setProperty('--mx', (x+.5)*100 + '%'); c.style.setProperty('--my', (y+.5)*100 + '%');
  }, {passive: true});
  D.addEventListener('mouseout', function(ev){
    var c = ev.target.closest && ev.target.closest('.dc-tilt');
    if (c && !c.contains(ev.relatedTarget)) c.style.transform = '';
  }, {passive: true});

  /* ---- zoom de imagens: overlay no <body> (funciona dentro de qualquer card) ---- */
  D.addEventListener('click', function(ev){
    var im = ev.target.closest && ev.target.closest('img[data-zoom]');
    if (!im) return;
    ev.preventDefault(); ev.stopPropagation();
    var old = D.getElementById('dc-zoom'); if (old) old.remove();
    var box = D.createElement('div'); box.id = 'dc-zoom'; box.setAttribute('role', 'dialog');
    var big = D.createElement('img'); big.src = im.getAttribute('data-zoom') || im.src; big.alt = im.alt || '';
    var x = D.createElement('button'); x.type = 'button'; x.setAttribute('aria-label', 'Fechar'); x.textContent = '×';
    box.appendChild(big); box.appendChild(x); D.body.appendChild(box);
    function close(){ D.removeEventListener('keydown', esc, true); box.classList.add('out'); setTimeout(function(){ box.remove(); }, 200); }
    function esc(e){ if (e.key === 'Escape') close(); }
    box.addEventListener('click', close); D.addEventListener('keydown', esc, true);
  }, true);

  /* ---- rolagem suave para âncoras ---- */
  D.addEventListener('click', function(ev){
    var a = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (!a) return;
    var id = a.getAttribute('href').slice(1), t = id && D.getElementById(id);
    if (t){ ev.preventDefault(); t.scrollIntoView({behavior: reduce ? 'auto' : 'smooth', block: 'start'}); }
  });

  /* ---- ADMIN: paleta de comandos (Ctrl/⌘+K) + dock mobile ---- */
  function navLinks(){
    var out = [], seen = {};
    D.querySelectorAll('section[data-testid="stSidebar"] a[data-testid^="stPageLink"]').forEach(function(a){
      var label = (a.textContent || '').trim().replace(/\s+/g, ' ').replace(/^([^\p{L}\p{N}]+)(?=[\p{L}\p{N}])/u, '$1 ');
      if (!label || seen[a.href]) return; seen[a.href] = 1;
      out.push({el: a, label: label, href: a.getAttribute('href') || ''});
    });
    return out;
  }
  function esc(s){ return s.replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  function openPalette(){
    var links = navLinks(); if (!links.length) return;
    var old = D.getElementById('dc-cmdk'); if (old) old.remove();
    var box = D.createElement('div'); box.id = 'dc-cmdk';
    box.innerHTML = '<div class="dc-cmdk-card" role="dialog" aria-label="Ir para"><input class="dc-cmdk-in" placeholder="Ir para… (pedidos, entregas, clientes)" autocomplete="off"><div class="dc-cmdk-list"></div><div class="dc-cmdk-foot">↑ ↓ navegar · Enter abrir · Esc fechar</div></div>';
    D.body.appendChild(box);
    var inp = box.querySelector('input'), list = box.querySelector('.dc-cmdk-list'), idx = 0, shown = [];
    function norm(s){ return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
    function draw(){
      var q = norm(inp.value.trim());
      shown = links.filter(function(l){ return !q || norm(l.label).indexOf(q) > -1; });
      if (q) shown.sort(function(a, b){
        var sa = new RegExp('(^|[^a-z0-9])' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).test(norm(a.label)) ? 0 : 1;
        var sb = new RegExp('(^|[^a-z0-9])' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).test(norm(b.label)) ? 0 : 1;
        return sa - sb;
      });
      if (idx >= shown.length) idx = 0;
      list.innerHTML = shown.length ? shown.map(function(l, i){ return '<button class="dc-cmdk-it'+(i===idx?' on':'')+'" data-i="'+i+'">'+esc(l.label)+'</button>'; }).join('') : '<div class="dc-cmdk-none">Nada encontrado</div>';
    }
    function go(i){ var l = shown[i]; if (!l) return; close(); l.el.click(); }
    function close(){ box.classList.add('out'); setTimeout(function(){ box.remove(); }, 160); D.removeEventListener('keydown', key, true); }
    function key(e){
      if (e.key === 'Escape'){ close(); }
      else if (e.key === 'ArrowDown'){ e.preventDefault(); idx = (idx+1) % Math.max(1, shown.length); draw(); }
      else if (e.key === 'ArrowUp'){ e.preventDefault(); idx = (idx-1+shown.length) % Math.max(1, shown.length); draw(); }
      else if (e.key === 'Enter'){ e.preventDefault(); go(idx); }
    }
    inp.addEventListener('input', function(){ idx = 0; draw(); });
    list.addEventListener('click', function(e){ var b = e.target.closest('.dc-cmdk-it'); if (b) go(+b.dataset.i); });
    box.addEventListener('mousedown', function(e){ if (e.target === box) close(); });
    D.addEventListener('keydown', key, true);
    draw(); setTimeout(function(){ inp.focus(); }, 30);
  }
  W.__dcOpenPalette = openPalette;

  D.addEventListener('keydown', function(e){
    if (!W.__dcIsAdmin) return;
    var typing = /input|textarea|select/i.test((e.target.tagName||'')) || e.target.isContentEditable;
    if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') || (!typing && e.key === '/')){ e.preventDefault(); openPalette(); }
  });

  W.__dcAdmin = function(){
    if (!W.__dcIsAdmin) return;
    var links = navLinks();
    var has = links.length > 0;
    var btn = D.getElementById('dc-cmdk-btn');
    if (has && !btn){
      btn = D.createElement('button'); btn.id = 'dc-cmdk-btn'; btn.type = 'button';
      btn.innerHTML = '<span>🔎</span><b>Ir para…</b><kbd>Ctrl K</kbd>';
      btn.addEventListener('click', openPalette); D.body.appendChild(btn);
    } else if (!has && btn){ btn.remove(); }
    var dock = D.getElementById('dc-dock');
    if (!has){ if (dock) dock.remove(); return; }
    if (dock && dock.dataset.n === String(links.length)) return;
    if (dock) dock.remove();
    var pick = [['/Admin','🏠','Início'],['/Pedidos','📋','Pedidos'],['/Pedido_Manual','🛍️','Vender'],['/Entregas','🛵','Rotas']];
    dock = D.createElement('nav'); dock.id = 'dc-dock'; dock.dataset.n = String(links.length); dock.setAttribute('aria-label','Atalhos');
    var html = '';
    pick.forEach(function(p){
      var l = links.find(function(x){ try { return new URL(x.el.href).pathname.replace(/\/$/,'').slice(-p[0].length) === p[0]; } catch(e){ return false; } });
      if (l) html += '<button type="button" data-h="'+esc(l.href)+'"><i>'+p[1]+'</i><span>'+p[2]+'</span></button>';
    });
    html += '<button type="button" data-menu="1"><i>☰</i><span>Menu</span></button>';
    dock.innerHTML = html; D.body.appendChild(dock);
    dock.addEventListener('click', function(e){
      var b = e.target.closest('button'); if (!b) return;
      if (b.dataset.menu){
        var t = D.querySelector('[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button, [data-testid="collapsedControl"] button');
        if (t) t.click(); return;
      }
      var l = navLinks().find(function(x){ return x.href === b.dataset.h; }); if (l) l.el.click();
    });
  };

  W.__dcBoot = function(tema){
    W.__dcIsAdmin = (tema === 'admin');
    D.documentElement.setAttribute('data-dc-tema', tema);
    scan(); if (W.__dcAdmin) W.__dcAdmin();
  };
})();
