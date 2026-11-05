import uuid
import boto3
import streamlit as st
from config.db import supabase

# =====================================================
# INICIALIZAR CLIENTE S3 (CLOUDFLARE R2)
# =====================================================
def _get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=st.secrets["cloudflare"]["endpoint_url"],
        aws_access_key_id=st.secrets["cloudflare"]["access_key_id"],
        aws_secret_access_key=st.secrets["cloudflare"]["secret_access_key"],
        region_name="auto"
    )


# =====================================================
# LISTAR PRODUTOS
# =====================================================
def listar_produtos():
    resposta = (
        supabase
        .table("produtos")
        .select(
            """
            *,
            categorias(
                id,
                nome,
                possui_preco
            )
            """
        )
        .order("nome")
        .execute()
    )
    return resposta.data or []


# =====================================================
# LISTAR CATEGORIAS
# =====================================================
def listar_categorias():
    resposta = (
        supabase
        .table("categorias")
        .select("*")
        .order("nome")
        .execute()
    )
    return resposta.data or []


# =====================================================
# LISTAR CATEGORIAS ATIVAS
# =====================================================
def listar_categorias_ativas():
    resposta = (
        supabase
        .table("categorias")
        .select("*")
        .eq("ativo", True)
        .order("ordem")
        .execute()
    )
    return resposta.data or []


# =====================================================
# LISTAR CATEGORIAS DO PEDIDO
# =====================================================
def listar_categorias_pedido():
    resposta = (
        supabase
        .table("categorias")
        .select("*")
        .eq("ativo", True)
        .eq("exibir_no_pedido", True)
        .order("ordem")
        .execute()
    )
    return resposta.data or []


# =====================================================
# LISTAR PRODUTOS POR CATEGORIA
# =====================================================
def listar_produtos_por_categoria(categoria_nome):
    categoria = (
        supabase
        .table("categorias")
        .select("id")
        .eq("nome", categoria_nome)
        .single()
        .execute()
    )

    if not categoria.data:
        return []

    return listar_produtos_por_categoria_id(categoria.data["id"])


def listar_produtos_por_categoria_id(categoria_id):
    resposta = (
        supabase
        .table("produtos")
        .select(
            """
            *,
            categorias(
                id,
                nome,
                possui_preco
            )
            """
        )
        .eq("categoria_id", categoria_id)
        .eq("ativo", True)
        .order("nome")
        .execute()
    )
    return resposta.data or []


# =====================================================
# BUSCAR PRODUTO
# =====================================================
def buscar_produto(produto_id):
    resposta = (
        supabase
        .table("produtos")
        .select(
            """
            *,
            categorias(
                id,
                nome,
                possui_preco
            )
            """
        )
        .eq("id", produto_id)
        .single()
        .execute()
    )
    return resposta.data


# =====================================================
# BUSCAR CATEGORIA
# =====================================================
def buscar_categoria_produto(categoria_id):
    resposta = (
        supabase
        .table("categorias")
        .select(
            """
            id,
            nome,
            possui_preco
            """
        )
        .eq("id", categoria_id)
        .single()
        .execute()
    )
    return resposta.data


# =====================================================
# UPLOAD DA IMAGEM DO PRODUTO (CLOUDFLARE R2)
# =====================================================
def upload_imagem_produto(arquivo):
    if arquivo is None:
        return None

    try:
        extensao = arquivo.name.split(".")[-1]
        nome_arquivo = f"{uuid.uuid4()}.{extensao}"

        s3_client = _get_s3_client()
        nome_bucket = "produtos"

        # Upload direto para o Cloudflare R2
        s3_client.upload_fileobj(
            arquivo,
            nome_bucket,
            nome_arquivo,
            ExtraArgs={"ContentType": arquivo.type}
        )

        # URL pública do Cloudflare R2 para o bucket de produtos
        url_publica = f"https://pub-21cecd1686dc4042bb5984f98c2dd0a2.r2.dev/{nome_arquivo}"
        return url_publica

    except Exception as erro:
        raise Exception(f"Erro no upload da imagem do produto: {erro}")


# =====================================================
# REMOVER IMAGEM DO PRODUTO (CLOUDFLARE R2 / SUPABASE)
# =====================================================
def remover_imagem_produto(produto_id):
    try:
        produto = buscar_produto(produto_id)
        
        if produto and produto.get("imagem"):
            url_imagem = produto["imagem"]
            nome_arquivo = url_imagem.split("/")[-1]
            
            # Deleta fisicamente se for imagem no Cloudflare R2
            if "r2.dev" in url_imagem:
                try:
                    s3_client = _get_s3_client()
                    s3_client.delete_object(Bucket="produtos", Key=nome_arquivo)
                except Exception as e:
                    print(f"Aviso: Erro ao remover imagem no R2: {e}")
   
        # Desvincula do banco de dados
        (
            supabase
            .table("produtos")
            .update({"imagem": None})
            .eq("id", produto_id)
            .execute()
        )
    except Exception as e:
        print(f"Erro ao remover imagem do produto: {e}")


