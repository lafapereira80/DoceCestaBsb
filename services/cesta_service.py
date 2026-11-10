import io
import mimetypes
import streamlit as st
import boto3
from config.db import supabase
import uuid
import time

class CestaService:
    @staticmethod
    def _execute_with_retry(func, max_retries=3, delay=1.5):
        """Executa consultas com retries progressivos para lidar com instabilidades ou Cold Start."""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(delay * (attempt + 1))

    # =====================================================
    # INICIALIZAR CLIENTE S3 (CLOUDFLARE R2)
    # =====================================================
    @staticmethod
    def _get_s3_client():
        return boto3.client(
            's3',
            endpoint_url=st.secrets["cloudflare"]["endpoint_url"],
            aws_access_key_id=st.secrets["cloudflare"]["access_key_id"],
            aws_secret_access_key=st.secrets["cloudflare"]["secret_access_key"],
            region_name="auto"
        )

    # =====================================================
    # LISTAR CESTAS
    # =====================================================
    @classmethod
    def listar_cestas(cls):
        def query():
            return (
                supabase
                .table("cestas")
                .select("*")
                .order("ordem", desc=False)
                .order("nome", desc=False)
                .execute()
            )
        resposta = cls._execute_with_retry(query)
        return resposta.data or []

    # =====================================================
    # UPLOAD IMAGEM DA CESTA (CLOUDFLARE R2)
    # =====================================================
    @staticmethod
    def _otimizar_imagem(arquivo, lado_max=1600):
        """Devolve (bytes, extensão, content_type). Se o Pillow falhar, envia o arquivo original."""
        if hasattr(arquivo, "seek"):
            arquivo.seek(0)
        bruto = arquivo.getvalue() if hasattr(arquivo, "getvalue") else arquivo.read()
        ext_orig = (arquivo.name.rsplit(".", 1)[-1] if "." in arquivo.name else "jpg").lower()
        tipo_orig = getattr(arquivo, "type", "") or mimetypes.guess_type(arquivo.name)[0] or "image/jpeg"
        try:
            from PIL import Image, ImageOps
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(bruto)))
            img.thumbnail((lado_max, lado_max))
            buf = io.BytesIO()
            if ext_orig == "png" and img.mode in ("RGBA", "LA", "P"):
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue(), "png", "image/png"
            if ext_orig == "webp":
                img.convert("RGB").save(buf, format="WEBP", quality=85)
                return buf.getvalue(), "webp", "image/webp"
            img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
            return buf.getvalue(), "jpg", "image/jpeg"
        except Exception:
            return bruto, ext_orig, tipo_orig


    @classmethod
    def upload_imagem_cesta(cls, arquivo):
        if arquivo is None:
            return None

        try:
            # Redimensiona/comprime fotos grandes de celular antes de enviar ao R2
            conteudo, extensao, tipo = cls._otimizar_imagem(arquivo)
            nome_arquivo = f"{uuid.uuid4()}.{extensao}"
            caminho = f"{nome_arquivo}"

            s3_client = cls._get_s3_client()
            url_base_r2 = st.secrets["r2_urls"]["cestas"].rstrip("/")
            nome_bucket = "cestas"

            s3_client.upload_fileobj(
                io.BytesIO(conteudo),
                nome_bucket,
                caminho,
                ExtraArgs={"ContentType": tipo}
            )

            url_publica = f"{url_base_r2}/{caminho}"
            return url_publica

        except Exception as erro:
            raise Exception(f"Erro no upload da imagem da cesta: {erro}")

    # =====================================================
    # CADASTRAR CESTA COM REORDENAÇÃO EM CASCATA
    # =====================================================
    @classmethod
    def cadastrar_cesta(cls, dados: dict):
        ordem = int(dados.get("ordem") or 1)
        cestas_existentes = cls.listar_cestas()

        for c in cestas_existentes:
            if c.get("ordem", 0) >= ordem:
                supabase.table("cestas").update({"ordem": c.get("ordem", 0) + 1}).eq("id", c["id"]).execute()

        dados_finais = {**dados, "ordem": ordem}
        dados_finais.setdefault("ativa", True)

        resposta = supabase.table("cestas").insert(dados_finais).execute()
        return resposta.data

    # =====================================================
    # EXCLUIR CESTA
    # =====================================================
    @staticmethod
    def excluir_cesta(cesta_id):
        supabase.table("cestas").delete().eq("id", cesta_id).execute()

    # =====================================================
    # ALTERAR STATUS
    # =====================================================
    @staticmethod
    def alterar_status_cesta(cesta_id, ativa):
        supabase.table("cestas").update({"ativa": ativa}).eq("id", cesta_id).execute()

    # =====================================================
    # BUSCAR CESTA
    # =====================================================
    @classmethod
    def buscar_cesta(cls, cesta_id):
        def query():
            return (
                supabase
                .table("cestas")
                .select("*")
                .eq("id", cesta_id)
                .single()
                .execute()
            )
        resposta = cls._execute_with_retry(query)
        return resposta.data

    # =====================================================
    # ATUALIZAR CESTA COM REORDENAÇÃO EM CASCATA
    # =====================================================
    @classmethod
    def atualizar_cesta(cls, cesta_id, dados: dict):
        ordem = dados.get("ordem")
        if ordem is not None:
            ordem = int(ordem)
            cestas_existentes = cls.listar_cestas()
            for c in cestas_existentes:
                if c["id"] != cesta_id and c.get("ordem", 0) >= ordem:
                    supabase.table("cestas").update({"ordem": c.get("ordem", 0) + 1}).eq("id", c["id"]).execute()
            dados = {**dados, "ordem": ordem}

        supabase.table("cestas").update(dados).eq("id", cesta_id).execute()
        return True

    # =====================================================
    # REMOVER IMAGEM DA CESTA (CLOUDFLARE R2)
    # =====================================================
    @classmethod
    def remover_imagem_cesta(cls, cesta_id, imagem_url=None):
        try:
            if not imagem_url:
                cesta = cls.buscar_cesta(cesta_id)
                if cesta and cesta.get("imagem"):
                    imagem_url = cesta["imagem"]

            if imagem_url:
                nome_arquivo = str(imagem_url).split("/")[-1]
                try:
                    s3_client = cls._get_s3_client()
                    s3_client.delete_object(Bucket="cestas", Key=nome_arquivo)
                except Exception as e:
                    print(f"Aviso: Não foi possível apagar a imagem no R2: {e}")
                    
        except Exception as e:
            print(f"Erro ao tentar remover arquivo físico: {e}")
            pass  

        supabase.table("cestas").update({"imagem": None}).eq("id", cesta_id).execute()
        return True


# =====================================================
# ALIASES DE COMPATIBILIDADE (Para manter telas antigas funcionando)
# =====================================================
listar_cestas = CestaService.listar_cestas
upload_imagem_cesta = CestaService.upload_imagem_cesta
cadastrar_cesta = CestaService.cadastrar_cesta
excluir_cesta = CestaService.excluir_cesta
alterar_status_cesta = CestaService.alterar_status_cesta
buscar_cesta = CestaService.buscar_cesta
buscar_cesta_por_id = CestaService.buscar_cesta
atualizar_cesta = CestaService.atualizar_cesta
remover_imagem_cesta = CestaService.remover_imagem_cesta
deletar_imagem_cesta = CestaService.remover_imagem_cesta
