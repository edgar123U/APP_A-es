import streamlit as st
from mplsoccer import Pitch
import matplotlib.pyplot as plt
import pandas as pd
import io
import numpy as np
from fpdf import FPDF
import os
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Relatório Tecnico-Tático FMH", layout="wide")

# --- FICHEIROS ---
fmh_logo_path = "faculdade_de_motricidade_humana_logo.jpeg"

# 2. ESTADO DA SESSÃO (PERSISTÊNCIA DE DADOS)
if 'actions' not in st.session_state:
    st.session_state.actions = pd.DataFrame(columns=[
        'Jogador', 'Ação', 'x', 'y', 'end_x', 'end_y', 'Resultado', 
        'Visualizacao', 'Cor', 'xG', 'Detalhes'
    ])
if 'temp_coords' not in st.session_state:
    st.session_state.temp_coords = None

# --- FUNÇÃO xG (TORVANEY) ---
def calculate_advanced_xg(x, y, is_header, sit_previa):
    goal_x, goal_y = 105, 34
    dist = np.sqrt((105 - x)**2 + (34 - y)**2)
    a = np.sqrt((105 - x)**2 + (34 - 3.66 - y)**2)
    b = np.sqrt((105 - x)**2 + (34 + 3.66 - y)**2)
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

# 3. CABEÇALHO DA APP
col_l, col_t = st.columns([1, 4])
with col_l:
    if os.path.exists(fmh_logo_path): st.image(fmh_logo_path, width=120)
with col_t:
    st.title("Relatório de Ações Tecnico-Táticas")

# 4. SIDEBAR - CONFIGURAÇÕES E REGISTO
st.sidebar.image(fmh_logo_path, width=100) if os.path.exists(fmh_logo_path) else None

st.sidebar.header("🎨 Estética do Campo")
p_theme = st.sidebar.selectbox("Tema:", ["Branco Total", "Grass", "Dark", "Midnight"])
is_strip = st.sidebar.checkbox("Relvado Cortado?", value=False)
is_pos = st.sidebar.checkbox("Linhas Posicionais?", value=False)
report_title = st.sidebar.text_input("Título do PDF", "Análise Técnica FMH")

themes = {
    "Branco Total": {"pitch": "white", "line": "black", "stripe": "#f2f2f2"},
    "Grass": {"pitch": "#2d5a27", "line": "white", "stripe": "#366b2f"},
    "Dark": {"pitch": "#22312b", "line": "#c7d5cc", "stripe": "#2c3e37"},
    "Midnight": {"pitch": "#1a1c2c", "line": "#94a3b8", "stripe": "#23263a"}
}
c_theme = themes[p_theme]

st.sidebar.markdown("---")
st.sidebar.header("🕹️ Registar Ação")
p_name = st.sidebar.text_input("Jogador", placeholder="Geral")
a_type = st.sidebar.selectbox("Tipo de Ação", list(action_rules.keys()))
rule = action_rules[a_type]

# Lógica condicional para Remate
is_h, sit_p = False, "Jogo Corrido"
v_mode = "Seta" if rule['seta'] else "Marca"
if a_type == 'Remate':
    v_mode = st.sidebar.radio("Estilo:", ["Marca", "Seta"], horizontal=True)
    is_h = st.sidebar.checkbox("De Cabeça?")
    sit_p = st.sidebar.selectbox("Origem:", ["Jogo Corrido", "Após Cruzamento", "Após Drible"])

res = "Sucesso"
if rule['tem_resultado']:
    res = st.sidebar.radio("Resultado", ["Sucesso", "Insucesso"], horizontal=True)

# 5. ÁREA PRINCIPAL - FILTROS E CAMPO
f1, f2 = st.columns(2)
sel_p = f1.selectbox("Filtrar Jogador:", ["Todos"] + sorted(st.session_state.actions['Jogador'].unique().tolist()))
sel_a = f2.selectbox("Filtrar Ação:", ["Todas"] + list(action_rules.keys()))

