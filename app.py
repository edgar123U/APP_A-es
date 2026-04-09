import streamlit as st
from mplsoccer import Pitch
import matplotlib.pyplot as plt
import pandas as pd
import io
import numpy as np
from fpdf import FPDF
import os

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Relatório Tecnico-Tático", layout="wide")

# --- FICHEIRO DO LOGO ---
fmh_logo_path = "faculdade_de_motricidade_humana_logo.jpeg"

# 2. ESTADO DA SESSÃO
if 'actions' not in st.session_state:
    st.session_state.actions = pd.DataFrame(columns=[
        'Jogador', 'Ação', 'x', 'y', 'end_x', 'end_y', 'Resultado', 
        'Visualizacao', 'Cor', 'xG', 'Detalhes'
    ])

# --- FUNÇÃO xG ---
def calculate_advanced_xg(x, y, is_header, sit_previa):
    goal_x, goal_y = 105, 34
    dist = np.sqrt((105 - x)**2 + (34 - y)**2)
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

# 3. CABEÇALHO
col_l, col_t = st.columns([1, 4])
with col_l:
    if os.path.exists(fmh_logo_path): st.image(fmh_logo_path, width=120)
with col_t:
    st.title("Relatório de Ações Tecnico-Táticas")

# 4. SIDEBAR - CONFIGURAÇÕES E REGISTO
st.sidebar.header("🎨 Estética e Relatório")
p_theme = st.sidebar.selectbox("Tema do Campo:", ["Branco Total", "Grass", "Dark", "Midnight"])
is_strip = st.sidebar.checkbox("Relvado Cortado?", value=False)
is_pos = st.sidebar.checkbox("Linhas Posicionais?", value=False)
report_custom_title = st.sidebar.text_input("Título do Relatório PDF", "Relatório Técnico-Tático")

themes = {
    "Branco Total": {"pitch": "white", "line": "black", "stripe": "#f2f2f2"},
    "Grass": {"pitch": "#2d5a27", "line": "white", "stripe": "#366b2f"},
    "Dark": {"pitch": "#22312b", "line": "#c7d5cc", "stripe": "#2c3e37"},
    "Midnight": {"pitch": "#1a1c2c", "line": "#94a3b8", "stripe": "#23263a"}
}
c_theme = themes[p_theme]

st.sidebar.markdown("---")
st.sidebar.header("🕹️ Registar Ação")
p_input = st.sidebar.text_input("Jogador (opcional)")
a_type = st.sidebar.selectbox("Tipo de Ação", list(action_rules.keys()))
rule = action_rules[a_type]

# Variáveis específicas de Remate
is_h, sit_p = False, "Jogo Corrido"
v_mode = "Seta" if rule['seta'] else "Marca"
if a_type == 'Remate':
    v_mode = st.sidebar.radio("Visualização:", ["Marca", "Seta"], horizontal=True)
    is_h = st.sidebar.checkbox("De Cabeça?")
    sit_p = st.sidebar.selectbox("Origem:", ["Jogo Corrido", "Após Cruzamento", "Após Drible"])

