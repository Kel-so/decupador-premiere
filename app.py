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

# ==========================================
# FUNÇÕES DE APOIO (PROCESSAMENTO E XML)
# ==========================================

def extract_clips_from_transcript(text):
    """
    Lê o TXT ou SRT, extrai os tempos exatos e dá um ID pra cada fala.
    """
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[:.,]\d{2,3})\s*(?:-|-->)\s*(\d{2}:\d{2}:\d{2}[:.,]\d{2,3})')
    clips = []
    matches = list(pattern.finditer(text))
    
    for i, match in enumerate(matches):
        start_time = match.group(1)
        end_time = match.group(2)
        
        text_start_idx = match.end()
        text_end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        spoken_text = text[text_start_idx:text_end_idx].strip()
        spoken_text = re.sub(r'^Unknown\n?', '', spoken_text, flags=re.IGNORECASE).strip()
        spoken_text = re.sub(r'^\d+\n?', '', spoken_text).strip()
        
        if spoken_text:
            clips.append({
                "id": i + 1,
                "start": start_time,
                "end": end_time,
                "text": spoken_text
            })
    return clips

def parse_time_to_frames(time_str, fps):
    """
    Converte HH:MM:SS:FF ou HH:MM:SS,MMM para frames de forma robusta.
    """
    time_str = str(time_str).strip()
    match = re.search(r'(\d+):(\d+):(\d+)[:,\.](\d+)', time_str)
    if match:
        h, m, s, f_or_ms = map(int, [match.group(1), match.group(2), match.group(3), match.group(4)])
        if ',' in time_str or '.' in time_str:
            frames = int((f_or_ms / 1000.0) * fps)
        else:
            frames = f_or_ms
        return int((h * 3600 + m * 60 + s) * fps + frames)
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
    
    # Gerando mapeamento EXATO das tracks de áudio para o Premiere ler o Stereo limpo
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
            # O mapeamento do track (Canal 1 para Track 1, Canal 2 para Track 2)
            xml_parts.append('                <sourcetrack>')
            xml_parts.append('                  <mediatype>audio</mediatype>')
            xml_parts.append(f'                  <trackindex>{track_idx + 1}</trackindex>')
            xml_parts.append('                </sourcetrack>')
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
        # Extrai os clipes via Python primeiro pra não depender da memória da IA
        parsed_clips = extract_clips_from_transcript(transcript_text)
        
        if not parsed_clips:
            st.error("Não consegui encontrar as marcações de tempo. Tem certeza que copiou do Premiere direito?")
        else:
            with st.spinner("Decupando... O Python separou os tempos, a IA tá escolhendo os cortes."):
                model = genai.GenerativeModel('gemini-3.0-flash', generation_config={"response_mime_type": "application/json"})
                
                # Prepara o texto enumerado pra IA focar SÓ no conteúdo
                numbered_transcript = ""
                for c in parsed_clips:
                    numbered_transcript += f"ID: {c['id']} | Texto: {c['text']}\n"
                
                prompt = f"""
                Você é um editor de vídeo SÊNIOR com foco em fast pacing (corte seco). 
                Sua missão é limpar a transcrição abaixo e separar os tópicos.
                
                COMO AVALIAR OS TEXTOS (REGRAS ESTRITAS):
                1. RETAKES: Se o locutor errar ou hesitar e depois repetir a frase melhor no ID seguinte, DESCARTE os IDs ruins. Mantenha APENAS o ID da tentativa boa.
                2. GAGUEIRAS E RESPIROS VAZIOS: Descarte IDs que só contêm coisas como "éé", "hmm" ou frases incompletas sem sentido.
                3. Identifique 3 tópicos principais do vídeo, além da "Limpeza Geral".
                
                IMPORTANTE: Eu não quero que você copie o texto nem invente tempos.
                Seu retorno DEVE ser EXATAMENTE um JSON, contendo APENAS os arrays de números inteiros (os IDs) que DEVEM FICAR na timeline final.
                
                Exemplo de formato exigido:
                {{
                    "topico_1": {{"title": "Título do Tópico 1", "ids": [1, 2, 5, 6]}},
                    "topico_2": {{"title": "Título do Tópico 2", "ids": [10, 11, 12]}},
                    "topico_3": {{"title": "Título do Tópico 3", "ids": [20, 21]}},
                    "limpeza_geral": {{"title": "Limpeza Geral (Vídeo Limpo)", "ids": [1, 2, 4, 5, 8, 9, 10, 12]}}
                }}
                
                Transcrição Numerada:
                {numbered_transcript}
                """
                
                try:
                    response = model.generate_content(prompt)
                    data = json.loads(response.text)
                    
                    # Salva os dados processados e os clipes originais
                    st.session_state['decupagem_data'] = data
                    st.session_state['parsed_clips'] = parsed_clips
                    st.success("Análise cirúrgica concluída com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao falar com a IA: {e}")

# ==========================================
# GERAÇÃO DO XML
# ==========================================
if 'decupagem_data' in st.session_state and 'parsed_clips' in st.session_state:
    st.markdown("### Escolha o que você quer exportar:")
    data = st.session_state['decupagem_data']
    parsed_clips = st.session_state['parsed_clips']
    
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
            if info and "ids" in info:
                st.subheader(info['title'])
                st.write(f"Total de cortes gerados: **{len(info['ids'])}**")
                
                # Reconstrói a lista de clipes com os tempos EXATOS que o Python guardou
                final_clips = []
                for clip_id in info['ids']:
                    original_clip = next((c for c in parsed_clips if c['id'] == clip_id), None)
                    if original_clip:
                        final_clips.append(original_clip)
                
                if final_clips:
                    xml_string = generate_fcp_xml(final_clips, fps_choice, format_choice, video_filename)
                    
                    st.download_button(
                        label=f"⬇️ Baixar XML: {info['title']}",
                        data=xml_string,
                        file_name=f"timeline_{key}.xml",
                        mime="text/xml",
                        type="primary"
                    )
                else:
                    st.warning("Nenhum clipe foi selecionado para esse tópico.")
