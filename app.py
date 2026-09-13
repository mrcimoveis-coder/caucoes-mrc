import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# 1. Configuração da Página
st.set_page_config(page_title="Gestão de Cauções | MRC Imóveis", page_icon="🔐", layout="wide")

try:
    st.image("https://raw.githubusercontent.com/mrcimoveis-coder/portal-intranet/main/logo.jpeg", width=260)
except Exception:
    pass

# 2. Conexão com Google Sheets via ID
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def conectar_google_sheets():
    credenciais_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in credenciais_dict:
        credenciais_dict["private_key"] = credenciais_dict["private_key"].replace("\\n", "\n")
    
    credentials = Credentials.from_service_account_info(credenciais_dict, scopes=SCOPES)
    client = gspread.authorize(credentials)
    return client.open_by_key("1OE3lN6bLUAemM_PyrsrVtN4BqMc-zrH1sCy5qzWGmrk").sheet1

# 3. Autenticação de Acesso
USUARIOS = {
    "admin": "431360#In",
    "marcelo": "431360Ca",
    "marcio": "Mpve2804",
    "pedro.martinez": "431360"
}

if "autenticado_caucao" not in st.session_state:
    st.session_state.autenticado_caucao = False

if not st.session_state.autenticado_caucao:
    st.title("🔒 Acesso Restrito — Gestão de Cauções")
    usuario_input = st.text_input("Usuário:").lower().strip()
    senha_input = st.text_input("Senha:", type="password")
    
    if st.button("Entrar", type="primary"):
        if usuario_input in USUARIOS and USUARIOS[usuario_input] == senha_input:
            st.session_state.autenticado_caucao = True
            st.rerun()
        else:
            st.error("❌ Usuário ou senha incorretos.")
    st.stop()

# 4. Carregamento dos Dados
try:
    sheet = conectar_google_sheets()
except Exception as e:
    st.error(f"❌ Erro de conexão com o Google Sheets: {e}")
    st.stop()

st.title("🔐 Gestão de Cauções de Aluguel — MRC Imóveis")
st.write("Controle de depósitos, cálculo de rendimentos e provisão de juros futuros.")

aba_dash, aba_consulta, aba_novo, aba_quitar, aba_editar = st.tabs([
    "📊 Dashboard & Projeções", 
    "🔍 Consulta & Pendências", 
    "➕ Novo Depósito", 
    "✅ Quitar / Devolver", 
    "✏️ Editar / Excluir"
])

dados_raw = sheet.get_all_records()
df = pd.DataFrame(dados_raw) if dados_raw else pd.DataFrame()

# Tratamento Numérico e Funções de Projeção
def tratar_valor_num(v):
    v_str = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(v_str)
    except:
        return 0.0

ano_atual = datetime.now().year
ano_seguinte = ano_atual + 1

def obter_taxa_anual(idx_type):
    idx = str(idx_type).upper()
    if "POUP" in idx:
        return 0.07  # Poupança (7.0% a.a.)
    elif "NENHUM" in idx:
        return 0.0
    return 0.02  # Padrão TR (2.0% a.a.)

def calcular_valor_em_data(row, target_year, target_month=12):
    v_ini = row.get("Valor_Num", 0.0)
    dt_str = str(row.get("Data Inicial", "")).strip()
    
    if not dt_str or v_ini <= 0:
        return v_ini
        
    try:
        dt_ini = pd.to_datetime(dt_str, format="%d/%m/%Y", errors="coerce")
        if pd.isna(dt_ini):
            return v_ini
        
        meses = (target_year - dt_ini.year) * 12 + (target_month - dt_ini.month)
        if meses < 0:
            meses = 0
            
        taxa_anual = obter_taxa_anual(row.get("Indexador", "TR"))
        return round(v_ini * ((1 + taxa_anual) ** (meses / 12.0)), 2)
    except:
        return v_ini

