import os
import urllib.parse

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
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #1A1A1A !important; font-weight: 700; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #1A1A1A !important; }
[data-testid="stSidebar"] textarea, [data-testid="stSidebar"] input {
    background-color: #F5F5F5 !important;
    color: #1A1A1A !important;
    border: 1px solid #B0B0B0 !important;
}
[data-testid="stSidebar"] textarea::placeholder,
[data-testid="stSidebar"] input::placeholder { color: #757575 !important; opacity: 1; }
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

WHATSAPP_CHANNEL_URL = get_secret("WHATSAPP_CHANNEL_URL", "")

# ----------------------------------------------------------------------------
# Formatação e mensagem
# ----------------------------------------------------------------------------
def formatar_preco(valor):
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def montar_mensagem(produto):
    texto = f"🔥 *Oferta imperdível!* 🔥\n\n{produto['titulo']}\n\n"
    original = produto.get("preco_original")
    preco = produto["preco"]
    if original and original > preco:
        desconto = round((1 - preco / original) * 100)
        texto += f"De ~{formatar_preco(original)}~ por *{formatar_preco(preco)}* ({desconto}% OFF)\n"
    else:
        texto += f"Por *{formatar_preco(preco)}*\n"
    if produto.get("nota"):
        texto += f"⭐ {produto['nota']:.1f}/5.0\n"
    texto += f"\n👉 {produto['link']}"
    return texto


def montar_link_whatsapp(mensagem):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(mensagem)}"

# ----------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------
if "produtos_manual" not in st.session_state:
    st.session_state.produtos_manual = []

st.markdown('<div class="faixa-ml">🛒 Painel de Ofertas de Afiliado — Mercado Livre</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configurações")

    if WHATSAPP_CHANNEL_URL:
        st.link_button("📢 Abrir meu canal", WHATSAPP_CHANNEL_URL, use_container_width=True)

    st.markdown("---")
    st.subheader("➕ Adicionar oferta")
    st.caption(
        "Gere o link no Portal do Afiliado do Mercado Livre "
        "(Central de Afiliados → Gerador de Links) e cole aqui junto com os dados do produto."
    )

    with st.form("form_adicionar", clear_on_submit=True):
        titulo = st.text_input("Título do produto")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            preco = st.number_input("Preço atual (R$)", min_value=0.0, step=0.01, format="%.2f")
        with col_p2:
            preco_original = st.number_input("Preço antes (R$) — opcional", min_value=0.0, step=0.01, format="%.2f")
        nota = st.slider("Avaliação (opcional)", 0.0, 5.0, 0.0, 0.1)
        link = st.text_input("Link de afiliado (gerado no Portal do Afiliado)")
        imagem = st.text_input("URL da imagem (opcional)")
        enviado = st.form_submit_button("➕ Adicionar oferta", use_container_width=True)

    if enviado:
        if not titulo or not preco or not link:
            st.error("Preencha pelo menos título, preço e link.")
        else:
            st.session_state.produtos_manual.append({
                "titulo": titulo,
                "preco": preco,
                "preco_original": preco_original or None,
                "nota": nota or None,
                "link": link,
                "imagem": imagem or None,
            })

    if st.session_state.produtos_manual:
        st.markdown("---")
        if st.button("🧹 Limpar todas as ofertas", use_container_width=True):
            st.session_state.produtos_manual = []
            st.rerun()

if not st.session_state.produtos_manual:
    st.info("Adicione sua primeira oferta pela barra lateral (título, preço e link de afiliado).")
    st.stop()

colunas = st.columns(2)
for indice, produto in enumerate(st.session_state.produtos_manual):
    with colunas[indice % 2]:
        with st.container(border=True):
            if produto.get("imagem"):
                st.image(produto["imagem"], use_container_width=True)
            else:
                st.caption("Sem imagem cadastrada")

            st.markdown(f"**{produto['titulo']}**")

            if produto.get("preco_original") and produto["preco_original"] > produto["preco"]:
                desconto = round((1 - produto["preco"] / produto["preco_original"]) * 100)
                st.markdown(
                    f'<span class="preco-original">{formatar_preco(produto["preco_original"])}</span> '
                    f'<span class="preco-atual">{formatar_preco(produto["preco"])}</span>'
                    f'<span class="badge-desconto">{desconto}% OFF</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f'<span class="preco-atual">{formatar_preco(produto["preco"])}</span>', unsafe_allow_html=True)

            if produto.get("nota"):
                st.markdown(f'<span class="nota-produto">⭐ {produto["nota"]:.1f} / 5.0</span>', unsafe_allow_html=True)

            mensagem = montar_mensagem(produto)
            st.code(mensagem, language=None)
            st.link_button("📲 Compartilhar no WhatsApp", montar_link_whatsapp(mensagem), use_container_width=True)

            if st.button("🗑️ Remover", key=f"remover_{indice}", use_container_width=True):
                st.session_state.produtos_manual.pop(indice)
                st.rerun()
    
