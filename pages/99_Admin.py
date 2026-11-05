import html
from datetime import datetime, timedelta, timezone

import streamlit as st

from config.db import supabase
from services.usuario_service import autenticar_usuario
from utils.cookie_auth import salvar_sessao_cookie, restaurar_sessao_cookie
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import alerta, brl, secao

st.set_page_config(page_title="Painel | Doce Cesta", page_icon="🧺", layout="wide")
configurar_pagina()
restaurar_sessao_cookie()
menu_lateral()

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def agora_br():
    return datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)


# ---------------------------------------------------------------- LOGIN
if not st.session_state.get("usuario"):
    st.markdown("""
    <style>
    section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], #dc-dock, #dc-cmdk-btn { display:none !important; }
    html body .stApp .block-container { max-width: 1040px !important; padding-top: 6vh !important; }
    .stHorizontalBlock, div[data-testid="stHorizontalBlock"]{gap:0!important;align-items:stretch!important;filter:drop-shadow(0 24px 40px rgba(60,35,18,.16))}
    html body .stApp div[data-testid="stForm"]{border:none!important;box-shadow:none!important;padding:0!important;background:transparent!important}
    html body .stApp [class*="st-key-dccard-login"]{border-radius:0 32px 32px 0!important;min-height:530px;padding:48px 44px!important;box-shadow:none!important;border:none!important;justify-content:center;transform:none!important}
    html body .stApp [class*="st-key-dccard-login"]:hover{transform:none!important}
    .lg-art{position:relative;padding:44px 38px;color:#fff;min-height:530px;display:flex;flex-direction:column;justify-content:flex-end;isolation:isolate;
      background:radial-gradient(380px 300px at 80% 0%,rgba(232,162,78,.6),transparent 65%),radial-gradient(300px 260px at 0% 100%,rgba(19,115,51,.5),transparent 70%),linear-gradient(150deg,#3B2417,#1E130D)}
    .lg-cup{position:absolute;top:44px;left:38px;font-size:56px;animation:dc-bob 4s ease-in-out infinite}
    .lg-steam{position:absolute;top:26px;left:56px;display:flex;gap:7px}
    .lg-steam i{width:5px;height:34px;border-radius:6px;background:linear-gradient(to top,rgba(255,255,255,.55),transparent);animation:dc-steam 3s ease-in-out infinite}
    .lg-steam i:nth-child(2){animation-delay:.8s;height:42px}.lg-steam i:nth-child(3){animation-delay:1.6s}
    html body .stApp .lg-art h2{color:#fff!important;font-size:38px!important;line-height:1.02;margin:0 0 10px!important;letter-spacing:-.04em!important}
    html body .stApp .lg-art p{color:#E6D2BE;margin:0;font-size:15px;max-width:320px}
    .lg-brand{font:700 30px var(--f-script);color:var(--caramelo-2);margin-bottom:12px}
    .lg-form-h{margin:0 0 4px!important;font-size:26px!important;letter-spacing:-.03em!important}
    .lg-form-p{color:var(--muted);margin:0 0 18px;font-size:14px}
    @media (max-width:820px){html body .stApp [class*="st-key-dccard-login"]{border-radius:0 0 28px 28px!important;padding:28px 22px!important;min-height:0}.lg-art{min-height:200px;padding:28px 24px}.lg-cup{top:26px;left:24px;font-size:42px}.lg-steam{display:none}html body .stApp .lg-art h2{font-size:28px!important}}
    </style>
    """, unsafe_allow_html=True)

    col_arte, col_form = st.columns([1.05, 1], gap="small")
    with col_arte:
        st.markdown("""<div class="lg-art" style="border-radius:32px 0 0 32px">
            <div class="lg-steam"><i></i><i></i><i></i></div><div class="lg-cup">☕</div>
            <div class="lg-brand">Doce Cesta Brasília</div>
            <h2>Pedidos, rotas e vendas num só lugar.</h2>
            <p>Entre com seu acesso para acompanhar a produção do dia.</p></div>""".replace("\n", ""), unsafe_allow_html=True)
    with col_form, st.container(key="dccard-login"):
        if True:
            st.write("")
        with st.form("form_login", border=False):
            st.markdown('<h3 class="lg-form-h">Entrar no painel</h3><p class="lg-form-p">Área exclusiva para colaboradores.</p>', unsafe_allow_html=True)
            usuario_input = st.text_input("Usuário", placeholder="Seu login")
            senha_input = st.text_input("Senha", type="password", placeholder="Sua senha")
            st.write("")
            submit_login = st.form_submit_button("Entrar", use_container_width=True)
            if submit_login:
                if usuario_input and senha_input:
                    with st.spinner("Verificando acesso..."):
                        try:
                            autenticado = autenticar_usuario(usuario_input.strip(), senha_input.strip())
                            if autenticado:
                                st.session_state["usuario"] = autenticado
                                salvar_sessao_cookie(autenticado["login"])
                                st.rerun()
                            else:
                                st.error("Usuário ou senha incorretos. Confira e tente de novo.")
                        except Exception:
                            st.error("Não foi possível conectar ao banco de dados. Tente novamente em instantes.")
                else:
                    st.warning("Preencha usuário e senha para entrar.")
        st.page_link("app.py", label="Voltar para a loja", icon="🏠")
    st.stop()


