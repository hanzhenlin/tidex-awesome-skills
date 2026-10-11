#!/usr/bin/env python3
"""Volcano voice CLI. Secret inputs use stdin/getpass, never command-line flags."""
import argparse
import getpass
import json
from pathlib import Path
import sys

from handraw_volc import credentials, workflow


def configure(args):
    if args.stdin_json:
        try:
            values = json.load(sys.stdin)
        except (ValueError, TypeError):
            raise ValueError('标准输入不是有效配置JSON；不输出提交内容') from None
    elif args.from_env:
        values = credentials.from_env()
    elif args.interactive:
        key = getpass.getpass('API Key（隐藏输入；旧版账户留空）：').strip()
        values = {'api_key': key} if key else dict(app_id=getpass.getpass('AppID：').strip(),
                                                  access_token=getpass.getpass('Access Token：').strip())
    else:
        values = {}
    if args.speaker:
        values['speaker'] = args.speaker
    for key in ('tts_resource', 'asr_resource'):
        if getattr(args, key):
            values[key] = getattr(args, key)
    return credentials.save(values) if values else credentials.status()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    q = sub.add_parser('config')
    group = q.add_mutually_exclusive_group()
    group.add_argument('--stdin-json', action='store_true')
    group.add_argument('--from-env', action='store_true')
    group.add_argument('--interactive', action='store_true')
    q.add_argument('--speaker')
    q.add_argument('--tts-resource')
    q.add_argument('--asr-resource')
    sub.add_parser('status')
    q = sub.add_parser('episode'); q.add_argument('episode', type=Path)
    q = sub.add_parser('tts')
    q.add_argument('--text-file', type=Path, required=True)
    q.add_argument('--out-dir', type=Path, required=True)
    q.add_argument('--speaker'); q.add_argument('--direction', default='')
    q.add_argument('--speech-rate', type=int, default=0)
    q = sub.add_parser('asr')
    q.add_argument('--audio', type=Path, required=True); q.add_argument('--out-dir', type=Path, required=True)
    q.add_argument('--expected-text-file', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'config':
        result = configure(args)
    elif args.command == 'status':
        result = credentials.status()
    elif args.command == 'episode':
        result = workflow.episode(args.episode)
    elif args.command == 'asr':
        if args.expected_text_file:
            workflow.gate_paths(args.expected_text_file)
        result = workflow.asr(args.audio, args.out_dir,
                 args.expected_text_file.read_text(encoding='utf-8-sig') if args.expected_text_file else None)
    else:
        workflow.gate_paths(args.text_file, args.out_dir)
        account = credentials.resolve()
        audio, result = workflow.produce(args.text_file.read_text(encoding='utf-8-sig').strip(), args.out_dir,
                          args.speaker or account.get('speaker'), args.direction, args.speech_rate, account)
        result = {**result, 'audio_file': str(audio.resolve())}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        # These modules use sanitized errors for credentials and remote responses.
        print('[ERROR] '+str(exc), file=sys.stderr)
        sys.exit(2)
