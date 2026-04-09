import streamlit as st
from mplsoccer import Pitch
import matplotlib.pyplot as plt
import pandas as pd
import io
import numpy as np
from fpdf import FPDF
import os
from streamlit_image_coordinates import streamlit_image_coordinates

# Configuração da Página
st.set_page_config(page_title="Relatório Tecnico-Tático FMH", layout="wide")

# --- CONFIGURAÇÃO DO LOGO ---
fmh_logo_path = "faculdade_de_motricidade_humana_logo.jpeg"

# --- ESTADO DA SESSÃO ---
if 'actions' not in st.session_state:
    st.session_state.actions = pd.DataFrame(columns=[
        'Jogador', 'Ação', 'x', 'y', 'end_x', 'end_y', 'Resultado', 
        'Visualizacao', 'Cor', 'xG', 'Detalhes'
    ])
if 'temp_coords' not in st.session_state:
    st.session_state.temp_coords = None

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

# --- CABEÇALHO ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists(fmh_logo_path): st.image(fmh_logo_path, width=150)
with col_title:
    st.title("Relatório de Ações Tecnico-Táticas")

# --- SIDEBAR: CONFIGURAÇÃO ---
st.sidebar.header("🎨 Configuração")
p_theme = st.sidebar.selectbox("Tema:", ["Branco Total", "Grass", "Dark", "Midnight"])
is_strip = st.sidebar.checkbox("Relvado Cortado?", value=False)
is_pos = st.sidebar.checkbox("Linhas Posicionais?", value=False)
report_title = st.sidebar.text_input("Título do Relatório", "Análise Técnica")

themes = {
    "Branco Total": {"pitch": "white", "line": "black", "stripe": "#f2f2f2"},
    "Grass": {"pitch": "#2d5a27", "line": "white", "stripe": "#366b2f"},
    "Dark": {"pitch": "#22312b", "line": "#c7d5cc", "stripe": "#2c3e37"},
    "Midnight": {"pitch": "#1a1c2c", "line": "#94a3b8", "stripe": "#23263a"}
}
c_theme = themes[p_theme]

# --- SIDEBAR: REGISTO ---
st.sidebar.markdown("---")
st.sidebar.header("🕹️ Registar Ação")
p_name = st.sidebar.text_input("Jogador")
a_type = st.sidebar.selectbox("Tipo de Ação", list(action_rules.keys()))
rule = action_rules[a_type]

# Detalhes de Remate
is_h, sit_p = False, "Jogo Corrido"
v_mode = "Seta" if rule['seta'] else "Marca"
if a_type == 'Remate':
    v_mode = st.sidebar.radio("Estilo:", ["Marca", "Seta"], horizontal=True)
    is_h = st.sidebar.checkbox("De Cabeça?")
    sit_p = st.sidebar.selectbox("Origem:", ["Jogo Corrido", "Após Cruzamento", "Após Drible"])

res = "Sucesso"
if rule['tem_resultado']:
    res = st.sidebar.radio("Resultado", ["Sucesso", "Insucesso"], horizontal=True)

# --- ÁREA DE CLIQUE E DESENHO ---
st.subheader("📍 Clica no Campo para Marcar")
if v_mode == "Seta":
    if st.session_state.temp_coords is None:
        st.info("Clica no **INÍCIO** da ação.")
    else:
        st.warning("Agora clica no **FIM** da ação.")
else:
    st.info("Clica para marcar a posição da ação.")

# Função para desenhar o campo base e converter coordenadas
def get_pitch_image(df_to_plot):
    pitch = Pitch(pitch_type='uefa', pitch_color=c_theme['pitch'], line_color=c_theme['line'],
                  stripe=is_strip, stripe_color=c_theme['stripe'], positional=is_pos,
                  corner_arcs=True, goal_type='box')
    fig, ax = pitch.draw(figsize=(10, 7))
    for _, row in df_to_plot.iterrows():
        if row['Visualizacao'] == "Seta":
            pitch.arrows(row.x, row.y, row.end_x, row.end_y, width=2, color=row.Cor, ax=ax, alpha=0.8)
        else:
            ms = 180 + (row['xG'] * 1800) if row['Ação'] == 'Remate' else 180
            m = 'o' if row['Resultado'] == 'Sucesso' else 'X'
            pitch.scatter(row.x, row.y, s=ms, c=row.Cor, edgecolors='gray' if p_theme=="Branco Total" else 'white', marker=m, ax=ax, zorder=3)
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    return buf

