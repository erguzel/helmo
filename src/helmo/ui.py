import sys
from importlib.metadata import version, PackageNotFoundError
import click
from helmo.validate import file_exists, suffix_exists, is_path_or_file
class Icons:
    SUCCESS = "✅"
    FAILURE = "❌"
    WARNING = "⚠️"
    ROCKET  = "🚀"

def get_app_version():
    try:
        # Replace 'your-package-name' with the name in pyproject.toml
        return version("helmo")
    except PackageNotFoundError:
        return "0.0.0-dev"


def file_existence_ui_validate(file, message=''):
    message = message if message else f"File {file} does not exist."
    if not file_exists(file):
        click.secho(f"{Icons.FAILURE} {message}", fg="red", underline=False)
        sys.exit(1)
def file_extensions_ui_validate(file,*suffixes,message=''):
    message = message if message else f"File {file} is not in expected format. Expected: path/to/file-name{[*suffixes]}"
    if not suffix_exists(file,*suffixes):
        click.secho(f"{Icons.FAILURE} {message}", fg="red", underline=False)
        sys.exit(1)
def deployment_args_ui_validate(deployments,message=''):
    any_forbidden_release_name = any([is_path_or_file(rn) for rn in deployments])
    if any_forbidden_release_name:
        message = message if message else f"Release names {deployments} is not in expected format. Expected release-name format."
        click.secho(f"{Icons.FAILURE} {message}", fg="red", underline=False)
        sys.exit(1)
def serial_releases_file_ui_validate(releases, message=''):
    if not releases or releases == 'None':
        message = message if message else "Helmo serial deployments yaml file can not be null or empty. Either give it with -r option or set environment variable 'HELMO_SERIAL_RELEASES_YAML' with the absolute path of the file."
        click.secho(f"{Icons.FAILURE} {message}", fg="red", underline=False)
        sys.exit(1)



class HelpMessages:
    SUFFIX = 'Suffix to version latest values manifests files along with a timestamp.'
    DRYRUN = 'Reports what would be done without creating, writing or deleting anything.'
    YES = 'Confirms all prompts.'
    HELM_ACTION = 'install, upgrade and uninstall are helm actions.'
    HELM_VALUES = 'Additional values files to override main chart. Additional yaml files will apply to all given deployments. If there are conflicting fields in additional yamls, consider manual deployment for each release.'
    HELMO_SERIAL_RELEASES_YAML = 'HELMO_SERIAL_RELEASES_YAML file which defines multiple deployments. You do not need to give it if you set environment variable HELMO_SERIAL_RELEASES_YAML to absolute path of the file. Type helmo --defaults to see default file formats.'
    INIT_FILE = 'release-name.helmo init file of a deployment. See helmo --defaults for file formats.'
    ENVIRONMENT = 'The target environment for the execution: prod or test. It selects the matching <ENV>_CONTEXT entry of the .helmo init file.'
    WAIT = 'Wait timeout for deployed resources i.e. 10m, 5s etc. Default is 10s.'
    QUIET = 'Runs with minimal output.'
    REGISTRY_URL = 'Schemeless url of the registry like mydomain.myregistry.com. Default is the 1st entry machine name in ~/.netrc file'
    REGISTRY_REPO = 'Image-repository name in registry'
    REGISTRY_REPO_TAG = 'Tag of the repository in registry.'
    KUBERNETES_CONTEXT = 'Kubernetes cluster config context.'
    KUBERNETES_SECRET_OVERRIDE = 'Overrides existing secret if exists.'
    KUBERNETES_SECRET_FILE = 'Secret file.'
    KUBERNETES_SECRET_TITLE = 'Name for the secret.'
    KUBERNETES_NAMESPACE = 'Namespace for the secret. Creates the namespace if it does not exist.'
    KUBERNETES_JOB_NAME = 'Name of the job in kubernetes to create new job using it. Job must already exists in desired namespace.'
    KUBERNETES_POD_NAME = 'Name of the pod in kubernetes.'
    KUBERNETES_CONTAINER_NAME = 'Name of the container in the pod.'
    KUBERNETES_DELETE_NAMESPACE = 'Deletes the namespace of the deployment after uninstall.'