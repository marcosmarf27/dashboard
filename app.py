import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import requests
import locale

# Configuração da página
st.set_page_config(layout="wide", page_title="Dashboard Financeiro e Imobiliário", page_icon="🏠")

# Tentar configurar locale para formatação de moeda brasileira
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    use_locale = True
except locale.Error:
    use_locale = False
    st.warning("Não foi possível configurar o locale brasileiro. Usando formatação personalizada.")

# Função para formatar valores monetários
def format_currency(value):
    if use_locale:
        return locale.currency(value, grouping=True, symbol=None)
    else:
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Função para aplicar estilo CSS personalizado
def local_css(file_name):
    with open(file_name, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Aplicar estilo CSS personalizado
local_css("style.css")

@st.cache_data
def fetch_data(api_url):
    all_results = []
    cursor = 0

    while True:
        response = requests.get(f"{api_url}?cursor={cursor}")
        if response.status_code != 200:
            st.error(f"Falha ao buscar dados: {response.status_code}")
            return None

        data = response.json()
        results = data['response']['results']
        all_results.extend(results)

        remaining = data['response'].get('remaining', 0)
        if remaining == 0:
            break

        cursor += len(results)

    return pd.DataFrame(all_results)

def safe_parse_date(date_string):
    try:
        return pd.to_datetime(date_string, format='%Y-%m-%dT%H:%M:%S.%fZ', errors='raise')
    except:
        try:
            return pd.to_datetime(date_string, errors='raise')
        except:
            return pd.NaT

# URLs da API
caixa_url = "https://commitar.com.br/api/1.1/obj/I_caixa"
tipo_mov_url = "https://commitar.com.br/api/1.1/obj/I_tipo_mov"
imoveis_url = "https://commitar.com.br/api/1.1/obj/I_imoveis"
contratos_url = "https://commitar.com.br/api/1.1/obj/I_contratos"

# Buscar dados
with st.spinner('Carregando dados...'):
    df_caixa = fetch_data(caixa_url)
    df_tipo_mov = fetch_data(tipo_mov_url)
    df_imoveis = fetch_data(imoveis_url)
    df_contratos = fetch_data(contratos_url)

if all([df_caixa is not None, df_tipo_mov is not None, df_imoveis is not None, df_contratos is not None]):
    # Criar dicionários de mapeamento
    tipo_mov_dict = dict(zip(df_tipo_mov['_id'], df_tipo_mov['descrição']))
    imoveis_dict = dict(zip(df_imoveis['_id'], df_imoveis['descricao']))

    # Mapear descrições
    df_caixa['tipo_mov_desc'] = df_caixa['tipo_mov'].map(tipo_mov_dict)
    df_caixa['imovel_desc'] = df_caixa['imovel'].map(imoveis_dict)
    df_caixa['data_mov'] = df_caixa['data_mov'].apply(safe_parse_date)
    df_caixa['valor'] = pd.to_numeric(df_caixa['valor'], errors='coerce')

    # Remover linhas com datas inválidas
    df_caixa = df_caixa.dropna(subset=['data_mov'])

    # Título do Dashboard
    st.title("Dashboard Financeiro e Imobiliário")

    # Sidebar com filtros
    st.sidebar.header("Filtros")

    # Filtro de período
    periodo_options = ["Todos", "Ano Atual", "Mês Atual", "Últimos 3 meses", "Últimos 6 meses", "Personalizado"]
    periodo = st.sidebar.selectbox("Selecione período", periodo_options)

    if periodo == "Personalizado":
        start_date = st.sidebar.date_input("Data inicial", df_caixa['data_mov'].min())
        end_date = st.sidebar.date_input("Data final", df_caixa['data_mov'].max())
    elif periodo == "Ano Atual":
        start_date = datetime(datetime.now().year, 1, 1)
        end_date = datetime.now()
    elif periodo == "Mês Atual":
        start_date = datetime(datetime.now().year, datetime.now().month, 1)
        end_date = datetime.now()
    elif periodo == "Últimos 3 meses":
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
    elif periodo == "Últimos 6 meses":
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
    else:
        start_date = df_caixa['data_mov'].min()
        end_date = df_caixa['data_mov'].max()

    df_filtered = df_caixa[(df_caixa['data_mov'] >= pd.Timestamp(start_date)) & (df_caixa['data_mov'] <= pd.Timestamp(end_date))]

    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    entrada_total = df_filtered[df_filtered['categoria'] == 'entrada']['valor'].sum()
    saida_total = df_filtered[df_filtered['categoria'] == 'saida']['valor'].sum()
    saldo = entrada_total - saida_total
    contratos_ativos = len(df_contratos[df_contratos['ativo'] == True])

    col1.metric("Entrada", f"R$ {format_currency(entrada_total)}")
    col2.metric("Saída", f"R$ {format_currency(saida_total)}")
    col3.metric("Saldo", f"R$ {format_currency(saldo)}")
    col4.metric("Contratos ativos", contratos_ativos)

    # Última atualização
    st.markdown(f"**Última atualização:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Lista de Imóveis
    st.subheader("Lista de Imóveis")
    imoveis_summary = df_filtered.groupby(['imovel_desc', 'categoria'])['valor'].sum().unstack(fill_value=0).reset_index()

    # Ensure 'entrada' and 'saida' columns exist
    if 'entrada' not in imoveis_summary.columns:
        imoveis_summary['entrada'] = 0
    if 'saida' not in imoveis_summary.columns:
        imoveis_summary['saida'] = 0

    imoveis_summary = imoveis_summary[['imovel_desc', 'entrada', 'saida']]
    imoveis_summary.columns = ['Imóvel', 'Entrada', 'Saída']
    imoveis_summary['Saldo'] = imoveis_summary['Entrada'] - imoveis_summary['Saída']

    # Adicionar linha de total
    total_row = pd.DataFrame({
        'Imóvel': ['Total'],
        'Entrada': [imoveis_summary['Entrada'].sum()],
        'Saída': [imoveis_summary['Saída'].sum()],
        'Saldo': [imoveis_summary['Saldo'].sum()]
    })
    imoveis_summary = pd.concat([imoveis_summary, total_row], ignore_index=True)

    st.dataframe(
        imoveis_summary.style.format({
            'Entrada': lambda x: f"R$ {format_currency(x)}",
            'Saída': lambda x: f"R$ {format_currency(x)}",
            'Saldo': lambda x: f"R$ {format_currency(x)}"
        }).apply(lambda x: ['font-weight: bold' if x.name == len(imoveis_summary) - 1 else '' for _ in x], axis=1),
        height=400
    )

    # Maiores despesas
    st.subheader("Maiores despesas")
    maiores_despesas = df_filtered[df_filtered['categoria'] == 'saida'].groupby('tipo_mov_desc')['valor'].sum().sort_values(ascending=True).tail(10)
    fig_despesas = go.Figure(go.Bar(
        x=maiores_despesas.values,
        y=maiores_despesas.index,
        orientation='h',
        marker_color='#FF4136',
        text=[f"R$ {format_currency(x)}" for x in maiores_despesas.values],
        textposition='auto'
    ))
    fig_despesas.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_despesas, use_container_width=True)

    # Faturamento e despesas ao decorrer do tempo
    st.subheader("Faturamento e despesas ao decorrer do tempo")

    if periodo in ["Mês Atual", "Personalizado"] and (end_date - start_date).days <= 31:
        # Visualização diária
        df_time = df_filtered.groupby(['data_mov', 'categoria'])['valor'].sum().unstack(fill_value=0).reset_index()
        x_axis = df_time['data_mov'].dt.strftime('%d/%m/%Y')
    elif periodo in ["Ano Atual", "Últimos 3 meses", "Últimos 6 meses", "Personalizado"]:
        # Visualização mensal
        df_time = df_filtered.groupby([df_filtered['data_mov'].dt.to_period('M'), 'categoria'])['valor'].sum().unstack(fill_value=0).reset_index()
        df_time['data_mov'] = df_time['data_mov'].dt.to_timestamp()
        x_axis = df_time['data_mov'].dt.strftime('%m/%Y')
    else:
        # Visualização anual
        df_time = df_filtered.groupby([df_filtered['data_mov'].dt.year, 'categoria'])['valor'].sum().unstack(fill_value=0).reset_index()
        x_axis = df_time['data_mov'].astype(str)

    # Ensure 'entrada' and 'saida' columns exist in df_time
    if 'entrada' not in df_time.columns:
        df_time['entrada'] = 0
    if 'saida' not in df_time.columns:
        df_time['saida'] = 0

    fig_time = go.Figure()
    fig_time.add_trace(go.Bar(x=x_axis, y=df_time['entrada'], name='Entrada', marker_color='#0074D9',
                              text=[f"R$ {format_currency(x)}" for x in df_time['entrada']], textposition='auto'))
    fig_time.add_trace(go.Bar(x=x_axis, y=df_time['saida'], name='Saída', marker_color='#FF4136',
                              text=[f"R$ {format_currency(x)}" for x in df_time['saida']], textposition='auto'))
    fig_time.update_layout(barmode='group', height=400)
    st.plotly_chart(fig_time, use_container_width=True)

    # Botões adicionais
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Despesas Avulsas"):
            st.write("Funcionalidade de Despesas Avulsas a ser implementada")
    with col2:
        if st.button("Limpar Filtros"):
            st.experimental_rerun()

else:
    st.error("Não foi possível carregar todos os dados necessários. Por favor, verifique sua conexão e tente novamente.")