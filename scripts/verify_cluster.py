"""Read-only infrastructure checks. Exits nonzero for an unenforced policy."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
KUBE = ['kubectl', '--context', 'docker-desktop', '--request-timeout=20s']


def out(*args):
    return subprocess.check_output([*KUBE, *args], cwd=ROOT, text=True).strip()


def probe(deployment, host, port, allowed):
    script = ("import socket,sys; s=socket.socket(); s.settimeout(4); "
              f"result=s.connect_ex(('{host}',{port})); s.close(); "
              f"print(result); sys.exit(0 if (result == 0) == {allowed!r} else 1)")
    out('exec', '-n', 'campus-bookstore', f'deployment/{deployment}', '-c', deployment,
        '--', 'python', '-c', script)
    print(f'PASS: {deployment} -> {host}:{port}: {"allowed" if allowed else "blocked"}')


def main():
    deployments = json.loads(out('get', 'deployments', '-n', 'campus-bookstore', '-o', 'json'))
    names = {d['metadata']['name'] for d in deployments['items']}
    assert {'storefront', 'product-service', 'order-service', 'orders-db'} <= names
    for d in deployments['items']:
        assert d['status'].get('availableReplicas', 0) >= 1, d['metadata']['name']
    print('PASS: all four deployments available')
    catalog = json.loads(out('exec', '-n', 'campus-bookstore', 'deployment/storefront',
                             '--', 'wget', '-q', '-O-', 'http://127.0.0.1:8080/api/products'))
    assert isinstance(catalog.get('products'), list)
    print('PASS: Kubernetes storefront proxies a real catalog response')
    assert out('auth', 'can-i', 'list', 'pods', '-n', 'campus-bookstore',
               '--as=system:serviceaccount:campus-bookstore:bookstore-reader') == 'yes'
    result = subprocess.run([*KUBE, 'auth', 'can-i', 'delete', 'pods', '-n', 'campus-bookstore',
                             '--as=system:serviceaccount:campus-bookstore:bookstore-reader'],
                            capture_output=True, text=True)
    assert result.stdout.strip() == 'no'
    print('PASS: RBAC allows list and denies delete')
    probe('order-service', 'orders-db', 5432, True)
    probe('order-service', 'product-service', 5001, True)
    probe('product-service', 'orders-db', 5432, False)
    probe('product-service', 'order-service', 5002, False)
    hpa = json.loads(out('get', 'hpa', 'order-service-hpa', '-n', 'campus-bookstore', '-o', 'json'))
    assert any(c['type'] == 'ScalingActive' and c['status'] == 'True'
               for c in hpa['status']['conditions'])
    print('PASS: HPA has live resource metrics')


if __name__ == '__main__':
    main()
