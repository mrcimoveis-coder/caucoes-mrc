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

# 2. Conexão com Google Sheets
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
st.write("Controle de depósitos, taxas de reajuste customizáveis e reserva de juros futuros.")

aba_dash, aba_consulta, aba_novo, aba_quitar, aba_editar = st.tabs([
    "📊 Dashboard & Projeções", 
    "🔍 Consulta & Pendências", 
    "➕ Novo Depósito", 
    "✅ Quitar / Devolver", 
    "✏️ Editar / Excluir"
])

dados_raw = sheet.get_all_records()
df = pd.DataFrame(dados_raw) if dados_raw else pd.DataFrame()

# Tratamento Numérico
def tratar_valor_num(v):
    v_str = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(v_str)
    except:
        return 0.0

def tratar_taxa_num(v):
    v_str = str(v).replace("%", "").replace(",", ".").strip()
    try:
        return float(v_str) / 100.0
    except:
        return 0.02

if not df.empty and "Projeção Dez/26 (R$)" in df.columns:
    df["Valor_Ini_Num"] = df["Valor Inicial (R$)"].apply(tratar_valor_num)
    df["Projecao_26_Num"] = df["Projeção Dez/26 (R$)"].apply(tratar_valor_num)
    df["Taxa_Num"] = df["% Taxa Anual"].apply(tratar_taxa_num)
    
    # Cálculo dinâmico para o próximo ano com base na taxa de cada contrato
    df["Projecao_27_Num"] = df.apply(
        lambda r: round(r["Projecao_26_Num"] * (1.0 + r["Taxa_Num"]), 2) if r["Projecao_26_Num"] > 0 else 0.0,
        axis=1
    )
    df["Reserva_Juros"] = df["Projecao_27_Num"] - df["Projecao_26_Num"]
else:
    df = pd.DataFrame(columns=[
        "ID", "Imóvel", "Locatário", "CPF/CNPJ", "Data Inicial", "Valor Inicial (R$)", 
        "Indexador", "% Taxa Anual", "Projeção Dez/26 (R$)", "Projeção Dez/27 (R$)", 
        "Status", "Data de Devolução", "Observação"
    ])
    df["Valor_Ini_Num"] = 0.0
    df["Projecao_26_Num"] = 0.0
    df["Taxa_Num"] = 0.02
    df["Projecao_27_Num"] = 0.0
    df["Reserva_Juros"] = 0.0

