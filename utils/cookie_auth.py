import time
import streamlit as st

try:
    from streamlit_cookies_controller import CookieController
    _COOKIES_DISPONIVEL = True
except Exception:
    _COOKIES_DISPONIVEL = False

_NOME_COOKIE = "dc_login"
_DIAS_EXPIRACAO = 7


def _obter_controller():
    """
    Uma instância do controller por SESSÃO DE NAVEGADOR (st.session_state),
    nunca compartilhada entre usuários diferentes.

    IMPORTANTE: isso não pode usar @st.cache_resource — esse cache é GLOBAL
    (compartilhado por todo o servidor, entre todos os visitantes ao mesmo
    tempo). Cachear o CookieController ali fazia com que o primeiro usuário
    a carregar a página "gravasse" sua instância pra sempre, e os visitantes
    seguintes reaproveitavam os cookies de outra pessoa — foi exatamente o
    bug que fez todo mundo aparecer logado como o mesmo Administrador.
    """
    if "_cookie_controller_instance" not in st.session_state:
        st.session_state["_cookie_controller_instance"] = CookieController()
    return st.session_state["_cookie_controller_instance"]


def salvar_sessao_cookie(login):
    """Grava o login do usuário num cookie do navegador, para sobreviver a quedas
    de conexão do Streamlit (troca de aba, celular bloqueando a tela, etc.)."""
    if not _COOKIES_DISPONIVEL:
        return
    try:
        controller = _obter_controller()
        controller.set("dc_login", login, max_age=60 * 60 * 24 * _DIAS_EXPIRACAO)
    except Exception:
        pass  # nunca deve impedir o login de funcionar


def limpar_sessao_cookie():
    """Remove o cookie de sessão (usado no logout)."""
    if not _COOKIES_DISPONIVEL:
        return
    try:
        controller = _obter_controller()
        controller.remove("dc_login")
    except Exception:
        pass


def restaurar_sessao_cookie():
    """
    Se st.session_state perdeu o usuário logado (reconexão do Streamlit após a
    aba ficar em segundo plano, celular bloqueando a tela, etc.), tenta
    reconstruir a sessão a partir do cookie salvo no navegador — sem precisar
    pedir login de novo. Não faz nada se já houver usuário na sessão atual.
    """
    if st.session_state.get("usuario"):
        return
    if not _COOKIES_DISPONIVEL:
        return
    try:
        controller = _obter_controller()
        login_salvo = controller.get("dc_login")
        if login_salvo:
            from services.usuario_service import buscar_usuario_por_login
            usuario = buscar_usuario_por_login(login_salvo)
            if usuario:
                st.session_state["usuario"] = usuario
                return

        # Na primeiríssima renderização de uma sessão nova, o valor do cookie
        # pode ainda não ter sincronizado do navegador (o componente precisa
        # de um round-trip). Dá só mais uma chance, uma única vez, antes de
        # desistir e cair na tela de login normal (evita loop de reruns).
        if not st.session_state.get("_cookie_tentativa_sync"):
            st.session_state["_cookie_tentativa_sync"] = True
            time.sleep(0.4)
            st.rerun()
    except Exception:
        pass  # se a leitura do cookie falhar, cai no fluxo normal de login
