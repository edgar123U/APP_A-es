import streamlit as st
from mplsoccer import Pitch
import matplotlib.pyplot as plt
import pandas as pd
import io
import numpy as np
from fpdf import FPDF
import os

# Configuração da Página
st.set_page_config(page_title="Relatório Tecnico-Tático", layout="wide")

# --- CONFIGURAÇÃO DO LOGO ---
fmh_logo_path = "faculdade_de_motricidade_humana_logo.jpeg"

# --- CABEÇALHO ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists(fmh_logo_path):
        st.image(fmh_logo_path, width=150)
    else:
        st.info("Logo FMH")
with col_title:
    st.title("Relatório de Ações Tecnico-Táticas")

# 1. Estado da Sessão
if 'actions' not in st.session_state:
    st.session_state.actions = pd.DataFrame(columns=[
        'Jogador', 'Ação', 'x', 'y', 'end_x', 'end_y', 'Resultado', 
        'Visualizacao', 'Cor', 'xG', 'Detalhes'
    ])

# --- FUNÇÃO xG ---
def calculate_advanced_xg(x, y, is_header, sit_previa):
    goal_x, goal_y = 105, 34
    dist = np.sqrt((goal_x - x)**2 + (goal_y - y)**2)
    a = np.sqrt((goal_x - x)**2 + (34 - 3.66 - y)**2)
    b = np.sqrt((goal_x - x)**2 + (34 + 3.66 - y)**2)
    cos_angle = np.clip((a**2 + b**2 - 7.32**2) / (2 * a * b), -1, 1)
    angle = np.arccos(cos_angle)
    logit = -0.5 + (1.35 * angle) - (0.11 * dist)
    if is_header: logit -= 1.1
    if sit_previa == "Após Cruzamento": logit -= 0.4
    elif sit_previa == "Após Drible": logit += 0.2
    return round(1 / (1 + np.exp(-logit)), 3)

# --- REGRAS DAS AÇÕES ---
action_rules = {
    'Passe': {'cor': '#3498db', 'seta': True, 'tem_resultado': True},
    'Condução': {'cor': '#9b59b6', 'seta': True, 'tem_resultado': False},
    'Remate': {'cor': '#f1c40f', 'seta': False, 'tem_resultado': True},
    'Interceção': {'cor': '#2ecc71', 'seta': False, 'tem_resultado': False},
    'Bloqueio': {'cor': '#e67e22', 'seta': False, 'tem_resultado': False},
    'Desarme': {'cor': '#1abc9c', 'seta': False, 'tem_resultado': True}
}

# --- SIDEBAR: ESTÉTICA E TÍTULO ---
st.sidebar.header("🎨 Configuração do Campo")
p_theme = st.sidebar.selectbox("Tema:", ["Branco Total", "Grass", "Dark", "Midnight"])
is_strip = st.sidebar.checkbox("Relvado Cortado?", value=False)
is_pos = st.sidebar.checkbox("Linhas Posicionais?", value=False)

themes = {
    "Branco Total": {"pitch": "white", "line": "black", "stripe": "#f2f2f2"},
    "Grass": {"pitch": "#2d5a27", "line": "white", "stripe": "#366b2f"},
    "Dark": {"pitch": "#22312b", "line": "#c7d5cc", "stripe": "#2c3e37"},
    "Midnight": {"pitch": "#1a1c2c", "line": "#94a3b8", "stripe": "#23263a"}
}
c_theme = themes[p_theme]

# TÍTULO PERSONALIZADO DO RELATÓRIO
st.sidebar.markdown("---")
st.sidebar.header("📝 Dados do Relatório")
report_custom_title = st.sidebar.text_input("Título do Relatório PDF", "Relatório Técnico-Tático")

# --- SIDEBAR: REGISTO ---
st.sidebar.markdown("---")
st.sidebar.header("🕹️ Registar Ação")
p_input = st.sidebar.text_input("Jogador (opcional)")
a_type = st.sidebar.selectbox("Tipo de Ação", list(action_rules.keys()))

is_h, sit_p, v_mode = False, "Jogo Corrido", "Marca"
rule = action_rules[a_type]

if a_type == 'Remate':
    v_mode = st.sidebar.radio("Visualização:", ["Marca", "Seta"], horizontal=True)
    is_h = st.sidebar.checkbox("De Cabeça?")
    sit_p = st.sidebar.selectbox("Origem:", ["Jogo Corrido", "Após Cruzamento", "Após Drible"])
elif rule['seta']:
    v_mode = "Seta"