# Filtros para visualização
f1, f2 = st.columns(2)
sel_p = f1.selectbox("Filtrar Jogador:", ["Todos"] + sorted(st.session_state.actions['Jogador'].unique().tolist()))
sel_a = f2.selectbox("Filtrar Ação:", ["Todas"] + list(action_rules.keys()))

df_view = st.session_state.actions.copy()
if sel_p != "Todos": df_view = df_view[df_view['Jogador'] == sel_p]
if sel_a != "Todas": df_view = df_view[df_view['Ação'] == sel_a]

# Mostrar Campo Interativo
pitch_img = get_pitch_image(df_view)
value = streamlit_image_coordinates(pitch_img, key="pitch_click")

if value:
    # Conversão de pixels para metros UEFA (Aprox. baseado no tamanho da imagem do mplsoccer)
    # Nota: Em 10x7 polegadas a 100dpi, temos cerca de 1000x700 pixels.
    # O rácio é 105m / largura_px e 68m / altura_px
    px_x, px_y = value['x'], value['y']
    
    # Estimativa de mapeamento (ajustável conforme o redimensionamento do browser)
    # O Streamlit redimensiona a imagem, por isso calculamos rácios relativos
    x_m = (px_x / 750) * 105 # 750 é a largura base aproximada no Streamlit
    y_m = 68 - (px_y / 485) * 68 # 485 é a altura base aproximada
    
    if v_mode == "Seta":
        if st.session_state.temp_coords is None:
            st.session_state.temp_coords = (x_m, y_m)
            st.rerun()
        else:
            x_start, y_start = st.session_state.temp_coords
            x_end, y_end = x_m, y_m
            
            # Guardar Ação
            xg_val = calculate_advanced_xg(x_start, y_start, is_h, sit_p) if a_type == 'Remate' else 0.0
            new_row = {
                'Jogador': p_name if p_name else "Geral", 'Ação': a_type, 
                'x': x_start, 'y': y_start, 'end_x': x_end, 'end_y': y_end,
                'Resultado': res, 'Visualizacao': v_mode, 
                'Cor': rule['cor'] if res == "Sucesso" else "#e74c3c",
                'xG': xg_val, 'Detalhes': f"{sit_p}{' (Cabeça)' if is_h else ''}" if a_type == 'Remate' else "-"
            }
            st.session_state.actions = pd.concat([st.session_state.actions, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state.temp_coords = None
            st.rerun()
    else:
        # Guardar Ação de Ponto
        xg_val = calculate_advanced_xg(x_m, y_m, is_h, sit_p) if a_type == 'Remate' else 0.0
        new_row = {
            'Jogador': p_name if p_name else "Geral", 'Ação': a_type, 
            'x': x_m, 'y': y_m, 'end_x': x_m, 'end_y': y_m,
            'Resultado': res, 'Visualizacao': v_mode, 
            'Cor': rule['cor'] if res == "Sucesso" else "#e74c3c",
            'xG': xg_val, 'Detalhes': f"{sit_p}{' (Cabeça)' if is_h else ''}" if a_type == 'Remate' else "-"
        }
        st.session_state.actions = pd.concat([st.session_state.actions, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

# --- EXPORTAÇÃO E TABELAS ---
if not st.session_state.actions.empty:
    st.markdown("---")
    def generate_pdf(df_filt, fig_pitch, title):
        pdf = FPDF()
        pdf.add_page()
        if os.path.exists(fmh_logo_path): pdf.image(fmh_logo_path, x=165, y=10, w=30)
        pdf.set_font("Helvetica", "B", 18); pdf.set_y(15)
        pdf.cell(150, 10, title, ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(150, 6, "Faculdade de Motricidade Humana", ln=True)
        
        img_buf = io.BytesIO()
        fig_pitch.savefig(img_buf, format="png", bbox_inches='tight', dpi=150)
        pdf.image(img_buf, x=15, y=45, w=180)
        
        # Legenda e Tabela
        pdf.set_y(172)
        if sel_a == "Todas":
            pdf.set_font("Helvetica", "B", 10); pdf.cell(190, 8, "Legenda:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            for act, info in action_rules.items():
                pdf.cell(30, 5, act)
            pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10); pdf.cell(190, 8, "Resultados:", ln=True)
        pdf.set_font("Helvetica", "B", 8); pdf.set_fill_color(230, 230, 230)
        headers = ["Acao", "Sucesso", "Insucesso", "Total", "xG Acum."]
        ws = [45, 35, 35, 35, 40]
        for i, h in enumerate(headers): pdf.cell(ws[i], 7, h, border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        s_t, i_t, t_t, x_t = 0, 0, 0, 0.0
        for act in df_filt['Ação'].unique():
            temp = df_filt[df_filt['Ação'] == act]
            s = len(temp[temp['Resultado'] == 'Sucesso']) if action_rules[act]['tem_resultado'] else 0
            f = len(temp[temp['Resultado'] == 'Insucesso']) if action_rules[act]['tem_resultado'] else 0
            xg = temp['xG'].sum()
            pdf.cell(ws[0], 7, act, border=1)
            pdf.cell(ws[1], 7, str(s), border=1)
            pdf.cell(ws[2], 7, str(f), border=1)
            pdf.cell(ws[3], 7, str(s+f), border=1)
            pdf.cell(ws[4], 7, f"{xg:.2f}", border=1)
            pdf.ln()
            s_t += s; i_t += f; t_t += (s+f); x_t += xg
        
        # TOTAL
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(ws[0], 7, "TOTAL", border=1, fill=True)
        pdf.cell(ws[1], 7, str(s_t), border=1, fill=True)
        pdf.cell(ws[2], 7, str(i_t), border=1, fill=True)
        pdf.cell(ws[3], 7, str(s_t+i_t), border=1, fill=True)
        pdf.cell(ws[4], 7, f"{x_t:.2f}", border=1, fill=True)
        
        if (s_t + i_t) > 0:
            pdf.ln(10); pdf.cell(190, 7, f"Eficacia Global: {(s_t/(s_t+i_t))*100:.1f}%", ln=True)
            
        return bytes(pdf.output())

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📄 Exportar")
        # Gerar figura final para o PDF (sem ser a imagem clicável)
        pitch_final = Pitch(pitch_type='uefa', pitch_color=c_theme['pitch'], line_color=c_theme['line'], stripe=is_strip, corner_arcs=True, goal_type='box')
        fig_f, ax_f = pitch_final.draw(figsize=(10, 7))
        for _, row in df_view.iterrows():
            if row['Visualizacao'] == "Seta": pitch_final.arrows(row.x, row.y, row.end_x, row.end_y, width=2, color=row.Cor, ax=ax_f)
            else: pitch_final.scatter(row.x, row.y, s=180, c=row.Cor, marker='o' if row['Resultado']=='Sucesso' else 'X', ax=ax_f)
        
        pdf_bytes = generate_pdf(df_view, fig_f, report_title)
        st.download_button("📥 Descarregar PDF", pdf_bytes, "relatorio.pdf", "application/pdf")
    
    with c2:
        st.subheader("🗑️ Gestão")
        if st.button("Apagar Última"):
            st.session_state.actions = st.session_state.actions.iloc[:-1]; st.rerun()
        if st.button("🚨 Limpar Tudo"):
            st.session_state.actions = pd.DataFrame(columns=st.session_state.actions.columns); st.rerun()

    st.dataframe(st.session_state.actions[['Jogador', 'Ação', 'Resultado', 'xG', 'Detalhes']], use_container_width=True)
