def generate_fcp_xml(clips, fps, format_type, video_name):
    """
    Gera a estrutura FCP 7 XML com suporte a 2 canais de áudio (Stereo).
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

    # Track de Vídeo
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
            # Declarando 2 canais de áudio no arquivo de origem
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
    
    # Tracks de Áudio (Stereo - 2 Tracks)
    xml_parts.append('          <audio>')
    xml_parts.append('            <format>')
    xml_parts.append('              <samplecharacteristics>')
    xml_parts.append('                <depth>16</depth>')
    xml_parts.append('                <samplerate>48000</samplerate>')
    xml_parts.append('              </samplecharacteristics>')
    xml_parts.append('            </format>')
    
    # Cria Track 1 e Track 2
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
            # Vincula cada track ao respectivo canal (1 ou 2) do arquivo
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
