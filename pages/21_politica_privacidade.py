import streamlit as st

st.set_page_config(
    page_title="Política de Privacidade | Doce Cesta Brasília",
    page_icon="🔒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

from utils.ui import tema_loja

tema_loja()
st.markdown(
    """<style>
    html body .stApp .block-container { max-width: 820px !important; }
    html body .stApp [data-testid="stMarkdownContainer"] h1 { font-size: clamp(26px, 4vw, 38px) !important; letter-spacing: -.04em !important; margin-bottom: 4px !important; }
    html body .stApp [data-testid="stMarkdownContainer"] h2 { font-size: 21px !important; margin-top: 28px !important; padding-left: 14px; border-left: 4px solid var(--caramelo); }
    html body .stApp [data-testid="stMarkdownContainer"] li, html body .stApp [data-testid="stMarkdownContainer"] p { line-height: 1.7; color: var(--ink-2); }
    </style>""",
    unsafe_allow_html=True,
)
st.page_link("app.py", label="Voltar para a loja", icon="🏠")

st.markdown("""
# POLÍTICA DE PRIVACIDADE – DOCE CESTA BRASÍLIA

**Última atualização:** 25/08/2026

A **Doce Cesta Brasília** está comprometida com a proteção da privacidade e dos dados pessoais de seus clientes e visitantes. Esta Política descreve como coletamos, usamos, armazenamos e compartilhamos informações pessoais em conformidade com a **Lei Geral de Proteção de Dados (LGPD – Lei nº 13.709/2018)** e demais legislações aplicáveis.

Ao utilizar nosso site e serviços, você declara ter lido e compreendido esta Política, concordando com o tratamento de seus dados conforme aqui descrito.

---

## 1. Dados Pessoais Coletados

Coletamos apenas os dados estritamente necessários para a execução do contrato de compra e entrega de produtos, bem como para cumprimento de obrigações legais e regulatórias.

**Dados fornecidos por você:**
- **Dados do comprador:** nome completo, e-mail, telefone/WhatsApp, CPF.
- **Dados do destinatário:** nome, telefone (opcional).
- **Dados de entrega:** CEP, cidade, bairro, rua, número, complemento.
- **Informações do pedido:** ocasião (opcional), mensagem de cartão (opcional), solicitações especiais (opcional).
- **Dados de pagamento (forma de pagamento):** apenas a modalidade escolhida (Pix ou cartão), sem coleta de dados bancários ou de cartão nesta plataforma.
- **Fotografias (opcional):** caso você opte pelo adicional “Polaroid”, poderá enviar imagens para personalização do produto. Essas imagens podem conter dados pessoais sensíveis (como imagem de pessoas) e serão tratadas com seu consentimento explícito.

**Dados coletados automaticamente:**
- Informações de navegação (cookies, endereço IP, tipo de navegador) para melhoria da experiência e segurança, conforme nossa Política de Cookies.

## 2. Finalidades do Tratamento

Utilizamos seus dados pessoais para as seguintes finalidades:

| Finalidade | Base Legal (LGPD) |
|------------|-------------------|
| Processamento e entrega do pedido | Execução de contrato (art. 7º, V) |
| Emissão de nota fiscal / obrigações fiscais | Cumprimento de obrigação legal (art. 7º, II) |
| Comunicação sobre o andamento do pedido | Execução de contrato |
| Envio de confirmação e recibo por e-mail | Execução de contrato |
| Personalização de produtos (fotos) | Consentimento explícito (art. 7º, I) |
| Prevenção a fraudes e segurança | Legítimo interesse (art. 7º, IX) |

**Não utilizamos seus dados para fins de marketing sem seu consentimento prévio e específico.**

## 3. Compartilhamento de Dados

Seus dados pessoais podem ser compartilhados com terceiros apenas na medida do necessário para a prestação dos serviços, conforme abaixo:

| Terceiro | Finalidade | Dados Compartilhados |
|----------|------------|----------------------|
| **Supabase** (provedor de banco de dados) | Armazenamento seguro dos pedidos | Todos os dados do formulário |
| **Serviço de e-mail transacional** (ex.: SendGrid) | Envio de confirmação e recibo | Nome, e-mail, resumo do pedido |
| **Telegram** (notificações internas) | Alertar a equipe sobre novos pedidos | Nome do cliente, valor, ID do pedido |
| **ViaCEP** (API pública) | Preenchimento automático de endereço a partir do CEP | Somente o CEP digitado |

Esses fornecedores estão obrigados a adotar medidas de segurança compatíveis com a LGPD e não podem utilizar seus dados para finalidades próprias.

## 4. Transferência Internacional de Dados

Alguns dos serviços acima podem estar hospedados fora do Brasil (ex.: Supabase, provedor de e-mail). Nesses casos, garantimos que a transferência internacional ocorra em conformidade com a LGPD, mediante cláusulas contratuais adequadas ou outros mecanismos legais.

## 5. Armazenamento e Retenção

Os dados pessoais serão armazenados pelo período necessário para cumprir as finalidades descritas nesta Política, respeitando prazos legais (ex.: guarda de documentos fiscais por 5 anos). Após esse período, os dados serão eliminados ou anonimizados de forma segura.

As fotografias enviadas para personalização serão mantidas apenas até a conclusão do pedido e, em seguida, excluídas definitivamente, salvo se houver obrigação legal de retenção.

## 6. Direitos do Titular

Nos termos da LGPD, você tem os seguintes direitos:

- **Confirmação e acesso** aos dados tratados;
- **Correção** de dados incompletos, inexatos ou desatualizados;
- **Anonimização, bloqueio ou eliminação** de dados desnecessários ou tratados em desconformidade;
- **Portabilidade** dos dados a outro fornecedor;
- **Revogação do consentimento**, quando aplicável;
- **Informação** sobre com quem compartilhamos seus dados.

Para exercer qualquer direito, entre em contato pelo e-mail: **docecestabrasilia@gmail.com** ou WhatsApp: **61 99975-9079**. Responderemos em até 15 dias.

## 7. Segurança da Informação

Adotamos medidas técnicas e organizacionais para proteger seus dados contra acessos não autorizados, perda, alteração ou destruição, incluindo:

- Criptografia em trânsito (HTTPS);
- Controle de acesso restrito ao banco de dados;
- Monitoramento de atividades suspeitas;
- Treinamento contínuo da equipe sobre proteção de dados.

Apesar dos esforços, nenhum sistema é 100% seguro. Em caso de incidente de segurança que possa acarretar risco relevante, comunicaremos você e a Autoridade Nacional de Proteção de Dados (ANPD), conforme exigido pela lei.

## 8. Cookies e Tecnologias Semelhantes

Utilizamos cookies estritamente necessários para o funcionamento do site. Não utilizamos cookies de rastreamento ou publicidade sem seu consentimento.

## 9. Alterações desta Política

Esta Política pode ser atualizada periodicamente. A versão mais recente estará sempre disponível em nosso site, com a data de revisão indicada no topo.

## 10. Contato

Em caso de dúvidas sobre esta Política ou sobre o tratamento de seus dados, fale conosco:

- **E-mail:** docecestabrasilia@gmail.com
- **WhatsApp:** +55 61 99975-9079
""")

st.divider()
st.markdown("**Doce Cesta Brasília** – Comprometida com a sua privacidade.")
