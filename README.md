# Painel de Ofertas de Afiliado — Mercado Livre

Protótipo em Streamlit que busca ofertas com nota ≥ 4.5 em Eletrônicos,
Informática, Periféricos e Consoles, com link de afiliado e mensagem
pronta para postar no WhatsApp.

## Variáveis no Streamlit Secrets
```toml
MERCADO_LIVRE_CLIENT_ID = "seu_client_id"
MERCADO_LIVRE_CLIENT_SECRET = "seu_client_secret"
MERCADO_LIVRE_REDIRECT_URI = "https://seuapp.streamlit.app"
MERCADO_LIVRE_AFFILIATE_TAG = "matt:seu_usuario:123456"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/SEU_CODIGO"
