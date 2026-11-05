import streamlit as st
import time
import boto3

from services.produto_service import (
    listar_categorias,
    buscar_produto,
    atualizar_produto,
    upload_imagem_produto,
    remover_imagem_produto
)

from utils.ui import page_header
from utils.menu import (
    configurar_pagina,
    menu_lateral
)

from utils.permissao import (
    administrador
)


# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================

st.set_page_config(
    page_title="Editar Produto",
    page_icon="✏️",
    layout="wide"
)

configurar_pagina()
menu_lateral()
administrador()


# =====================================================
# FUNÇÃO PRIVADA (DELETAR DO CLOUDFLARE R2)
# =====================================================
def _deletar_arquivo_r2(imagem_url):
    try:
        if not imagem_url:
            return
        # Extrai o nome do arquivo no final da URL do R2
        nome_arquivo = str(imagem_url).split("/")[-1]
        if nome_arquivo:
            s3_client = boto3.client(
                's3',
                endpoint_url=st.secrets["cloudflare"]["endpoint_url"],
                aws_access_key_id=st.secrets["cloudflare"]["access_key_id"],
                aws_secret_access_key=st.secrets["cloudflare"]["secret_access_key"],
                region_name="auto"
            )
            s3_client.delete_object(Bucket="produtos", Key=nome_arquivo)
    except Exception as e:
        print(f"Aviso: Não foi possível apagar o arquivo físico no R2: {e}")


# =====================================================
# CSS PREMIUM E RESPONSIVIDADE
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
    max-width: 1000px;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.5rem !important;
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
   CONTAINER CARD DO FORMULÁRIO (FOCUS CARD)
========================================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff;
    border: 1px solid #e8ddd3 !important;
    border-radius: 16px !important;
    padding: 24px 28px !important;
    margin-bottom: 10px !important;
    box-shadow: 0 4px 15px rgba(90, 59, 40, 0.04);
    transition: all 0.3s ease;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #d2bfae !important;
    box-shadow: 0 8px 25px rgba(90, 59, 40, 0.08);
}

/* =========================================
   CUSTOMIZAÇÃO DO UPLOADER MODERNO (DROPZONE)
========================================== */
div[data-testid="stFileUploader"] {
    width: 100% !important;
}

div[data-testid="stFileUploader"] section {
    background-color: #faf7f3 !important;
    border: 2px dashed #dfcdbb !important;
    border-radius: 12px !important;
    padding: 12px !important;
    text-align: center !important;
    transition: all 0.3s ease !important;
}

div[data-testid="stFileUploader"] section:hover {
    border-color: #a87b57 !important;
    background-color: #f5eee6 !important;
}

div[data-testid="stFileUploader"] section button {
    background-color: #ffffff !important;
    border: 1px solid #dfcdbb !important;
    color: #5a3b28 !important;
    font-weight: 800 !important;
    border-radius: 10px !important;
    padding: 6px 16px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.03) !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stFileUploader"] section button span {
    display: none !important;
}

div[data-testid="stFileUploader"] section button::after {
    content: "📁 Selecionar Foto" !important;
    font-size: 13px !important;
    font-weight: 800 !important;
}

/* =========================================
   ESTILIZAÇÃO DE BOTÕES E IMAGENS
========================================== */
div[data-testid="stColumn"] > div > div > div > div[data-testid="stButton"] > button {
    font-size: 14px !important;
    font-weight: 800 !important;
    border-radius: 10px !important;
    min-height: 40px !important;
    transition: all 0.2s ease;
}
div[data-testid="stColumn"] > div > div > div > div[data-testid="stButton"] > button:hover {
    transform: scale(1.02);
}

