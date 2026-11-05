import streamlit as st
import pandas as pd
from config.db import supabase
from utils.menu import configurar_pagina, menu_lateral
from utils.permissao import administrador_operador

st.set_page_config(page_title="Seções da Vitrine", page_icon="🖥️", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

if "secao_confirmar_exclusao" not in st.session_state:
    st.session_state["secao_confirmar_exclusao"] = None

st.markdown("""
<style>
.app-header { font-size: clamp(24px, 4vw, 32px); font-weight: 800; color: #0F172A; margin-top: 10px; margin-bottom: 5px; letter-spacing: -1px; }
.app-sub { font-size: 15px; color: #64748B; margin-bottom: 25px; font-weight: 500; }
div[data-testid="stVerticalBlockBorderWrapper"] { background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-radius: 24px !important; padding: 24px !important; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02) !important; margin-bottom: 24px !important; }
.stTextInput>div>div>input, .stNumberInput>div>div>input { border-radius: 12px !important; border: 1px solid #E2E8F0 !important; background-color: #F8FAFC !important; color: #1E293B !important; }
div[data-testid="stFormSubmitButton"] button, div[data-testid="stButton"] button { border-radius: 12px !important; font-weight: 700 !important; }
div[data-testid="stFormSubmitButton"] button[kind="primary"] { background: #10B981 !important; color: white !important; border: none !important; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.2) !important; }
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(16, 185, 129, 0.3) !important; }

@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 18px !important; }
}

@media (max-width: 640px) {
    .block-container { padding-left: .8rem !important; padding-right: .8rem !important; padding-top: 1rem !important; }
    .app-sub { font-size: 13px; margin-bottom: 16px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px !important; border-radius: 18px !important; }
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header">🖥️ Seções da Vitrine</div><div class="app-sub">Crie e organize as abas do seu catálogo público separadas por público-alvo (CPF e CNPJ).</div>', unsafe_allow_html=True)

MAPA_PUBLICO_ROTULO = {
    "AMBOS": "Ambos (PF e PJ)",
    "PF": "Pessoa Física (CPF - Início)",
    "PJ": "Corporativo (CNPJ - B2B)"
}

aba_lista, aba_nova = st.tabs(["📋 Abas Cadastradas", "➕ Criar Nova Aba"])

with aba_nova:
    with st.container(border=True):
        st.markdown('<div style="font-weight: 700; color: #1E293B; margin-bottom: 15px;">✨ Configurar Nova Seção</div>', unsafe_allow_html=True)
        with st.form("form_nova_secao", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome da Aba *", placeholder="Ex: Cestas Corporativas / Cestas de Café")
                publico_rotulo = st.selectbox("Público-Alvo da Aba *", list(MAPA_PUBLICO_ROTULO.values()), index=0)
                ativa = st.checkbox("Aba Ativa (Aparece no site)?", value=True)
            with col2:
                ordem = st.number_input("Ordem de Exibição", min_value=1, step=1, value=1, help="1 aparece primeiro (mais à esquerda).")
            
            st.write("")
            if st.form_submit_button("✅ Adicionar à Vitrine", type="primary", use_container_width=True):
                if not nome.strip():
                    st.error("O nome da seção é obrigatório!")
                else:
                    publico_chave = [k for k, v in MAPA_PUBLICO_ROTULO.items() if v == publico_rotulo][0]
                    try:
                        supabase.table("vitrine_secoes").insert({
                            "nome": nome.strip(), 
                            "ordem": ordem, 
                            "ativa": ativa,
                            "publico": publico_chave
                        }).execute()
                        st.success(f"Aba '{nome}' criada com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        try:
                            supabase.table("vitrine_secoes").insert({
                                "nome": nome.strip(), 
                                "ordem": ordem, 
                                "ativa": ativa
                            }).execute()
                            st.success(f"Aba '{nome}' criada com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as ex:
                            st.error("Erro ao salvar. Verifique se o nome já existe.")

with aba_lista:
    try:
        secoes = supabase.table("vitrine_secoes").select("*").order("ordem").execute().data or []
    except Exception:
        secoes = []
        
    if not secoes:
        st.info("Nenhuma seção cadastrada.")
    else:
        df_secoes = []
        for s in secoes:
            pub_cod = s.get("publico") or "AMBOS"
            df_secoes.append({
                "Posição": s.get("ordem", 1),
                "Nome da Aba": s.get("nome", ""),
                "Público-Alvo": MAPA_PUBLICO_ROTULO.get(pub_cod, "Ambos (PF e PJ)"),
                "Ativa no Site?": "Sim" if s.get("ativa") else "Não",
                "id": s.get("id")
            })
            
        df_display = pd.DataFrame(df_secoes)[["Posição", "Nome da Aba", "Público-Alvo", "Ativa no Site?"]]
        
        with st.container(border=True):
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
        st.markdown('<div style="font-weight: 700; color: #1E293B; margin-top: 20px; margin-bottom: 10px;">✏️ Editar ou Excluir</div>', unsafe_allow_html=True)
        with st.container(border=True):
            secao_selecionada = st.selectbox("Selecione a aba", secoes, format_func=lambda x: f"{x['nome']} ({MAPA_PUBLICO_ROTULO.get(x.get('publico', 'AMBOS'), 'Ambos')})")
            
            if secao_selecionada:
                pub_atual_cod = secao_selecionada.get("publico") or "AMBOS"
                pub_atual_rotulo = MAPA_PUBLICO_ROTULO.get(pub_atual_cod, MAPA_PUBLICO_ROTULO["AMBOS"])
                idx_pub_atual = list(MAPA_PUBLICO_ROTULO.values()).index(pub_atual_rotulo)

                with st.form("form_editar_secao"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_nome = st.text_input("Nome", value=secao_selecionada["nome"])
                        e_publico_rotulo = st.selectbox("Público-Alvo", list(MAPA_PUBLICO_ROTULO.values()), index=idx_pub_atual)
                        e_ativa = st.checkbox("Ativa?", value=bool(secao_selecionada["ativa"]))
                    with e_col2:
                        e_ordem = st.number_input("Ordem", value=int(secao_selecionada["ordem"]), step=1)
                    
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        salvar_secao = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
                    with c_btn2:
                        pedir_exclusao = st.form_submit_button("🗑️ Excluir Aba", use_container_width=True)

                    if salvar_secao:
                        e_publico_chave = [k for k, v in MAPA_PUBLICO_ROTULO.items() if v == e_publico_rotulo][0]
                        try:
                            supabase.table("vitrine_secoes").update({
                                "nome": e_nome.strip(), 
                                "ordem": e_ordem, 
                                "ativa": e_ativa,
                                "publico": e_publico_chave
                            }).eq("id", secao_selecionada["id"]).execute()
                            st.success("Atualizado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception:
                            try:
                                supabase.table("vitrine_secoes").update({
                                    "nome": e_nome.strip(), 
                                    "ordem": e_ordem, 
                                    "ativa": e_ativa
                                }).eq("id", secao_selecionada["id"]).execute()
                                st.success("Atualizado com sucesso!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception:
                                st.error("Erro ao atualizar.")

                    if pedir_exclusao:
                        st.session_state["secao_confirmar_exclusao"] = secao_selecionada["id"]
                        st.rerun()

                if st.session_state.get("secao_confirmar_exclusao") == secao_selecionada["id"]:
                    st.warning(f"⚠️ Confirma excluir a aba **{secao_selecionada['nome']}**? Isso não pode ser desfeito.")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Sim, excluir aba", key=f"conf_del_secao_{secao_selecionada['id']}", use_container_width=True, type="primary"):
                            try:
                                supabase.table("vitrine_secoes").delete().eq("id", secao_selecionada["id"]).execute()
                                st.session_state["secao_confirmar_exclusao"] = None
                                st.warning("Aba excluída!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception:
                                st.error("Erro: existem cestas vinculadas a esta aba. Altere as cestas antes de excluir.")
                    with cc2:
                        if st.button("❌ Cancelar", key=f"canc_del_secao_{secao_selecionada['id']}", use_container_width=True):
                            st.session_state["secao_confirmar_exclusao"] = None
                            st.rerun()
