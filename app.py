import streamlit as st
import google.generativeai as genai
import json
import math
import re

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Corte Rápido - Premiere", page_icon="🎬", layout="wide")

# ==========================================
# SISTEMA DE SEGURANÇA (SENHA)
# ==========================================
senha_digitada = st.sidebar.text_input("🔑 Senha de Acesso", type="password")

try:
    senha_correta = st.secrets["APP_PASSWORD"]
except:
    # Se você esquecer de configurar no site, ele trava o acesso
    st.error("Erro interno: A senha do aplicativo não foi configurada nos Secrets do Streamlit.")
    st.stop()

if senha_digitada != senha_correta:
    st.warning("Ferramenta bloqueada. Digite a senha na barra lateral para acessar o decupador.")
    st.stop()

# ==========================================
# O RESTO DO CÓDIGO SÓ RODA SE A SENHA BATER
# ==========================================
st.title("🎬 Decupador Automático pro Premiere")
st.markdown("Joga a transcrição, escolhe os cortes e baixa a timeline pronta. Sem enrolação.")

def parse_time_to_frames(time_str, fps):
    time_str = time_str.strip()
    if ',' in time_str:
        parts = time_str.replace(',', ':').split(':')
        if len(parts) == 4:
            h, m, s, ms = map(int, parts)
            frames = int((ms / 1000.0) * fps)
            return int((h * 3600 + m * 60 + s) * fps + frames)
    elif time_str.count(':') == 3:
        parts = time_str.split(':')
        h, m, s, f = map(int, parts)
        return int((h * 3600 + m * 60 + s) * fps + f)
    return 0

def get_timebase_ntsc(fps):
    if fps == 23.976: return 24, "TRUE"
    if fps == 29.97: return 30, "TRUE"
    if fps == 59.94: return 60, "TRUE"
    return int(fps), "FALSE"

def generate_fcp_xml(clips, fps, format_type, video_name):
    timebase, ntsc = get_timebase_ntsc(fps)
    
    if format_type == "Vertical (1080x1920)":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    xml_parts = []
    xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_parts.append('<!DOCTYPE xmeml>')
    xml_parts.append('<xmeml version="4">')
    xml_parts.append('  <project>')
    xml_parts.append(f'    <name>Decupagem_{video_name}</name>')
    xml_parts.append('    <children>')
    xml_parts.append('      <sequence id="sequence-1">')
    xml_parts.append(f'        <name>Timeline - {video_name}</name>')
    xml_parts.append(f'        <duration>999999</duration>')
    xml_parts.append('        <rate>')
    xml_parts.append(f'          <timebase>{timebase}</timebase>')
    xml_parts.append(f'          <ntsc>{ntsc}</ntsc>')
    xml_parts.append('        </rate>')
    xml_parts.append('        <media>')
    xml_parts.append('          <video>')
    xml_parts.append('            <format>')
    xml_parts.append('              <samplecharacteristics>')
    xml_parts.append('                <rate>')
    xml_parts.append(f'                  <timebase>{timebase}</timebase>')
    xml_parts.append(f'                  <ntsc>{ntsc}</ntsc>')
    xml_parts.append('                </rate>')
    xml_parts.append(f'                <width>{width}</width>')
    xml_parts.append(f'                <height>{height}</height>')
    xml_parts.append('                <pixelaspectratio>square</pixelaspectratio>')
    xml_parts.append('              </samplecharacteristics>')
    xml_parts.append('            </format>')
    xml_parts.append('            <track>')

    current_timeline_frame = 0
    for i, clip in enumerate(clips):
        start_frame = parse_time_to_frames(clip['start'], fps)
        end_frame = parse_time_to_frames(clip['end'], fps)
        duration = end_frame - start_frame
        
        if duration <= 0: continue

        xml_parts.append('              <clipitem id="video-clip-' + str(i) + '">')
        xml_parts.append(f'                <name>{video_name}</name>')
        xml_parts.append(f'                <duration>{duration}</duration>')
        xml_parts.append('                <rate>')
        xml_parts.append(f'                  <timebase>{timebase}</timebase>')
        xml_parts.append(f'                  <ntsc>{ntsc}</ntsc>')
        xml_parts.append('                </rate>')
        xml_parts.append(f'                <start>{current_timeline_frame}</start>')
        xml_parts.append(f'                <end>{current_timeline_frame + duration}</end>')
        xml_parts.append(f'                <in>{start_frame}</in>')
        xml_parts.append(f'                <out>{end_frame}</out>')
        
        if i == 0:
            xml_parts.append('                <file id="file-1">')
            xml_parts.append(f'                  <name>{video_name}</name>')
            xml_parts.append(f'                  <pathurl>file://localhost/{video_name}</pathurl>')
            xml_parts.append('                  <rate>')
            xml_parts.append(f'                    <timebase>{timebase}</timebase>')
            xml_parts.append(f'                    <ntsc>{ntsc}</ntsc>')
            xml_parts.append('                  </rate>')
            xml_parts.append('                  <media>')
            xml_parts.append('                    <video></video>')
            xml_parts.append('                    <audio>')
            xml_parts.append('                      <channelcount>2</channelcount>')
            xml_parts.append('                    </audio>')
            xml_parts.append('                  </media>')
            xml_parts.append('                </file>')
        else:
            xml_parts.append('                <file id="file-1"/>')
            
        xml_parts.append('              </clipitem>')
        current_timeline_frame += duration

    xml_parts.append('            </track>')
    xml_parts.append('          </video>')
    
    xml_parts.append('          <audio>')
    xml_parts.append('            <format>')
    xml_parts.append('              <samplecharacteristics>')
    xml_parts.append('                <depth>16</depth>')
    xml_parts.append('                <samplerate>48000</samplerate>')
    xml_parts.append('              </samplecharacteristics>')
    xml_parts.append('            </format>')
    
    for track_idx in range(2):
        xml_parts.append('            <track>')
        current_timeline_frame = 0
        for i, clip in enumerate(clips):
            start_frame = parse_time_to_frames(clip['start'], fps)
            end_frame = parse_time_to_frames(clip['end'], fps)
            duration = end_frame - start_frame
            if duration <= 0: continue

            xml_parts.append(f'              <clipitem id="audio-clip-{track_idx}-{i}">')
            xml_parts.append(f'                <name>{video_name}</name>')
            xml_parts.append(f'                <duration>{duration}</duration>')
            xml_parts.append('                <rate>')
            xml_parts.append(f'                  <timebase>{timebase}</timebase>')
            xml_parts.append(f'                  <ntsc>{ntsc}</ntsc>')
            xml_parts.append('                </rate>')
            xml_parts.append(f'                <start>{current_timeline_frame}</start>')
            xml_parts.append(f'                <end>{current_timeline_frame + duration}</end>')
            xml_parts.append(f'                <in>{start_frame}</in>')
            xml_parts.append(f'                <out>{end_frame}</out>')
            xml_parts.append('                <file id="file-1"/>')
            xml_parts.append('              </clipitem>')
            current_timeline_frame += duration

        xml_parts.append('            </track>')

    xml_parts.append('          </audio>')
    xml_parts.append('        </media>')
    xml_parts.append('      </sequence>')
    xml_parts.append('    </children>')
    xml_parts.append('  </project>')
    xml_parts.append('</xmeml>')
    
    return "\n".join(xml_parts)

