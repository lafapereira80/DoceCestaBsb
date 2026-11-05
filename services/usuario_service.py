import bcrypt

from config.db import supabase


# =====================================================
# HELPERS DE SENHA (hash bcrypt + compatibilidade com
# senhas antigas gravadas em texto puro)
# =====================================================

def _gerar_hash_senha(senha_texto_puro):
    """Gera um hash bcrypt para a senha informada."""
    return bcrypt.hashpw(senha_texto_puro.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _eh_hash_bcrypt(valor):
    """Identifica se o valor salvo no banco já é um hash bcrypt."""
    return isinstance(valor, str) and valor.startswith(("$2a$", "$2b$", "$2y$"))


def _senha_confere(senha_texto_puro, valor_armazenado):
    """
    Verifica a senha digitada contra o valor salvo no banco.
    Suporta tanto hashes bcrypt (novo padrão) quanto senhas antigas
    em texto puro (para não quebrar contas já existentes).
    """
    if not valor_armazenado:
        return False

    if _eh_hash_bcrypt(valor_armazenado):
        try:
            return bcrypt.checkpw(senha_texto_puro.encode("utf-8"), valor_armazenado.encode("utf-8"))
        except Exception:
            return False

    # Conta antiga: senha ainda em texto puro no banco
    return senha_texto_puro == valor_armazenado


# =====================================================
# AUTENTICA USUÁRIO
# =====================================================

def autenticar_usuario(login, senha):
    try:
        resposta = supabase.table("usuarios").select("*").eq("login", login).execute()

        if not resposta.data:
            return None

        usuario = resposta.data[0]
        senha_armazenada = usuario.get("senha", "")

        if not _senha_confere(senha, senha_armazenada):
            return None

        # Migração automática e transparente: se a senha ainda estava em
        # texto puro e o login deu certo, já salva como hash bcrypt agora.
        if not _eh_hash_bcrypt(senha_armazenada):
            try:
                novo_hash = _gerar_hash_senha(senha)
                supabase.table("usuarios").update({"senha": novo_hash}).eq("id", usuario["id"]).execute()
                usuario["senha"] = novo_hash
            except Exception:
                # Se a migração falhar por qualquer motivo, o login não é bloqueado.
                pass

        return usuario

    except Exception as erro:
        raise Exception(f"Erro na autenticação: {erro}")


# =====================================================
# BUSCAR USUÁRIO PELO LOGIN
# =====================================================

def buscar_usuario_por_login(login):
    try:
        resposta = supabase.table("usuarios").select("*").eq("login", login).execute()

        if resposta.data:
            return resposta.data[0]

        return None

    except Exception as erro:
        raise Exception(f"Erro ao buscar usuário: {erro}")


# =====================================================
# LISTAR USUÁRIOS
# =====================================================

def listar_usuarios():
    try:
        resposta = supabase.table("usuarios").select("*").order("created_at", desc=True).execute()
        return resposta.data or []

    except Exception as erro:
        raise Exception(f"Erro ao listar usuários: {erro}")


# =====================================================
# SALVAR USUÁRIO
# =====================================================

def salvar_usuario(login, senha, perfil):
    try:
        # verifica se já existe
        usuario_existente = buscar_usuario_por_login(login)

        if usuario_existente:
            return False, "Este login já existe."

        resposta = (
            supabase
            .table("usuarios")
            .insert({
                "login": login,
                "senha": _gerar_hash_senha(senha),
                "perfil": perfil,
            })
            .execute()
        )

        return True, resposta.data

    except Exception as erro:
        return False, str(erro)


# =====================================================
# ATUALIZAR USUÁRIO
# =====================================================

def atualizar_usuario(usuario_id, login, senha, perfil):
    try:
        dados_atualizacao = {
            "login": login,
            "perfil": perfil,
        }

        # Só mexe na senha se uma nova foi realmente informada.
        # Isso evita apagar a senha atual quando o campo é deixado em branco
        # (o formulário promete "deixe vazio para manter atual").
        if senha:
            dados_atualizacao["senha"] = _gerar_hash_senha(senha)

        resposta = (
            supabase
            .table("usuarios")
            .update(dados_atualizacao)
            .eq("id", usuario_id)
            .execute()
        )

        return True, resposta.data

    except Exception as erro:
        return False, str(erro)


# =====================================================
# EXCLUIR USUÁRIO
# =====================================================

def excluir_usuario(usuario_id):
    try:
        supabase.table("usuarios").delete().eq("id", usuario_id).execute()
        return True, "Usuário excluído com sucesso."

    except Exception as erro:
        return False, str(erro)
