"""Official fixed HTTPS endpoints; errors never dump headers, bodies or credentials."""
import base64
import json
from pathlib import Path
import socket
import urllib.error
import urllib.request
import uuid

TTS_URL = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
ASR_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash'


def safe_code(value):
    return str(value) if str(value).isdigit() and len(str(value)) <= 10 else 'unknown'


def headers(account, resource, asr=False):
    result = {'Content-Type': 'application/json', 'X-Api-Resource-Id': resource,
              'X-Api-Request-Id': str(uuid.uuid4())}
    if account.get('api_key'):
        result['X-Api-Key'] = account['api_key']
    elif account.get('app_id') and account.get('access_token'):
        result['X-Api-App-Key' if asr else 'X-Api-App-Id'] = account['app_id']
        result['X-Api-Access-Key'] = account['access_token']
    else:
        raise ValueError('火山账户凭据不完整')
    if asr:
        result['X-Api-Sequence'] = '-1'
    return result


def tts_request(text, speaker, rate=0, direction=''):
    if not isinstance(text, str) or not text.strip() or not isinstance(speaker, str) or not speaker.strip():
        raise ValueError('配音需要非空文本和控制台确认的音色ID')
    if type(rate) is not int or not -50 <= rate <= 100:
        raise ValueError('speech_rate必须为[-50,100]整数；不是speed_ratio')
    params = dict(text=text, speaker=speaker, audio_params=dict(format='mp3', sample_rate=24000, speech_rate=rate))
    if direction:
        params['additions'] = json.dumps({'context_texts': [direction]}, ensure_ascii=False)
    return {'req_params': params}


def _open(url, body, auth, timeout, opener):
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'), headers=auth)
    try:
        return opener(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # No raw response text: even a proxy may reflect request headers.
        raise RuntimeError('火山语音HTTP错误 '+str(exc.code)+'；检查服务权限、资源和账户，不自动重试') from None
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        raise RuntimeError('火山语音网络请求失败；检查网络、代理或执行权限，不自动重试') from None


def synthesize(request, output, account, *, opener=urllib.request.urlopen, timeout=180):
    output = Path(output)
    partial = output.with_suffix(output.suffix + '.partial')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _open(TTS_URL, request, headers(account, account['tts_resource']), timeout, opener) as response:
            count = 0
            with partial.open('wb') as stream:
                for line in response:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                        code = item.get('code', 0)
                        if code not in (0, 20000000):
                            raise RuntimeError('火山TTS服务错误 '+safe_code(code)+'；未保存不完整音频')
                        if item.get('data'):
                            data = base64.b64decode(item['data'], validate=True)
                            stream.write(data)
                            count += len(data)
                    except (ValueError, TypeError, AttributeError):
                        raise RuntimeError('火山TTS响应格式无效；未保存不完整音频') from None
            if not count:
                raise RuntimeError('火山TTS没有返回音频')
        partial.replace(output)
    finally:
        if partial.exists():
            partial.unlink()
    return output


def recognize(audio, account, *, opener=urllib.request.urlopen, timeout=180):
    audio = Path(audio)
    if audio.stat().st_size > 100_000_000:
        raise ValueError('ASR音频超过100MB，请按实际段落分段，不截断声音')
    body = dict(user={'uid': 'handraw-voice'}, audio={'data': base64.b64encode(audio.read_bytes()).decode('ascii')},
                request=dict(model_name='bigmodel', enable_punc=True, enable_itn=False, show_utterances=True))
    with _open(ASR_URL, body, headers(account, account['asr_resource'], True), timeout, opener) as response:
        code = response.headers.get('X-Api-Status-Code')
        if code != '20000000':
            raise RuntimeError('火山ASR服务状态 '+safe_code(code)+'；检查识别资源权限')
        try:
            result = json.load(response)
        except (ValueError, TypeError):
            raise RuntimeError('火山ASR响应格式无效') from None
    return result