# ---------------------------------------------------------------- DADOS DO DIA
@st.cache_data(ttl=60, show_spinner=False)
def carregar_painel():
    dados = {"pedidos": [], "leads_novos": 0, "ok": True}
    try:
        dados["pedidos"] = (
            supabase.table("pedidos")
            .select("id,status,data_entrega,periodo_entrega,cliente_nome,cesta_nome,valor_total,created_at,entregador_login,cesta_montada,arquivado,data_pagamento")
            .order("created_at", desc=True).limit(600).execute().data or []
        )
    except Exception:
        dados["ok"] = False
    try:
        leads = supabase.table("leads_corporativos").select("id,status").execute().data or []
        dados["leads_novos"] = sum(1 for l in leads if l.get("status", "novo") == "novo")
    except Exception:
        pass
    return dados


def _data(valor):
    try:
        return datetime.fromisoformat(str(valor)[:19])
    except Exception:
        return None


usuario = st.session_state.get("usuario", {})
perfil = usuario.get("perfil")
login_seguro = html.escape(str(usuario.get("login", "Admin")))
agora = agora_br()
saudacao = "Bom dia" if agora.hour < 12 else ("Boa tarde" if agora.hour < 18 else "Boa noite")
data_extenso = f"{DIAS[agora.weekday()].capitalize()}, {agora.day} de {MESES[agora.month - 1]}"

if perfil == "Entregador":
    st.markdown(f"""<div class="dc-hero"><div class="dc-hero-date">🗓️ {data_extenso}</div>
        <h2>{saudacao}, {login_seguro}.</h2><p>Sua rota do dia está pronta. Toque abaixo para começar.</p></div>""".replace("\n", ""), unsafe_allow_html=True)
    st.page_link("pages/08_Entregas.py", label="Abrir minha rota", icon="🗺️")
    st.stop()

if perfil not in ("Administrador", "Operador"):
    st.warning("Seu perfil não tem nenhum módulo configurado. Fale com um Administrador.")
    st.stop()

painel = carregar_painel()
pedidos = [p for p in painel["pedidos"] if not (p.get("status") == "Entregue" and p.get("arquivado"))]
hoje = agora.date()
amanha = hoje + timedelta(days=1)


def _dt_entrega(p):
    d = _data(p.get("data_entrega"))
    return d.date() if d else None


receita_pago = [p for p in painel["pedidos"] if p.get("status") in ("Pago", "Enviado", "Em Rota de Entrega", "Entregue")]
mes_atual = [p for p in receita_pago if (_data(p.get("created_at")) or datetime.min).strftime("%Y-%m") == agora.strftime("%Y-%m")]
faturamento_mes = sum(float(p.get("valor_total") or 0) for p in mes_atual)
a_receber = [p for p in pedidos if p.get("status") == "Recebido"]
entregas_hoje = [p for p in pedidos if _dt_entrega(p) == hoje and p.get("status") not in ("Entregue", "Desistência")]
sem_entregador = [p for p in entregas_hoje if not p.get("entregador_login")]
amanha_qtd = [p for p in pedidos if _dt_entrega(p) == amanha and p.get("status") not in ("Entregue", "Desistência")]