df_view = st.session_state.actions.copy()
if sel_p != "Todos": df_view = df_view[df_view['Jogador'] == sel_p]
if sel_a != "Todas": df_view = df_view[df_view['Ação'] == sel_a]

# Função para desenhar imagem PIL (para cliques)
def get_pitch_pil(df_plot):
    pitch = Pitch(pitch_type='uefa', pitch_color=c_theme['pitch'], line_color=c_theme['line'],
                  stripe=is_strip, stripe_color=c_theme['stripe'], positional=is_pos,
                  corner_arcs=True, goal_type='box')
    fig, ax = pitch.draw(figsize=(10, 6.47))
    for _, row in df_plot.iterrows():
        if row['Visualizacao'] == "Seta":
            pitch.arrows(row.x, row.y, row.end_x, row.end_y, width=1.5, headwidth=5, headlength=5, color=row.Cor, ax=ax, zorder=4)
        else:
            ms = 180 + (row['xG'] * 1800) if row['Ação'] == 'Remate' else 180
            m = 'o' if row['Resultado'] == 'Sucesso' else 'X'
            pitch.scatter(row.x, row.y, s=ms, c=row.Cor, edgecolors='gray' if p_theme=="Branco Total" else 'white', marker=m, ax=ax, zorder=3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    return Image.open(buf)

st.subheader("📍 Marcar no Campo")
pil_img = get_pitch_pil(df_view)
value = streamlit_image_coordinates(pil_img, width=800, key="pitch_click")

# Processamento do Clique
if value:
    x_m = (value['x'] / 800) * 105
    y_m = 68 - (value['y'] / 518) * 68 
    
    if v_mode == "Seta":
        if st.session_state.temp_coords is None:
            st.session_state.temp_coords = (x_m, y_m)
            st.rerun()
        else:
            xs, ys = st.session_state.temp_coords
            xg = calculate_advanced_xg(xs, ys, is_h, sit_p) if a_type == 'Remate' else 0.0
            new_row = {
                'Jogador': p_name if p_name else "Geral", 'Ação': a_type, 'x': xs, 'y': ys, 'end_x': x_m, 'end_y': y_m,
                'Resultado': res, 'Visualizacao': v_mode, 'Cor': rule['cor'] if res == "Sucesso" else "#e74c3c",
                'xG': xg, 'Detalhes': f"{sit_p}{' (Cabeça)' if is_h else ''}" if a_type == 'Remate' else "-"
            }
            st.session_state.actions = pd.concat([st.session_state.actions, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state.temp_coords = None
            st.rerun()
    else:
        xg = calculate_advanced_xg(x_m, y_m, is_h, sit_p) if a_type == 'Remate' else 0.0
        new_row = {
            'Jogador': p_name if p_name else "Geral", 'Ação': a_type, 'x': x_m, 'y': y_m, 'end_x': x_m, 'end_y': y_m,
            'Resultado': res, 'Visualizacao': v_mode, 'Cor': rule['cor'] if res == "Sucesso" else "#e74c3c",
            'xG': xg, 'Detalhes': f"{sit_p}{' (Cabeça)' if is_h else ''}" if a_type == 'Remate' else "-"
        }
        st.session_state.actions = pd.concat([st.session_state.actions, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

# 6. GESTÃO E EXPORTAÇÃO
st.markdown("---")
if not st.session_state.actions.empty:
    col_t, col_m = st.columns([2, 1])
    
    with col_t:
        st.subheader("📋 Log Detalhado")
        st.dataframe(st.session_state.actions[['Jogador', 'Ação', 'Resultado', 'xG', 'Detalhes']], use_container_width=True)

    with col_m:
        st.subheader("🗑️ Gestão")
        if st.button("Apagar Última"):
            st.session_state.actions = st.session_state.actions.iloc[:-1]; st.rerun()
        
        idx_del = st.selectbox("Apagar por ID:", st.session_state.actions.index, format_func=lambda i: f"ID {i}: {st.session_state.actions.loc[i, 'Ação']}")
        if st.button("Confirmar Eliminação"):
            st.session_state.actions = st.session_state.actions.drop(idx_del).reset_index(drop=True); st.rerun()
        
        if st.button("🚨 Limpar Tudo"):
            st.session_state.actions = pd.DataFrame(columns=st.session_state.actions.columns); st.rerun()

    # --- PDF GENERATOR ---
    def generate_pdf(df_filt, fig_p, title, current_sel_a):
        pdf = FPDF()
        pdf.add_page()
        if os.path.exists(fmh_logo_path): pdf.image(fmh_logo_path, x=165, y=10, w=30)
        pdf.set_font("Helvetica", "B", 18); pdf.set_y(15); pdf.cell(150, 10, title, ln=True)
        pdf.set_font("Helvetica", "", 10); pdf.cell(150, 6, "Faculdade de Motricidade Humana", ln=True)
        
        img_b = io.BytesIO()
        fig_p.savefig(img_b, format="png", bbox_inches='tight', dpi=150)
        pdf.image(img_b, x=15, y=35, w=180)
        
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
        s_t, i_t, t_t, x_t = 0, 0, 0, 0.0
        for act in df_filt['Ação'].unique():
            temp = df_filt[df_filt['Ação'] == act]
            s = len(temp[temp['Resultado'] == 'Sucesso']) if action_rules[act]['tem_resultado'] else 0
            f = len(temp[temp['Resultado'] == 'Insucesso']) if action_rules[act]['tem_resultado'] else 0
            s_t += s; i_t += f; t_t += len(temp); x_t += temp['xG'].sum()
            pdf.cell(ws[0], 8, act, border=1)
            pdf.cell(ws[1], 8, str(s) if action_rules[act]['tem_resultado'] else "-", border=1, align="C")
            pdf.cell(ws[2], 8, str(f) if action_rules[act]['tem_resultado'] else "-", border=1, align="C")
            pdf.cell(ws[3], 8, str(len(temp)), border=1, align="C")
            if has_remate: pdf.cell(ws[4], 8, f"{temp['xG'].sum():.2f}" if act == "Remate" else "-", border=1, align="C")
            pdf.ln()

        pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(245, 245, 245)
        pdf.cell(ws[0], 8, "TOTAL", border=1, fill=True, align="C")
        pdf.cell(ws[1], 8, str(s_t), border=1, fill=True, align="C"); pdf.cell(ws[2], 8, str(i_t), border=1, fill=True, align="C")
        pdf.cell(ws[3], 8, str(t_t), border=1, fill=True, align="C")
        if has_remate: pdf.cell(ws[4], 8, f"{x_t:.2f}", border=1, fill=True, align="C")
        pdf.ln(10)
        if (s_t + i_t) > 0:
            pdf.set_font("Helvetica", "B", 10); pdf.cell(190, 8, f"Eficacia Global: {(s_t/(s_t+i_t))*100:.1f}%", ln=True)
        return bytes(pdf.output())

    st.subheader("📄 Exportar")
    # Pitch estático para o PDF
    p_final = Pitch(pitch_type='uefa', pitch_color=c_theme['pitch'], line_color=c_theme['line'], stripe=is_strip, corner_arcs=True, goal_type='box')
    fig_f, ax_f = p_final.draw(figsize=(10, 7))
    for _, r in df_view.iterrows():
        if r.Visualizacao == "Seta": p_final.arrows(r.x, r.y, r.end_x, r.end_y, width=1.5, headwidth=5, headlength=5, color=r.Cor, ax=ax_f)
        else: p_final.scatter(r.x, r.y, s=180, c=r.Cor, marker='o' if r.Resultado=='Sucesso' else 'X', ax=ax_f)
    
    pdf_out = generate_pdf(df_view, fig_f, report_title, sel_a)
    st.download_button("📥 Descarregar PDF FMH", pdf_out, "relatorio_FMH.pdf", "application/pdf")
else:
    st.info("O campo está pronto. Use os cliques para registar ações.")
