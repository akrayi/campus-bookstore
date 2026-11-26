"""Reproducible local deployment. Run from CMD: python scripts/deploy.py"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ('product-service', 'order-service', 'storefront')


def run(*args, capture=False, stdin=None):
    result = subprocess.run(args, cwd=ROOT, input=stdin, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        # Never echo stdin: it can contain a Secret.
        raise RuntimeError(f'Command failed: {args[0]} {args[1]}')
    return result.stdout if capture else None


def source_tag():
    digest = hashlib.sha256()
    for folder in ('product-service', 'order-service', 'frontend', 'shared'):
        for path in sorted((ROOT / folder).rglob('*')):
            if not path.is_file() or any(p in {'.venv', '__pycache__', 'node_modules'} for p in path.parts):
                continue
            if path.suffix in {'.db', '.pyc'}:
                continue
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return 'local-' + digest.hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', default='docker-desktop', choices=['docker-desktop'])
    parser.add_argument('--tag', help='Immutable image tag; default hashes the local source.')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    tag = args.tag or source_tag()
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', tag):
        parser.error('Invalid container image tag')
    if not (ROOT / 'tests/node_modules/yaml').exists():
        run('npm.cmd' if os.name == 'nt' else 'npm', 'ci', '--prefix', 'tests')
    run('node', 'tests/check_manifests.cjs')
    kube = ['kubectl', '--context', args.context, '--request-timeout=30s']
    nodes = json.loads(run(*kube, 'get', 'nodes', '-o', 'json', capture=True))
    if len(nodes['items']) != 1 or nodes['items'][0]['metadata']['name'] != 'docker-desktop':
        raise RuntimeError('This deployment requires the single-node Docker Desktop cluster.')
    engine = run('docker', 'info', '--format', '{{.OperatingSystem}}', capture=True)
    if 'Docker Desktop' not in engine:
        raise RuntimeError('Select the Docker Desktop Linux engine before building.')
    print(f'Deploying source image tag: {tag}', flush=True)
    if not args.skip_build:
        for service in SERVICES:
            folder = 'frontend' if service == 'storefront' else service
            context = str(ROOT / 'frontend') if service == 'storefront' else str(ROOT)
            dockerfile = str(ROOT / folder / 'Dockerfile')
            run('docker', 'build', '-f', dockerfile, '-t', f'campus-bookstore/{service}:{tag}', context)
    # Apply namespace first. Existing database credentials and volumes are retained.
    run(*kube, 'apply', '-f', 'k8s/namespace.yaml')
    existing = run(*kube, 'get', 'secret', 'orders-db-secret', '-n', 'campus-bookstore',
                   '--ignore-not-found', '-o', 'json', capture=True)
    if existing.strip():
        if not json.loads(existing).get('data', {}).get('POSTGRES_PASSWORD'):
            raise RuntimeError('Existing database Secret is missing POSTGRES_PASSWORD.')
    else:
        password = os.getenv('POSTGRES_PASSWORD', '')
        envfile = ROOT / '.env'
        if not password and envfile.exists():
            for line in envfile.read_text(encoding='utf-8-sig').splitlines():
                if line.startswith('POSTGRES_PASSWORD='):
                    password = line.partition('=')[2].strip().strip('\"\'')
                    break
        if not password:
            raise RuntimeError('For first deployment, set POSTGRES_PASSWORD in the ignored .env file.')
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
                  'metadata': {'name': 'orders-db-secret', 'namespace': 'campus-bookstore'},
                  'stringData': {'POSTGRES_PASSWORD': password}}
        run(*kube, 'apply', '-f', '-', stdin=json.dumps(secret))
    documents = []
    for path in sorted((ROOT / 'k8s').glob('*.yaml')):
        if path.name == 'namespace.yaml':
            continue
        text = path.read_text(encoding='utf-8-sig')
        for service in SERVICES:
            text = text.replace(f'campus-bookstore/{service}:1.0', f'campus-bookstore/{service}:{tag}')
        documents.append(text)
    # Images are built before any application workload changes.
    manifest = '\n---\n'.join(documents)
    run(*kube, 'apply', '--dry-run=server', '-f', '-', stdin=manifest)
    run(*kube, 'apply', '-f', '-', stdin=manifest)
    for service in ('orders-db', 'product-service', 'order-service', 'storefront'):
        run(*kube, '-n', 'campus-bookstore', 'rollout', 'status',
            f'deployment/{service}', '--timeout=240s')
    # A partial rollout is a failing deployment; no false success marker is recorded.
    run(*kube, '-n', 'campus-bookstore', 'annotate', 'deployment/storefront',
        f'bookstore/source-tag={tag}', '--overwrite')
    print('All four deployments are ready. Open the Kubernetes storefront with:')
    print('kubectl --context docker-desktop port-forward -n campus-bookstore svc/storefront 3002:80')


if __name__ == '__main__':
    main()
