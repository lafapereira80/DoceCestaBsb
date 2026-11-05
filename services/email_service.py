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
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")
    
    if not remetente or not senha:
        return False, "⚠️ E-mail ou Senha não configurados nos Secrets do sistema."
        
    assunto = f"Detalhes do seu Pedido #{pedido_id} - Doce Cesta"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta <{remetente}>"
    msg["To"] = email_destino
    
    html_botao = ""
    if link_pagamento:
        html_botao = f"""
        <div style="text-align: center; margin-top: 25px;">
            <a href="{link_pagamento}" style="background-color: #137333; color: white; padding: 14px 24px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">💳 CLIQUE AQUI PARA PAGAR</a>
        </div>
        """
        
    corpo_html = f"""
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
    msg.attach(MIMEText(corpo_html, "html"))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "✅ E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


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
    
    cesta_nome = resumo.get('cesta_nome', '')
    destinatario = resumo.get('destinatario_nome', '')
    data_ent = resumo.get('data_entrega', '')
    periodo = resumo.get('periodo_entrega', '')
    valor_tot = resumo.get('valor_total', '')
    extras = resumo.get('adicionais_str', 'Nenhum')
    itens_personalizados = resumo.get('itens_personalizados_str', 'Nenhum')
    tem_polaroid = resumo.get('tem_polaroid', False)
    
    corpo_html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            
            <div style="background: linear-gradient(135deg, #C5721F 0%, #A65D14 100%); padding: 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">🎁 Pedido Recebido!</h1>
            </div>
            
            <div style="padding: 30px;">
                <h3 style="color: #0F172A; font-size: 18px; margin-top: 0;">Olá, {cliente_nome}!</h3>
                <p style="color: #475569; font-size: 15px;">Que alegria! Seu pedido <b>#{pedido_id}</b> foi recebido com sucesso pela nossa equipe e já está em processo de reserva.</p>
                
                <div style="background-color: #F0FDF4; border-left: 4px solid #16A34A; padding: 15px; border-radius: 4px; margin: 25px 0;">
                    <p style="margin: 0; color: #166534; font-size: 14.5px;">
                        ⏳ <b>Próximo Passo:</b> Nossa equipe entrará em contato via WhatsApp em instantes para confirmar a taxa de entrega e enviar o link/chave de pagamento.
                    </p>
                </div>
                
                <h4 style="color: #1E293B; border-bottom: 2px dashed #E2E8F0; padding-bottom: 8px; margin-top: 35px; font-size: 16px;">📋 Resumo da Encomenda</h4>
                <ul style="font-size: 14.5px; color: #475569; line-height: 1.8; list-style-type: none; padding-left: 0;">
                    <li>🎁 <b>Presente:</b> {cesta_nome}</li>
                    <li>🍓 <b>Itens Personalizados:</b><br><span style="white-space: pre-line;">{itens_personalizados}</span></li>
                    <li>🎀 <b>Extras:</b> {extras}</li>
                    <li>📷 <b>Fotos Polaroid:</b> {'Sim' if tem_polaroid else 'Não'}</li>
                    <li>💝 <b>Para:</b> {destinatario}</li>
                    <li>📅 <b>Entrega:</b> {data_ent} ({periodo})</li>
                    <li style="margin-top: 15px; font-size: 18px; color: #16A34A; padding-top: 10px; border-top: 1px solid #f1f5f9;">💰 <b>Valor Estimado (Sem Frete):</b> {valor_tot}</li>
                </ul>
            </div>
            
            <div style="background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 12px; color: #64748B;">
                <p style="margin: 0;">Obrigado por escolher a Doce Cesta Brasília! Feito com amor ❤️</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText("Seu pedido foi recebido com sucesso! Acesse este e-mail através de um leitor com suporte a HTML para ver os detalhes completos.", "plain"))
    msg.attach(MIMEText(corpo_html, "html"))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de confirmação enviado."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


def enviar_email_recibo(email_destino, cliente_nome, pedido_id, resumo_recibo, dados_pagamento, itens_detalhados=None):
    """
    Envia um e-mail em formato de recibo oficial após confirmação de pagamento.
    resumo_recibo: dicionário com detalhes do pedido (cliente, endereço, etc.)
    dados_pagamento: dicionário com informações da InfinitePay (transaction_id, data_pagamento, valor, status)
    itens_detalhados: lista de dicionários {"nome": str, "valor": float}
    """
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")
    if not remetente or not senha or not email_destino:
        return False, "Credenciais de e-mail ausentes ou e-mail de destino inválido."

    assunto = f"Recibo do Pedido #{pedido_id} - Doce Cesta Brasília"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta <{remetente}>"
    msg["To"] = email_destino

    # Dados do resumo
    cesta_nome = html.escape(str(resumo_recibo.get('cesta_nome', '')))
    destinatario = html.escape(str(resumo_recibo.get('destinatario_nome', '')))
    data_entrega = html.escape(str(resumo_recibo.get('data_entrega', '')))
    periodo = html.escape(str(resumo_recibo.get('periodo_entrega', '')))
    endereco = html.escape(str(resumo_recibo.get('endereco', '')))
    valor_total = html.escape(str(resumo_recibo.get('valor_total', '')))

    # Dados do pagamento
    transacao_id = html.escape(str(dados_pagamento.get('transaction_id', 'N/A')))
    data_pagamento = html.escape(str(dados_pagamento.get('data_pagamento', 'N/A')))
    forma_pagamento = html.escape(str(dados_pagamento.get('forma_pagamento', 'InfinitePay')))
    valor_pago = html.escape(str(dados_pagamento.get('valor_pago', '')))
    status_pagamento = html.escape(str(dados_pagamento.get('status', 'Aprovado')))

    # Monta tabela de itens detalhados
    itens_html = ""
    if itens_detalhados:
        for item in itens_detalhados:
            nome_item = html.escape(str(item.get("nome", "")))
            try:
                valor_item = f"R$ {float(item.get('valor', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except:
                valor_item = "R$ 0,00"
            itens_html += f"<tr><td style='padding:8px; border-bottom:1px solid #e2e8f0;'>{nome_item}</td><td style='padding:8px; border-bottom:1px solid #e2e8f0; text-align:right;'>{valor_item}</td></tr>"
    else:
        # Fallback: exibe apenas o total
        itens_html = f"<tr><td style='padding:8px;'>Total do Pedido</td><td style='padding:8px; text-align:right;'>{valor_total}</td></tr>"

    corpo_html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">

            <div style="background: linear-gradient(135deg, #137333 0%, #0d4e22 100%); padding: 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800;">✅ Pagamento Confirmado</h1>
            </div>

            <div style="padding: 30px;">
                <h3 style="color: #0F172A; font-size: 18px; margin-top: 0;">Olá, {cliente_nome}!</h3>
                <p style="color: #475569; font-size: 15px;">Recebemos o pagamento do seu pedido <b>#{pedido_id}</b>. Abaixo está o recibo detalhado.</p>

                <div style="background-color: #F0FDF4; border-left: 4px solid #16A34A; padding: 15px; border-radius: 4px; margin: 25px 0;">
                    <p style="margin: 0; color: #166534; font-size: 14.5px;">
                        💳 <b>Transação:</b> {transacao_id}<br>
                        📅 <b>Data do pagamento:</b> {data_pagamento}<br>
                        💰 <b>Valor pago:</b> {valor_pago}<br>
                        🏦 <b>Forma:</b> {forma_pagamento}<br>
                        📌 <b>Status:</b> {status_pagamento}
                    </p>
                </div>

                <h4 style="color: #1E293B; border-bottom: 2px dashed #E2E8F0; padding-bottom: 8px; margin-top: 35px; font-size: 16px;">📋 Itens da Encomenda</h4>
                <table style="width:100%; border-collapse:collapse; margin:15px 0;">
                    <thead>
                        <tr style="background:#f1f5f9;">
                            <th style="text-align:left; padding:8px;">Item</th>
                            <th style="text-align:right; padding:8px;">Valor</th>
                        </tr>
                    </thead>
                    <tbody>
                        {itens_html}
                    </tbody>
                </table>

                <div style="margin-top: 20px;">
                    <p style="font-size: 14.5px; color: #475569; margin: 5px 0;">
                        💝 <b>Para:</b> {destinatario}<br>
                        📅 <b>Entrega:</b> {data_entrega} ({periodo})<br>
                        📍 <b>Endereço:</b> {endereco}
                    </p>
                </div>

                <div style="margin-top: 25px; font-size: 18px; color: #16A34A; padding-top: 10px; border-top: 2px solid #16A34A; text-align: right;">
                    💰 <b>Total do Pedido:</b> {valor_total}
                </div>
            </div>

            <div style="background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 12px; color: #64748B;">
                <p style="margin: 0;">Obrigado por comprar conosco! Em breve você receberá atualizações sobre a entrega.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText("Seu pagamento foi confirmado. Abra este e-mail em um leitor com suporte a HTML para ver o recibo completo.", "plain"))
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de recibo enviado."
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
        f'<div style="margin-top:24px; text-align:center;">'
        f'<img src="{esc(foto_url)}" alt="Foto da entrega" style="max-width:100%; border-radius:14px; border:6px solid #ffffff; box-shadow:0 10px 30px rgba(0,0,0,0.15); transform:rotate(-1.5deg);">'
        f'<div style="font-size:12px; color:#94A3B8; margin-top:10px; font-style:italic;">📸 Registro do momento da entrega</div>'
        f'</div>'
        if foto_url else ""
    )

    corpo_html = f"""
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
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de entrega enviado."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


