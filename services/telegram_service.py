import streamlit as st
import requests

def enviar_notificacao_telegram(mensagem):
    try:
        # Busca a chave EXATAMENTE como está no seu cofre
        bot_token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        
        # Validação: Se não tiver chave, grita na tela
        if not bot_token or not chat_id:
            st.error("⚠️ ERRO: TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não encontrados no st.secrets.")
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Monta o pacote de envio com parse_mode HTML (para os <b> funcionarem)
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        # Dispara a mensagem
        resposta = requests.post(url, json=payload, timeout=10)
        
        # Se o Telegram recusar, mostra a mensagem exata na tela!
        if resposta.status_code != 200:
            st.error(f"🤖 **O Telegram Recusou!** Motivo exato:\n\n`{resposta.text}`")
            return False
            
        return True
        
    except Exception as e:
        st.error(f"⚠️ ERRO CRÍTICO NO SERVIÇO DO TELEGRAM: {e}")
        return False
