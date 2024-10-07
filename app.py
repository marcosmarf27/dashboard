import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuração da página (deve ser a primeira chamada Streamlit)
st.set_page_config(layout="wide", page_title="Dashboard Financeiro e Imobiliário")

# Funções auxiliares (mantenha as funções existentes aqui)
def format_currency(value):
    if pd.isna(value):
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_date(date):
    return date.strftime("%d/%m/%Y")

def create_card(title, value, color="#FFF", text_color="#333"):
    st.markdown(
        f"""
        <div style="
            background-color: {color};
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        ">
            <h3 style="color: {text_color}; margin-bottom: 0; font-size: 18px;">{title}</h3>
            <p style="color: {text_color}; font-size: 24px; font-weight: bold; margin-top: 10px;">{value}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

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

def analise_despesas(df_caixa, df_tipo_mov):
    st.header("Análise Detalhada de Despesas")

    # Filtrar apenas as saídas (despesas)
    df_despesas = df_caixa[df_caixa['categoria'] == 'saida'].copy()

    # Converter a coluna 'data_mov' para datetime
    df_despesas['data_mov'] = pd.to_datetime(df_despesas['data_mov'], errors='coerce')

    # Remover linhas com datas inválidas
    df_despesas = df_despesas.dropna(subset=['data_mov'])

    # Criar dicionário de mapeamento para descrições de tipo_mov
    tipo_mov_dict = dict(zip(df_tipo_mov['_id'], df_tipo_mov['descrição']))
    df_despesas['tipo_mov_desc'] = df_despesas['tipo_mov'].map(tipo_mov_dict)

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        data_inicio = st.date_input("Data Inicial", min(df_despesas['data_mov']).date(), format="DD/MM/YYYY")
    with col2:
        data_fim = st.date_input("Data Final", max(df_despesas['data_mov']).date(), format="DD/MM/YYYY")
    with col3:
        categorias = st.multiselect("Categorias", options=df_despesas['tipo_mov_desc'].unique())

    # Filtro de texto para observações
    texto_pesquisa = st.text_input("Pesquisar nas observações", "")

    # Aplicar filtros
    mask = (df_despesas['data_mov'].dt.date >= data_inicio) & (df_despesas['data_mov'].dt.date <= data_fim)
    if categorias:
        mask &= df_despesas['tipo_mov_desc'].isin(categorias)
    if texto_pesquisa:
        mask &= df_despesas['obs'].str.contains(texto_pesquisa, case=False, na=False)

    df_filtrado = df_despesas[mask]

    # Gráfico de despesas ao longo do tempo
    df_timeline = df_filtrado.groupby(df_filtrado['data_mov'].dt.date)['valor'].sum().reset_index()
    df_timeline['data_mov_str'] = df_timeline['data_mov'].astype(str)
    fig_timeline = px.bar(
        df_timeline,
        x='data_mov',
        y='valor',
        title="Despesas ao Longo do Tempo",
        labels={'data_mov': 'Data', 'valor': 'Valor Total (R$)'}
    )
    fig_timeline.update_traces(
        hovertemplate="Data: %{x|%d/%m/%Y}<br>Valor: R$ %{y:,.2f}<extra></extra>"
    )
    fig_timeline.update_layout(
        xaxis_tickformat='%d/%m/%Y',
        yaxis_tickformat='R$ ,',
        xaxis_title="Data",
        yaxis_title="Valor Total (R$)"
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

    # Gráfico de pizza para categorias de despesas
    fig_pie = px.pie(
        df_filtrado.groupby('tipo_mov_desc')['valor'].sum().reset_index(),
        values='valor',
        names='tipo_mov_desc',
        title="Distribuição de Despesas por Categoria"
    )
    fig_pie.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate="Categoria: %{label}<br>Valor: R$ %{value:,.2f}<br>Porcentagem: %{percent}<extra></extra>"
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    # Tabela detalhada de despesas
    st.subheader("Detalhamento de Despesas")
    df_tabela = df_filtrado[['data_mov', 'valor', 'tipo_mov_desc', 'obs']].sort_values('data_mov', ascending=False)
    df_tabela['data_mov'] = df_tabela['data_mov'].dt.strftime('%d/%m/%Y')
    df_tabela['valor'] = df_tabela['valor'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    st.dataframe(df_tabela)

    # Estatísticas resumidas
    st.subheader("Resumo Estatístico")
    col1, col2, col3 = st.columns(3)
    total_despesas = df_filtrado['valor'].sum()
    media_diaria = df_filtrado.groupby(df_filtrado['data_mov'].dt.date)['valor'].sum().mean()
    maior_despesa = df_filtrado['valor'].max()

    col1.metric("Total de Despesas", f"R$ {total_despesas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    col2.metric("Média Diária", f"R$ {media_diaria:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    col3.metric("Maior Despesa", f"R$ {maior_despesa:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
# Função principal
def main():
    # Título do Dashboard
    st.title("Dashboard Financeiro e Imobiliário")

    # URLs da API
    caixa_url = "https://commitar.com.br/api/1.1/obj/I_caixa"
    tipo_mov_url = "https://commitar.com.br/api/1.1/obj/I_tipo_mov"
    imoveis_url = "https://commitar.com.br/api/1.1/obj/I_imoveis"

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

    if all([df_caixa is not None, df_tipo_mov is not None, df_imoveis is not None]):
        # Criar dicionários de mapeamento
        tipo_mov_dict = dict(zip(df_tipo_mov['_id'], df_tipo_mov['descrição']))
        imoveis_dict = dict(zip(df_imoveis['_id'], df_imoveis['descricao']))

        # Mapear descrições
        df_caixa['tipo_mov_desc'] = df_caixa['tipo_mov'].map(tipo_mov_dict)
        df_caixa['imovel_desc'] = df_caixa['imovel'].map(imoveis_dict)
        df_caixa['data_mov'] = df_caixa['data_mov'].apply(safe_parse_date)
        df_caixa['valor'] = pd.to_numeric(df_caixa['valor'], errors='coerce')

        # Filtros no sidebar
        periodo = st.sidebar.selectbox(
            "Selecione período",
            ["Todos", "Mês atual", "Último mês", "Últimos 3 meses", "Últimos 6 meses", "Último ano", "Personalizado"]
        )

        if periodo == "Personalizado":
            min_date = df_caixa['data_mov'].min().date()
            max_date = df_caixa['data_mov'].max().date()
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
                start_date = df_caixa['data_mov'].min().date()
                end_date = df_caixa['data_mov'].max().date()

        if periodo != "Todos":
            df_caixa_filtered = df_caixa[(df_caixa['data_mov'].dt.date >= start_date) & (df_caixa['data_mov'].dt.date <= end_date)]
        else:
            df_caixa_filtered = df_caixa

        if periodo != "Todos":
            st.write(f"Dados de {format_date(start_date)} até {format_date(end_date)}")
        else:
            st.write("Mostrando todos os dados disponíveis")

        # Cálculos gerais
        entrada_total = df_caixa_filtered[df_caixa_filtered['categoria'] == 'entrada']['valor'].sum()
        saida_total = df_caixa_filtered[df_caixa_filtered['categoria'] == 'saida']['valor'].sum()
        saldo = entrada_total - saida_total

        # Exibir cards com resumo
        col1, col2, col3 = st.columns(3)
        with col1:
            create_card("Entrada", format_currency(entrada_total), "#4CAF50", "#FFF")  # Verde para entrada
        with col2:
            create_card("Saída", format_currency(saida_total), "#F44336", "#FFF")  # Vermelho para saída
        with col3:
            if saldo >= 0:
                create_card("Saldo", format_currency(saldo), "#4CAF50", "#FFF")  # Verde para saldo positivo
            else:
                create_card("Saldo", format_currency(saldo), "#F44336", "#FFF")  # Vermelho para saldo negativo

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

        # Adicionar uma separação visual antes da análise de despesas
        st.markdown("---")

        # Chamar a função de análise de despesas
        analise_despesas(df_caixa, df_tipo_mov)

    else:
        st.error("Não foi possível carregar todos os dados necessários. Por favor, verifique sua conexão e tente novamente.")

# Executar a função principal
if __name__ == "__main__":
    main()