def enviar_email_cupom(email_destino, cliente_nome, codigo_cupom, mensagem_personalizada, cupom_info=None):
    """
    Envia um cupom de cortesia/promocional por e-mail.
    cupom_info: dict opcional com 'tipo', 'valor', 'valido_ate' para exibir os detalhes.
    """
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")

    if not remetente or not senha or not email_destino:
        return False, "⚠️ Credenciais de e-mail ausentes ou e-mail de destino inválido."

    assunto = f"🎁 Um mimo especial pra você, {cliente_nome}!"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta <{remetente}>"
    msg["To"] = email_destino

    detalhe_desconto = ""
    validade_txt = ""
    if cupom_info:
        tipo = cupom_info.get("tipo")
        valor = cupom_info.get("valor")
        if tipo == "percentual":
            detalhe_desconto = f"{valor:.0f}% de desconto"
        elif tipo == "fixo":
            detalhe_desconto = f"R$ {valor:.2f} de desconto"
        elif tipo == "cortesia_total":
            detalhe_desconto = "Pedido 100% grátis"
        if cupom_info.get("valido_ate"):
            validade_txt = f"Válido até {str(cupom_info['valido_ate'])[:10]}"

    mensagem_html = html.escape(mensagem_personalizada).replace("\n", "<br>")

    corpo_html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #FAF3EA; padding: 24px 12px; margin:0;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 40px rgba(197,114,31,0.12);">

            <div style="background: linear-gradient(135deg, #C5721F 0%, #A65D14 100%); padding: 36px 24px; text-align: center;">
                <div style="font-size: 46px; line-height:1;">🎁</div>
                <h1 style="color: #ffffff; margin: 12px 0 0 0; font-size: 24px; font-weight: 800;">Um presente pra você!</h1>
            </div>

            <div style="padding: 30px;">
                <p style="color: #475569; font-size: 15px;">{mensagem_html}</p>

                <div style="background: linear-gradient(135deg, #FFF7ED 0%, #FEF3E2 100%); border: 2px dashed #C5721F; border-radius: 14px; padding: 22px; text-align: center; margin: 26px 0;">
                    <div style="font-size: 11px; font-weight: 800; color: #9A3412; text-transform: uppercase; letter-spacing: .06em;">Seu código de cupom</div>
                    <div style="font-size: 28px; font-weight: 900; color: #C5721F; letter-spacing: 2px; margin: 8px 0;">{html.escape(codigo_cupom)}</div>
                    {f'<div style="font-size:14px; color:#7C2D12; font-weight:700;">{html.escape(detalhe_desconto)}</div>' if detalhe_desconto else ''}
                    {f'<div style="font-size:12px; color:#94A3B8; margin-top:6px;">{html.escape(validade_txt)}</div>' if validade_txt else ''}
                </div>

                <div style="text-align:center; margin-top: 20px;">
                    <a href="https://www.docecestabrasilia.com.br/Inicio" style="display:inline-block; background: linear-gradient(135deg, #16A34A 0%, #15803D 100%); color:#ffffff; text-decoration:none; font-weight:800; font-size:14px; padding:14px 28px; border-radius:30px; box-shadow:0 6px 16px rgba(22,163,74,0.3);">
                        🧺 Usar meu cupom agora
                    </a>
                </div>
            </div>

            <div style="background-color: #FAF3EA; padding: 20px; text-align: center; font-size: 12px; color: #94A3B8; border-top: 1px dashed #EADFCF;">
                <p style="margin: 0;">Doce Cesta Brasília — feito com carinho pra você. ❤️</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(mensagem_personalizada, "plain"))
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de cupom enviado."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


