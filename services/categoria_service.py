import streamlit as st
import boto3
import uuid
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

# ... (Mantenha as funções listar_cestas inalteradas) ...

# =====================================================
# UPLOAD IMAGEM DA CESTA (ATUALIZADO PARA CLOUDFLARE R2)
# =====================================================
def upload_imagem_cesta(arquivo):
    if arquivo is None:
        return None

    try:
        extensao = arquivo.name.split(".")[-1]
        nome_arquivo = f"{uuid.uuid4()}.{extensao}"
        
        # O caminho agora é direto na raiz do bucket "cestas"
        caminho = f"{nome_arquivo}"

        s3_client = _get_s3_client()
        url_base_r2 = st.secrets["r2_urls"]["cestas"].rstrip("/")
        nome_bucket = "cestas"

        # Faz o upload direto para o Cloudflare R2
        s3_client.upload_fileobj(
            arquivo,
            nome_bucket,
            caminho,
            ExtraArgs={"ContentType": arquivo.type}
        )

        # Monta a URL pública oficial
        url_publica = f"{url_base_r2}/{caminho}"
        return url_publica

    except Exception as erro:
        raise Exception(f"Erro no upload da imagem da cesta: {erro}")


# ... (Mantenha cadastrar_cesta, excluir_cesta, alterar_status_cesta, buscar_cesta e atualizar_cesta inalteradas) ...


# =====================================================
# REMOVER IMAGEM DA CESTA (ATUALIZADO PARA CLOUDFLARE R2)
# =====================================================
def remover_imagem_cesta(cesta_id):
    try:
        # Busca a URL atual da imagem no banco para apagar do Cloudflare
        cesta = buscar_cesta(cesta_id)
        
        if cesta and cesta.get("imagem"):
            url_imagem = cesta["imagem"]
            # Extrai o nome do arquivo no final do link
            nome_arquivo = url_imagem.split("/")[-1]
            
            try:
                # Tenta deletar fisicamente do Cloudflare R2
                s3_client = _get_s3_client()
                s3_client.delete_object(Bucket="cestas", Key=nome_arquivo)
            except Exception as e:
                print(f"Aviso: Não foi possível apagar a imagem no R2: {e}")

        # Limpa o campo de imagem no Supabase
        (
            supabase
            .table("cestas")
            .update({
                "imagem": None
            })
            .eq("id", cesta_id)
            .execute()
        )
    except Exception as e:
        print(f"Erro ao remover imagem da cesta: {e}")