with st.sidebar.form("add_form"):
    c1, c2 = st.columns(2)
    x, y = c1.slider("X", 0.0, 105.0, 52.5), c2.slider("Y", 0.0, 68.0, 34.0)
    ex, ey = x, y
    if v_mode == "Seta":
        c3, c4 = st.columns(2)
        ex, ey = c3.slider("X Fim", 0.0, 105.0, 60.0), c4.slider("Y Fim", 0.0, 68.0, 40.0)
    
    res = "Sucesso"
    if rule['tem_resultado']:
        res = st.radio("Resultado", ["Sucesso", "Insucesso"], horizontal=True)
    
    if st.form_submit_button("Adicionar Ação"):
        final_p = p_input if p_input.strip() != "" else "Geral/Equipa"
        xg_val = calculate_advanced_xg(x, y, is_h, sit_p) if a_type == 'Remate' else 0.0
        detalhes_extra = f"{sit_p}{' (Cabeça)' if is_h else ''}" if a_type == 'Remate' else "-"
        
        new_row = {
            'Jogador': final_p, 'Ação': a_type, 'x': x, 'y': y, 'end_x': ex, 'end_y': ey,
            'Resultado': res, 'Visualizacao': v_mode, 
            'Cor': rule['cor'] if res == "Sucesso" else "#e74c3c",
            'xG': xg_val, 'Detalhes': detalhes_extra
        }
        st.session_state.actions = pd.concat([st.session_state.actions, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.subheader("🔍 Filtros de Visualização")
f_col1, f_col2 = st.columns(2)
sel_p = f_col1.selectbox("Filtrar Jogador:", ["Todos"] + sorted(st.session_state.actions['Jogador'].unique().tolist()))
sel_a = f_col2.selectbox("Filtrar Ação:", ["Todas"] + list(action_rules.keys()))

df_plot = st.session_state.actions.copy()
if sel_p != "Todos": df_plot = df_plot[df_plot['Jogador'] == sel_p]
if sel_a != "Todas": df_plot = df_plot[df_plot['Ação'] == sel_a]

pitch = Pitch(pitch_type='uefa', pitch_color=c_theme['pitch'], line_color=c_theme['line'],
              stripe=is_strip, stripe_color=c_theme['stripe'], positional=is_pos,
              corner_arcs=True, goal_type='box')
fig, ax = pitch.draw(figsize=(10, 7))

for _, row in df_plot.iterrows():
    if row['Visualizacao'] == "Seta":
        pitch.arrows(row.x, row.y, row.end_x, row.end_y, width=2, color=row.Cor, ax=ax, alpha=0.8)
    else:
        ms = 180 + (row['xG'] * 1800) if row['Ação'] == 'Remate' else 180
        marker = 'o'
        if action_rules[row['Ação']]['tem_resultado'] and row['Resultado'] == 'Insucesso':
            marker = 'X'
        pitch.scatter(row.x, row.y, s=ms, c=row.Cor, edgecolors='gray' if p_theme=="Branco Total" else 'white', marker=marker, ax=ax, zorder=3)
st.pyplot(fig)

# --- GESTÃO E EXPORTAÇÃO ---
st.markdown("---")
if not st.session_state.actions.empty:
    
    # --- PDF GENERATOR ---
    def generate_pdf(df_filt, fig_pitch, report_title):
        pdf = FPDF()
        pdf.add_page()
        
        # Logo FMH
        if os.path.exists(fmh_logo_path):
            pdf.image(fmh_logo_path, x=165, y=10, w=30)
        
        # Cabeçalho
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_y(15)
        pdf.cell(150, 10, report_title, ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(150, 6, "Faculdade de Motricidade Humana", ln=True)
        pdf.cell(150, 6, f"Filtros Aplicados: {sel_p} | {sel_a}", ln=True)
        
        # Mapa de Campo
        img_buf = io.BytesIO()
        fig_pitch.savefig(img_buf, format="png", bbox_inches='tight', dpi=150)
        pdf.image(img_buf, x=15, y=45, w=180)
        
        # Legenda das Cores/Ações (O "Logo" das ações)
        pdf.set_y(172)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(190, 8, "Legenda de Cores e Simbolos:", ln=True)
        pdf.set_font("Helvetica", "", 8)
        
        # Gerar legenda baseada nas regras
        for act, info in action_rules.items():
            # Desenhar um quadradinho colorido como "logo"
            r, g, b = tuple(int(info['cor'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            pdf.set_fill_color(r, g, b)
            pdf.rect(pdf.get_x(), pdf.get_y()+1, 3, 3, 'F')
            pdf.set_x(pdf.get_x() + 5)
            pdf.cell(30, 5, f"{act} ({'Seta' if info['seta'] else 'Marca'})")
        pdf.ln(8)

        # Tabela Estatística
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(190, 8, "Tabela de Resultados:", ln=True)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        
        headers = ["Acao", "Sucesso", "Insucesso", "Total", "xG Acum."]
        ws = [45, 35, 35, 35, 40]
        for i, h in enumerate(headers):
            pdf.cell(ws[i], 8, h, border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        for act in df_filt['Ação'].unique():
            temp = df_filt[df_filt['Ação'] == act]
            suc = str(len(temp[temp['Resultado'] == 'Sucesso'])) if action_rules[act]['tem_resultado'] else "-"
            ins = str(len(temp[temp['Resultado'] == 'Insucesso'])) if action_rules[act]['tem_resultado'] else "-"
            total = str(len(temp))
            xg_sum = f"{temp['xG'].sum():.2f}" if act == "Remate" else "-"
            
            pdf.cell(ws[0], 8, act, border=1, align="C")
            pdf.cell(ws[1], 8, suc, border=1, align="C")
            pdf.cell(ws[2], 8, ins, border=1, align="C")
            pdf.cell(ws[3], 8, total, border=1, align="C")
            pdf.cell(ws[4], 8, xg_sum, border=1, align="C")
            pdf.ln()
            
        return bytes(pdf.output())

    # Área de Botões
    col_pdf, col_del = st.columns([1, 1])
    with col_pdf:
        st.subheader("📄 Exportar")
        pdf_bytes = generate_pdf(df_plot, fig, report_custom_title)
        st.download_button("📥 Descarregar PDF", pdf_bytes, f"relatorio_FMH.pdf", "application/pdf")
    
    with col_del:
        st.subheader("🗑️ Gestão")
        if st.button("🚨 Limpar Tudo"):
            st.session_state.actions = pd.DataFrame(columns=st.session_state.actions.columns)
            st.rerun()

    # Tabela detalhada na App
    st.dataframe(df_plot[['Jogador', 'Ação', 'Resultado', 'xG', 'Detalhes']], use_container_width=True)
else:
    st.info("Registe ações para gerar o mapa e o relatório.")
