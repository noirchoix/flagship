from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any
from fastapi import UploadFile
from ai_suite.modules.workflow.core.config import settings
from ai_suite.modules.workflow.repositories.store import Store

SAFE_LIMIT_BYTES = 80 * 1024 * 1024
MAX_FILES = 2500
TEXT_EXTS = {'.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.py', '.ts', '.js', '.svelte', '.html', '.css', '.env', '.example'}

DEFAULT_NAMES = {
    'readme.md', 'package.json', 'requirements.txt', 'pyproject.toml', 'vite.config.ts',
    'svelte.config.js', 'app.html', '.env.example', 'dockerfile', 'docker-compose.yml',
    'main.py', 'client.ts', '+page.svelte', 'workflow.json', 'workflows.json'
}

class ContextService:
    def __init__(self, store: Store):
        self.store = store

    def _safe_extract(self, zip_path: Path, dest: Path) -> None:
        total = 0
        count = 0
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                count += 1
                if count > MAX_FILES:
                    raise ValueError(f'ZIP contains more than {MAX_FILES} files')
                total += info.file_size
                if total > SAFE_LIMIT_BYTES:
                    raise ValueError('ZIP is larger than the safe extraction limit')
                name = info.filename.replace('\\', '/')
                if name.startswith('/') or '..' in Path(name).parts:
                    raise ValueError(f'Unsafe ZIP path: {info.filename}')
            zf.extractall(dest)

    def _kind(self, path: Path) -> str:
        lower = path.name.lower()
        if lower == 'package.json': return 'node_manifest'
        if lower in {'requirements.txt', 'pyproject.toml'}: return 'python_manifest'
        if lower in {'.env.example', '.env.sample'}: return 'environment'
        if lower in {'dockerfile', 'docker-compose.yml'}: return 'deployment'
        if '.github' in path.parts: return 'ci'
        if path.suffix in {'.md', '.txt'}: return 'documentation'
        if path.suffix in {'.ts', '.js', '.svelte', '.py'}: return 'source'
        if path.suffix in {'.json', '.yml', '.yaml', '.toml'}: return 'config'
        return 'file'

    def _detect_stack(self, files: list[dict[str, Any]]) -> list[str]:
        names = {Path(f['path']).name.lower() for f in files}
        paths = {f['path'].lower() for f in files}
        stack = []
        if 'package.json' in names: stack.append('Node')
        if 'svelte.config.js' in names or any('+page.svelte' in p for p in paths): stack.append('SvelteKit')
        if 'requirements.txt' in names or 'pyproject.toml' in names: stack.append('Python')
        if any(p.endswith('main.py') for p in paths): stack.append('FastAPI')
        if 'dockerfile' in names or 'docker-compose.yml' in names: stack.append('Docker')
        if any('.github/workflows' in p for p in paths): stack.append('GitHub Actions')
        return stack or ['Repository']

    def _default_targets(self, files: list[dict[str, Any]]) -> list[str]:
        selected = []
        for f in files:
            name = Path(f['path']).name.lower()
            p = f['path'].lower()
            if name in DEFAULT_NAMES or 'router' in p or 'service' in p or 'schema' in p or 'workflow' in p:
                selected.append(f['path'])
        return selected[:80]

    async def upload(self, file: UploadFile) -> dict[str, Any]:
        if not file.filename or not file.filename.lower().endswith('.zip'):
            raise ValueError('Upload a .zip repository archive')
        session_id = uuid.uuid4().hex[:12]
        workdir = settings.upload_dir / session_id
        if workdir.exists(): shutil.rmtree(workdir)
        workdir.mkdir(parents=True)
        zip_path = workdir / 'repo.zip'
        with zip_path.open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        extract_dir = workdir / 'repo'
        extract_dir.mkdir()
        self._safe_extract(zip_path, extract_dir)
        zip_path.unlink(missing_ok=True)

        all_files = []
        for path in extract_dir.rglob('*'):
            if path.is_file() and path.stat().st_size <= 2_000_000:
                rel = path.relative_to(extract_dir).as_posix()
                if path.suffix.lower() in TEXT_EXTS or path.name.lower() in DEFAULT_NAMES or '.github/workflows' in rel.lower():
                    all_files.append({'path': rel, 'kind': self._kind(path), 'size': path.stat().st_size})
        all_files.sort(key=lambda x: x['path'])
        repo_name = Path(file.filename).stem
        stack = self._detect_stack(all_files)
        self.store.insert_session(session_id, repo_name, str(extract_dir), all_files, stack)
        return {'session_id': session_id, 'repo_name': repo_name, 'file_count': len(all_files), 'default_targets': self._default_targets(all_files), 'detected_stack': stack}

    def files(self, session_id: str) -> dict[str, Any]:
        files = self.store.list_files(session_id)
        if not files:
            raise ValueError('Session not found or has no readable files')
        return {'session_id': session_id, 'files': files, 'default_targets': self._default_targets(files)}

    def read_selected(self, session_id: str | None, paths: list[str], limit_chars: int = 60000) -> dict[str, str]:
        if not session_id:
            return {}
        session = self.store.get_session(session_id)
        if not session:
            return {}
        root = Path(session['root_path']).resolve()
        content: dict[str, str] = {}
        budget = limit_chars
        for rel in paths[:60]:
            target = (root / rel).resolve()
            if not str(target).startswith(str(root)) or not target.exists() or not target.is_file():
                continue
            txt = target.read_text(errors='ignore')[:8000]
            if budget <= 0: break
            content[rel] = txt[:budget]
            budget -= len(content[rel])
        return content
