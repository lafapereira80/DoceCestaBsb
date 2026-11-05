import streamlit as st
import pandas as pd

from config.db import supabase
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador
from utils.formatacao import formatar_moeda # <-- Central de Formatação

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Painel Financeiro", page_icon="💰", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

usuario = st.session_state.get("usuario", {})

# =====================================================
# CSS PREMIUM E ANIMAÇÕES
# =====================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1200px; }
div[data-testid="stVerticalBlock"] { gap: 0.8rem !important; }

h1 { font-size: 28px !important; font-weight: 800 !important; color: #4a2e1b !important; margin-bottom: 2px !important; letter-spacing: -0.5px; }
h2, h3, h4 { font-size: 16px !important; font-weight: 800 !important; color: #5a3b28 !important; margin-top: 10px !important; margin-bottom: 8px !important; }

.metric-card { background: linear-gradient(145deg, #ffffff 0%, #fdfcfb 100%); border: 1px solid #e8ddd3; border-radius: 16px; padding: 22px 16px; text-align: center; box-shadow: 0 4px 15px rgba(90, 59, 40, 0.03); transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); margin-bottom: 10px; }
.metric-card:hover { border-color: #c5721f; box-shadow: 0 8px 25px rgba(197, 114, 31, 0.08); transform: translateY(-3px); }
.kpi-title { font-size: 12px !important; font-weight: 800; color: #775a46; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
.kpi-value { font-size: 26px !important; font-weight: 800; color: #137333; }
.kpi-value-neutral { font-size: 26px !important; font-weight: 800; color: #4a2e1b; }

div[data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff; border: 1px solid #e8ddd3 !important; border-radius: 16px !important; padding: 20px 24px !important; margin-bottom: 12px !important; box-shadow: 0 4px 15px rgba(90, 59, 40, 0.02); }
div[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: #d2bfae !important; box-shadow: 0 8px 20px rgba(90, 59, 40, 0.06); }
div[data-testid="stDataFrame"] { border: 1px solid #e8ddd3 !important; border-radius: 10px !important; overflow: hidden !important; }

@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}

@media (max-width: 768px) {
    .block-container { padding-top: 1rem !important; padding-left: .8rem !important; padding-right: .8rem !important; }
    h1 { font-size: 22px !important; }
    .metric-card { padding: 14px 10px; }
    .kpi-title { font-size: 10.5px !important; }
    .kpi-value, .kpi-value-neutral { font-size: 19px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px 16px !important; }
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# TÍTULO E CABEÇALHO
# =====================================================
page_header("Painel financeiro", "Faturamento, fretes, descontos e ticket médio.", "💰", ["Gestão", "Financeiro"], "ok")
st.caption("Acompanhe o faturamento, volume de vendas e desempenho do negócio de forma analítica.")

# =====================================================
# CARREGAR DADOS COM MAX PERFORMANCE (IGNORA TEXTOS GRANDES)
# =====================================================
@st.cache_data(ttl=60)
def carregar_pedidos_financeiros():
    # A mágica do Payload Leve: Retorna apenas ID, Datas e Valores (Ignora Endereços e Bilhetes)
    resposta = supabase.table("pedidos").select("id, created_at, valor_total, valor_frete, desconto, status, cesta_nome, cliente_nome, cliente_telefone").execute()
    return resposta.data or []

@st.cache_data(ttl=60)
def carregar_adicionais():
    resposta = supabase.table("pedido_adicionais").select("pedido_id, nome_produto, quantidade, valor_unitario").execute()
    return resposta.data or []

try:
    pedidos = carregar_pedidos_financeiros()
    adicionais = carregar_adicionais()
except Exception as erro:
    st.error(f"Erro ao carregar dados financeiros: {erro}")
    st.stop()

if not pedidos:
    st.warning("Ainda não há dados financeiros suficientes para gerar o relatório.")
    st.stop()

df = pd.DataFrame(pedidos)
df_adicionais = pd.DataFrame(adicionais)

# =====================================================
# TRATAMENTO DOS DADOS E FILTRAGEM DE STATUS
# =====================================================
if "created_at" in df.columns:
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
else:
    df["created_at"] = pd.Timestamp.now()

df["valor_total"] = pd.to_numeric(df.get("valor_total", 0), errors="coerce").fillna(0)
df["valor_frete"] = pd.to_numeric(df.get("valor_frete", 0), errors="coerce").fillna(0)
df["desconto"] = pd.to_numeric(df.get("desconto", 0), errors="coerce").fillna(0)

if "status" in df.columns:
    df["status"] = df["status"].fillna("Desconhecido").astype(str).str.strip().str.capitalize()
else:
    df["status"] = "Desconhecido"

status_excluir = ["Recebido", "Desistência", "Desistencia"]
df = df[~df["status"].isin(status_excluir)]

if df.empty:
    st.info("📊 Não há faturamento confirmado no momento. Todos os pedidos atuais estão aguardando pagamento ou foram cancelados.")
    st.stop()

df["ano"] = df["created_at"].dt.year
df["mes"] = df["created_at"].dt.month

meses_dict = {
    1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril",
    5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto",
    9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"
}

# =====================================================
# FILTROS DINÂMICOS
# =====================================================
with st.container(border=True):
    st.markdown("<div style='font-size: 14px; font-weight: 800; color: #5a3b28; margin-bottom: 8px;'>🔍 Filtros de Período</div>", unsafe_allow_html=True)
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        anos = sorted(df["ano"].dropna().astype(int).unique(), reverse=True)
        ano_selecionado = st.selectbox("Ano de Apuração", ["Todos"] + list(anos))

    with col_f2:
        if ano_selecionado != "Todos":
            meses_disponiveis_nums = sorted(df[df["ano"] == ano_selecionado]["mes"].dropna().unique())
        else:
            meses_disponiveis_nums = sorted(df["mes"].dropna().unique())
            
        meses_disponiveis_nomes = [meses_dict[m] for m in meses_disponiveis_nums if m in meses_dict]
        mes_selecionado = st.selectbox("Mês Específico", ["Todos"] + meses_disponiveis_nomes)

# Aplica Filtros
df_filtrado = df.copy()
if ano_selecionado != "Todos": df_filtrado = df_filtrado[df_filtrado["ano"] == ano_selecionado]
if mes_selecionado != "Todos":
    numero_mes = [chave for chave, valor in meses_dict.items() if valor == mes_selecionado][0]
    df_filtrado = df_filtrado[df_filtrado["mes"] == numero_mes]

# =====================================================
# RESUMO FINANCEIRO (KPIs PREMIUM)
# =====================================================
st.write("")
col1, col2, col3, col4 = st.columns(4)

faturamento = df_filtrado["valor_total"].sum()
total_fretes = df_filtrado["valor_frete"].sum()
quantidade_pedidos = len(df_filtrado)
ticket_medio = faturamento / quantidade_pedidos if quantidade_pedidos > 0 else 0

with col1:
    st.markdown(f'<div class="metric-card"><div class="kpi-title">💰 Faturamento</div><div class="kpi-value">R$ {formatar_moeda(faturamento)}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="kpi-title">🚚 Total de Fretes</div><div class="kpi-value-neutral">R$ {formatar_moeda(total_fretes)}</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="kpi-title">📋 Pedidos Concluídos</div><div class="kpi-value-neutral">{quantidade_pedidos}</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div class="kpi-title">🎯 Ticket Médio</div><div class="kpi-value-neutral">R$ {formatar_moeda(ticket_medio)}</div></div>', unsafe_allow_html=True)

st.write("")

# =====================================================
# BLOCO DE VISÃO GERAL (SIDES BY SIDE)
# =====================================================
col_left, col_right = st.columns(2)

with col_left:
    with st.container(border=True):
        st.markdown("#### 📅 Desempenho Mensal")
        if not df_filtrado.empty:
            faturamento_mes = df_filtrado.groupby(df_filtrado["created_at"].dt.strftime("%m/%Y"))["valor_total"].sum().reset_index()
            faturamento_mes.columns = ["Mês/Ano", "Faturamento"]
            faturamento_mes["Faturamento"] = faturamento_mes["Faturamento"].apply(lambda x: f"R$ {formatar_moeda(x)}")
            st.dataframe(faturamento_mes, use_container_width=True, hide_index=True, height=180)
        else: st.info("Nenhum dado para o período.")

    with st.container(border=True):
        st.markdown("#### 📌 Faturamento por Status")
        if "status" in df_filtrado.columns and not df_filtrado.empty:
            resumo_status = df_filtrado.groupby("status").agg(Quantidade=("id", "count"), Valor=("valor_total", "sum")).reset_index()
            resumo_status.columns = ["Status", "Pedidos", "Valor Arrecadado"]
            resumo_status["Valor Arrecadado"] = resumo_status["Valor Arrecadado"].apply(lambda x: f"R$ {formatar_moeda(x)}")
            st.dataframe(resumo_status, use_container_width=True, hide_index=True, height=160)

with col_right:
    with st.container(border=True):
        st.markdown("#### 🧺 Ranking de Opções")
        if "cesta_nome" in df_filtrado.columns and not df_filtrado.empty:
            cestas = df_filtrado.groupby("cesta_nome").size().reset_index(name="Volume de Vendas").sort_values("Volume de Vendas", ascending=False)
            cestas.columns = ["Nome do Pacote / Cesta", "Volume de Vendas"]
            st.dataframe(cestas, use_container_width=True, hide_index=True, height=180)
        else: st.info("Nenhuma venda encontrada no período.")

    with st.container(border=True):
        st.markdown("#### 🎀 Extras e Adicionais")
        if not df_adicionais.empty and not df_filtrado.empty:
            pedidos_filtrados_ids = df_filtrado["id"].tolist()
            adicionais_filtrados = df_adicionais[df_adicionais["pedido_id"].isin(pedidos_filtrados_ids)].copy()

            if not adicionais_filtrados.empty:
                adicionais_filtrados["quantidade"] = pd.to_numeric(adicionais_filtrados["quantidade"], errors="coerce").fillna(1)
                adicionais_filtrados["valor_unitario"] = pd.to_numeric(adicionais_filtrados["valor_unitario"], errors="coerce").fillna(0)
                adicionais_filtrados["total"] = adicionais_filtrados["quantidade"] * adicionais_filtrados["valor_unitario"]

                resumo_adicionais = adicionais_filtrados.groupby("nome_produto").agg(Quantidade=("quantidade", "sum"), Faturamento=("total", "sum")).reset_index()
                resumo_adicionais.columns = ["Adicional", "Vendas", "Receita Gerada"]
                resumo_adicionais["Receita Gerada"] = resumo_adicionais["Receita Gerada"].apply(lambda x: f"R$ {formatar_moeda(x)}")
                resumo_adicionais = resumo_adicionais.sort_values("Vendas", ascending=False)

                st.dataframe(resumo_adicionais, use_container_width=True, hide_index=True, height=160)
            else: st.info("Nenhum item extra faturado neste período.")
        else: st.info("Nenhum item extra faturado neste período.")

# =====================================================
# DETALHAMENTO FINANCEIRO COMPACTO
# =====================================================
st.write("")
with st.container(border=True):
    st.markdown("#### 📋 Detalhamento de Transações")

    colunas_detalhamento = ["created_at", "cliente_nome", "cliente_telefone", "cesta_nome", "status", "valor_frete", "desconto", "valor_total"]
    colunas_existentes = [coluna for coluna in colunas_detalhamento if coluna in df_filtrado.columns]

    detalhamento = df_filtrado[colunas_existentes].sort_values("created_at", ascending=False).copy()

    if "created_at" in detalhamento.columns:
        detalhamento["created_at"] = detalhamento["created_at"].dt.strftime("%d/%m/%Y %H:%M")

    for coluna in ["valor_frete", "desconto", "valor_total"]:
        if coluna in detalhamento.columns:
            detalhamento[coluna] = detalhamento[coluna].apply(lambda x: f"R$ {formatar_moeda(x)}")

    detalhamento = detalhamento.rename(columns={"created_at": "Data/Hora", "cliente_nome": "Cliente", "cliente_telefone": "Contato", "cesta_nome": "Pacote", "status": "Status", "valor_frete": "Frete", "desconto": "Desconto", "valor_total": "Total Gasto"})
    st.dataframe(detalhamento, use_container_width=True, hide_index=True, height=300)

st.write("")
st.divider()

if not df_filtrado.empty:
    pedidos_sem_valor = df_filtrado[df_filtrado["valor_total"] <= 0]
    if not pedidos_sem_valor.empty:
        st.warning(f"⚠️ Atenção para auditoria: Existem **{len(pedidos_sem_valor)} pedido(s)** contabilizados sem valor total definido (R$ 0,00).")

st.caption("📊 Relatórios Financeiros Oficiais da Loja")