# ==========================================
# INTERFACE PRINCIPAL E REQUISIÇÃO
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("🚨 Adicione a GEMINI_API_KEY nos Secrets do Streamlit.")
    st.stop()

col1, col2, col3 = st.columns(3)

with col1:
    fps_choice = st.selectbox("FPS do Projeto", [23.976, 24, 25, 29.97, 30, 59.94, 60], index=0)
with col2:
    format_choice = st.selectbox("Formato da Timeline", ["Horizontal (1920x1080)", "Vertical (1080x1920)"])
with col3:
    video_filename = st.text_input("Nome exato do vídeo (ex: C0094.mp4)", value="video_01.mp4")

transcript_text = st.text_area("Cole a transcrição aqui (.txt com tempo ou .srt)", height=250)

if st.button("Analisar Transcrição", type="primary"):
    if not transcript_text.strip():
        st.warning("Cole o texto da transcrição antes de clicar.")
    else:
        with st.spinner("Decupando... Analisando os tempos com a IA."):
            # Modelo atualizado conforme solicitado
            model = genai.GenerativeModel('gemini-3.1-flash-preview', generation_config={"response_mime_type": "application/json"})
            
            prompt = """
            Você é um assistente de edição de vídeo. Analise a seguinte transcrição com timestamps.
            1. Identifique 3 tópicos principais discutidos e extraia os tempos (início e fim) de cada um.
            2. Faça uma "Limpeza Geral": crie uma lista de tempos contínua, mas REMOVA todos os retakes, gagueiras, frases que o locutor errou e repetiu. Mantenha apenas os takes bons.
            
            Seu retorno DEVE ser um JSON estrito neste exato formato:
            {
                "topico_1": {"title": "Título do Tópico", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]},
                "topico_2": {"title": "Título do Tópico", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]},
                "topico_3": {"title": "Título do Tópico", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]},
                "limpeza_geral": {"title": "Apenas Cortes e Correções (Vídeo Completo Limpo)", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]}
            }
            IMPORTANTE: Copie EXATAMENTE o formato do timestamp da transcrição original para os campos "start" e "end".
            
            Transcrição:
            """ + transcript_text
            
            try:
                response = model.generate_content(prompt)
                data = json.loads(response.text)
                st.session_state['decupagem_data'] = data
                st.success("Análise concluída com sucesso!")
            except Exception as e:
                st.error(f"Erro ao falar com a IA: {e}")

if 'decupagem_data' in st.session_state:
    st.markdown("### Escolha o que você quer exportar:")
    data = st.session_state['decupagem_data']
    
    tabs = st.tabs(["🧹 Limpeza Geral", "🔥 Tópico 1", "🔥 Tópico 2", "🔥 Tópico 3"])
    
    opcoes = [
        ("limpeza_geral", tabs[0]),
        ("topico_1", tabs[1]),
        ("topico_2", tabs[2]),
        ("topico_3", tabs[3])
    ]
    
    for key, tab in opcoes:
        with tab:
            info = data.get(key)
            if info:
                st.subheader(info['title'])
                st.write(f"Total de cortes gerados: **{len(info['clips'])}**")
                
                xml_string = generate_fcp_xml(info['clips'], fps_choice, format_choice, video_filename)
                
                st.download_button(
                    label=f"⬇️ Baixar XML: {info['title']}",
                    data=xml_string,
                    file_name=f"timeline_{key}.xml",
                    mime="text/xml",
                    type="primary"
                )