# --- ABA 1: DASHBOARD ---
with aba_dash:
    if df.empty:
        st.info("Nenhuma caução cadastrada até o momento.")
    else:
        df_ativas = df[df["Status"].astype(str).str.upper() == "ATIVA"]
        df_quitadas = df[df["Status"].astype(str).str.upper() != "ATIVA"]
        
        tot_ini_ativas = df_ativas["Valor_Ini_Num"].sum()
        tot_26_ativas = df_ativas["Projecao_26_Num"].sum()
        tot_27_ativas = df_ativas["Projecao_27_Num"].sum()
        tot_juros_reserva = df_ativas["Reserva_Juros"].sum()
        
        st.subheader("📊 Resumo Geral de Cauções Ativas (Projeção 2026 ➔ 2027)")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Contratos Ativos", f"{len(df_ativas)}")
        c2.metric("Projeção Dez/2026", f"R$ {tot_26_ativas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c3.metric("Projeção Dez/2027", f"R$ {tot_27_ativas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c4.metric("Juros a Guardar (2026 ➔ 2027)", f"R$ {tot_juros_reserva:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=f"+ R$ {tot_juros_reserva:,.2f}")
        
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("Saldo Retido por Indexador (Dez/2026)")
            if not df_ativas.empty:
                fig_idx = px.pie(df_ativas, names="Indexador", values="Projecao_26_Num", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig_idx, use_container_width=True)
                
        with col_g2:
            st.subheader("Top 7 Maiores Reservas de Juros Necessárias")
            if not df_ativas.empty:
                df_top = df_ativas.sort_values("Reserva_Juros", ascending=False).head(7)
                fig_top = px.bar(df_top, x="Reserva_Juros", y="Locatário", orientation="h", color="Indexador", labels={"Reserva_Juros": "Juros a Guardar (R$)"})
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
            
        st.write(f"**Registros encontrados:** {len(df_f)} | **Juros Totais a Guardar:** R$ {df_f['Reserva_Juros'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        df_f["Projeção 2026"] = df_f["Projecao_26_Num"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df_f["Projeção 2027"] = df_f["Projecao_27_Num"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df_f["Reserva Juros"] = df_f["Reserva_Juros"].apply(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        cols_show = ["ID", "Imóvel", "Locatário", "Valor Inicial (R$)", "Indexador", "% Taxa Anual", "Projeção 2026", "Projeção 2027", "Reserva Juros", "Status"]
        cols_exist = [c for c in cols_show if c in df_f.columns]
        st.dataframe(df_f[cols_exist], use_container_width=True, hide_index=True)

# --- ABA 3: NOVO DEPÓSITO ---
with aba_novo:
    st.subheader("Cadastrar Nova Caução Recebida")
    
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        imovel = st.text_input("Endereço / Imóvel *", placeholder="Ex: SQS 216 Bl C Apto 301")
        locatario = st.text_input("Nome do Locatário / Inquilino *", placeholder="Ex: Flavia Pimentel")
        cpf_cnpj = st.text_input("CPF / CNPJ do Locatário", placeholder="Ex: 000.000.000-00")
        dt_dep = st.date_input("Data do Depósito Inicial *", value=datetime.today(), format="DD/MM/YYYY")
    with col_n2:
        valor_dep = st.number_input("Valor Inicial Depositado (R$) *", min_value=0.0, format="%.2f")
        indexador = st.selectbox("Indexador de Correção *", ["TR", "Poupança (NOVA)", "Poup ant/Nova", "nenhum"])
        
        # Sugestão dinâmica do percentual com possibilidade de alteração pelo usuário
        sugestao_taxa = 2.0
        if "POUP" in indexador.upper():
            sugestao_taxa = 7.0
        elif "NENHUM" in indexador.upper():
            sugestao_taxa = 0.0
            
        taxa_custom = st.number_input("% Reajuste Anual Estimado *", min_value=0.0, max_value=50.0, value=sugestao_taxa, step=0.1, format="%.2f")
        obs = st.text_area("Observações Adicionais")
        
    btn_salvar_c = st.button("💾 Salvar Caução", type="primary", use_container_width=True)
    
    if btn_salvar_c:
        if valor_dep <= 0 or not imovel or not locatario:
            st.error("⚠️ Preencha o imóvel, locatário e um valor maior que R$ 0,00.")
        else:
            try:
                prox_id = f"CAU-{len(df)+1:03d}"
                dt_fmt = dt_dep.strftime("%d/%m/%Y")
                v_fmt = f"R$ {valor_dep:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                taxa_fmt = f"{taxa_custom:.1f}%".replace(".", ",")
                
                # Projeção inicial (Dez/26 base igual valor depositado se for do ano vigente)
                p26_fmt = v_fmt
                p27_calc = valor_dep * (1.0 + (taxa_custom / 100.0))
                p27_fmt = f"R$ {p27_calc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                nova_linha = [prox_id, imovel, locatario, cpf_cnpj, dt_fmt, v_fmt, indexador, taxa_fmt, p26_fmt, p27_fmt, "Ativa", "", obs]
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
            
            st.info(f"Contrato Selecionado: **{dados_q['Imóvel']}** | Inquilino: **{dados_q['Locatário']}** | Base Dez/2026: **R$ {dados_q['Projecao_26_Num']:,.2f}**")
            
            with st.form("form_quitar_caucao"):
                dt_dev = st.date_input("Data de Devolução / Quitação *", value=datetime.today(), format="DD/MM/YYYY")
                obs_dev = st.text_input("Observação da Quitação", value="Caução devolvida integralmente ao término do contrato.")
                
                btn_baixa = st.form_submit_button("✅ Confirmar Devolução e Retirar das Pendências", type="primary")
                
                if btn_baixa:
                    try:
                        sheet.update_cell(linha_real_q, 11, "Quitada/Devolvida")
                        sheet.update_cell(linha_real_q, 12, dt_dev.strftime("%d/%m/%Y"))
                        sheet.update_cell(linha_real_q, 13, obs_dev)
                        st.success("✅ Caução quitada com sucesso e arquivada!")
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
                        ed_val = st.text_input("Valor Inicial (R$)", value=str(dados_e.get("Valor Inicial (R$)", "")))
                    with e2:
                        ed_idx = st.text_input("Indexador", value=str(dados_e.get("Indexador", "")))
                        ed_taxa = st.text_input("% Taxa Anual", value=str(dados_e.get("% Taxa Anual", "2,0%")))
                        ed_p26 = st.text_input("Projeção Dez/26 (R$)", value=str(dados_e.get("Projeção Dez/26 (R$)", "")))
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
                            sheet.update_cell(linha_real_e, 8, ed_taxa)
                            sheet.update_cell(linha_real_e, 9, ed_p26)
                            sheet.update_cell(linha_real_e, 11, ed_st)
                            sheet.update_cell(linha_real_e, 12, ed_dt_dev)
                            st.success("✅ Registro atualizado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar edição: {e}")
