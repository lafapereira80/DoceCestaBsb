import streamlit as st
import html
from config.db import supabase

from utils.ui import page_header
from utils.menu import (
    configurar_pagina,
    menu_lateral
)

from utils.permissao import (
    administrador_operador
)

# =====================================================
# FUNÇÕES DE BANCO DE DADOS (INCORPORADAS DIRETAMENTE)
# =====================================================
def listar_categorias():
    resposta = supabase.table("categorias").select("*").order("ordem").execute()
    return resposta.data or []

def cadastrar_categoria(nome, possui_preco, exibir_no_pedido, ativo, ordem):
    dados = {
        "nome": nome,
        "possui_preco": possui_preco,
        "exibir_no_pedido": exibir_no_pedido,
        "ativo": ativo,
        "ordem": ordem
    }
    supabase.table("categorias").insert(dados).execute()

def atualizar_categoria(cat_id, nome, possui_preco, exibir_no_pedido, ativo, ordem):
    dados = {
        "nome": nome,
        "possui_preco": possui_preco,
        "exibir_no_pedido": exibir_no_pedido,
        "ativo": ativo,
        "ordem": ordem
    }
    supabase.table("categorias").update(dados).eq("id", cat_id).execute()

def alterar_status_categoria(cat_id, ativo):
    supabase.table("categorias").update({"ativo": ativo}).eq("id", cat_id).execute()

def excluir_categoria(cat_id):
    try:
        supabase.table("categorias").delete().eq("id", cat_id).execute()
        return True
    except Exception as e:
        print(f"Erro ao excluir categoria: {e}")
        return False


# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================

st.set_page_config(
    page_title="Gestão de Categorias",
    page_icon="📂",
    layout="wide"
)

configurar_pagina()
menu_lateral()
administrador_operador()


# =====================================================
# CONTROLE DE EDIÇÃO
# =====================================================

if "categoria_editando" not in st.session_state:
    st.session_state["categoria_editando"] = None
if "categoria_confirmar_exclusao" not in st.session_state:
    st.session_state["categoria_confirmar_exclusao"] = None


# =====================================================
# CSS PREMIUM E RESPONSIVIDADE MOBILE
# =====================================================

st.markdown(
"""
<style>
/* =========================================
   CONFIGURAÇÃO GERAL E ESPAÇAMENTOS
========================================== */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1150px;
}

h1 {
    font-size: 28px !important;
    font-weight: 800 !important;
    color: #4a2e1b;
    margin-bottom: 2px !important;
    letter-spacing: -0.5px;
}

.block-container p, 
.block-container label {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    font-size: 13px !important;
}

/* =========================================
   ACORDEÃO (EXPANDER) "NOVA CATEGORIA"
========================================== */
div[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #e8ddd3 !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 15px rgba(90, 59, 40, 0.05) !important;
    overflow: hidden;
    margin-bottom: 25px;
}
div[data-testid="stExpander"] summary {
    background: #faf7f3;
    padding: 15px 20px !important;
    font-size: 16px !important;
    font-weight: 800 !important;
    color: #5a3b28 !important;
    transition: all 0.3s ease;
}
div[data-testid="stExpander"] summary:hover {
    background: #f3ece6;
}
div[data-testid="stExpanderDetails"] {
    padding: 20px !important;
}

/* =========================================
   CARDS DE CATEGORIA
========================================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff;
    border: 1px solid #e8ddd3 !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    margin-bottom: 10px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #d2bfae !important;
    box-shadow: 0 8px 20px rgba(90, 59, 40, 0.08);
    transform: translateY(-2px);
}

/* Alinhamento vertical Desktop */
@media (min-width: 641px) {
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }
}

/* =========================================
   ELEMENTOS DE TEXTO & BADGES
========================================== */
.categoria-nome {
    font-weight: 800;
    color: #2c1e14;
    font-size: 16px !important;
    margin-bottom: 2px;
}

.badge-ativa, .badge-inativa {
    display: inline-block;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-ativa { background-color: #e6f4ea; color: #137333; border: 1px solid #ceead6; }
.badge-inativa { background-color: #fce8e6; color: #c5221f; border: 1px solid #fad2cf; }

.badge-info {
    display: inline-block;
    background-color: #faf7f3;
    color: #5a3b28;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 8px;
    font-size: 11px !important;
    border: 1px solid #e8ddd3;
    margin-right: 4px;
    margin-bottom: 4px;
}

/* =========================================
   BOTÕES DE AÇÃO NA TABELA
========================================== */
div[data-testid="stColumn"] div[data-testid="stButton"] button {
    font-size: 15px !important;
    padding: 4px 6px !important;
    border-radius: 10px !important;
    min-height: 38px !important;
    border: 1px solid #e8ddd3 !important;
    background: #faf7f3 !important;
    transition: all 0.2s ease;
}
div[data-testid="stColumn"] div[data-testid="stButton"] button:hover {
    background: #e8ddd3 !important;
    transform: scale(1.05);
}

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}

/* =========================================
   RESPONSIVIDADE MOBILE E BOTÕES (LADO A LADO)
========================================== */
@media (max-width: 768px) {
    h1 { font-size: 24px !important; }
    
    /* Força os botões a ficarem na horizontal no mobile dividindo o espaço igualmente */
    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
        margin-top: 10px !important;
        justify-content: space-between;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) > div[data-testid="stColumn"] {
        flex: 1 1 0% !important; /* Faz os botões dividirem o espaço 50/50 ou 33/33/33 dependendo de quantos existam */
        min-width: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) button {
        width: 100% !important;
        padding: 6px 0px !important;
    }
}
</style>
""",
unsafe_allow_html=True
)