def enviar_email_lead_corporativo(email_destino, contato_nome, empresa_nome):
    """Confirmação automática enviada ao lead corporativo assim que ele preenche o formulário público."""
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")
    if not remetente or not senha or not email_destino:
        return False, "⚠️ Credenciais de e-mail ausentes ou e-mail de destino inválido."

    assunto = "Recebemos sua solicitação — Doce Cesta Brasília Corporativo"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta Corporativo <{remetente}>"
    msg["To"] = email_destino

    corpo_html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 24px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 800;">🏢 Doce Cesta Corporativo</h1>
            </div>
            <div style="padding: 30px;">
                <h3 style="color: #0F172A; font-size: 18px; margin-top: 0;">Olá, {html.escape(contato_nome)}!</h3>
                <p style="color: #475569; font-size: 15px;">
                    Recebemos a solicitação de orçamento da <b>{html.escape(empresa_nome)}</b>. Nossa equipe comercial
                    vai analisar os detalhes e retornar o contato em até <b>1 dia útil</b>, com uma proposta personalizada.
                </p>
                <p style="color: #475569; font-size: 15px;">Se preferir agilizar, pode responder este e-mail com mais detalhes ou horários preferenciais de contato.</p>
            </div>
            <div style="background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 12px; color: #64748B;">
                <p style="margin: 0;">Doce Cesta Brasília — Presentes corporativos com identidade.</p>
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(f"Olá {contato_nome}, recebemos a solicitação da {empresa_nome}. Retornaremos em até 1 dia útil.", "plain"))
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail de confirmação enviado."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"


