import io
import re
import pandas as pd
import streamlit as st
from unidecode import unidecode


st.set_page_config(
    page_title="Dashboard ERP - Ofensores",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard ERP - Ofensores e Produtividade")
st.caption("Envie o CSV unificado do ERP. O dashboard classifica tudo automaticamente.")


def ler_csv(arquivo):
    tentativas = [
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "latin1"},
        {"sep": "\t", "encoding": "utf-8-sig"},
        {"sep": "\t", "encoding": "latin1"},
    ]

    melhor_df = None

    for config in tentativas:
        try:
            arquivo.seek(0)
            df_temp = pd.read_csv(
                arquivo,
                sep=config["sep"],
                encoding=config["encoding"],
                dtype=str,
                low_memory=False,
                on_bad_lines="skip"
            )

            if melhor_df is None or len(df_temp.columns) > len(melhor_df.columns):
                melhor_df = df_temp

            if "descricao" in df_temp.columns and len(df_temp.columns) > 20:
                return df_temp

        except Exception:
            pass

    if melhor_df is not None:
        return melhor_df

    raise ValueError("Não foi possível ler o CSV.")


def limpar_texto(texto):
    if pd.isna(texto):
        return ""

    texto = str(texto).lower()
    texto = unidecode(texto)
    texto = re.sub(r"http\S+", " ", texto)
    texto = re.sub(r"www\S+", " ", texto)
    texto = re.sub(r"\b\d{1,2}h\d{0,2}\b", " ", texto)
    texto = re.sub(r"\b\d{1,2}:\d{2}\b", " ", texto)
    texto = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", " ", texto)
    texto = re.sub(r"[^a-z0-9\s\-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def classificar_ofensor(descricao):
    texto = limpar_texto(descricao)

    regras = [
        ("Nobreak", ["nobreak", "no-break", "ups", "nhs", "bateria"]),
        ("Link / Internet", ["sem internet", "internet", "link", "wan", "fibra", "operadora", "circuito", "indisponivel"]),
        ("Firewall", ["firewall", "er605", "er7206", "er7212", "fortinet", "palo alto", "vpn", "nat"]),
        ("Switch", ["switch", "sg2210", "sg3428", "sg2016", "es210", "porta poe", "poe"]),
        ("Access Point / Wi-Fi", ["access point", "wifi", "wi-fi", "eap", "ap offline", "ssid", "wireless"]),
        ("Controladora Omada", ["oc200", "omada", "controladora", "controller"]),
        ("Energia", ["energia", "sem energia", "queda de energia", "tomada", "disjuntor", "eletrica"]),
        ("Cabeamento", ["cabeamento", "cabo rompido", "cabo de rede", "rj45", "conector", "patch cord"]),
        ("Configuração", ["vlan", "dhcp", "dns", "ip", "rota", "gateway", "configuracao", "senha", "portal"]),
        ("Hardware / Equipamento", ["queimado", "queimada", "defeito", "travado", "travada", "nao liga", "fonte", "reiniciando"]),
    ]

    for categoria, palavras in regras:
        for palavra in palavras:
            if palavra in texto:
                return categoria

    return "Outros / Não classificado"


def classificar_resultado(row):
    campos = [
        "status_chamado",
        "status_tecnico",
        "ocasiao_fechamento",
        "motivo_improdutivo",
        "justificativa_ocasiao_fechamento",
        "descricao_fechamento"
    ]

    texto = " ".join(str(row.get(c, "")) for c in campos)
    texto = limpar_texto(texto)

    if any(p in texto for p in ["cancelado", "cancelada", "cancelamento"]):
        return "Cancelado"

    if any(p in texto for p in ["no show", "noshow", "nao compareceu", "tecnico nao foi", "tecnico nao compareceu"]):
        return "No-show técnico"

    if any(p in texto for p in ["improdutivo", "improdutiva", "improd"]):
        return "Improdutivo"

    if any(p in texto for p in ["produtivo", "produtiva", "concluido", "finalizado", "resolvido"]):
        return "Produtivo"

    if any(p in texto for p in ["aberto", "andamento", "pendente", "agendado", "aguardando"]):
        return "Aberto / Em andamento"

    return "Não identificado"


def preparar_data(df):
    colunas_data = [
        "data_hora_solicitacao",
        "data_registro",
        "data_hora_inicio_atendimento",
        "data_hora_fim_atendimento"
    ]

    for coluna in colunas_data:
        if coluna in df.columns:
            df["data_base"] = pd.to_datetime(df[coluna], errors="coerce", dayfirst=True)
            df["mes"] = df["data_base"].dt.strftime("%Y-%m")
            df["mes"] = df["mes"].fillna("Sem data")
            return df, coluna

    df["mes"] = "Sem data"
    return df, None


arquivo = st.file_uploader("📂 Envie o CSV unificado do ERP", type=["csv"])

if not arquivo:
    st.warning("Envie o CSV unificado para gerar o dashboard.")
    st.stop()

try:
    df_original = ler_csv(arquivo)
except Exception as e:
    st.error(f"Erro ao ler CSV: {e}")
    st.stop()

st.info(f"Linhas lidas do CSV: **{len(df_original):,}** | Colunas: **{len(df_original.columns)}**".replace(",", "."))

if "descricao" not in df_original.columns:
    st.error("A coluna `descricao` não foi encontrada no CSV.")
    st.write("Colunas encontradas:")
    st.write(df_original.columns.tolist())
    st.stop()

df_original, coluna_data_usada = preparar_data(df_original)

df_original["ofensor"] = df_original["descricao"].apply(classificar_ofensor)
df_original["resultado_atendimento"] = df_original.apply(classificar_resultado, axis=1)

df = df_original.copy()

st.sidebar.header("🔎 Filtros")

meses = sorted(df["mes"].dropna().unique())
filtro_mes = st.sidebar.multiselect("Mês", meses)

if filtro_mes:
    df = df[df["mes"].isin(filtro_mes)]

if "cliente" in df.columns:
    clientes = sorted(df["cliente"].dropna().unique())
    filtro_cliente = st.sidebar.multiselect("Cliente", clientes)
    if filtro_cliente:
        df = df[df["cliente"].isin(filtro_cliente)]

if "estado_cliente" in df.columns:
    estados = sorted(df["estado_cliente"].dropna().unique())
    filtro_estado = st.sidebar.multiselect("Estado", estados)
    if filtro_estado:
        df = df[df["estado_cliente"].isin(filtro_estado)]

resultados = sorted(df["resultado_atendimento"].dropna().unique())
filtro_resultado = st.sidebar.multiselect("Resultado", resultados)

if filtro_resultado:
    df = df[df["resultado_atendimento"].isin(filtro_resultado)]

st.info(f"Linhas após filtros: **{len(df):,}**".replace(",", "."))

total = len(df)
produtivos = (df["resultado_atendimento"] == "Produtivo").sum()
improdutivos = (df["resultado_atendimento"] == "Improdutivo").sum()
cancelados = (df["resultado_atendimento"] == "Cancelado").sum()
noshow = (df["resultado_atendimento"] == "No-show técnico").sum()

base_produtividade = produtivos + improdutivos
taxa_produtividade = (produtivos / base_produtividade * 100) if base_produtividade else 0

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("📞 Total", f"{total:,}".replace(",", "."))
col2.metric("✅ Produtivos", f"{produtivos:,}".replace(",", "."))
col3.metric("❌ Improdutivos", f"{improdutivos:,}".replace(",", "."))
col4.metric("🚫 Cancelados", f"{cancelados:,}".replace(",", "."))
col5.metric("👷 No-show", f"{noshow:,}".replace(",", "."))

st.metric("📈 Taxa de produtividade", f"{taxa_produtividade:.2f}%")

st.divider()

col_a, col_b = st.columns([2, 1])

with col_a:
    st.subheader("🚨 Top 10 Ofensores")

    top_ofensores = (
        df["ofensor"]
        .fillna("Outros / Não classificado")
        .value_counts()
        .reset_index()
        .head(10)
    )

    top_ofensores.columns = ["ofensor", "quantidade"]

    st.bar_chart(top_ofensores.set_index("ofensor")["quantidade"])
    st.dataframe(top_ofensores, use_container_width=True, hide_index=True)

with col_b:
    st.subheader("✅ Resultado")

    resultado_qtd = (
        df["resultado_atendimento"]
        .fillna("Não identificado")
        .value_counts()
        .reset_index()
    )

    resultado_qtd.columns = ["resultado", "quantidade"]

    st.bar_chart(resultado_qtd.set_index("resultado")["quantidade"])
    st.dataframe(resultado_qtd, use_container_width=True, hide_index=True)

st.divider()

col_c, col_d = st.columns(2)

with col_c:
    st.subheader("📅 Chamados por mês")

    chamados_mes = (
        df.groupby("mes")
        .size()
        .reset_index(name="quantidade")
        .sort_values("mes")
    )

    st.bar_chart(chamados_mes.set_index("mes")["quantidade"])
    st.dataframe(chamados_mes, use_container_width=True, hide_index=True)

with col_d:
    st.subheader("🚨 Ofensor x Resultado")

    tabela = pd.crosstab(
        df["ofensor"],
        df["resultado_atendimento"]
    ).reset_index()

    st.dataframe(tabela, use_container_width=True, hide_index=True)

st.divider()

st.subheader("🔎 Detalhamento dos chamados")

colunas_detalhe = [
    c for c in [
        "id",
        "num_chamado",
        "mes",
        "cliente",
        "estado_cliente",
        "status_chamado",
        "status_tecnico",
        "ofensor",
        "resultado_atendimento",
        "descricao",
        "descricao_fechamento"
    ]
    if c in df.columns
]

st.dataframe(df[colunas_detalhe], use_container_width=True)

st.divider()

csv_buffer = io.StringIO()
df.to_csv(csv_buffer, index=False, sep=";", encoding="utf-8-sig")

st.download_button(
    "📥 Baixar base analisada CSV",
    data=csv_buffer.getvalue(),
    file_name="dashboard_erp_analisado.csv",
    mime="text/csv"
)

excel_buffer = io.BytesIO()

with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Base Analisada")
    top_ofensores.to_excel(writer, index=False, sheet_name="Top Ofensores")
    resultado_qtd.to_excel(writer, index=False, sheet_name="Resultado")
    chamados_mes.to_excel(writer, index=False, sheet_name="Chamados Mes")

st.download_button(
    "📥 Baixar Excel executivo",
    data=excel_buffer.getvalue(),
    file_name="dashboard_erp_executivo.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
