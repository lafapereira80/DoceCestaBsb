#!/usr/bin/env python3
"""
Injeta meta tags de SEO direto no index.html do Streamlit instalado na VM.
Roda depois de `pip install -r requirements.txt` em todo deploy, porque
uma atualização do Streamlit sobrescreve esse arquivo com o padrão de fábrica.

Uso na VM:
    python3 patch_streamlit_seo.py
"""

import re
import streamlit as st
from pathlib import Path

INDEX_HTML = Path(st.__file__).parent / "static" / "index.html"

MARCADOR_INICIO = "<!-- SEO-DOCECESTA-START -->"
MARCADOR_FIM = "<!-- SEO-DOCECESTA-END -->"

BLOCO_SEO = f"""{MARCADOR_INICIO}
<meta name="description" content="Cestas de café da manhã e presentes em Brasília - DF. Monte sua cesta, escolha os adicionais e receba no mesmo dia.">
<meta name="keywords" content="cesta de café da manhã brasília, cesta de presente brasília, doce cesta brasília, cesta café da manhã DF">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://www.docecestabrasilia.com.br/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Doce Cesta Brasília">
<meta property="og:title" content="Doce Cesta Brasília | Cestas de Café da Manhã e Presentes">
<meta property="og:description" content="Cestas de café da manhã e presentes em Brasília - DF. Monte sua cesta, escolha os adicionais e receba no mesmo dia.">
<meta property="og:url" content="https://www.docecestabrasilia.com.br/">
<meta property="og:image" content="https://www.docecestabrasilia.com.br/assets/logo.webp">
<meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Doce Cesta Brasília">
<meta name="twitter:description" content="Cestas de café da manhã e presentes em Brasília - DF.">
<meta name="twitter:image" content="https://www.docecestabrasilia.com.br/assets/logo.webp">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Bakery",
  "name": "Doce Cesta Brasília",
  "image": "https://www.docecestabrasilia.com.br/assets/logo.webp",
  "url": "https://www.docecestabrasilia.com.br/",
  "areaServed": {{
    "@type": "City",
    "name": "Brasília"
  }},
  "priceRange": "$$"
}}
</script>
{MARCADOR_FIM}
"""

TITULO_NOVO = "<title>Doce Cesta Brasília | Cestas de Café da Manhã e Presentes em Brasília - DF</title>"


def main():
    if not INDEX_HTML.exists():
        raise FileNotFoundError(f"index.html do Streamlit não encontrado em: {INDEX_HTML}")

    html = INDEX_HTML.read_text(encoding="utf-8")

    # Remove um bloco antigo, se já tiver sido injetado antes (evita duplicar a cada deploy)
    html = re.sub(
        re.escape(MARCADOR_INICIO) + r".*?" + re.escape(MARCADOR_FIM) + r"\n?",
        "",
        html,
        flags=re.S,
    )

    # Título
    html = re.sub(r"<title>.*?</title>", TITULO_NOVO, html, count=1, flags=re.S)

    # Injeta o bloco de SEO antes de </head>
    html = html.replace("</head>", BLOCO_SEO + "</head>")

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"OK — SEO injetado em {INDEX_HTML}")


if __name__ == "__main__":
    main()
