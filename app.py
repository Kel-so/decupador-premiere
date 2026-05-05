import streamlit as st
import google.generativeai as genai
import json
import math
import re

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Corte Rápido - Premiere", page_icon="🎬", layout="wide")

st.title("🎬 Decupador Automático pro Premiere")
st.markdown("Joga a transcrição, escolhe os cortes e baixa a timeline pronta. Sem enrolação.")

# ==========================================
# FUNÇÕES DE APOIO (MATEMÁTICA E XML)
# ==========================================
def parse_time_to_frames(time_str, fps):
    """
    Converte HH:MM:SS:FF ou HH:MM:SS,MMM para frames totais.
    """
    time_str = time_str.strip()
    # Verifica se é formato SRT (com vírgula)
    if ',' in time_str:
        parts = time_str.replace(',', ':').split(':')
        if len(parts) == 4:
            h, m, s, ms = map(int, parts)
            frames = int((ms / 1000.0) * fps)
            return int((h * 3600 + m * 60 + s) * fps + frames)
    # Verifica se é formato de frames (com dois pontos)
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
    """
    Gera a estrutura brutal do FCP 7 XML que o Premiere ama ler.
    """
    timebase, ntsc = get_timebase_ntsc(fps)
    
    # Define resolução
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

    # Inserir os cortes de vídeo
    current_timeline_frame = 0
    for i, clip in enumerate(clips):
        start_frame = parse_time_to_frames(clip['start'], fps)
        end_frame = parse_time_to_frames(clip['end'], fps)
        duration = end_frame - start_frame
        
        # Ignora cortes negativos ou inválidos
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
        
        # O Premiere exige que o arquivo (file) seja definido no primeiro clipe
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
            xml_parts.append('                    <audio></audio>')
            xml_parts.append('                  </media>')
            xml_parts.append('                </file>')
        else:
            xml_parts.append('                <file id="file-1"/>')
            
        xml_parts.append('              </clipitem>')
        current_timeline_frame += duration

    xml_parts.append('            </track>')
    xml_parts.append('          </video>')
    
    # Adicionando uma track de áudio linkada
    xml_parts.append('          <audio>')
    xml_parts.append('            <format>')
    xml_parts.append('              <samplecharacteristics>')
    xml_parts.append('                <depth>16</depth>')
    xml_parts.append('                <samplerate>48000</samplerate>')
    xml_parts.append('              </samplecharacteristics>')
    xml_parts.append('            </format>')
    xml_parts.append('            <track>')
    
    current_timeline_frame = 0
    for i, clip in enumerate(clips):
        start_frame = parse_time_to_frames(clip['start'], fps)
        end_frame = parse_time_to_frames(clip['end'], fps)
        duration = end_frame - start_frame
        if duration <= 0: continue

        xml_parts.append('              <clipitem id="audio-clip-' + str(i) + '">')
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
# INTERFACE PRINCIPAL
# ==========================================

# Tenta carregar a API Key dos secrets do Streamlit
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("🚨 Ferramenta sem chave de ignição! Adicione a GEMINI_API_KEY nos Secrets do Streamlit.")
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
        st.warning("Pô, cola o texto aí antes de clicar.")
    else:
        with st.spinner("Decupando... O Gemini tá lendo e cortando os erros."):
            # Configura a IA pra cuspir um JSON exato
            model = genai.GenerativeModel('gemini-3.1-flash-lite-preview', generation_config={"response_mime_type": "application/json"})
            
            prompt = """
            Você é um editor de vídeo SÊNIOR especialista em decupagem inteligente e fast pacing. Analise a seguinte transcrição com timestamps.
            1. Identifique 3 tópicos principais discutidos e extraia os tempos (início e fim) de cada um.
            2. Faça uma "Limpeza Geral" agressiva, mantendo apenas o ouro.
            
            COMO AVALIAR O TEXTO E OS TEMPOS:
            - RELEVÂNCIA SEMÂNTICA: O conteúdo selecionado deve fazer sentido dentro do tema central do vídeo, não apenas conter palavras-chave soltas.
            - COMPLETUDE: Priorize frases inteiras ou grupos de frases adjacentes que formem um pensamento completo e fechem um raciocínio. Nunca corte o locutor no meio de um pensamento.
            - CLAREZA: Selecione apenas os trechos onde a fala é inquestionavelmente clara e direta, sem ambiguidades.
            - DURAÇÃO E RITMO: Evite fragmentos muito curtos (menores que 2 segundos), a menos que sejam frases de impacto (punchlines) extremamente diretas, enérgicas e independentes.
            - RETAKES E REDUNDÂNCIAS: Se houver duas frases ou ideias seguidas muito semelhantes (ex: o locutor errou e repetiu, ou reformulou para soar melhor), MANTENHA EXCLUSIVAMENTE A ÚLTIMA VERSÃO.
            - RESPIROS: Remova blocos de tempo inúteis e pausas longas para manter o dinamismo, respeitando as regras de Completude acima.
            
            Seu retorno DEVE ser um JSON estrito neste exato formato:
            {
                "topico_1": {"title": "Título do Tópico", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]},
                "topico_2": {"title": "Título do Tópico", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]},
                "topico_3": {"title": "Título do Tópico", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]},
                "limpeza_geral": {"title": "Apenas Cortes e Correções (Vídeo Completo Limpo)", "clips": [{"start": "00:00:00:00", "end": "00:00:10:00"}]}
            }
            IMPORTANTE: Copie EXATAMENTE o formato do timestamp da transcrição original (ex: 00:01:23:15 ou 00:01:23,500) para os campos "start" e "end".
            
            Transcrição:
            """ + transcript_text
            
            try:
                response = model.generate_content(prompt)
                data = json.loads(response.text)
                
                # Salva os dados na sessão pra não sumir se o usuário clicar nos botões depois
                st.session_state['decupagem_data'] = data
                st.success("Análise concluída com sucesso!")
            except Exception as e:
                st.error(f"Erro ao falar com a IA: {e}")

# ==========================================
# GERAÇÃO DO XML
# ==========================================
if 'decupagem_data' in st.session_state:
    st.markdown("### Escolha o que você quer exportar:")
    data = st.session_state['decupagem_data']
    
    # Cria abas para organizar visualmente
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
                
                # Gera o XML escondido na memória
                xml_string = generate_fcp_xml(info['clips'], fps_choice, format_choice, video_filename)
                
                # Botão de download
                st.download_button(
                    label=f"⬇️ Baixar XML: {info['title']}",
                    data=xml_string,
                    file_name=f"timeline_{key}.xml",
                    mime="text/xml",
                    type="primary"
                )
