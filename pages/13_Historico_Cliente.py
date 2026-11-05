import streamlit as st
import html
import json
import urllib.parse
import re
import time

from config.db import supabase
from services.pedido_service import excluir_pedido_completo, buscar_pedido
from services.pedido_adicional_service import listar_adicionais_pedido
from services.cesta_service import buscar_cesta
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador


def esc(valor, padrao='-'):
    """Escapa texto antes de inserir em blocos HTML (evita XSS/quebra de layout).
    Importante nesta página: nome, motivo, endereço etc. vêm do formulário público
    (01_Inicio.py) — ou seja, de qualquer visitante da internet, não só de admins."""
    texto = str(valor) if valor not in (None, '') else padrao
    return html.escape(texto)


def montar_link_whatsapp(telefone):
    """
    Monta o link wa.me. Desde que o checkout público passou a ter seletor de DDI
    internacional, o telefone salvo já vem com o código do país embutido (55, 1,
    351, 34...). Números BR com DDI+DDD+número costumam ter 12-13 dígitos; abaixo
    disso, assumimos que é um cadastro antigo/sem DDI e prefixamos 55 (Brasil),
    que é como esse link sempre funcionou até aqui.
    """
    digitos = re.sub(r'\D', '', str(telefone or ''))
    if not digitos:
        return ""
    if len(digitos) >= 12:
        return f"https://wa.me/{digitos}"
    return f"https://wa.me/55{digitos}"