# série dos últimos 7 dias (faturamento por dia de criação)
serie = []
for i in range(6, -1, -1):
    dia = hoje - timedelta(days=i)
    serie.append(sum(float(p.get("valor_total") or 0) for p in receita_pago if (_data(p.get("created_at")) or datetime.min).date() == dia))
total7 = sum(serie)
pico = max(serie) or 1
pts = [(i * 300 / 6, 54 - (v / pico) * 48) for i, v in enumerate(serie)]
linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
area = f"0,60 {linha} 300,60"
circulos = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#fff" stroke="#E8A24E" stroke-width="2"/>' for x, y in pts)

st.markdown(f"""
<div class="dc-hero">
  <div class="dc-hero-row">
    <div>
      <div class="dc-hero-date">🗓️ {data_extenso}</div>
      <h2>{saudacao}, {login_seguro}.</h2>
      <p>{"Você tem <b>%d entrega(s) para hoje</b> e <b>%d pedido(s) aguardando pagamento</b>." % (len(entregas_hoje), len(a_receber)) if (entregas_hoje or a_receber) else "Nada urgente por aqui. Aproveite para revisar o catálogo."}</p>
    </div>
    <div class="dc-spark">
      <small>Vendas confirmadas · últimos 7 dias</small><b>{brl(total7)}</b>
      <svg viewBox="0 0 300 60" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="sg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#E8A24E" stop-opacity=".45"/><stop offset="1" stop-color="#E8A24E" stop-opacity="0"/></linearGradient></defs>
        <polygon points="{area}" fill="url(#sg)"/>
        <polyline class="ln" points="{linha}" fill="none" stroke="#E8A24E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>{circulos}
      </svg>
    </div>
  </div>
</div>
""".replace("\n", ""), unsafe_allow_html=True)

if not painel["ok"]:
    alerta("Não consegui carregar os números do dia agora. Os módulos continuam disponíveis — tente atualizar em instantes.", "warn", "📡")

from utils.ui import kpi_grid  # noqa: E402

kpi_grid([
    {"icone": "📥", "rotulo": "Aguardando pagamento", "valor": len(a_receber), "tom": "info", "dica": "status Recebido"},
    {"icone": "🛵", "rotulo": "Entregas hoje", "valor": len(entregas_hoje), "tom": "warn", "dica": f"{len(amanha_qtd)} para amanhã"},
    {"icone": "💰", "rotulo": f"Vendas em {MESES[agora.month - 1]}", "valor": faturamento_mes, "prefixo": "R$ ", "casas": 2, "tom": "ok", "dica": f"{len(mes_atual)} pedidos"},
    {"icone": "📨", "rotulo": "Orçamentos novos", "valor": painel["leads_novos"], "tom": "violet", "dica": "empresas aguardando"},
])

# ---------------------------------------------------------------- PRECISA DE VOCÊ
secao("Precisa de você agora", "O que está parado e pode virar atraso", "🔔")
alertas_html = []
antigos = [p for p in a_receber if (_data(p.get("created_at")) or agora) < agora - timedelta(hours=24)]
if sem_entregador:
    alertas_html.append(("danger", "🛵", f"{len(sem_entregador)} entrega(s) de hoje sem entregador", "Atribua uma rota em Rotas de entrega."))
if antigos:
    alertas_html.append(("warn", "⏳", f"{len(antigos)} pedido(s) sem pagamento há mais de 24h", "Confirme o Pix ou fale com o cliente."))
if painel["leads_novos"]:
    alertas_html.append(("violet", "📨", f"{painel['leads_novos']} orçamento(s) corporativo(s) novo(s)", "Responda em até um dia útil."))
if amanha_qtd:
    nao_montadas = [p for p in amanha_qtd if not p.get("cesta_montada")]
    if nao_montadas:
        alertas_html.append(("info", "🧺", f"{len(nao_montadas)} cesta(s) de amanhã ainda sem montagem", "Veja o painel de Produção."))
if alertas_html:
    st.markdown('<div class="dc-now">' + "".join(
        f'<div class="dc-now-it dc-tone-{t}" style="--i:{i}"><div class="dc-now-ico">{ic}</div><div><b>{html.escape(tt)}</b><span>{html.escape(sub)}</span></div></div>'
        for i, (t, ic, tt, sub) in enumerate(alertas_html)) + "</div>", unsafe_allow_html=True)
