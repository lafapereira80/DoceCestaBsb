import html
import streamlit as st

from services.usuario_service import (
    listar_usuarios,
    salvar_usuario,
    excluir_usuario,
    atualizar_usuario
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
    page_title="Gestão de Usuários",
    page_icon="👤",
    layout="wide"
)

configurar_pagina()
menu_lateral()
administrador()

usuario_logado = st.session_state.usuario


# =====================================================
# CONTROLE DE EDIÇÃO / EXCLUSÃO
# =====================================================

if "usuario_editando" not in st.session_state:
    st.session_state["usuario_editando"] = None


# =====================================================
# CSS PREMIUM E RESPONSIVIDADE MOBILE
# =====================================================

st.markdown(
"""
<style>
:root {
    --ink: #2c1e14;
    --brand: #5a3b28;
    --muted: #775a46;
    --border: #e8ddd3;
    --bg-soft: #faf7f3;
}

/* =========================================
   CONFIGURAÇÃO GERAL E ESPAÇAMENTOS
========================================== */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1150px;
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
   MÉTRICAS RÁPIDAS
========================================== */
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 6px; }
.metric-box {
    background: #fff; border: 1px solid var(--border); border-radius: 14px;
    padding: 14px 16px; display: flex; align-items: center; gap: 12px;
    box-shadow: 0 2px 8px rgba(90,59,40,.03); min-width: 0;
}
.metric-icon { font-size: 22px; flex-shrink: 0; }
.metric-num { font-size: 20px; font-weight: 800; color: var(--ink); line-height: 1; }
.metric-label { font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* =========================================
   ACORDEÃO (EXPANDER) "NOVO USUÁRIO"
========================================== */
div[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 15px rgba(90, 59, 40, 0.05) !important;
    overflow: hidden;
    margin-bottom: 25px;
}
div[data-testid="stExpander"] summary {
    background: var(--bg-soft);
    padding: 15px 20px !important;
    font-size: 16px !important;
    font-weight: 800 !important;
    color: var(--brand) !important;
    transition: all 0.3s ease;
}
div[data-testid="stExpander"] summary:hover {
    background: #f3ece6;
}
div[data-testid="stExpanderDetails"] {
    padding: 20px !important;
}

/* =========================================
   CARDS DE USUÁRIOS
========================================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    margin-bottom: 10px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #d2bfae !important;
    box-shadow: 0 8px 20px rgba(90, 59, 40, 0.08);
    transform: translateY(-2px);
}

/* Alinhamento vertical Desktop */
@media (min-width: 641px) {
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }
}

/* =========================================
   AVATAR DO USUÁRIO
========================================== */
.user-row { display: flex; align-items: center; gap: 10px; min-width: 0; }
.user-row > div:last-child { min-width: 0; overflow: hidden; }
.avatar-user {
    width: 36px; height: 36px; border-radius: 10px; background: var(--brand); color: #fff;
    display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px;
    flex-shrink: 0;
}

/* =========================================
   ELEMENTOS DE TEXTO & BADGES
========================================== */
.user-title {
    font-weight: 800;
    color: var(--ink);
    font-size: 16px !important;
    margin-bottom: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
}

.badge-admin { background-color: #fef7e0; color: #b06000; border: 1px solid #fce8b2; }
.badge-operador { background-color: #e8f0fe; color: #1a73e8; border: 1px solid #d2e3fc; }
.badge-entregador { background-color: #f3e8fd; color: #6a1b9a; border: 1px solid #e9d2fd; }
.badge-self { background-color: #e6f4ea; color: #137333; border: 1px solid #ceead6; }

.badge-admin, .badge-operador, .badge-entregador, .badge-self {
    display: inline-block;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}

.user-date {
    font-size: 12px;
    color: #666;
    font-weight: 600;
}

/* =========================================
   BOTÕES DE AÇÃO NA TABELA
========================================== */
div[data-testid="stColumn"] div[data-testid="stButton"] button {
    font-size: 15px !important;
    padding: 4px 6px !important;
    border-radius: 10px !important;
    min-height: 38px !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-soft) !important;
    transition: all 0.2s ease;
}
div[data-testid="stColumn"] div[data-testid="stButton"] button:hover {
    background: var(--border) !important;
    transform: scale(1.05);
}

/* =========================================
   RESPONSIVIDADE — TABLET (≤ 1024px)
========================================== */
@media (max-width: 1024px) {
    .metrics-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
}

/* =========================================
   RESPONSIVIDADE MOBILE E BOTÕES (LADO A LADO)
========================================== */
@media (max-width: 768px) {
    h1 { font-size: 24px !important; }

    .metrics-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .metric-box { padding: 10px 12px; gap: 8px; }
    .metric-icon { font-size: 18px; }
    .metric-num { font-size: 16px; }
    .metric-label { font-size: 9.5px; }

    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 12px !important; }
    .avatar-user { width: 32px; height: 32px; font-size: 12px; }
    .user-title { font-size: 14px !important; }
    .user-date { margin-top: 4px; }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
        margin-top: 10px !important;
        justify-content: space-between;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) > div[data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) button {
        width: 100% !important;
        padding: 6px 0px !important;
    }
}

/* =========================================
   RESPONSIVIDADE — CELULAR PEQUENO (≤ 480px)
========================================== */
@media (max-width: 480px) {
    div[data-testid="stExpander"] summary { padding: 12px 14px !important; font-size: 14px !important; }
    div[data-testid="stExpanderDetails"] { padding: 14px !important; }
}
</style>
""",
unsafe_allow_html=True
)