if not df.empty and "Valor Inicial (R$)" in df.columns:
    df["Valor_Num"] = df["Valor Inicial (R$)"].apply(tratar_valor_num)
    
    # Cálculos Dinâmicos
    df["Valor_Hoje"] = df.apply(lambda r: calcular_valor_em_data(r, datetime.now().year, datetime.now().month), axis=1)
    df["Valor_Dez_Atual"] = df.apply(lambda r: calcular_valor_em_data(r, ano_atual, 12), axis=1)
    df["Valor_Dez_Seguinte"] = df.apply(lambda r: calcular_valor_em_data(r, ano_seguinte, 12), axis=1)
    df["Reserva_Juros_Ano"] = df["Valor_Dez_Seguinte"] - df["Valor_Dez_Atual"]
else:
    df = pd.DataFrame(columns=[
        "ID", "Imóvel", "Locatário", "CPF/CNPJ", "Data Inicial", "Valor Inicial (R$)", "Indexador", "Status", "Data de Devolução", "Observação"
    ])
    df["Valor_Num"] = 0.0
    df["Valor_Hoje"] = 0.0
    df["Valor_Dez_Atual"] = 0.0
    df["Valor_Dez_Seguinte"] = 0.0
    df["Reserva_Juros_Ano"] = 0.0

