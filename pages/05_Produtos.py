import streamlit as st
import html

from services.produto_service import (
    listar_produtos,
    cadastrar_produto,
    excluir_produto,
    listar_categorias,
    alterar_status_produto,
    upload_imagem_produto
)

from utils.ui import page_header
from utils.menu import (
    configurar_pagina,
    menu_lateral
)

from utils.permissao import (
    administrador_operador
)


# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================

st.set_page_config(
    page_title="Gestão de Produtos",
    page_icon="🛒",
    layout="wide"
)

configurar_pagina()
menu_lateral()
administrador_operador()

usuario = st.session_state.usuario
if "produto_confirmar_exclusao" not in st.session_state:
    st.session_state["produto_confirmar_exclusao"] = None


# =====================================================
# CSS PREMIUM E ANIMAÇÕES
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
   ACORDEÃO (EXPANDER) "NOVO PRODUTO"
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
   CARDS DE PRODUTOS
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
   DIVISOR DE CATEGORIAS (GRADIENTE PREMIUM)
========================================== */
.categoria-header {
    background: linear-gradient(135deg, #5a3b28 0%, #8c6245 100%);
    color: #ffffff;
    padding: 10px 18px;
    border-radius: 12px;
    margin-top: 30px;
    margin-bottom: 15px;
    font-weight: 800;
    font-size: 15px !important;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    box-shadow: 0 4px 10px rgba(90, 59, 40, 0.15);
}

/* =========================================
   ELEMENTOS DE TEXTO & BADGES
========================================== */
.produto-nome {
    font-weight: 800;
    color: #2c1e14;
    font-size: 15px !important;
    margin-bottom: 2px;
}

.produto-preco {
    font-weight: 800;
    color: #2e7d32;
    font-size: 15px !important;
}

.badge-incluso, .badge-consulta, .badge-ativo, .badge-inativo {
    display: inline-block;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-incluso { background-color: #e8f0fe; color: #1a73e8; border: 1px solid #d2e3fc; }
.badge-consulta { background-color: #fef7e0; color: #b06000; border: 1px solid #fce8b2; }
.badge-ativo { background-color: #e6f4ea; color: #137333; border: 1px solid #ceead6; }
.badge-inativo { background-color: #fce8e6; color: #c5221f; border: 1px solid #fad2cf; }

/* Botões de Ação na Tabela */
div[data-testid="stColumn"] div[data-testid="stButton"] button {
    font-size: 14px !important;
    padding: 4px 8px !important;
    border-radius: 10px !important;
    min-height: 36px !important;
    border: 1px solid #e8ddd3 !important;
    background: #faf7f3 !important;
    transition: all 0.2s ease;
}
div[data-testid="stColumn"] div[data-testid="stButton"] button:hover {
    background: #e8ddd3 !important;
    transform: scale(1.05);
}

.stImage img { border-radius: 8px; object-fit: cover; border: 1px solid #e8ddd3; }

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}

/* =========================================
   RESPONSIVIDADE MOBILE E BOTÕES LADO A LADO
========================================== */
@media (max-width: 768px) {
    h1 { font-size: 24px !important; }
    .categoria-header { font-size: 13px !important; padding: 8px 14px; margin-top: 22px; }
    .produto-nome { font-size: 13.5px !important; }
    .produto-preco { font-size: 13.5px !important; }
    .badge-incluso, .badge-consulta, .badge-ativo, .badge-inativo { font-size: 9.5px !important; padding: 3px 8px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 10px 12px !important; }
    
    /* Força os botões dentro do bloco da direita a ficarem na horizontal */
    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
        margin-top: 15px !important;
        justify-content: space-between;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) > div[data-testid="stColumn"] {
        width: 33.33% !important;
        flex: 1 1 0% !important;
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
    page_header("Produtos e insumos", "Itens do catálogo, estoque e adicionais.", "🍓", ["Catálogo", "Produtos"], "ok")
    st.caption("Organize seu catálogo, controle preços, status e adicione fotos aos itens extras.")


# =====================================================
# CARREGAR CATEGORIAS
# =====================================================

try:
    categorias = listar_categorias()
except Exception as erro:
    st.error(f"Erro ao carregar categorias: {erro}")
    categorias = []


# =====================================================
# CADASTRO DE PRODUTO (NOVO MODELO COM EXPANDER)
# =====================================================

salvar = False

if usuario.get("perfil") == "Administrador":
    # Aqui está o Expander, que mantém a tela limpa abrindo apenas quando clicado
    with st.expander("✨ Cadastrar Novo Produto", expanded=False):
        col_f1, col_f2 = st.columns([1.5, 1])

        with col_f1:
            nome = st.text_input("Nome do Produto", placeholder="Ex: Nutella 350g")
            descricao = st.text_area("Descrição Breve", height=80, placeholder="Descreva detalhes ou sabores (Opcional)...")
            ativo = st.checkbox("Produto visível e ativo", value=True)

        with col_f2:
            if categorias:
                categoria = st.selectbox("Categoria", categorias, format_func=lambda x: x["nome"])
            else:
                categoria = None
                st.warning("Nenhuma categoria cadastrada.")

            imagem_arquivo = None
            tipo_preco = "Incluso na cesta"
            preco = None

            if categoria:
                categoria_possui_preco = categoria.get("possui_preco", False)
                nome_categoria_atual = str(categoria.get("nome", "")).strip().lower()

                if categoria_possui_preco:
                    tipo_preco = st.radio("Configuração de Valor", ["Preço definido", "Preço sob consulta"], horizontal=True)
                    if tipo_preco == "Preço sob consulta":
                        st.info("O valor será negociado no momento da venda.")
                    else:
                        preco = st.number_input("Preço de Venda (R$)", min_value=0.0, value=0.0, step=0.50, format="%.2f")
                else:
                    st.success("Item Padrão (Valor já embutido nas cestas)")

                if nome_categoria_atual == "adicionais":
                    st.write("")
                    imagem_arquivo = st.file_uploader("📷 Imagem de Vitrine (Opcional)", type=["jpg", "jpeg", "png", "webp"])
                    if imagem_arquivo:
                        st.image(imagem_arquivo, width=80, caption="Pré-visualização")

        st.write("")
        salvar = st.button("💾 Adicionar Produto ao Catálogo", use_container_width=True, type="primary")

else:
    st.info("Modo consulta ativo. Apenas Administradores podem cadastrar novos produtos.")


# =====================================================
# SALVAR PRODUTO
# =====================================================

if salvar:
    if not nome.strip():
        st.error("Informe o nome do produto.")
        st.stop()
    if not categoria:
        st.error("Selecione uma categoria.")
        st.stop()
    if categoria.get("possui_preco") and tipo_preco == "Preço definido" and (preco is None or preco <= 0):
        st.error("Informe o valor do produto.")
        st.stop()

    try:
        with st.spinner("Salvando produto no banco de dados..."):
            imagem_url = None
            if imagem_arquivo:
                imagem_url = upload_imagem_produto(imagem_arquivo)

            cadastrar_produto(
                categoria_id=categoria["id"],
                nome=nome.strip(),
                descricao=descricao.strip(),
                preco=preco,
                ativo=ativo,
                tipo_preco=tipo_preco,
                imagem=imagem_url
            )
        st.success("✅ Produto cadastrado com sucesso!")
        st.cache_data.clear()
        st.rerun()
    except Exception as erro:
        st.error(f"Erro ao cadastrar produto: {erro}")


# =====================================================
# FUNÇÃO EXIBIR PRODUTO (LAYOUT CARD)
# =====================================================

def exibir_produto(produto, categoria, usuario_eh_admin):
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([4.5, 2.5, 1.2, 1.8])
        
        nome_cat_formatado = str(categoria.get("nome", "")).strip().lower()

        # Coluna 1: Imagem (se Adicional) + Nome/Desc
        with col1:
            imagem_url = produto.get("imagem", None)
            
            if imagem_url and nome_cat_formatado == "adicionais":
                col_img, col_txt = st.columns([1, 4])
                with col_img:
                    st.image(imagem_url, width=50)
                with col_txt:
                    st.markdown(f'<div class="produto-nome">{html.escape(str(produto.get("nome") or "-"))}</div>', unsafe_allow_html=True)
                    if produto.get("descricao"):
                        st.caption(produto["descricao"])
            else:
                st.markdown(f'<div class="produto-nome">{html.escape(str(produto.get("nome") or "-"))}</div>', unsafe_allow_html=True)
                if produto.get("descricao"):
                    st.caption(produto["descricao"])

        # Coluna 2: Regra Financeira
        with col2:
            possui_preco = categoria.get("possui_preco", False)

            if possui_preco:
                tipo = str(produto.get("tipo_preco", "Preço definido")).strip()
                if tipo.lower() == "preço sob consulta":
                    st.markdown('<span class="badge-consulta">Sob Consulta</span>', unsafe_allow_html=True)
                else:
                    valor = produto.get("preco")
                    if valor is not None:
                        valor_formatado = f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
                        st.markdown(f'<div class="produto-preco">{valor_formatado}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="badge-consulta">Sob Consulta</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge-incluso">Incluso na Cesta</span>', unsafe_allow_html=True)

        # Coluna 3: Visibilidade
        with col3:
            if produto.get("ativo", True):
                st.markdown('<span class="badge-ativo">Ativo</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge-inativo">Inativo</span>', unsafe_allow_html=True)

        # Coluna 4: Painel de Controle (Botões)
        with col4:
            b1, b2, b3 = st.columns(3)
            with b1:
                editar = st.button("✏️", key=f"editar_{produto['id']}", help="Editar detalhes do produto" if usuario_eh_admin else "Somente Administrador pode editar", use_container_width=True, disabled=not usuario_eh_admin)
            with b2:
                status = st.button("🔴" if produto.get("ativo", True) else "🟢", key=f"status_{produto['id']}", help="Ativar/Desativar produto", use_container_width=True)
            with b3:
                excluir = st.button("🗑️", key=f"excluir_{produto['id']}", help="Excluir do catálogo" if usuario_eh_admin else "Somente Administrador pode excluir", use_container_width=True, disabled=not usuario_eh_admin)

    return editar, status, excluir


# =====================================================
# LISTAGEM DOS PRODUTOS
# =====================================================

try:
    produtos = listar_produtos()
except Exception as erro:
    st.error(f"Erro ao carregar produtos: {erro}")
    produtos = []

if not produtos:
    st.info("O catálogo de produtos está vazio. Cadastre o primeiro item acima.")
    st.stop()

busca_produto = st.text_input("Buscar produto", placeholder="🔎 Buscar produto por nome...", label_visibility="collapsed")
if busca_produto:
    termo = busca_produto.strip().lower()
    produtos = [p for p in produtos if termo in str(p.get("nome") or "").lower()]
    if not produtos:
        st.info("Nenhum produto encontrado para essa busca.")
        st.stop()


# Organiza e Agrupa Produtos por Categoria
categorias_dict = {categoria["id"]: categoria for categoria in categorias}
produtos_agrupados = {}

for produto in produtos:
    categoria_id = produto.get("categoria_id")
    categoria = categorias_dict.get(categoria_id)
    nome_categoria = categoria.get("nome", "Sem Categoria") if categoria else "Sem Categoria"

    if nome_categoria not in produtos_agrupados:
        produtos_agrupados[nome_categoria] = {"categoria": categoria, "produtos": []}
    
    produtos_agrupados[nome_categoria]["produtos"].append(produto)


# Ordena Categorias baseado na propriedade 'ordem' do banco
categorias_ordenadas = sorted(
    produtos_agrupados.items(),
    key=lambda x: x[1]["categoria"].get("ordem", 999) if x[1]["categoria"] else 999
)


# Renderização Visual
for categoria_nome, dados in categorias_ordenadas:
    categoria = dados["categoria"] or {}

    st.markdown(
        f'<div class="categoria-header">📁 {html.escape(str(categoria_nome))}</div>',
        unsafe_allow_html=True
    )

    for produto in dados["produtos"]:
        editar, status, excluir = exibir_produto(produto, categoria, usuario.get("perfil") == "Administrador")

        if editar and usuario.get("perfil") == "Administrador":
            st.session_state["produto_editar"] = produto["id"]
            st.switch_page("pages/10_Editar_Produto.py")

        if status:
            novo_status = not produto.get("ativo", True)
            try:
                alterar_status_produto(produto["id"], novo_status)
                st.cache_data.clear()
                st.rerun()
            except Exception as erro:
                st.error(f"Erro ao alterar status: {erro}")

        if excluir and usuario.get("perfil") == "Administrador":
            st.session_state["produto_confirmar_exclusao"] = produto["id"]
            st.rerun()

        if st.session_state.get("produto_confirmar_exclusao") == produto["id"]:
            with st.container(border=True):
                st.warning(f"⚠️ Confirma excluir **{produto.get('nome') or 'este produto'}** do catálogo? Essa ação não pode ser desfeita.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ Sim, excluir", key=f"conf_excluir_{produto['id']}", use_container_width=True, type="primary"):
                        try:
                            excluir_produto(produto["id"])
                            st.session_state["produto_confirmar_exclusao"] = None
                            st.toast("✅ Produto removido com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as erro:
                            st.error(f"Erro ao excluir produto: {erro}")
                with cc2:
                    if st.button("❌ Cancelar", key=f"canc_excluir_{produto['id']}", use_container_width=True):
                        st.session_state["produto_confirmar_exclusao"] = None
                        st.rerun()


# =====================================================
# RODAPÉ
# =====================================================

st.write("")
st.divider()
st.caption("📦 Gerenciamento Oficial de Produtos - Doce Cesta Brasília")
