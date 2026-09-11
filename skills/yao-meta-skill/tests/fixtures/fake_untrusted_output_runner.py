#!/usr/bin/env python3
"""Return output while deliberately omitting model identity metadata."""

import json
import sys


request = json.loads(sys.stdin.read())
print(json.dumps({"output": f"untrusted output for {request['case_id']}", "usage": {"total_tokens": 1}}))
