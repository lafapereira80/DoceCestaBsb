import html

import streamlit as st

from utils.ui import tema_admin


def _esc(valor, padrao=''):
    """Escapa texto do usuário antes de inserir em blocos HTML (evita XSS/quebra de layout)."""
    texto = str(valor) if valor not in (None, '') else padrao
    return html.escape(texto)


def configurar_pagina():
    """Aplica o design system do painel (CSS + animações + paleta de comandos Ctrl K + dock mobile).
    Chamado no topo de TODAS as páginas administrativas."""
    tema_admin()


def _grupo(titulo):
    st.markdown(f'<div class="dc-nav-t">{_esc(titulo)}</div>', unsafe_allow_html=True)


def menu_lateral():
    usuario = st.session_state.get("usuario")

    with st.sidebar:
        st.markdown(
            """<div class="dc-brand"><div class="dc-brand-steam"><i></i><i></i><i></i></div>
            <div class="dc-brand-logo">Doce Cesta</div><div class="dc-brand-sub">Central de gestão</div></div>""".replace("\n", ""),
            unsafe_allow_html=True,
        )

        if usuario:
            perfil = _esc(usuario.get("perfil", "Usuário"))
            login = _esc(usuario.get("login", "Admin"))
            inicial = (login[:1] or "A").upper()
            st.markdown(
                f"""<div class="dc-user"><div class="dc-user-av">{inicial}</div>
                <div style="min-width:0"><b>{login}</b><small>{perfil}</small></div></div>""".replace("\n", ""),
                unsafe_allow_html=True,
            )

            if perfil in ["Administrador", "Operador"]:
                st.page_link("pages/99_Admin.py", label="Início", icon="🏠")

                _grupo("Operação e vendas")
                st.page_link("pages/02_Pedidos.py", label="Pedidos", icon="📋")
                st.page_link("pages/19_Pedido_Manual.py", label="Venda no balcão (PDV)", icon="🛍️")
                st.page_link("pages/18_Corporativo.py", label="Vendas B2B", icon="🏢")
                st.page_link("pages/24_Leads_Corporativos.py", label="Orçamentos B2B", icon="📨")
                st.page_link("pages/16_Previsao.py", label="Produção", icon="🏭")
                st.page_link("pages/08_Entregas.py", label="Rotas de entrega", icon="🛵")

                _grupo("Gestão e financeiro")
                st.page_link("pages/03_Clientes.py", label="Clientes", icon="👥")
                st.page_link("pages/06_Financeiro.py", label="Financeiro", icon="💰")
                st.page_link("pages/22_Cupons.py", label="Cupons", icon="🎟️")

                _grupo("Catálogo da loja")
                st.page_link("pages/04_Cestas.py", label="Cestas e kits", icon="🧺")
                st.page_link("pages/05_Produtos.py", label="Produtos e insumos", icon="🍓")
                st.page_link("pages/15_Categorias.py", label="Categorias", icon="🏷️")
                st.page_link("pages/17_Secoes_Vitrine.py", label="Seções da vitrine", icon="🖥️")

                _grupo("Sistema")
                st.page_link("pages/20_Configuracoes_Loja.py", label="Configurações da loja", icon="⚙️")
                st.page_link("pages/07_Usuarios.py", label="Usuários", icon="🔑")
                st.page_link("app.py", label="Ver a vitrine", icon="🌐")

            elif perfil == "Entregador":
                st.page_link("pages/99_Admin.py", label="Início", icon="🏠")
                _grupo("Entregador")
                st.page_link("pages/08_Entregas.py", label="Minha rota", icon="🗺️")

            st.write("")
            st.divider()

            if st.button("Sair da conta", use_container_width=True, icon="🚪"):
                from utils.cookie_auth import limpar_sessao_cookie
                limpar_sessao_cookie()
                st.session_state.clear()
                st.switch_page("app.py")
        else:
            st.info("Faça login para acessar o painel restrito.")
            st.page_link("app.py", label="Voltar para a loja", icon="🏠")
