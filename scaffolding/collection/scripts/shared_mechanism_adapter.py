"""One trusted binary, shared Task timing or one-role PMU call; no dispatch."""
import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().with_name('shared_validation_adapter.py')
spec = importlib.util.spec_from_file_location('original_shared_adapter', BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
OPERATORS, ROLES = base.OPERATORS, base.ROLES


def mechanism_block(operator):
    stream = 'st' if operator == 'group_norm' else 'stream'
    check = 'C' if operator == 'group_norm' else 'Check'
    return f'''        if (!mechanism_role.empty()) {{
            if (std::getenv("APROF_TASK_PROFILE_DIR"))
                throw std::invalid_argument("mechanism capture cannot enable Task API profiling");
            if (mechanism_role == "baseline") launch_baseline({stream}, buffers);
            else launch_candidate({stream}, buffers);
            {check}(aclrtSynchronizeStream({stream}), "mechanism complete call");
            snapshot(mechanism_role.c_str(), {stream}, buffers);
        }} else {{
'''


def generated(operator, roles, headers):
    files = base.generated(operator, roles, headers)
    name = f'op_host/{operator}.asc'
    host = files[name].decode()
    arg = 'A(ac,av,' if operator == 'group_norm' else 'Arg(argc, argv, '
    host = base.exact(host, '        const char *cycle_text = std::getenv("APROF_SHARED_CYCLE");',
        f'''        const std::string mechanism_role = {arg}"--aprof-mechanism-role");
        if (!mechanism_role.empty() && mechanism_role != "baseline" && mechanism_role != "candidate")
            throw std::invalid_argument("unknown mechanism role");
        const char *cycle_text = mechanism_role.empty() ? std::getenv("APROF_SHARED_CYCLE") : "0";''')
    begin = host.index('        task_profile.Start(')
    end = host.index('        task_profile.Finish();', begin) + len('        task_profile.Finish();')
    # Preserve every byte of the existing timing branch; only surround it.
    host = host[:begin] + mechanism_block(operator) + host[begin:end] + '\n        }' + host[end:]
    files[name] = host.encode()
    return files


def expected(operator, sources, expected_roles, expected_headers):
    roles = base.checked_roles(operator, sources, expected_roles)
    headers = {name: (base.ASSETS / name).read_bytes() for name in base.HEADERS}
    if base.inventory(headers) != expected_headers:
        raise ValueError('trusted headers changed')
    return roles, generated(operator, roles, headers)


def proof_for(operator, sources, destination, roles, files, expected_roles, expected_headers):
    proof = base.assembly_proof(operator, sources, destination, roles, files, expected_roles, expected_headers)
    proof['producer_files'][str(Path(__file__).resolve())] = base.digest(Path(__file__).read_bytes())
    proof['purpose'] = 'draft_shared_task_and_single_role_mechanism'
    proof['mechanism_entry'] = {'flag': '--aprof-mechanism-role', 'roles': list(ROLES),
                              'calls': 1, 'snapshot_all_outputs': True, 'task_api_enabled': False}
    return proof


def assemble(operator, sources, destination, *, expected_roles, expected_headers):
    roles, files = expected(operator, sources, expected_roles, expected_headers)
    destination = Path(destination).absolute()
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        path = destination / 'source' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    proof = proof_for(operator, sources, destination, roles, files, expected_roles, expected_headers)
    (destination / 'source-review.json').write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    return proof


def source_identity(destination):
    destination = Path(destination).absolute()
    proof = json.loads((destination / 'source-review.json').read_text())
    sources = {r: Path(proof['roles'][r]['path']) for r in ROLES}
    expected_roles = {r: proof['roles'][r]['files'] for r in ROLES}
    roles, files = expected(proof['operator'], sources, expected_roles, proof['trusted_headers'])
    if base.tree(destination / 'source') != files or proof != proof_for(
            proof['operator'], sources, destination, roles, files, expected_roles, proof['trusted_headers']):
        raise ValueError('source or mechanical proof changed')
    return proof
