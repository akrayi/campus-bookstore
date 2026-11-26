# Continuous integration and local deployment

GitHub-hosted CI runs on pushes and pull requests to master. It installs locked
test dependencies, validates manifests, runs both API unit suites, builds the
images, starts isolated Compose services, executes integration/end-to-end and
browser tests, then removes only its test project. It never connects to the demo
database. The observability unit tests also run in unittest discovery.

## Direct deployment from GitHub Actions

The deploy-local job depends on successful tests and only runs for master push
or manual events when ENABLE_LOCAL_DEPLOY=true. It uses a self-hosted Windows
runner labeled campus-bookstore. Pull requests never enter this laptop job.
All cluster commands explicitly target docker-desktop. The exact tested commit
is checked out, built into commit-tagged images, and deployed with scripts/deploy.py.
The job then verifies availability, RBAC, policy enforcement and live HPA metrics.
Deployments are serialized and failed rollouts fail the job.

Repository configuration is an external prerequisite, not something a YAML file
can register automatically. In GitHub > repository > Settings > Actions > Runners,
add a Windows x64 self-hosted runner on this laptop. Follow GitHub's generated
download/registration commands, adding the campus-bookstore label. Keep its
registration token private. The runner's account needs Docker, kubectl, Python
and the existing Docker Desktop kubeconfig. Run the runner while demonstrating.
Do not accept workflows from untrusted branches or run pull request jobs there.

Add the repository Actions variable ENABLE_LOCAL_DEPLOY with value true. For a
brand-new database also add the BOOKSTORE_POSTGRES_PASSWORD Actions secret; an
existing cluster Secret is reused and is never overwritten. Push reviewed changes
to master, then show build-and-test and deploy-local succeeding for the same SHA.
No repository variable or runner is registered by merely editing local files.

## Alternative local deployment watcher

`python deploy_local.py` polls successful master push CI runs every two minutes.
It clones the exact tested commit, checks its SHA, and runs that checkout's
deployment script to build and deploy all application components. Keep the watcher
terminal open. Its first deployment needs a pre-created database Secret; bootstrap
the cluster once using scripts/deploy.py from your regular checkout first.

After these changes are pushed, run the watcher to demonstrate:

```cmd
python deploy_local.py
```

Press Ctrl+C to stop. Running a watcher against a remote commit older than these
changes does not deploy the new code. Do not claim end-to-end CI/CD evidence until
the tested remote SHA and deployed images match.
