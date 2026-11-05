import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time
import html
from datetime import datetime, timedelta, date

from config.db import supabase
from services.cesta_service import listar_cestas
from services.configuracao_cesta_service import carregar_configuracao_cesta
from services.produto_service import listar_produtos_por_categoria_id
from services.pedido_service import salvar_pedido
from services.pedido_adicional_service import salvar_adicionais_pedido
from services.foto_service import salvar_fotos
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador
from utils.formatacao import formatar_moeda, tratar_preco, NOME_LOJA
from utils.email_service import enviar_email_confirmacao

# =====================================================
# CONFIGURAÇÃO DA PÁGINA 
# =====================================================
st.set_page_config(page_title="Painel PDV | Pedido Varejo", page_icon="🛍️", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

# =====================================================
# CSS PREMIUM COM SUPRESSÃO DE PISCADAS (SMOOTH UI)
# =====================================================
CSS_CUSTOMIZADO = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Dancing+Script:wght@600;700&display=swap');

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; color: #4a2e1b !important; }
.block-container { padding-top: 1.2rem !important; padding-bottom: 4rem !important; max-width: 1200px; }
h1, h2, h3, h4 { color: #5a3b28 !important; font-weight: 800 !important; margin-bottom: 6px !important; letter-spacing: -0.3px; }

.header-banner {
    display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 4px; margin-bottom: 1.5rem;
    background: linear-gradient(135deg, #ffffff 0%, #fdfbf8 100%); padding: 20px;
    border-radius: 16px; border: 1px solid #e8ddd3; box-shadow: 0 4px 15px rgba(90, 59, 40, 0.03);
}
.header-title { font-family: 'Dancing Script', cursive !important; font-size: 38px !important; font-weight: 700 !important; color: #c5721f !important; margin: 0 !important; line-height: 1 !important; text-align: center;}
.header-subtitle { font-size: 13px !important; color: #775a46 !important; font-weight: 600 !important; margin-top: 0px !important; text-align: center;}

.corp-card {
    background: #ffffff; border: 1px solid #e8ddd3; border-radius: 16px; padding: 20px;
    box-shadow: 0 4px 12px rgba(90, 59, 40, 0.02); margin-bottom: 15px;
}
.corp-title { font-size: 16px; font-weight: 800; color: #c5721f; margin-bottom: 12px; margin-top: 28px; border-bottom: 2px dashed #f5eee6; padding-bottom: 8px;}

.resumo-financeiro {
    background: #fdfbf8; border: 1px solid #e8ddd3; border-radius: 12px; padding: 12px 18px;
    display: flex; justify-content: space-between; align-items: center; margin-top: 15px;
}
.resumo-item { text-align: center; }
.resumo-label { font-size: 11.5px; font-weight: 700; color: #775a46; text-transform: uppercase; letter-spacing: 0.5px; }
.resumo-valor { font-size: 18px; font-weight: 800; color: #4a2e1b; }
.resumo-destaque { font-size: 22px; font-weight: 800; color: #137333; }

div[data-testid="stButton"] button { border-radius: 10px !important; font-weight: 800 !important; transition: all 0.15s ease !important; }
div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, #137333 0%, #0d4e22) !important; color: white !important; border: none !important; box-shadow: 0 4px 12px rgba(19, 115, 51, 0.2) !important; }
div[data-testid="stButton"] button[kind="primary"]:hover { background: linear-gradient(135deg, #0f5c28 0%, #093818) !important; transform: translateY(-1px) !important; }

@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .header-title { font-size: 32px !important; }
    .corp-card { padding: 16px; }
}

@media (max-width: 640px) {
    .block-container { padding-left: .8rem !important; padding-right: .8rem !important; padding-top: 1rem !important; }
    .header-banner { padding: 14px; }
    .header-title { font-size: 24px !important; }
    .header-subtitle { font-size: 11.5px !important; }
    .corp-card { padding: 12px; }
    .corp-title { font-size: 14px; }
    .resumo-financeiro { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; text-align: left; }
    .resumo-item { text-align: left; }
    .resumo-valor { font-size: 14px; }
    .resumo-destaque { font-size: 17px; }
}
</style>
'''
st.markdown(CSS_CUSTOMIZADO, unsafe_allow_html=True)

# CABEÇALHO COM BOTÃO DE VOLTAR ALINHADO
c_head, c_btn = st.columns([4, 1], vertical_alignment="center")
with c_head:
    page_header("Venda no balcão (PDV)", "Lance pedidos manualmente, rápido e sem interrupções.", "🛍️", ["Operação", "PDV"])
with c_btn:
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if st.button("⬅️ Voltar", use_container_width=True):
        st.switch_page("pages/02_Pedidos.py")

st.write("")

# =====================================================
# FUNÇÕES 
# =====================================================
def obter_cestas_admin():
    try:
        cestas = listar_cestas()
        return sorted([c for c in cestas if c.get("ativa", True)], key=lambda x: x.get("nome", ""))
    except: return []

def obter_adicionais_admin():
    try:
        categorias = supabase.table("categorias").select("*").execute().data or []
        cat_add = next((c for c in categorias if c.get("nome", "").strip().lower() == "adicionais"), None)
        if cat_add:
            produtos_add = listar_produtos_por_categoria_id(cat_add["id"])
            return sorted([p for p in produtos_add if p.get("ativo", True)], key=lambda x: x.get("nome", ""))
        return []
    except: return []

def carregar_config_cesta_cached(cesta_id):
    try:
        return carregar_configuracao_cesta(cesta_id)
    except: return []

def buscar_cep_api(cep_str):
    cep_limpo = re.sub(r'\D', '', cep_str)
    if len(cep_limpo) != 8: return False, "CEP inválido."
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}", timeout=2)
        if r.status_code == 200:
            d = r.json()
            return True, {"logradouro": d.get("street", ""), "bairro": d.get("neighborhood", ""), "localidade": d.get("city", ""), "uf": d.get("state", "")}
        return False, "CEP não encontrado."
    except: return False, "Erro de conexão."

cestas_disponiveis = obter_cestas_admin()
adicionais_disponiveis = obter_adicionais_admin()

# ESTADOS DA SESSÃO - ADICIONADO man_email AQUI TAMBÉM
for key in ["man_nome", "man_email", "man_cpf", "man_tel", "man_rua", "man_num", "man_comp", "man_bairro", "man_cidade", "man_cep", "ultimo_cep_man"]:
    if key not in st.session_state: st.session_state[key] = ""
if "modo_busca_cli" not in st.session_state: st.session_state.modo_busca_cli = False
if "itens_orcamento_varejo" not in st.session_state: st.session_state["itens_orcamento_varejo"] = []
if "man_processando" not in st.session_state: st.session_state["man_processando"] = False

# =====================================================
# 1. DADOS DO COMPRADOR
# =====================================================
st.markdown('<div class="corp-title">👤 1. Dados do Comprador</div>', unsafe_allow_html=True)

cc1, cc_btn = st.columns([3.5, 1], vertical_alignment="bottom")
with cc1: nome_comp = st.text_input("Nome Completo *", value=st.session_state.man_nome, key="in_nome")
with cc_btn:
    if st.button("🔍 Buscar Clientes", help="Pesquisar histórico", use_container_width=True):
        st.session_state.modo_busca_cli = not st.session_state.modo_busca_cli

# DESTAQUEI O CAMPO DE E-MAIL AQUI COMO O PRIMEIRO CAMPO DA SEGUNDA LINHA
c_email, c_tel, c_cpf = st.columns([2, 1.5, 1.5])
with c_email: email_comp = st.text_input("E-mail (Para Envio de Recibo)", value=st.session_state.man_email, placeholder="cliente@email.com", key="in_email")
with c_tel: tel_comp = st.text_input("WhatsApp / Telefone *", value=st.session_state.man_tel, key="in_tel")
with c_cpf: cpf_comp = st.text_input("CPF", value=st.session_state.man_cpf, key="in_cpf")

if st.session_state.modo_busca_cli:
    st.markdown("<div style='background: #faf7f3; padding: 12px; border-radius: 10px; margin-top: 10px; border: 1px solid #e8ddd3;'>", unsafe_allow_html=True)
    termo_busca = st.text_input("🔍 Digite Nome ou CPF:", key="man_termo_busca")
    try:
        res_cli = supabase.table("pedidos").select("cliente_nome, cliente_cpf, cliente_telefone, cliente_email").not_.ilike("cliente_nome", "%[B2B]%").execute()
        cli_dict = {c.get("cliente_telefone", "").strip(): c for c in (res_cli.data or []) if c.get("cliente_telefone", "").strip()}
        lista_clientes = sorted(list(cli_dict.values()), key=lambda x: x.get("cliente_nome", ""))
    except: lista_clientes = []
    
    if termo_busca: lista_clientes = [c for c in lista_clientes if termo_busca.lower() in str(c.get("cliente_nome", "")).lower() or termo_busca in str(c.get("cliente_cpf", ""))]
    opcoes_cli = [{"cliente_nome": "--- Selecione ---", "cliente_cpf": "", "cliente_telefone": "", "cliente_email": ""}] + lista_clientes
    cli_sel = st.selectbox("Resultados:", opcoes_cli, format_func=lambda x: f"{x['cliente_nome']} ({x['cliente_telefone']})", key="man_busca_dropdown")
    
    if cli_sel and cli_sel["cliente_nome"] != "--- Selecione ---":
        st.session_state.man_nome = cli_sel["cliente_nome"]
        st.session_state.man_cpf = cli_sel["cliente_cpf"]
        st.session_state.man_tel = cli_sel["cliente_telefone"]
        st.session_state.man_email = cli_sel.get("cliente_email", "") or ""
        st.session_state.modo_busca_cli = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================
# 2. SELEÇÃO DE PRODUTOS E ADICIONAIS
# =====================================================
st.markdown('<div class="corp-title">🎁 2. Seleção de Produtos e Adicionais</div>', unsafe_allow_html=True)

col_add1, col_add2, col_add3 = st.columns(3)

with col_add1:
    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #775a46;'>📦 Pacotes (Cestas Base)</div>", unsafe_allow_html=True)
    cesta_sel = st.selectbox("Cestas", [None] + cestas_disponiveis, format_func=lambda x: x["nome"] if x else "Selecione uma Cesta...", label_visibility="collapsed")
    
    selecoes_cesta_varejo = {}
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
                    esc = st.selectbox(f"{cat}", prods, format_func=lambda p: p["nome"], key=f"var_rad_{cesta_sel['id']}_{cat}")
                    if esc: selecoes_cesta_varejo[cat] = [esc]
                else:
                    escs = st.multiselect(f"{cat} (Máx: {maximo})", prods, format_func=lambda p: p["nome"], max_selections=maximo, key=f"var_mul_{cesta_sel['id']}_{cat}")
                    selecoes_cesta_varejo[cat] = escs

    if st.button("➕ Inserir Cesta", use_container_width=True):
        if cesta_sel:
            itens_sel_str = ""
            if selecoes_cesta_varejo:
                opcoes_str = " | ".join([f"{cat}: {', '.join([i['nome'] for i in itens])}" for cat, itens in selecoes_cesta_varejo.items() if itens])
                if opcoes_str: itens_sel_str = f"Itens: {opcoes_str}"

            st.session_state["itens_orcamento_varejo"].append({
                "id": str(uuid.uuid4()), "tipo": "Cesta", "cesta_id": cesta_sel["id"], "nome": cesta_sel["nome"], 
                "preco_unitario": tratar_preco(cesta_sel.get("preco")), "quantidade": 1, "descricao": itens_sel_str
            })
            st.rerun()

with col_add2:
    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #775a46;'>✨ Extras do Catálogo</div>", unsafe_allow_html=True)
    adc_sel = st.selectbox("Extras", [None] + adicionais_disponiveis, format_func=lambda x: x["nome"] if x else "Selecione um Adicional...", label_visibility="collapsed")
    if st.button("➕ Inserir Extra", use_container_width=True):
        if adc_sel:
            st.session_state["itens_orcamento_varejo"].append({
                "id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None, "nome": adc_sel["nome"], 
                "produto_id": adc_sel.get("id"), "preco_unitario": tratar_preco(adc_sel.get("preco")), "quantidade": 1, "descricao": ""
            })
            st.rerun()

with col_add3:
    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #775a46;'>✍️ Extra Personalizado</div>", unsafe_allow_html=True)
    txt_man = st.text_input("Extra Manual", placeholder="Digite o nome do item...", label_visibility="collapsed")
    if st.button("➕ Inserir Manual", use_container_width=True):
        if txt_man.strip():
            st.session_state["itens_orcamento_varejo"].append({
                "id": str(uuid.uuid4()), "tipo": "Extra", "cesta_id": None, "nome": txt_man.strip(), 
                "produto_id": None, "preco_unitario": 0.0, "quantidade": 1, "descricao": ""
            })
            st.rerun()

if adc_sel and "polaroid" in str(adc_sel.get("nome", "")).lower():
    fotos_polaroid_novas = st.file_uploader(
        "📷 Fotos para o Polaroid (serão enviadas ao bucket ao registrar o pedido)",
        type=["jpg", "jpeg", "png", "webp", "heic"],
        accept_multiple_files=True, key="upload_polaroid_manual"
    )
    if fotos_polaroid_novas:
        st.session_state["fotos_polaroid_staged_man"] = fotos_polaroid_novas

total_bruto = 0
if st.session_state["itens_orcamento_varejo"]:
    st.markdown("<hr style='border-top: 1px dashed #e8ddd3; margin: 20px 0;'>", unsafe_allow_html=True)
    st.markdown("### 🛒 Resumo do Pedido")
    
    h1, h2, h3, h4, h5 = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
    h1.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Descrição</div>", unsafe_allow_html=True)
    h2.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>V. Un. (R$)</div>", unsafe_allow_html=True)
    h3.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Qtd</div>", unsafe_allow_html=True)
    h4.markdown("<div style='color:#775a46; font-size:12px; font-weight:700; text-transform:uppercase;'>Subtotal</div>", unsafe_allow_html=True)
    
    for i, item in enumerate(st.session_state["itens_orcamento_varejo"]):
        c1, c2, c3, c4, c5 = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
        with c1:
            icone = "📦" if item["tipo"] == "Cesta" else "✨"
            st.markdown(f"<div style='margin-top:6px; font-weight:700; font-size:13.5px; color:#4a2e1b;'>{icone} {html.escape(str(item['nome']))}</div>", unsafe_allow_html=True)
            if item.get("descricao"): st.caption(item["descricao"])
        with c2:
            novo_preco = st.number_input("Valor", value=float(item["preco_unitario"]), min_value=0.0, step=1.0, format="%.2f", key=f"var_p_{item['id']}", label_visibility="collapsed")
            st.session_state["itens_orcamento_varejo"][i]["preco_unitario"] = novo_preco
        with c3:
            nova_qtd = st.number_input("Qtd", value=int(item["quantidade"]), min_value=1, step=1, key=f"var_q_{item['id']}", label_visibility="collapsed")
            st.session_state["itens_orcamento_varejo"][i]["quantidade"] = nova_qtd
        with c4:
            subtotal_linha = novo_preco * nova_qtd
            total_bruto += subtotal_linha
            st.markdown(f"<div style='margin-top:8px; font-weight:800; font-size:15px; color:#137333;'>R$ {formatar_moeda(subtotal_linha)}</div>", unsafe_allow_html=True)
        with c5:
            if st.button("🗑️", key=f"var_d_{item['id']}"):
                st.session_state["itens_orcamento_varejo"].pop(i)
                st.rerun()

    st.write("")
    if st.button("🧹 Limpar Carrinho"):
        st.session_state["itens_orcamento_varejo"] = []
        st.rerun()


# =====================================================
# 3. DESTINATÁRIO E CARTÃO
# =====================================================
st.markdown('<div class="corp-title">💌 3. Destinatário e Cartão</div>', unsafe_allow_html=True)

cd1, cd2 = st.columns(2)
with cd1: dest_nome = st.text_input("Nome do Homenageado *", key="man_dest_nome")
with cd2: dest_tel = st.text_input("Telefone do Homenageado", key="man_dest_tel")
motivo = st.text_input("Ocasião (Ex: Aniversário)", key="man_motivo")
mensagem = st.text_area("Mensagem do Cartão", height=70, key="man_msg", placeholder="Texto impresso no cartão.")


# =====================================================
# 5. ENDEREÇO E ENTREGA
# =====================================================
st.markdown('<div class="corp-title">📍 5. Endereço e Entrega</div>', unsafe_allow_html=True)

cx1, cx2 = st.columns([1.5, 2.5], vertical_alignment="bottom")
with cx1: cep_in = st.text_input("CEP", max_chars=8, placeholder="Somente números", key="in_cep")
with cx2:
    if st.button("🔍 Buscar CEP", use_container_width=True):
        cep_limpo = re.sub(r'\D', '', cep_in)
        sucesso, dados = buscar_cep_api(cep_limpo)
        if sucesso:
            st.session_state.man_rua = dados.get("logradouro", "")
            st.session_state.man_bairro = dados.get("bairro", "")
            st.session_state.man_cidade = f"{dados.get('localidade', '')} - {dados.get('uf', '')}"
            st.toast("✅ Endereço carregado!")
            st.rerun()
        else: st.warning(dados)

c_r1, c_r2 = st.columns([3, 1])
with c_r1: rua = st.text_input("Rua/Logradouro *", key="man_rua")
with c_r2: num = st.text_input("Nº *", key="in_num")

comp = st.text_input("Complemento (opcional)", placeholder="Apto, bloco, ponto de referência...", key="man_comp")

c_b1, c_b2 = st.columns(2)
with c_b1: bairro = st.text_input("Bairro *", key="man_bairro")
with c_b2: cidade = st.text_input("Cidade-UF *", key="man_cidade")

st.markdown("<hr style='border: none; border-top: 1px dashed #dfcdbb; margin: 12px 0;'>", unsafe_allow_html=True)
ce1, ce2 = st.columns(2)
with ce1: dt_ent = st.date_input("Data da Entrega", value=date.today(), format="DD/MM/YYYY", key="man_dt")
with ce2: per_ent = st.text_input("Horário Combinado", placeholder="Ex: 08h às 10h", key="man_per")


# =====================================================
# LOGÍSTICA, PAGAMENTO E FECHAMENTO
# =====================================================
st.markdown('<div class="corp-title">💰 Logística, Pagamento e Resumo</div>', unsafe_allow_html=True)

col_d1, col_d2, col_d3, col_d4 = st.columns(4)
with col_d1: frete_lote = st.number_input("Frete / Taxa (R$)", min_value=0.0, step=5.0, value=0.0, key="man_frete")
with col_d2: desconto_perc = st.number_input("Desconto (%)", min_value=0.0, max_value=100.0, step=1.0, value=0.0, key="man_desc")
with col_d3: pag = st.selectbox("Forma de Pagamento", ["Pix", "Cartão de Crédito"], key="man_pag")
with col_d4: status = st.selectbox("Status Inicial", ["Recebido", "Pago"], key="man_status")

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
        <div class="resumo-label">Frete</div>
        <div class="resumo-valor">R$ {formatar_moeda(frete_lote)}</div>
    </div>
    <div class="resumo-item">
        <div class="resumo-label">VALOR TOTAL</div>
        <div class="resumo-destaque">R$ {formatar_moeda(total_liquido)}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")
if st.button("✅ GRAVAR PEDIDO NO SISTEMA", type="primary", use_container_width=True, disabled=st.session_state.get("man_processando", False)):
    if not nome_comp: st.error("Informe o nome do comprador."); st.stop()
    if not tel_comp: st.error("Informe o WhatsApp do comprador."); st.stop()
    if not st.session_state["itens_orcamento_varejo"]: st.error("Adicione ao menos um item ao pedido."); st.stop()
    if not dest_nome: st.error("Informe o Nome do Destinatário."); st.stop()
    if not rua or not num or not bairro: st.error("Preencha o Endereço completo."); st.stop()

    lista_cestas = [it for it in st.session_state["itens_orcamento_varejo"] if it["tipo"] == "Cesta"]
    lista_extras = [it for it in st.session_state["itens_orcamento_varejo"] if it["tipo"] == "Extra"]
    
    lista_str_produtos = [f"{it['quantidade']}x {it['nome']} (R$ {formatar_moeda(it['preco_unitario'])})\n{it.get('descricao','')}".strip() for it in lista_cestas]
    lista_str_extras = [f"{it['quantidade']}x {it['nome']} (R$ {formatar_moeda(it['preco_unitario'])})" for it in lista_extras]
    
    nome_da_cesta_principal = "Pedido Varejo"
    cesta_id_principal = None
    if lista_cestas:
        nome_da_cesta_principal = lista_cestas[0]["nome"]
        cesta_id_principal = lista_cestas[0]["cesta_id"]
    elif lista_extras:
        nome_da_cesta_principal = "Itens Extras"
        
    if not lista_cestas and lista_extras:
        lista_str_produtos = lista_str_extras
        msg_adicionais = f"Desconto de {desconto_perc}% aplicado."
    else:
        msg_adicionais = f"Desconto de {desconto_perc}% aplicado."
        if lista_str_extras:
            msg_adicionais += "\n\nEXTRAS E ADICIONAIS:\n" + "\n".join(lista_str_extras)

    comp_fmt = f" - {comp.strip()}" if comp and comp.strip() else ""
    end_comp = f"{rua}, {num}{comp_fmt} - {bairro}, {cidade} (CEP: {cep_in})"
    
    dados_ped = {
        "cliente_nome": nome_comp.strip(),
        "cliente_email": email_comp.strip(),
        "cliente_cpf": re.sub(r'\D', '', cpf_comp),
        "cliente_telefone": re.sub(r'\D', '', tel_comp),
        "destinatario_nome": dest_nome.strip(),
        "destinatario_telefone": dest_tel.strip(),
        "motivo_homenagem": motivo.strip() or "Varejo/Manual",
        "cesta_id": cesta_id_principal,
        "cesta_nome": nome_da_cesta_principal,
        "produtos": "\n\n".join(lista_str_produtos),
        "adicionais": msg_adicionais,
        "pagamento": pag,
        "mensagem": mensagem,
        "pedido_especial": "",
        "endereco": end_comp,
        "data_entrega": dt_ent.strftime("%Y-%m-%d"),
        "periodo_entrega": per_ent.strip() or "A combinar",
        "status": status,
        "valor_frete": frete_lote,
        "valor_total": total_liquido,
        "cesta_montada": False
    }
    
    with st.spinner("Registrando pedido..."):
        st.session_state["man_processando"] = True
        try:
            suc, p_id = salvar_pedido(dados_ped)
        except Exception as e:
            st.session_state["man_processando"] = False
            st.error(f"Erro de conexão ao registrar pedido: {e}")
            st.stop()

        if suc:
            adicionais_para_banco = [
                {"produto_id": e.get("produto_id"), "nome": e["nome"], "preco": e.get("preco_unitario", 0.0)}
                for e in lista_extras if e.get("produto_id")
            ]
            if adicionais_para_banco:
                try:
                    salvar_adicionais_pedido(p_id, adicionais_para_banco)
                except Exception as e:
                    st.warning(f"Pedido salvo, mas houve falha ao registrar detalhes dos extras: {e}")

            fotos_pendentes_man = st.session_state.get("fotos_polaroid_staged_man") or []
            if fotos_pendentes_man:
                with st.spinner("📦 Enviando fotos Polaroid para o bucket..."):
                    ok_fotos, msg_fotos = salvar_fotos(p_id, fotos_pendentes_man[:2])
                if ok_fotos:
                    st.session_state["fotos_polaroid_staged_man"] = []
                else:
                    st.warning(f"Pedido criado, mas houve falha ao enviar as fotos: {msg_fotos}")

            # --- ENVIO DE EMAIL AO CLIENTE (SE PREENCHIDO) ---
            if email_comp.strip() and "@" in email_comp:
                with st.spinner("📧 Enviando recibo para o e-mail do cliente..."):
                    resumo_email = {
                        "cesta_nome": nome_da_cesta_principal,
                        "destinatario_nome": dest_nome.strip(),
                        "data_entrega": dt_ent.strftime("%d/%m/%Y"),
                        "periodo_entrega": per_ent.strip() or "A combinar",
                        "adicionais_str": ", ".join([e["nome"] for e in lista_extras]) if lista_extras else "Nenhum",
                        "valor_total": f"R$ {formatar_moeda(total_liquido)}"
                    }
                    id_curto = str(p_id).split('-')[0].upper()
                    try:
                        enviar_email_confirmacao(email_comp.strip(), nome_comp.strip(), id_curto, resumo_email)
                    except Exception as e:
                        pass # E-mail é secundário, não trava o pedido

            st.success(f"✅ Pedido criado com sucesso para {nome_comp}!")
            st.session_state["itens_orcamento_varejo"] = []
            
            linhas_wpp = "\n".join([f"📦 {p}" for p in lista_str_produtos])
            if lista_str_extras:
                linhas_wpp += "\n" + "\n".join([f"🎀 {e}" for e in lista_str_extras])
            
            texto_wpp = f"""*NOVO PEDIDO - {NOME_LOJA.upper()}* 🎁\n\n👤 *De:* {nome_comp}\n💝 *Para:* {dest_nome}\n📅 *Entrega:* {dt_ent.strftime("%d/%m/%Y")} ({per_ent})\n📍 *Local:* {bairro} - {cidade}\n\n*ITENS:*\n{linhas_wpp}\n\n*VALORES:*\n💰 Subtotal: R$ {formatar_moeda(total_bruto)}\n🚚 Frete: R$ {formatar_moeda(frete_lote)}\n🔻 Desconto: - R$ {formatar_moeda(valor_desconto)}\n━━━━━━━━━━━━━━━━━━━━\n*TOTAL:* R$ {formatar_moeda(total_liquido)}\n\n💳 *Pagamento:* {pag}"""
            
            st.info("📱 Copie a mensagem para enviar ao cliente no WhatsApp:")
            st.code(texto_wpp, language="markdown")
            st.session_state["man_processando"] = False
            time.sleep(3)
            st.switch_page("pages/02_Pedidos.py")
        else: 
            st.session_state["man_processando"] = False
            st.error("Erro ao registrar no banco de dados.")
