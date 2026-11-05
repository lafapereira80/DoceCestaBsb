import html
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

def enviar_email_cobranca(email_destino, cliente_nome, pedido_id, resumo_texto, link_pagamento):
    """
    Monta e dispara um e-mail em formato HTML profissional com o resumo do pedido.
    Usado no painel administrativo para enviar cobranças manuais.
    """
    # Busca as credenciais configuradas no secrets.toml
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")
    
    if not remetente or not senha:
        return False, "⚠️ E-mail ou Senha não configurados nos Secrets do sistema."
        
    assunto = f"Detalhes do seu Pedido #{pedido_id} - Doce Cesta"
    
    # Criando o contêiner do e-mail
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta <{remetente}>"
    msg["To"] = email_destino
    
    # Adiciona o botão de pagamento apenas se o link existir
    html_botao = ""
    if link_pagamento:
        html_botao = f"""
        <div style="text-align: center; margin-top: 25px;">
            <a href="{link_pagamento}" style="background-color: #137333; color: white; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">💳 CLIQUE AQUI PARA PAGAR</a>
        </div>
        """
        
    # HTML do E-mail (O layout bonito que o cliente vai ver)
    html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            
            <div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: 800; letter-spacing: 1px;">🧺 Doce Cesta</h1>
            </div>
            
            <div style="padding: 30px;">
                <h3 style="color: #0F172A; font-size: 18px; margin-top: 0;">Olá, {cliente_nome}!</h3>
                <p style="color: #475569; font-size: 15px;">Aqui está o resumo oficial do seu pedido. Por favor, verifique os dados abaixo:</p>
                
                <div style="background: #F8FAFC; padding: 15px; border-left: 4px solid #C5721F; border-radius: 6px; font-family: monospace; font-size: 14px; color: #1E293B; white-space: pre-wrap;">{resumo_texto}</div>
                
                {html_botao}
            </div>
            
            <div style="background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 12px; color: #64748B;">
                <p style="margin: 0;">Obrigado por escolher a Doce Cesta Brasília!</p>
                <p style="margin: 5px 0 0 0;">Se tiver dúvidas, responda a este e-mail.</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(resumo_texto, "plain"))
    msg.attach(MIMEText(html, "html"))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "✅ E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


def _normalizar_itens_escolhidos(resumo):
    """Retorna [(categoria, [itens])]. Aceita 'itens_personalizados' (lista de dicts) ou o texto 'itens_personalizados_str'."""
    grupos = []
    brutos = resumo.get("itens_personalizados")
    if isinstance(brutos, list):
        for g in brutos:
            if isinstance(g, dict):
                itens = [str(i).strip() for i in (g.get("itens") or []) if str(i).strip()]
                if itens: grupos.append((str(g.get("categoria") or "Itens"), itens))
    if grupos: return grupos
    for linha in str(resumo.get("itens_personalizados_str") or "").splitlines():
        if ":" not in linha: continue
        cat, _, nomes = linha.partition(":")
        itens = [n.strip() for n in nomes.split(",") if n.strip()]
        if cat.strip() and itens: grupos.append((cat.strip(), itens))
    return grupos