# =====================================================
# TÍTULO E CABEÇALHO
# =====================================================

col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    page_header("Usuários", "Quem acessa o painel e com qual perfil.", "🔑", ["Sistema", "Usuários"], "violet")
    st.caption("Administre as contas de acesso da equipe e defina o perfil de permissões de cada um.")


# =====================================================
# NOVO USUÁRIO (MODELO EXPANDER)
# =====================================================

with st.expander("✨ Cadastrar Novo Usuário", expanded=False):
    col_n1, col_n2, col_n3 = st.columns([1.5, 1.5, 1])

    with col_n1:
        novo_login = st.text_input("Login de Acesso", key="novo_login", placeholder="Ex: joao.silva")

    with col_n2:
        nova_senha = st.text_input("Senha", type="password", key="nova_senha", placeholder="••••••••")

    with col_n3:
        novo_perfil = st.selectbox("Perfil de Permissão", ["Administrador", "Operador", "Entregador"], key="novo_perfil")

    st.write("")
    if st.button("💾 Adicionar Usuário ao Sistema", use_container_width=True, type="primary"):
        login_normalizado = novo_login.strip()
        senha_normalizada = nova_senha.strip()

        if not login_normalizado:
            st.error("Informe o login.")
            st.stop()

        if not senha_normalizada:
            st.error("Informe a senha.")
            st.stop()

        if len(senha_normalizada) < 4:
            st.error("A senha deve ter pelo menos 4 caracteres.")
            st.stop()

        sucesso, mensagem = salvar_usuario(
            login_normalizado,
            senha_normalizada,
            novo_perfil
        )

        if sucesso:
            st.success("✅ Usuário cadastrado com sucesso!")
            st.rerun()
        else:
            st.error(mensagem)


# =====================================================
# LISTAGEM DE USUÁRIOS (CARDS PREMIUM)
# =====================================================

st.write("")
st.subheader("📋 Usuários Cadastrados")

try:
    usuarios = listar_usuarios()
except Exception as erro:
    st.error(f"Erro ao carregar usuários: {erro}")
    st.stop()

if not usuarios:
    st.info("Nenhum usuário cadastrado.")
    st.stop()

# --- Métricas rápidas por perfil (grid único, reflow controlado por CSS) ---
qtd_admin = sum(1 for u in usuarios if u.get("perfil") == "Administrador")
qtd_operador = sum(1 for u in usuarios if u.get("perfil") == "Operador")
qtd_entregador = sum(1 for u in usuarios if u.get("perfil") == "Entregador")

metricas = [
    ("👥", len(usuarios), "Total"),
    ("👑", qtd_admin, "Administradores"),
    ("👤", qtd_operador, "Operadores"),
    ("🛵", qtd_entregador, "Entregadores"),
]
metrics_html = "<div class='metrics-grid'>" + "".join(
    f"""<div class="metric-box">
        <div class="metric-icon">{icone}</div>
        <div>
            <div class="metric-num">{num}</div>
            <div class="metric-label">{label}</div>
        </div>
    </div>"""
    for icone, num, label in metricas
) + "</div>"
st.markdown(metrics_html, unsafe_allow_html=True)

st.write("")

# --- Busca rápida ---
busca = st.text_input("Buscar usuário", placeholder="🔎 Buscar por login...", label_visibility="collapsed")
if busca:
    termo = busca.strip().lower()
    usuarios = [u for u in usuarios if termo in str(u.get("login", "")).lower()]
    if not usuarios:
        st.info("Nenhum usuário encontrado para essa busca.")
        st.stop()

st.write("")

perfis_disponiveis = ["Administrador", "Operador", "Entregador"]

