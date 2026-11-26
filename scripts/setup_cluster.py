"""Enable local resource metrics and enforce NetworkPolicies in Docker Desktop."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KUBE = ['kubectl', '--context', 'docker-desktop', '--request-timeout=30s']


def run(*args, capture=False):
    result = subprocess.run([*KUBE, *args], cwd=ROOT, text=True, check=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout


def main():
    nodes = json.loads(run('get', 'nodes', '-o', 'json', capture=True))
    if len(nodes['items']) != 1 or nodes['items'][0]['metadata']['name'] != 'docker-desktop':
        raise RuntimeError('This installer is restricted to the Docker Desktop node.')
    run('apply', '--dry-run=server', '-f', 'infra/network-policy-controller.yaml')
    run('apply', '-f', 'infra/network-policy-controller.yaml')
    run('rollout', 'status', 'daemonset/kube-router', '-n', 'kube-system', '--timeout=180s')
    existing = run('get', 'deployment', 'metrics-server', '-n', 'kube-system',
                   '--ignore-not-found', '-o', 'name', capture=True)
    if not existing.strip():
        run('apply', '-f', 'https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.1/components.yaml')
        # Docker Desktop's local kubelet certificate is not trusted by metrics-server.
        patch = {'spec': {'template': {'spec': {'containers': [{'name': 'metrics-server',
                 'args': ['--cert-dir=/tmp', '--secure-port=10250', '--kubelet-preferred-address-types=InternalIP,Hostname',
                          '--kubelet-use-node-status-port', '--metric-resolution=15s', '--kubelet-insecure-tls']}]}}}}
        run('patch', 'deployment/metrics-server', '-n', 'kube-system', '--type=strategic', '-p', json.dumps(patch))
    run('rollout', 'status', 'deployment/metrics-server', '-n', 'kube-system', '--timeout=180s')
    print('Cluster prerequisites ready. Run python scripts/deploy.py next.')


if __name__ == '__main__':
    main()
