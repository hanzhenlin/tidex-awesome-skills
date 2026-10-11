"""Real service boundaries, never proportional text timing or silent correction."""
import math
import re


def normalize(text):
    return ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text)).lower()


def actual_cues(result, expected=None, max_chars=16):
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError('字幕行长必须为正整数')
    utterances = result.get('result', {}).get('utterances', [])
    if not utterances:
        raise ValueError('ASR未返回实际语音时间戳；不能猜测字幕时间')
    cues = []
    transcript = ''
    previous = 0.0
    granularities = set()
    for utterance in utterances:
        transcript += utterance.get('text', '')
        words = utterance.get('words')
        if words and normalize(''.join(w.get('text', '') for w in words)) != normalize(utterance.get('text', '')):
            raise ValueError('ASR词级与句级文本不一致；需实际审听')
        tokens = words if words else [utterance]
        granularity = 'word' if words else 'utterance'
        granularities.add(granularity)
        current = ''
        begin = end = None
        for item in tokens:
            try:
                start, stop = float(item['start_time'])/1000, float(item['end_time'])/1000
                text = item['text'].strip()
            except (KeyError, TypeError, ValueError):
                raise ValueError('ASR时间戳格式无效') from None
            if not text or not math.isfinite(start) or not math.isfinite(stop) or start < previous or stop <= start:
                raise ValueError('ASR时间戳为空、逆序或无效；需实际审听')
            if current and (len(current)+len(text)>max_chars or start-end > .38):
                cues.append(dict(start=begin, end=end, text=current))
                current = ''
            if not current:
                begin = start
            current += text
            end = stop
            previous = stop
        if current:
            cues.append(dict(start=begin, end=end, text=current))
    recognized = normalize(transcript)
    if not recognized:
        raise ValueError('ASR文本为空')
    if expected is not None and recognized != normalize(expected):
        raise ValueError('ASR文本与批准台词不一致；已保留结果，请审听并核对，禁止静默改字幕')
    return cues, '+'.join(sorted(granularities))


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def srt(cues):
    return '\n\n'.join(f'{i}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c["text"]}'
                       for i, c in enumerate(cues, 1)) + '\n'