def enviar_email_confirmacao(email_destino, cliente_nome, pedido_id, resumo):
    """
    Dispara um e-mail automático de confirmação assim que o cliente finaliza o pedido na vitrine.
    """
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")
    
    if not remetente or not senha or not email_destino:
        return False, "⚠️ Credenciais de e-mail ausentes ou e-mail de destino inválido."
        
    assunto = f"Pedido Recebido #{pedido_id} - Doce Cesta 🎁"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta <{remetente}>"
    msg["To"] = email_destino
    
    # Prevenção caso falte algum dado no dicionário de resumo
    def esc(v, padrao=""):
        return html.escape(str(v)) if v not in (None, "") else padrao

    cesta_nome = esc(resumo.get('cesta_nome'))
    destinatario = esc(resumo.get('destinatario_nome'))
    data_ent = esc(resumo.get('data_entrega'))
    periodo = esc(resumo.get('periodo_entrega'))
    valor_tot = esc(resumo.get('valor_total'))
    extras = esc(resumo.get('adicionais_str'), 'Nenhum')
    cliente_nome_seg = esc(cliente_nome, "Cliente")
    pedido_id_seg = esc(pedido_id)

    # Detalhamento dos itens escolhidos na cesta (por categoria)
    grupos_itens = _normalizar_itens_escolhidos(resumo)
    bloco_itens = ""
    texto_itens = ""
    if grupos_itens:
        blocos = ""
        for categoria, itens in grupos_itens:
            lis = "".join(f'<li style="margin: 0 0 2px 0;">{esc(i)}</li>' for i in itens)
            blocos += (
                '<div style="margin-bottom: 14px;">'
                f'<div style="font-size: 12px; font-weight: 800; color: #A65D14; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 4px;">📦 {esc(categoria)}</div>'
                f'<ul style="margin: 0; padding-left: 20px; font-size: 14.5px; color: #475569; line-height: 1.7;">{lis}</ul>'
                '</div>'
            )
            texto_itens += f"- {categoria}: {', '.join(itens)}\n"
        bloco_itens = (
            '<h4 style="color: #1E293B; border-bottom: 2px dashed #E2E8F0; padding-bottom: 8px; margin-top: 30px; font-size: 16px;">🍓 Itens escolhidos na sua cesta</h4>'
            f'<div style="background: #FFFBF5; border: 1px solid #F5EBDD; border-radius: 10px; padding: 16px 18px;">{blocos}</div>'
        )
    
    # HTML do E-mail de Recebimento
    html_corpo = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            
            <div style="background: linear-gradient(135deg, #C5721F 0%, #A65D14 100%); padding: 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">🎁 Pedido Recebido!</h1>
            </div>
            
            <div style="padding: 30px;">
                <h3 style="color: #0F172A; font-size: 18px; margin-top: 0;">Olá, {cliente_nome_seg}!</h3>
                <p style="color: #475569; font-size: 15px;">Que alegria! Seu pedido <b>#{pedido_id_seg}</b> foi recebido com sucesso pela nossa equipe e já está em processo de reserva.</p>
                
                <div style="background-color: #F0FDF4; border-left: 4px solid #16A34A; padding: 15px; border-radius: 4px; margin: 25px 0;">
                    <p style="margin: 0; color: #166534; font-size: 14.5px;">
                        ⏳ <b>Próximo Passo:</b> Nossa equipe entrará em contato via WhatsApp em instantes para confirmar a taxa de entrega e enviar o link/chave de pagamento.
                    </p>
                </div>
                
                <h4 style="color: #1E293B; border-bottom: 2px dashed #E2E8F0; padding-bottom: 8px; margin-top: 35px; font-size: 16px;">📋 Resumo da Encomenda</h4>
                <ul style="font-size: 14.5px; color: #475569; line-height: 1.8; list-style-type: none; padding-left: 0;">
                    <li>🎁 <b>Presente:</b> {cesta_nome}</li>
                    <li>🎀 <b>Extras:</b> {extras}</li>
                    <li>💝 <b>Para:</b> {destinatario}</li>
                    <li>📅 <b>Entrega:</b> {data_ent} ({periodo})</li>
                </ul>
                
                {bloco_itens}
                
                <div style="margin-top: 25px; font-size: 18px; color: #16A34A; padding-top: 12px; border-top: 1px solid #f1f5f9;">💰 <b>Valor Estimado (Sem Frete):</b> {valor_tot}</div>
            </div>
            
            <div style="background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 12px; color: #64748B;">
                <p style="margin: 0;">Obrigado por escolher a Doce Cesta Brasília! Feito com amor ❤️</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    texto_plano = (
        f"Seu pedido #{pedido_id} foi recebido com sucesso!\n\n"
        f"Presente: {resumo.get('cesta_nome', '')}\n"
        f"Extras: {resumo.get('adicionais_str', 'Nenhum')}\n"
        f"Para: {resumo.get('destinatario_nome', '')}\n"
        f"Entrega: {resumo.get('data_entrega', '')} ({resumo.get('periodo_entrega', '')})\n"
        + (f"\nItens escolhidos na sua cesta:\n{texto_itens}" if texto_itens else "")
        + f"\nValor estimado (sem frete): {resumo.get('valor_total', '')}\n"
    )
    msg.attach(MIMEText(texto_plano, "plain"))
    msg.attach(MIMEText(html_corpo, "html"))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de confirmação enviado."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


