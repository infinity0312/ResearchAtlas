"""Server-side adapter for a published AgentArts Workflow invocation."""

import json
import os
import re
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

import httpx


class AgentArtsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Runtime:
    url: str
    key: str


def configured_runtime():
    url = os.getenv('ATLAS_AGENTARTS_URL', '').strip()
    key = os.getenv('ATLAS_AGENTARTS_KEY', '').strip()
    try:
        target = urlsplit(url)
        if (
            target.scheme == 'https' and target.hostname and not target.username
            and not target.password and not target.query and not target.fragment
            and re.fullmatch(r'/runtimes/agent-arts-[\w-]{1,53}/invocations', target.path, re.ASCII)
            and key
        ):
            return Runtime(url, key)
    except ValueError:
        pass
    return None


def terminal_event(lines):
    """Read the documented workflow_finished SSE event, never model deltas."""
    frame = []
    size = 0
    deadline = monotonic() + 90
    for line in lines:
        size += len(line)
        if size > 2_000_000 or monotonic() > deadline:
            raise AgentArtsError('AgentArts 响应超过本次评审限制')
        if line.startswith('data:'):
            frame.append(line[5:].lstrip(' '))
        elif not line and frame:
            try:
                event = json.loads('\n'.join(frame))
            except ValueError:
                raise AgentArtsError('AgentArts 返回了无效的工作流事件') from None
            frame.clear()
            if not isinstance(event, dict):
                continue
            kind = event.get('event')
            if kind in ('error', 'node_wait', 'workflow_blocked'):
                raise AgentArtsError('AgentArts 工作流失败或正在等待输入')
            if kind == 'workflow_finished':
                data = event.get('data')
                status = data.get('status') if isinstance(data, dict) else None
                if not isinstance(status, dict) or status.get('code') != 1 or status.get('desc') != 'succeeded':
                    raise AgentArtsError('AgentArts 工作流未成功完成')
                outputs = data.get('outputs')
                if not isinstance(outputs, dict):
                    raise AgentArtsError('AgentArts 工作流没有返回评审结果')
                fields = outputs.get('user_fields')
                output = fields.get('review_json') if isinstance(fields, dict) else None
                if output is None:
                    output = outputs.get('responseContent')
                trace = data.get('execution_id')
                return output, trace[:200] if isinstance(trace, str) else None
    raise AgentArtsError('AgentArts 连接结束前未返回工作流结果')


def invoke(runtime, run_id, context):
    headers = {
        'Authorization': f'Bearer {runtime.key}',
        'Accept': 'text/event-stream',
        'x-hw-agentarts-session-id': run_id,
    }
    try:
        with httpx.stream('POST', runtime.url, headers=headers, follow_redirects=False,
                          timeout=httpx.Timeout(25, connect=5),
                          json={'inputs': {'review_context': json.dumps(context, ensure_ascii=False)}}) as response:
            if response.status_code != 200:
                raise AgentArtsError(f'AgentArts 调用失败（HTTP {response.status_code}）')
            if 'text/event-stream' not in response.headers.get('content-type', '').lower():
                raise AgentArtsError('AgentArts 未返回工作流事件流')
            return terminal_event(response.iter_lines())
    except httpx.TimeoutException:
        raise AgentArtsError('AgentArts 连接或响应超时，可显式发起新评审') from None
    except httpx.HTTPError:
        raise AgentArtsError('无法连通 AgentArts 工作流') from None
