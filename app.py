import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(layout="wide", page_title="Dashboard Financeiro e Imobiliário")

# Função para formatar valores em reais
def format_currency(value):
    if pd.isna(value):
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Função para formatar datas
def format_date(date):
    return date.strftime("%d/%m/%Y")

# Função para criar um card
def create_card(title, value, color="#FFF"):
    st.markdown(
        f"""
        <div style="
            background-color: {color};
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        ">
            <h3 style="color: #333; margin-bottom: 0; font-size: 18px;">{title}</h3>
            <p style="color: #333; font-size: 24px; font-weight: bold; margin-top: 10px;">{value}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# Função para traduzir nomes de meses para português
def traduzir_mes(mes):
    meses = {
        'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril',
        'May': 'Maio', 'June': 'Junho', 'July': 'Julho', 'August': 'Agosto',
        'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
    }
    for en, pt in meses.items():
        if en in mes:
            return mes.replace(en, pt)
    return mes

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
clientes_url = "https://commitar.com.br/api/1.1/obj/l_clientes"

# Sidebar para filtros
st.sidebar.title("Filtros")

# Botão Limpar Filtros no topo da sidebar
if st.sidebar.button("Limpar Filtros"):
    st.rerun()

# Buscar dados
with st.spinner('Carregando dados...'):
    df_caixa = fetch_data(caixa_url)
    df_tipo_mov = fetch_data(tipo_mov_url)
    df_imoveis = fetch_data(imoveis_url)
    df_contratos = fetch_data(contratos_url)
    df_clientes = fetch_data(clientes_url)

if all([df_caixa is not None, df_tipo_mov is not None, df_imoveis is not None, df_contratos is not None, df_clientes is not None]):
    # Criar dicionários de mapeamento
    tipo_mov_dict = dict(zip(df_tipo_mov['_id'], df_tipo_mov['descrição']))
    imoveis_dict = dict(zip(df_imoveis['_id'], df_imoveis['descricao']))
    clientes_dict = dict(zip(df_clientes['_id'], df_clientes['nome']))

    # Mapear descrições
    df_caixa['tipo_mov_desc'] = df_caixa['tipo_mov'].map(tipo_mov_dict)
    df_caixa['imovel_desc'] = df_caixa['imovel'].map(imoveis_dict)
    df_caixa['data_mov'] = df_caixa['data_mov'].apply(safe_parse_date)
    df_caixa['valor'] = pd.to_numeric(df_caixa['valor'], errors='coerce')
    df_contratos['cliente_nome'] = df_contratos['cliente'].map(clientes_dict)

    # Remover linhas com datas inválidas
    df_caixa = df_caixa.dropna(subset=['data_mov'])

    # Filtros no sidebar
    periodo = st.sidebar.selectbox(
        "Selecione período",
        ["Todos", "Mês atual", "Último mês", "Últimos 3 meses", "Últimos 6 meses", "Último ano", "Personalizado"]
    )

    if periodo == "Personalizado":
        min_date = min(df_caixa['data_mov'].dt.date)
        max_date = datetime.now().date()
        start_date = st.sidebar.date_input("Data inicial", min_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
        end_date = st.sidebar.date_input("Data final", max_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    else:
        end_date = datetime.now().date()
        if periodo == "Mês atual":
            start_date = end_date.replace(day=1)
        elif periodo == "Último mês":
            start_date = end_date - timedelta(days=30)
        elif periodo == "Últimos 3 meses":
            start_date = end_date - timedelta(days=90)
        elif periodo == "Últimos 6 meses":
            start_date = end_date - timedelta(days=180)
        elif periodo == "Último ano":
            start_date = end_date - timedelta(days=365)
        else:  # "Todos"
            start_date = min(df_caixa['data_mov'].dt.date)

    df_caixa_filtered = df_caixa[(df_caixa['data_mov'].dt.date >= start_date) & (df_caixa['data_mov'].dt.date <= end_date)]

    # Título do Dashboard
    st.title("Dashboard Financeiro e Imobiliário")
    st.write(f"Dados de {format_date(start_date)} até {format_date(end_date)}")

    # Cálculos gerais
    entrada_total = df_caixa_filtered[df_caixa_filtered['categoria'] == 'entrada']['valor'].sum()
    saida_total = df_caixa_filtered[df_caixa_filtered['categoria'] == 'saida']['valor'].sum()
    saldo = entrada_total - saida_total
    contratos_ativos = len(df_contratos[df_contratos['ativo'] == True])

    # Exibir cards com resumo
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        create_card("Entrada", format_currency(entrada_total), "#4CAF50")  # Verde para entrada
    with col2:
        create_card("Saída", format_currency(saida_total), "#F44336")  # Vermelho para saída
    with col3:
        create_card("Saldo", format_currency(saldo), "#2196F3")  # Azul para saldo
    with col4:
        create_card("Contratos ativos", str(contratos_ativos), "#FFA726")  # Laranja para contratos

    # Lista de Imóveis
    st.subheader("Resumo por Imóvel")
    imoveis_summary = df_caixa_filtered.groupby(['imovel_desc', 'categoria'])['valor'].sum().unstack(fill_value=0).reset_index()

    # Ensure all necessary columns exist
    for col in ['entrada', 'saida']:
        if col not in imoveis_summary.columns:
            imoveis_summary[col] = 0

    imoveis_summary = imoveis_summary.rename(columns={'entrada': 'Entrada', 'saida': 'Saída'})
    imoveis_summary['Saldo'] = imoveis_summary['Entrada'] - imoveis_summary['Saída']
    imoveis_summary = imoveis_summary.rename(columns={'imovel_desc': 'Descrição'})

    for col in ['Entrada', 'Saída', 'Saldo']:
        imoveis_summary[col] = imoveis_summary[col].apply(format_currency)

    st.dataframe(imoveis_summary, use_container_width=True)

    # Maiores despesas
    st.subheader("Maiores despesas")
    maiores_despesas = df_caixa_filtered[df_caixa_filtered['categoria'] == 'saida'].groupby('tipo_mov_desc')['valor'].sum().sort_values(ascending=False).head(10)
    fig_despesas = px.bar(maiores_despesas, x=maiores_despesas.index, y=maiores_despesas.values, 
                          labels={'x': 'Tipo de Despesa', 'y': 'Valor Total'},
                          title="Top 10 Maiores Despesas")
    fig_despesas.update_traces(text=[format_currency(val) for val in maiores_despesas.values], textposition='outside')
    fig_despesas.update_layout(yaxis_title="Valor Total (R$)")
    st.plotly_chart(fig_despesas, use_container_width=True)

    # Faturamento e despesas ao decorrer dos dias
    st.subheader("Faturamento e Despesas Mensais")
    df_mensal = df_caixa_filtered.groupby([df_caixa_filtered['data_mov'].dt.to_period('M'), 'categoria'])['valor'].sum().unstack(fill_value=0)
    df_mensal.index = df_mensal.index.strftime('%B %Y').map(traduzir_mes)
    fig_mensal = go.Figure()
    fig_mensal.add_trace(go.Bar(x=df_mensal.index, y=df_mensal['entrada'], name='Entrada', marker_color='green'))
    fig_mensal.add_trace(go.Bar(x=df_mensal.index, y=df_mensal['saida'], name='Saída', marker_color='red'))
    fig_mensal.update_layout(
        barmode='group',
        title="Faturamento e Despesas Mensais",
        xaxis_title="Mês",
        yaxis_title="Valor (R$)",
        legend_title="Categoria",
        xaxis_tickangle=-45  # Inclina os rótulos para melhor legibilidade
    )
    fig_mensal.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside')
    st.plotly_chart(fig_mensal, use_container_width=True)

    # Informações sobre Contratos
    st.subheader("Contratos Ativos")

    if 'ativo' in df_contratos.columns and 'imovel' in df_contratos.columns:
        contratos_ativos = df_contratos[df_contratos['ativo'] == True]

        # Mesclar df_contratos com df_imoveis para obter valor_aluguel
        contratos_summary = pd.merge(contratos_ativos, df_imoveis[['_id', 'descricao', 'valor_aluguel']], 
                                     left_on='imovel', right_on='_id', how='left')

        # Selecionar e renomear as colunas relevantes
        columns_to_display = ['descricao', 'cliente_nome', 'valor_aluguel']
        new_column_names = {
            'descricao': 'Imóvel',
            'cliente_nome': 'Cliente',
            'valor_aluguel': 'Valor do Aluguel'
        }

        contratos_summary = contratos_summary[columns_to_display].rename(columns=new_column_names)
        contratos_summary['Valor do Aluguel'] = contratos_summary['Valor do Aluguel'].apply(format_currency)

        # Exibir o resumo dos contratos
        st.dataframe(contratos_summary, use_container_width=True)
    else:
        st.write("As colunas necessárias não estão presentes no DataFrame de contratos.")

    # Mapa de Imóveis
    st.subheader("Localização dos Imóveis")
    df_imoveis['lat'] = df_imoveis['localização'].apply(lambda x: x['lat'] if isinstance(x, dict) else None)
    df_imoveis['lon'] = df_imoveis['localização'].apply(lambda x: x['lng'] if isinstance(x, dict) else None)
    df_imoveis['valor_aluguel_formatado'] = df_imoveis['valor_aluguel'].apply(format_currency)

    fig_map = px.scatter_mapbox(df_imoveis, 
                                lat="lat", 
                                lon="lon", 
                                hover_name="descricao",
                                hover_data={"valor_aluguel_formatado": True, "lat": False, "lon": False},
                                zoom=10,
                                color="valor_aluguel",
                                size="valor_aluguel",
                                color_continuous_scale=px.colors.sequential.Viridis,
                                size_max=15,
                                title="Localização e Valor de Aluguel dos Imóveis")

    fig_map.update_layout(mapbox_style="open-street-map")
    fig_map.update_layout(height=600)
    st.plotly_chart(fig_map, use_container_width=True)

else:
    st.error("Não foi possível carregar todos os dados necessários. Por favor, verifique sua conexão e tente novamente.")