# =====================================================
# CADASTRAR PRODUTO 
# =====================================================
def cadastrar_produto(
    categoria_id,
    nome,
    descricao,
    preco,
    ativo=True,
    tipo_preco="Incluso na cesta",
    imagem=None
):
    categoria = buscar_categoria_produto(categoria_id)

    if not categoria:
        raise Exception("Categoria não encontrada.")

    if not categoria.get("possui_preco", False):
        preco = None
        tipo_preco = "Incluso na cesta"

    dados = {
        "categoria_id": categoria_id,
        "nome": nome,
        "descricao": descricao,
        "preco": preco,
        "ativo": ativo,
        "tipo_preco": tipo_preco,
        "imagem": imagem
    }

    resposta = (
        supabase
        .table("produtos")
        .insert(dados)
        .execute()
    )
    return resposta.data


# =====================================================
# ATUALIZAR PRODUTO 
# =====================================================
def atualizar_produto(
    produto_id,
    categoria_id,
    nome,
    descricao,
    preco,
    ativo,
    tipo_preco="Incluso na cesta",
    imagem=None
):
    categoria = buscar_categoria_produto(categoria_id)

    if not categoria:
        raise Exception("Categoria não encontrada.")

    if not categoria.get("possui_preco", False):
        preco = None
        tipo_preco = "Incluso na cesta"

    resposta = (
        supabase
        .table("produtos")
        .update({
            "categoria_id": categoria_id,
            "nome": nome,
            "descricao": descricao,
            "preco": preco,
            "ativo": ativo,
            "tipo_preco": tipo_preco,
            "imagem": imagem
        })
        .eq("id", produto_id)
        .execute()
    )
    return resposta.data


# =====================================================
# STATUS PRODUTO
# =====================================================
def alterar_status_produto(produto_id, ativo):
    resposta = (
        supabase
        .table("produtos")
        .update({"ativo": ativo})
        .eq("id", produto_id)
        .execute()
    )
    return resposta.data


def desativar_produto(produto_id):
    return alterar_status_produto(produto_id, False)


# =====================================================
# VERIFICA USO EM CESTAS
# =====================================================
def verificar_uso_produto(produto_id):
    resposta = (
        supabase
        .table("cesta_produtos")
        .select("id")
        .eq("produto_id", produto_id)
        .limit(1)
        .execute()
    )
    return bool(resposta.data)


# =====================================================
# EXCLUIR PRODUTO COM SEGURANÇA
# =====================================================
def excluir_produto(produto_id):
    try:
        # REMOVE VÍNCULOS COM CESTAS
        supabase.table("cesta_produtos").delete().eq("produto_id", produto_id).execute()

        # REMOVE PRODUTO
        resposta = (
            supabase
            .table("produtos")
            .delete()
            .eq("id", produto_id)
            .execute()
        )
        return resposta.data
    except Exception as erro:
        raise Exception(
            "Não foi possível excluir o produto. "
            "Verifique se existem vínculos ou permissões no Supabase.\n\n"
            f"Detalhes: {erro}"
        )


# =====================================================
# LISTAR PRODUTOS ATIVOS
# =====================================================
def listar_produtos_ativos():
    resposta = (
        supabase
        .table("produtos")
        .select(
            """
            *,
            categorias(
                id,
                nome,
                possui_preco
            )
            """
        )
        .eq("ativo", True)
        .order("nome")
        .execute()
    )
    return resposta.data or []


# =====================================================
# LISTAR PRODUTOS PARA ADMIN
# =====================================================
def listar_produtos_categoria_admin(categoria_id):
    resposta = (
        supabase
        .table("produtos")
        .select(
            """
            *,
            categorias(
                id,
                nome,
                possui_preco
            )
            """
        )
        .eq("categoria_id", categoria_id)
        .order("nome")
        .execute()
    )
    return resposta.data or []


# =====================================================
# VALIDAR PREÇO DA CATEGORIA
# =====================================================
def categoria_possui_preco(categoria_id):
    categoria = buscar_categoria_produto(categoria_id)
    if not categoria:
        return False
    return categoria.get("possui_preco", False)


# =====================================================
# PRODUTOS SOB CONSULTA
# =====================================================
def listar_produtos_sob_consulta():
    resposta = (
        supabase
        .table("produtos")
        .select(
            """
            *,
            categorias(
                id,
                nome,
                possui_preco
            )
            """
        )
        .is_("preco", None)
        .eq("ativo", True)
        .order("nome")
        .execute()
    )
    return resposta.data or []
