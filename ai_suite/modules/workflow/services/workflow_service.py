from __future__ import annotations

import json
import re
import uuid
from typing import Any

import requests

from ai_suite.modules.workflow.core.config import settings
from ai_suite.modules.workflow.repositories.store import Store
from ai_suite.modules.workflow.services.context_service import ContextService

TEMPLATES = [
    {
        'id': 'repo_to_release',
        'name': 'Repository to release workflow',
        'summary': 'Review a repository, gate risky changes, and produce a release-ready implementation chain.',
        'use_case': 'Software project QA and launch preparation',
        'nodes': ['Trigger', 'Repository Context', 'Code Review Agent', 'Security Gate', 'Test Plan', 'Human Approval', 'Release Report'],
    },
    {
        'id': 'n8n_agentic_automation',
        'name': 'n8n implementation workflow',
        'summary': 'Produce a concrete n8n node-by-node workflow with trigger, code/action nodes, error branches, and run logging.',
        'use_case': 'Webhook, scheduled, API, or AI-agent automation',
        'nodes': ['Trigger', 'Validation', 'Transform', 'Tool Action', 'Error Handler', 'Run Log'],
    },
    {
        'id': 'zapier_make_decision_flow',
        'name': 'Zapier/Make implementation map',
        'summary': 'Map trigger/action/branch modules and identify where no-code is sufficient or where code/MCP is required.',
        'use_case': 'Business automation planning and migration to code',
        'nodes': ['Trigger', 'Filter/Router', 'Branch Actions', 'Cost Guard', 'Fallback', 'Export'],
    },
    {
        'id': 'tdd_feature_builder',
        'name': 'TDD feature workflow',
        'summary': 'Define failing tests, implement minimal change, refactor, and verify release readiness.',
        'use_case': 'Feature implementation or bugfix planning',
        'nodes': ['Requirement', 'Failing Test', 'Implementation', 'Regression Test', 'Review', 'Report'],
    },
    {
        'id': 'security_validation',
        'name': 'Defensive security validation',
        'summary': 'Run an authorized defensive checklist without destructive or exploitative actions.',
        'use_case': 'Pre-release security assurance',
        'nodes': ['Scope', 'Surface Map', 'Input Validation Check', 'Dependency Check', 'Security Report'],
    },
]

NODE_TYPES = [
    {'id': 'trigger', 'name': 'Trigger', 'description': 'Starts a workflow from a manual request, schedule, webhook, repository upload, or form submission.'},
    {'id': 'context', 'name': 'Context Loader', 'description': 'Reads selected files, README content, manifests, or workflow documentation.'},
    {'id': 'agent', 'name': 'Agent Step', 'description': 'Performs planning, review, synthesis, debugging, or implementation guidance.'},
    {'id': 'tool', 'name': 'Tool Action', 'description': 'Calls an MCP/API/n8n/Zapier/Make capability with validated inputs and structured output.'},
    {'id': 'condition', 'name': 'Condition', 'description': 'Routes the workflow based on risk, missing inputs, tests, confidence, or human response.'},
    {'id': 'approval', 'name': 'Human Approval', 'description': 'Pauses before irreversible, external, security-sensitive, or production actions.'},
    {'id': 'test', 'name': 'Test Gate', 'description': 'Defines and checks validation steps before the workflow can pass.'},
    {'id': 'security', 'name': 'Security Gate', 'description': 'Applies defensive security checks and safe execution constraints.'},
    {'id': 'report', 'name': 'Runbook Writer', 'description': 'Compiles implementation steps, checks, failure handling, and operational notes.'},
    {'id': 'export', 'name': 'Export', 'description': 'Produces Skill.md, technical schema, n8n/Zapier/Make implementation docs, JSON, and YAML.'},
]

ALLOWED_NODE_TYPES = {n['id'] for n in NODE_TYPES}


