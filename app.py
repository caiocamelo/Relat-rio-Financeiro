import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import os
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Gestão Financeira", layout="wide")
st.title("💰 Gestão Financeira Pessoal e Loja")

# Arquivo de persistência
DATA_FILE = "financeiro.csv"

# Categorias Padrão
CATEGORIAS = [
    "Vendas/Receita",
    "Aluguel",
    "Mercadoria",
    "Pro-labore",
    "Investimento",
    "Marketing",
    "Serviços (Luz/Água/Net)",
    "Outros"
]

# --- Funções de Dados ---

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            return pd.read_csv(DATA_FILE)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame(columns=["Data", "Descrição", "Categoria", "Tipo", "Valor"])
    else:
        return pd.DataFrame(columns=["Data", "Descrição", "Categoria", "Tipo", "Valor"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# Carregar dados iniciais
if "df" not in st.session_state:
    st.session_state["df"] = load_data()

# --- Sidebar: Menu ---
menu = st.sidebar.radio("Navegação", ["Dashboard", "Lançamentos e Importação"])

# --- Lógica Principal ---

if menu == "Lançamentos e Importação":
    st.header("📝 Lançamentos e Importação de Dados")

    tab1, tab2 = st.tabs(["Registro Manual", "Importação de Arquivos"])

    with tab1:
        st.subheader("Novo Lançamento")
        with st.form("form_lancamento"):
            col1, col2 = st.columns(2)
            data = col1.date_input("Data", datetime.today())
            tipo = col2.selectbox("Tipo", ["Entrada", "Saída"])
            
            col3, col4 = st.columns(2)
            valor = col3.number_input("Valor (R$)", min_value=0.0, step=0.01)
            categoria = col4.selectbox("Categoria", CATEGORIAS)
            
            descricao = st.text_input("Descrição")
            
            submitted = st.form_submit_button("Salvar Lançamento")
            
            if submitted:
                novo_registro = {
                    "Data": data.strftime("%Y-%m-%d"),
                    "Descrição": descricao,
                    "Categoria": categoria,
                    "Tipo": tipo,
                    "Valor": valor
                }
                st.session_state["df"] = pd.concat([st.session_state["df"], pd.DataFrame([novo_registro])], ignore_index=True)
                save_data(st.session_state["df"])
                st.success("Lançamento salvo com sucesso!")

    with tab2:
        st.subheader("Importar Arquivos")
        st.info("Suporta .xlsx e .pdf (extratos). O sistema tentará identificar colunas automaticamente.")
        uploaded_file = st.file_uploader("Escolha um arquivo", type=["xlsx", "pdf"])
        
        if uploaded_file:
            tipo_arquivo = uploaded_file.name.split('.')[-1].lower()
            if st.button("Processar Importação"):
                try:
                    df_novo = pd.DataFrame()
                    
                    if tipo_arquivo == 'xlsx':
                        df_temp = pd.read_excel(uploaded_file)
                        # Normalização simples de colunas (tentativa)
                        # Mapeamento flexível: chave é o padrão esperado, valores são possíveis nomes no arquivo
                        mapa_colunas = {
                            "Data": ["Data", "Date", "Dia", "Data Movimento"],
                            "Descrição": ["Descrição", "Description", "Histórico", "Descricao"],
                            "Valor": ["Valor", "Value", "Quantia", "Montante", "Crédito", "Débito"] # Simples, assume coluna única ou trata depois
                        }

                        # Renomear colunas encontradas
                        rename_dict = {}
                        for padrao, possiveis in mapa_colunas.items():
                            for col in df_temp.columns:
                                if col in possiveis:
                                    rename_dict[col] = padrao
                                    break
                        
                        df_temp.rename(columns=rename_dict, inplace=True)
                        
                        # Filtrar apenas as colunas necessárias se existirem
                        cols_existentes = [c for c in ["Data", "Descrição", "Valor"] if c in df_temp.columns]
                        if len(cols_existentes) >= 3:
                            df_novo = df_temp[cols_existentes].copy()
                            # Definir categoria e tipo padrão para edição posterior
                            df_novo["Categoria"] = "Outros"
                            df_novo["Tipo"] = df_novo["Valor"].apply(lambda x: "Entrada" if x > 0 else "Saída")
                            df_novo["Valor"] = df_novo["Valor"].abs()
                        else:
                            st.error(f"Não foi possível identificar as colunas Data, Descrição e Valor. Colunas encontradas: {list(df_temp.columns)}")
                    
                    elif tipo_arquivo == 'pdf':
                        rows = []
                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
                                table = page.extract_table()
                                if table:
                                    for row in table:
                                        # Heurística simples: Data na primeira col, Descrição no meio, Valor no fim
                                        # Ajuste conforme extratos reais. Aqui assumimos uma estrutura tabular limpa.
                                        # Ignorar cabeçalhos e linhas vazias
                                        if row and len(row) >= 3:
                                            # Tentar identificar data
                                            try:
                                                # Tenta parsers de data comuns
                                                pd.to_datetime(row[0], dayfirst=True) # Apenas teste silencioso
                                                data_str = row[0]
                                                desc_str = row[1] 
                                                # Valor pode estar em variadas posições, pegamos a última com valor numérico ou a última coluna
                                                valor_str = row[-1]
                                                
                                                # Limpeza básica de moeda (R$, espaço, pontos)
                                                valor_limpo = str(valor_str).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                                                valor_float = float(valor_limpo)
                                                
                                                rows.append({
                                                    "Data": data_str,
                                                    "Descrição": desc_str,
                                                    "Valor": abs(valor_float),
                                                    "Categoria": "Outros",
                                                    "Tipo": "Entrada" if valor_float > 0 else "Saída" 
                                                })
                                            except:
                                                continue # Linha não é um lançamento válido
                        
                        if rows:
                            df_novo = pd.DataFrame(rows)

                    if not df_novo.empty:
                        # Conversão final e salvamento
                        df_novo["Data"] = pd.to_datetime(df_novo["Data"], dayfirst=True, errors='coerce').dt.strftime("%Y-%m-%d")
                        df_novo.dropna(subset=["Data"], inplace=True) # Remove linhas onde data falhou
                        
                        st.session_state["df"] = pd.concat([st.session_state["df"], df_novo], ignore_index=True)
                        save_data(st.session_state["df"])
                        st.success(f"{len(df_novo)} registros importados com sucesso! Verifique a tabela abaixo para ajustar Categorias.")
                    else:
                        st.warning("Nenhum dado válido encontrado para importação.")

                except Exception as e:
                    st.error(f"Erro ao processar arquivo: {e}")

    st.divider()
    st.subheader("📋 Últimos Lançamentos")
    st.dataframe(st.session_state["df"].sort_values(by="Data", ascending=False).head(10), use_container_width=True)

elif menu == "Dashboard":
    st.header("📊 Visão Geral")
    df = st.session_state["df"]
    
    if not df.empty:
        # Conversão de tipos para garantir cálculos
        df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0)
        
        # Filtros de data (opcional, por enquanto pega tudo)
        
        # KPIs
        total_entradas = df[df["Tipo"] == "Entrada"]["Valor"].sum()
        total_saidas = df[df["Tipo"] == "Saída"]["Valor"].sum()
        
        # Lucro Operacional (Simplificado: Entradas - Saídas)
        # Nota: O usuário pediu 'Lucro Operacional' = Receitas - Despesas Operacionais.
        # Vamos assumir que 'Investimento' e 'Pro-labore' NÃO são despesas operacionais para esse cálculo, 
        # mas 'Saída' geral inclui tudo. Vamos refinar isso.
        
        despesas_operacionais = df[
            (df["Tipo"] == "Saída") & 
            (~df["Categoria"].isin(["Pro-labore", "Investimento"]))
        ]["Valor"].sum()
        
        lucro_operacional = total_entradas - despesas_operacionais
        
        pro_labore = df[df["Categoria"] == "Pro-labore"]["Valor"].sum()
        investimento = df[df["Categoria"] == "Investimento"]["Valor"].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Lucro Operacional Est.", f"R$ {lucro_operacional:,.2f}")
        col2.metric("Pro-labore Acumulado", f"R$ {pro_labore:,.2f}")
        col3.metric("Total Investido", f"R$ {investimento:,.2f}")
        
        st.divider()
        
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.subheader("Entradas vs Saídas")
            # Agrupar por Tipo
            fig_bar = px.bar(
                df.groupby("Tipo")["Valor"].sum().reset_index(), 
                x="Tipo", y="Valor", color="Tipo", title="Comparativo Total"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_graf2:
            st.subheader("Gastos por Categoria")
            df_saidas = df[df["Tipo"] == "Saída"]
            if not df_saidas.empty:
                fig_pie = px.pie(
                    df_saidas, values="Valor", names="Categoria", title="Distribuição de Saídas"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Sem dados de saída para exibir gráfico de categorias.")
                
    else:
        st.info("Nenhum dado registrado. Vá para a aba 'Lançamentos' para começar.")
