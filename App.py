import os
import re
import urllib.parse
from datetime import datetime, timedelta

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Ofertas ML - Afiliados", page_icon="🛒", layout="wide")

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
# OAuth Mercado Livre (necessário para /items e /reviews autenticados)
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
# Extração de IDs e busca de produtos/avaliações
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


@st.cache_data(ttl=300, show_spinner=False)
def buscar_itens(ids_lote, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{ML_API}/items", headers=headers, params={"ids": ",".join(ids_lote)}, timeout=15)
    if resp.status_code in (401, 403):
        raise PermissionError("Token inválido, expirado ou sem permissão.")
    resp.raise_for_status()
    produtos = []
    for entrada in resp.json():
        if entrada.get("code", 200) != 200:
            continue
        corpo = entrada.get("body", entrada)
        produtos.append({
            "id": corpo.get("id"),
            "title": corpo.get("title"),
            "price": corpo.get("price"),
            "original_price": corpo.get("original_price"),
            "permalink": corpo.get("permalink"),
            "thumbnail": (corpo.get("thumbnail") or "").replace("http://", "https://"),
        })
    return produtos


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

st.title("🛒 Painel de Ofertas de Afiliado — Mercado Livre")

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

    texto_links = st.text_area(
        "Cole aqui os links dos produtos (um por linha)",
        height=160,
        placeholder="https://produto.mercadolivre.com.br/MLB-1234567890-...",
    )

    if st.button("🔄 Atualizar avaliações"):
        buscar_itens.clear()
        buscar_avaliacao.clear()
        st.rerun()

if not token_atual:
    st.info("Conecte sua conta do Mercado Livre na barra lateral para começar a buscar as ofertas.")
    st.stop()

ids_colados = extrair_ids(texto_links)
if not ids_colados:
    st.info("Cole ao menos um link de produto do Mercado Livre na barra lateral (ex.: https://produto.mercadolivre.com.br/MLB-...).")
    st.stop()

produtos_aprovados = []
produtos_reprovados = 0
with st.spinner("Buscando produtos e avaliações..."):
    for inicio in range(0, len(ids_colados), 20):
        lote = tuple(ids_colados[inicio:inicio + 20])
        try:
            itens = buscar_itens(lote, token_atual)
        except PermissionError:
            st.error("Sessão expirada. Reconecte sua conta na barra lateral.")
            st.session_state.ml_token = None
            st.stop()
        except Exception as e:
            st.error(f"Erro ao buscar os produtos: {e}")
            itens = []

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
                    f"~~{formatar_preco(produto['original_price'])}~~ "
                    f"**{formatar_preco(produto['price'])}** 🔻{desconto}%"
                )
            else:
                st.markdown(f"**{formatar_preco(produto['price'])}**")

            st.markdown(f"⭐ {nota:.1f} / 5.0")
            mensagem = montar_mensagem(produto, link_afiliado, nota)
            st.code(mensagem, language=None)
            st.link_button("📲 Compartilhar no WhatsApp", montar_link_whatsapp(mensagem), use_container_width=True)
            if imagem:
                st.markdown(f"[🖼️ Abrir imagem para salvar]({imagem})")