def enviar_email_entrega(email_destino, cliente_nome, pedido_id, resumo, foto_url=None):
    """
    Dispara o e-mail de "cesta entregue", com layout mais festivo/comemorativo.
    'resumo' aceita: cesta_nome, destinatario_nome, hora_entrega, quem_recebeu, endereco.
    'foto_url', se houver, mostra a foto Polaroid registrada na entrega (se existir).
    """
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")

    if not remetente or not senha or not email_destino:
        return False, "⚠️ Credenciais de e-mail ausentes ou e-mail de destino inválido."

    def esc(v, padrao=""):
        return html.escape(str(v)) if v not in (None, "") else padrao

    cliente_nome_seg = esc(cliente_nome, "Cliente")
    pedido_id_seg = esc(pedido_id)
    cesta_nome_seg = esc(resumo.get("cesta_nome"), "sua cesta")
    destinatario_seg = esc(resumo.get("destinatario_nome"), "—")
    hora_entrega_seg = esc(resumo.get("hora_entrega"), "agora há pouco")
    quem_recebeu_seg = esc(resumo.get("quem_recebeu"), "")
    endereco_seg = esc(resumo.get("endereco"), "")

    assunto = f"🎉 Entregue! Seu pedido #{pedido_id} chegou com sucesso"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta Brasília <{remetente}>"
    msg["To"] = email_destino

    bloco_recebedor = (
        f'<div style="display:flex; align-items:center; gap:10px; background:#F0FDF4; border-radius:10px; padding:12px 16px; margin-top:18px;">'
        f'<span style="font-size:20px;">🖊️</span>'
        f'<div><div style="font-size:11px; font-weight:800; color:#166534; text-transform:uppercase; letter-spacing:.04em;">Recebido por</div>'
        f'<div style="font-size:15px; color:#14532D; font-weight:700;">{quem_recebeu_seg}</div></div></div>'
        if quem_recebeu_seg else ""
    )

    bloco_foto = (
        f'<div style="display:flex; align-items:center; gap:10px; background:#FEF3E2; border-radius:10px; padding:12px 16px; margin-top:18px;">'
        f'<span style="font-size:20px;">📸</span>'
        f'<div style="font-size:13.5px; color:#7C4A03; font-weight:600;">Seu pedido também tem fotos Polaroid registradas — combinadas com muito carinho para esse presente!</div>'
        f'</div>'
        if foto_url else ""
    )

    html_corpo = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #FAF3EA; padding: 24px 12px; margin:0;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 40px rgba(197,114,31,0.12);">

            <!-- Faixa comemorativa -->
            <div style="background: linear-gradient(135deg, #16A34A 0%, #15803D 60%, #14532D 100%); padding: 40px 24px; text-align: center; position: relative;">
                <div style="font-size: 54px; line-height:1;">🎉🧺🎊</div>
                <h1 style="color: #ffffff; margin: 14px 0 4px 0; font-size: 26px; font-weight: 800; letter-spacing: 0.3px;">Entrega Concluída!</h1>
                <p style="color: #DCFCE7; margin: 0; font-size: 14px; font-weight: 600;">Pedido #{pedido_id_seg} • {hora_entrega_seg}</p>
            </div>

            <div style="padding: 34px 30px 10px 30px;">
                <h3 style="color: #0F172A; font-size: 19px; margin-top: 0;">Oi, {cliente_nome_seg}! 💛</h3>
                <p style="color: #475569; font-size: 15px;">
                    É com muita alegria que avisamos: <b>{cesta_nome_seg}</b> acabou de ser entregue com todo o
                    carinho que a Doce Cesta Brasília coloca em cada pedido. Esperamos que essa surpresa arranque
                    um sorriso enorme de <b>{destinatario_seg}</b>! ✨
                </p>

                {bloco_foto}

                <div style="background-color: #FFF7ED; border-left: 4px solid #C5721F; padding: 16px 18px; border-radius: 8px; margin: 26px 0 6px 0;">
                    <div style="font-size:11px; font-weight:800; color:#9A3412; text-transform:uppercase; letter-spacing:.04em; margin-bottom:6px;">📍 Local de entrega</div>
                    <div style="font-size: 14.5px; color: #7C2D12;">{endereco_seg}</div>
                </div>

                {bloco_recebedor}

                <div style="text-align:center; margin: 34px 0 10px 0;">
                    <p style="font-size: 14px; color:#64748B; margin-bottom: 14px;">Adorou a experiência? Conte pra gente ou faça um novo pedido:</p>
                    <a href="https://wa.me/" style="display:inline-block; background: linear-gradient(135deg, #C5721F 0%, #A65D14 100%); color:#ffffff; text-decoration:none; font-weight:800; font-size:14px; padding:14px 28px; border-radius:30px; box-shadow:0 6px 16px rgba(197,114,31,0.35);">
                        🧺 Fazer Novo Pedido
                    </a>
                </div>
            </div>

            <div style="background-color: #FAF3EA; padding: 22px; text-align: center; font-size: 12px; color: #94A3B8; border-top: 1px dashed #EADFCF;">
                <p style="margin: 0 0 4px 0; font-size: 13px; color:#A65D14; font-weight:700;">Doce Cesta Brasília</p>
                <p style="margin: 0;">Obrigado por espalhar carinho através de nós. Até a próxima encomenda! ❤️</p>
            </div>

        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText("Seu pedido foi entregue com sucesso! Abra este e-mail num leitor com suporte a HTML para ver os detalhes completos.", "plain"))
    msg.attach(MIMEText(html_corpo, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de entrega enviado."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"
