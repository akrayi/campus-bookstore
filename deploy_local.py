import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


REPO_URL = "https://github.com/akrayi/campus-bookstore.git"
RUNS_URL = (
    "https://api.github.com/repos/akrayi/campus-bookstore/"
    "actions/workflows/ci.yml/runs?branch=master&event=push&per_page=1"
)

KUBECTL = ["kubectl", "--context", "docker-desktop", "-n", "campus-bookstore"]
SERVICES = ("product-service", "order-service")
POLL_SECONDS = 120


def run(*args):
    subprocess.run(args, check=True)


def check_and_deploy(last_deployed):
    with urlopen(RUNS_URL, timeout=15) as response:
        runs = json.load(response)["workflow_runs"]

    if not runs or runs[0]["conclusion"] != "success":
        print("Waiting for the latest master CI run to pass.", flush=True)
        return last_deployed

    latest_run = runs[0]
    sha = latest_run["head_sha"]

    if sha == last_deployed:
        print(f"Already deployed {sha[:7]}. Waiting for a new commit.", flush=True)
        return last_deployed

    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / "source"
        run("git", "clone", "--quiet", "--depth", "1", "--branch", "master",
            REPO_URL, source)

        checked_out_sha = subprocess.check_output(
            ["git", "-C", source, "rev-parse", "HEAD"], text=True
        ).strip()

        if checked_out_sha != sha:
            print("A newer commit is on master. Waiting for its CI run.", flush=True)
            return last_deployed

        print(f"Deploying CI run {latest_run['run_number']}, commit {sha}", flush=True)

        # Build both images before updating either service.
        for service in SERVICES:
            image = f"campus-bookstore/{service}:{sha}"
            run("docker", "--context", "desktop-linux", "build",
                "-t", image, source / service)

        for service in SERVICES:
            image = f"campus-bookstore/{service}:{sha}"
            updates = [f"{service}={image}"]

            # The catalog init container uses the same image as the Product Service.
            if service == "product-service":
                updates.append(f"prepare-catalog={image}")

            run(*KUBECTL, "set", "image", f"deployment/{service}", *updates)
            run(*KUBECTL, "rollout", "status", f"deployment/{service}",
                "--timeout=180s")

    print(f"Both services rolled out successfully at {sha[:7]}.", flush=True)
    return sha


def watch():
    last_deployed = None
    print("Watching Bookstore CI every two minutes. Press Ctrl+C to stop.", flush=True)

    while True:
        try:
            last_deployed = check_and_deploy(last_deployed)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"Deployment check failed: {error}", flush=True)
            print("Will retry in two minutes.", flush=True)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        watch()
    except KeyboardInterrupt:
        print("\nDeployment watcher stopped.")