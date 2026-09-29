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
**Etapa 3: criar o app no Streamlit Cloud**
1. Acesse share.streamlit.io e entre com sua conta do GitHub.
2. Toque em "New app" (ou "Create app").
3. Escolha o repositório `painel-ofertas-ml`, branch `main`, e no campo do arquivo principal digite `app.py`.
4. Toque em "Deploy". Vai aparecer uma tela de carregamento.
5. Quando abrir (mesmo com erro de Secrets faltando, é normal nesse momento), copie a URL que aparece no topo do navegador — algo como `https://painel-ofertas-ml-xxxx.streamlit.app`.

Depois disso, me avise que eu te levo para a Etapa 4: cadastrar essa URL no Mercado Livre e preencher os Secrets. Quer que eu já reenvie o texto do `app.py` aqui em bloco de código para colar direto, em vez de baixar o arquivo?