# =====================================================
# TÍTULO E CABEÇALHO
# =====================================================

col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    page_header("Categorias", "Organize os produtos do catálogo.", "🏷️", ["Catálogo", "Categorias"])
    st.caption("Organize as seções do seu catálogo para facilitar a navegação e configuração de preços.")


# =====================================================
# NOVA CATEGORIA (MODELO EXPANDER)
# =====================================================

with st.expander("✨ Cadastrar Nova Categoria", expanded=False):
    col_n1, col_n2 = st.columns([1.5, 1])

    with col_n1:
        nome_categoria = st.text_input("Nome da Categoria", placeholder="Ex: Bebidas Quentes, Adicionais, Cestas...")

    with col_n2:
        ordem = st.number_input("Ordem de Exibição", min_value=0, value=0, step=1, help="Define a posição em que a categoria aparece nas listagens.")

    st.write("")
    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #5a3b28; margin-bottom: 5px;'>Configurações de Regra:</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        possui_preco = st.checkbox("💸 Possui preço individual", help="Marque se os produtos desta categoria são cobrados à parte (como adicionais).")
    with c2:
        exibir_no_pedido = st.checkbox("📋 Exibir no Fechamento", help="Marque se esta categoria deve aparecer na seleção de produtos ao montar um pedido.")
    with c3:
        ativo = st.checkbox("🟢 Categoria Ativa", value=True)

    st.write("")
    if st.button("💾 Adicionar Categoria", use_container_width=True, type="primary"):
        if not nome_categoria.strip():
            st.error("Informe o nome da categoria.")
        else:
            try:
                cadastrar_categoria(
                    nome_categoria.strip(),
                    possui_preco,
                    exibir_no_pedido,
                    ativo,
                    ordem
                )
                st.success("✅ Categoria cadastrada com sucesso!")
                st.cache_data.clear()
                st.rerun()
            except Exception as erro:
                st.error(f"Erro ao cadastrar: {erro}")


# =====================================================
# LISTAGEM DE CATEGORIAS (CARDS PREMIUM)
# =====================================================

st.write("")
st.subheader("📋 Categorias Cadastradas")

try:
    categorias = listar_categorias()
except Exception as erro:
    st.error(f"Erro ao carregar categorias: {erro}")
    st.stop()

if not categorias:
    st.info("Nenhuma categoria cadastrada. Utilize o botão acima para criar a primeira.")
    st.stop()


