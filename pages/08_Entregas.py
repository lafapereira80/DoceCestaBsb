import streamlit as st
import urllib.parse
import re
import html
from datetime import datetime, timezone, timedelta
from config.db import supabase
from utils.menu import configurar_pagina, menu_lateral
from utils.ui import page_header
from services.telegram_service import enviar_notificacao_telegram
try:
    from utils.email_service import enviar_email_entrega
except ImportError:
    enviar_email_entrega = None
from services.foto_service import listar_fotos, deletar_foto


def esc(valor, padrao='-'):
    """Escapa texto antes de inserir em blocos HTML (evita XSS/quebra de layout).
    Importante nesta página: nome, endereço etc. vêm do formulário público (01_Inicio.py)."""
    texto = str(valor) if valor not in (None, '') else padrao
    return html.escape(texto)


def id_curto(pid):
    return html.escape(str(pid).split('-')[0].upper())

# =====================================================
# CONFIGURAÇÃO DA PÁGINA E BLINDAGEM DE SESSÃO
# =====================================================
st.set_page_config(page_title="Gestão de Entregas", page_icon="🛵", layout="wide")
configurar_pagina()
menu_lateral()

usuario = st.session_state.get("usuario")
if not usuario:
    st.warning("⚠️ Você precisa fazer login para acessar esta página.")
    st.stop()
perfil_usuario = usuario.get("perfil", "Operador")
login_atual = usuario.get("login", "Sistema")

