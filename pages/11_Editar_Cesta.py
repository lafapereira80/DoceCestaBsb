import streamlit as st
import time
from config.db import supabase
from services.cesta_service import buscar_cesta_por_id, atualizar_cesta, upload_imagem_cesta, listar_cestas
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Editar Cesta", page_icon="✏️", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

# =====================================================
# CSS PREMIUM E ANIMAÇÕES
# =====================================================
st.markdown(
"""
<style>
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 900px; }
h1 { font-size: 28px !important; font-weight: 800 !important; color: #4a2e1b; margin-bottom: 2px !important; }
div[data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff; border: 1px solid #e8ddd3 !important; border-radius: 16px !important; padding: 24px !important; box-shadow: 0 4px 15px rgba(90, 59, 40, 0.05); }
.stButton button { font-size: 15px !important; font-weight: 800 !important; border-radius: 12px !important; height: 48px !important; }
.stButton button[kind="primary"] { background: linear-gradient(135deg, #137333 0%, #0d4e22 100%) !important; color: white !important; border: none !important; }
.stButton button[kind="secondary"] { background: #faf7f3 !important; border: 1px solid #dfcdbb !important; color: #5a3b28 !important; }

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 18px !important; }
}

/* =========================================
   RESPONSIVIDADE — CELULAR (≤ 640px)
========================================== */
@media (max-width: 640px) {
    .block-container { padding-left: .8rem !important; padding-right: .8rem !important; padding-top: 1rem !important; }
    h1 { font-size: 22px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px !important; border-radius: 14px !important; }
    .stButton button { height: 44px !important; font-size: 13.5px !important; }
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# VALIDAÇÃO DE ESTADO
# =====================================================
cesta_id = st.session_state.get("cesta_editar")

if not cesta_id:
    st.warning("⚠️ Nenhuma cesta selecionada para edição.")
    if st.button("⬅️ Voltar para Cestas", use_container_width=True):
        st.switch_page("pages/04_Cestas.py")
    st.stop()

# =====================================================
# CACHE DINÂMICO PARA SEÇÕES DA VITRINE
# =====================================================
@st.cache_data(ttl=120, show_spinner=False)
def obter_secoes_oficiais():
    try:
        res = supabase.table("vitrine_secoes").select("nome").order("ordem").execute()
        secoes = [s["nome"] for s in (res.data or [])]
        return secoes if secoes else ["Cestas de Café"]
    except:
        return ["Cestas de Café"]

# =====================================================
# CARREGAR DADOS DA CESTA
# =====================================================
cesta_atual = buscar_cesta_por_id(cesta_id)

if not cesta_atual:
    st.error("Cesta não encontrada no banco de dados.")
    if st.button("⬅️ Voltar", use_container_width=True):
        st.switch_page("pages/04_Cestas.py")
    st.stop()

page_header("Editar cesta", "Nome, descrição, preço, promoção e fotos.", "✏️", ["Catálogo", "Cestas", "Editar"])
st.caption(f"Atualizando os dados do item: **{cesta_atual['nome']}**")
st.write("")

# =====================================================
# FORMULÁRIO DE EDIÇÃO (BLINDADO COM SEÇÕES DINÂMICAS)
# =====================================================
lista_secoes = obter_secoes_oficiais()

secao_atual = cesta_atual.get("secao_vitrine", "Cestas de Café")
if secao_atual not in lista_secoes:
    lista_secoes.insert(0, secao_atual) # Garante que a seção atual apareça, mesmo se foi desativada

with st.container(border=True):
    col1, col2 = st.columns([1.5, 1], gap="large")

    with col1:
        novo_nome = st.text_input("Nome da Opção", value=cesta_atual.get("nome", ""))
        
        # Selectbox blindado
        nova_secao = st.selectbox("Seção na Vitrine", lista_secoes, index=lista_secoes.index(secao_atual))
        
        nova_descricao = st.text_area("Descrição (Itens principais)", value=cesta_atual.get("descricao", ""), height=130)
        total_cestas = len(listar_cestas()) or 1
        nova_ordem = st.number_input(
            "Ordem de Exibição", value=min(int(cesta_atual.get("ordem", 1)), total_cestas),
            min_value=1, max_value=total_cestas, step=1,
            help=f"Posição na vitrine (1 a {total_cestas}). As outras cestas se reajustam automaticamente."
        )

    with col2:
        nova_ativa = st.toggle("Item Ativo na Vitrine?", value=cesta_atual.get("ativa", True))
        preco_atual = cesta_atual.get("preco")
        novo_preco = st.number_input("Preço (R$)", value=float(preco_atual) if preco_atual is not None else 0.0, min_value=0.0, step=1.0, format="%.2f")
        nova_sem_preco = st.checkbox("💬 Preço sob consulta (não definido)", value=preco_atual is None, help="Marque se essa cesta ainda não tem preço fechado. A vitrine mostrará 'Sob consulta' em vez de R$ 0,00.")
        novo_dias_producao = st.number_input(
            "⏱️ Tempo Mínimo de Produção (dias)", min_value=0, max_value=90, step=1,
            value=int(cesta_atual.get("dias_producao") or 0),
            help="Quantos dias de antecedência, no mínimo, esta cesta exige entre o pedido e a entrega. Deixe 0 para usar o prazo padrão da loja (definido em Configurações da Loja)."
        )
        
        st.write("")
        if cesta_atual.get("imagem"):
            st.markdown("<div style='font-size: 13px; font-weight: 800; color: #5a3b28; margin-bottom: 8px;'>📷 Foto Atual</div>", unsafe_allow_html=True)
            st.image(cesta_atual["imagem"], width=150)
            
        nova_imagem = st.file_uploader("Substituir Foto (Opcional)", type=["jpg", "jpeg", "png", "webp"])

# =====================================================
# AÇÕES: SALVAR OU CANCELAR
# =====================================================
st.write("")
col_b1, col_b2 = st.columns(2)

with col_b1:
    if st.button("❌ Cancelar", use_container_width=True):
        st.switch_page("pages/04_Cestas.py")

with col_b2:
    if st.button("💾 Salvar Alterações", use_container_width=True, type="primary"):
        if not novo_nome.strip():
            st.error("O nome é obrigatório.")
        else:
            with st.spinner("Atualizando dados..."):
                try:
                    imagem_url = cesta_atual.get("imagem")
                    if nova_imagem:
                        imagem_url = upload_imagem_cesta(nova_imagem)

                    dados_atualizados = {
                        "nome": novo_nome.strip(),
                        "descricao": nova_descricao.strip(),
                        "preco": None if nova_sem_preco else novo_preco,
                        "ativa": nova_ativa,
                        "dias_producao": int(novo_dias_producao),
                        "ordem": int(nova_ordem),
                        "secao_vitrine": nova_secao,
                        "imagem": imagem_url
                    }

                    sucesso = atualizar_cesta(cesta_id, dados_atualizados)
                except Exception as erro:
                    sucesso = False
                    st.error(f"Erro ao atualizar a cesta: {erro}")
                    st.stop()

                if sucesso:
                    st.success("✅ Cesta atualizada com sucesso!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.switch_page("pages/04_Cestas.py")
                else:
                    st.error("Erro ao atualizar a cesta no banco de dados.")
