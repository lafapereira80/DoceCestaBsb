import streamlit as st
import json
from datetime import datetime

from config.db import supabase
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from utils.permissao import administrador_operador
from services.cesta_service import listar_cestas
from services.configuracao_cesta_service import carregar_configuracao_cesta
from services.infinitepay_service import gerar_link_checkout_infinitepay
from services.email_service import enviar_email_orcamento_corporativo
from services.pedido_adicional_service import salvar_adicionais_pedido

st.set_page_config(page_title="Leads Corporativos", page_icon="📋", layout="wide")
configurar_pagina()
menu_lateral()
administrador_operador()

page_header("Orçamentos corporativos", "Solicitações de empresas recebidas pelo site.", "📨", ["Operação", "Corporativo"], "violet")
st.caption("Leads recebidos pela página pública corporativa — trate, monte a proposta e envie.")

STATUS_OPCOES = ["novo", "em_contato", "proposta_enviada", "ganho", "perdido"]
STATUS_LABEL = {
    "novo": "🆕 Novo", "em_contato": "💬 Em contato", "proposta_enviada": "📤 Proposta enviada",
    "ganho": "✅ Ganho", "perdido": "❌ Perdido",
}
CENARIO_LABEL = {
    "brindes_fim_de_ano": "🎄 Brindes de Fim de Ano", "eventos_corporativos": "🎉 Eventos & Confraternizações",
    "onboarding_rh": "👋 Onboarding de Colaboradores", "parcerias": "🤝 Parcerias & Marketing", "outro": "✍️ Outro",
}


def _update_defensivo(lead_id, payload_completo, campos_minimos_seguros):
    """
    Tenta salvar com todos os campos; se alguma coluna nova ainda não existir
    no banco (migração não rodada), tenta de novo só com os campos garantidos.
    """
    try:
        supabase.table("leads_corporativos").update(payload_completo).eq("id", lead_id).execute()
        return True, None
    except Exception as e1:
        payload_reduzido = {k: v for k, v in payload_completo.items() if k in campos_minimos_seguros}
        if not payload_reduzido:
            return False, str(e1)
        try:
            supabase.table("leads_corporativos").update(payload_reduzido).eq("id", lead_id).execute()
            return True, f"Salvo parcialmente (algumas colunas novas ainda não existem no banco — rode a migração SQL): {e1}"
        except Exception as e2:
            return False, str(e2)


@st.cache_data(ttl=300, show_spinner=False)  # invalidado ativamente pelas paginas de admin
def obter_adicionais_catalogo():
    try:
        categorias = supabase.table("categorias").select("*").execute().data or []
        cat_add = next((c for c in categorias if c.get("nome", "").strip().lower() == "adicionais"), None)
        if not cat_add:
            return []
        res = supabase.table("produtos").select("*").eq("categoria_id", cat_add["id"]).eq("ativo", True).execute()
        return res.data or []
    except Exception:
        return []


try:
    leads = supabase.table("leads_corporativos").select("*").order("created_at", desc=True).execute().data or []
except Exception as e:
    st.error(f"Erro ao carregar leads: {e}")
    leads = []

col_f1, col_f2 = st.columns([1, 3])
with col_f1:
    filtro_status = st.selectbox("Filtrar por status", ["Todos"] + STATUS_OPCOES, format_func=lambda s: "Todos" if s == "Todos" else STATUS_LABEL[s])

leads_filtrados = leads if filtro_status == "Todos" else [l for l in leads if l.get("status") == filtro_status]

if not leads_filtrados:
    st.info("Nenhuma solicitação encontrada.")
    st.stop()

todas_cestas = listar_cestas()
mapa_cestas = {c["id"]: c for c in todas_cestas}
adicionais_catalogo = obter_adicionais_catalogo()
mapa_adicionais = {p["id"]: p for p in adicionais_catalogo}

