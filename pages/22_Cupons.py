import streamlit as st
import pandas as pd
import re
from datetime import date, time, timedelta

from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador
from services.cupom_service import (
    gerar_codigo, criar_cupom, listar_cupons, alternar_ativo,
    excluir_cupom, contar_usos, listar_clientes_para_envio,
)
from services.email_service import enviar_email_cupom
from services.cesta_service import listar_cestas

st.set_page_config(page_title="Cupons de Desconto", page_icon="🎟️", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

page_header("Cupons de desconto", "Crie e acompanhe campanhas promocionais.", "🎟️", ["Gestão", "Cupons"], "violet")
st.caption("Crie códigos promocionais, controle validade/uso e envie cortesias para clientes da base.")

todas_cestas = listar_cestas()
mapa_cestas = {c["id"]: c.get("nome", f"Cesta #{c['id']}") for c in todas_cestas}

aba_criar, aba_listar, aba_enviar = st.tabs(["➕ Criar Cupom", "📋 Cupons Ativos", "🎁 Enviar Cortesia"])

# =====================================================
# ABA 1 — CRIAR CUPOM
# =====================================================
with aba_criar:
    with st.form("form_novo_cupom", clear_on_submit=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            codigo_manual = st.text_input("Código do cupom (deixe vazio para gerar automaticamente)", placeholder="ex: NATAL10")
        with col2:
            if st.form_submit_button("🎲 Gerar código sugerido", use_container_width=True):
                st.session_state["codigo_sugerido"] = gerar_codigo()
        if st.session_state.get("codigo_sugerido"):
            st.info(f"Sugestão gerada: **{st.session_state['codigo_sugerido']}** — copie para o campo acima se quiser usá-la.")

        tipo = st.selectbox(
            "Tipo de desconto",
            ["percentual", "fixo", "cortesia_total"],
            format_func=lambda t: {
                "percentual": "Percentual (%)",
                "fixo": "Valor fixo (R$)",
                "cortesia_total": "Cortesia total (pedido 100% grátis)",
            }[t],
        )

        valor = 0.0
        if tipo == "percentual":
            valor = st.number_input("Percentual de desconto (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
        elif tipo == "fixo":
            valor = st.number_input("Valor do desconto (R$)", min_value=1.0, value=10.0, step=1.0)

        st.markdown("**Período de validade**")
        col3, col4 = st.columns(2)
        with col3:
            valido_de = st.date_input("Válido a partir de", value=date.today(), format="DD/MM/YYYY")
            hora_inicio = st.time_input("Horário de início", value=time(0, 0), step=300)
        with col4:
            valido_ate = st.date_input("Válido até", value=date.today() + timedelta(days=30), format="DD/MM/YYYY")
            hora_fim = st.time_input("Horário de término", value=time(23, 59), step=300)

        col5, col6 = st.columns(2)
        with col5:
            limite_usos = st.number_input("Limite total de usos", min_value=1, value=50, step=1)
        with col6:
            limite_por_cliente = st.number_input("Limite de usos por cliente", min_value=1, value=1, step=1)

        valor_minimo = st.number_input("Valor mínimo do pedido para usar (R$)", min_value=0.0, value=0.0, step=5.0)

        st.markdown("**Restringir a cestas específicas (opcional)**")
        cestas_restritas = st.multiselect(
            "Deixe vazio para o cupom valer em qualquer cesta",
            options=list(mapa_cestas.keys()),
            format_func=lambda cid: mapa_cestas.get(cid, f"#{cid}"),
        )

        descricao = st.text_area("Descrição interna (não aparece pro cliente)", placeholder="ex: campanha de Natal 2026")

        enviar = st.form_submit_button("✅ Criar Cupom", type="primary", use_container_width=True)

        if enviar:
            codigo_final = (codigo_manual or st.session_state.get("codigo_sugerido") or gerar_codigo()).strip().upper()
            if not re.match(r"^[A-Z0-9\-]{3,30}$", codigo_final):
                st.error("Código inválido — use apenas letras, números e hífen (3 a 30 caracteres).")
            elif valido_ate < valido_de:
                st.error("A data final não pode ser antes da data inicial.")
            else:
                ok, resultado = criar_cupom(
                    codigo=codigo_final, tipo=tipo, valor=valor,
                    valido_de=valido_de, valido_ate=valido_ate,
                    valido_de_hora=hora_inicio, valido_ate_hora=hora_fim,
                    limite_usos=limite_usos, limite_por_cliente=limite_por_cliente,
                    valor_minimo_pedido=valor_minimo, descricao=descricao,
                    cesta_ids=cestas_restritas or None,
                    origem="manual", criado_por=st.session_state.get("usuario_logado_nome", "admin"),
                )
                if ok:
                    st.success(f"Cupom **{codigo_final}** criado com sucesso!")
                    st.session_state.pop("codigo_sugerido", None)
                    st.rerun()
                else:
                    st.error(f"Erro ao criar cupom: {resultado}")

# =====================================================
# ABA 2 — LISTAR / GERENCIAR
# =====================================================
with aba_listar:
    cupons = listar_cupons()
    if not cupons:
        st.info("Nenhum cupom cadastrado ainda.")
    else:
        for c in cupons:
            usos = contar_usos(c["id"])
            limite = c.get("limite_usos", 1)
            expirado = str(c.get("valido_ate", ""))[:10] < date.today().isoformat()
            cestas_do_cupom = c.get("cesta_ids") or []

            with st.container(border=True):
                col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 1])
                with col_a:
                    st.markdown(f"### `{c['codigo']}`")
                    st.caption(c.get("descricao") or "Sem descrição")
                    if cestas_do_cupom:
                        nomes_cestas = ", ".join(mapa_cestas.get(cid, f"#{cid}") for cid in cestas_do_cupom)
                        st.caption(f"🧺 Restrito a: {nomes_cestas}")
                    else:
                        st.caption("🧺 Válido em todas as cestas")
                with col_b:
                    if c["tipo"] == "percentual":
                        st.write(f"**{c['valor']:.0f}% de desconto**")
                    elif c["tipo"] == "fixo":
                        st.write(f"**R$ {c['valor']:.2f} de desconto**")
                    else:
                        st.write("**Cortesia total (grátis)**")
                    hora_ini = str(c.get("valido_de_hora", "00:00:00"))[:5]
                    hora_fi = str(c.get("valido_ate_hora", "23:59:59"))[:5]
                    de_fmt = "/".join(reversed(str(c["valido_de"])[:10].split("-")))
                    ate_fmt = "/".join(reversed(str(c["valido_ate"])[:10].split("-")))
                    st.caption(f"Válido: {de_fmt} {hora_ini} → {ate_fmt} {hora_fi}")
                with col_c:
                    st.write(f"**Usos:** {usos} / {limite}")
                    st.caption(f"Limite por cliente: {c.get('limite_por_cliente', 1)}")
                    if expirado:
                        st.warning("Expirado")
                    elif not c.get("ativo", True):
                        st.error("Desativado")
                    else:
                        st.success("Ativo")
                with col_d:
                    if c.get("ativo", True):
                        if st.button("⏸️ Desativar", key=f"desat_{c['id']}", use_container_width=True):
                            alternar_ativo(c["id"], False)
                            st.rerun()
                    else:
                        if st.button("▶️ Ativar", key=f"at_{c['id']}", use_container_width=True):
                            alternar_ativo(c["id"], True)
                            st.rerun()
                    if st.button("🗑️ Excluir", key=f"exc_{c['id']}", use_container_width=True):
                        excluir_cupom(c["id"])
                        st.rerun()

# =====================================================
# ABA 3 — ENVIAR CORTESIA PARA CLIENTES DA BASE
# =====================================================
with aba_enviar:
    st.markdown("""
Gera um cupom novo (ou usa um já existente) e ajuda a disparar pra clientes da base.
- **E-mail:** enviado automaticamente, um por um, direto desta página.
- **WhatsApp:** o sistema não tem integração paga com a API do WhatsApp Business, então
  para cada cliente selecionado é gerado um **link `wa.me` com a mensagem já escrita** —
  você só clica em "Abrir" e aperta enviar, sem digitar nada.
    """)

    cupons_disponiveis = [c for c in listar_cupons() if c.get("ativo", True)]
    if not cupons_disponiveis:
        st.warning("Crie um cupom ativo na aba 'Criar Cupom' antes de enviar cortesias.")
        st.stop()

    codigo_escolhido = st.selectbox(
        "Qual cupom enviar?",
        [c["codigo"] for c in cupons_disponiveis],
    )
    cupom_obj = next(c for c in cupons_disponiveis if c["codigo"] == codigo_escolhido)

    clientes = listar_clientes_para_envio()
    if not clientes:
        st.info("Nenhum cliente na base ainda.")
        st.stop()

    st.write(f"**{len(clientes)} clientes encontrados na base.**")
    busca = st.text_input("Filtrar por nome (opcional)", "")
    clientes_filtrados = [c for c in clientes if busca.lower() in c["nome"].lower()] if busca else clientes

    df = pd.DataFrame(clientes_filtrados)
    df.insert(0, "Enviar", False)
    df_editado = st.data_editor(
        df,
        column_config={
            "Enviar": st.column_config.CheckboxColumn("Enviar?"),
            "nome": "Nome",
            "telefone": "Telefone",
            "email": "E-mail",
            "total_pedidos": "Pedidos feitos",
        },
        disabled=["nome", "telefone", "email", "total_pedidos"],
        hide_index=True,
        use_container_width=True,
        key="tabela_envio_cupom",
    )

    selecionados = df_editado[df_editado["Enviar"] == True].to_dict("records")
    st.write(f"**{len(selecionados)} cliente(s) selecionado(s).**")

    mensagem_base = st.text_area(
        "Mensagem (o código do cupom é adicionado automaticamente no final)",
        value=(
            f"Oi {{nome}}! 🎁 Preparamos um mimo especial pra você: use o cupom "
            f"*{codigo_escolhido}* no seu próximo pedido na Doce Cesta Brasília. "
            f"Corre que é por tempo limitado! 💛"
        ),
    )

    col_env1, col_env2 = st.columns(2)

    with col_env1:
        if st.button("📧 Enviar por e-mail para os selecionados", type="primary", use_container_width=True, disabled=not selecionados):
            enviados, falhas = 0, 0
            barra = st.progress(0.0)
            for i, cli in enumerate(selecionados):
                if cli.get("email"):
                    msg = mensagem_base.replace("{nome}", cli["nome"])
                    ok, _ = enviar_email_cupom(cli["email"], cli["nome"], codigo_escolhido, msg, cupom_obj)
                    enviados += 1 if ok else 0
                    falhas += 0 if ok else 1
                barra.progress((i + 1) / len(selecionados))
            st.success(f"✅ {enviados} e-mail(s) enviado(s). {falhas} falha(s) (sem e-mail cadastrado ou erro de envio).")

    with col_env2:
        st.markdown("**Links do WhatsApp (clique em cada um para abrir e enviar):**")
        for cli in selecionados:
            tel = re.sub(r"\D", "", cli.get("telefone", ""))
            if not tel:
                st.caption(f"⚠️ {cli['nome']} sem telefone cadastrado.")
                continue
            if not tel.startswith("55"):
                tel = "55" + tel
            msg = mensagem_base.replace("{nome}", cli["nome"])
            from urllib.parse import quote
            link = f"https://wa.me/{tel}?text={quote(msg)}"
            st.markdown(f"- [{cli['nome']} — Abrir WhatsApp]({link})")
