"""Install pinned local monitoring, centralized logging and API dashboards."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    # Every cluster operation explicitly names the local context.
    kube = ['kubectl', '--context', 'docker-desktop', '--request-timeout=30s']
    run(*kube, 'apply', '-f', 'infra/monitoring-namespace.yaml')
    run('helm', 'repo', 'add', 'prometheus-community', 'https://prometheus-community.github.io/helm-charts')
    run('helm', 'repo', 'add', 'grafana', 'https://grafana.github.io/helm-charts')
    run('helm', 'repo', 'update')
    run('helm', 'upgrade', '--install', 'bookstore-monitoring',
        'prometheus-community/kube-prometheus-stack', '--version', '93.9.0',
        '--kube-context', 'docker-desktop', '-n', 'monitoring',
        '-f', 'monitoring/stack-values.yaml', '--wait', '--timeout', '5m')
    run(*kube, 'apply', '-f', 'monitoring/loki.yaml')
    run('helm', 'upgrade', '--install', 'bookstore-alloy', 'grafana/alloy',
        '--version', '1.16.0', '--kube-context', 'docker-desktop', '-n', 'monitoring',
        '-f', 'monitoring/alloy-values.yaml', '--wait', '--timeout', '5m')
    run(*kube, 'apply', '-f', 'monitoring/service-monitors.yaml')
    run(*kube, 'apply', '-f', 'monitoring/dashboard.yaml')
    run(*kube, '-n', 'monitoring', 'rollout', 'status', 'deployment/bookstore-loki', '--timeout=180s')


if __name__ == '__main__':
    main()
