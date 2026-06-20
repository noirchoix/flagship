from __future__ import annotations
import json, re
from typing import Any
import requests
from fastapi import HTTPException
from ai_suite.modules.shipgate.core.config import settings
from ai_suite.modules.shipgate.repositories.store import Store
from ai_suite.modules.shipgate.services.repo_service import RepoService
from ai_suite.modules.shipgate.schemas.shipgate import AuditRequest, Finding, EnvVariable, CommandBlock

ALLOWED_SEVERITIES={'blocker','warning','suggestion','nit','pass'}
ALLOWED_AGENTS={'environment_auditor','build_auditor','deployment_auditor','security_auditor','runtime_auditor','frontend_release_auditor','database_storage_auditor','documentation_auditor','rag_readiness_auditor','launch_plan_writer'}

SKILLS = [
    {'name':'README Generator','incorporated_as':'documentation_auditor','purpose':'Audits whether docs explain local dev, system architecture, and production deployment.'},
    {'name':'RAG Engineer','incorporated_as':'rag_readiness_auditor','purpose':'Checks retrieval/chunking/vector configuration when a project contains RAG components.'},
    {'name':'Receiving Code Review','incorporated_as':'launch_plan_writer','purpose':'Forces verification-first patch guidance and avoids blindly applying external review output.'},
    {'name':'DevOps Automator','incorporated_as':'deployment_auditor','purpose':'Checks CI/CD, health checks, rollback, monitoring, and infrastructure readiness.'},
    {'name':'Frontend Developer','incorporated_as':'frontend_release_auditor','purpose':'Checks frontend production build, accessibility, API base URL, and SvelteKit/Vite issues.'},
    {'name':'Backend Architect','incorporated_as':'runtime_auditor','purpose':'Checks API startup, service boundaries, error handling, and production runtime posture.'},
    {'name':'Database Optimizer','incorporated_as':'database_storage_auditor','purpose':'Checks schema, migrations, persistence, connection and storage readiness.'},
    {'name':'UI Designer','incorporated_as':'frontend_release_auditor','purpose':'Checks release UI polish, responsive states, contrast, and empty/error states.'},
]

