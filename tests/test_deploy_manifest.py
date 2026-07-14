"""Guard: every local module cloud/api-proxy.py imports must be shipped by cloud/deploy.sh.

deploy.sh scp's a hand-maintained list of proxy modules to the VPS. If someone adds an import to
api-proxy.py but forgets to add the file to deploy.sh (as happened with verify_gate.py), the next
deploy ships a proxy that ImportErrors on startup — the restart leaves it DOWN and the deploy's
health check fails. This test turns that latent production outage into a fast, offline CI failure.

Pure stdlib; runs in the same offline suite as the rest of tests/.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLOUD = REPO / "cloud"


def _local_module_names():
    return {p.stem for p in CLOUD.glob("*.py")}


def _proxy_local_imports():
    src = (CLOUD / "api-proxy.py").read_text()
    local = _local_module_names()
    imported = set()
    for m in re.finditer(r"^(?:from|import)\s+(\w+)", src, re.M):
        if m.group(1) in local:
            imported.add(m.group(1))
    return imported


def _deploy_shipped():
    src = (REPO / "cloud" / "deploy.sh").read_text()
    # Matches: scp -q "${HERE}/<name>.py" "${CLOUD}:${APIDIR}/..."
    return {m.group(1) for m in re.finditer(r'/(\w+)\.py"\s+"\$\{CLOUD\}', src)}


def test_every_imported_proxy_module_is_deployed():
    imported = _proxy_local_imports()
    shipped = _deploy_shipped()
    missing = imported - shipped
    assert not missing, (
        f"cloud/api-proxy.py imports {sorted(missing)} but cloud/deploy.sh does not scp "
        f"them. The next deploy would ImportError on startup. Add an scp line to deploy.sh."
    )