# =====================================================
# ESTILOS GERAIS E LAYOUT MODERNO PREMIUM (DESIGN SYSTEM)
# =====================================================
st.markdown(
"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Dancing+Script:wght@600;700&display=swap');

html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; color: #4a2e1b !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1250px; }

h1, h2, h3, h4 { color: #5a3b28 !important; font-weight: 800 !important; margin-bottom: 8px !important; letter-spacing: -0.3px; }

.header-banner {
    display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 6px; margin-bottom: 2rem;
    background: linear-gradient(135deg, #ffffff 0%, #fdfbf8 100%); padding: 25px 20px;
    border-radius: 20px; border: 1px solid #e8ddd3; box-shadow: 0 8px 24px rgba(90, 59, 40, 0.04);
}
.header-title { font-family: 'Dancing Script', cursive !important; font-size: 42px !important; font-weight: 700 !important; color: #c5721f !important; margin: 0 !important; line-height: 1.1 !important; text-align: center;}
.header-subtitle { font-size: 14px !important; color: #775a46 !important; font-weight: 600 !important; margin-top: 0px !important; text-align: center;}

div[data-testid="stVerticalBlockBorderWrapper"] { 
    background: #ffffff !important; 
    border: 1px solid #e8ddd3 !important; 
    border-radius: 18px !important; 
    padding: 20px 22px !important; 
    margin-bottom: 12px !important; 
    box-shadow: 0 4px 15px rgba(90, 59, 40, 0.03) !important; 
    transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: #d2bfae !important; box-shadow: 0 8px 25px rgba(90, 59, 40, 0.08) !important; }

.pedido-id-badge { background: linear-gradient(135deg, #c5721f 0%, #a65d14 100%); color: white; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 11px; display: inline-block; letter-spacing: 0.5px; text-transform: uppercase; box-shadow: 0 4px 8px rgba(197, 114, 31, 0.2); }
.comprador-txt { font-size: 13px; color: #775a46; margin-top: 10px; font-weight: 600; }
.destinatario-txt { font-size: 16px; font-weight: 800; color: #2c1e14; margin-top: 2px; }
.endereco-box { font-size: 14px; color: #4a2e1b; margin-top: 10px; background: #faf7f3; padding: 12px 15px; border-radius: 12px; border-left: 4px solid #1a73e8; line-height: 1.4; font-weight: 600; }
.hora-badge { font-size: 12px; font-weight: 800; color: #b06000; background: #fef7e0; padding: 6px 10px; border-radius: 8px; display: inline-block; margin-top: 12px; border: 1px solid #fce8b2; }

div[data-testid="stButton"] button { border-radius: 12px !important; font-weight: 800 !important; font-size: 14px !important; min-height: 44px !important; transition: all 0.2s ease !important; }
div[data-testid="stButton"] button:hover { transform: translateY(-2px) !important; box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important; }
div[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(135deg, #137333 0%, #0d4e22) !important; color: white !important; border: none !important; box-shadow: 0 4px 15px rgba(19, 115, 51, 0.2) !important; }
div[data-testid="stButton"] button[kind="primary"]:hover { background: linear-gradient(135deg, #0f5c28 0%, #093818) !important; box-shadow: 0 6px 20px rgba(19, 115, 51, 0.3) !important; }

.ficha-entrega { font-size: 15px; color: #4a2e1b; }
.ficha-entrega strong { color: #5a3b28; font-weight: 800; }
.ficha-secao { margin-top: 12px; padding-top: 12px; border-top: 1px dashed #dfcdbb; }

div[data-testid="stLinkButton"] a { font-weight: 800 !important; font-size: 14px !important; border-radius: 12px !important; padding: 12px !important; display: flex; justify-content: center; transition: all 0.2s ease !important; text-decoration: none !important;}
div[data-testid="stLinkButton"] a:hover { transform: translateY(-2px) !important; box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important;}
.btn-waze > a { background-color: #e8f0fe !important; color: #1a73e8 !important; border: 1px solid #d2e3fc !important; }
.btn-maps > a { background-color: #fce8e6 !important; color: #c5221f !important; border: 1px solid #fad2cf !important; }

.entregue-box { opacity: 0.85; background-color: #f0f7f4 !important; border: 1px solid #c8e6c9 !important; border-left: 6px solid #137333 !important; }
.admin-card-header { text-align: center; background: linear-gradient(135deg, #fdfbf8 0%, #ffffff 100%); color: #5a3b28; font-weight: 800; padding: 15px; border-radius: 14px; margin-bottom: 15px; font-size: 16px; border: 1px solid #e8ddd3; }

@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .header-title { font-size: 36px !important; }
}

@media (max-width: 768px) {
    .block-container { padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
    .header-title { font-size: 28px !important; }
    .header-subtitle { font-size: 12.5px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px !important; }
    .destinatario-txt { font-size: 14px; }
    .endereco-box { font-size: 13px; padding: 10px 12px; }
    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; gap: 8px !important; margin-top: 10px !important; justify-content: space-between; }
    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) > div[data-testid="stColumn"] { flex: 1 1 0% !important; min-width: 0 !important; padding: 0 !important; }
    div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(button) button { width: 100% !important; padding: 8px 0px !important; }
}
</style>
""", unsafe_allow_html=True)

if "modo_entrega_ativa" not in st.session_state: st.session_state.modo_entrega_ativa = False

# =====================================================
# FUNÇÕES DE BANCO E LÓGICA COMPARTILHADA
# =====================================================
def formatar_data(data_str):
    if not data_str: return "-"
    try:
        dt = datetime.strptime(str(data_str)[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except:
        return str(data_str)

def obter_horario_brasilia():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br)

def buscar_entregas_dia(driver_login=None):
    data_hoje = obter_horario_brasilia().strftime("%d/%m/%Y")
    
    query_env = supabase.table("pedidos").select("*").in_("status", ["Pago", "Enviado", "Em Rota de Entrega"])
    if perfil_usuario == "Entregador" or driver_login:
        alvo = login_atual if perfil_usuario == "Entregador" else driver_login
        query_env = query_env.eq("entregador_login", alvo)
        
    res_env = query_env.execute()
    enviados = res_env.data or []
    # Pedidos com status "Pago" só entram na fila de logística quando a cesta já foi
    # montada e liberada pela produção (16_Previsao.py). "Enviado"/"Em Rota de Entrega"
    # seguem valendo por compatibilidade com pedidos antigos que já usavam esse status.
    enviados = [p for p in enviados if p.get("status") in ("Enviado", "Em Rota de Entrega") or p.get("cesta_montada")]
    enviados.sort(key=lambda x: (x.get('ordem_entrega') if x.get('ordem_entrega') is not None else 999, x.get('created_at')))
    
    query_ent = supabase.table("pedidos").select("*").eq("status", "Entregue")
    if perfil_usuario == "Entregador" or driver_login:
        alvo = login_atual if perfil_usuario == "Entregador" else driver_login
        query_ent = query_ent.eq("entregador_login", alvo)
        
    res_ent = query_ent.execute()
    entregues = res_ent.data or []
    entregues_hoje = [p for p in entregues if p.get('hora_entrega_realizada') and data_hoje in p.get('hora_entrega_realizada') and not p.get('arquivado')]
    entregues_hoje.sort(key=lambda x: x.get('hora_entrega_realizada', ''), reverse=True)
    
    return enviados, entregues_hoje

def salvar_ordem(pedidos_ordenados):
    for i, p in enumerate(pedidos_ordenados):
        if p.get("ordem_entrega") != i:
            try: supabase.table("pedidos").update({"ordem_entrega": i}).eq("id", p["id"]).execute()
            except: pass 

def atualizar_entregador(pedido_id, widget_key):
    novo_entregador = st.session_state[widget_key]
    val = None if novo_entregador == "Não atribuído" else novo_entregador
    try: 
        supabase.table("pedidos").update({"entregador_login": val}).eq("id", pedido_id).execute()
        st.toast("✅ Entregador atribuído com sucesso!")
    except Exception as e: 
        st.error(f"Erro ao atribuir: {e}")

def marcar_como_entregue(pedido, login_autor, quem_recebeu, horario_manual=None):
    try:
        agora_br = obter_horario_brasilia()
        
        if horario_manual:
            hora_formatada = f"{agora_br.strftime('%d/%m/%Y')} {horario_manual.strftime('%H:%M')}"
            apenas_hora = horario_manual.strftime("%H:%M")
        else:
            hora_formatada = agora_br.strftime("%d/%m/%Y %H:%M")
            apenas_hora = agora_br.strftime("%H:%M")
            
        nome_recebedor_final = quem_recebeu.strip() if quem_recebeu.strip() else "Não informado"
        
        supabase.table("pedidos").update({
            "status": "Entregue", 
            "ordem_entrega": 999, 
            "hora_entrega_realizada": hora_formatada,
            "quem_recebeu": nome_recebedor_final
        }).eq("id", pedido["id"]).execute()
        
        bairro_local = (str(pedido.get('endereco') or '').split(',')[-1].split('(')[0].strip()) or "Região Central"
        texto_telegram = (
            f"🚀 *ATUALIZAÇÃO DE ROTA — DOÇURA ENTREGUE!* 🎁\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *ID do Pedido:* `#{pedido.get('id')}`\n"
            f"🎁 *Pacote:* {pedido.get('cesta_nome', '-')}\n"
            f"💝 *Destinatário:* {pedido.get('destinatario_nome', '-')}\n"
            f"📍 *Bairro / Local:* {bairro_local}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛵 *Responsável:* {login_autor}\n"
            f"⏰ *Horário Real:* {apenas_hora}\n"
            f"👤 *Recebido por:* {nome_recebedor_final}\n"
            f"✅ *Status:* Concluído com Sucesso!"
        )
        enviar_notificacao_telegram(texto_telegram)

        # E-mail de confirmação de entrega pro cliente (best-effort: nunca deve
        # travar a baixa da entrega se o envio falhar ou não houver e-mail salvo).
        try:
            email_cliente_entrega = pedido.get("cliente_email")
            if email_cliente_entrega and "@" in str(email_cliente_entrega):
                foto_url_entrega = None
                try:
                    fotos_pedido_entrega = listar_fotos(pedido["id"])
                    if fotos_pedido_entrega:
                        foto_url_entrega = fotos_pedido_entrega[0].get("url")
                except Exception:
                    pass

                nome_cliente_email = str(pedido.get("cliente_nome") or "").replace("[B2B]", "").replace("[VITRINE]", "").strip()
                resumo_entrega = {
                    "cesta_nome": pedido.get("cesta_nome"),
                    "destinatario_nome": pedido.get("destinatario_nome"),
                    "hora_entrega": hora_formatada,
                    "quem_recebeu": nome_recebedor_final,
                    "endereco": pedido.get("endereco"),
                }
                id_curto_email = str(pedido["id"]).split("-")[0].upper()
                if enviar_email_entrega:
                    enviar_email_entrega(email_cliente_entrega, nome_cliente_email or "Cliente", id_curto_email, resumo_entrega, foto_url=foto_url_entrega)
        except Exception:
            pass
    except Exception as e:
        st.error(f"Erro ao finalizar entrega: {e}")

def voltar_para_enviado(pedido_id):
    try:
        supabase.table("pedidos").update({"status": "Em Rota de Entrega", "ordem_entrega": 0, "hora_entrega_realizada": None, "quem_recebeu": None}).eq("id", pedido_id).execute()
        st.toast("↩️ Cesta retornada para a rota com sucesso!")
    except Exception as e:
        st.error(f"Erro ao reverter status: {e}")

def arquivar_pedidos_concluidos(lista_ids):
    """
    Marca os pedidos entregues como arquivados e apaga as fotos polaroid do bucket/banco.
    """
    if not lista_ids:
        return True, "Nenhum pedido para arquivar."
    try:
        for pid in lista_ids:
            # 1. Busca e deleta as fotos (polaroids) associadas ao pedido no bucket e no banco
            try:
                fotos = listar_fotos(pid)
                if fotos:
                    for foto in fotos:
                        deletar_foto(foto["id"], foto["caminho_arquivo"])
            except Exception as e:
                print(f"Erro ao tentar deletar foto do pedido {pid}: {e}")

            # 2. Arquiva o pedido no banco de dados
            supabase.table("pedidos").update({"arquivado": True}).eq("id", pid).execute()
            
        return True, f"{len(lista_ids)} pedido(s) arquivado(s) com sucesso."
    except Exception as e:
        return False, f"Erro ao arquivar: {e}"

pedidos_ativos_geral, pedidos_concluidos_geral = buscar_entregas_dia()

if "confirmar_arquivar_painel" not in st.session_state:
    st.session_state["confirmar_arquivar_painel"] = False


# =====================================================
# VISÃO 1: ADMINISTRADOR E OPERADOR (PAINEL DE CONTROLE)
# =====================================================
if perfil_usuario in ["Administrador", "Operador"]:
    
    page_header("Despacho e entregas", "Atribua pedidos aos entregadores e monitore a operação.", "🛵", ["Operação", "Entregas"], "warn")
    
    col_t2 = st.columns([1, 4, 1])[2]
    with col_t2:
        if st.button("🔄 Atualizar Grid", use_container_width=True):
            st.rerun()

    if pedidos_concluidos_geral:
        with st.container(border=True):
            col_arq_info, col_arq_btn = st.columns([3, 1.4])
            with col_arq_info:
                st.markdown(
                    f"<div style='font-size:14px; font-weight:700; color:#166534;'>✅ {len(pedidos_concluidos_geral)} pedido(s) entregue(s) hoje, aguardando arquivamento.</div>"
                    f"<div style='font-size:12.5px; color:#64748B;'>Eles continuam aparecendo em Pedidos (dentro do filtro 'Pago') até você concluir a rota aqui.</div>",
                    unsafe_allow_html=True
                )
            with col_arq_btn:
                if st.session_state["confirmar_arquivar_painel"]:
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Confirmar", use_container_width=True, type="primary"):
                            ids_para_arquivar = [p["id"] for p in pedidos_concluidos_geral]
                            ok, msg = arquivar_pedidos_concluidos(ids_para_arquivar)
                            st.session_state["confirmar_arquivar_painel"] = False
                            if ok:
                                st.toast(f"🏁 {msg}")
                                st.rerun()
                            else:
                                st.error(msg)
                    with cc2:
                        if st.button("❌ Cancelar", use_container_width=True):
                            st.session_state["confirmar_arquivar_painel"] = False
                            st.rerun()
                else:
                    if st.button("🏁 Concluir Rota e Arquivar Painel", use_container_width=True, type="primary"):
                        st.session_state["confirmar_arquivar_painel"] = True
                        st.rerun()

    aba_geral, aba_visao_motoboy = st.tabs(["📦 Cestas na Base & Rotas", "📱 Simulador do Motoboy"])

    # -------------------------------------------------
    # ABA 1: PAINEL GERAL DE DESPACHO E ROTAS
    # -------------------------------------------------
    with aba_geral:
        lista_entregadores = []
        try:
            res_ent = supabase.table("usuarios").select("login").eq("perfil", "Entregador").execute()
            lista_entregadores = [e["login"] for e in (res_ent.data or [])]
        except: pass
        opcoes_ent = ["Não atribuído"] + lista_entregadores

        nao_atribuidos = [p for p in pedidos_ativos_geral if not p.get("entregador_login")]
        
        st.markdown("<h3 style='margin-top: 0;'>📥 Aguardando Atribuição</h3>", unsafe_allow_html=True)
        
        if not nao_atribuidos:
            st.info("✨ Todas as cestas despachadas já estão com um entregador responsável.")
        else:
            cols_despacho = st.columns(2)
            for i, ped in enumerate(nao_atribuidos):
                with cols_despacho[i % 2]:
                    with st.container(border=True):
                        endereco_completo = ped.get('endereco') or 'Endereço não informado'
                        data_entrega = formatar_data(ped.get('data_entrega'))
                        turno = ped.get('periodo_entrega') or 'N/I'
                        hora_combinada = ped.get('horario_combinado', '')
                        hora_str = f" • Às {esc(hora_combinada)}" if hora_combinada else ""
                        tel_dest = ped.get('destinatario_telefone')
                        tel_dest_str = f" (📞 {esc(tel_dest)})" if tel_dest else ""
                        
                        col_detalhes, col_acao = st.columns([1.7, 1])
                        
                        with col_detalhes:
                            st.markdown(
                                f"""
                                <div>
                                    <span class="pedido-id-badge">ID #{id_curto(ped.get('id'))}</span>
                                    <div class="comprador-txt">👤 Comp: <strong>{esc(ped.get('cliente_nome'))}</strong></div>
                                    <div class="destinatario-txt">🎁 {esc(ped.get('cesta_nome'))} p/ <em>{esc(ped.get('destinatario_nome'))}</em>{tel_dest_str}</div>
                                    <div class="endereco-box">📍 {esc(endereco_completo)}</div>
                                    <div class="hora-badge">📅 {esc(data_entrega)} | 🕒 {esc(turno)}{hora_str}</div>
                                </div>
                                """, unsafe_allow_html=True
                            )
                        
                        with col_acao:
                            st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 4px; text-transform: uppercase;'>Atribuir Moto:</div>", unsafe_allow_html=True)
                            chave_widget = f"despacho_{ped['id']}"
                            st.selectbox("Entregador", opcoes_ent, index=0, key=chave_widget, label_visibility="collapsed", on_change=atualizar_entregador, args=(ped["id"], chave_widget))
                            
                            st.write("")
                            st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 4px; text-transform: uppercase;'>Finalizar:</div>", unsafe_allow_html=True)
                            recebedor_desp = st.text_input("Quem recebeu?", key=f"rec_desp_{ped['id']}", placeholder="Nome da pessoa", label_visibility="collapsed")
                            horario_baixa_desp = st.time_input("Horário da entrega", value=obter_horario_brasilia().time(), key=f"hora_desp_{ped['id']}", label_visibility="collapsed")
                            
                            if st.button("✅ Dar Baixa Manual", key=f"entregue_desp_{ped['id']}", use_container_width=True):
                                se_vazio = recebedor_desp if recebedor_desp else "Baixa Manual Admin"
                                marcar_como_entregue(ped, login_atual, se_vazio, horario_manual=horario_baixa_desp)
                                st.rerun()

        # Verifica rotas ativas
        data_hoje = obter_horario_brasilia().strftime("%d-%m-%Y")
        rotas_ativas_existem = False
        if lista_entregadores:
            for driver in lista_entregadores:
                p_ativos = [p for p in pedidos_ativos_geral if p.get("entregador_login") == driver]
                p_concl = [p for p in pedidos_concluidos_geral if p.get("entregador_login") == driver]
                arquivada = st.session_state.get(f"limpar_rota_{driver}_{data_hoje}", False)
                if p_ativos or (p_concl and not arquivada):
                    rotas_ativas_existem = True
                    break

        if rotas_ativas_existem:
            st.divider()
            st.markdown("<h3>🛵 Rotas em Andamento</h3>", unsafe_allow_html=True)
            cols_rotas = st.columns(2)
            
            for idx_driver, driver in enumerate(lista_entregadores):
                ped_driver_ativos = [p for p in pedidos_ativos_geral if p.get("entregador_login") == driver]
                ped_driver_concluidos = [p for p in pedidos_concluidos_geral if p.get("entregador_login") == driver]
                
                rota_arquivada = st.session_state.get(f"limpar_rota_{driver}_{data_hoje}", False)
                if rota_arquivada: ped_driver_concluidos = []

                if not ped_driver_ativos and not ped_driver_concluidos: continue 
                    
                with cols_rotas[idx_driver % 2]:
                    with st.container(border=True):
                        st.markdown(f"<div class='admin-card-header'>🚴 Rota: {driver}</div>", unsafe_allow_html=True)

                        salvar_ordem(ped_driver_ativos)
                        
                        if ped_driver_ativos:
                            st.markdown("<span style='font-size:13px; font-weight:800; color:#5a3b28; text-transform: uppercase;'>Itens na Rota:</span>", unsafe_allow_html=True)
                            for i, ped in enumerate(ped_driver_ativos):
                                with st.container(border=True):
                                    endereco_completo = ped.get('endereco') or 'Endereço não informado'
                                    data_entrega = formatar_data(ped.get('data_entrega'))
                                    turno = ped.get('periodo_entrega') or 'N/I'
                                    hora_combinada = ped.get('horario_combinado', '')
                                    hora_str = f" • Às {esc(hora_combinada)}" if hora_combinada else ""
                                    tel_dest = ped.get('destinatario_telefone')
                                    tel_dest_str = f" (📞 {esc(tel_dest)})" if tel_dest else ""
                                    
                                    col_inf_ativa, col_acoes_ativa = st.columns([1.6, 1])
                                    
                                    with col_inf_ativa:
                                        st.markdown(
                                            f"""
                                            <div>
                                                <div class="comprador-txt" style="margin-top: 0px;">👤 Comprador: <strong>{esc(ped.get('cliente_nome'))}</strong></div>
                                                <div class="destinatario-txt">#{i+1} - 🎁 {esc(ped.get('cesta_nome'))} p/ <em>{esc(ped.get('destinatario_nome'))}</em></div>
                                                <div class="endereco-box" style="border-left-color: #5a3b28;">📍 {esc(endereco_completo)}</div>
                                                <div class="hora-badge">📅 {esc(data_entrega)} | 🕒 {esc(turno)}{hora_str}</div>
                                            </div>
                                            """, unsafe_allow_html=True
                                        )
                                    
                                    with col_acoes_ativa:
                                        st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 4px; text-transform: uppercase;'>Realocar para:</div>", unsafe_allow_html=True)
                                        chave_realocar = f"realocar_{ped['id']}"
                                        indice_atual = opcoes_ent.index(driver) if driver in opcoes_ent else 0
                                        st.selectbox("Realocar", opcoes_ent, index=indice_atual, key=chave_realocar, label_visibility="collapsed", on_change=atualizar_entregador, args=(ped["id"], chave_realocar))
                                        
                                        st.write("")
                                        st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 4px; text-transform: uppercase;'>Finalizar:</div>", unsafe_allow_html=True)
                                        recebedor_ativa = st.text_input("Quem recebeu?", key=f"rec_ativa_{ped['id']}", placeholder="Nome da pessoa", label_visibility="collapsed")
                                        horario_baixa_ativa = st.time_input("Horário da entrega", value=obter_horario_brasilia().time(), key=f"hora_ativa_{ped['id']}", label_visibility="collapsed")
                                        
                                        if st.button("✅ Forçar Baixa", key=f"entregue_ativa_{ped['id']}", use_container_width=True, type="primary"):
                                            se_vazio = recebedor_ativa if recebedor_ativa else "Forçado Admin"
                                            marcar_como_entregue(ped, login_atual, se_vazio, horario_manual=horario_baixa_ativa)
                                            st.rerun()

                                    st.write("")
                                    col_u, col_d = st.columns(2)
                                    with col_u:
                                        if i > 0:
                                            if st.button("⬆️ Subir na Rota", key=f"up_admin_{ped['id']}", use_container_width=True):
                                                ped_driver_ativos[i], ped_driver_ativos[i-1] = ped_driver_ativos[i-1], ped_driver_ativos[i]
                                                salvar_ordem(ped_driver_ativos)
                                                st.rerun()
                                    with col_d:
                                        if i < len(ped_driver_ativos) - 1:
                                            if st.button("⬇️ Descer na Rota", key=f"down_admin_{ped['id']}", use_container_width=True):
                                                ped_driver_ativos[i], ped_driver_ativos[i+1] = ped_driver_ativos[i+1], ped_driver_ativos[i]
                                                salvar_ordem(ped_driver_ativos)
                                                st.rerun()

                        if ped_driver_concluidos:
                            st.markdown("<span style='font-size:13px; font-weight:800; color:#137333; margin-top:15px; display:block; text-transform: uppercase;'>✅ Finalizados Hoje:</span>", unsafe_allow_html=True)
                            for ped in ped_driver_concluidos:
                                hora_ext = (ped.get('hora_entrega_realizada') or '')[-5:]
                                bairro_con = str(ped.get('endereco') or '').split(',')[-1].split('(')[0].strip()
                                st.markdown(f"""
                                <div data-testid="stVerticalBlockBorderWrapper" class="entregue-box" style="padding: 14px !important;">
                                    <div style="font-size:14px; font-weight:800; color:#137333;">✅ Entregue às {esc(hora_ext)} - 📍 {esc(bairro_con)} ({esc(ped.get('cesta_nome'))})</div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                if perfil_usuario == "Administrador":
                                    if st.button("↩️ Desfazer e Retornar p/ Rota", key=f"voltar_rota_{ped['id']}", use_container_width=True):
                                        voltar_para_enviado(ped['id'])
                                        st.rerun()

                        if len(ped_driver_ativos) == 0 and len(ped_driver_concluidos) > 0:
                            st.write("")
                            if st.button(f"🧹 Concluir Rota e Arquivar Painel", key=f"btn_ok_{driver}", use_container_width=True):
                                st.session_state[f"limpar_rota_{driver}_{data_hoje}"] = True
                                st.rerun()

    # -------------------------------------------------
    # ABA 2: VISÃO POR ENTREGADOR (SIMULADOR)
    # -------------------------------------------------
    with aba_visao_motoboy:
        st.markdown("### 📱 Simulador do Aplicativo")
        st.caption("Verifique o que o motoboy está enxergando na rua agora.")
        
        lista_entregadores_todos = []
        try:
            res_ent = supabase.table("usuarios").select("login").eq("perfil", "Entregador").execute()
            lista_entregadores_todos = [e["login"] for e in (res_ent.data or [])]
        except: pass

        if not lista_entregadores_todos:
            st.warning("⚠️ Nenhum entregador cadastrado no sistema.")
        else:
            motoboy_selecionado = st.selectbox("Selecione o Entregador para espelhar:", lista_entregadores_todos, key="select_vis_motoboy")
            st.divider()

            p_ativos_mb, p_concluidos_mb = buscar_entregas_dia(driver_login=motoboy_selecionado)

            if not p_ativos_mb and not p_concluidos_mb:
                st.info(f"📭 A rota de **{motoboy_selecionado}** está limpa.")
            else:
                if p_ativos_mb:
                    salvar_ordem(p_ativos_mb)
                    for i, ped in enumerate(p_ativos_mb):
                        with st.container(border=True):
                            horario = ped.get('horario_combinado') or ped.get('periodo_entrega') or 'Livre'
                            data_e = formatar_data(ped.get('data_entrega'))
                            tel_dest = ped.get('destinatario_telefone')
                            tel_dest_str = f" (📞 {esc(tel_dest)})" if tel_dest else ""
                            
                            col_info_mb, col_btn_mb = st.columns([1.6, 1])
                            
                            with col_info_mb:
                                st.markdown(f"""
                                    <div>
                                        <span class="pedido-id-badge">📍 PARADA #{i+1}</span>
                                        <div class="comprador-txt" style="margin-top: 8px;">👤 Comprador: {esc(ped.get('cliente_nome'))} ({esc(ped.get('cliente_telefone'))})</div>
                                        <div class="destinatario-txt">🎁 {esc(ped.get('cesta_nome'))} p/ <strong>{esc(ped.get('destinatario_nome'))}</strong>{tel_dest_str}</div>
                                        <div class="endereco-box">📍 {esc(ped.get('endereco'))}</div>
                                        <div class="hora-badge">📅 {esc(data_e)} | 🕒 {esc(horario)}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                                
                                st.write("")
                                endereco_gps = urllib.parse.quote(re.sub(r'\(CEP:.*?\)', '', ped.get('endereco') or '').strip())
                                c_m, c_w = st.columns(2)
                                with c_m:
                                    st.markdown('<div class="btn-maps">', unsafe_allow_html=True)
                                    st.link_button("🗺️ Abrir Maps", url=f"https://www.google.com/maps/search/?api=1&query={endereco_gps}", use_container_width=True)
                                    st.markdown('</div>', unsafe_allow_html=True)
                                with c_w:
                                    st.markdown('<div class="btn-waze">', unsafe_allow_html=True)
                                    st.link_button("🚗 Abrir Waze", url=f"https://waze.com/ul?q={endereco_gps}&navigate=yes", use_container_width=True)
                                    st.markdown('</div>', unsafe_allow_html=True)

                            with col_btn_mb:
                                st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 4px; text-transform: uppercase;'>Finalizar:</div>", unsafe_allow_html=True)
                                recebedor_sim = st.text_input("Quem recebeu?", key=f"rec_sim_{ped['id']}", placeholder="Nome...", label_visibility="collapsed")
                                if st.button("✅ Concluir Entrega", key=f"entregue_sim_{ped['id']}", use_container_width=True, type="primary"):
                                    if not recebedor_sim.strip():
                                        st.error("Digite o nome de quem recebeu!")
                                    else:
                                        marcar_como_entregue(ped, motoboy_selecionado, recebedor_sim)
                                        st.rerun()

                if p_concluidos_mb:
                    st.write("")
                    st.markdown("<span style='font-size:14px; font-weight:800; color:#137333; margin-top:10px; display:block; text-transform: uppercase;'>✅ Histórico de Hoje:</span>", unsafe_allow_html=True)
                    for ped in p_concluidos_mb:
                        hora_extraida = (ped.get('hora_entrega_realizada') or '')[-5:]
                        bairro_concluido = str(ped.get('endereco') or '').split(',')[-1].split('(')[0].strip()
                        st.markdown(f"""
                        <div data-testid="stVerticalBlockBorderWrapper" class="entregue-box">
                            <div style="font-size:14px; font-weight:800; color:#137333;">✅ Entregue às {esc(hora_extraida)} - 📍 {esc(bairro_concluido)}</div>
                        </div>
                        """, unsafe_allow_html=True)


# =====================================================
# VISÃO 2: ENTREGADOR REAL (APLICATIVO DO MOTOBOY)
# =====================================================
else:
    page_header("Minha rota", "Guia oficial de entregas do dia.", "🗺️", None, "warn")

    pedidos_ativos_driver, pedidos_concluidos_driver = buscar_entregas_dia()

    if not pedidos_ativos_driver and not pedidos_concluidos_driver:
        st.success("🎉 Rota limpa! Nenhuma entrega pendente para você no momento.")
        st.session_state.modo_entrega_ativa = False
        st.stop()

    if not st.session_state.modo_entrega_ativa:
        if pedidos_ativos_driver:
            st.info("👇 As cestas abaixo estão sob sua responsabilidade. Organize a ordem se desejar, e inicie o Modo Navegação.")
            salvar_ordem(pedidos_ativos_driver)
            
            for i, ped in enumerate(pedidos_ativos_driver):
                with st.container(border=True):
                    endereco_completo = ped.get('endereco') or 'Endereço não informado'
                    data_entrega = formatar_data(ped.get('data_entrega'))
                    turno = ped.get('periodo_entrega') or 'N/I'
                    hora_combinada = ped.get('horario_combinado', '')
                    hora_str = f" • Às {esc(hora_combinada)}" if hora_combinada else ""
                    tel_dest = ped.get('destinatario_telefone')
                    tel_dest_str = f" (📞 {esc(tel_dest)})" if tel_dest else ""
                    
                    col_inf_drv, col_btn_drv = st.columns([1.6, 1])
                    
                    with col_inf_drv:
                        st.markdown(
                            f"""
                            <div>
                                <span class="pedido-id-badge">📍 PARADA #{i+1}</span>
                                <div class="comprador-txt" style="margin-top: 8px;">👤 Comprador: {esc(ped.get('cliente_nome'))} ({esc(ped.get('cliente_telefone'))})</div>
                                <div class="destinatario-txt">🎁 <strong>{esc(ped.get('cesta_nome'))}</strong> p/ <em>{esc(ped.get('destinatario_nome'))}</em>{tel_dest_str}</div>
                                <div class="endereco-box">📍 {esc(endereco_completo)}</div>
                                <div class="hora-badge">📅 {esc(data_entrega)} | 🕒 {esc(turno)}{hora_str}</div>
                            </div>
                            """, unsafe_allow_html=True
                        )
                        
                        st.write("")
                        endereco_gps = urllib.parse.quote(re.sub(r'\(CEP:.*?\)', '', ped.get('endereco') or '').strip())
                        c_m_d, c_w_d = st.columns(2)
                        with c_m_d:
                            st.markdown('<div class="btn-maps">', unsafe_allow_html=True)
                            st.link_button("🗺️ Maps", url=f"https://www.google.com/maps/search/?api=1&query={endereco_gps}", use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        with c_w_d:
                            st.markdown('<div class="btn-waze">', unsafe_allow_html=True)
                            st.link_button("🚗 Waze", url=f"https://waze.com/ul?q={endereco_gps}&navigate=yes", use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)

                    with col_btn_drv:
                        st.markdown("<div style='font-size: 11px; font-weight: 800; color: #775a46; margin-bottom: 4px; text-transform: uppercase;'>Finalizar:</div>", unsafe_allow_html=True)
                        recebedor_fila = st.text_input("Quem recebeu?", key=f"rec_fila_{ped['id']}", placeholder="Nome...", label_visibility="collapsed")
                        if st.button("✅ Dar Baixa", key=f"entregue_fila_{ped['id']}", use_container_width=True, type="primary"):
                            if not recebedor_fila.strip():
                                st.error("⚠️ Digite o nome de quem recebeu!")
                            else:
                                marcar_como_entregue(ped, login_atual, recebedor_fila)
                                st.rerun()

                    st.write("")
                    col_up, col_down = st.columns(2)
                    with col_up:
                        if i > 0:
                            if st.button("⬆️ Subir na Fila", key=f"up_{ped['id']}", use_container_width=True):
                                pedidos_ativos_driver[i], pedidos_ativos_driver[i-1] = pedidos_ativos_driver[i-1], pedidos_ativos_driver[i]
                                salvar_ordem(pedidos_ativos_driver)
                                st.rerun()
                    with col_down:
                        if i < len(pedidos_ativos_driver) - 1:
                            if st.button("⬇️ Descer na Fila", key=f"down_{ped['id']}", use_container_width=True):
                                pedidos_ativos_driver[i], pedidos_ativos_driver[i+1] = pedidos_ativos_driver[i+1], pedidos_ativos_driver[i]
                                salvar_ordem(pedidos_ativos_driver)
                                st.rerun()

            st.write("")
            if st.button("🚀 INICIAR MODO NAVEGAÇÃO FOCO", type="primary", use_container_width=True):
                st.session_state.modo_entrega_ativa = True
                st.rerun()
        else:
            st.success("🎉 Rota limpa! Nenhuma entrega pendente na fila ativa.")

    else:
        if pedidos_ativos_driver:
            pedido_atual = pedidos_ativos_driver[0] 
            st.warning("⚠️ **Modo Foco Ativo:** Você está em rota. Conclua a parada atual para liberar a próxima.")
            
            with st.container(border=True):
                st.markdown(f'<div style="font-size:22px; font-weight:800; color:#1a73e8; text-align:center; margin-bottom: 4px; text-transform: uppercase;">🎯 Parada Atual</div>', unsafe_allow_html=True)
                st.divider()
                tel_dest_atual = pedido_atual.get('destinatario_telefone')
                tel_dest_atual_str = f" (📞 {esc(tel_dest_atual)})" if tel_dest_atual else " (Sem telefone)"
                
                col_foco_info, col_foco_botoes = st.columns([1.6, 1])
                
                with col_foco_info:
                    st.markdown(f"""
                        <div class="ficha-entrega">
                            <div><strong>👤 Comprador:</strong> {esc(pedido_atual.get('cliente_nome'))} (📞 {esc(pedido_atual.get('cliente_telefone'))})</div>
                            <div class="ficha-secao"><strong>🎁 Pacote:</strong> {esc(pedido_atual.get('cesta_nome'))}</div>
                            <div class="ficha-secao"><strong>💝 Quem Recebe:</strong><br><span style="font-size: 18px; color: #137333;">{esc(pedido_atual.get('destinatario_nome'))}</span>{tel_dest_atual_str}</div>
                            <div class="ficha-secao"><strong>📍 Endereço de Entrega:</strong><br><span style="font-size: 18px; font-weight: 800; color: #c5721f; line-height:1.4; display:block; margin-top:5px;">{esc(pedido_atual.get('endereco'))}</span></div>
                            <div class="ficha-secao"><strong>📅 Horário Marcado:</strong><br>{esc(formatar_data(pedido_atual.get('data_entrega')))} | 🕒 {esc(pedido_atual.get('horario_combinado') or pedido_atual.get('periodo_entrega') or 'Livre')}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.write("")
                    endereco_gps = urllib.parse.quote(re.sub(r'\(CEP:.*?\)', '', pedido_atual.get('endereco') or '').strip())
                    c_maps, c_waze = st.columns(2)
                    with c_maps:
                        st.markdown('<div class="btn-maps">', unsafe_allow_html=True)
                        st.link_button("🗺️ Abrir Maps", url=f"https://www.google.com/maps/search/?api=1&query={endereco_gps}", use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    with c_waze:
                        st.markdown('<div class="btn-waze">', unsafe_allow_html=True)
                        st.link_button("🚗 Abrir Waze", url=f"https://waze.com/ul?q={endereco_gps}&navigate=yes", use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                with col_foco_botoes:
                    st.markdown("<div style='font-size: 13px; font-weight: 800; color: #137333; margin-bottom: 8px; text-transform: uppercase;'>Finalizar Entrega:</div>", unsafe_allow_html=True)
                    recebedor_foco = st.text_input("Nome de quem recebeu o pacote:", key=f"rec_foco_{pedido_atual['id']}", placeholder="Ex: Porteiro José...")
                    
                    if st.button("✅ MARCAR COMO ENTREGUE", type="primary", use_container_width=True):
                        if not recebedor_foco.strip():
                            st.error("⚠️ Obrigatório digitar o nome de quem recebeu a encomenda!")
                        else:
                            with st.spinner("Confirmando entrega..."):
                                marcar_como_entregue(pedido_atual, login_atual, recebedor_foco)
                            st.rerun() 
                        
                    st.write("")
                    st.markdown("<div style='font-size: 12px; font-weight: 800; color: #775a46; margin-bottom: 8px; text-transform: uppercase;'>Gerenciar Rota:</div>", unsafe_allow_html=True)
                    if st.button("⏸️ Pausar e Ver Fila Completa", use_container_width=True):
                        st.session_state.modo_entrega_ativa = False
                        st.rerun()
        else:
            st.session_state.modo_entrega_ativa = False
            st.rerun()

    if pedidos_concluidos_driver and not st.session_state.modo_entrega_ativa:
        st.write("")
        st.markdown("<span style='font-size:15px; font-weight:800; color:#137333; margin-top:20px; display:block; text-transform: uppercase;'>✅ Histórico de Entregas Hoje:</span>", unsafe_allow_html=True)
        
        for ped in pedidos_concluidos_driver:
            hora_extraida = (ped.get('hora_entrega_realizada') or '')[-5:]
            bairro_concluido = str(ped.get('endereco') or '').split(',')[-1].split('(')[0].strip()
            recebedor_nome = ped.get('quem_recebeu') or 'Não informado'
            st.markdown(f"""
            <div data-testid="stVerticalBlockBorderWrapper" class="entregue-box">
                <div style="font-size:14px; font-weight:800; color:#137333;">✅ Entregue às {esc(hora_extraida)} - 📍 {esc(bairro_concluido)}</div>
                <div class="nome-destaque" style="margin-top:6px; font-size: 13px;">🎁 {esc(ped.get('cesta_nome'))} | 👤 Recebido por: <strong>{esc(recebedor_nome)}</strong></div>
            </div>
            """, unsafe_allow_html=True)
