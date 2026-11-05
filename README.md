# DoceCestaBrasilia
## Design system v2

- `utils/ui.py` — tema (`tema_loja()` / `tema_admin()`), `page_header`, `kpi_grid`, `badge`, `secao`, `empty_state`, `alerta` e a camada de compatibilidade de `st.container(border=True)` para qualquer versão do Streamlit.
- `assets/ds_base.css`, `ds_loja.css`, `ds_admin.css` — estilos (tokens, componentes, animações; respeita `prefers-reduced-motion`).
- `assets/motion.js` — count-up, ripple, paleta de comandos (Ctrl/⌘+K ou `/`) e barra de atalhos no celular.
- Páginas do painel: chamam `configurar_pagina()` (aplica o tema admin). Vitrine/checkout/páginas públicas: `tema_loja()`.
