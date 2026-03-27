from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_client_pilot_root(client: str, pilot: str) -> Path:
    return get_project_root() / "data" / "clients" / client / pilot


def get_raw_dir(client: str, pilot: str) -> Path:
    return get_client_pilot_root(client, pilot) / "raw"


def get_config_dir(client: str, pilot: str) -> Path:
    return get_client_pilot_root(client, pilot) / "config"


def get_processed_dir(client: str, pilot: str) -> Path:
    path = get_client_pilot_root(client, pilot) / "processed"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_outputs_dir(client: str, pilot: str) -> Path:
    path = get_client_pilot_root(client, pilot) / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir(client: str, pilot: str) -> Path:
    path = get_client_pilot_root(client, pilot) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path