class AuditService:
    def __init__(self, store: Store, repo: RepoService):
        self.store=store; self.repo=repo

    def health(self):
        mode=self._llm_mode()
        return {'ok': True, 'ai_enabled': mode!='offline', 'provider': self._provider_label(mode), 'audits': self.store.audit_count(), 'version':'1.0.0'}

    def skills(self):
        return SKILLS

    def run(self, req: AuditRequest):
        session=self.store.get_session(req.session_id)
        if not session: raise HTTPException(404,'Session not found')
        files=self.repo.read_targets(req.session_id, req.target_files)
        if not files: raise HTTPException(400,'No readable target files selected')
        context='\n\n'.join([f'## FILE: {p}\n{txt[:6000]}' for p,txt in files.items()])[:settings.max_context_chars]
        findings=self._static_findings(files, session, req.deployment_target)
        llm_note=''
        if req.use_llm and self._llm_mode()!='offline':
            try:
                extra, llm_note = self._llm_findings(req, session, context)
                findings.extend(extra)
            except Exception as exc:
                findings.append(self._finding('warning','launch_plan_writer','LLM synthesis failed; static audit was used',None,'The optional LLM launch-readiness synthesis raised an exception.','The platform should degrade safely to deterministic checks instead of failing the audit.',f'Check LLM provider configuration and retry if synthesis is required. Error: {exc}'))
        findings=self._dedupe(findings)
        score=self._score(findings, files)
        readiness='blocked' if any(f.severity=='blocker' for f in findings) else 'caution' if any(f.severity in {'warning','suggestion'} for f in findings) else 'ready'
        launch_plan=self._launch_plan(session, files, findings, req.deployment_target)
        summary=self._summary(score, readiness, findings, session, llm_note)
        traces=self._traces(findings)
        payload={'session_id': req.session_id, 'score': score, 'readiness': readiness, 'summary': summary, 'findings':[f.model_dump() for f in findings], 'launch_plan': launch_plan, 'traces': traces}
        payload['markdown_report']=self._markdown(payload)
        self.store.save_audit(req.session_id, payload, score, readiness)
        self.store.remember(req.session_id, 'last_readiness', readiness)
        return payload

    def _llm_mode(self):
        p=(settings.llm_provider or 'offline').lower().strip()
        if p=='deepseek' and settings.deepseek_api_key: return 'deepseek'
        if p=='gemini' and settings.gemini_api_key: return 'gemini'
        return 'offline'

    def _provider_label(self, mode):
        if mode=='deepseek': return f'deepseek:{settings.deepseek_model}'
        if mode=='gemini': return f'gemini:{settings.gemini_model}'
        return 'offline'

    def _finding(self, severity, agent, title, file, evidence, why, recommendation, command=None):
        sev_map={'critical':'blocker','fatal':'blocker','error':'blocker','high':'warning','major':'warning','medium':'suggestion','moderate':'suggestion','low':'nit','info':'nit','ok':'pass'}
        agent_map={'env':'environment_auditor','environment':'environment_auditor','build':'build_auditor','deploy':'deployment_auditor','deployment':'deployment_auditor','security':'security_auditor','runtime':'runtime_auditor','frontend':'frontend_release_auditor','database':'database_storage_auditor','storage':'database_storage_auditor','docs':'documentation_auditor','documentation':'documentation_auditor','rag':'rag_readiness_auditor','planner':'launch_plan_writer','launch':'launch_plan_writer'}
        s=sev_map.get(str(severity).lower(), str(severity).lower())
        a=agent_map.get(str(agent).lower(), str(agent).lower())
        if s not in ALLOWED_SEVERITIES: s='suggestion'
        if a not in ALLOWED_AGENTS: a='launch_plan_writer'
        return Finding(severity=s, agent=a, title=str(title)[:220], file=file, evidence=str(evidence)[:1000], why_it_matters=str(why)[:1000], recommendation=str(recommendation)[:1200], command=command)

    def _static_findings(self, files: dict[str,str], session: dict[str,Any], target: str):
        f=[]; paths={p.lower():p for p in files}; joined='\n'.join(files.values())
        names=set(paths.keys())
        # Environment
        env_files=[p for p in files if '.env' in p.lower()]
        if not any(p.lower().endswith(('.env.example','.env.sample')) for p in files):
            f.append(self._finding('blocker','environment_auditor','Missing .env.example or .env.sample',None,'No environment template was selected or detected.','A production handoff cannot be verified without an explicit environment variable contract.','Add apps/api/.env.example and apps/web/.env.example with required variables, safe defaults, and no secrets.'))
        for p,txt in files.items():
            if re.search(r'(sk_live_|sk_test_|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z_]{30,})', txt):
                f.append(self._finding('blocker','security_auditor','Possible hardcoded secret detected',p,'A token-like value appears in a selected file.','Hardcoded secrets can leak through source control, frontend bundles, logs, or artifact uploads.','Remove the secret, rotate it, and load it from server-only environment variables.'))
            if 'NEXT_PUBLIC_' in txt and re.search(r'NEXT_PUBLIC_.*(SECRET|TOKEN|KEY|PASSWORD)', txt, re.I):
                f.append(self._finding('blocker','security_auditor','Potential secret exposed through public frontend environment variable',p,'A NEXT_PUBLIC_* variable appears to contain key/token/secret/password naming.','Public-prefixed variables are shipped to the browser in many frontend frameworks.','Keep only public values in NEXT_PUBLIC_/VITE_* variables; move secrets to server-only env vars.'))
        # Frontend build
        if 'package.json' in names:
            pkg=self._json(files[paths['package.json']])
            scripts=(pkg.get('scripts') or {}) if isinstance(pkg,dict) else {}
            if 'build' not in scripts:
                f.append(self._finding('blocker','build_auditor','package.json has no production build script','package.json','No build script was found.','Deployment platforms and CI need a deterministic build command.','Add a build script such as "vite build" or "svelte-kit sync && vite build".'))
            if 'dev' not in scripts:
                f.append(self._finding('suggestion','build_auditor','package.json has no local dev script','package.json','No dev script was found.','New developers and preview environments need a consistent local startup command.','Add a dev script.'))
            deps={**(pkg.get('dependencies') or {}), **(pkg.get('devDependencies') or {})}
            if '@sveltejs/kit' in deps and pkg.get('type')!='module':
                f.append(self._finding('blocker','frontend_release_auditor','SvelteKit package should declare ESM module type','package.json','@sveltejs/kit is present but package.json lacks "type": "module".','SvelteKit/Vite config can fail on Windows or newer Vite because kit/vite is ESM-only.','Add "type": "module" to apps/web/package.json.'))
        if any('svelte.config' in p for p in names) and 'src/app.html' not in names and 'app.html' not in names:
            f.append(self._finding('blocker','frontend_release_auditor','SvelteKit app.html not selected or missing',None,'SvelteKit projects require app.html with %sveltekit.head% and %sveltekit.body%.','Missing placeholders break the dev server and production build.','Ensure src/app.html exists and contains %sveltekit.head% and %sveltekit.body%.'))
        for p,txt in files.items():
            low=p.lower()
            if low.endswith('app.html') and ('%sveltekit.head%' not in txt or '%sveltekit.body%' not in txt):
                f.append(self._finding('blocker','frontend_release_auditor','app.html missing required SvelteKit placeholders',p,'The app.html file does not contain both required placeholders.','SvelteKit cannot inject page head/body correctly without these placeholders.','Add %sveltekit.head% inside <head> and %sveltekit.body% inside <body>.'))
            if low.endswith(('client.ts','api.ts','.svelte')) and 'localhost:8000' in txt:
                f.append(self._finding('warning','frontend_release_auditor','Frontend contains hardcoded localhost API URL',p,'A frontend file references localhost:8000.','Hardcoded local URLs break preview/production deployments and cause stale-port confusion.','Read API base URL from VITE_API_BASE_URL or equivalent environment variable and document it.'))
        # Backend/runtime
        if 'requirements.txt' in names:
            req=files[paths['requirements.txt']].lower()
            if 'fastapi' in req and 'uvicorn' not in req:
                f.append(self._finding('blocker','runtime_auditor','FastAPI requirements missing uvicorn','requirements.txt','fastapi is present but uvicorn is not listed.','The API cannot be reliably started in deployment without an ASGI server dependency.','Add uvicorn[standard] to requirements.txt.'))
            if 'pydantic-settings' not in req and 'pydantic_settings' in joined:
                f.append(self._finding('blocker','runtime_auditor','pydantic-settings import used but dependency missing','requirements.txt','Code imports pydantic_settings but requirements.txt does not include pydantic-settings.','Deployment will fail on a clean environment with ModuleNotFoundError.','Add pydantic-settings>=2.0.0 to requirements.txt.'))
        for p,txt in files.items():
            low=p.lower()
            if low.endswith('main.py'):
                if 'CORSMiddleware' not in txt:
                    f.append(self._finding('warning','security_auditor','FastAPI app has no visible CORS middleware',p,'CORSMiddleware was not found in main.py.','Separate frontend/backend origins need explicit CORS configuration.','Configure CORSMiddleware using an environment-driven allowlist.'))
                if '/health' not in txt and 'health' not in joined.lower():
                    f.append(self._finding('warning','runtime_auditor','No visible health route',p,'No health endpoint was found in selected backend files.','Deployment platforms and smoke tests need a lightweight health check.','Add GET /health or /api/v1/<service>/health.'))
                if 'debug=True' in txt or 'reload=True' in txt:
                    f.append(self._finding('warning','runtime_auditor','Development debug/reload setting appears in application startup',p,'debug=True or reload=True appears in the app startup code.','Production workers should not run in debug/reload mode.','Move reload/debug to local-only command scripts.'))
        # Deployment
        deployment_files=[p for p in files if p.lower().split('/')[-1] in {'dockerfile','docker-compose.yml','vercel.json','render.yaml','railway.json','procfile'} or '.github/workflows/' in p.lower()]
        if not deployment_files:
            f.append(self._finding('warning','deployment_auditor','No deployment configuration detected',None,'No Dockerfile, Procfile, Vercel/Render/Railway config, or GitHub Actions workflow was selected.','Launch readiness requires a reproducible deployment path.','Add deployment config or document the exact hosting target and commands in README.'))
        if not any('.github/workflows/' in p.lower() for p in files):
            f.append(self._finding('suggestion','deployment_auditor','No CI workflow detected',None,'No GitHub Actions workflow was selected.','CI catches install/build/test failures before deployment.','Add a workflow that installs dependencies, runs type checks/tests, and builds frontend/backend artifacts.'))
        # Docs
        readmes=[p for p in files if p.lower().endswith('readme.md')]
        if not readmes:
            f.append(self._finding('warning','documentation_auditor','README not selected or missing',None,'No README.md was included in the audit context.','Launch handoff needs local setup, architecture, env vars, and deployment instructions.','Add or select README.md.'))
        else:
            r='\n'.join(files[p] for p in readmes).lower()
            for term,label in [('environment','environment setup'),('deploy','deployment instructions'),('production','production operations')]:
                if term not in r:
                    f.append(self._finding('suggestion','documentation_auditor',f'README lacks {label}',readmes[0],f'The README does not appear to mention {term}.','Documentation should let a new developer run and deploy the project without guessing.','Add explicit setup, env, deployment, and smoke-test sections.'))
        # DB/storage
        if re.search(r'(sqlite|postgres|duckdb|sqlalchemy|prisma|supabase)', joined, re.I):
            if not re.search(r'(migration|alembic|prisma migrate|schema.sql|db/migrate)', '\n'.join(files.keys()), re.I):
                f.append(self._finding('suggestion','database_storage_auditor','Database/storage detected but no migration path selected',None,'Database-related code or dependencies appear in selected files, but no migrations/schema files were detected.','Production launches need repeatable schema setup and rollback.','Add migrations or document schema initialization and backup/restore steps.'))
        # RAG
        if re.search(r'(rag|embedding|vector|qdrant|chromadb|faiss|retrieval)', joined, re.I):
            if not re.search(r'(chunk|top_k|rerank|metadata|hybrid)', joined, re.I):
                f.append(self._finding('suggestion','rag_readiness_auditor','RAG/vector functionality lacks visible retrieval controls',None,'RAG-related terms are present but chunking, metadata, top-k, hybrid search, or reranking controls were not obvious.','Retrieval quality determines generation quality; launch readiness should expose retrieval parameters and evaluation checks.','Document chunking strategy, retrieval mode, top_k defaults, metadata filters, and source trace output.'))
        if not f:
            f.append(self._finding('pass','launch_plan_writer','No launch blockers found in selected files',None,'Static checks did not detect known blocker patterns.','This does not prove production readiness, but the selected files passed the built-in launch gate checks.','Run build/test commands and deploy to a staging environment for final validation.'))
        return f

    def _json(self, text):
        try: return json.loads(text)
        except Exception: return {}

    def _llm_findings(self, req, session, context):
        system=("You are ShipGate, a production launch readiness auditor. Return strict JSON with keys findings and note. "
                "Each finding must use severity only: blocker, warning, suggestion, nit, pass. "
                "Each agent must be one of: environment_auditor, build_auditor, deployment_auditor, security_auditor, runtime_auditor, frontend_release_auditor, database_storage_auditor, documentation_auditor, rag_readiness_auditor, launch_plan_writer. "
                "Be conservative and file-specific. Do not invent files.")
        prompt=f"Objective: {req.objective}\nDeployment target: {req.deployment_target}\nDetected stack: {session.get('detected_stack')}\n\nRepository context:\n{context[:40000]}"
        mode=self._llm_mode()
        if mode=='deepseek': text=self._call_deepseek(system,prompt)
        else: text=self._call_gemini(system,prompt)
        parsed=self._parse_json(text)
        items=parsed.get('findings') or []
        out=[]
        for item in items[:12]:
            out.append(self._finding(item.get('severity','suggestion'), item.get('agent','launch_plan_writer'), item.get('title','LLM launch finding'), item.get('file'), item.get('evidence','LLM finding'), item.get('why_it_matters','Potential launch risk.'), item.get('recommendation','Review and verify this finding.'), item.get('command')))
        return out, str(parsed.get('note') or '')

    def _call_deepseek(self, system, user):
        r=requests.post(settings.deepseek_api_url, headers={'Authorization':f'Bearer {settings.deepseek_api_key}','Content-Type':'application/json'}, json={'model':settings.deepseek_model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0.1,'response_format':{'type':'json_object'}}, timeout=settings.deepseek_timeout_seconds)
        r.raise_for_status(); return r.json()['choices'][0]['message']['content']
    def _call_gemini(self, system, user):
        url=f'https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}'
        r=requests.post(url,json={'systemInstruction':{'parts':[{'text':system}]},'contents':[{'role':'user','parts':[{'text':user}]}],'generationConfig':{'temperature':0.1,'responseMimeType':'application/json'}},timeout=settings.deepseek_timeout_seconds)
        r.raise_for_status(); return r.json()['candidates'][0]['content']['parts'][0]['text']
    def _parse_json(self, text):
        try: return json.loads(text)
        except json.JSONDecodeError:
            s=text.find('{'); e=text.rfind('}')
            if s>=0 and e>s: return json.loads(text[s:e+1])
            raise

    def _dedupe(self, findings):
        seen=set(); out=[]
        for f in findings:
            key=(f.severity,f.agent,f.title,f.file)
            if key not in seen:
                seen.add(key); out.append(f)
        order={'blocker':0,'warning':1,'suggestion':2,'nit':3,'pass':4}
        return sorted(out, key=lambda x:(order.get(x.severity,9), x.file or '', x.title))

    def _score(self, findings, files):
        score=100
        for f in findings:
            score -= {'blocker':18,'warning':8,'suggestion':4,'nit':1,'pass':0}.get(f.severity,3)
        return max(0,min(100,score))

    def _summary(self, score, readiness, findings, session, note):
        counts={s:sum(1 for f in findings if f.severity==s) for s in ['blocker','warning','suggestion','nit','pass']}
        msg=f"{session['repo_name']} scored {score}/100 with {counts['blocker']} blockers, {counts['warning']} warnings, and readiness status '{readiness}'."
        if note: msg += ' LLM note: '+note[:220]
        return msg

    def _env_matrix(self, files):
        found={}
        for p,txt in files.items():
            for m in re.finditer(r'\b([A-Z][A-Z0-9_]{2,})\b', txt):
                name=m.group(1)
                if name in {'HTTP','GET','POST','JSON','URL','API','SQL','CSS','HTML'}: continue
                if name not in found:
                    exposure='public' if name.startswith(('VITE_','NEXT_PUBLIC_','PUBLIC_')) else 'server' if re.search(r'(SECRET|TOKEN|KEY|DATABASE|PASSWORD|URL)', name) else 'unknown'
                    found[name]=EnvVariable(name=name, exposure=exposure, required=True, source=p, note='Detected in selected source/config files')
        return list(found.values())[:40]

    def _launch_plan(self, session, files, findings, target):
        stack=session.get('detected_stack') or []
        resolved=target if target!='auto' else ('Vercel + API host' if 'SvelteKit' in stack and 'FastAPI' in stack else 'Docker/Render' if 'FastAPI' in stack else 'Static/Vercel' if 'Node' in stack else 'Manual')
        readiness='blocked' if any(f.severity=='blocker' for f in findings) else 'caution' if any(f.severity in {'warning','suggestion'} for f in findings) else 'ready'
        build=[]
        if 'Node' in stack: build.append(CommandBlock(label='Frontend install/build', command='npm install --registry=https://registry.npmjs.org/ && npm run build', purpose='Verify frontend production compilation.'))
        if 'Python' in stack: build.append(CommandBlock(label='Backend install', command='python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt', purpose='Verify backend dependencies install cleanly.'))
        if 'FastAPI' in stack: build.append(CommandBlock(label='Backend start', command='python -m uvicorn main:app --host 127.0.0.1 --port 8000', purpose='Start API with production-like ASGI command.'))
        smoke=[CommandBlock(label='Health check', command='curl http://localhost:8000/health || curl http://localhost:8000/api/v1/health', purpose='Confirm API is reachable.'), CommandBlock(label='Frontend preview', command='npm run preview', purpose='Serve production frontend build locally before deployment.')]
        pre=['Resolve all blocker findings','Create/update .env.example files','Run clean install in a new environment','Run frontend build and backend startup','Confirm deployment target and port binding','Verify CORS origins and API base URL']
        post=['Open deployed frontend URL','Call health endpoint','Run one core user workflow','Check server logs for startup/runtime exceptions','Verify no secrets are exposed in browser bundle','Record rollback command and previous deployment identifier']
        rollback=['Keep previous deployment active until smoke tests pass','Use provider rollback to previous build if health check fails','Revert env changes separately from code changes','Restore database from backup/snapshot if migration causes data issues']
        return {'deployment_target':resolved,'readiness':readiness,'environment_matrix':[x.model_dump() for x in self._env_matrix(files)],'build_commands':[x.model_dump() for x in build],'smoke_tests':[x.model_dump() for x in smoke],'rollback_plan':rollback,'predeploy_checklist':pre,'postdeploy_checklist':post}

    def _traces(self, findings):
        traces=[]
        for agent in ALLOWED_AGENTS:
            items=[f for f in findings if f.agent==agent]
            if not items: continue
            status='blocked' if any(f.severity=='blocker' for f in items) else 'warn' if any(f.severity in {'warning','suggestion'} for f in items) else 'pass'
            traces.append({'agent':agent,'status':status,'findings':len(items),'summary':'; '.join(i.title for i in items[:2])})
        return traces

    def _markdown(self, payload):
        lp=payload['launch_plan']
        lines=[f"# ShipGate Launch Readiness Report",'',f"**Score:** {payload['score']}/100",f"**Readiness:** {payload['readiness']}",'',payload['summary'],'','## Findings']
        for f in payload['findings']:
            lines += ['',f"### {f['severity'].upper()} — {f['title']}",f"- Agent: `{f['agent']}`",f"- File: `{f.get('file') or 'n/a'}`",f"- Evidence: {f['evidence']}",f"- Why: {f['why_it_matters']}",f"- Recommendation: {f['recommendation']}"]
            if f.get('command'): lines.append(f"- Command: `{f['command']}`")
        lines += ['','## Environment Matrix']
        for e in lp['environment_matrix']:
            lines.append(f"- `{e['name']}` — {e['exposure']} — {e['note']} ({e['source']})")
        lines += ['','## Predeploy Checklist']+[f"- [ ] {x}" for x in lp['predeploy_checklist']]
        lines += ['','## Smoke Tests']+[f"- `{x['command']}` — {x['purpose']}" for x in lp['smoke_tests']]
        lines += ['','## Rollback Plan']+[f"- {x}" for x in lp['rollback_plan']]
        return '\n'.join(lines).strip()+'\n'
