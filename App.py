import os
import re
import urllib.parse
from datetime import datetime, timedelta

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Ofertas ML - Afiliados", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #EBEBEB; }
h1 { color: #333333 !important; }
[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E0E0; }
[data-testid="stSidebar"] * { color: #1A1A1A !important; }
[data-testid="stSidebar"] h2 { color: #1A1A1A !important; font-weight: 700; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #1A1A1A !important; }
[data-testid="stSidebar"] textarea, [data-testid="stSidebar"] input {
    background-color: #F5F5F5 !important;
    color: #1A1A1A !important;
    border: 1px solid #B0B0B0 !important;
}
[data-testid="stSidebar"] textarea::placeholder { color: #757575 !important; opacity: 1; }
[data-testid="stSidebar"] [data-testid="stAlert"] p { color: #1A1A1A !important; }
[data-testid="stSidebar"] .stButton>button,
[data-testid="stSidebar"] .stLinkButton>a,
[data-testid="stSidebar"] .stFormSubmitButton>button { color: #FFFFFF !important; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    padding: 4px;
}
.stButton>button, .stLinkButton>a, .stFormSubmitButton>button {
    background-color: #3483FA !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
.stButton>button:hover, .stLinkButton>a:hover, .stFormSubmitButton>button:hover {
    background-color: #2968C8 !important;
}
.faixa-ml {
    background-color: #FFE600;
    padding: 10px 16px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-weight: 600;
    color: #333333;
}
.preco-atual { color: #333333; font-size: 1.4rem; font-weight: 700; }
.preco-original { color: #999999; text-decoration: line-through; font-size: 0.95rem; }
.badge-desconto {
    background-color: #00A650; color: #FFFFFF; font-weight: 700;
    padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 6px;
}
.nota-produto { color: #666666; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Configuração / Secrets
# ----------------------------------------------------------------------------
def get_secret(name, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)

CLIENT_ID = get_secret("MERCADO_LIVRE_CLIENT_ID")
CLIENT_SECRET = get_secret("MERCADO_LIVRE_CLIENT_SECRET")
AFFILIATE_TAG = get_secret("MERCADO_LIVRE_AFFILIATE_TAG", "")
REDIRECT_URI = get_secret("MERCADO_LIVRE_REDIRECT_URI", "http://localhost:8501")
WHATSAPP_CHANNEL_URL = get_secret("WHATSAPP_CHANNEL_URL", "")

ML_API = "https://api.mercadolibre.com"
NOTA_MINIMA = 4.5


# ----------------------------------------------------------------------------
# OAuth Mercado Livre (necessário para /search e /reviews autenticados)
# ----------------------------------------------------------------------------
def montar_url_autorizacao():
    params = {"response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI}
    return f"https://auth.mercadolivre.com.br/authorization?{urllib.parse.urlencode(params)}"


def trocar_code_por_token(code):
    resp = requests.post(
        f"{ML_API}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def renovar_token(refresh_token):
    resp = requests.post(
        f"{ML_API}/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def processar_login():
    if "ml_token" not in st.session_state:
        st.session_state.ml_token = None

    code = st.query_params.get("code")
    if code:
        if not st.session_state.ml_token:
            try:
                dados = trocar_code_por_token(code)
                st.session_state.ml_token = {
                    "access_token": dados["access_token"],
                    "refresh_token": dados.get("refresh_token"),
                    "expira_em": datetime.now() + timedelta(seconds=dados.get("expires_in", 21600) - 60),
                }
            except Exception as e:
                st.sidebar.error(f"Falha ao conectar com o Mercado Livre: {e}")
        st.query_params.clear()


def obter_token_valido():
    token = st.session_state.get("ml_token")
    if not token:
        return None
    if datetime.now() >= token["expira_em"] and token.get("refresh_token"):
        try:
            dados = renovar_token(token["refresh_token"])
            token = {
                "access_token": dados["access_token"],
                "refresh_token": dados.get("refresh_token", token["refresh_token"]),
                "expira_em": datetime.now() + timedelta(seconds=dados.get("expires_in", 21600) - 60),
            }
            st.session_state.ml_token = token
        except Exception:
            st.session_state.ml_token = None
            return None
    return token["access_token"]

# ----------------------------------------------------------------------------
# Categorias (resolução dinâmica com fallback)
# ----------------------------------------------------------------------------
def extrair_ids(texto):
    """Extrai IDs de item (ex.: MLB1234567890) de uma lista de links colados."""
    brutos = re.findall(r"MLB-?\d+", texto or "", flags=re.IGNORECASE)
    vistos, ids = set(), []
    for bruto in brutos:
        item_id = bruto.upper().replace("-", "")
        if item_id not in vistos:
            vistos.add(item_id)
            ids.append(item_id)
    return ids


def _detalhe_erro(resp):
    try:
        corpo = resp.json()
        return corpo.get("message") or corpo.get("error") or str(corpo)
    except Exception:
        return resp.text[:200]


def _buscar_item_unico(item_id, token):
    """Busca um item pelo endpoint /items/{id}. Tenta com token; se a
    Mercado Livre recusar, tenta de novo sem cabeçalho de autenticação
    (dado público de item às vezes não exige login)."""
    tentativas = []
    if token:
        tentativas.append({"Authorization": f"Bearer {token}"})
    tentativas.append({})  # sem token, como segunda tentativa

    ultimo_erro = None
    for headers in tentativas:
        resp = requests.get(f"{ML_API}/items/{item_id}", headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json(), None
        if resp.status_code in (401, 403):
            ultimo_erro = f"{resp.status_code}: {_detalhe_erro(resp)}"
            continue
        resp.raise_for_status()
    return None, ultimo_erro


@st.cache_data(ttl=300, show_spinner=False)
def buscar_itens(ids_lote, token):
    produtos = []
    erros = []
    for item_id in ids_lote:
        corpo, erro = _buscar_item_unico(item_id, token)
        if corpo is None:
            erros.append(f"{item_id}: {erro}")
            continue
        produtos.append({
            "id": corpo.get("id"),
            "title": corpo.get("title"),
            "price": corpo.get("price"),
            "original_price": corpo.get("original_price"),
            "permalink": corpo.get("permalink"),
            "thumbnail": (corpo.get("thumbnail") or "").replace("http://", "https://"),
        })
    if erros and not produtos:
        raise PermissionError(" | ".join(erros))
    return produtos, erros


@st.cache_data(ttl=1800, show_spinner=False)
def buscar_avaliacao(item_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{ML_API}/reviews/item/{item_id}", headers=headers, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.json().get("rating_average")

# ----------------------------------------------------------------------------
# Links de afiliado e mensagens
# ----------------------------------------------------------------------------
def formatar_preco(valor):
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def montar_link_afiliado(permalink, tag):
    if not tag:
        return permalink
    separador = "&" if "?" in permalink else "?"
    if tag.startswith("matt:"):
        try:
            _, usuario, ferramenta = tag.split(":", 2)
            return f"{permalink}{separador}matt_word={usuario}&matt_tool={ferramenta}"
        except ValueError:
            pass
    return f"{permalink}{separador}tag={tag}"


def montar_mensagem(produto, link_afiliado, nota):
    texto = f"🔥 *Oferta imperdível!* 🔥\n\n{produto['title']}\n\n"
    original = produto.get("original_price")
    if original and original > produto["price"]:
        desconto = round((1 - produto["price"] / original) * 100)
        texto += f"De ~{formatar_preco(original)}~ por *{formatar_preco(produto['price'])}* ({desconto}% OFF)\n"
    else:
        texto += f"Por *{formatar_preco(produto['price'])}*\n"
    texto += f"⭐ {nota:.1f}/5.0\n\n👉 {link_afiliado}"
    return texto


def montar_link_whatsapp(mensagem):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(mensagem)}"

# ----------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------
processar_login()
token_atual = obter_token_valido()

st.markdown('<div class="faixa-ml">🛒 Painel de Ofertas de Afiliado — Mercado Livre</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configurações")

    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("Configure MERCADO_LIVRE_CLIENT_ID e MERCADO_LIVRE_CLIENT_SECRET nos Secrets.")
    elif token_atual:
        st.success("✅ Conectado à sua conta Mercado Livre")
        if st.button("Desconectar"):
            st.session_state.ml_token = None
            st.rerun()
    else:
        st.warning("🔒 Conecte sua conta para buscar ofertas.")
        st.link_button("Conectar com Mercado Livre", montar_url_autorizacao())

    if WHATSAPP_CHANNEL_URL:
        st.link_button("📢 Abrir meu canal", WHATSAPP_CHANNEL_URL)

    if "links_salvos" not in st.session_state:
        st.session_state.links_salvos = ""

    with st.form("form_busca"):
        texto_links = st.text_area(
            "Cole os links dos produtos (pode colar vários de uma vez, juntos ou um por linha)",
            value=st.session_state.links_salvos,
            height=160,
            placeholder="Cole aqui um ou vários links do Mercado Livre, ex.: "
                        "https://produto.mercadolivre.com.br/MLB-1234567890-...",
        )
        enviado = st.form_submit_button("🔎 Gerar ofertas", use_container_width=True)

    if enviado:
        st.session_state.links_salvos = texto_links
        buscar_itens.clear()
        buscar_avaliacao.clear()

    if st.button("🔄 Atualizar avaliações", use_container_width=True):
        buscar_itens.clear()
        buscar_avaliacao.clear()
        st.rerun()

if not token_atual:
    st.info("Conecte sua conta do Mercado Livre na barra lateral para começar a buscar as ofertas.")
    st.stop()

ids_colados = extrair_ids(st.session_state.links_salvos)
if not ids_colados:
    st.info("Cole ao menos um link de produto do Mercado Livre na barra lateral (ex.: https://produto.mercadolivre.com.br/MLB-...).")
    st.stop()

produtos_aprovados = []
produtos_reprovados = 0
with st.spinner("Buscando produtos e avaliações..."):
    for inicio in range(0, len(ids_colados), 20):
        lote = tuple(ids_colados[inicio:inicio + 20])
        try:
            itens, erros_lote = buscar_itens(lote, token_atual)
        except PermissionError as e:
            st.error(f"A Mercado Livre recusou a consulta: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Erro ao buscar os produtos: {e}")
            itens, erros_lote = [], []

        for erro in erros_lote:
            st.caption(f"⚠️ Não foi possível validar: {erro}")

        for produto in itens:
            nota = buscar_avaliacao(produto["id"], token_atual)
            if nota is not None and nota >= NOTA_MINIMA:
                produtos_aprovados.append((produto, nota))
            else:
                produtos_reprovados += 1

st.caption(f"{len(produtos_aprovados)} produto(s) aprovado(s) · {produtos_reprovados} abaixo de {NOTA_MINIMA} ou sem nota")

if not produtos_aprovados:
    st.warning("Nenhum produto colado tem avaliação ≥ 4.5 (ou os links não foram reconhecidos).")
    st.stop()

colunas = st.columns(2)
for indice, (produto, nota) in enumerate(produtos_aprovados):
    link_afiliado = montar_link_afiliado(produto["permalink"], AFFILIATE_TAG)
    imagem = produto.get("thumbnail", "").replace("http://", "https://")

    with colunas[indice % 2]:
        with st.container(border=True):
            if imagem:
                st.image(imagem, use_container_width=True)
            else:
                st.caption("Sem imagem disponível")
            st.markdown(f"**{produto['title']}**")

            if produto.get("original_price") and produto["original_price"] > produto["price"]:
                desconto = round((1 - produto["price"] / produto["original_price"]) * 100)
                st.markdown(
                    f'<span class="preco-original">{formatar_preco(produto["original_price"])}</span> '
                    f'<span class="preco-atual">{formatar_preco(produto["price"])}</span>'
                    f'<span class="badge-desconto">{desconto}% OFF</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f'<span class="preco-atual">{formatar_preco(produto["price"])}</span>', unsafe_allow_html=True)

            st.markdown(f'<span class="nota-produto">⭐ {nota:.1f} / 5.0</span>', unsafe_allow_html=True)
            mensagem = montar_mensagem(produto, link_afiliado, nota)
            st.code(mensagem, language=None)
            st.link_button("📲 Compartilhar no WhatsApp", montar_link_whatsapp(mensagem), use_container_width=True)
            if imagem:
                st.markdown(f"[🖼️ Abrir imagem para salvar]({imagem})")
