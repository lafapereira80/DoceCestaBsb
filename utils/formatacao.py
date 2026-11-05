import urllib.parse
import re
from datetime import datetime

# ==========================================
# DADOS GERAIS DA LOJA (Central de Controle)
# ==========================================
NOME_LOJA = "Doce Cesta Brasília"
NOME_LOJA_CURTO = "Doce Cesta"
TELEFONE_WHATSAPP = "5561999759079"
TELEFONE_EXIBICAO = "(61) 99975-9079"
INSTAGRAM_ARROBA = "@docecestabrasilia"
INSTAGRAM_URL = "https://instagram.com/docecestabrasilia"

# ==========================================
# FUNÇÕES GLOBAIS DE MATEMÁTICA E DATA
# ==========================================
def formatar_moeda(valor):
    """Garante que R$ 15.5 vire R$ 15,50"""
    try: 
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: 
        return "0,00"

def tratar_preco(valor):
    """Converte o texto digitado pelo usuário em número seguro para o banco"""
    if valor is None or str(valor).strip() == "": return 0.0
    try: return float(str(valor).replace(",", "."))
    except: return 0.0

def formatar_data_br(d_str):
    """Converte padrão americano do banco para DD/MM/YYYY"""
    if not d_str: return "-"
    try: return datetime.strptime(str(d_str)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(d_str)

def gerar_link_wpp(telefone, texto):
    """Gera um link clicável do WhatsApp blindado contra erros de digitação"""
    fone_limpo = re.sub(r'\D', '', str(telefone))
    if not fone_limpo: return "#"
    # Adiciona o 55 do Brasil se o usuário digitou apenas DDD+Número
    if len(fone_limpo) <= 11: fone_limpo = f"55{fone_limpo}"
    return f"https://wa.me/{fone_limpo}?text={urllib.parse.quote(texto)}"

# ==========================================
# GERADOR DE RESUMO PARA WHATSAPP
# ==========================================
def gerar_resumo_whatsapp(cliente, destinatario, data, periodo, local, itens_str, subtotal, desconto, frete, total, pagamento, link_pagamento=None):
    """Gera o texto padronizado do WhatsApp para qualquer tela do sistema"""
    texto = f"*RESUMO DO PEDIDO - {NOME_LOJA.upper()}* 🎁\n\n"
    texto += f"👤 *De:* {cliente}\n"
    texto += f"💝 *Para:* {destinatario}\n"
    texto += f"📅 *Entrega:* {data} ({periodo})\n"
    texto += f"📍 *Local:* {local}\n\n"
    texto += f"*ITENS:*\n{itens_str}\n\n"
    texto += f"*VALORES:*\n"
    texto += f"💰 Subtotal: R$ {formatar_moeda(subtotal)}\n"
    
    if float(desconto) > 0:
        texto += f"🔻 Desconto: - R$ {formatar_moeda(desconto)}\n"
        
    texto += f"🚚 Frete: R$ {formatar_moeda(frete)}\n"
    texto += f"━━━━━━━━━━━━━━━━━━━━\n"
    texto += f"*TOTAL:* R$ {formatar_moeda(total)}\n\n"
    
    if link_pagamento:
        texto += f"💳 *PAGAMENTO SEGURO:*\n"
        texto += f"Acesse o link abaixo para pagar via Pix ou Cartão:\n"
        texto += f"{link_pagamento}\n\n"
    else:
        texto += f"💳 *Pagamento:* {pagamento}\n\n"
    
    texto += "Qualquer dúvida, estamos à disposição! 🌻"
    return texto
