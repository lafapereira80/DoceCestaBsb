import io
import mimetypes
import streamlit as st
import boto3
from uuid import uuid4
from config.db import supabase

def _get_s3_client():
    """Inicializa e retorna o cliente de conexão com o Cloudflare R2."""
    return boto3.client(
        's3',
        endpoint_url=st.secrets["cloudflare"]["endpoint_url"],
        aws_access_key_id=st.secrets["cloudflare"]["access_key_id"],
        aws_secret_access_key=st.secrets["cloudflare"]["secret_access_key"],
        region_name="auto" # O boto3 exige esse parâmetro, 'auto' é o padrão para o R2
    )

def salvar_fotos(pedido_id, arquivos):
    """
    Faz o upload das fotos para o Cloudflare R2 e salva os metadados na tabela pedido_fotos no Supabase.
    """
    if not arquivos:
        return True, ""

    if not isinstance(arquivos, list):
        arquivos = [arquivos]
        
    erros = []
    
    try:
        s3_client = _get_s3_client()
        url_base_r2 = st.secrets["r2_urls"]["pedido_fotos"].rstrip("/")
        nome_bucket = "pedido-fotos"
    except Exception as e:
        return False, f"Erro ao configurar a conexão com o servidor de imagens: {type(e).__name__}: {e}"

    for arquivo in arquivos:
        try:
            extensao = (arquivo.name.rsplit(".", 1)[-1] if "." in arquivo.name else "jpg").lower()
            conteudo = arquivo.getvalue() if hasattr(arquivo, "getvalue") else arquivo.read()
            if not conteudo:
                raise ValueError("arquivo vazio (o carregamento não terminou)")
            tipo = getattr(arquivo, "type", "") or mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"

            # iPhone: HEIC/HEIF não abre em navegadores/WhatsApp -> converte para JPEG quando possível
            if extensao in ("heic", "heif") or tipo in ("image/heic", "image/heif"):
                try:
                    from PIL import Image
                    try:
                        import pillow_heif
                        pillow_heif.register_heif_opener()
                    except Exception:
                        pass
                    img = Image.open(io.BytesIO(conteudo)).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=92)
                    conteudo, extensao, tipo = buf.getvalue(), "jpg", "image/jpeg"
                except Exception:
                    pass

            nome_arquivo = f"{pedido_id}/{uuid4()}.{extensao}"

            # 1. Faz o upload para o Cloudflare R2 (sempre do início do arquivo)
            s3_client.upload_fileobj(
                io.BytesIO(conteudo),
                nome_bucket,
                nome_arquivo,
                ExtraArgs={"ContentType": tipo}
            )

            # 2. Gera o link público oficial a partir da URL do Secrets
            url_publica = f"{url_base_r2}/{nome_arquivo}"

            # 3. Insere na tabela do Supabase
            supabase.table("pedido_fotos").insert({
                "pedido_id": pedido_id,
                "arquivo": nome_arquivo,
                "nome_original": arquivo.name,
                "url": url_publica
            }).execute()
            
        except Exception as e:
            erros.append(f"Falha na foto {arquivo.name}: {str(e)}")
            
    if erros:
        return False, " | ".join(erros)
        
    return True, ""


def listar_fotos(pedido_id):
    """
    Busca as fotos de um pedido no banco de dados. 
    Possui sistema de fallback apontando para o R2 caso a URL falhe.
    """
    try:
        resposta = supabase.table("pedido_fotos").select("*").eq("pedido_id", pedido_id).order("created_at").execute()
        fotos = resposta.data or []
        
        url_base_r2 = st.secrets.get("r2_urls", {}).get("pedido_fotos", "").rstrip("/")
        
        for foto in fotos:
            # Fallback atualizado: Se a URL estiver vazia, tenta montar com o link do R2
            if not foto.get("url") and foto.get("arquivo") and url_base_r2:
                foto["url"] = f"{url_base_r2}/{foto['arquivo']}"
                
        return fotos
    except Exception as e:
        print(f"Erro ao listar fotos: {e}")
        return []


def deletar_foto(foto_id, caminho_arquivo):
    """
    Deleta o arquivo físico do Cloudflare R2 e o registro da tabela no Supabase.
    """
    try:
        # Tenta excluir fisicamente do R2
        if caminho_arquivo:
            try:
                s3_client = _get_s3_client()
                s3_client.delete_object(Bucket="pedido-fotos", Key=caminho_arquivo)
            except Exception as e:
                print(f"Aviso: Não foi possível apagar o arquivo no Storage: {e}")
            
        # Exclui o registro no banco de dados
        supabase.table("pedido_fotos").delete().eq("id", foto_id).execute()
        return True, ""
    except Exception as e:
        return False, f"Erro ao deletar: {str(e)}"


def deletar_todas_fotos_do_pedido(pedido_id):
    """
    Apaga do Cloudflare R2 e do banco TODAS as fotos de um pedido de uma vez.
    Usado ao excluir um pedido por completo (ex: status "Desistência" em
    02_Pedidos.py) — antes dessa função existir, o pedido era apagado do banco
    mas as fotos ficavam órfãs no bucket "pedido-fotos".
    """
    try:
        fotos = listar_fotos(pedido_id)
    except Exception as e:
        return False, f"Erro ao listar fotos do pedido: {str(e)}"

    if not fotos:
        return True, ""

    try:
        s3_client = _get_s3_client()
    except Exception:
        s3_client = None  # segue tentando limpar os registros no banco mesmo sem conseguir falar com o R2

    erros = []
    for foto in fotos:
        caminho = foto.get("arquivo")
        if s3_client and caminho:
            try:
                s3_client.delete_object(Bucket="pedido-fotos", Key=caminho)
            except Exception as e:
                erros.append(f"Falha ao apagar {caminho} do bucket: {str(e)}")

    try:
        supabase.table("pedido_fotos").delete().eq("pedido_id", pedido_id).execute()
    except Exception as e:
        erros.append(f"Falha ao limpar registros no banco: {str(e)}")

    if erros:
        return False, " | ".join(erros)
    return True, ""