for lead in leads_filtrados:
    status_atual = lead.get("status", "novo")
    with st.container(border=True):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(f"### 🏭 {lead['empresa_nome']}")
            st.caption(f"{CENARIO_LABEL.get(lead.get('caso_de_uso'), lead.get('caso_de_uso'))} · {lead.get('quantidade_estimada')} cestas · recebido em {str(lead.get('created_at'))[:16].replace('T', ' ')}")
            st.write(f"👤 **{lead.get('contato_nome')}** — 📧 {lead.get('contato_email')} — 📱 {lead.get('contato_telefone')}")
            if lead.get("cnpj"):
                st.caption(f"CNPJ: {lead['cnpj']}")

            # Mostra se o cliente já chegou com uma cesta do catálogo escolhida
            # no formulário público, ou se pediu sem preferência (precisa sugerir).
            cesta_pedida_id = lead.get("cesta_base_id")
            if cesta_pedida_id and cesta_pedida_id in mapa_cestas:
                st.success(f"🧺 Cliente já escolheu no formulário: **{mapa_cestas[cesta_pedida_id].get('nome')}**")
            else:
                st.warning("🧺 Cliente não escolheu uma cesta específica — pediu sugestão da nossa equipe.")

            if lead.get("observacoes"):
                st.caption(f"💬 {lead['observacoes']}")
        with col_b:
            novo_status = st.selectbox(
                "Status", STATUS_OPCOES, index=STATUS_OPCOES.index(status_atual),
                format_func=lambda s: STATUS_LABEL[s], key=f"status_{lead['id']}",
            )
            if novo_status != status_atual:
                _update_defensivo(lead["id"], {"status": novo_status}, {"status"})
                st.rerun()

            if novo_status == "perdido":
                st.caption("Lead marcado como perdido.")
                if st.session_state.get(f"confirmar_exclusao_{lead['id']}"):
                    st.warning("Excluir esta solicitação permanentemente?")
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        if st.button("✅ Sim, excluir", key=f"conf_sim_{lead['id']}", use_container_width=True):
                            try:
                                supabase.table("leads_corporativos").delete().eq("id", lead["id"]).execute()
                                st.toast("Lead excluído.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")
                    with col_conf2:
                        if st.button("❌ Cancelar", key=f"conf_nao_{lead['id']}", use_container_width=True):
                            st.session_state[f"confirmar_exclusao_{lead['id']}"] = False
                            st.rerun()
                else:
                    if st.button("🗑️ Excluir solicitação", key=f"del_{lead['id']}", use_container_width=True):
                        st.session_state[f"confirmar_exclusao_{lead['id']}"] = True
                        st.rerun()

        with st.expander("🧺 Montar proposta (cesta, adicionais e envio)"):
            opcoes_cesta_nomes = {c["id"]: c.get("nome") for c in todas_cestas}
            cesta_base_default = lead.get("cesta_base_id") or (todas_cestas[0]["id"] if todas_cestas else None)
            cesta_escolhida_id = st.selectbox(
                "Cesta base da proposta",
                list(opcoes_cesta_nomes.keys()),
                index=list(opcoes_cesta_nomes.keys()).index(cesta_base_default) if cesta_base_default in opcoes_cesta_nomes else 0,
                format_func=lambda cid: opcoes_cesta_nomes.get(cid, f"#{cid}"),
                key=f"cesta_base_{lead['id']}",
            )
            if lead.get("cesta_base_id") and cesta_escolhida_id != lead.get("cesta_base_id"):
                st.caption(f"⚠️ O cliente pediu \"{mapa_cestas.get(lead['cesta_base_id'], {}).get('nome', '?')}\" — você está montando com uma cesta diferente.")

            configuracao = carregar_configuracao_cesta(cesta_escolhida_id) if cesta_escolhida_id else []
            itens_proposta = {}

            if configuracao:
                st.markdown("**Personalize os itens da cesta base:**")
                for grupo in configuracao:
                    cat = grupo.get("categoria", "Categoria")
                    prods = grupo.get("produtos", [])
                    maximo = grupo.get("max_escolhas", 1)
                    if not prods:
                        continue
                    opcoes = {p["id"]: p["nome"] for p in prods}
                    if maximo == 1:
                        escolha_id = st.radio(
                            cat, options=list(opcoes.keys()), format_func=lambda x: opcoes[x],
                            key=f"lead_radio_{lead['id']}_{cat}", horizontal=True,
                        )
                        itens_proposta[cat] = [{"id": escolha_id, "nome": opcoes[escolha_id]}]
                    else:
                        escolhas_ids = st.multiselect(
                            f"{cat} (até {maximo})", options=list(opcoes.keys()), format_func=lambda x: opcoes[x],
                            max_selections=maximo, key=f"lead_multi_{lead['id']}_{cat}",
                        )
                        itens_proposta[cat] = [{"id": pid, "nome": opcoes[pid]} for pid in escolhas_ids]
            else:
                st.caption("Esta cesta não tem itens personalizáveis configurados — a proposta usa a composição padrão.")

            # ---------------- Adicionais / Extras (igual ao Detalhes do Pedido) ----------------
            st.markdown("**Adicionais / Extras (opcional):**")
            adicionais_salvos = lead.get("adicionais_proposta") or []
            ids_default = [a.get("produto_id") for a in adicionais_salvos if a.get("produto_id") in mapa_adicionais]
            if adicionais_catalogo:
                adicionais_escolhidos_ids = st.multiselect(
                    "Selecione os extras que farão parte da proposta",
                    options=list(mapa_adicionais.keys()),
                    default=ids_default,
                    format_func=lambda pid: f"{mapa_adicionais[pid]['nome']} (R$ {float(mapa_adicionais[pid].get('preco') or 0):.2f})",
                    key=f"lead_adicionais_{lead['id']}",
                )
            else:
                adicionais_escolhidos_ids = []
                st.caption("Nenhum produto cadastrado na categoria 'Adicionais' ainda.")

            adicionais_proposta = [
                {"produto_id": pid, "nome": mapa_adicionais[pid]["nome"], "preco": float(mapa_adicionais[pid].get("preco") or 0)}
                for pid in adicionais_escolhidos_ids
            ]
            valor_adicionais_total = sum(a["preco"] for a in adicionais_proposta)
            if adicionais_proposta:
                st.caption(f"➕ Extras somam **R$ {valor_adicionais_total:.2f}** por unidade.")

            cesta_obj = mapa_cestas.get(cesta_escolhida_id, {})
            preco_base_sugerido = float(cesta_obj.get("preco") or 0) + valor_adicionais_total

            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                valor_unitario = st.number_input("Valor unitário (R$, já com extras)", min_value=0.0, value=preco_base_sugerido, step=1.0, key=f"valor_unit_{lead['id']}")
            with col_p2:
                try:
                    qtd_default = int(lead.get("quantidade_estimada") or 10)
                except Exception:
                    qtd_default = 10
                quantidade_confirmada = st.number_input("Quantidade confirmada", min_value=1, value=qtd_default, step=1, key=f"qtd_{lead['id']}")
            with col_p3:
                valor_total_proposto = valor_unitario * quantidade_confirmada
                st.metric("Valor total", f"R$ {valor_total_proposto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            col_ac1, col_ac2 = st.columns(2)

            with col_ac1:
                if st.button("💾 Salvar proposta", key=f"salvar_prop_{lead['id']}", use_container_width=True):
                    payload_prop = {
                        "cesta_base_id": cesta_escolhida_id,
                        "itens_proposta": itens_proposta,
                        "adicionais_proposta": adicionais_proposta,
                        "valor_unitario_proposto": valor_unitario,
                        "quantidade_confirmada": quantidade_confirmada,
                        "valor_total_proposto": valor_total_proposto,
                    }
                    ok, aviso = _update_defensivo(lead["id"], payload_prop, {"status"})
                    if ok:
                        st.toast("Proposta salva.")
                        if aviso:
                            st.warning(aviso)
                        st.rerun()
                    else:
                        st.error(f"Erro ao salvar: {aviso}")

            with col_ac2:
                if st.button("💳 Gerar link de pagamento", key=f"link_pag_{lead['id']}", use_container_width=True):
                    itens_txt = "\n".join(f"{cat}: " + ", ".join(p["nome"] for p in prods) for cat, prods in itens_proposta.items() if prods)
                    if adicionais_proposta:
                        itens_txt += "\nAdicionais: " + ", ".join(a["nome"] for a in adicionais_proposta)

                    novo_pedido = {
                        "cliente_nome": f"{lead['empresa_nome']} [CORPORATIVO]",
                        "cliente_email": lead.get("contato_email"),
                        "cliente_telefone": lead.get("contato_telefone"),
                        "cliente_cpf": lead.get("cnpj"),
                        "destinatario_nome": lead.get("contato_nome"),
                        "cesta_id": cesta_escolhida_id,
                        "cesta_nome": opcoes_cesta_nomes.get(cesta_escolhida_id),
                        "produtos": f"{quantidade_confirmada}x {opcoes_cesta_nomes.get(cesta_escolhida_id)} (R$ {valor_unitario:.2f})\n{itens_txt}",
                        "itens_consulta": json.dumps(itens_proposta, ensure_ascii=False),
                        "valor_total": valor_total_proposto,
                        "status": "Recebido",
                        "pagamento": "Faturamento",
                        "data_entrega": str(lead.get("data_desejada") or datetime.now().date()),
                    }
                    try:
                        res_pedido = supabase.table("pedidos").insert(novo_pedido).execute()
                        pedido_id_novo = res_pedido.data[0]["id"]

                        if adicionais_proposta:
                            try:
                                salvar_adicionais_pedido(pedido_id_novo, [
                                    {"produto_id": a["produto_id"], "nome": a["nome"], "preco": a["preco"]}
                                    for a in adicionais_proposta
                                ])
                            except Exception as e_add:
                                st.warning(f"Pedido criado, mas houve erro ao salvar os adicionais: {e_add}")

                        link = gerar_link_checkout_infinitepay(
                            pedido_id_novo, valor_total_proposto,
                            lead["empresa_nome"], lead.get("contato_telefone"), lead.get("contato_email"),
                        )
                        if link:
                            supabase.table("pedidos").update({"infinitepay_url": link}).eq("id", pedido_id_novo).execute()
                            _update_defensivo(lead["id"], {"link_pagamento": link}, set())
                            st.success(f"Link gerado: {link}")
                            st.rerun()
                        else:
                            st.error("Não foi possível gerar o link (confira o valor mínimo de R$ 1,00).")
                    except Exception as e:
                        st.error(f"Erro ao gerar pedido/link: {e}")

            if lead.get("link_pagamento"):
                st.info(f"🔗 Link de pagamento atual: {lead['link_pagamento']}")

            if st.button("📧 Enviar proposta por e-mail", key=f"env_email_{lead['id']}", use_container_width=True):
                itens_html = "".join(
                    f"<p style='margin:4px 0;'><b>{cat}:</b> {', '.join(p['nome'] for p in prods)}</p>"
                    for cat, prods in itens_proposta.items() if prods
                ) or "<p>Composição padrão da cesta selecionada.</p>"
                if adicionais_proposta:
                    itens_html += "<p style='margin:4px 0;'><b>Adicionais:</b> " + ", ".join(a["nome"] for a in adicionais_proposta) + "</p>"

                ok, msg = enviar_email_orcamento_corporativo(
                    lead.get("contato_email"), lead.get("contato_nome"), lead.get("empresa_nome"),
                    itens_html, valor_unitario, quantidade_confirmada, valor_total_proposto,
                    link_pagamento=lead.get("link_pagamento"),
                )
                if ok:
                    ok2, aviso2 = _update_defensivo(
                        lead["id"],
                        {"status": "proposta_enviada", "proposta_enviada_em": datetime.now().isoformat()},
                        {"status"},
                    )
                    st.success("Proposta enviada por e-mail!")
                    if aviso2:
                        st.warning(aviso2)
                    st.rerun()
                else:
                    st.error(msg)

        observacoes_internas = st.text_area(
            "Observações internas (só a equipe vê)", value=lead.get("observacoes_internas") or "",
            key=f"obs_int_{lead['id']}", height=68,
        )
        if st.button("💾 Salvar observações", key=f"salvar_obs_{lead['id']}"):
            ok, aviso = _update_defensivo(lead["id"], {"observacoes_internas": observacoes_internas}, {"status"})
            if ok:
                st.toast("Observações salvas.")
                if aviso:
                    st.warning(aviso)
            elif "does not exist" in (aviso or "").lower() or "undefinedcolumn" in (aviso or "").lower():
                st.error("Essa coluna ainda não existe no banco. Rode a migração SQL (2026_cupons_e_leads.sql) e tente de novo.")
            else:
                st.error(f"Erro ao salvar: {aviso}")