class WorkflowService:
    def __init__(self, store: Store, context: ContextService):
        self.store = store
        self.context = context

    def templates(self) -> list[dict[str, Any]]:
        return TEMPLATES

    def node_types(self) -> list[dict[str, Any]]:
        return NODE_TYPES

    def _llm_mode(self) -> str:
        provider = (settings.llm_provider or 'offline').lower().strip()
        if provider == 'deepseek' and settings.deepseek_api_key:
            return 'deepseek'
        if provider == 'gemini' and settings.gemini_api_key:
            return 'gemini'
        return 'offline'

    def _slug(self, text: str) -> str:
        s = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')
        return s[:44] or 'workflow'

    def _decision_map(self, req: dict[str, Any]) -> dict[str, bool]:
        decisions = {str(d.get('id')): str(d.get('answer', 'no')).lower() == 'yes' for d in req.get('human_decisions') or []}
        decisions.setdefault('target_n8n', 'n8n_agentic_automation' in set(req.get('template_ids') or []))
        decisions.setdefault('target_zapier_make', 'zapier_make_decision_flow' in set(req.get('template_ids') or []))
        decisions.setdefault('generate_skill', True)
        decisions.setdefault('include_mcp_contract', True)
        decisions.setdefault('require_tests', 'tdd_feature_builder' in set(req.get('template_ids') or []))
        decisions.setdefault('require_security_gate', 'security_validation' in set(req.get('template_ids') or []))
        decisions.setdefault('human_approval', bool(req.get('require_approval', True)))
        return decisions

    def _context_digest(self, context_files: dict[str, str]) -> list[str]:
        if not context_files:
            return ['No repository context selected; design from the stated objective and human decisions.']
        facts: list[str] = []
        names = list(context_files.keys())
        if any(name.endswith('package.json') for name in names):
            facts.append('JavaScript/TypeScript package manifest detected; include install/build/test command validation.')
        if any(name.endswith('requirements.txt') or name.endswith('pyproject.toml') for name in names):
            facts.append('Python backend dependency file detected; include venv, import, and runtime validation.')
        if any('+page.svelte' in name or 'svelte.config' in name for name in names):
            facts.append('Svelte/SvelteKit frontend context detected; include app.html, VITE env, accessibility, and build checks.')
        if any('main.py' in name or '/routers/' in name or '\\routers\\' in name for name in names):
            facts.append('FastAPI-style backend context detected; include route table, CORS, health checks, and uvicorn command checks.')
        if any('.env' in name for name in names):
            facts.append('Environment file context detected; include public/private variable separation and no-secret export rules.')
        if not facts:
            facts.append(f'{len(context_files)} selected files loaded; use them only for workflow implementation details.')
        return facts[:6]

    def _infer_nodes(self, objective: str, template_ids: list[str], context_files: dict[str, str], decisions: dict[str, bool]) -> list[dict[str, Any]]:
        obj = objective.lower()
        selected_templates = set(template_ids or [])
        nodes = [
            {
                'id': 'manual_request',
                'type': 'trigger',
                'title': 'Manual request intake',
                'instruction': 'Collect the objective, selected files, target platform decisions, and approval rules before generating any workflow artifact.',
                'input_from': [],
                'guardrail': 'Do not assume credentials, production access, or external side-effect permission.',
                'output_key': 'request_packet',
                'implementation': ['UI asks human yes/no routing questions.', 'Persist objective, selected templates, selected files, and decisions as the run input.'],
            },
            {
                'id': 'context_loader',
                'type': 'context',
                'title': 'Selected context loader',
                'instruction': 'Read only selected repository files and extract facts that affect implementation, routing, credentials, tests, and deployment.',
                'input_from': ['manual_request'],
                'guardrail': 'Ignore binaries, generated folders, unrelated docs, package locks unless selected, and hidden secrets.',
                'output_key': 'context_facts',
                'implementation': self._context_digest(context_files),
            },
            {
                'id': 'blueprint_planner',
                'type': 'agent',
                'title': 'Implementation blueprint planner',
                'instruction': 'Convert the objective into a concrete automation blueprint with event, nodes, inputs, outputs, checks, and failure branches.',
                'input_from': ['context_loader'],
                'guardrail': 'Produce implementable workflow units, not a narrative summary.',
                'output_key': 'blueprint',
                'implementation': ['Define event source.', 'Define exact node chain.', 'Define required inputs and outputs.', 'Define failure and retry behavior.'],
            },
        ]

        if decisions.get('target_n8n') or 'n8n' in obj or 'workflow' in obj:
            nodes.append({
                'id': 'n8n_builder',
                'type': 'tool',
                'title': 'n8n component builder',
                'instruction': 'Generate a node-by-node n8n implementation plan with trigger node, validation node, code/action nodes, error branch, and run log.',
                'input_from': ['blueprint_planner'],
                'guardrail': 'Prefer native n8n nodes before code nodes; use code nodes only for transformation, validation, and branching that native nodes cannot express.',
                'output_key': 'n8n_blueprint',
                'implementation': ['Manual/Webhook Trigger', 'Set/Code validation node', 'HTTP Request or MCP tool node', 'IF/Switch risk branch', 'Error Trigger or failure branch', 'Execution log sink'],
            })

        if decisions.get('target_zapier_make') or 'zapier' in obj or 'make' in obj:
            nodes.append({
                'id': 'zapier_make_builder',
                'type': 'tool',
                'title': 'Zapier/Make component builder',
                'instruction': 'Generate a no-code automation map with trigger, filters/routers, actions, fallback path, and escalation to code/MCP where no-code is brittle.',
                'input_from': ['blueprint_planner'],
                'guardrail': 'Do not hide loops, expensive polling, weak observability, or unsupported branching behind generic no-code labels.',
                'output_key': 'zapier_make_blueprint',
                'implementation': ['Trigger app/event', 'Filter/Router module', 'Formatter/Tools transform', 'Webhooks/API call', 'Storage/log row', 'Fallback notification'],
            })

        if decisions.get('include_mcp_contract') or 'mcp' in obj:
            nodes.append({
                'id': 'mcp_contract',
                'type': 'tool',
                'title': 'MCP tool contract designer',
                'instruction': 'Define the MCP tool interface needed by the workflow: names, descriptions, typed parameters, returns, errors, and environment variables.',
                'input_from': ['blueprint_planner'],
                'guardrail': 'One responsibility per tool; environment-based secrets only; structured output only.',
                'output_key': 'mcp_contract',
                'implementation': ['Define verb_noun tool names.', 'Define Pydantic/Zod-compatible input schema.', 'Define JSON return shape.', 'Define isError-style failure output.'],
            })

        if decisions.get('require_tests') or 'test' in obj or 'tdd' in obj:
            nodes.append({
                'id': 'test_gate',
                'type': 'test',
                'title': 'Acceptance and regression gate',
                'instruction': 'Define tests that must fail before implementation and pass after implementation before the workflow is approved.',
                'input_from': ['blueprint_planner'],
                'guardrail': 'No implementation-ready output without acceptance criteria and smoke tests.',
                'output_key': 'test_plan',
                'implementation': ['Contract test for expected output shape.', 'Failure-path test for bad input.', 'Smoke command for local run.', 'Regression check for existing behavior.'],
            })

        if decisions.get('require_security_gate') or 'security' in obj or 'deploy' in obj or 'production' in obj:
            nodes.append({
                'id': 'security_gate',
                'type': 'security',
                'title': 'Defensive security gate',
                'instruction': 'Check authorization, secrets, input validation, dependency integrity, CORS, audit logging, and external side-effect boundaries.',
                'input_from': ['blueprint_planner'],
                'guardrail': 'Defensive validation only. Do not generate exploit payloads or destructive steps.',
                'output_key': 'security_checks',
                'implementation': ['Secrets are read from environment only.', 'Inputs are validated before any tool call.', 'CORS is restricted for browser clients.', 'External writes require approval.'],
            })

        if decisions.get('human_approval'):
            nodes.append({
                'id': 'approval_gate',
                'type': 'approval',
                'title': 'Human approval checkpoint',
                'instruction': 'Pause and ask for explicit confirmation before external API writes, deployment, security scans, irreversible updates, or paid operations.',
                'input_from': [nodes[-1]['id']],
                'guardrail': 'No silent execution of production or irreversible actions.',
                'output_key': 'approval_status',
                'implementation': ['Render yes/no approval question.', 'Continue only on yes.', 'Store rejection reason or fallback path on no.'],
            })

        if decisions.get('generate_skill'):
            nodes.append({
                'id': 'skill_writer',
                'type': 'report',
                'title': 'Skill.md generator',
                'instruction': 'Generate a full SKILL.md-style operating manual for the workflow with purpose, inputs, outputs, workflow, guardrails, and validation checks.',
                'input_from': [nodes[-1]['id']],
                'guardrail': 'The skill must be directly reusable by an agent or developer.',
                'output_key': 'skill_md',
                'implementation': ['Write purpose and triggers.', 'Define input contract.', 'Define operating workflow.', 'Define safety rules.', 'Define validation checks.'],
            })

        nodes.extend([
            {
                'id': 'implementation_readme',
                'type': 'report',
                'title': 'Implementation README compiler',
                'instruction': 'Compile detailed implementation instructions for n8n and/or Zapier/Make using event → node → node → result structure.',
                'input_from': [nodes[-1]['id']],
                'guardrail': 'Include concrete components and failure branches rather than shallow trace summaries.',
                'output_key': 'implementation_readme',
                'implementation': ['Document event source.', 'List each node/module.', 'Define data passed between nodes.', 'Define error handling.', 'Define operational validation.'],
            },
            {
                'id': 'export_artifacts',
                'type': 'export',
                'title': 'Artifact export package',
                'instruction': 'Export advanced technical schema, Skill.md, n8n README, Zapier/Make README, MCP contract, JSON, and YAML as applicable.',
                'input_from': ['implementation_readme'],
                'guardrail': 'No secrets, no vague metadata, and no unsupported platform claims.',
                'output_key': 'artifact_package',
                'implementation': ['Generate JSON schema.', 'Generate YAML handoff.', 'Generate copyable implementation documents.'],
            },
        ])
        return nodes

    def _edges(self, nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        edges: list[dict[str, str]] = []
        for node in nodes:
            for source in node.get('input_from', []):
                edges.append({'source': source, 'target': node['id'], 'label': 'feeds'})
        if not edges:
            edges = [{'source': a['id'], 'target': b['id'], 'label': 'next'} for a, b in zip(nodes, nodes[1:])]
        return edges

    def _workflow_export(self, payload: dict[str, Any]) -> tuple[str, str]:
        json_text = json.dumps(payload, indent=2)
        lines = [f"workflow_id: {payload['workflow_id']}", f"title: {json.dumps(payload['title'])}", 'nodes:']
        for n in payload['nodes']:
            lines.extend([
                f"  - id: {n['id']}",
                f"    type: {n['type']}",
                f"    title: {json.dumps(n['title'])}",
                f"    instruction: {json.dumps(n['instruction'])}",
                f"    output_key: {n['output_key']}",
            ])
            if n.get('implementation'):
                lines.append('    implementation:')
                for step in n['implementation'][:8]:
                    lines.append(f"      - {json.dumps(str(step))}")
        lines.append('edges:')
        for e in payload['edges']:
            lines.append(f"  - {e['source']} -> {e['target']} ({e['label']})")
        return json_text, '\n'.join(lines) + '\n'

    def _title(self, objective: str) -> str:
        words = [w.strip('.,:;') for w in objective.split() if len(w.strip('.,:;')) > 2]
        return ' '.join(words[:8]).capitalize() or 'Agentic workflow'

    def _build_workflow(self, req: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        context_files = self.context.read_selected(req.get('session_id'), req.get('target_files') or [])
        decisions = self._decision_map(req)
        wid = uuid.uuid4().hex[:12]
        title = self._title(req['objective'])
        nodes = self._infer_nodes(req['objective'], req.get('template_ids') or [], context_files, decisions)
        edges = self._edges(nodes)
        payload = {'workflow_id': wid, 'title': title, 'objective': req['objective'], 'nodes': nodes, 'edges': edges}
        payload['export_json'], payload['export_yaml'] = self._workflow_export(payload)
        self.store.insert_workflow(wid, req.get('session_id'), title, req['objective'], payload)
        return payload, context_files

    def _static_traces(self, workflow: dict[str, Any], context_files: dict[str, str]) -> list[dict[str, Any]]:
        traces = []
        for node in workflow['nodes']:
            summary = self._node_summary(node, context_files)
            traces.append({
                'node_id': node['id'],
                'title': node['title'],
                'status': 'needs_approval' if node['type'] == 'approval' else 'passed',
                'summary': summary,
                'output': {node['output_key']: node.get('implementation') or summary},
            })
        return traces

    def _node_summary(self, node: dict[str, Any], context_files: dict[str, str]) -> str:
        if node['type'] == 'context':
            if not context_files:
                return 'No selected repository context; generated implementation from objective and human decisions.'
            return f"Read {len(context_files)} selected files and extracted implementation facts only."
        if node['id'] == 'n8n_builder':
            return 'Generated concrete n8n node chain with trigger, validation, action, error branch, and log sink.'
        if node['id'] == 'zapier_make_builder':
            return 'Generated Zapier/Make trigger-action-router map with no-code boundaries and fallback path.'
        if node['id'] == 'mcp_contract':
            return 'Defined agent-callable MCP tool contract with typed inputs, structured output, and error behavior.'
        if node['type'] == 'approval':
            return 'Human approval is required before side effects or production actions.'
        if node['type'] == 'export':
            return 'Exported implementation artifacts, not just a trace summary.'
        return 'Completed with concrete implementation outputs and guardrails.'

    def _findings(self, workflow: dict[str, Any], req: dict[str, Any]) -> list[dict[str, str]]:
        types = {n['type'] for n in workflow['nodes']}
        findings: list[dict[str, str]] = []
        if 'approval' not in types:
            findings.append({'severity': 'warning', 'title': 'No human approval gate', 'detail': 'The workflow can proceed without explicit human confirmation.', 'recommendation': 'Enable approval before external writes, deployments, scans, or paid operations.'})
        if 'test' not in types:
            findings.append({'severity': 'suggestion', 'title': 'No test-first gate', 'detail': 'The workflow lacks a dedicated acceptance-check step.', 'recommendation': 'Add acceptance tests or smoke checks before implementation actions.'})
        if 'security' not in types:
            findings.append({'severity': 'suggestion', 'title': 'No defensive security gate', 'detail': 'The workflow does not explicitly validate secrets, auth, inputs, dependencies, CORS, or logs.', 'recommendation': 'Add a defensive security gate for production-facing workflows.'})
        findings.append({'severity': 'pass', 'title': 'Implementation artifacts generated', 'detail': 'The run produced Skill.md, technical schema, and platform implementation documents.', 'recommendation': 'Review the artifacts and use the appropriate export for your target runtime.'})
        return findings

    def _platform_sequence(self, workflow: dict[str, Any], platform: str) -> list[str]:
        title = workflow['title']
        if platform == 'n8n':
            return [
                'Manual Trigger or Webhook Trigger receives the workflow request payload.',
                'Set node normalizes objective, approval policy, selected file list, and target runtime.',
                'Code node validates required fields and rejects missing objective/context with a clear error object.',
                'HTTP Request node calls repository/context service or MCP tool server to load selected context only.',
                'AI Agent or HTTP LLM node generates the implementation blueprint using the context packet.',
                'IF node checks risk flags: external write, deployment, security scan, paid action, or missing credentials.',
                'Wait node or Form node asks a human yes/no approval question when risk flags are present.',
                'Code node compiles Skill.md, technical schema, runbook, and JSON/YAML exports.',
                'Storage/log node records run id, decision answers, generated artifacts, and failure state.',
                'Respond to Webhook node returns the artifacts to the caller.',
            ]
        return [
            'Trigger event starts from form submit, schedule, webhook catch hook, or repository upload notification.',
            'Filter step rejects incomplete objective, missing target runtime, or disallowed side-effect request.',
            'Formatter/Code step creates a normalized workflow request packet.',
            'Webhooks/API step calls the builder API or MCP gateway with selected file references.',
            'Router step separates no-risk generation from approval-required execution.',
            'Approval step sends yes/no question to Slack, email, or an approvals table.',
            'Action step creates the Skill.md/schema/README artifacts after approval or produces a blocked run report.',
            'Storage/log step saves artifact URLs, decision values, run status, and operator notes.',
        ]

    def _technical_schema(self, workflow: dict[str, Any], decisions: dict[str, bool]) -> str:
        payload = {
            'schema_version': 'flowforge.workflow.v2',
            'workflow_id': workflow['workflow_id'],
            'title': workflow['title'],
            'human_in_loop': {
                'enabled': decisions.get('human_approval', True),
                'approval_required_for': ['external_api_write', 'production_deploy', 'security_scan', 'paid_operation', 'irreversible_change'],
                'decision_shape': {'id': 'string', 'question': 'string', 'answer': 'yes|no'},
            },
            'runtime_targets': {
                'n8n': decisions.get('target_n8n', False),
                'zapier_make': decisions.get('target_zapier_make', False),
                'mcp': decisions.get('include_mcp_contract', False),
                'agent_skill': decisions.get('generate_skill', True),
            },
            'nodes': [
                {
                    'id': n['id'],
                    'type': n['type'],
                    'title': n['title'],
                    'inputs': n.get('input_from', []),
                    'output_key': n['output_key'],
                    'guardrail': n.get('guardrail'),
                    'implementation': n.get('implementation', []),
                }
                for n in workflow['nodes']
            ],
            'error_policy': {
                'validation_error': 'return structured error and stop before tool calls',
                'tool_error': 'capture error object, route to fallback, notify human if side effect was intended',
                'approval_no': 'stop workflow and return blocked runbook',
                'llm_error': 'fall back to deterministic artifact generation',
            },
        }
        return json.dumps(payload, indent=2)

    def _skill_md(self, workflow: dict[str, Any], decisions: dict[str, bool]) -> str:
        lines = [
            f"# {workflow['title']} Skill",
            '',
            '## Purpose',
            workflow['objective'],
            '',
            '## When to use',
            '- Use when a user needs a concrete automation workflow rather than a narrative plan.',
            '- Use when repository context, MCP tools, n8n/Zapier/Make, approval gates, tests, or release-risk checks affect implementation.',
            '',
            '## Inputs',
            '- `objective`: the automation or agentic workflow goal.',
            '- `selected_files`: repository/context files intentionally included by the user.',
            '- `human_decisions`: yes/no decisions that define target runtimes and safety gates.',
            '- `credentials`: provided only through environment variables or platform secret stores.',
            '',
            '## Human-in-the-loop questions',
            '- Should this generate an n8n implementation? yes/no',
            '- Should this generate a Zapier/Make implementation? yes/no',
            '- Should external side effects require approval? yes/no',
            '- Should a reusable Skill.md be generated? yes/no',
            '- Should an MCP tool contract be generated? yes/no',
            '',
            '## Workflow',
        ]
        for i, node in enumerate(workflow['nodes'], 1):
            lines.append(f"{i}. **{node['title']}** — {node['instruction']}")
            for step in node.get('implementation', [])[:6]:
                lines.append(f"   - {step}")
        lines.extend([
            '',
            '## Guardrails',
            '- Never execute production writes, scans, paid operations, or irreversible actions without explicit approval.',
            '- Never export secrets; reference secret names only.',
            '- Defensive security validation only; do not generate exploit payloads or destructive commands.',
            '- Generated workflows must include validation, failure handling, and an operator-readable runbook.',
            '',
            '## Success criteria',
            '- A runnable workflow schema is available.',
            '- n8n/Zapier/Make implementation steps are concrete if those targets are selected.',
            '- Skill.md and MCP contract are generated if requested.',
            '- Approval and failure paths are explicit.',
        ])
        return '\n'.join(lines).strip() + '\n'

    def _n8n_readme(self, workflow: dict[str, Any]) -> str:
        lines = [f"# n8n Implementation README — {workflow['title']}", '', '## Event chain', '']
        for i, step in enumerate(self._platform_sequence(workflow, 'n8n'), 1):
            lines.append(f"{i}. {step}")
        lines.extend([
            '',
            '## Required n8n nodes',
            '- Manual Trigger or Webhook Trigger',
            '- Set node for request normalization',
            '- Code node for validation and artifact shaping',
            '- HTTP Request node for API/MCP/LLM calls',
            '- IF or Switch node for risk routing',
            '- Wait/Form/Slack approval node for human confirmation',
            '- Error Trigger or failure branch',
            '- Respond to Webhook or storage/log node',
            '',
            '## Data contract between nodes',
            '```json',
            json.dumps({'objective': 'string', 'selected_files': ['path'], 'human_decisions': [{'id': 'target_n8n', 'answer': 'yes'}], 'risk_flags': ['external_write'], 'artifacts': {'skill_md': 'markdown', 'technical_schema': 'json'}}, indent=2),
            '```',
            '',
            '## Failure handling',
            '- Validation failure: stop and return missing fields.',
            '- Tool/API failure: capture message, status code, retry eligibility, and fallback path.',
            '- Approval denied: stop before side effects and export a blocked-run report.',
            '- LLM failure: use deterministic schema and document the fallback.',
        ])
        return '\n'.join(lines).strip() + '\n'

    def _zapier_make_readme(self, workflow: dict[str, Any]) -> str:
        lines = [f"# Zapier/Make Implementation README — {workflow['title']}", '', '## Event → module → result chain', '']
        for i, step in enumerate(self._platform_sequence(workflow, 'zapier_make'), 1):
            lines.append(f"{i}. {step}")
        lines.extend([
            '',
            '## Zapier component map',
            '- Trigger: Webhooks by Zapier / Schedule / Form submission',
            '- Filter: required fields and risk flags',
            '- Formatter or Code by Zapier: normalize request packet',
            '- Webhooks by Zapier: call builder API or MCP gateway',
            '- Paths by Zapier: route approval-required vs direct artifact generation',
            '- Email/Slack/Approval table: collect yes/no human decision',
            '- Storage by Zapier / Tables: save artifacts and run status',
            '',
            '## Make component map',
            '- Webhook/Scheduler module receives event',
            '- Tools/Text parser module normalizes payload',
            '- Router module splits risk paths',
            '- HTTP module calls builder API or MCP gateway',
            '- Data store module logs run state and artifacts',
            '- Notification module asks for approval when needed',
            '',
            '## No-code boundaries',
            '- Use code/MCP when loops, structured validation, repository parsing, or artifact generation exceed platform-native modules.',
            '- Avoid high-frequency polling where webhook or event-driven design is available.',
            '- Keep credentials in platform secret stores only.',
        ])
        return '\n'.join(lines).strip() + '\n'

    def _mcp_contract(self, workflow: dict[str, Any]) -> str:
        contract = {
            'server_name': f"{self._slug(workflow['title'])}_server",
            'tools': [
                {
                    'name': 'build_workflow_artifacts',
                    'description': 'Build Skill.md, technical schema, and platform implementation docs from a validated workflow request. Use after human decisions are collected.',
                    'parameters': {
                        'objective': {'type': 'string', 'description': 'Workflow objective'},
                        'selected_files': {'type': 'array[string]', 'description': 'Context files selected by the user'},
                        'target_runtime': {'type': 'enum', 'values': ['n8n', 'zapier_make', 'mcp', 'agent_skill']},
                        'require_approval': {'type': 'boolean', 'default': True},
                    },
                    'returns': {'artifacts': ['skill_md', 'technical_schema', 'n8n_readme', 'zapier_make_readme'], 'risk_flags': ['string'], 'next_action': 'string'},
                    'errors': ['missing_objective', 'approval_required', 'unsupported_runtime', 'context_unavailable'],
                },
                {
                    'name': 'request_human_approval',
                    'description': 'Ask a yes/no approval question before external side effects, deployments, paid operations, or security-sensitive execution.',
                    'parameters': {'question': {'type': 'string'}, 'risk_flags': {'type': 'array[string]'}, 'run_id': {'type': 'string'}},
                    'returns': {'approved': 'boolean', 'answer': 'yes|no', 'reason': 'string|null'},
                    'errors': ['approval_timeout', 'invalid_run_id'],
                },
            ],
            'env': ['WORKFLOW_STORE_URL', 'LLM_PROVIDER', 'DEEPSEEK_API_KEY or GEMINI_API_KEY'],
        }
        return json.dumps(contract, indent=2)

    def _runbook(self, workflow: dict[str, Any], findings: list[dict[str, str]]) -> str:
        lines = [f"# Runbook — {workflow['title']}", '', '## Execution sequence', '']
        for i, node in enumerate(workflow['nodes'], 1):
            lines.append(f"{i}. {node['title']}")
            lines.append(f"   - Output: `{node['output_key']}`")
            if node.get('guardrail'):
                lines.append(f"   - Guardrail: {node['guardrail']}")
        lines.extend(['', '## Release checks', ''])
        for f in findings:
            lines.append(f"- {f['severity'].upper()}: {f['title']} — {f['recommendation']}")
        return '\n'.join(lines).strip() + '\n'

    def _artifacts(self, workflow: dict[str, Any], req: dict[str, Any], findings: list[dict[str, str]]) -> list[dict[str, str]]:
        decisions = self._decision_map(req)
        artifacts = [
            {'name': 'SKILL.md', 'kind': 'skill_md', 'content': self._skill_md(workflow, decisions)},
            {'name': 'workflow.schema.json', 'kind': 'technical_schema', 'content': self._technical_schema(workflow, decisions)},
            {'name': 'MCP_CONTRACT.json', 'kind': 'mcp_contract', 'content': self._mcp_contract(workflow)},
            {'name': 'RUNBOOK.md', 'kind': 'runbook', 'content': self._runbook(workflow, findings)},
        ]
        if decisions.get('target_n8n'):
            artifacts.append({'name': 'N8N_IMPLEMENTATION.md', 'kind': 'n8n_readme', 'content': self._n8n_readme(workflow)})
        if decisions.get('target_zapier_make'):
            artifacts.append({'name': 'ZAPIER_MAKE_IMPLEMENTATION.md', 'kind': 'zapier_make_readme', 'content': self._zapier_make_readme(workflow)})
        return artifacts

    def _markdown(self, workflow: dict[str, Any], findings: list[dict[str, str]], artifacts: list[dict[str, str]]) -> str:
        lines = [f"# {workflow['title']}", '', workflow['objective'], '', '## Built artifacts', '']
        for artifact in artifacts:
            lines.append(f"- **{artifact['name']}** — {artifact['kind']}")
        lines.extend(['', '## Implementation chain', ''])
        for node in workflow['nodes']:
            lines.append(f"- **{node['title']}** — {node['instruction']}")
        lines.extend(['', '## Checks', ''])
        for f in findings:
            lines.append(f"- **{f['severity'].upper()}**: {f['title']} — {f['recommendation']}")
        return '\n'.join(lines).strip() + '\n'

    def _normalize_llm_workflow(self, data: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            return base
        title = str(data.get('title') or base['title']).strip()[:100]
        nodes = []
        for raw in data.get('nodes') or []:
            if not isinstance(raw, dict):
                continue
            ntype = str(raw.get('type') or 'agent').strip().lower()
            if ntype not in ALLOWED_NODE_TYPES:
                ntype = 'agent'
            nodes.append({
                'id': self._slug(str(raw.get('id') or raw.get('title') or ntype)),
                'type': ntype,
                'title': str(raw.get('title') or ntype.title()).strip()[:90],
                'instruction': str(raw.get('instruction') or 'Execute this workflow step with structured output.').strip()[:600],
                'input_from': [str(x) for x in raw.get('input_from') or []][:4],
                'guardrail': None if raw.get('guardrail') is None else str(raw.get('guardrail'))[:350],
                'output_key': self._slug(str(raw.get('output_key') or raw.get('title') or ntype)),
                'implementation': [str(x) for x in raw.get('implementation') or []][:8],
            })
        if len(nodes) < 5:
            return base
        payload = {'workflow_id': base['workflow_id'], 'title': title, 'objective': base['objective'], 'nodes': nodes, 'edges': self._edges(nodes)}
        payload['export_json'], payload['export_yaml'] = self._workflow_export(payload)
        return payload

    def _call_llm(self, req: dict[str, Any], base: dict[str, Any], context_files: dict[str, str]) -> dict[str, Any]:
        mode = self._llm_mode()
        if mode == 'offline' or not req.get('use_llm', True):
            return base
        system = (
            'You design production-safe human-in-the-loop AI workflows. Return strict JSON with keys title and nodes only. '
            'Every node must include id, type, title, instruction, input_from, guardrail, output_key, and implementation. '
            f'Allowed node types: {sorted(ALLOWED_NODE_TYPES)}. '
            'The output must be implementable: include event -> node -> node -> result details, approval gates, failure handling, tests, security checks, and export artifacts. '
            'Do not return a shallow trace summary or redundant metadata.'
        )
        user = json.dumps({
            'objective': req['objective'],
            'selected_template_ids': req.get('template_ids') or [],
            'human_decisions': req.get('human_decisions') or [],
            'base_workflow': base,
            'context_file_names': list(context_files),
        }, indent=2)[:12000]
        try:
            if mode == 'deepseek':
                resp = requests.post(
                    settings.deepseek_api_url,
                    headers={'Authorization': f'Bearer {settings.deepseek_api_key}', 'Content-Type': 'application/json'},
                    json={'model': settings.deepseek_model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'temperature': 0.2, 'response_format': {'type': 'json_object'}},
                    timeout=45,
                )
                resp.raise_for_status(); text = resp.json()['choices'][0]['message']['content']
            else:
                url = f'https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}'
                resp = requests.post(url, json={'systemInstruction': {'parts': [{'text': system}]}, 'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json'}}, timeout=45)
                resp.raise_for_status(); text = resp.json()['candidates'][0]['content']['parts'][0]['text']
            return self._normalize_llm_workflow(json.loads(text), base)
        except Exception:
            return base

    def run(self, req: dict[str, Any]) -> dict[str, Any]:
        base, context_files = self._build_workflow(req)
        workflow = self._call_llm(req, base, context_files)
        # Regenerate exports after LLM normalization so implementation steps are included.
        workflow['export_json'], workflow['export_yaml'] = self._workflow_export(workflow)
        traces = self._static_traces(workflow, context_files)
        findings = self._findings(workflow, req)
        artifacts = self._artifacts(workflow, req, findings)
        report = self._markdown(workflow, findings, artifacts)
        result = {'workflow': workflow, 'traces': traces, 'findings': findings, 'artifacts': artifacts, 'report_markdown': report}
        self.store.insert_run(uuid.uuid4().hex[:12], workflow['workflow_id'], result)
        return result
