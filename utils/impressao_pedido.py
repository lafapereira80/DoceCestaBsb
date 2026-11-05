import io
import json
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from services.pedido_adicional_service import listar_adicionais_pedido
from utils.formatacao import NOME_LOJA  # <-- Trazendo o nome dinâmico!

# =====================================================
# CONFIGURAÇÃO DOS FORMATOS
# =====================================================
LARGURA_ETIQUETA = 7 * cm
ALTURA_ETIQUETA = 10 * cm

# =====================================================
# ESCUDO XML (O segredo para o PDF não ficar em branco)
# =====================================================
def texto_seguro(texto):
    if not texto: return "-"
    texto = str(texto).replace("\n", " ")
    texto = texto.replace("&", "&amp;")
    texto = texto.replace("<", "&lt;")
    texto = texto.replace(">", "&gt;")
    return texto

def limitar_texto(texto, tamanho=80):
    if not texto: return "-"
    texto = str(texto).replace("\n", " ")
    if len(texto) > tamanho:
        texto = texto[:tamanho] + "..."
    return texto_seguro(texto)

# =====================================================
# NORMALIZA JSON E DATAS
# =====================================================
def normalizar_itens_consulta(valor):
    if not valor: return {}
    if isinstance(valor, dict): return valor
    if isinstance(valor, str):
        try: return json.loads(valor)
        except: return {}
    return {}

def formatar_data(data):
    if not data: return "-"
    try:
        if isinstance(data, str):
            data = data[:10]
            data = datetime.strptime(data, "%Y-%m-%d")
        return data.strftime("%d/%m/%Y")
    except:
        return str(data)

def formatar_horario(horario):
    if not horario: return ""
    return str(horario)[:5]

# =====================================================
# ESTILOS PDF
# =====================================================
styles = getSampleStyleSheet()

estilo_destaque = ParagraphStyle("destaque", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=TA_LEFT)
estilo_normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=8, leading=10, alignment=TA_LEFT)
estilo_item = ParagraphStyle("item", parent=styles["Normal"], fontSize=7, leading=8, alignment=TA_LEFT)
estilo_observacao = ParagraphStyle("observacao", parent=styles["Normal"], fontSize=7, leading=8, alignment=TA_LEFT)

# =====================================================
# BUSCA ITENS PARA MONTAGEM
# =====================================================
def buscar_itens_montagem(pedido):
    itens = []
    produtos = pedido.get("produtos", "")
    if produtos:
        for item in str(produtos).split("\n"):
            item = item.strip()
            if item:
                item = item.replace('•', '').strip()
                itens.append(item)

    try:
        adicionais = listar_adicionais_pedido(pedido["id"])
        for adicional in adicionais:
            nome = adicional.get("nome_produto", "")
            if nome:
                itens.append(f"[Adicional] {nome}")
    except Exception:
        pass

    consulta = normalizar_itens_consulta(pedido.get("itens_consulta"))
    for nome in consulta.keys():
        nome_marcado = f"[Extra] {nome}"
        if nome_marcado not in itens:
            itens.append(nome_marcado)

    return itens

def montar_itens_pdf(itens):
    if not itens:
        return Paragraph("Sem itens na montagem", estilo_item)
    linhas = []
    for item in itens:
        item_seguro = texto_seguro(item)
        linhas.append(f"[  ] {item_seguro}")
    return Paragraph("<br/>".join(linhas), estilo_item)