else:
    st.markdown('<div class="dc-allgood">✅ Tudo em dia. Nenhum pedido parado.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- ATALHOS
secao("Atalhos do dia", "Os módulos que mais resolvem", "⚡")
a1, a2, a3, a4 = st.columns(4)
with a1:
    st.page_link("pages/02_Pedidos.py", label="Pedidos", icon="📋")
with a2:
    st.page_link("pages/19_Pedido_Manual.py", label="Nova venda (PDV)", icon="🛍️")
with a3:
    st.page_link("pages/08_Entregas.py", label="Rotas de entrega", icon="🛵")
with a4:
    st.page_link("pages/16_Previsao.py", label="Produção", icon="🏭")

# ---------------------------------------------------------------- TODOS OS MÓDULOS (com busca)
secao("Todos os módulos", "Digite para filtrar — ou use Ctrl K em qualquer tela", "🧭")
busca = st.text_input("Buscar módulo", placeholder="Ex.: cupom, cliente, frete, categoria…", label_visibility="collapsed")

MODULOS = [
    ("pages/02_Pedidos.py", "Pedidos", "📋", "Mural, status e etapas de cada pedido", "pedidos mural status"),
    ("pages/19_Pedido_Manual.py", "Venda no balcão (PDV)", "🛍️", "Lance um pedido manualmente", "pdv varejo venda manual"),
    ("pages/18_Corporativo.py", "Vendas B2B", "🏢", "Pedidos de empresas", "b2b empresa corporativo"),
    ("pages/24_Leads_Corporativos.py", "Orçamentos corporativos", "📨", "Solicitações recebidas pelo site", "leads orcamento"),
    ("pages/16_Previsao.py", "Produção", "🏭", "O que montar e comprar", "producao previsao insumos"),
    ("pages/08_Entregas.py", "Rotas de entrega", "🛵", "Despacho e entregadores", "entregas rota motoboy"),
    ("pages/03_Clientes.py", "Clientes", "👥", "Base e histórico de compras", "clientes base historico"),
    ("pages/06_Financeiro.py", "Financeiro", "💰", "Faturamento, frete e descontos", "financeiro faturamento caixa"),
    ("pages/22_Cupons.py", "Cupons", "🎟️", "Descontos e campanhas", "cupom desconto promocao"),
    ("pages/04_Cestas.py", "Cestas e kits", "🧺", "Preços, fotos e promoções", "cestas kits catalogo"),
    ("pages/05_Produtos.py", "Produtos e insumos", "🍓", "Itens e adicionais", "produtos insumos adicionais"),
    ("pages/15_Categorias.py", "Categorias", "🏷️", "Organize os produtos", "categorias"),
    ("pages/17_Secoes_Vitrine.py", "Seções da vitrine", "🖥️", "Abas do catálogo online", "vitrine secoes abas"),
    ("pages/20_Configuracoes_Loja.py", "Configurações da loja", "⚙️", "Bairros, horários e regras", "configuracoes bairros frete"),
    ("pages/07_Usuarios.py", "Usuários", "🔑", "Quem acessa o painel", "usuarios acesso senha"),
    ("app.py", "Ver a vitrine", "🌐", "Como o cliente enxerga a loja", "loja vitrine site"),
]


def _norm(t):
    import unicodedata
    return unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode()


termo = _norm(busca.strip())
filtrados = [m for m in MODULOS if not termo or termo in _norm(m[1] + " " + m[3] + " " + m[4])]
if not filtrados:
    from utils.ui import empty_state
    empty_state("Nenhum módulo encontrado", "Tente outra palavra, como “pedido” ou “cliente”.", "🔎")
else:
    for ini in range(0, len(filtrados), 3):
        cols = st.columns(3)
        for col, (caminho, nome, ico, desc, _) in zip(cols, filtrados[ini:ini + 3]):
            with col:
                st.page_link(caminho, label=nome, icon=ico, help=desc)
                st.caption(desc)

st.markdown('<div style="text-align:center;color:var(--faint);font-size:12px;margin-top:34px">Doce Cesta Brasília · Painel v2</div>', unsafe_allow_html=True)
