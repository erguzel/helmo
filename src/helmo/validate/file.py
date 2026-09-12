import netrc, yaml
from dotenv import load_dotenv
from helmo.validate import RegistryAuthConfigModel, HelmoInitFileModel, NetrcEntryModel,HelmoReleasesYamlFileModel
from pydantic import ValidationError

def safe_load_helmo_releases_yaml_file(yaml_file)->HelmoReleasesYamlFileModel:
    yaml_content=[]
    with open(yaml_file) as file:
        yaml_content = yaml.safe_load(file)
    validated = HelmoReleasesYamlFileModel(**yaml_content)
    return validated

def releases_yaml_format_validate(yaml_content:dict):
    try:
        HelmoInitFileModel(**yaml_content)
    except ValidationError as e:
        e.add_note("Yaml file must be in exact format.")
        raise e

def load_validated_netrc(path: str = "~/.netrc"):
    try:
        raw_netrc = netrc.netrc(path)
        validated_entries = []
        for host, data in raw_netrc.hosts.items():
            # netrc returns a tuple: (login, account, password)
            entry = NetrcEntryModel(
                machine=host,
                login=data[0],
                account=data[1],
                password=data[2]
            )
            validated_entries.append(entry)
        
        return validated_entries

    except (netrc.NetrcParseError, FileNotFoundError) as e:
        e.add_note(f"Netrc file {path} does not exists or not in correct format. Inspect file and retry.")
        raise e from e

def docker_auth_config_format_validate(json_content:RegistryAuthConfigModel):
    try:
        return RegistryAuthConfigModel.model_validate_json(json_content)
    except ValidationError as e:
        e.add_note("Docker auth json file must be in correct format.")
        raise e

def ensure_helmo_init_file_format(init_file, load = False,override=False):
    #release_file = ensure_file(release_file,'.helmo')
    settings = None
    try:
        settings = HelmoInitFileModel(_env_file=init_file,_env_file_encoding='utf-8')
    except ValidationError as e:
        e.add_note(f"Release file {init_file} is not in expected format. Release file must have these variables with valid values: {[
            "TEST_CONTEXT",
            "PROD_CONTEXT",
            "CHART_VERSION",
            "APP_VERSION",
            "REPO_URL",
            "REPOSITORY_NAME",
            "CHART_NAME",
            "NAMESPACE",
        ]}")
        raise e from e
    if load:
        load_dotenv(init_file,override=override)
    
    return settings