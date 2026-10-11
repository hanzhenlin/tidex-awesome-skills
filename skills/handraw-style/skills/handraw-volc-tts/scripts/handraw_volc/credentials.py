"""Persistent user credentials; Windows DPAPI, private file permissions elsewhere."""
import base64
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile

SECRET_FIELDS = ('api_key', 'app_id', 'access_token')
ENV_FIELDS = dict(zip(SECRET_FIELDS, ('VOLC_API_KEY', 'VOLC_APPID', 'VOLC_ACCESS_TOKEN')))
DEFAULTS = dict(tts_resource='seed-tts-2.0', asr_resource='volc.bigasr.auc_turbo')
SETTINGS = ('speaker', 'tts_resource', 'asr_resource')


def config_path():
    override = os.environ.get('HVP_VOICE_CONFIG_DIR')
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise ValueError('HVP_VOICE_CONFIG_DIR必须为仓库外的绝对路径')
    elif sys.platform == 'win32':
        root = Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming') / 'handraw-video-producer'
    else:
        root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'handraw-video-producer'
    root = root.resolve()
    if any((p / '.git').exists() or (p / 'SKILL.md').is_file() for p in (root, *root.parents)):
        raise ValueError('语音凭据目录不能位于仓库或Skill内；请使用用户配置目录')
    return root / 'volc-tts.json'


def _dpapi(data, decrypt=False):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError('Windows用户密钥加解密失败；请在原用户账户配置或重新提交凭据')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def atomic_json(path, value, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='.voice-',
                                         suffix='.tmp', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            if private and sys.platform != 'win32':
                os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def read_saved():
    path = config_path()
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc['version'] != 1:
            raise ValueError()
        if doc['storage'] == 'windows-dpapi':
            if sys.platform != 'win32':
                raise ValueError()
            values = json.loads(_dpapi(base64.b64decode(doc['payload'], validate=True), True))
        elif doc['storage'] == 'user-file-0600' and sys.platform != 'win32':
            if path.stat().st_mode & 0o077:
                raise ValueError()
            values = doc['values']
        else:
            raise ValueError()
        if not isinstance(values, dict):
            raise ValueError()
        return values
    except (ValueError, KeyError, TypeError, OSError):
        raise ValueError('语音凭据文件无法读取；不输出文件内容，请在本机重新配置') from None


def save(values):
    if not isinstance(values, dict) or not values or set(values) - set(SECRET_FIELDS + SETTINGS):
        raise ValueError('配置只接受api_key、app_id、access_token、speaker、tts_resource、asr_resource')
    if any(not isinstance(v, str) or not v.strip() or '\n' in v or '\r' in v for v in values.values()):
        raise ValueError('配置字段必须是非空单行字符串；不输出提交内容')
    stored = read_saved()
    if 'api_key' in values:
        for key in ('app_id', 'access_token'):
            stored.pop(key, None)
        values = {k: v for k, v in values.items() if k not in ('app_id', 'access_token')}
    elif 'app_id' in values or 'access_token' in values:
        if not values.get('app_id') or not values.get('access_token'):
            raise ValueError('更新旧版账户时须同时提交AppID和Access Token，不能与旧账户混用')
        stored.pop('api_key', None)
    stored.update({k: v.strip() for k, v in values.items()})
    if not stored.get('api_key') and not (stored.get('app_id') and stored.get('access_token')):
        raise ValueError('需要API Key，或完整AppID与Access Token')
    # Save all fields as one encrypted blob on Windows, including legacy account id.
    if sys.platform == 'win32':
        payload = _dpapi(json.dumps(stored, ensure_ascii=False).encode('utf-8'))
        doc = dict(version=1, storage='windows-dpapi', payload=base64.b64encode(payload).decode('ascii'))
    else:
        doc = dict(version=1, storage='user-file-0600', values=stored)
    atomic_json(config_path(), doc, private=True)
    return status()


def from_env():
    values = {k: os.environ[v] for k, v in ENV_FIELDS.items() if os.environ.get(v)}
    if not values:
        raise ValueError('未发现VOLC_API_KEY或旧版凭据环境变量')
    return values


def resolve():
    saved = read_saved()
    # A complete environment auth overrides saved auth; never mix accounts silently.
    if os.environ.get('VOLC_API_KEY'):
        auth = {'api_key': os.environ['VOLC_API_KEY']}
    elif os.environ.get('VOLC_APPID') or os.environ.get('VOLC_ACCESS_TOKEN'):
        if not os.environ.get('VOLC_APPID') or not os.environ.get('VOLC_ACCESS_TOKEN'):
            raise ValueError('旧版环境凭据不完整，不能与保存账户混用')
        auth = {k: os.environ[v] for k, v in ENV_FIELDS.items() if k != 'api_key'}
    else:
        auth = {k: saved[k] for k in SECRET_FIELDS if saved.get(k)}
    if not auth.get('api_key') and not (auth.get('app_id') and auth.get('access_token')):
        raise ValueError('尚未配置火山账户；使用volc_voice.py config输入或保存环境凭据')
    return {**DEFAULTS, **{k: saved[k] for k in SETTINGS if k in saved}, **auth}


def status():
    saved = read_saved()
    env_key = bool(os.environ.get('VOLC_API_KEY'))
    env_legacy = bool(os.environ.get('VOLC_APPID') and os.environ.get('VOLC_ACCESS_TOKEN'))
    return dict(config_file=str(config_path()), saved=bool(saved.get('api_key') or
                (saved.get('app_id') and saved.get('access_token'))),
                environment_available=env_key or env_legacy,
                credential_source='environment' if env_key or env_legacy else 'saved' if saved else 'missing',
                encryption='Windows DPAPI current user' if sys.platform == 'win32' else 'private user file 0600',
                speaker=saved.get('speaker'), update_preserves_config=True)