# =====================================================
# CONFIGURAÇÃO DA PÁGINA E DESIGN PREMIUM
# =====================================================
st.set_page_config(page_title="Histórico de Clientes", page_icon="👥", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()
usuario = st.session_state.get("usuario", {})
perfil_usuario = usuario.get("perfil", "Operador")

st.markdown(
"""
<style>
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1250px; }
div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
h1 { font-size: 28px !important; font-weight: 800 !important; color: #4a2e1b; margin-bottom: 0px !important; letter-spacing: -0.5px; }
p, label { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important; font-size: 13px !important; }

div[data-testid="stVerticalBlockBorderWrapper"] { 
    background: #ffffff; border: 1px solid #e8ddd3 !important; border-radius: 16px !important; 
    padding: 16px 20px !important; margin-bottom: 10px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.02); 
}

.card-title { font-size: 16px !important; font-weight: 800 !important; color: #5a3b28 !important; margin-bottom: 12px !important; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #f3ece6; padding-bottom: 6px; }
.cliente-header { font-size: 22px; font-weight: 800; color: #2c1e14; margin-bottom: 2px; }
.info-label { font-weight: 800; color: #9d7d65; font-size: 10px !important; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
.info-value { font-weight: 700; color: #333; font-size: 14px !important; margin-bottom: 6px; }

.resumo-container { background: linear-gradient(145deg, #ffffff 0%, #fdfcfb 100%); border: 1px solid #e8ddd3; border-radius: 14px; padding: 18px; display: flex; flex-direction: column; gap: 8px; }
.resumo-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px !important; color: #444; padding: 4px 0; border-bottom: 1px dashed #e8ddd3; }
.resumo-row:last-child { border-bottom: none; padding-top: 10px; }
.resumo-label { font-weight: 600; color: #775a46; }
.resumo-val { font-weight: 800; color: #2c1e14; }
.resumo-total-val { font-size: 24px !important; font-weight: 800 !important; color: #137333 !important; }

.badge-status { display: inline-block; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 11px !important; text-transform: uppercase; text-align: center; }
.badge-pago { background-color: #e6f4ea; color: #137333; border: 1px solid #ceead6; }
.badge-recebido { background-color: #fef7e0; color: #b06000; border: 1px solid #fce8b2; }
.badge-enviado { background-color: #e8f0fe; color: #1a73e8; border: 1px solid #d2e3fc; }
.badge-entregue { background-color: #f3e8fd; color: #6a1b9a; border: 1px solid #e9d2fd; }
.badge-desistencia { background-color: #fce8e6; color: #c5221f; border: 1px solid #fad2cf; }
.badge-montada { background-color: #e6f4ea; color: #137333; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 800; border: 1px solid #ceead6; margin-left: 10px; display: inline-block; text-transform: uppercase; }

div[data-testid="stButton"] > button { border-radius: 10px !important; min-height: 38px !important; font-weight: 800 !important; font-size: 13px !important; }
div[data-testid="stLinkButton"] > a { width: 100% !important; border-radius: 10px !important; min-height: 40px !important; font-weight: 800 !important; display: flex !important; align-items: center !important; justify-content: center !important; background-color: #25D366 !important; color: white !important; border: none !important; }

.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0px 0px; font-weight: 800; color: #5a3b28; background-color: #faf7f3; border: 1px solid #e8ddd3; padding: 10px 20px; }
.stTabs [aria-selected="true"] { background-color: #ffffff !important; color: #c5721f !important; border-bottom: 2px solid #c5721f !important; }

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .resumo-total-val { font-size: 20px !important; }
}

/* =========================================
   RESPONSIVIDADE — CELULAR (≤ 768px)
========================================== */
@media (max-width: 768px) {
    .block-container { padding-top: 1rem !important; padding-left: .8rem !important; padding-right: .8rem !important; }
    h1 { font-size: 22px !important; }
    .cliente-header { font-size: 18px; }
    .card-title { font-size: 13px !important; }
    .info-value { font-size: 12.5px !important; }
    .resumo-total-val { font-size: 18px !important; }
    .stTabs [data-baseweb="tab"] { padding: 8px 12px; font-size: 12.5px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 12px 14px !important; }
}
</style>
""",
unsafe_allow_html=True
)

# =====================================================
# CACHING DE DADOS (OTIMIZADO PARA PEDIDO ÚNICO)
# =====================================================
@st.cache_data(ttl=120)
def obter_adicionais_cacheado(pid):
    try: return listar_adicionais_pedido(pid)
    except: return []

@st.cache_data(ttl=300)
def obter_cesta_cacheada(cesta_id):
    try: return buscar_cesta(cesta_id)
    except: return None

@st.cache_data(ttl=60)
def obter_fotos_cacheadas(pid):
    try:
        resposta = supabase.table("pedido_fotos").select("*").eq("pedido_id", pid).order("created_at").execute()
        fotos = resposta.data or []
        url_base = st.secrets.get("SUPABASE_URL", "").rstrip("/")
        for foto in fotos:
            if not foto.get("url") and foto.get("arquivo"):
                foto["url"] = f"{url_base}/storage/v1/object/public/pedido_fotos/{foto['arquivo']}"
        return fotos
    except: return []

# =====================================================
# ROTEAMENTO INTERNO (MODO HISTÓRICO VS MODO FICHA)
# =====================================================
pedido_aberto_id = st.session_state.get("pedido_ficha_aberta")

if pedido_aberto_id:
    # --- MODO VISUALIZAÇÃO DE PEDIDO (SOMENTE LEITURA) ---
    pedido = buscar_pedido(pedido_aberto_id)
    if not pedido:
        st.error("Pedido não encontrado.")
        if st.button("⬅ Voltar"):
            st.session_state["pedido_ficha_aberta"] = None
            st.rerun()
        st.stop()

    col_t1, col_t2 = st.columns([3.5, 1.2])
    with col_t1:
        page_header("Visualização de pedido", "Detalhes completos do pedido.", "👁️", ["Clientes", "Pedido"], "info")
        badge_montada = '<span class="badge-montada">✅ Cesta Montada</span>' if pedido.get("cesta_montada") else ''
        st.markdown(f"**ID #{esc(pedido.get('id'))}** | Status: **{esc(pedido.get('status'))}** {badge_montada}", unsafe_allow_html=True)
    with col_t2:
        st.write("")
        if st.button("⬅ Voltar ao Histórico", use_container_width=True):
            st.session_state["pedido_ficha_aberta"] = None
            st.rerun()

    st.write("")

    # LEITURA DE DADOS AUXILIARES DO PEDIDO
    lista_bruta_adicionais = obter_adicionais_cacheado(pedido["id"])
    adicionais_pedido = []
    nomes_vistos = set()
    for ad in lista_bruta_adicionais:
        nome_ad = ad.get("nome_produto")
        if nome_ad and nome_ad not in nomes_vistos:
            adicionais_pedido.append(ad)
            nomes_vistos.add(nome_ad)

    itens_consulta_salvos = pedido.get("itens_consulta") or {}
    if isinstance(itens_consulta_salvos, str):
        try: itens_consulta_salvos = json.loads(itens_consulta_salvos)
        except: itens_consulta_salvos = {}

    def formatar_valor(valor):
        try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
        except: return "R$ 0,00"

    def formatar_data(data):
        if not data: return "-"
        try:
            ano, mes, dia = str(data)[:10].split("-")
            return f"{dia}/{mes}/{ano}"
        except: return str(data)

    def obter_icone_pagamento(metodo):
        m = str(metodo).strip().lower()
        if "pix" in m: return '<div class="pgto-badge" style="background: #e6f4ea; border-color: #137333; color: #137333;">⚡ PIX</div>'
        elif "cart" in m: return '<div class="pgto-badge" style="background: #e8f0fe; border-color: #1a73e8; color: #1a73e8;">💳 CARTÃO</div>'
        elif "dinheiro" in m: return '<div class="pgto-badge" style="background: #fef7e0; border-color: #b06000; color: #b06000;">💵 DINHEIRO</div>'
        elif "transfer" in m: return '<div class="pgto-badge" style="background: #f3ece6; border-color: #5a3b28; color: #5a3b28;">🏦 TRANSF.</div>'
        return f'<span class="pgto-badge">{esc(metodo)}</span>'

    # ABAS DA FICHA TRAVADA
    aba_geral, aba_itens, aba_financeiro, aba_anexos = st.tabs([
        "📋 1. Visão Geral & Logística", 
        "🍓 2. Personalização & Extras", 
        "💰 3. Fechamento Financeiro", 
        "📷 4. Anotações & Polaroids"
    ])

    with aba_geral:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            with st.container(border=True):
                st.markdown('<div class="card-title">👤 Informações de Contato</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-label">Comprador</div><div class="info-value">{esc(pedido.get("cliente_nome"))} <span style="font-size:12px;color:#666;">(CPF: {esc(pedido.get("cliente_cpf"))})</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-value">📞 +{esc(pedido.get("cliente_telefone"))} | 📧 {esc(pedido.get("cliente_email"))}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-label">Homenageado (Destinatário)</div><div class="info-value">{esc(pedido.get("destinatario_nome"))} (📞 {esc(pedido.get("destinatario_telefone"), "Não inf.")})</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-label">Motivo</div><div class="info-value">{esc(pedido.get("motivo_homenagem"))}</div>', unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown('<div class="card-title">💌 Cartão de Homenagem</div>', unsafe_allow_html=True)
                st.text_area("", value=pedido.get("mensagem") or "Sem mensagem informada.", disabled=True, height=85, label_visibility="collapsed")

        with col_g2:
            with st.container(border=True):
                st.markdown('<div class="card-title">🎁 Detalhes da Entrega e Pacote</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1: 
                    st.markdown(f'<div class="info-label">Cesta Adquirida</div><div class="info-value">{esc(pedido.get("cesta_nome"))}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="info-label">Data Limite</div><div class="info-value">{esc(formatar_data(pedido.get("data_entrega")))}</div>', unsafe_allow_html=True)
                with c2: 
                    st.markdown(f'<div class="info-label">Forma de Pagto</div><div class="info-value">{obter_icone_pagamento(pedido.get("pagamento", "-"))}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="info-label">Período Ideal</div><div class="info-value">{esc(pedido.get("periodo_entrega"))}</div>', unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown('<div class="card-title">✨ Observações Especiais</div>', unsafe_allow_html=True)
                st.text_area("", value=pedido.get("pedido_especial") or "Nenhuma solicitação especial.", disabled=True, height=85, label_visibility="collapsed")

        # =====================================================
        # NOVO: COMPROVANTE DE ENTREGA DA LOGÍSTICA
        # =====================================================
        if pedido.get("status") == "Entregue":
            with st.container(border=True):
                st.markdown('<div class="card-title" style="color: #137333; border-bottom: 1px solid #ceead6;">✅ Comprovante de Entrega</div>', unsafe_allow_html=True)
                col_c1, col_c2, col_c3 = st.columns(3)
                with col_c1:
                    st.markdown(f'<div class="info-label">Recebido por</div><div class="info-value" style="color:#137333; font-size: 16px !important;">👤 {esc(pedido.get("quem_recebeu"), "Não informado")}</div>', unsafe_allow_html=True)
                with col_c2:
                    st.markdown(f'<div class="info-label">Data e Hora da Baixa</div><div class="info-value">⏰ {esc(pedido.get("hora_entrega_realizada"))}</div>', unsafe_allow_html=True)
                with col_c3:
                    st.markdown(f'<div class="info-label">Entregador Responsável</div><div class="info-value">🛵 {esc(pedido.get("entregador_login"))}</div>', unsafe_allow_html=True)
                    
        with st.container(border=True):
            st.markdown('<div class="card-title">📍 Localização e Roteirização (GPS)</div>', unsafe_allow_html=True)
            endereco_pedido = pedido.get("endereco", "")
            st.text_area("", value=endereco_pedido if endereco_pedido else "O cliente não informou o endereço completo.", disabled=True, height=65, label_visibility="collapsed")
            if endereco_pedido:
                endereco_limpo_gps = re.sub(r'\(CEP:.*?\)', '', endereco_pedido).strip()
                endereco_encoded = urllib.parse.quote(endereco_limpo_gps)
                col_map1, col_map2 = st.columns(2)
                with col_map1: st.link_button("🗺️ Abrir no Google Maps", url=f"https://www.google.com/maps/search/?api=1&query={endereco_encoded}", use_container_width=True)
                with col_map2: st.link_button("🚗 Abrir Rota no Waze", url=f"https://waze.com/ul?q={endereco_encoded}&navigate=yes", use_container_width=True)

    with aba_itens:
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            with st.container(border=True):
                st.markdown('<div class="card-title">🛒 Checklist / Composição da Cesta</div>', unsafe_allow_html=True)
                produtos = pedido.get("produtos", "")
                if produtos:
                    for item in produtos.split("\n"): st.markdown(f"<div style='font-size:13px; margin-bottom:6px; font-weight:600;'>✅ {esc(item.replace('•','').strip())}</div>", unsafe_allow_html=True)
                else: st.caption("Nenhum item configurado.")

        with col_i2:
            with st.container(border=True):
                st.markdown('<div class="card-title">🎀 Adicionais e Extras do Pedido</div>', unsafe_allow_html=True)
                
                # 1. Adicionais de Catálogo
                if adicionais_pedido:
                    for adicional in adicionais_pedido:
                        nome = adicional.get("nome_produto", "-")
                        valor = adicional.get("valor_unitario")
                        if valor is not None:
                            st.markdown(f"<div style='font-size:13px; margin-bottom:6px; font-weight:600;'>➕ {esc(nome)} - <span style='color:#137333;'>{formatar_valor(valor)}</span></div>", unsafe_allow_html=True)
                        else:
                            val_manual = itens_consulta_salvos.get(nome, 0)
                            st.markdown(f"<div style='font-size:13px; margin-bottom:6px; font-weight:600;'>➕ {esc(nome)} - <span style='color:#137333;'>{formatar_valor(val_manual)}</span></div>", unsafe_allow_html=True)
                
                # 2. Extras Avulsos Dinâmicos consolidados na Aba 2
                tem_extras_dinamicos = False
                for k, v in itens_consulta_salvos.items():
                    if "Valor Manual de" not in k and not k.startswith("Valor de ") and k not in [ad.get("nome_produto") for ad in adicionais_pedido]:
                        if not tem_extras_dinamicos:
                            st.markdown("<div style='margin-top: 10px; font-size: 13px; font-weight: 800; color: #5a3b28;'>➕ Extras Avulsos Personalizados:</div>", unsafe_allow_html=True)
                            tem_extras_dinamicos = True
                        st.markdown(f"<div style='font-size:13px; margin-bottom:4px; font-weight:600;'>🔹 {esc(k)} - <span style='color:#137333;'>{formatar_valor(v)}</span></div>", unsafe_allow_html=True)

                if not adicionais_pedido and not tem_extras_dinamicos:
                    st.caption("Nenhum adicional ou extra solicitado.")

    with aba_financeiro:
        valor_cesta = 0.0
        cesta = obter_cesta_cacheada(pedido.get("cesta_id"))
        if cesta: valor_cesta = float(cesta.get("preco", 0) or 0)

        valor_adicionais_catalogo = 0.0
        for ad in adicionais_pedido:
            nome_ad = ad.get("nome_produto")
            val_ad = ad.get("valor_unitario")
            if val_ad is not None: valor_adicionais_catalogo += float(val_ad)
            else: valor_adicionais_catalogo += float(itens_consulta_salvos.get(nome_ad, 0) or 0)

        valor_extras_total = 0.0
        for k, v in itens_consulta_salvos.items():
            if "Valor Manual de" not in k and not k.startswith("Valor de ") and k not in [ad.get("nome_produto") for ad in adicionais_pedido]:
                try:
                    valor_extras_total += float(v)
                except:
                    pass

        valor_frete = float(pedido.get("valor_frete") or 0)
        desconto = float(pedido.get("desconto") or 0)
        valor_total_calculado = max(0, valor_cesta + valor_adicionais_catalogo + valor_frete + valor_extras_total - desconto)

        col_f1, col_f2 = st.columns([1.2, 1])
        with col_f1:
            with st.container(border=True):
                st.markdown('<div class="card-title">💰 Informações Logísticas e Fiscais</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-label">Horário Fixo de Entrega</div><div class="info-value">🕒 {esc(pedido.get("horario_combinado"), "Não definido")}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-label">Status do Pedido</div><div class="info-value">{esc(pedido.get("status"))}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="info-label">Cesta Montada</div><div class="info-value">{"✅ Sim" if pedido.get("cesta_montada") else "⏳ Não"}</div>', unsafe_allow_html=True)

        with col_f2:
            with st.container(border=True):
                st.markdown('<div class="card-title">🧮 Extrato do Recibo Oficial</div>', unsafe_allow_html=True)
                
                st.markdown(
                    f"""
                    <div class="resumo-container">
                        <div class="resumo-row"><span class="resumo-label">🎁 Valor da Cesta</span><span class="resumo-val">{formatar_valor(valor_cesta)}</span></div>
                        <div class="resumo-row"><span class="resumo-label">🎀 Adicionais (Catálogo)</span><span class="resumo-val">{formatar_valor(valor_adicionais_catalogo)}</span></div>
                        <div class="resumo-row"><span class="resumo-label">🚚 Taxa de Entrega</span><span class="resumo-val">{formatar_valor(valor_frete)}</span></div>
                        <div class="resumo-row"><span class="resumo-label">➕ Total Extras Avulsos</span><span class="resumo-val">{formatar_valor(valor_extras_total)}</span></div>
                        <div class="resumo-row"><span class="resumo-label">🏷️ Desconto</span><span class="resumo-val" style="color: #c5221f;">- {formatar_valor(desconto)}</span></div>
                        <div class="resumo-row"><span class="resumo-label" style="font-size:15px; font-weight:800; color:#2c1e14;">💰 VALOR FINAL</span><span class="resumo-total-val">{formatar_valor(valor_total_calculado)}</span></div>
                    </div>
                    """, unsafe_allow_html=True
                )

    with aba_anexos:
        col_an1, col_an2 = st.columns(2)
        with col_an1:
            with st.container(border=True):
                st.markdown('<div class="card-title">📝 Anotações Internas</div>', unsafe_allow_html=True)
                st.text_area("", value=pedido.get("anotacoes_internas") or "Nenhuma anotação registrada.", disabled=True, height=140, label_visibility="collapsed")

        with col_an2:
            with st.container(border=True):
                st.markdown('<div class="card-title">📷 Fotos Polaroid & Anexos</div>', unsafe_allow_html=True)
                fotos = obter_fotos_cacheadas(pedido["id"])
                if fotos:
                    colunas = st.columns(2)
                    for i, foto in enumerate(fotos):
                        with colunas[i % 2]:
                            link_imagem = foto.get("url")
                            if link_imagem:
                                st.image(link_imagem, caption=foto.get("nome_original", "Foto"), use_container_width=True)
                            else: st.caption("⚠️ Link quebrado.")
                else: st.caption("Nenhum anexo ou Polaroid neste pedido.")

    st.write("")
    st.divider()
    if st.button("⬅ Voltar para o Histórico de Compras", use_container_width=True):
        st.session_state["pedido_ficha_aberta"] = None
        st.rerun()
    st.stop()


# =====================================================
# MODO PADRÃO: HISTÓRICO DE COMPRAS DO CLIENTE OTIMIZADO
# =====================================================
alvo_session = st.session_state.get("cliente_historico_alvo")

if not alvo_session:
    st.warning("⚠️ Nenhum cliente selecionado. Retorne à Base de Clientes para selecionar um perfil.")
    if st.button("Ir para Base de Clientes"):
        st.switch_page("pages/03_Clientes.py")
    st.stop()

col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    page_header("Histórico do cliente", "Todos os pedidos e contatos.", "👥", ["Clientes", "Histórico"], "info")
    st.caption("Acompanhe o perfil, o LTV e todas as compras válidas para este cliente.")
with col_t2:
    st.write("")
    if st.button("⬅ Voltar para a Base", use_container_width=True):
        st.switch_page("pages/03_Clientes.py")

# MÁGICA DA PERFORMANCE: Em vez de baixar o banco inteiro, pede para o Supabase filtrar!
try:
    res = supabase.table("pedidos").select("*").or_(f"cliente_cpf.eq.{alvo_session},cliente_telefone.eq.{alvo_session}").execute()
    # Filtra os status descartados
    compras_cliente = [p for p in (res.data or []) if str(p.get("status", "")).strip().capitalize() not in ["Recebido", "Desistência", "Desistencia"]]
except Exception as e:
    st.error(f"Erro ao buscar histórico: {e}")
    compras_cliente = []

if not compras_cliente:
    st.info("Nenhuma compra finalizada encontrada para este cliente.")
    st.stop()

# Monta o "Cliente Atual" baseado na compra mais recente
compras_cliente.sort(key=lambda x: x.get("created_at", ""), reverse=True)
pedido_mais_recente = compras_cliente[0]

# Procura o último e-mail preenchido se o mais recente for nulo
email_mais_recente = "-"
for c in compras_cliente:
    if c.get("cliente_email"):
        email_mais_recente = c.get("cliente_email")
        break

cliente_atual = {
    "nome": pedido_mais_recente.get("cliente_nome", "Cliente sem nome"),
    "cpf": pedido_mais_recente.get("cliente_cpf", "-"),
    "telefone": pedido_mais_recente.get("cliente_telefone", "-"),
    "email": email_mais_recente
}

total_gasto = sum([float(c.get("valor_total", 0) or 0) for c in compras_cliente])
qtd_compras = len(compras_cliente)

st.write("")
with st.container(border=True):
    col_inf1, col_inf2, col_inf3, col_inf4, col_inf5 = st.columns([2.2, 1.3, 1.8, 1.7, 1.5])
    with col_inf1:
        st.markdown(f"<div class='cliente-header'>👤 {esc(cliente_atual['nome'])}</div>", unsafe_allow_html=True)
        st.caption("Perfil Cadastrado Oficial")
    with col_inf2:
        st.markdown(f'<div class="info-label">CPF</div><div class="info-value">{esc(cliente_atual["cpf"])}</div>', unsafe_allow_html=True)
    with col_inf3:
        link_wpp_cliente = montar_link_whatsapp(cliente_atual["telefone"])
        st.markdown(f'<div class="info-label">Contato / WhatsApp</div><div class="info-value"><a href="{esc(link_wpp_cliente, "#")}" target="_blank" style="color: #137333; text-decoration: none; font-weight: 800;">📱 +{esc(cliente_atual["telefone"])}</a></div>', unsafe_allow_html=True)
    with col_inf4:
        st.markdown(f'<div class="info-label">E-mail Principal</div><div class="info-value">📧 {esc(cliente_atual["email"])}</div>', unsafe_allow_html=True)
    with col_inf5:
        total_gasto_fmt = f"R$ {total_gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        st.markdown(f'<div class="info-label">Total Gasto (LTV)</div><div class="info-value" style="color: #137333; font-size: 16px !important;">{total_gasto_fmt}</div>', unsafe_allow_html=True)

    if perfil_usuario == "Administrador":
        with st.expander("⚙️ Zona de Perigo - Excluir Cliente Permanentemente", expanded=False):
            st.error("⚠️ Atenção: Ao deletar o comprador, todos os pedidos e históricos associados a ele serão apagados do banco.")
            confirmar_texto = st.text_input("Digite 'DELETAR' abaixo para confirmar:", key=f"conf_del_cli_{cliente_atual['cpf']}")
            if st.button("🗑️ Deletar Comprador e Compras", type="primary", use_container_width=True):
                if confirmar_texto.strip().upper() == "DELETAR":
                    for comp in compras_cliente:
                        excluir_pedido_completo(comp["id"])
                    st.success("✅ Apagado com sucesso!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.switch_page("pages/03_Clientes.py")
                else:
                    st.warning("⚠️ Digite exatamente a palavra 'DELETAR'.")

st.write("")
st.subheader(f"📦 Histórico de Compras ({qtd_compras} pedidos)")

for compra in compras_cliente:
    with st.container(border=True):
        c_id = compra.get("id")
        status = str(compra.get("status", "Recebido")).strip().capitalize()
        
        classe_badge = "badge-recebido"
        if status == "Pago": classe_badge = "badge-pago"
        elif status == "Enviado": classe_badge = "badge-enviado"
        elif status == "Entregue": classe_badge = "badge-entregue"
        elif "Desistência" in status or "Desistencia" in status: classe_badge = "badge-desistencia"

        col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns([1.2, 3.0, 1.6, 1.6, 1.2])
        with col_c1:
            st.markdown(f'<div class="info-label">Pedido ID</div><div class="info-value">#{esc(str(c_id).split("-")[0].upper())}</div>', unsafe_allow_html=True)
        with col_c2:
            st.markdown(f'<div class="info-label">Pacote Adquirido</div><div class="info-value">🎁 {esc(compra.get("cesta_nome"))}</div>', unsafe_allow_html=True)
            # NOVO: Exibe quem recebeu direto na lista principal!
            if status == "Entregue" and compra.get("quem_recebeu"):
                st.markdown(f"<div style='font-size:12px; color:#137333; margin-top:2px;'>👤 Recebido por: <strong>{esc(compra.get('quem_recebeu'))}</strong></div>", unsafe_allow_html=True)
        with col_c3:
            dt_entrega = compra.get("data_entrega", "-")
            dt_fmt = f"{dt_entrega[8:10]}/{dt_entrega[5:7]}/{dt_entrega[0:4]}" if dt_entrega and len(str(dt_entrega)) >= 10 else str(dt_entrega)
            st.markdown(f'<div class="info-label">Data Entrega</div><div class="info-value">🗓️ {esc(dt_fmt)}</div>', unsafe_allow_html=True)
        with col_c4:
            val = float(compra.get("valor_total", 0) or 0)
            val_fmt = f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            st.markdown(f'<div class="info-label">Valor Total</div><div class="info-value" style="color: #137333;">{val_fmt}</div>', unsafe_allow_html=True)
        with col_c5:
            st.markdown(f'<div class="info-label">Status</div><div><span class="badge-status {classe_badge}">{esc(status)}</span></div>', unsafe_allow_html=True)

        st.write("")
        cc_acao1, cc_acao2 = st.columns([1, 1])
        with cc_acao1:
            if st.button("👁️ Abrir Ficha do Pedido", key=f"abrir_pedido_{c_id}", use_container_width=True):
                st.session_state["pedido_ficha_aberta"] = c_id
                st.rerun()
                
        with cc_acao2:
            if perfil_usuario == "Administrador":
                if st.button("🗑️ Deletar Histórico", key=f"del_compra_{c_id}", use_container_width=True):
                    sucesso_del, msg_del = excluir_pedido_completo(c_id)
                    if sucesso_del:
                        st.toast("✅ Compra apagada!")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    else: st.error(f"❌ {msg_del}")

st.write("")
st.divider()
st.caption("👥 Controle Oficial de Clientes - Doce Cesta Brasília")
