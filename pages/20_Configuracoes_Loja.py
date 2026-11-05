import streamlit as st
import pandas as pd
from datetime import time as dtime
import re
import unicodedata

from config.db import supabase
from utils.menu import configurar_pagina, menu_lateral
from utils.permissao import administrador_operador

# =====================================================
# LISTA INICIAL (SEMENTE) DE BAIRROS DO DF
# Usada apenas na primeira vez para popular o banco de dados.
# Depois disso, a lista é gerenciada nesta página e salva em
# configuracoes_loja.bairros_cadastrados (banco Neon).
# =====================================================
BAIRROS_PADRAO_DF = [
    "Água Quente", "Águas Claras", "Arapoanga", "Areal (Águas Claras)", "Arniqueira",
    "Asa Norte", "Asa Sul", "Brazlândia", "Candangolândia", "Ceilândia", "Cruzeiro Novo",
    "Cruzeiro Velho", "Fercal", "Gama", "Grande Colorado", "Granja do Torto", "Guará I",
    "Guará II", "Itapoã", "Jardim Botânico", "Jardim Mangueiral", "Lago Norte", "Lago Sul",
    "Mestre d'Armas", "Noroeste", "Núcleo Bandeirante", "Paranoá", "Park Way", "Planaltina",
    "Plano Piloto - Setores Centrais (Esplanada / Hoteleiro / Comercial)", "Recanto das Emas",
    "Riacho Fundo I", "Riacho Fundo II", "Samambaia", "Santa Maria", "São Sebastião",
    "SCIA / Estrutural", "Setor Habitacional Taquari", "Setor Militar Urbano (SMU)",
    "SIA (Setor de Indústria e Abastecimento)", "Sobradinho I", "Sobradinho II",
    "Sol Nascente / Pôr do Sol", "Sudoeste / Octogonal", "Taguatinga Centro", "Taguatinga Norte",
    "Taguatinga Sul", "Vale do Amanhecer", "Varjão", "Vicente Pires", "Vila Planalto"
]

SQL_COLUNA_BAIRROS = "ALTER TABLE configuracoes_loja ADD COLUMN IF NOT EXISTS bairros_cadastrados jsonb;"

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Configurações da Loja", page_icon="⚙️", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

# =====================================================
# CSS PREMIUM (CRYSTAL CLEAN)
# =====================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; color: #1E293B !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 4rem !important; max-width: 900px !important; }

