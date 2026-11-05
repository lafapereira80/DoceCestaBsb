import html
import json
from datetime import datetime, timezone

import streamlit as st

from config.db import supabase
from services.pedido_service import excluir_pedido_completo
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador

st.set_page_config(page_title="Mural de Pedidos", page_icon="📋", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

# ==========================================
# ESTILO — paleta via CSS variables, cards com accent por status,
# stepper de etapa logística, badges e micro-interações
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

:root {
    --brand: #c5721f;
    --brand-dark: #a55c14;
    --text: #4a2e1b;
    --text-strong: #2c1e14;
    --text-muted: #775a46;
    --border: #e8ddd3;
    --ok: #137333;
    --ok-bg: #e6f4ea;
    --info: #1a73e8;
    --info-bg: #e8f0fe;
    --warn: #b06000;
    --warn-bg: #fef7e0;
    --danger: #c5221f;
    --danger-bg: #fce8e6;
    --purple: #7c3aed;
    --purple-bg: #efe6fd;
}

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; color: var(--text) !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 4rem !important; max-width: 1350px !important; }

.header-title { font-size: 28px !important; font-weight: 800 !important; color: var(--brand) !important; margin-bottom: 2px; }
.header-subtitle { font-size: 13px !important; color: var(--text-muted) !important; font-weight: 600 !important; margin-bottom: 18px; }

.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 6px; }
.metric-box {
    background: #fff; border: 1px solid var(--border); border-radius: 14px;
    padding: 14px 16px; display: flex; align-items: center; gap: 12px;
    box-shadow: 0 2px 8px rgba(90,59,40,.03); min-width: 0;
}
.metric-icon { font-size: 22px; flex-shrink: 0; }
.metric-num { font-size: 20px; font-weight: 800; color: var(--text-strong); line-height: 1; }
.metric-label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .03em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.pedido-card {
    position: relative;
    background: #ffffff; border: 1px solid var(--border); border-radius: 14px;
    padding: 18px 18px 14px 18px; box-shadow: 0 4px 14px rgba(90, 59, 40, .04);
    margin-bottom: 15px; transition: all .18s ease; overflow: hidden;
}
.pedido-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px;
    background: var(--accent, var(--brand));
}
.pedido-card:hover { border-color: var(--accent, var(--brand)); box-shadow: 0 10px 22px rgba(197, 114, 31, .12); transform: translateY(-3px); }

.card-header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; margin-bottom: 10px; border-bottom: 1px dashed var(--border); flex-wrap: wrap; gap: 8px; }
.pedido-id { font-size: 16px; font-weight: 800; color: var(--ok); margin: 0; letter-spacing: .02em; }