# =====================================================
# MONTA CONTEÚDO DA ETIQUETA
# =====================================================
def montar_conteudo_etiqueta(pedido):
    elementos = []

    cliente_nome = limitar_texto(pedido.get("cliente_nome", "-"), 30)
    cliente_tel = texto_seguro(pedido.get("cliente_telefone", "-"))
    dest_nome = limitar_texto(pedido.get("destinatario_nome", "-"), 30)
    dest_tel = texto_seguro(pedido.get("destinatario_telefone", "-"))

    cesta = limitar_texto(pedido.get("cesta_nome", "-"), 40)
    data = formatar_data(pedido.get("data_entrega"))
    periodo = texto_seguro(pedido.get("periodo_entrega", ""))
    horario = texto_seguro(formatar_horario(pedido.get("horario_combinado")))
    horario_str = f" ({horario})" if horario else ""

    elementos.append(Paragraph(f"<b>CESTA: {cesta.upper()}</b>", estilo_destaque))
    elementos.append(Spacer(1, 4))
    elementos.append(Paragraph(f"<b>COMPRADOR:</b> {cliente_nome} | Tel: {cliente_tel}", estilo_normal))
    elementos.append(Paragraph(f"<b>HOMENAGEADO:</b> {dest_nome} | Tel: {dest_tel}", estilo_normal))
    elementos.append(Paragraph(f"<b>ENTREGA:</b> {data} - {periodo}{horario_str}", estilo_normal))
    elementos.append(Spacer(1, 4))
    elementos.append(Paragraph("<b>ITENS PARA MONTAGEM:</b>", estilo_normal))
    elementos.append(Spacer(1, 2))
    elementos.append(montar_itens_pdf(buscar_itens_montagem(pedido)))
    elementos.append(Spacer(1, 5))

    endereco = limitar_texto(pedido.get("endereco", "-"), 90)
    elementos.append(Paragraph(f"<b>ENDERECO:</b> {endereco}", estilo_observacao))
    
    mensagem = limitar_texto(pedido.get("mensagem", "-"), 90)
    elementos.append(Paragraph(f"<b>CARTAO:</b> {mensagem}", estilo_observacao))

    pedido_especial = limitar_texto(pedido.get("pedido_especial", ""), 90)
    if pedido_especial and pedido_especial != "-":
        elementos.append(Paragraph(f"<b>ATENCAO - PEDIDO ESPECIAL:</b> {pedido_especial}", estilo_observacao))

    observacao = limitar_texto(pedido.get("anotacoes_internas", ""), 100)
    if observacao and observacao != "-":
        elementos.append(Spacer(1, 2))
        elementos.append(Paragraph(f"<b>OBS INTERNA:</b> {observacao}", estilo_observacao))

    return elementos

# =====================================================
# CRIA CAIXA 7X10 PARA FOLHA A4
# =====================================================
def criar_caixa_7x10(pedido):
    conteudo = montar_conteudo_etiqueta(pedido)
    tabela = Table([[conteudo]], colWidths=[LARGURA_ETIQUETA - 0.3*cm], rowHeights=[ALTURA_ETIQUETA - 0.3*cm])
    tabela.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.8, None),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5)
    ]))
    return tabela

# =====================================================
# PDF A4 E INDIVIDUAL
# =====================================================
def gerar_pdf_a4(pedidos):
    arquivo = io.BytesIO()
    doc = SimpleDocTemplate(arquivo, pagesize=A4, rightMargin=0.4*cm, leftMargin=0.4*cm, topMargin=0.4*cm, bottomMargin=0.4*cm)
    
    elementos = []
    caixas = [criar_caixa_7x10(pedido) for pedido in pedidos]

    while len(caixas) % 12 != 0:
        caixas.append("")

    for pagina_inicio in range(0, len(caixas), 12):
        pagina = caixas[pagina_inicio : pagina_inicio + 12]
        linhas = []
        for i in range(0, 12, 3):
            linhas.append(pagina[i:i+3])

        tabela = Table(linhas, colWidths=[LARGURA_ETIQUETA, LARGURA_ETIQUETA, LARGURA_ETIQUETA], rowHeights=[ALTURA_ETIQUETA] * 4)
        tabela.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING", (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0)
        ]))

        elementos.append(tabela)
        if pagina_inicio + 12 < len(caixas):
            elementos.append(PageBreak())

    doc.build(elementos)
    arquivo.seek(0)
    return arquivo.getvalue()

def gerar_pdf_individual(pedidos):
    arquivo = io.BytesIO()
    doc = SimpleDocTemplate(arquivo, pagesize=(LARGURA_ETIQUETA, ALTURA_ETIQUETA), rightMargin=0.3*cm, leftMargin=0.3*cm, topMargin=0.3*cm, bottomMargin=0.3*cm)

    elementos = []
    for indice, pedido in enumerate(pedidos):
        conteudo = montar_conteudo_etiqueta(pedido)
        elementos.append(KeepTogether(conteudo))
        if indice < len(pedidos) - 1:
            elementos.append(PageBreak())

    doc.build(elementos)
    arquivo.seek(0)
    return arquivo.getvalue()

def gerar_pdf_pedidos(pedidos, formato):
    if formato.startswith("📄"):
        return gerar_pdf_a4(pedidos)
    return gerar_pdf_individual(pedidos)