# --- ABA 1: DASHBOARD ---
with aba_dash:
    if df.empty:
        st.info("Nenhuma caução cadastrada até o momento.")
    else:
        df_ativas = df[df["Status"].astype(str).str.upper() == "ATIVA"]
        df_quitadas = df[df["Status"].astype(str).str.upper() != "ATIVA"]
        
        tot_ini_ativas = df_ativas["Valor_Num"].sum()
        tot_dez_atual = df_ativas["Valor_Dez_Atual"].sum()
        tot_dez_seg = df_ativas["Valor_Dez_Seguinte"].sum()
        tot_provisao_juros = df_ativas["Reserva_Juros_Ano"].sum()
        
        st.subheader(f"📊 Resumo Geral de Cauções Ativas (Base: {ano_atual})")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Contratos Ativos", f"{len(df_ativas)}")
        c2.metric(f"Projeção Dez/{ano_atual}", f"R$ {tot_dez_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c3.metric(f"Projeção Dez/{ano_seguinte}", f"R$ {tot_dez_seg:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c4.metric(f"Juros a Guardar ({ano_atual} ➔ {ano_seguinte})", f"R$ {tot_provisao_juros:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=f"+ R$ {tot_provisao_juros:,.2f}")
        
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader(f"Projeção de Saldo por Indexador (Dez/{ano_seguinte})")
            if not df_ativas.empty:
                fig_idx = px.pie(df_ativas, names="Indexador", values="Valor_Dez_Seguinte", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig_idx, use_container_width=True)
                
        with col_g2:
            st.subheader(f"Top 7 Maior Provisão de Juros Necessária")
            if not df_ativas.empty:
                df_top = df_ativas.sort_values("Reserva_Juros_Ano", ascending=False).head(7)
                fig_top = px.bar(df_top, x="Reserva_Juros_Ano", y="Locatário", orientation="h", color="Indexador", labels={"Reserva_Juros_Ano": "Juros a Guardar (R$)"})
                fig_top.update_layout(yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_top, use_container_width=True)

# --- ABA 2: CONSULTA & PENDÊNCIAS ---
with aba_consulta:
    st.subheader("Consulta e Histórico de Garantias")
    if not df.empty:
        f1, f2, f3 = st.columns(3)
        with f1:
            st_sel = st.selectbox("Status:", ["Ativas (Pendentes)", "Todas", "Quitadas / Devolvidas"])
        with f2:
            idx_sel = st.selectbox("Indexador:", ["Todos"] + list(df["Indexador"].unique()))
        with f3:
            kw = st.text_input("🔎 Pesquisar (Locatário, Imóvel ou CPF/CNPJ):")
            
        df_f = df.copy()
        if st_sel == "Ativas (Pendentes)":
            df_f = df_f[df_f["Status"].astype(str).str.upper() == "ATIVA"]
        elif st_sel == "Quitadas / Devolvidas":
            df_f = df_f[df_f["Status"].astype(str).str.upper() != "ATIVA"]
            
        if idx_sel != "Todos":
            df_f = df_f[df_f["Indexador"] == idx_sel]
            
        if kw:
            kw_l = kw.lower()
            mask = df_f.apply(lambda r: r.astype(str).str.lower().str.contains(kw_l).any(), axis=1)
            df_f = df_f[mask]
            
        st.write(f"**Registros encontrados:** {len(df_f)} | **Juros Totais a Guardar:** R$ {df_f['Reserva_Juros_Ano'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        # Formatação para tabela
        df_f["Projeção Dez/26"] = df_f["Valor_Dez_Atual"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df_f["Projeção Dez/27"] = df_f["Valor_Dez_Seguinte"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df_f["Juros (26-27)"] = df_f["Reserva_Juros_Ano"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        cols_show = ["ID", "Imóvel", "Locatário", "Valor Inicial (R$)", "Indexador", "Projeção Dez/26", "Projeção Dez/27", "Juros (26-27)", "Status", "Data de Devolução"]
        cols_exist = [c for c in cols_show if c in df_f.columns]
        st.dataframe(df_f[cols_exist], use_container_width=True, hide_index=True)

# --- ABA 3: NOVO DEPÓSITO ---
with aba_novo:
    st.subheader("Cadastrar Nova Caução Recebida")
    with st.form("form_nova_caucao", clear_on_submit=True):
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            imovel = st.text_input("Endereço / Imóvel *", placeholder="Ex: SQS 216 Bl C Apto 301")
            locatario = st.text_input("Nome do Locatário / Inquilino *", placeholder="Ex: Flavia Pimentel")
            cpf_cnpj = st.text_input("CPF / CNPJ do Locatário", placeholder="Ex: 000.000.000-00")
        with col_n2:
            dt_dep = st.date_input("Data do Depósito Inicial *", value=datetime.today(), format="DD/MM/YYYY")
            valor_dep = st.number_input("Valor Inicial Depositado (R$) *", min_value=0.0, format="%.2f")
            indexador = st.selectbox("Indexador de Correção *", ["TR", "Poupança (NOVA)", "Poup ant/Nova", "nenhum"])
            obs = st.text_area("Observações Adicionais")
            
        btn_salvar_c = st.form_submit_button("💾 Salvar Caução", type="primary")
        
        if btn_salvar_c:
            if valor_dep <= 0 or not imovel or not locatario:
                st.error("⚠️ Preencha o imóvel, locatário e um valor maior que R$ 0,00.")
            else:
                try:
                    prox_id = f"CAU-{len(df)+1:03d}"
                    dt_fmt = dt_dep.strftime("%d/%m/%Y")
                    v_fmt = f"R$ {valor_dep:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    
                    nova_linha = [prox_id, imovel, locatario, cpf_cnpj, dt_fmt, v_fmt, indexador, "Ativa", "", obs]
                    sheet.append_row(nova_linha)
                    st.success(f"✅ Caução {prox_id} registrada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

# --- ABA 4: QUITAR / DEVOLVER ---
with aba_quitar:
    st.subheader("Dar Baixa em Caução Devolvida ao Inquilino")
    df_ativas_q = df[df["Status"].astype(str).str.upper() == "ATIVA"]
    
    if df_ativas_q.empty:
        st.info("Não há cauções ativas pendentes de devolução.")
    else:
        df_ativas_q["ID_Select"] = df_ativas_q.index.astype(str) + " - [" + df_ativas_q["ID"].astype(str) + "] " + df_ativas_q["Locatário"].astype(str) + " (" + df_ativas_q["Valor Inicial (R$)"].astype(str) + ")"
        item_q = st.selectbox("Selecione a caução para dar baixa:", [""] + df_ativas_q["ID_Select"].tolist())
        
        if item_q:
            idx_q = int(item_q.split(" - ")[0])
            linha_real_q = idx_q + 2
            dados_q = df.iloc[idx_q]
            
            st.info(f"Contrato Selecionado: **{dados_q['Imóvel']}** | Inquilino: **{dados_q['Locatário']}** | Projeção Dez/{ano_atual}: **R$ {dados_q['Valor_Dez_Atual']:,.2f}**")
            
            with st.form("form_quitar_caucao"):
                dt_dev = st.date_input("Data de Devolução / Quitação *", value=datetime.today(), format="DD/MM/YYYY")
                obs_dev = st.text_input("Observação da Quitação", value="Caução devolvida integralmente ao término do contrato.")
                
                btn_baixa = st.form_submit_button("✅ Confirmar Devolução e Retirar das Pendências", type="primary")
                
                if btn_baixa:
                    try:
                        sheet.update_cell(linha_real_q, 8, "Quitada/Devolvida")
                        sheet.update_cell(linha_real_q, 9, dt_dev.strftime("%d/%m/%Y"))
                        sheet.update_cell(linha_real_q, 10, obs_dev)
                        st.success("✅ Caução quitada com sucesso e arquivada nas movimentações passadas!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar quitação: {e}")

# --- ABA 5: EDITAR / EXCLUIR ---
with aba_editar:
    st.subheader("Gerenciar e Editar Lançamentos")
    if not df.empty:
        kw_ed = st.text_input("🔎 Pesquisar para alterar ou apagar:")
        df_e = df.copy()
        if kw_ed:
            mask_e = df_e.apply(lambda r: r.astype(str).str.lower().str.contains(kw_ed.lower()).any(), axis=1)
            df_e = df_e[mask_e]
            
        if not df_e.empty:
            df_e["ID_Edit"] = df_e.index.astype(str) + " - [" + df_e["ID"].astype(str) + "] " + df_e["Locatário"].astype(str)
            item_e = st.selectbox("Selecione para editar ou excluir:", [""] + df_e["ID_Edit"].tolist())
            
            if item_e:
                idx_e = int(item_e.split(" - ")[0])
                linha_real_e = idx_e + 2
                dados_e = df.iloc[idx_e]
                
                with st.form("form_edit_caucao"):
                    e1, e2 = st.columns(2)
                    with e1:
                        ed_imovel = st.text_input("Imóvel", value=str(dados_e.get("Imóvel", "")))
                        ed_loc = st.text_input("Locatário", value=str(dados_e.get("Locatário", "")))
                        ed_cpf = st.text_input("CPF/CNPJ", value=str(dados_e.get("CPF/CNPJ", "")))
                        ed_dt = st.text_input("Data Inicial", value=str(dados_e.get("Data Inicial", "")))
                    with e2:
                        ed_val = st.text_input("Valor Inicial (R$)", value=str(dados_e.get("Valor Inicial (R$)", "")))
                        ed_idx = st.text_input("Indexador", value=str(dados_e.get("Indexador", "")))
                        ed_st = st.selectbox("Status", ["Ativa", "Quitada/Devolvida"], index=0 if str(dados_e.get("Status")).upper()=="ATIVA" else 1)
                        ed_dt_dev = st.text_input("Data de Devolução", value=str(dados_e.get("Data de Devolução", "")))
                    
                    btn_alt = st.form_submit_button("🔄 Salvar Alterações", type="primary")
                    if btn_alt:
                        try:
                            sheet.update_cell(linha_real_e, 2, ed_imovel)
                            sheet.update_cell(linha_real_e, 3, ed_loc)
                            sheet.update_cell(linha_real_e, 4, ed_cpf)
                            sheet.update_cell(linha_real_e, 5, ed_dt)
                            sheet.update_cell(linha_real_e, 6, ed_val)
                            sheet.update_cell(linha_real_e, 7, ed_idx)
                            sheet.update_cell(linha_real_e, 8, ed_st)
                            sheet.update_cell(linha_real_e, 9, ed_dt_dev)
                            st.success("✅ Registro atualizado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar edição: {e}")
