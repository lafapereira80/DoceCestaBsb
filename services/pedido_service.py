import streamlit as st
from config.db import supabase
from services.foto_service import deletar_todas_fotos_do_pedido

# =====================================================
# LISTAR TODOS OS PEDIDOS (ATIVOS = DENTRO DO FLUXO)
# =====================================================
def listar_pedidos_ativos():
    resposta = (
        supabase
        .table("pedidos")
        .select("*")
        .neq("status", "Entregue")
        .order("created_at", desc=True)
        .execute()
    )
    return resposta.data or []


# =====================================================
# LISTAR PEDIDOS HISTÓRICOS (ENTREGUES)
# =====================================================
def listar_pedidos_historico():
    resposta = (
        supabase
        .table("pedidos")
        .select("*")
        .eq("status", "Entregue")
        .order("created_at", desc=True)
        .execute()
    )
    return resposta.data or []


# =====================================================
# SALVAR (CRIAR NOVO)
# =====================================================
def salvar_pedido(dados):
    resposta = (
        supabase
        .table("pedidos")
        .insert(dados)
        .execute()
    )
    
    if resposta.data:
        return True, resposta.data[0]["id"]
    return False, "Erro ao salvar"


# =====================================================
# BUSCAR PEDIDO POR ID
# =====================================================
def buscar_pedido(pedido_id):
    resposta = (
        supabase
        .table("pedidos")
        .select("*")
        .eq("id", pedido_id)
        .single()
        .execute()
    )
    return resposta.data


# =====================================================
# ATUALIZAR PEDIDO (DADOS GERAIS)
# =====================================================
def atualizar_pedido(pedido_id, dados):
    """Atualiza as informações de um pedido existente."""
    try:
        supabase.table("pedidos").update(dados).eq("id", pedido_id).execute()
        return True
    except Exception as erro:
        print(f"Erro ao atualizar pedido: {erro}")
        return False


# =====================================================
# ATUALIZAR ANOTAÇÃO INTERNA DO PEDIDO
# =====================================================
def atualizar_anotacao_pedido(pedido_id, anotacao):
    """Atualiza especificamente o campo de anotações internas."""
    try:
        supabase.table("pedidos").update({"anotacoes_internas": anotacao}).eq("id", pedido_id).execute()
        return True
    except Exception as erro:
        print(f"Erro ao atualizar anotação: {erro}")
        return False


# =====================================================
# ATUALIZAR STATUS (MUDANÇA DE ESTÁGIO)
# =====================================================
def atualizar_status(pedido_id, novo_status):
    """
    Se o novo status for 'Entregue', ele ativa o gatilho 
    para apagar as fotos pesadas dos clientes do Bucket 
    para economizar espaço, mantendo só o texto no histórico.
    """
    if str(novo_status).strip().capitalize() == "Entregue":
        deletar_todas_fotos_do_pedido(pedido_id)

    (
        supabase
        .table("pedidos")
        .update({"status": novo_status})
        .eq("id", pedido_id)
        .execute()
    )


# =====================================================
# EXCLUIR PEDIDO COMPLETO (DESISTÊNCIAS)
# =====================================================
def excluir_pedido_completo(pedido_id):
    """
    Exclui um pedido que estava em 'Desistência'.
    Garante que os arquivos físicos sejam excluídos do 
    servidor antes de apagar os registros de texto!
    """
    try:
        # 1. Deleta os arquivos (imagens) pesados do servidor primeiro (e também limpa a tabela de fotos)
        deletar_todas_fotos_do_pedido(pedido_id)

        # 2. Deleta os adicionais no banco
        supabase.table("pedido_adicionais").delete().eq("pedido_id", pedido_id).execute()
        
        # 3. Deleta o pedido em si (Tabela pedidos)
        supabase.table("pedidos").delete().eq("id", pedido_id).execute()
        
        return True, "Pedido e todas as fotos foram excluídos com sucesso."
    
    except Exception as e:
        return False, f"Erro ao excluir pedido: {str(e)}"