for usuario in usuarios:
    usuario_id = usuario["id"]
    login = usuario["login"]
    perfil = usuario["perfil"]
    data_criacao = str(usuario.get("created_at", "-"))[:10]

    eh_conta_atual = (login == usuario_logado["login"])

    login_seguro = html.escape(str(login))
    inicial = login_seguro[0].upper() if login_seguro else "?"

    with st.container(border=True):
        # Separação clara de colunas
        col_info, col_perfil, col_data, col_acoes = st.columns([3, 2.5, 2, 1.5])

        # Coluna 1: Avatar + Login e Tag de Conta Atual (CORRIGIDA)
        with col_info:
            tag_conta = '<span class="badge-self">🔒 Conta Atual</span>' if eh_conta_atual else ''
            st.markdown(
                f'<div class="user-row"><div class="avatar-user">{inicial}</div><div><div class="user-title">{login_seguro}</div>{tag_conta}</div></div>', 
                unsafe_allow_html=True
            )

        # Coluna 2: Perfil (Badge Visual)
        with col_perfil:
            if perfil == "Administrador":
                st.markdown('<span class="badge-admin">👑 Administrador</span>', unsafe_allow_html=True)
            elif perfil == "Entregador":
                st.markdown('<span class="badge-entregador">🛵 Entregador</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge-operador">👤 Operador</span>', unsafe_allow_html=True)

        # Coluna 3: Data
        with col_data:
            if data_criacao != "-":
                data_fmt = f"{data_criacao[8:10]}/{data_criacao[5:7]}/{data_criacao[0:4]}"
                st.markdown(f'<div class="user-date">🗓️ Criado em: {data_fmt}</div>', unsafe_allow_html=True)

        # Coluna 4: Botões de Ação (Linha)
        with col_acoes:
            col_b1, col_b2 = st.columns(2)

            with col_b1:
                if st.button("✏️", key=f"btn_edit_{usuario_id}", help="Editar Usuário", use_container_width=True):
                    st.session_state["usuario_editando"] = usuario_id
                    st.rerun()

            with col_b2:
                # Impede abrir exclusão da conta atual
                desabilitar_exclusao = eh_conta_atual
                if st.button("🗑️", key=f"btn_del_{usuario_id}", help="Excluir Usuário", disabled=desabilitar_exclusao, use_container_width=True):
                    st.session_state["usuario_editando"] = f"del_{usuario_id}"
                    st.rerun()

        # =====================================================
        # FORMULÁRIO DE EDIÇÃO INLINE
        # =====================================================
        if st.session_state["usuario_editando"] == usuario_id:
            st.write("")
            with st.container(border=True):
                st.markdown("<div style='font-size: 14px; font-weight: 800; color: #5a3b28; margin-bottom: 10px;'>✏️ Editando Usuário</div>", unsafe_allow_html=True)

                with st.form(key=f"form_edicao_{usuario_id}"):
                    col_e1, col_e2, col_e3 = st.columns([1.5, 1.5, 1])

                    with col_e1:
                        editar_login = st.text_input("Login", value=login)

                    with col_e2:
                        editar_senha = st.text_input("Nova senha (deixe vazio para manter atual)", type="password")

                    with col_e3:
                        index_perfil = perfis_disponiveis.index(perfil) if perfil in perfis_disponiveis else 1
                        editar_perfil = st.selectbox("Perfil", perfis_disponiveis, index=index_perfil)

                    st.write("")
                    col_salvar, col_cancelar = st.columns(2)

                    with col_salvar:
                        salvar = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)

                    with col_cancelar:
                        cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    if salvar:
                        senha_normalizada = editar_senha.strip()

                        if not editar_login.strip():
                            st.error("Informe o login.")
                        elif senha_normalizada and len(senha_normalizada) < 4:
                            st.error("A senha deve ter pelo menos 4 caracteres.")
                        else:
                            try:
                                sucesso, mensagem = atualizar_usuario(
                                    usuario_id,
                                    editar_login.strip(),
                                    senha_normalizada,
                                    editar_perfil
                                )
                                if sucesso:
                                    st.session_state["usuario_editando"] = None
                                    st.success("✅ Usuário atualizado!")
                                    st.rerun()
                                else:
                                    st.error(mensagem)
                            except Exception as erro:
                                st.error(f"Erro ao atualizar: {erro}")

                    if cancelar:
                        st.session_state["usuario_editando"] = None
                        st.rerun()

        # =====================================================
        # CONFIRMAÇÃO DE EXCLUSÃO INLINE
        # =====================================================
        elif st.session_state["usuario_editando"] == f"del_{usuario_id}":
            st.write("")
            with st.container(border=True):
                st.error(f"⚠️ Atenção! Deseja realmente excluir o usuário **{login_seguro}**?")
                col_confirmar, col_cancelar = st.columns(2)

                with col_confirmar:
                    if st.button("✅ Sim, Excluir", key=f"confirmar_excluir_{usuario_id}", use_container_width=True, type="primary"):
                        sucesso, mensagem = excluir_usuario(usuario_id)
                        if sucesso:
                            st.toast("✅ Usuário excluído com sucesso!")
                            st.session_state["usuario_editando"] = None
                            st.rerun()
                        else:
                            st.error(mensagem)

                with col_cancelar:
                    if st.button("❌ Cancelar", key=f"cancelar_excluir_{usuario_id}", use_container_width=True):
                        st.session_state["usuario_editando"] = None
                        st.rerun()


# =====================================================
# RODAPÉ E BOTÃO DE VOLTAR
# =====================================================

st.write("")
st.divider()

col_v1, col_v2, col_v3 = st.columns([1, 2, 1])
with col_v2:
    if st.button("⬅ Voltar ao Painel Administrativo", use_container_width=True):
        st.switch_page("pages/99_Admin.py")

st.write("")
st.caption("👥 Controle de Acessos - Doce Cesta Brasília")