# Loop das Categorias
for categoria in categorias:
    categoria_id = categoria["id"]
    nome = categoria.get("nome", "")
    ativo = categoria.get("ativo", False)
    possui_preco = categoria.get("possui_preco", False)
    exibir_pedido = categoria.get("exibir_no_pedido", False)
    ordem_atual = categoria.get("ordem", 0)

    with st.container(border=True):
        # Separação clara de colunas
        col_nome, col_status, col_tags, col_acoes = st.columns([2.5, 1.2, 3.5, 1.8])

        # Coluna 1: Nome
        with col_nome:
            st.markdown(f'<div class="categoria-nome">📁 {html.escape(str(nome))}</div>', unsafe_allow_html=True)

        # Coluna 2: Status
        with col_status:
            if ativo:
                st.markdown('<span class="badge-ativa">Ativa</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge-inativa">Inativa</span>', unsafe_allow_html=True)

        # Coluna 3: Tags Informativas
        with col_tags:
            st.markdown(
                f"""
                <div style="margin-top: 2px;">
                    <span class="badge-info">💸 Preço: {'Sim' if possui_preco else 'Não'}</span>
                    <span class="badge-info">📋 Pedido: {'Sim' if exibir_pedido else 'Não'}</span>
                    <span class="badge-info">🔢 Posição: {ordem_atual}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Coluna 4: Ações (Botões em linha)
        with col_acoes:
            col_b1, col_b2, col_b3 = st.columns(3)

            with col_b1:
                texto_botao = "🔴" if ativo else "🟢"
                if st.button(texto_botao, key=f"status_{categoria_id}", help="Ativar/Desativar Categoria", use_container_width=True):
                    try:
                        alterar_status_categoria(categoria_id, not ativo)
                        st.toast("✅ Status alterado com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as erro:
                        st.error(f"Erro ao alterar status: {erro}")

            with col_b2:
                if st.button("✏️", key=f"editar_{categoria_id}", help="Editar Categoria", use_container_width=True):
                    st.session_state["categoria_editando"] = categoria_id
                    st.rerun()

            with col_b3:
                if st.button("🗑️", key=f"excluir_{categoria_id}", help="Excluir Categoria", use_container_width=True):
                    st.session_state["categoria_confirmar_exclusao"] = categoria_id
                    st.rerun()

        # =====================================================
        # FORMULÁRIO DE EDIÇÃO INLINE (DENTRO DO CARD)
        # =====================================================
        if st.session_state["categoria_editando"] == categoria_id:
            st.write("")
            with st.container(border=True):
                st.markdown("<div style='font-size: 14px; font-weight: 800; color: #5a3b28; margin-bottom: 10px;'>✏️ Editando Categoria</div>", unsafe_allow_html=True)

                with st.form(key=f"form_edicao_{categoria_id}"):
                    col_e1, col_e2 = st.columns([1.5, 1])

                    with col_e1:
                        novo_nome = st.text_input("Nome da Categoria", value=nome)

                    with col_e2:
                        nova_ordem = st.number_input("Posição / Ordem", min_value=0, value=int(ordem_atual), step=1, key=f"ordem_edit_{categoria_id}")

                    st.write("")
                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        novo_preco = st.checkbox("Possui preço individual", value=possui_preco, key=f"preco_edit_{categoria_id}")
                    with col_c2:
                        novo_exibir = st.checkbox("Exibir no fechamento", value=exibir_pedido, key=f"pedido_edit_{categoria_id}")
                    with col_c3:
                        novo_ativo = st.checkbox("Categoria ativa", value=ativo, key=f"ativo_edit_{categoria_id}")

                    st.write("")
                    col_salvar, col_cancelar = st.columns(2)

                    with col_salvar:
                        salvar = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)

                    with col_cancelar:
                        cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    if salvar:
                        if not novo_nome.strip():
                            st.error("Informe o nome da categoria.")
                        else:
                            try:
                                atualizar_categoria(
                                    categoria_id,
                                    novo_nome.strip(),
                                    novo_preco,
                                    novo_exibir,
                                    novo_ativo,
                                    nova_ordem
                                )
                                st.session_state["categoria_editando"] = None
                                st.success("✅ Categoria atualizada!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as erro:
                                st.error(f"Erro ao atualizar: {erro}")

                    if cancelar:
                        st.session_state["categoria_editando"] = None
                        st.rerun()

        # =====================================================
        # CONFIRMAÇÃO DE EXCLUSÃO
        # =====================================================
        if st.session_state.get("categoria_confirmar_exclusao") == categoria_id:
            st.error(f"⚠️ Atenção! Deseja realmente excluir a categoria **{nome}**?")
            col_confirmar, col_cancelar = st.columns(2)

            with col_confirmar:
                if st.button("✅ Sim, Excluir", key=f"confirmar_excluir_{categoria_id}", use_container_width=True, type="primary"):
                    try:
                        resultado = excluir_categoria(categoria_id)
                        if resultado is False:
                            st.error("❌ Não foi possível excluir a categoria.")
                        else:
                            st.toast("✅ Categoria excluída com sucesso!")
                            st.session_state["categoria_editando"] = None
                            st.session_state["categoria_confirmar_exclusao"] = None
                            st.cache_data.clear()
                            st.rerun()
                    except Exception as erro:
                        st.error(f"Erro ao excluir: {erro}")

            with col_cancelar:
                if st.button("❌ Cancelar", key=f"cancelar_excluir_{categoria_id}", use_container_width=True):
                    st.session_state["categoria_confirmar_exclusao"] = None
                    st.rerun()


# =====================================================
# RODAPÉ
# =====================================================

st.write("")
st.divider()
st.caption("📂 Gerenciamento Oficial de Categorias - Doce Cesta Brasília")
