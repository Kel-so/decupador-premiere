import streamlit as st
import google.generativeai as genai
import json
import math
import re
import os
from datetime import datetime

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Corte Rápido - Premiere", page_icon="🎬", layout="wide")

# ==========================================
# SISTEMA DE BANCO DE DADOS LOCAL (CONTADOR)
# ==========================================
ARQUIVO_USO = "uso_diario.json"

def carregar_uso():
    hoje = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(ARQUIVO_USO):
        try:
            with open(ARQUIVO_USO, "r") as f:
                dados = json.load(f)
                if dados.get("data") == hoje:
                    return dados
        except:
            pass
    return {"data": hoje, "gemini-3.1-flash-lite-preview": 0}

def salvar_uso(dados):
    with open(ARQUIVO_USO, "w") as f:
        json.dump(dados, f)

uso_atual = carregar_uso()

# ==========================================
# SIDEBAR: PAINEL DE CONTROLE
# ==========================================
st.sidebar.title("⚙️ Painel de Controle")
st.sidebar.subheader("📊 Consumo Diário")
st.sidebar.caption(f"Data: {uso_atual['data']}")
st.sidebar.text(f"Lite (Prod): {uso_atual['gemini-3.1-flash-lite-preview']} / 500")

# ==========================================
# O RESTO DO CÓDIGO
# ==========================================
st.title("🎬 Decupador Automático pro Premiere")
st.markdown("Joga a transcrição, faz a limpeza geral e baixa a timeline pronta.")

def extract_clips_from_transcript(text):
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
            clips.append({"id": i + 1, "start": start_time, "end": end_time, "text": spoken_text})
    return clips

def parse_time_to_frames(time_str, fps):
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

modelo_api_str = "gemini-3.1-flash-lite-preview"

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
        parsed_clips = extract_clips_from_transcript(transcript_text)
        
        if not parsed_clips:
            st.error("Não consegui encontrar as marcações de tempo. Tem certeza que copiou do Premiere direito?")
        else:
            with st.spinner("Decupando com Gemini 3.1 Flash Lite..."):
                model = genai.GenerativeModel(modelo_api_str, generation_config={"response_mime_type": "application/json"})
                
                numbered_transcript = ""
                for c in parsed_clips:
                    numbered_transcript += f"ID: {c['id']} | Texto: {c['text']}\n"
                
                prompt = f"""
                Você é um editor de vídeo SÊNIOR especialista em decupagem inteligente e fast pacing. 
                
                CRITÉRIOS DE SELEÇÃO E CORTE (REGRAS ESTRITAS):
                1. RELEVÂNCIA SEMÂNTICA: O conteúdo selecionado deve fazer sentido dentro do tema central.
                2. COMPLETUDE: Priorize frases inteiras. Nunca corte o locutor no meio de um pensamento.
                3. CLAREZA: Selecione apenas os trechos onde a fala é inquestionavelmente clara.
                4. DURAÇÃO E RITMO: Evite fragmentos muito curtos, a menos que sejam frases de impacto.
                5. RETAKES: Se houver duas frases seguidas semelhantes (o locutor repetiu para soar melhor), MANTENHA EXCLUSIVAMENTE O ID DA ÚLTIMA VERSÃO.
                6. RESPIROS: Remova IDs que contenham apenas pausas, gagueiras ou erros.
                
                Sua tarefa dupla:
                1. Fazer a "Limpeza Geral" do vídeo inteiro aplicando as regras acima (isto é obrigatório e será a timeline principal).
                2. Listar os tópicos/assuntos discutidos durante o vídeo, agrupando os IDs que pertencem a cada um deles, para o caso de eu querer baixar apenas um pedaço isolado depois.
                
                Seu retorno DEVE ser EXATAMENTE um JSON, contendo os arrays de números inteiros (os IDs). Não invente IDs!
                
                Exemplo de formato exigido:
                {{
                    "limpeza_geral": {{"title": "Limpeza Geral Completa", "ids": [1, 2, 4, 5, 8, 9, 10, 12, 15]}},
                    "topicos": [
                        {{"title": "Introdução aos Conceitos", "ids": [1, 2, 4, 5]}},
                        {{"title": "Aplicações Práticas", "ids": [8, 9, 10]}},
                        {{"title": "Encerramento e Revisão", "ids": [12, 15]}}
                    ]
                }}
                
                Transcrição Numerada:
                {numbered_transcript}
                """
                
                try:
                    response = model.generate_content(prompt)
                    data = json.loads(response.text)
                    
                    st.session_state['decupagem_data'] = data
                    st.session_state['parsed_clips'] = parsed_clips
                    
                    uso_atual[modelo_api_str] += 1
                    salvar_uso(uso_atual)
                    
                    st.success("Análise cirúrgica concluída com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao falar com a IA: {e}")

# ==========================================
# GERAÇÃO DO XML
# ==========================================
if 'decupagem_data' in st.session_state and 'parsed_clips' in st.session_state:
    st.markdown("---")
    data = st.session_state['decupagem_data']
    parsed_clips = st.session_state['parsed_clips']
    
    # 1. ÁREA PRINCIPAL: LIMPEZA GERAL
    if "limpeza_geral" in data:
        st.subheader("🧹 Limpeza Geral (Vídeo Completo)")
        info_limpeza = data["limpeza_geral"]
        st.write(f"Total de cortes mantidos no vídeo: **{len(info_limpeza['ids'])}**")
        
        final_clips_limpeza = [c for c in parsed_clips if c['id'] in info_limpeza['ids']]
        
        if final_clips_limpeza:
            xml_limpeza = generate_fcp_xml(final_clips_limpeza, fps_choice, format_choice, video_filename)
            st.download_button(
                label="⬇️ Baixar XML: Limpeza Geral",
                data=xml_limpeza,
                file_name="timeline_limpeza_geral.xml",
                mime="text/xml",
                type="primary"
            )
            
    # 2. ÁREA SECUNDÁRIA: TÓPICOS ESPECÍFICOS (Opcional)
    if "topicos" in data and len(data["topicos"]) > 0:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("🎯 Isolar Assunto Específico (Opcional)")
        st.write("Opcional: A IA detectou os seguintes assuntos no material. Escolha um se quiser exportar apenas esse bloco.")
        
        titulos_topicos = [t["title"] for t in data["topicos"]]
        topico_selecionado = st.selectbox("Selecione o tópico que deseja isolar:", ["Nenhum"] + titulos_topicos)
        
        if topico_selecionado != "Nenhum":
            info_topico = next(t for t in data["topicos"] if t["title"] == topico_selecionado)
            st.write(f"Cortes encontrados neste assunto: **{len(info_topico['ids'])}**")
            
            final_clips_topico = [c for c in parsed_clips if c['id'] in info_topico['ids']]
            if final_clips_topico:
                xml_topico = generate_fcp_xml(final_clips_topico, fps_choice, format_choice, video_filename)
                
                nome_arquivo = info_topico['title'].lower().replace(" ", "_").replace("/", "_")
                
                st.download_button(
                    label=f"⬇️ Baixar XML: {info_topico['title']}",
                    data=xml_topico,
                    file_name=f"timeline_{nome_arquivo}.xml",
                    mime="text/xml",
                    type="secondary"
                )
