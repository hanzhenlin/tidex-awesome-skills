"""Measured audio caches and gated episode integration; no automatic retiming."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave

from . import client, credentials, timing

CLIENT_VERSION = '1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def video_modules():
    sibling = Path(__file__).resolve().parents[3] / 'handraw-video-producer' / 'lib'
    if not (sibling / 'production_stage.py').is_file():
        raise RuntimeError('视频配音需要同包handraw-video-producer；独立语音功能不依赖它')
    sys.path.insert(0, str(sibling))
    import production_stage, output_backends
    return production_stage, output_backends


def gate_paths(*paths):
    for path in paths:
        absolute = Path(path).resolve()
        for parent in (absolute, *absolute.parents):
            if (parent / 'episode.json').is_file() or (parent / 'production.json').is_file():
                stage, backends = video_modules()
                stage.require(parent)
                meta = read(parent / 'episode.json')
                backends.require_plan(parent, meta.get('output_target', 'web'))
                break


def executable(name):
    override = __import__('os').environ.get('HVP_'+name.upper())
    result = override or shutil.which(name)
    if not result or not Path(result).is_file():
        raise RuntimeError('缺少'+name+'；请安装到PATH或配置HVP_'+name.upper())
    return result


def decode(audio, wav):
    result = subprocess.run([executable('ffmpeg'), '-y', '-v', 'error', '-i', str(audio),
                             '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', str(wav)],
                            capture_output=True)
    if result.returncode:
        raise RuntimeError('配音文件解码失败；保留音频供检查，不输出服务响应或凭据')


def measure(wav):
    with wave.open(str(wav), 'rb') as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2 or stream.getframerate() != 24000:
            raise ValueError('配音缓存必须为24000Hz单声道16位PCM')
        duration = stream.getnframes()/stream.getframerate()
        if not duration or duration > 7200:
            raise ValueError('音频为空或超过两小时识别范围')
        return duration


def produce(text, output_dir, speaker, direction='', rate=0, account=None, max_chars=16):
    gate_paths(output_dir)
    executable('ffmpeg')  # Fail before a paid request when decode runtime is missing.
    account = account or credentials.resolve()
    request = client.tts_request(text, speaker, rate, direction)
    fingerprint = hashlib.sha256(json.dumps(dict(version=CLIENT_VERSION, request=request,
                    resource=account['tts_resource']), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    folder = Path(output_dir) / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    credentials.atomic_json(folder / 'request.json', request)  # Body only; never auth headers.
    mp3, wav, receipt = folder/'voice.mp3', folder/'voice.wav', folder/'audio.json'
    if receipt.is_file():
        info = read(receipt)
        if not mp3.is_file() or info.get('sha256') != digest(mp3):
            raise ValueError('配音缓存损坏；不会自动重新付费生成，请明确删除损坏版本后重试')
    else:
        if mp3.exists():
            raise ValueError('音频缓存缺少完整回执，请审查后移走；不会自动覆盖或重复计费')
        client.synthesize(request, mp3, account)
        credentials.atomic_json(receipt, dict(sha256=digest(mp3), request_fingerprint=fingerprint))
    # Recreate decoded PCM from verified MP3, without a new service request.
    decode(mp3, wav)
    duration = measure(wav)
    asr_key = hashlib.sha256((digest(wav)+account['asr_resource']+CLIENT_VERSION).encode()).hexdigest()[:24]
    asr_file = folder/('asr-'+asr_key+'.json')
    if not asr_file.exists():
        credentials.atomic_json(asr_file, client.recognize(wav, account))
    cues, granularity = timing.actual_cues(read(asr_file), text, max_chars)
    if any(c['end'] > duration+.001 for c in cues):
        raise ValueError('ASR边界超出实测音频；需要审听，不截断或猜测')
    info = dict(duration=duration, duration_source='PCM sample count', segments=cues,
                boundary_source='Volcano ASR actual '+granularity+' timestamps', speaker=speaker,
                request_fingerprint=fingerprint, audio_sha256=digest(wav))
    credentials.atomic_json(folder/'timing.json', info)
    (folder/'subtitles.srt').write_text(timing.srt(cues), encoding='utf-8')
    return wav, info


def asr(audio, output_dir, expected=None, max_chars=16):
    gate_paths(audio, output_dir)
    executable('ffmpeg')
    account = credentials.resolve()
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    # Avoid overwriting the input if it happens to be named recognition.wav.
    fingerprint = digest(audio)[:24]
    wav = folder/('recognition-'+fingerprint+'.wav')
    if Path(audio).resolve() == wav.resolve():
        raise ValueError('识别缓存不能与输入文件相同')
    decode(audio, wav)
    duration = measure(wav)
    path = folder/('asr-'+hashlib.sha256((digest(wav)+account['asr_resource']).encode()).hexdigest()[:24]+'.json')
    if not path.exists():
        credentials.atomic_json(path, client.recognize(wav, account))
    cues, granularity = timing.actual_cues(read(path), expected, max_chars)
    if any(c['end'] > duration+.001 for c in cues):
        raise ValueError('ASR边界超出实测音频；需要审听')
    info = dict(duration=duration, duration_source='PCM sample count', segments=cues,
                boundary_source='Volcano ASR actual '+granularity+' timestamps')
    credentials.atomic_json(folder/'timing.json', info)
    (folder/'subtitles.srt').write_text(timing.srt(cues), encoding='utf-8')
    return info


def _silence(stream, samples):
    while samples:
        chunk = min(samples, 24000)
        stream.writeframesraw(b'\0\0' * chunk)
        samples -= chunk


def episode(ep):
    ep = Path(ep).resolve()
    stage, backends = video_modules()
    stage.require(ep)
    meta, board = read(ep/'episode.json'), read(ep/'composition.json')
    backends.require_plan(ep, meta.get('output_target', 'web'))
    voice = meta.get('narration', {})
    if voice.get('provider') not in ('volc', 'volc-tts', 'volcano'):
        raise ValueError('本入口只使用用户选定的火山引擎，不修改配音服务')
    if voice.get('path'):
        raise ValueError('工程已有旁白绑定；请明确管理版本后再生成，不覆盖原旁白')
    account = credentials.resolve()
    options = voice.get('volc', {})
    speaker = options.get('speaker') or voice.get('voice') or account.get('speaker')
    if not isinstance(speaker, str) or not speaker:
        raise ValueError('缺少控制台确认的音色ID；填写narration.volc.speaker或保存默认speaker')
    account = {**account, **{k: options[k] for k in ('tts_resource', 'asr_resource') if k in options}}
    fps = meta.get('fps')
    count = board.get('duration_frames')
    if type(fps) is not int or fps < 1 or type(count) is not int or count < 1 or board.get('version') != 2:
        raise ValueError('配音前需要完整composition-v2帧时间线')
    shots = board.get('shots', [])
    anchors = ''.join(s.get('voice_anchor', '') for s in shots)
    if not anchors or timing.normalize(anchors) != timing.normalize((ep/'script.txt').read_text(encoding='utf-8-sig')):
        raise ValueError('逐镜voice_anchor与script.txt不一致；请先核对已批准台词')
    last = 0
    for shot in shots:
        start, end = shot.get('start_frame'), shot.get('end_frame')
        if type(start) is not int or type(end) is not int or not last <= start < end <= count:
            raise ValueError('镜头帧范围无效或重叠')
        last = end
        cfg = shot.get('voice', {})
        pause = cfg.get('pause_after', options.get('pause_after', .4))
        if type(pause) not in (int, float) or not math.isfinite(pause) or pause < 0:
            raise ValueError('pause_after必须为非负秒数')
        client.tts_request(shot.get('voice_anchor') or '静音', speaker, cfg.get('speech_rate', options.get('speech_rate', 0)),
                           cfg.get('direction', voice.get('direction', '')))
    folder = ep/'work/volc-voice'
    measurements, cues, errors = [], [], []
    # Gate checks precede all paid requests, including cache misses on a resumed run.
    for shot in shots:
        text = shot.get('voice_anchor', '').strip()
        if not text:
            continue
        cfg = shot.get('voice', {})
        wav, info = produce(text, folder/'clips', speaker, cfg.get('direction', voice.get('direction', '')),
                            cfg.get('speech_rate', options.get('speech_rate', 0)), account,
                            options.get('subtitle_max_chars', 16))
        pause = cfg.get('pause_after', options.get('pause_after', .4))
        minimum_frames = math.ceil((info['duration']+pause)*fps)
        available = shot['end_frame']-shot['start_frame']
        measurements.append(dict(shot_id=shot['id'], wav=wav.relative_to(ep).as_posix(),
                            duration=info['duration'], required_frames=minimum_frames, available_frames=available,
                            boundary_source=info['boundary_source'], start_frame=shot['start_frame']))
        if minimum_frames > available:
            errors.append(shot['id']+'配音与停顿需要'+str(minimum_frames)+'帧，镜头仅'+str(available)+'帧')
        offset = shot['start_frame']/fps
        cues.extend(dict(start=c['start']+offset, end=c['end']+offset, text=c['text']) for c in info['segments'])
    credentials.atomic_json(folder/'measurements.json', dict(clips=measurements, errors=errors,
                            next_step='调整镜头时间并复核动作与素材范围后重新hvp tts；语音缓存可复用' if errors else '审听实际声音和字幕'))
    if errors:
        raise ValueError('; '.join(errors)+'；见work/volc-voice/measurements.json，未修改时间线或绑定旁白')
    stage.require(ep)
    # Exact frame schedule, original speech speed, explicit silence in remaining slots.
    target = ep/('assets/audio/volc-narration-'+hashlib.sha256(json.dumps(measurements, sort_keys=True).encode()).hexdigest()[:16]+'.wav')
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix('.partial.wav')
    cursor = 0
    try:
        with wave.open(str(partial), 'wb') as output:
            output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            for item in measurements:
                start = round(item['start_frame']*24000/fps)
                _silence(output, start-cursor)
                with wave.open(str(ep/item['wav']), 'rb') as source:
                    output.writeframesraw(source.readframes(source.getnframes()))
                    cursor = start+source.getnframes()
            _silence(output, round(count*24000/fps)-cursor)
        partial.replace(target)
    finally:
        if partial.exists():
            partial.unlink()
    info = dict(duration=measure(target), duration_source='PCM sample count', segments=cues,
                boundary_source='Volcano ASR actual boundaries; per-clip granularity in clips',
                voice=speaker, clips=measurements, audio_sha256=digest(target), listening_review='pending')
    credentials.atomic_json(folder/'timing.json', info)
    (folder/'subtitles.srt').write_text(timing.srt(cues), encoding='utf-8')
    # Do not change approved directions, voice id, shot lengths or subtitle policy.
    board['subtitle_cues'] = [dict(start_frame=round(c['start']*fps),
                             end_frame=max(round(c['start']*fps)+1, round(c['end']*fps)), text=c['text']) for c in cues]
    voice.update(path=target.relative_to(ep).as_posix(), actual_voice=speaker)
    credentials.atomic_json(ep/'composition.json', board)
    credentials.atomic_json(ep/'episode.json', meta)
    credentials.atomic_json(ep/'work/timing.json', info)
    stage.require(ep)
    return info
