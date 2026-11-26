"""Bounded CPU load to demonstrate the real Order Service HPA; no database writes."""
import subprocess
import time
import json

KUBE = ['kubectl', '--context', 'docker-desktop', '--request-timeout=20s', '-n', 'campus-bookstore']


def main():
    # Burn roughly 20% of one CPU core instead of saturating the laptop.
    code = ('import time\nend=time.monotonic()+120\n'
            'while time.monotonic()<end:\n'
            ' start=time.monotonic()\n'
            ' while time.monotonic()-start<0.02: pass\n'
            ' time.sleep(max(0,0.1-(time.monotonic()-start)))')
    print('Generating bounded CPU load for 120 seconds. The HPA should scale above one replica.', flush=True)
    load = subprocess.Popen([*KUBE, 'exec', 'deployment/order-service', '--', 'python', '-c', code])
    maximum = 1
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                raw = subprocess.check_output([*KUBE, 'get', 'hpa', 'order-service-hpa', '-o', 'json'], text=True)
            except subprocess.CalledProcessError:
                print('API server busy; retrying within the five-minute observation window.', flush=True)
                time.sleep(5)
                continue
            status = json.loads(raw)['status']
            current = status.get('currentReplicas', 1)
            maximum = max(maximum, current)
            print(f'Current replicas: {current}, desired: {status.get("desiredReplicas")}', flush=True)
            if maximum >= 2 and load.poll() is not None:
                break
            time.sleep(5)
    finally:
        # The remote workload always has its own deadline, even if this CLI is interrupted.
        load.wait(timeout=150)
    if maximum < 2:
        raise RuntimeError('No HPA scale-up observed. Check metrics-server and CPU requests.')
    print(f'PASS: observed {maximum} replicas. HPA will return to minimum as CPU falls.')


if __name__ == '__main__':
    main()