.tag-tipo { font-size: 10px; font-weight: 800; padding: 4px 9px; border-radius: 20px; text-transform: uppercase; border: 1px solid transparent; letter-spacing: .02em; }
.tag-b2b { background: var(--ok-bg); color: var(--ok); border-color: #ceead6; }
.tag-vitrine { background: var(--info-bg); color: var(--info); border-color: #d2e3fc; }
.tag-varejo { background: var(--warn-bg); color: var(--warn); border-color: #fce8b2; }

.pedido-info { font-size: 13px; color: var(--text); margin-bottom: 4px; font-weight: 500; }
.pedido-info b { color: var(--text-strong); font-weight: 700; }
.pedido-total { font-size: 19px; font-weight: 800; color: var(--ok); margin-top: 10px; }

.status-badge {
    display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 800;
    padding: 4px 10px; border-radius: 20px; text-transform: uppercase; letter-spacing: .02em;
}
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

.stepper { display: flex; align-items: center; margin-top: 12px; padding-top: 10px; border-top: 1px solid #f3ece6; }
.step { display: flex; flex-direction: column; align-items: center; flex: 1; position: relative; }
.step-dot {
    width: 12px; height: 12px; border-radius: 50%; background: #e8ddd3; border: 2px solid #e8ddd3;
    z-index: 2; transition: all .2s ease;
}
.step.done .step-dot { background: var(--accent, var(--brand)); border-color: var(--accent, var(--brand)); }
.step-line { position: absolute; top: 5px; left: -50%; width: 100%; height: 2px; background: #e8ddd3; z-index: 1; }
.step.done .step-line { background: var(--accent, var(--brand)); }
.step:first-child .step-line { display: none; }
.step-label { font-size: 8.5px; font-weight: 700; color: var(--text-muted); margin-top: 4px; text-align: center; text-transform: uppercase; }
.step.done .step-label { color: var(--text-strong); }

.linha-producao-texto { font-size: 11px; color: var(--text-muted); font-weight: 600; margin-top: 8px; text-align: center; }

div[data-testid="stSelectbox"] label { display: none !important; }
div[data-testid="stButton"] button { border-radius: 8px !important; font-weight: 800 !important; transition: all .2s; }
div[data-testid="stButton"] button:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(197,114,31,.25); }

div[role="radiogroup"] { flex-wrap: wrap !important; row-gap: 6px !important; }

@media (max-width: 1024px) {
    .metrics-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .header-title { font-size: 24px !important; }
}

@media (max-width: 640px) {
    .block-container { padding-top: 1rem !important; padding-left: .8rem !important; padding-right: .8rem !important; }
    .header-title { font-size: 21px !important; }
    .header-subtitle { font-size: 12px !important; margin-bottom: 12px; }

    .metrics-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .metric-box { padding: 10px 12px; gap: 8px; }
    .metric-icon { font-size: 18px; }
    .metric-num { font-size: 16px; }
    .metric-label { font-size: 9.5px; }

    .pedido-card { padding: 14px 14px 12px 14px; }
    .pedido-id { font-size: 15px; }
    .pedido-info { font-size: 12.5px; }
    .pedido-total { font-size: 17px; }

    .stepper { margin-top: 10px; padding-top: 8px; }
    .step-label { font-size: 7px; letter-spacing: 0; }
    .step-dot { width: 10px; height: 10px; }

    .status-badge { font-size: 9.5px; padding: 3px 8px; }
    .tag-tipo { font-size: 9px; padding: 3px 7px; }
}
</style>
""", unsafe_allow_html=True)

STATUS_PERMITIDOS = ["Recebido", "Pago", "Desistência"]

STATUS_STYLE = {
    "Recebido":            {"cor": "#1a73e8", "bg": "#e8f0fe", "icone": "📥"},
    "Pago":                {"cor": "#137333", "bg": "#e6f4ea", "icone": "💰"},
    "Enviado":             {"cor": "#7c3aed", "bg": "#efe6fd", "icone": "📦"},
    "Em Rota de Entrega":  {"cor": "#b06000", "bg": "#fef7e0", "icone": "🛵"},
    "Entregue":            {"cor": "#137333", "bg": "#e6f4ea", "icone": "🎉"},
    "Desistência":         {"cor": "#c5221f", "bg": "#fce8e6", "icone": "⚠️"},
}
STATUS_STYLE_PADRAO = {"cor": "#775a46", "bg": "#f3ece6", "icone": "❔"}

ETAPAS = ["Aguardando", "Montagem", "Cesta Pronta", "Em Rota", "Entregue"]

def _etapa_index(status_db, entregador, cesta_montada, chk):
    if status_db == "Entregue":
        return 4
    if status_db in ["Enviado", "Em Rota de Entrega"] or entregador:
        return 3
    if cesta_montada:
        return 2
    if chk and any(chk.values()):
        return 1
    return 0

def _texto_etapa(idx):
    return {
        4: "🎉 Pedido entregue ao destinatário",
        3: "🛵 Saiu para entrega (Rota)",
        2: "✅ Cesta montada na fábrica",
        1: "⚙️ Montagem iniciada (fábrica)",
        0: "⏳ Aguardando montagem",
    }[idx]

@st.cache_data(ttl=30, show_spinner=False)
def carregar_pedidos():
    colunas = (
        "id,status,data_entrega,periodo_entrega,cliente_nome,cesta_nome,"
        "valor_total,checklist,entregador_login,cesta_montada,arquivado,cliente_email"
    )
    res = (
        supabase.table("pedidos")
        .select(colunas)
        .in_("status", ["Recebido", "Pago", "Enviado", "Em Rota de Entrega", "Entregue", "Desistência"])
        .order("data_entrega", desc=False)
        .execute()
    )
    return res.data or []

def alterar_status_callback(pedido_id, widget_key):
    novo_status = st.session_state[widget_key]
    try:
        update_data = {"status": novo_status}
        # Se mudou para "Pago", grava a data/hora atual do pagamento
        if novo_status == "Pago":
            update_data["data_pagamento"] = datetime.now(timezone.utc).isoformat()
            update_data["infinitepay_transaction_id"] = None  # pagamento manual
        supabase.table("pedidos").update(update_data).eq("id", pedido_id).execute()
        carregar_pedidos.clear()
        st.toast(f"✅ Pedido atualizado para: {novo_status}!")
    except Exception as e:
        st.toast(f"❌ Falha ao atualizar pedido: {e}", icon="⚠️")

def enviar_para_rota_callback(pedido_id):
    """Considera a cesta como completamente montada (16_Previsao.py) e libera o pedido
    para a criação de rota (08_Entregas.py). O status permanece 'Pago'."""
    try:
        res = supabase.table("pedidos").select("checklist,status,entregador_login").eq("id", pedido_id).execute()
        atual = (res.data or [{}])[0]
        if atual.get("status") != "Pago":
            st.toast("⚠️ Só é possível enviar para rota pedidos com status Pago.", icon="⚠️")
            return
        chk = atual.get("checklist") or {}
        if isinstance(chk, str):
            try: chk = json.loads(chk)
            except Exception: chk = {}
        if not isinstance(chk, dict): chk = {}
        # Marca todos os itens existentes do checklist como concluídos
        chk = {k: True for k in chk.keys()} if chk else {"✅ Cesta montada (enviada para rota pelo Mural)": True}
        supabase.table("pedidos").update({
            "checklist": chk,
            "cesta_montada": True,
        }).eq("id", pedido_id).eq("status", "Pago").execute()
        carregar_pedidos.clear()
        st.toast("🚚 Pedido enviado para a criação de rota (Entregas)!")
    except Exception as e:
        st.toast(f"❌ Falha ao enviar para rota: {e}", icon="⚠️")

page_header("Mural de pedidos", "Acompanhe a situação e a etapa de cada pedido.", "📋", ["Operação", "Pedidos"])

if "pedido_excluir_confirmar" not in st.session_state:
    st.session_state["pedido_excluir_confirmar"] = None

try:
    with st.spinner("Carregando pedidos ativos..."):
        todos_pedidos = carregar_pedidos()
except Exception as e:
    st.error(f"Não foi possível carregar os pedidos: {e}")
    st.stop()

todos_pedidos = [p for p in todos_pedidos if not (p.get('status') == 'Entregue' and p.get('arquivado'))]

qtd_recebido = sum(1 for p in todos_pedidos if p.get('status') == 'Recebido')
qtd_pago = sum(1 for p in todos_pedidos if p.get('status') in ('Pago', 'Entregue', 'Enviado', 'Em Rota de Entrega'))
qtd_desistencia = sum(1 for p in todos_pedidos if p.get('status') == 'Desistência')

metricas = [
    ("📥", qtd_recebido, "Recebidos"),
    ("💰", qtd_pago, "Pagos"),
    ("⚠️", qtd_desistencia, "Desistências"),
    ("📦", len(todos_pedidos), "Total Ativo"),
]
metrics_html = "<div class='metrics-grid'>" + "".join(
    f"""<div class="metric-box">
        <div class="metric-icon">{icone}</div>
        <div>
            <div class="metric-num">{num}</div>
            <div class="metric-label">{label}</div>
        </div>
    </div>"""
    for icone, num, label in metricas
) + "</div>"
st.markdown(metrics_html, unsafe_allow_html=True)

st.write("")

c_filtro, c_busca, c_colunas, c_refresh = st.columns([2.4, 1.6, .8, .6])
with c_filtro:
    filtro_selecionado = st.radio(
        "Filtro:",
        [f"Recebidos ({qtd_recebido})", f"Pagos ({qtd_pago})", f"Desistência ({qtd_desistencia})", "Todos"],
        horizontal=True,
    )
with c_busca:
    busca = st.text_input("Buscar cliente ou ID", placeholder="🔎 Buscar cliente ou #ID", label_visibility="collapsed")
with c_colunas:
    n_colunas = st.selectbox("Colunas", [2, 3, 4], index=1, label_visibility="collapsed")
with c_refresh:
    if st.button("🔄 Atualizar", use_container_width=True):
        carregar_pedidos.clear()
        st.rerun()

pedidos_filtrados = []
for p in todos_pedidos:
    st_atual = p.get('status', '')
    if filtro_selecionado.startswith("Recebidos") and st_atual == "Recebido":
        pedidos_filtrados.append(p)
    elif filtro_selecionado.startswith("Pagos") and st_atual in ('Pago', 'Entregue', 'Enviado', 'Em Rota de Entrega'):
        pedidos_filtrados.append(p)
    elif filtro_selecionado.startswith("Desistência") and st_atual == "Desistência":
        pedidos_filtrados.append(p)
    elif filtro_selecionado.startswith("Todos"):
        pedidos_filtrados.append(p)

if busca:
    termo = busca.strip().lower()
    pedidos_filtrados = [
        p for p in pedidos_filtrados
        if termo in str(p.get('cliente_nome') or '').lower()
        or termo in str(p['id']).split('-')[0].lower()
    ]

if not pedidos_filtrados:
    st.info("Nenhum pedido encontrado no filtro.")
    st.stop()

cols = st.columns(n_colunas)
for idx, p in enumerate(pedidos_filtrados):
    col = cols[idx % n_colunas]
    pid = p['id']
    id_curto = str(pid).split('-')[0].upper()

    cliente_bruto = str(p.get('cliente_nome') or '')
    if "[B2B]" in cliente_bruto:
        tag_html = '<span class="tag-tipo tag-b2b">🏢 B2B</span>'
    elif "[VITRINE]" in cliente_bruto:
        tag_html = '<span class="tag-tipo tag-vitrine">🌐 VITRINE</span>'
    else:
        tag_html = '<span class="tag-tipo tag-varejo">🛍️ VAREJO</span>'
    cliente_limpo = html.escape(cliente_bruto.replace('[B2B]', '').replace('[VITRINE]', '').strip())
    cesta_nome_seguro = html.escape(str(p.get('cesta_nome') or '-'))
    periodo_seguro = html.escape(str(p.get('periodo_entrega') or '-'))

    try:
        data_f = datetime.strptime(str(p.get('data_entrega'))[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        data_f = "Não definida"
    try:
        valor_f = f"{float(p.get('valor_total', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        valor_f = "0,00"

    chk_str = p.get('checklist') or "{}"
    if isinstance(chk_str, str):
        try:
            chk_str = json.loads(chk_str)
        except Exception:
            chk_str = {}

    status_db = p.get('status', '')
    entregador = p.get('entregador_login')
    cesta_montada = p.get('cesta_montada', False)

    etapa_idx = _etapa_index(status_db, entregador, cesta_montada, chk_str)
    texto_discreto = _texto_etapa(etapa_idx)

    estilo_status = STATUS_STYLE.get(status_db, STATUS_STYLE_PADRAO)
    accent = estilo_status["cor"]

    steps_html = ""
    for i, label in enumerate(ETAPAS):
        done = "done" if i <= etapa_idx else ""
        steps_html += f"""
        <div class="step {done}">
            <div class="step-line"></div>
            <div class="step-dot"></div>
            <div class="step-label">{label}</div>
        </div>
        """

    with col:
        html_card = f"""
        <div class="pedido-card" style="--accent: {accent};">
            <div class="card-header">
                <h3 class="pedido-id">#{id_curto}</h3>
                <div style="display:flex; gap:6px;">
                    {tag_html}
                    <span class="status-badge" style="color:{estilo_status['cor']}; background:{estilo_status['bg']};">
                        <span class="status-dot"></span>{estilo_status['icone']} {html.escape(status_db or '—')}
                    </span>
                </div>
            </div>
            <div class="pedido-info"><b>👤 Cliente:</b> {cliente_limpo}</div>
            <div class="pedido-info"><b>🎁 Cesta:</b> {cesta_nome_seguro}</div>
            <div class="pedido-info"><b>📅 Entrega:</b> {data_f} ({periodo_seguro})</div>
            <div class="pedido-total">R$ {valor_f}</div>
            <div class="stepper">{steps_html}</div>
            <div class="linha-producao-texto">{texto_discreto}</div>
        </div>
        """
        st.markdown(html_card.replace('\n', ''), unsafe_allow_html=True)

        c_status, c_btn = st.columns([1.5, 1])
        with c_status:
            opcoes_status_card = STATUS_PERMITIDOS if status_db in STATUS_PERMITIDOS else STATUS_PERMITIDOS + [status_db]
            idx_st = opcoes_status_card.index(status_db) if status_db in opcoes_status_card else 0
            widget_key = f"st_{pid}"
            st.selectbox(
                "Status Oficial", opcoes_status_card, index=idx_st, key=widget_key,
                on_change=alterar_status_callback, args=(pid, widget_key),
                label_visibility="collapsed",
            )
        with c_btn:
            if st.button("Detalhes", key=f"btn_{pid}", use_container_width=True, type="primary"):
                st.session_state['pedido_detalhe_id'] = pid
                st.switch_page("pages/09_Detalhes_Pedido.py")

        # Botão: enviar para rota (cesta montada + fila de 08_Entregas.py)
        if status_db in ("Recebido", "Pago") and not entregador:
            if cesta_montada and status_db == "Pago":
                st.caption("✅ Cesta montada • aguardando atribuição de entregador em Entregas")
            else:
                st.button(
                    "🚚 Enviar para Rota",
                    key=f"rota_{pid}",
                    use_container_width=True,
                    disabled=(status_db != "Pago"),
                    help=None if status_db == "Pago" else "Disponível após o pagamento (status Pago).",
                    on_click=enviar_para_rota_callback,
                    args=(pid,),
                )
        elif entregador and status_db in ("Pago", "Enviado", "Em Rota de Entrega"):
            st.caption(f"🛵 Em rota com: {html.escape(str(entregador))}")

        if status_db == "Desistência":
            st.write("")
            if st.session_state.get("pedido_excluir_confirmar") == pid:
                st.warning("⚠️ Excluir **definitivamente** este pedido, incluindo as fotos no bucket? Ação irreversível.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ Confirmar", key=f"conf_excl_{pid}", use_container_width=True, type="primary"):
                        sucesso, msg = excluir_pedido_completo(pid)
                        if sucesso:
                            st.session_state["pedido_excluir_confirmar"] = None
                            carregar_pedidos.clear()
                            st.toast("🗑️ Pedido e fotos excluídos definitivamente.")
                            st.rerun()
                        else:
                            st.error(msg)
                with cc2:
                    if st.button("❌ Cancelar", key=f"canc_excl_{pid}", use_container_width=True):
                        st.session_state["pedido_excluir_confirmar"] = None
                        st.rerun()
            else:
                if st.button("🗑️ Excluir Definitivamente", key=f"excl_{pid}", use_container_width=True):
                    st.session_state["pedido_excluir_confirmar"] = pid
                    st.rerun()