def enviar_email_orcamento_corporativo(email_destino, contato_nome, empresa_nome, itens_html, valor_unitario, quantidade, valor_total, link_pagamento=None):
    """Envia a proposta corporativa formatada (itens escolhidos + valores + link de pagamento opcional)."""
    remetente = st.secrets.get("EMAIL_SENDER", "")
    senha = st.secrets.get("EMAIL_PASSWORD", "")
    if not remetente or not senha or not email_destino:
        return False, "⚠️ Credenciais de e-mail ausentes ou e-mail de destino inválido."

    assunto = f"📋 Sua proposta corporativa — Doce Cesta Brasília"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Doce Cesta Corporativo <{remetente}>"
    msg["To"] = email_destino

    valor_unitario_fmt = f"R$ {valor_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_total_fmt = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    botao_pagamento = ""
    if link_pagamento:
        botao_pagamento = f"""
        <div style="text-align:center; margin-top: 24px;">
            <a href="{html.escape(link_pagamento)}" style="display:inline-block; background: linear-gradient(135deg, #16A34A 0%, #15803D 100%); color:#ffffff; text-decoration:none; font-weight:800; font-size:14px; padding:14px 32px; border-radius:30px; box-shadow:0 6px 16px rgba(22,163,74,0.3);">
                💳 Confirmar e Pagar
            </a>
        </div>
        """

    corpo_html = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.5; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 620px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 26px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 21px; font-weight: 800;">📋 Proposta Corporativa</h1>
            </div>
            <div style="padding: 30px;">
                <p style="color: #475569; font-size: 15px;">Olá, {html.escape(contato_nome)}! Segue a proposta preparada para a <b>{html.escape(empresa_nome)}</b>:</p>

                <div style="background: #F8FAFC; border-radius: 10px; padding: 16px; margin: 18px 0;">
                    {itens_html}
                </div>

                <table style="width:100%; font-size: 14px; margin-top: 10px;">
                    <tr><td style="padding:6px 0; color:#64748B;">Valor unitário</td><td style="text-align:right; font-weight:700;">{valor_unitario_fmt}</td></tr>
                    <tr><td style="padding:6px 0; color:#64748B;">Quantidade</td><td style="text-align:right; font-weight:700;">{quantidade}</td></tr>
                    <tr><td style="padding:10px 0; border-top:1px solid #E2E8F0; font-size:16px; font-weight:800; color:#0F172A;">Total</td><td style="text-align:right; padding:10px 0; border-top:1px solid #E2E8F0; font-size:16px; font-weight:800; color:#16A34A;">{valor_total_fmt}</td></tr>
                </table>

                {botao_pagamento}
            </div>
            <div style="background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 12px; color: #64748B;">
                <p style="margin: 0;">Doce Cesta Brasília — Presentes corporativos com identidade.</p>
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(f"Proposta para {empresa_nome}: {quantidade}x a {valor_unitario_fmt} = {valor_total_fmt}.", "plain"))
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "Proposta enviada por e-mail."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"
