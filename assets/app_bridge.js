/* Doce Cesta — ponte do app mobile (Capacitor). Só atua dentro do aplicativo. */
(function(){
  var W = window, D = document;
  if (W.__dcApp) { return; }
  var C = W.Capacitor;
  var nativo = !!(C && C.isNativePlatform && C.isNativePlatform());
  W.__dcApp = { native: nativo };
  if (!nativo) { return; }

  var PUBLICAS = ['', 'inicio', 'politica_privacidade', 'corporativo_publico'];
  var TEMPO_RELOCK_MS = 2 * 60 * 1000;
  var Bio = C.registerPlugin('BiometricAuth');
  var liberadoEm = 0, ocupado = false, saiuEm = 0;

  function rota(){
    var p = (W.location.pathname || '/').replace(/^\/+|\/+$/g, '').split('/')[0] || '';
    try { p = decodeURIComponent(p); } catch (e) {}
    return p.toLowerCase();
  }
  function ehAdmin(){
    var r = rota();
    if (r.indexOf('_') === 0 || r === 'assets' || r === 'static') { return false; }
    return PUBLICAS.indexOf(r) === -1;
  }
  var expirou = false;

  function estilo(){
    if (D.getElementById('dc-bio-css')) { return; }
    var s = D.createElement('style'); s.id = 'dc-bio-css';
    s.textContent =
      '#dc-bio-lock{position:fixed;inset:0;z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:32px;text-align:center;color:#fff;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;' +
      'background:radial-gradient(420px 320px at 80% 0%,rgba(232,162,78,.55),transparent 65%),radial-gradient(320px 280px at 0% 100%,rgba(19,115,51,.45),transparent 70%),linear-gradient(150deg,#3B2417,#1E130D)}' +
      '#dc-bio-lock img{width:96px;height:96px;border-radius:24px;object-fit:cover;box-shadow:0 10px 30px rgba(0,0,0,.35)}' +
      '#dc-bio-lock h2{margin:6px 0 0;font-size:24px;letter-spacing:-.02em;color:#fff}' +
      '#dc-bio-lock p{margin:0;max-width:300px;color:#E6D2BE;font-size:15px;line-height:1.4}' +
      '#dc-bio-lock .dc-bio-ico{font-size:54px;line-height:1}' +
      '#dc-bio-lock button{appearance:none;border:0;border-radius:999px;padding:15px 28px;font-size:16px;font-weight:700;width:min(300px,100%);cursor:pointer}' +
      '#dc-bio-lock .dc-bio-main{background:#E8A24E;color:#2A190F}' +
      '#dc-bio-lock .dc-bio-sec{background:transparent;color:#E6D2BE;border:1px solid rgba(230,210,190,.4)}' +
      '#dc-bio-msg{min-height:20px;color:#FFD9A8;font-size:14px}';
    D.head.appendChild(s);
  }

  function mostrar(){
    estilo();
    if (D.getElementById('dc-bio-lock')) { return; }
    var d = D.createElement('div'); d.id = 'dc-bio-lock';
    d.innerHTML =
      '<img src="/assets/logo.webp" alt="" onerror="this.style.display=\'none\'">' +
      '<div class="dc-bio-ico">🔒</div>' +
      '<h2>Área administrativa</h2>' +
      '<p>Confirme sua identidade com a biometria do aparelho para continuar.</p>' +
      '<div id="dc-bio-msg"></div>' +
      '<button class="dc-bio-main" id="dc-bio-go">Desbloquear com biometria</button>' +
      '<button class="dc-bio-sec" id="dc-bio-back">Voltar para a loja</button>';
    D.body.appendChild(d);
    D.getElementById('dc-bio-go').onclick = pedir;
    D.getElementById('dc-bio-back').onclick = function(){ W.location.href = '/'; };
  }
  function esconder(){ var d = D.getElementById('dc-bio-lock'); if (d) { d.remove(); } }
  function msg(t){ var m = D.getElementById('dc-bio-msg'); if (m) { m.textContent = t || ''; } }

  async function pedir(){
    if (ocupado) { return; }
    ocupado = true; msg('');
    try {
      var info = await Bio.checkBiometry();
      if (!info.isAvailable && !info.deviceIsSecure) {
        msg('Cadastre uma biometria ou um bloqueio de tela no aparelho para acessar esta área.');
        return;
      }
      await Bio.authenticate({
        reason: 'Acessar a área administrativa',
        cancelTitle: 'Cancelar',
        allowDeviceCredential: true,
        iosFallbackTitle: 'Usar senha do aparelho',
        androidTitle: 'Doce Cesta Brasília',
        androidSubtitle: 'Área administrativa',
        androidConfirmationRequired: false
      });
      liberadoEm = Date.now(); expirou = false;
      esconder();
    } catch (e) {
      var code = (e && e.code) || '';
      if (code === 'userCancel' || code === 'systemCancel' || code === 'appCancel') { msg('Autenticação cancelada.'); }
      else if (code === 'biometryLockout') { msg('Biometria bloqueada. Use o bloqueio de tela do aparelho.'); }
      else { msg('Não foi possível validar. Tente novamente.'); }
    } finally { ocupado = false; }
  }

  function avaliar(){
    if (!ehAdmin()) { esconder(); return; }
    if (liberadoEm && !expirou) { return; }
    var novo = !D.getElementById('dc-bio-lock');
    mostrar();
    if (novo) { setTimeout(pedir, 250); }
  }

  /* detecta navegação interna do Streamlit (pushState) */
  ['pushState', 'replaceState'].forEach(function(fn){
    var orig = W.history[fn];
    W.history[fn] = function(){ var r = orig.apply(this, arguments); setTimeout(avaliar, 0); return r; };
  });
  W.addEventListener('popstate', avaliar);
  setInterval(avaliar, 500);

  /* volta do segundo plano: exige biometria de novo após o tempo limite */
  function foi(){ saiuEm = Date.now(); }
  function voltou(){
    if (saiuEm && (Date.now() - saiuEm) > TEMPO_RELOCK_MS) { expirou = true; liberadoEm = 0; }
    saiuEm = 0; avaliar();
  }
  D.addEventListener('visibilitychange', function(){ D.hidden ? foi() : voltou(); });
  try {
    var App = C.registerPlugin('App');
    App.addListener('appStateChange', function(s){ s && s.isActive ? voltou() : foi(); });
  } catch (e) {}

  /* Streamlit reabre a página ao reconectar: limpa o bloqueio herdado de outra sessão */
  avaliar();
})();
