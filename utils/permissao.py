import streamlit as st

# =====================================================
# VERIFICA LOGIN (Rápido e Limpo)
# =====================================================

def verificar_login():
    # Se a memória da sessão caiu (reconexão do Streamlit), tenta restaurar
    # a partir do cookie salvo no navegador antes de jogar pro login de novo.
    if not st.session_state.get("usuario"):
        from utils.cookie_auth import restaurar_sessao_cookie
        restaurar_sessao_cookie()

    if not st.session_state.get("usuario"):
        st.switch_page("pages/99_Admin.py")

# =====================================================
# USUÁRIO ATUAL
# =====================================================

def usuario_atual():
    verificar_login()
    return st.session_state.get("usuario")

# =====================================================
# EXIGIR PERFIL
# =====================================================

def exigir_perfil(perfis_permitidos):
    usuario = usuario_atual()
    
    if not usuario:
        st.stop()
        
    perfil = usuario.get("perfil")

    if perfil not in perfis_permitidos:
        st.error("Você não possui permissão para acessar este módulo.")
        st.stop()

# =====================================================
# SOMENTE ADMINISTRADOR
# =====================================================

def administrador():
    exigir_perfil(["Administrador"])

# =====================================================
# ADMINISTRADOR OU OPERADOR
# =====================================================

def administrador_operador():
    exigir_perfil(["Administrador", "Operador"])