.app-header { font-size: clamp(24px, 4vw, 32px); font-weight: 800; color: #0F172A; margin-top: 10px; margin-bottom: 5px; letter-spacing: -1px; }
.app-sub { font-size: 15px; color: #64748B; margin-bottom: 25px; font-weight: 500; }

div[data-testid="stVerticalBlockBorderWrapper"] { 
    background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; 
    border-radius: 20px !important; padding: 24px !important; 
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02) !important; margin-bottom: 20px !important; 
}

.section-title { font-size: 16px; font-weight: 800; color: #c5721f; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; border-bottom: 2px dashed #f5eee6; padding-bottom: 10px;}
.section-desc { font-size: 13px; color: #64748B; margin-bottom: 20px; line-height: 1.5; }

.stTextInput>div>div>input, .stNumberInput>div>div>input, .stTimeInput>div>div>div>input { 
    border-radius: 10px !important; border: 1px solid #E2E8F0 !important; background-color: #F8FAFC !important; 
}
div[data-testid="stCheckbox"] { background: #faf7f3; border: 1px solid #e8ddd3; padding: 10px 14px; border-radius: 12px; margin-bottom: 8px; }

div[data-testid="stButton"] button { border-radius: 12px !important; font-weight: 800 !important; transition: all 0.2s; }
div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, #137333 0%, #0d4e22) !important; color: white !important; border: none !important; box-shadow: 0 4px 15px rgba(19, 115, 51, 0.2) !important; }
div[data-testid="stButton"] button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(19, 115, 51, 0.3) !important; }

@media (max-width: 640px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 16px !important; }
}
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="app-header">⚙️ Configurações Globais</div><div class="app-sub">Gerencie as regras de negócio, bairros liberados, bloqueios e frete do site público.</div>', unsafe_allow_html=True)

# =====================================================
# FUNÇÕES DE BANCO DE DADOS
# =====================================================
def carregar_configuracoes():
    try:
        res = supabase.table("configuracoes_loja").select("*").eq("id", 1).execute()
        if res.data: return res.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao conectar com o banco: {e}")
        return None

def salvar_configuracoes(dados):
    try:
        supabase.table("configuracoes_loja").update(dados).eq("id", 1).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFKD', str(texto).lower()).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'\s+', ' ', texto).strip()

def ordenar_bairros(lista):
    return sorted({b for b in lista if isinstance(b, str) and b.strip()}, key=normalizar_texto)

def definir_aviso(tipo, msg):
    st.session_state["_aviso_bairros"] = (tipo, msg)

# ---------- CALLBACKS DO CADASTRO DE BAIRROS (executam antes da renderização) ----------
def cb_adicionar_bairro():
    nome = re.sub(r'\s+', ' ', st.session_state.get("novo_bairro_nome", "")).strip()
    liberar = st.session_state.get("novo_bairro_liberar", True)
    if len(nome) < 2:
        definir_aviso("error", "Informe o nome do bairro / região."); return
    cfg = carregar_configuracoes() or {}
    cadastrados = cfg.get("bairros_cadastrados") if isinstance(cfg.get("bairros_cadastrados"), list) else []
    if normalizar_texto(nome) in {normalizar_texto(b) for b in cadastrados}:
        definir_aviso("warning", f"O bairro '{nome}' já está cadastrado."); return
    novos_cadastrados = ordenar_bairros(cadastrados + [nome])
    dados = {"bairros_cadastrados": novos_cadastrados}
    if liberar:
        permitidos = cfg.get("bairros_permitidos") if isinstance(cfg.get("bairros_permitidos"), list) else cadastrados
        dados["bairros_permitidos"] = ordenar_bairros(list(permitidos) + [nome])
    if salvar_configuracoes(dados):
        st.cache_data.clear()
        st.session_state["novo_bairro_nome"] = ""
        if liberar:
            st.session_state["bairros_liberados_sel"] = list(st.session_state.get("bairros_liberados_sel", [])) + [nome]
        definir_aviso("success", f"✅ Bairro '{nome}' cadastrado" + (" e liberado para entrega." if liberar else ". Marque-o abaixo para liberar a entrega."))

def cb_remover_bairros():
    remover = st.session_state.get("bairros_para_remover", [])
    if not remover:
        definir_aviso("error", "Selecione ao menos um bairro para remover."); return
    cfg = carregar_configuracoes() or {}
    cadastrados = cfg.get("bairros_cadastrados") if isinstance(cfg.get("bairros_cadastrados"), list) else []
    permitidos = cfg.get("bairros_permitidos") if isinstance(cfg.get("bairros_permitidos"), list) else cadastrados
    dados = {
        "bairros_cadastrados": [b for b in cadastrados if b not in remover],
        "bairros_permitidos": [b for b in permitidos if b not in remover],
    }
    if salvar_configuracoes(dados):
        st.cache_data.clear()
        st.session_state["bairros_liberados_sel"] = [b for b in st.session_state.get("bairros_liberados_sel", []) if b not in remover]
        st.session_state["bairros_para_remover"] = []
        definir_aviso("success", f"🗑️ {len(remover)} bairro(s) removido(s) do cadastro.")

def cb_salvar_liberados():
    selecionados = ordenar_bairros(st.session_state.get("bairros_liberados_sel", []))
    if salvar_configuracoes({"bairros_permitidos": selecionados}):
        st.cache_data.clear()
        definir_aviso("success", f"✅ {len(selecionados)} bairro(s)/região(ões) liberado(s) para pedidos automáticos. O site público já usa a nova lista.")

# Carrega os dados atuais
config_atual = carregar_configuracoes()

if not config_atual:
    st.warning("Tabela de configurações não encontrada no banco de dados. Execute o script SQL no Neon primeiro.")
    st.stop()

# Popula o banco com a lista inicial na primeira execução
if not isinstance(config_atual.get("bairros_cadastrados"), list):
    salvos = config_atual.get("bairros_permitidos") if isinstance(config_atual.get("bairros_permitidos"), list) else []
    lista_inicial = ordenar_bairros(BAIRROS_PADRAO_DF + salvos)
    if salvar_configuracoes({"bairros_cadastrados": lista_inicial}):
        config_atual["bairros_cadastrados"] = lista_inicial
        if not isinstance(config_atual.get("bairros_permitidos"), list):
            config_atual["bairros_permitidos"] = lista_inicial
    else:
        st.warning("Não foi possível salvar a lista de bairros. Execute o comando abaixo no SQL Editor do Neon e recarregue a página:")
        st.code(SQL_COLUNA_BAIRROS, language="sql")
        st.stop()

bairros_cadastrados = ordenar_bairros(config_atual.get("bairros_cadastrados") or [])

# Avisos pós-ação (cadastro/remoção)
if "_aviso_bairros" in st.session_state:
    tipo_aviso, msg_aviso = st.session_state.pop("_aviso_bairros")
    getattr(st, tipo_aviso)(msg_aviso)

# =====================================================
# BAIRROS ATENDIDOS NO DF: CADASTRO + LIBERAÇÃO (SALVO NO BANCO)
# =====================================================
bairros_salvos = config_atual.get("bairros_permitidos")
if not isinstance(bairros_salvos, list):
    bairros_salvos = bairros_cadastrados
if "bairros_liberados_sel" not in st.session_state:
    st.session_state["bairros_liberados_sel"] = [b for b in bairros_salvos if b in bairros_cadastrados]
else:
    st.session_state["bairros_liberados_sel"] = [b for b in st.session_state["bairros_liberados_sel"] if b in bairros_cadastrados]

with st.container(border=True):
    st.markdown('<div class="section-title">📍 Bairros Atendidos no Distrito Federal (DF)</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Escolha os bairros e Regiões Administrativas liberados para pedidos automáticos no site. Pedidos de bairros do DF fora dessa lista direcionam o cliente para verificar a entrega no WhatsApp. Pedidos de fora do DF são bloqueados. Esta área tem salvamento próprio (botões abaixo), independente do botão de salvar do restante da página.</div>', unsafe_allow_html=True)

    st.multiselect(
        "Bairros / Regiões liberados para pedidos diretos:",
        options=bairros_cadastrados,
        key="bairros_liberados_sel",
        help="Pesquise, adicione ou remova bairros da lista de liberados. Para incluir um bairro que não existe na lista, use o cadastro logo abaixo."
    )
    st.caption(f"📊 **{len(st.session_state['bairros_liberados_sel'])}** de **{len(bairros_cadastrados)}** bairros/regiões cadastrados estão liberados para pedidos automáticos.")
    st.button("💾 Salvar bairros liberados", key="btn_salvar_liberados", on_click=cb_salvar_liberados, type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("**➕ Cadastrar novo bairro / região**")
    ca1, ca2 = st.columns([3, 1.4])
    with ca1:
        st.text_input("Nome do bairro / região", key="novo_bairro_nome", placeholder="Ex: Jardim Mangueiral", label_visibility="collapsed")
    with ca2:
        st.button("➕ Cadastrar", key="btn_add_bairro", on_click=cb_adicionar_bairro, use_container_width=True)
    st.checkbox("Liberar para entrega imediatamente (já cadastra e salva como liberado)", value=True, key="novo_bairro_liberar")

    with st.expander(f"🗑️ Remover bairros do cadastro ({len(bairros_cadastrados)} cadastrados)"):
        st.multiselect("Bairros a remover:", options=bairros_cadastrados, key="bairros_para_remover")
        st.button("Remover selecionados", key="btn_rem_bairro", on_click=cb_remover_bairros)

# =====================================================
# FORMULÁRIO DE CONFIGURAÇÃO
# =====================================================
with st.form("form_config_loja"):
    
    # 1. BLOCO DE AGENDAMENTO E HORÁRIOS
    with st.container(border=True):
        st.markdown('<div class="section-title">📅 Regras de Agendamento e Horário Limite</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-desc">Defina com quantos dias de antecedência o cliente pode pedir e configure a trava do WhatsApp caso passe do horário de fechamento da cozinha.</div>', unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            dias_ant = st.number_input(
                "Dias de Antecedência (D+X)", 
                min_value=0, max_value=30, step=1, 
                value=int(config_atual.get("dias_antecedencia", 1)),
                help="Ex: '1' significa que o cliente só consegue encomendar para o dia seguinte."
            )
        
        with c2:
            hora_str = config_atual.get("hora_corte", "18:00:00")
            try:
                h, m, s = map(int, hora_str.split(':'))
                hora_obj = dtime(h, m)
            except:
                hora_obj = dtime(18, 0)
                
            hora_corte = st.time_input(
                "⏰ Horário Limite (Corte)", 
                value=hora_obj,
                help="Até que horas o cliente pode fazer o pedido para a data mínima definida acima?"
            )

        st.write("")
        bloqueio_ativo = st.checkbox(
            "💬 Exibir Alerta do WhatsApp caso passe do horário limite?", 
            value=bool(config_atual.get("bloquear_apos_corte", True)),
            help="Se marcado, a loja vai travar a compra de quem pedir tarde da noite e mostrar o alerta pedindo para confirmar a disponibilidade da produção via WhatsApp."
        )

    # 2. BLOCO DE FRETE E LOGÍSTICA
    with st.container(border=True):
        st.markdown('<div class="section-title">🛵 Regras de Frete Dinâmico (Delivery)</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-desc">Configure os valores para o cálculo automático de frete baseado na distância entre a loja e o CEP do cliente.</div>', unsafe_allow_html=True)
        
        c3, c4 = st.columns([1.5, 2.5])
        with c3:
            cep_loja = st.text_input(
                "CEP Base da Loja", 
                value=config_atual.get("cep_origem", "71680377"),
                max_chars=8,
                help="Usado como ponto de origem para calcular a quilometragem até o cliente."
            )
        
        c5, c6 = st.columns(2)
        with c5:
            valor_km = st.number_input(
                "Valor cobrado por KM (R$)", 
                min_value=0.0, step=0.50, format="%.2f",
                value=float(config_atual.get("valor_km", 1.00))
            )
        with c6:
            taxa_fixa = st.number_input(
                "Taxa Fixa Adicional (R$)", 
                min_value=0.0, step=1.00, format="%.2f",
                value=float(config_atual.get("taxa_fixa", 3.00)),
                help="Ex: Taxa fixa de R$ 3,00 + (KM x R$ 1,00)."
            )

    # 3. BLOCO DE CONTATO
    with st.container(border=True):
        st.markdown('<div class="section-title">📱 Contato e Atendimento</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-desc">E-mail e WhatsApp oficiais da loja para onde os links e alertas da vitrine serão direcionados.</div>', unsafe_allow_html=True)
        
        c7, c8 = st.columns(2)
        with c7:
            whatsapp_loja = st.text_input(
                "WhatsApp da Loja (com DDD)", 
                value=config_atual.get("whatsapp_loja", "61999759079"),
                help="Apenas números. Ex: 61999999999"
            )
        with c8:
            email_loja = st.text_input(
                "E-mail Oficial", 
                value=config_atual.get("email_loja", "contato@docecestabrasilia.com.br")
            )

    # 4. BLOCO DA ÁREA CORPORATIVA
    with st.container(border=True):
        st.markdown('<div class="section-title">🏢 Área Corporativa</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-desc">Ative ou desative a faixa de divulgação e o acesso à área corporativa na página pública (app.py). Útil para colocar em manutenção sem precisar mexer no código.</div>', unsafe_allow_html=True)

        corporativo_ativo = st.checkbox(
            "🏢 Exibir a área Corporativa na loja pública?",
            value=bool(config_atual.get("corporativo_ativo", True)),
            help="Se desmarcado, a faixa 'Sua empresa também merece uma cesta especial' some da página inicial e o acesso à área corporativa fica indisponível."
        )

    st.write("")
    if st.form_submit_button("💾 Salvar Configurações da Loja", type="primary", use_container_width=True):
        cep_limpo = re.sub(r'\D', '', cep_loja)
        whatsapp_limpo = re.sub(r'\D', '', whatsapp_loja)
        
        if len(cep_limpo) != 8:
            st.error("O CEP da loja deve conter exatamente 8 números.")
        else:
            dados_update = {
                "dias_antecedencia": dias_ant,
                "bloquear_apos_corte": bloqueio_ativo,
                "hora_corte": hora_corte.strftime("%H:%M:%S"),
                "cep_origem": cep_limpo,
                "valor_km": valor_km,
                "taxa_fixa": taxa_fixa,
                "whatsapp_loja": whatsapp_limpo,
                "email_loja": email_loja.strip(),
                "corporativo_ativo": corporativo_ativo,
                "updated_at": "now()"
            }
            
            with st.spinner("Salvando as novas regras..."):
                if salvar_configuracoes(dados_update):
                    st.cache_data.clear()
                    st.success("✅ Configurações atualizadas com sucesso! O site público já está usando as novas regras.")