.stImage img {
    border-radius: 10px;
    object-fit: cover;
    border: 1px solid #e8ddd3;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
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
    h1 { font-size: 26px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 16px 14px !important; }
    
    /* Força os botões de ação a ficarem na horizontal no mobile */
    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 10px !important;
        margin-top: 15px !important;
        justify-content: space-between;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) > div[data-testid="stColumn"] {
        flex: 1 1 0% !important; 
        min-width: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) button {
        width: 100% !important;
        padding: 8px 0px !important;
    }
}
</style>
""",
unsafe_allow_html=True
)


# =====================================================
# VALIDA PRODUTO
# =====================================================

if "produto_editar" not in st.session_state or not st.session_state["produto_editar"]:
    st.warning("⚠️ Nenhum produto selecionado para edição.")
    if st.button("⬅ Voltar para Produtos"):
        st.switch_page("pages/05_Produtos.py")
    st.stop()

produto_id = st.session_state["produto_editar"]


# =====================================================
# BUSCAR DADOS
# =====================================================

try:
    produto = buscar_produto(produto_id)
    categorias = listar_categorias()
except Exception as erro:
    st.error(f"Erro ao carregar produto: {erro}")
    st.stop()

if not produto:
    st.error("Produto não encontrado no banco de dados.")
    st.stop()


# =====================================================
# TÍTULO E CABEÇALHO
# =====================================================

col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    page_header("Editar produto", "Atualize dados, preço e imagem.", "✏️", ["Catálogo", "Produtos", "Editar"])
    st.caption("Atualize as informações, preços e imagens deste item do catálogo.")


# =====================================================
# IDENTIFICA CATEGORIA ATUAL
# =====================================================

indice_categoria = 0

for i, categoria_item in enumerate(categorias):
    if categoria_item["id"] == produto["categoria_id"]:
        indice_categoria = i
        break


# =====================================================
# FORMULÁRIO DE EDIÇÃO (CARD PREMIUM SIDE-BY-SIDE)
# =====================================================

with st.container(border=True):
    col1, col2 = st.columns([1.4, 1])

    with col1:
        categoria = st.selectbox(
            "📁 Categoria",
            categorias,
            index=indice_categoria,
            format_func=lambda c: c["nome"]
        )

        nome = st.text_input(
            "🏷️ Nome do Produto",
            value=produto.get("nome", "")
        )

        descricao = st.text_area(
            "📝 Descrição",
            value=produto.get("descricao", "") or "",
            height=90,
            placeholder="Descreva detalhes, sabores ou observações importantes..."
        )
        
        ativo = st.checkbox(
            "🟢 Produto Ativo e Visível",
            value=produto.get("ativo", True)
        )

    with col2:
        # Regra de preço dinâmica baseada na categoria
        categoria_nome = categoria["nome"].strip().lower()

        if categoria_nome == "adicionais":
            tipo_atual = produto.get("tipo_preco", "Preço definido")

            tipo_preco = st.radio(
                "💰 Regra de Precificação",
                ["Preço definido", "Preço sob consulta"],
                index=(1 if tipo_atual == "Preço sob consulta" else 0),
                horizontal=True
            )

            if tipo_preco == "Preço sob consulta":
                preco = None
                st.info("ℹ️ Produto sem valor fixo. O preço será negociado no momento da venda.")
            else:
                preco = st.number_input(
                    "Valor (R$)",
                    min_value=0.0,
                    value=float(produto.get("preco", 0) or 0),
                    step=0.50,
                    format="%.2f"
                )
        else:
            tipo_preco = "Incluso na cesta"
            preco = None
            st.success("✅ Produto Padrão (O valor já está embutido nas cestas principais).")

        # =========================================
        # GESTÃO DE IMAGEM (APENAS PARA ADICIONAIS)
        # =========================================
        nova_imagem = None
        imagem_atual = produto.get("imagem", "")

        if "adicional" in categoria_nome or "adicionais" in categoria_nome:
            st.markdown("<hr style='margin: 15px 0; border: none; border-top: 1px dashed #dfcdbb;'>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 13px; font-weight: 800; color: #5a3b28; margin-bottom: 8px;'>📷 Imagem de Vitrine</div>", unsafe_allow_html=True)
            
            col_img1, col_img2 = st.columns(2)
            
            with col_img1:
                if imagem_atual:
                    st.image(imagem_atual, width=100)
                    if st.button("❌ Remover Foto", key="rm_foto_prod", use_container_width=True):
                        with st.spinner("Removendo foto..."):
                            try:
                                # 1. APAGA O ARQUIVO FÍSICO DO CLOUDFLARE R2
                                _deletar_arquivo_r2(imagem_atual)

                                # 2. REMOVE A REFERÊNCIA NO BANCO DE DADOS
                                remover_imagem_produto(produto_id)
                                st.toast("✅ Imagem removida com sucesso!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as erro:
                                st.error(f"Erro ao remover: {erro}")
                else:
                    st.caption("Nenhuma foto cadastrada.")
            
            nova_imagem = st.file_uploader("Upload de Nova Foto", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed")
            if nova_imagem:
                with col_img2:
                    st.image(nova_imagem, width=100, caption="Nova Imagem")

    st.write("")
    st.divider()

    # Botões de Ação
    col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 1])

    with col_b1:
        salvar = st.button("💾 Salvar Alterações", use_container_width=True, type="primary")

    with col_b2:
        cancelar = st.button("❌ Cancelar", use_container_width=True)


# =====================================================
# CANCELAR
# =====================================================

if cancelar:
    st.session_state.pop("produto_editar", None)
    st.switch_page("pages/05_Produtos.py")


# =====================================================
# SALVAR ALTERAÇÕES
# =====================================================

if salvar:
    if not nome.strip():
        st.error("Informe o nome do produto.")
        st.stop()

    # Validação de Preço
    if "adicional" in categoria_nome or "adicionais" in categoria_nome:
        if tipo_preco == "Preço definido" and (preco is None or preco <= 0):
            st.error("Informe o valor do adicional.")
            st.stop()
            
    # Tratamento da Imagem
    imagem_final = imagem_atual
    
    with st.spinner("Atualizando catálogo..."):
        if nova_imagem:
            try:
                # Apaga a imagem velha do R2 caso o usuário esteja substituindo por uma nova
                if imagem_atual:
                    _deletar_arquivo_r2(imagem_atual)
                
                # Faz o upload da nova imagem para o Cloudflare R2
                imagem_final = upload_imagem_produto(nova_imagem)
            except Exception as erro:
                st.error(f"Erro no upload da imagem: {erro}")
                st.stop()

        try:
            atualizar_produto(
                produto_id,
                categoria["id"],
                nome.strip(),
                descricao.strip(),
                preco,
                ativo,
                tipo_preco,
                imagem_final  
            )

            st.success("✅ Produto atualizado com sucesso!")
            st.cache_data.clear()
            st.session_state.pop("produto_editar", None)
            time.sleep(1)
            st.switch_page("pages/05_Produtos.py")

        except Exception as erro:
            st.error(f"Erro ao atualizar produto: {erro}")


# =====================================================
# RODAPÉ
# =====================================================

st.write("")
st.caption("📦 Gestão de Catálogo - Doce Cesta Brasília")