with st.sidebar.form("add_form"):
    c1, c2 = st.columns(2)
    x = c1.slider("X", 0.0, 105.0, 52.5)
    y = c2.slider("Y", 0.0, 68.0, 34.0)
    
    ex, ey = x, y
    if v_mode == "Seta":
        st.write("🎯 Destino da Seta:")
        c3, c4 = st.columns(2)
        ex = c3.slider("X Fim", 0.0, 105.0, 60.0)
        ey = c4.slider("Y Fim", 0.0, 68.0, 34.0)
    
    res = "Sucesso"
    if rule['tem_resultado']:
        res = st.radio("Resultado", ["Sucesso", "Insucesso"], horizontal=True)
    
    if st.form_submit_button("Adicionar Ação"):
        final_p = p_input if p_input.strip() != "" else "Geral/Equipa"
        xg_val = calculate_advanced_xg(x, y, is_h, sit_p) if a_type == 'Remate' else 0.0
        new_row = {
            'Jogador': final_p, 'Ação': a_type, 'x': x, 'y': y, 'end_x': ex, 'end_y': ey,
            'Resultado': res, 'Visualizacao': v_mode, 
            'Cor': rule['cor'] if res == "Sucesso" else "#e74c3c",
            'xG': xg_val, 'Detalhes': f"{sit_p}{' (Cabeça)' if is_h else ''}" if a_type == 'Remate' else "-"
        }
        st.session_state.actions = pd.concat([st.session_state.actions, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

# 5. ÁREA PRINCIPAL - FILTROS E CAMPO
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
        pitch.arrows(row.x, row.y, row.end_x, row.end_y, width=1.5, headwidth=6, headlength=6, color=row.Cor, ax=ax, zorder=4)
    else:
        ms = 180 + (row['xG'] * 1800) if row['Ação'] == 'Remate' else 180
        marker = 'o'
        if action_rules[row['Ação']]['tem_resultado'] and row['Resultado'] == 'Insucesso':
            marker = 'X'
        pitch.scatter(row.x, row.y, s=ms, c=row.Cor, edgecolors='gray' if p_theme=="Branco Total" else 'white', marker=marker, ax=ax, zorder=3)
st.pyplot(fig)

# 6. GESTÃO E EXPORTAÇÃO
st.markdown("---")
if not st.session_state.actions.empty:
    col_t, col_m = st.columns([2, 1])
    with col_t:
        st.subheader("📋 Log de Ações")
        st.dataframe(df_plot[['Jogador', 'Ação', 'Resultado', 'xG', 'Detalhes']], use_container_width=True)
    with col_m:
        st.subheader("🗑️ Gestão")
        if st.button("Apagar Última"):
            st.session_state.actions = st.session_state.actions.iloc[:-1]; st.rerun()
        
        idx_del = st.selectbox("Apagar por ID:", st.session_state.actions.index, 
                               format_func=lambda i: f"ID {i}: {st.session_state.actions.loc[i, 'Jogador']} - {st.session_state.actions.loc[i, 'Ação']}")
        if st.button("Confirmar Eliminação"):
            st.session_state.actions = st.session_state.actions.drop(idx_del).reset_index(drop=True); st.rerun()
        
        if st.button("🚨 Limpar Tudo"):
            st.session_state.actions = pd.DataFrame(columns=st.session_state.actions.columns); st.rerun()

    # --- PDF GENERATOR ---
    def generate_pdf(df_filt, fig_pitch, report_title, current_sel_a):
        pdf = FPDF()
        pdf.add_page()
        if os.path.exists(fmh_logo_path): pdf.image(fmh_logo_path, x=165, y=10, w=30)
        pdf.set_font("Helvetica", "B", 18); pdf.set_y(15); pdf.cell(150, 10, report_title, ln=True)
        pdf.set_font("Helvetica", "", 10); pdf.cell(150, 6, "Faculdade de Motricidade Humana", ln=True)
        
        img_buf = io.BytesIO()
        fig_pitch.savefig(img_buf, format="png", bbox_inches='tight', dpi=150)
        pdf.image(img_buf, x=15, y=35, w=180)
        
        pdf.set_y(172)
        if current_sel_a == "Todas":
            pdf.set_font("Helvetica", "B", 10); pdf.cell(190, 8, "Legenda:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            for act, info in action_rules.items():
                r, g, b = tuple(int(info['cor'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                pdf.set_fill_color(r, g, b); pdf.rect(pdf.get_x(), pdf.get_y()+1, 3, 3, 'F')
                pdf.set_x(pdf.get_x() + 5); pdf.cell(28, 5, act)
            pdf.ln(8)

        pdf.set_font("Helvetica", "B", 11); pdf.cell(190, 8, "Tabela de Resultados:", ln=True)
        pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(230, 230, 230)
        
        has_remate = "Remate" in df_filt['Ação'].values
        h = ["Acao", "Sucesso", "Insucesso", "Total", "xG Acum."] if has_remate else ["Acao", "Sucesso", "Insucesso", "Total"]
        ws = [45, 35, 35, 35, 40] if has_remate else [55, 45, 45, 45]
        for i, text in enumerate(h): pdf.cell(ws[i], 8, text, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        s_tot, i_tot, t_tot, x_tot = 0, 0, 0, 0.0
        for act in df_filt['Ação'].unique():
            temp = df_filt[df_filt['Ação'] == act]
            s = len(temp[temp['Resultado'] == 'Sucesso']) if action_rules[act]['tem_resultado'] else 0
            f = len(temp[temp['Resultado'] == 'Insucesso']) if action_rules[act]['tem_resultado'] else 0
            s_tot += s; i_tot += f; t_tot += len(temp); x_tot += temp['xG'].sum()
            pdf.cell(ws[0], 8, act, border=1)
            pdf.cell(ws[1], 8, str(s) if action_rules[act]['tem_resultado'] else "-", border=1, align="C")
            pdf.cell(ws[2], 8, str(f) if action_rules[act]['tem_resultado'] else "-", border=1, align="C")
            pdf.cell(ws[3], 8, str(len(temp)), border=1, align="C")
            if has_remate: pdf.cell(ws[4], 8, f"{temp['xG'].sum():.2f}" if act == "Remate" else "-", border=1, align="C")
            pdf.ln()

        # LINHA TOTAL
        pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(245, 245, 245)
        pdf.cell(ws[0], 8, "TOTAL", border=1, fill=True, align="C")
        pdf.cell(ws[1], 8, str(s_tot), border=1, fill=True, align="C"); pdf.cell(ws[2], 8, str(i_tot), border=1, fill=True, align="C")
        pdf.cell(ws[3], 8, str(t_tot), border=1, fill=True, align="C")
        if has_remate: pdf.cell(ws[4], 8, f"{x_tot:.2f}", border=1, fill=True, align="C")
        pdf.ln(10)
        
        if (s_tot + i_tot) > 0:
            perc = (s_tot / (s_tot + i_tot)) * 100
            pdf.set_font("Helvetica", "B", 10); pdf.cell(190, 8, f"Percentagem de Sucesso Global: {perc:.1f}%", ln=True)
            
        return bytes(pdf.output())

    st.markdown("---")
    st.subheader("📄 Exportação")
    p_final = Pitch(pitch_type='uefa', pitch_color=c_theme['pitch'], line_color=c_theme['line'], stripe=is_strip, corner_arcs=True, goal_type='box')
    fig_f, ax_f = p_final.draw(figsize=(10, 7))
    for _, r in df_plot.iterrows():
        if r.Visualizacao == "Seta": p_final.arrows(r.x, r.y, r.end_x, r.end_y, width=1.5, headwidth=6, headlength=6, color=r.Cor, ax=ax_f)
        else: p_final.scatter(r.x, r.y, s=180, c=r.Cor, marker='o' if r.Resultado=='Sucesso' else 'X', ax=ax_f)
    
    pdf_out = generate_pdf(df_plot, fig_f, report_custom_title, sel_a)
    st.download_button("📥 Descarregar PDF", pdf_out, "relatorio_FMH.pdf", "application/pdf")
else:
    st.info("O campo está pronto. Registe ações para gerar relatórios.")
