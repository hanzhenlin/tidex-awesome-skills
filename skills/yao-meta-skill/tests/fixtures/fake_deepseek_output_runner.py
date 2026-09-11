#!/usr/bin/env python3
"""Deterministic system-boundary fake for provider matrix tests."""

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--total-tokens", type=int, default=30)
    args = parser.parse_args()
    request = json.loads(sys.stdin.read())
    if request["variant"] == "with_skill":
        output = (
            "Create SKILL.md with a clear trigger boundary, canonical Skill IR, focused evals, "
            "immutable evidence, trust checks, owner review, and an explicit rollback plan."
        )
    else:
        output = "Write a short direct answer and a checklist."
    print(
        json.dumps(
            {
                "output": output,
                "execution_kind": "model",
                "provider": "deepseek",
                "model": args.model,
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": max(0, args.total_tokens - 10),
                    "total_tokens": args.total_tokens,
                    "estimated": False,
                },
                "response_id": f"fixture-{args.model}-{request['case_id']}-{request['variant']}",
            }
        )
    )


if __name__ == "__main__":
    main()
