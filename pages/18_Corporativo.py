import streamlit as st
import pandas as pd
import requests
import re
import uuid
import html
import time
from datetime import datetime, timedelta, date

from config.db import supabase
from services.cesta_service import listar_cestas
from services.configuracao_cesta_service import carregar_configuracao_cesta
from services.pedido_service import salvar_pedido
from services.foto_service import salvar_fotos
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador
from utils.formatacao import formatar_moeda, tratar_preco, NOME_LOJA # <-- Puxando da Central!

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Vendas Corporativas", page_icon="🏢", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

# =====================================================
# CSS PREMIUM E OTIMIZAÇÃO PARA IMPRESSÃO (PDF)
# =====================================================
st.markdown(
"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Dancing+Script:wght@600;700&display=swap');

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; color: #4a2e1b !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1200px; }
h1, h2, h3, h4 { color: #5a3b28 !important; font-weight: 800 !important; margin-bottom: 8px !important; letter-spacing: -0.3px; }

.header-banner {
    display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 6px; margin-bottom: 2rem;
    background: linear-gradient(135deg, #ffffff 0%, #fdfbf8 100%); padding: 25px 20px;
    border-radius: 20px; border: 1px solid #e8ddd3; box-shadow: 0 8px 24px rgba(90, 59, 40, 0.04);
}
.header-title { font-family: 'Dancing Script', cursive !important; font-size: 42px !important; font-weight: 700 !important; color: #c5721f !important; margin: 0 !important; line-height: 1.1 !important; text-align: center;}
.header-subtitle { font-size: 14px !important; color: #775a46 !important; font-weight: 600 !important; margin-top: 0px !important; text-align: center;}

.corp-card {
    background: #ffffff; border: 1px solid #e8ddd3; border-radius: 16px; padding: 24px;
    box-shadow: 0 4px 15px rgba(90, 59, 40, 0.02); margin-bottom: 15px;
}
.corp-title { font-size: 18px; font-weight: 800; color: #c5721f; margin-bottom: 15px; margin-top: 30px; border-bottom: 2px dashed #f5eee6; padding-bottom: 10px;}

.proposta-preview {
    background: #ffffff; border: 1px solid #dfcdbb; border-radius: 12px; padding: 40px;
    font-family: 'Arial', sans-serif; color: #333; box-shadow: 0 10px 30px rgba(0,0,0,0.05);
}
.proposta-header { text-align: center; border-bottom: 3px solid #137333; padding-bottom: 15px; margin-bottom: 25px; }
.proposta-total { font-size: 22px; font-weight: bold; color: #137333; text-align: right; margin-top: 20px; border-top: 2px solid #e8ddd3; padding-top: 15px;}

.resumo-financeiro {
    background: #fdfbf8; border: 1px solid #e8ddd3; border-radius: 12px; padding: 15px 20px;
    display: flex; justify-content: space-between; align-items: center; margin-top: 15px;
}
.resumo-item { text-align: center; }
.resumo-label { font-size: 12px; font-weight: 700; color: #775a46; text-transform: uppercase; letter-spacing: 0.5px; }
.resumo-valor { font-size: 20px; font-weight: 800; color: #4a2e1b; }
.resumo-destaque { font-size: 24px; font-weight: 800; color: #137333; }

div[data-testid="stButton"] button { border-radius: 12px !important; font-weight: 800 !important; transition: all 0.2s ease !important; }
div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, #137333 0%, #0d4e22) !important; color: white !important; border: none !important; box-shadow: 0 4px 15px rgba(19, 115, 51, 0.2) !important; }
div[data-testid="stButton"] button[kind="primary"]:hover { background: linear-gradient(135deg, #0f5c28 0%, #093818) !important; transform: translateY(-2px) !important; }

@media print {
    header, footer, section[data-testid="stSidebar"], .stAppDeployMenu, 
    div[data-testid="stButton"], .header-banner, .stTabs > div[role="tablist"],
    div[data-testid="stCheckbox"], div[data-baseweb="select"], input, .corp-card {
        display: none !important;
    }
    .block-container { padding: 0 !important; max-width: 100% !important; margin: 0 !important;}
    .proposta-preview { box-shadow: none !important; border: none !important; padding: 0 !important; }
    body { background-color: white !important; }
}

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .header-title { font-size: 34px !important; }
    .corp-card { padding: 18px; }
}

/* =========================================
   RESPONSIVIDADE — CELULAR (≤ 640px)
========================================== */
@media (max-width: 640px) {
    .block-container { padding-left: .8rem !important; padding-right: .8rem !important; padding-top: 1rem !important; }
    .header-banner { padding: 18px 14px; }
    .header-title { font-size: 26px !important; }
    .header-subtitle { font-size: 12.5px !important; }
    .corp-card { padding: 14px; }
    .corp-title { font-size: 15px; }
    .proposta-preview { padding: 18px; }

    .resumo-financeiro { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; text-align: left; }
    .resumo-item { text-align: left; }
    .resumo-valor { font-size: 15px; }
    .resumo-destaque { font-size: 18px; }
}
</style>
""", unsafe_allow_html=True)

# CABEÇALHO COM BOTÃO DE VOLTAR ALINHADO
c_head, c_btn = st.columns([4, 1], vertical_alignment="center")
with c_head:
    page_header("Vendas corporativas (B2B)", "Monte orçamentos, edite preços, gere PDFs e registre pedidos.", "🏢", ["Operação", "B2B"], "info")
with c_btn:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    if st.button("⬅️ Voltar ao Mural", use_container_width=True):
        st.switch_page("pages/02_Pedidos.py")

st.write("")

# =====================================================
# FUNÇÕES E CACHES OTIMIZADOS (ZERO PISCADAS)
# =====================================================
@st.cache_data(ttl=300, show_spinner=False)
def obter_cestas_admin():
    try:
        cestas = listar_cestas()
        return sorted([c for c in cestas if c.get("ativa", True)], key=lambda x: x.get("nome", ""))
    except: return []

@st.cache_data(ttl=300, show_spinner=False)
def obter_adicionais_admin():
    try:
        res = supabase.table("produtos").select("*").execute()
        ativos = [p for p in (res.data or []) if p.get("ativo", True)]
        return sorted(ativos, key=lambda x: x.get("nome", ""))
    except: return []

@st.cache_data(ttl=300, show_spinner=False)
def carregar_config_cesta_cached(cesta_id):
    try:
        return carregar_configuracao_cesta(cesta_id)
    except: return []

@st.cache_data(ttl=15, show_spinner=False)
def carregar_pedidos_b2b():
    try:
        res = supabase.table("pedidos").select("id, created_at, cliente_nome, valor_total, status, pagamento, cesta_nome").ilike("cliente_nome", "%[B2B]%").execute()
        return res.data or []
    except: return []

def buscar_cnpj_api(cnpj_str):
    cnpj_limpo = re.sub(r'\D', '', cnpj_str)
    if len(cnpj_limpo) != 14: return False, "CNPJ inválido. Digite 14 números."
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200: return True, r.json()
        else: return False, "CNPJ não encontrado."
    except Exception as e: return False, "Erro de conexão."

cestas_disponiveis = obter_cestas_admin()
adicionais_disponiveis = obter_adicionais_admin()

if "corp_cnpj" not in st.session_state: st.session_state.corp_cnpj = ""
if "corp_nome" not in st.session_state: st.session_state.corp_nome = ""
if "corp_tel" not in st.session_state: st.session_state.corp_tel = ""
if "corp_end" not in st.session_state: st.session_state.corp_end = ""
if "itens_orcamento" not in st.session_state: st.session_state["itens_orcamento"] = []
if "b2b_processando" not in st.session_state: st.session_state["b2b_processando"] = False

# =====================================================
# ABAS DO MÓDULO
# =====================================================
aba_proposta, aba_empresas = st.tabs(["📝 Novo Orçamento / Pedido", "🤝 Histórico de Vendas B2B"])

with aba_proposta:
    st.markdown('<div class="corp-title">⚙️ 1. Dados da Empresa e Negociação</div>', unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([2, 1, 3], vertical_alignment="bottom")
    with col_c1:
        cnpj_input = st.text_input("Consulta Rápida por CNPJ", value=st.session_state.corp_cnpj, placeholder="Somente números")
    with col_c2:
        if st.button("🔍 Buscar Dados", use_container_width=True):
            if cnpj_input:
                sucesso, dados = buscar_cnpj_api(cnpj_input)
                if sucesso:
                    st.session_state.corp_cnpj = cnpj_input
                    st.session_state.corp_nome = dados.get("nome_fantasia") or dados.get("razao_social", "")
                    st.session_state.corp_tel = dados.get("ddd_telefone_1", "")
                    
                    log = dados.get('logradouro', '')
                    num = dados.get('numero', '')
                    bairro = dados.get('bairro', '')
                    cidade = dados.get('municipio', '')
                    uf = dados.get('uf', '')
                    st.session_state.corp_end = f"{log}, {num} - {bairro}, {cidade}-{uf}"
                    
                    st.toast("✅ Dados importados com sucesso!")
                    st.rerun()
                else: st.error(dados)
            else: st.warning("Digite um CNPJ.")

    st.write("")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        empresa_nome = st.text_input("Nome da Empresa Cliente *", value=st.session_state.corp_nome, placeholder="Ex: Sicoob, Tribunal de Justiça, etc.")
        telefone_empresa = st.text_input("WhatsApp / Telefone da Empresa", value=st.session_state.corp_tel, placeholder="Ex: (61) 99999-9999")
        contato_nome = st.text_input("A/C (Nome do Contato)", placeholder="Ex: Ana Clara - Coord. de RH")
    with col_e2:
        validade = st.date_input("Validade da Proposta", value=datetime.now() + timedelta(days=7), format="DD/MM/YYYY")
        motivo = st.text_input("Motivo / Evento", placeholder="Ex: Brindes de Fim de Ano, Dia da Mulher")
        data_entrega = st.date_input("Data Acordada para Entrega", value=date.today(), format="DD/MM/YYYY")

    st.markdown("#### 🎁 2. Adicionar Itens ao Contrato (Pacotes e Extras)")
    
    col_add1, col_add2, col_add3 = st.columns(3)
    
    with col_add1:
        st.markdown("<div style='font-size: 13px; font-weight: 700; color: #775a46;'>📦 Pacotes (Cestas Base)</div>", unsafe_allow_html=True)
        cesta_sel = st.selectbox("Cestas", [None] + cestas_disponiveis, format_func=lambda x: x["nome"] if x else "Selecione uma Cesta...", label_visibility="collapsed")
        
        selecoes_cesta_corp = {}
        if cesta_sel:
            cfg = carregar_config_cesta_cached(cesta_sel["id"])
            if cfg and any(grp.get("produtos") for grp in cfg):
                st.markdown("<div style='font-size: 11.5px; font-weight: 700; color: #137333; margin-top: 5px;'>🍓 Opções da Cesta:</div>", unsafe_allow_html=True)
                for grp in cfg:
                    cat = grp.get("categoria", "Geral")
                    prods = grp.get("produtos", [])
                    maximo = grp.get("max_escolhas", 1)
                    if not prods: continue
                    if maximo == 1:
                        esc = st.selectbox(f"{cat}", prods, format_func=lambda p: p["nome"], key=f"corp_rad_{cesta_sel['id']}_{cat}")
                        if esc: selecoes_cesta_corp[cat] = [esc]
                    else:
                        escs = st.multiselect(f"{cat} (Máx: {maximo})", prods, format_func=lambda p: p["nome"], max_selections=maximo, key=f"corp_mul_{cesta_sel['id']}_{cat}")
                        selecoes_cesta_corp[cat] = escs

        if st.button("➕ Inserir Cesta", use_container_width=True):
            if cesta_sel:
                itens_sel_str = ""
                if selecoes_cesta_corp:
                    opcoes_str = " | ".join([f"{cat}: {', '.join([i['nome'] for i in itens])}" for cat, itens in selecoes_cesta_corp.items() if itens])
                    if opcoes_str: itens_sel_str = f"Itens: {opcoes_str}"

                st.session_state["itens_orcamento"].append({
                    "id": str(uuid.uuid4()), "tipo": "Cesta", "cesta_id": cesta_sel["id"], "nome": cesta_sel["nome"], 
                    "preco_unitario": tratar_preco(cesta_sel.get("preco")), "quantidade": 1, "descricao": itens_sel_str
                })
                st.rerun()

    with col_add2:
        st.markdown("<div style='font-size: 13px; font-weight: 700; color: #775a46;'>✨ Extras do Catálogo</div>", unsafe_allow_html=True)
        adc_sel = st.selectbox("Extras", [None] + adicionais_disponiveis, format_func=lambda x: x["nome"] if x else "Selecione um Adicional...", label_visibility="collapsed")
        if st.button("➕ Inserir Extra", use_container_width=True):
            if adc_sel:
                st.session_state["itens_orcamento"].append({
                    "id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None, "nome": adc_sel["nome"], 
                    "preco_unitario": tratar_preco(adc_sel.get("preco")), "quantidade": 1, "descricao": ""
                })
                st.rerun()

    with col_add3:
        st.markdown("<div style='font-size: 13px; font-weight: 700; color: #775a46;'>✍️ Extra Personalizado</div>", unsafe_allow_html=True)
        txt_man = st.text_input("Extra Manual", placeholder="Digite o nome do item...", label_visibility="collapsed")
        if st.button("➕ Inserir Manual", use_container_width=True):
            if txt_man.strip():
                st.session_state["itens_orcamento"].append({
                    "id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None, "nome": txt_man.strip(), 
                    "preco_unitario": 0.0, "quantidade": 1, "descricao": ""
                })
                st.rerun()

    # Uploader de fotos Polaroid em largura cheia (fora das colunas estreitas, evita
    # o layout apertado) — só aparece quando o item selecionado em Extras é Polaroid.
    if adc_sel and "polaroid" in str(adc_sel.get("nome", "")).lower():
        fotos_polaroid_novas = st.file_uploader(
            "📷 Fotos para o Polaroid (serão enviadas ao bucket ao registrar o pedido)",
            type=["jpg", "jpeg", "png", "webp", "heic"],
            accept_multiple_files=True, key="upload_polaroid_corp"
        )
        # Captura os arquivos numa chave estável assim que aparecem — o uploader some da
        # tela quando o admin troca a seleção do Extra, e sem isso as fotos se perdiam.
        if fotos_polaroid_novas:
            st.session_state["fotos_polaroid_staged"] = fotos_polaroid_novas

    total_bruto = 0
    if st.session_state["itens_orcamento"]:
        st.markdown("<hr style='border-top: 1px dashed #e8ddd3; margin: 25px 0;'>", unsafe_allow_html=True)
        st.markdown("### 🛒 Resumo do Contrato")
        
        h1, h2, h3, h4, h5 = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
        h1.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Descrição do Item</div>", unsafe_allow_html=True)
        h2.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Valor Un. (R$)</div>", unsafe_allow_html=True)
        h3.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Qtd</div>", unsafe_allow_html=True)
        h4.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Subtotal</div>", unsafe_allow_html=True)
        
        for i, item in enumerate(st.session_state["itens_orcamento"]):
            c1, c2, c3, c4, c5 = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
            with c1:
                icone = "📦" if item["tipo"] == "Cesta" else "✨"
                st.markdown(f"<div style='margin-top:8px; font-weight:700; font-size:14px; color:#4a2e1b;'>{icone} {html.escape(str(item['nome']))}</div>", unsafe_allow_html=True)
                if item.get("descricao"): st.caption(item["descricao"])
            with c2:
                novo_preco = st.number_input("Valor", value=float(item["preco_unitario"]), min_value=0.0, step=1.0, format="%.2f", key=f"p_{item['id']}", label_visibility="collapsed")
                st.session_state["itens_orcamento"][i]["preco_unitario"] = novo_preco
            with c3:
                nova_qtd = st.number_input("Qtd", value=int(item["quantidade"]), min_value=1, step=1, key=f"q_{item['id']}", label_visibility="collapsed")
                st.session_state["itens_orcamento"][i]["quantidade"] = nova_qtd
            with c4:
                subtotal_linha = novo_preco * nova_qtd
                total_bruto += subtotal_linha
                st.markdown(f"<div style='margin-top:10px; font-weight:800; font-size:16px; color:#137333;'>R$ {formatar_moeda(subtotal_linha)}</div>", unsafe_allow_html=True)
            with c5:
                if st.button("🗑️", key=f"d_{item['id']}"):
                    st.session_state["itens_orcamento"].pop(i)
                    st.rerun()

        st.write("")
        if st.button("🧹 Limpar Todo o Contrato"):
            st.session_state["itens_orcamento"] = []
            st.rerun()

    st.markdown("<hr style='border-top: 1px dashed #e8ddd3; margin: 20px 0;'>", unsafe_allow_html=True)
    st.markdown("#### 💰 3. Logística, Desconto e Fechamento")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1: frete_lote = st.number_input("Frete/Logística (R$)", min_value=0.0, step=10.0, value=0.0)
    with col_d2: desconto_perc = st.number_input("Desconto (%)", min_value=0.0, max_value=100.0, step=1.0, value=0.0)
    with col_d3: prazo_pagamento = st.selectbox("Condição de Pagamento", ["Pix", "Cartão de Crédito", "Faturamento (Boleto)", "Transferência Bancária"])

    endereco_empresa = st.text_input("📍 Endereço de Entrega da Empresa", value=st.session_state.corp_end, placeholder="Ex: SQS 101, Bloco A, Ed. Comercial")

    valor_desconto = total_bruto * (desconto_perc / 100)
    total_liquido = total_bruto - valor_desconto + frete_lote

    st.markdown(f"""
    <div class="resumo-financeiro">
        <div class="resumo-item">
            <div class="resumo-label">Subtotal</div>
            <div class="resumo-valor">R$ {formatar_moeda(total_bruto)}</div>
        </div>
        <div class="resumo-item">
            <div class="resumo-label">Desconto</div>
            <div class="resumo-valor" style="color: #c5221f;">- R$ {formatar_moeda(valor_desconto)}</div>
        </div>
        <div class="resumo-item">
            <div class="resumo-label">Logística</div>
            <div class="resumo-valor">R$ {formatar_moeda(frete_lote)}</div>
        </div>
        <div class="resumo-item">
            <div class="resumo-label">VALOR TOTAL B2B</div>
            <div class="resumo-destaque">R$ {formatar_moeda(total_liquido)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1: ver_preview = st.checkbox("👁️ Montar Documento de Orçamento (PDF / WhatsApp)", value=False)
    with col_btn2:
        if st.button("✅ REGISTRAR PEDIDO B2B", type="primary", use_container_width=True, disabled=st.session_state.get("b2b_processando", False)):
            if not empresa_nome: st.error("Informe o Nome da Empresa."); st.stop()
            if not st.session_state["itens_orcamento"]: st.error("Adicione itens ao contrato."); st.stop()
            if not endereco_empresa: st.error("Informe o Endereço de Entrega."); st.stop()
                
            lista_cestas = [it for it in st.session_state["itens_orcamento"] if it["tipo"] == "Cesta"]
            lista_extras = [it for it in st.session_state["itens_orcamento"] if it["tipo"] == "Extra"]
            
            lista_str_produtos = [f"{it['quantidade']}x {it['nome']} (R$ {formatar_moeda(it['preco_unitario'])})\n{it.get('descricao','')}".strip() for it in lista_cestas]
            lista_str_extras = [f"{it['quantidade']}x {it['nome']} (R$ {formatar_moeda(it['preco_unitario'])})" for it in lista_extras]
            
            nome_da_cesta_principal = lista_cestas[0]["nome"] if lista_cestas else "Lote Corporativo"
            cesta_id_principal = lista_cestas[0]["cesta_id"] if lista_cestas else None
                
            msg_adicionais = f"Desconto de {desconto_perc}% aplicado."
            if lista_str_extras:
                msg_adicionais += "\n\nEXTRAS E ADICIONAIS:\n" + "\n".join(lista_str_extras)

            cnpj_formatado = re.sub(r'\D', '', st.session_state.corp_cnpj) if st.session_state.corp_cnpj else "00000000000"

            dados_b2b = {
                "cliente_nome": f"[B2B] {empresa_nome.strip()}",
                "cliente_telefone": telefone_empresa.strip() or "00000000000",
                "cliente_cpf": cnpj_formatado,
                "destinatario_nome": contato_nome.strip() or "Colaboradores",
                "destinatario_telefone": telefone_empresa.strip(),
                "motivo_homenagem": f"B2B: {motivo.strip()}",
                "cesta_id": cesta_id_principal,
                "cesta_nome": nome_da_cesta_principal,
                "produtos": "\n\n".join(lista_str_produtos),
                "adicionais": msg_adicionais,
                "pagamento": prazo_pagamento,
                "mensagem": "Pedido corporativo gerado pelo painel B2B.",
                "endereco": endereco_empresa,
                "data_entrega": data_entrega.strftime("%Y-%m-%d"),
                "periodo_entrega": "Comercial",
                "status": "Recebido", 
                "valor_frete": frete_lote,
                "valor_total": total_liquido,
                "cesta_montada": False
            }
            
            with st.spinner("Registrando pedido..."):
                st.session_state["b2b_processando"] = True
                try:
                    sucesso, p_id = salvar_pedido(dados_b2b)
                except Exception as e:
                    st.session_state["b2b_processando"] = False
                    st.error(f"Erro de conexão ao registrar pedido: {e}")
                    st.stop()

                if sucesso:
                    fotos_pendentes = st.session_state.get("fotos_polaroid_staged") or []
                    if fotos_pendentes:
                        ok_fotos, msg_fotos = salvar_fotos(p_id, fotos_pendentes)
                        if not ok_fotos:
                            st.warning(f"⚠️ Pedido registrado, mas houve falha ao enviar algumas fotos: {msg_fotos}")
                        st.session_state["fotos_polaroid_staged"] = []
                    st.success(f"🎉 Pedido corporativo registrado com sucesso!")
                    st.session_state["itens_orcamento"] = []
                    st.session_state.corp_cnpj = ""
                    st.session_state.corp_nome = ""
                    st.session_state.corp_tel = ""
                    st.session_state.corp_end = ""
                    st.session_state["b2b_processando"] = False
                    time.sleep(2)
                    st.switch_page("pages/02_Pedidos.py")
                else:
                    st.session_state["b2b_processando"] = False
                    st.error("Erro ao registrar no banco de dados.")


    if st.session_state["itens_orcamento"] and empresa_nome and ver_preview:
        st.markdown("### 👁️ Enviar Proposta para o Cliente")
        aba_pdf, aba_whats = st.tabs(["📄 Documento Formal (Salvar em PDF)", "📱 Copiar para o WhatsApp"])

        with aba_pdf:
            st.info("🖨️ Pressione `Ctrl + P` para Salvar como PDF.")
            linhas_html = ""
            for item in st.session_state["itens_orcamento"]:
                desc_curta = (item['descricao'][:150] + '...') if item['descricao'] and len(item['descricao']) > 150 else (item['descricao'] or '')
                preco_f = formatar_moeda(item['preco_unitario'])
                subtotal_f = formatar_moeda(item['preco_unitario'] * item['quantidade'])
                linhas_html += f"""<tr><td style="padding: 10px; border-bottom: 1px solid #f5eee6;"><b>{html.escape(str(item['nome']))}</b><br><span style="font-size:11px; color:#666;">{html.escape(str(desc_curta))}</span></td><td style="padding: 10px; border-bottom: 1px solid #f5eee6; text-align: center;">{item['quantidade']}</td><td style="padding: 10px; border-bottom: 1px solid #f5eee6; text-align: right;">R$ {preco_f}</td><td style="padding: 10px; border-bottom: 1px solid #f5eee6; text-align: right;">R$ {subtotal_f}</td></tr>"""

            empresa_nome_seg = html.escape(str(empresa_nome))
            contato_nome_seg = html.escape(str(contato_nome)) if contato_nome else ""
            motivo_seg = html.escape(str(motivo)) if motivo else "Orçamento"

            html_documento = f"""<div class="proposta-preview"><div class="proposta-header"><h2 style="color: #137333; margin-bottom: 5px; font-weight: 800;">PROPOSTA COMERCIAL</h2><p style="margin: 0; color: #555; font-size: 14px;">{NOME_LOJA} - Gestão de Encantamento B2B</p></div><table style="width: 100%; border: none; margin-bottom: 25px;"><tr><td style="width: 60%; vertical-align: top;"><p style="margin:2px 0;"><b>Para:</b> {empresa_nome_seg}</p><p style="margin:2px 0;"><b>A/C:</b> {contato_nome_seg}</p><p style="margin:2px 0;"><b>Ref:</b> {motivo_seg}</p></td><td style="width: 40%; vertical-align: top; text-align: right;"><p style="margin:2px 0;"><b>Data Emissão:</b> {datetime.now().strftime("%d/%m/%Y")}</p><p style="margin:2px 0;"><b>Validade:</b> {validade.strftime("%d/%m/%Y")}</p></td></tr></table><table style="width: 100%; border-collapse: collapse; margin-top: 10px;"><tr style="background-color: #faf7f3;"><th style="padding: 12px; text-align: left; border-bottom: 2px solid #e8ddd3;">Descrição</th><th style="padding: 12px; text-align: center; border-bottom: 2px solid #e8ddd3;">Qtd</th><th style="padding: 12px; text-align: right; border-bottom: 2px solid #e8ddd3;">V. Unitário</th><th style="padding: 12px; text-align: right; border-bottom: 2px solid #e8ddd3;">Subtotal</th></tr>{linhas_html}</table><div style="margin-top: 25px; text-align: right; font-size: 15px;"><p style="margin: 4px 0;">Subtotal: R$ {formatar_moeda(total_bruto)}</p><p style="margin: 4px 0; color: #c5221f;">Desconto ({desconto_perc}%): - R$ {formatar_moeda(valor_desconto)}</p><p style="margin: 4px 0;">Logística: R$ {formatar_moeda(frete_lote)}</p></div><div class="proposta-total">TOTAL GERAL: R$ {formatar_moeda(total_liquido)}</div></div>"""
            st.markdown(html_documento, unsafe_allow_html=True)

        with aba_whats:
            linhas_whatsapp = "".join([f"▪️ {item['quantidade']}x *{item['nome']}* (R$ {formatar_moeda(item['preco_unitario'])})\n" for item in st.session_state["itens_orcamento"]])
            texto_wpp = f"""*PROPOSTA COMERCIAL - {NOME_LOJA.upper()}* 🎁\n\n🏢 *Para:* {empresa_nome}\n👤 *A/C:* {contato_nome}\n\n*ITENS:*\n{linhas_whatsapp}\n*VALORES:*\n💰 Subtotal: R$ {formatar_moeda(total_bruto)}\n🔻 Desconto: - R$ {formatar_moeda(valor_desconto)}\n🚚 Logística: R$ {formatar_moeda(frete_lote)}\n━━━━━━━━━━━━━━━━━━━━\n*TOTAL: R$ {formatar_moeda(total_liquido)}*"""
            st.code(texto_wpp, language="markdown")

with aba_empresas:
    st.markdown('<div class="corp-title">🏢 Histórico de Contratos B2B</div>', unsafe_allow_html=True)
    pedidos_b2b = carregar_pedidos_b2b()
    if not pedidos_b2b:
        st.info("Nenhuma venda corporativa registrada ainda.")
    else:
        df_b2b = pd.DataFrame(pedidos_b2b)
        df_b2b["Empresa"] = df_b2b["cliente_nome"].str.replace("[B2B]", "", regex=False).str.strip()
        df_b2b["Data"] = pd.to_datetime(df_b2b["created_at"]).dt.strftime("%d/%m/%Y")
        df_b2b["Valor"] = pd.to_numeric(df_b2b["valor_total"]).apply(lambda x: f"R$ {formatar_moeda(x)}")
        df_display = df_b2b[["Data", "Empresa", "cesta_nome", "Valor", "status", "pagamento"]].rename(columns={"cesta_nome": "Pacote", "status": "Status", "pagamento": "Condição"})
        st.dataframe(df_display, use_container_width=True, hide_index=True)
