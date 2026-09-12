
import os
import sys
from loguru import logger
import click
import helmo.ui as ui
import helmo.logic.helmo as helm
import helmo.logic.registry as docker
import helmo.logic.k8s as k8s
from helmo.validate import load_validated_netrc,ensure_file

def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=True,
        
    )

#TODO:
#Error messages-> message!r for additional quoted data
#--defaults for showing default file formats, serial-deployments.yaml, .netrc, .helmo
#--examples of commands
#region CLI COMMANDS
@click.version_option(version=ui.get_app_version(), message="%(prog)s %(version)s")
@click.group()
@logger.catch(onerror=lambda _: sys.exit(1))
def cli():
    """
    Helmo cli is for managing:\n
    - Serial-manual helm install-update-upgrade operations with auto versioning latest manifests.\n
    - Remote registry for listing-deleting repos, images, tags digests.\n
    - Kubernetes operations.
    """
    setup_logging()
@cli.group()
@logger.catch(onerror=lambda _: sys.exit(1))
def serial():
    """
    Performs serial helm actions for multiple releases.
    """


@serial.command()
@click.option(
    '--helmo-releases-yaml', '-f',
    default = f"{os.environ.get("HELMO_SERIAL_RELEASES_YAML")}",
    required=True,
    help=ui.HelpMessages.HELMO_SERIAL_RELEASES_YAML
)
@click.option('--values', '-v', multiple=True, help=ui.HelpMessages.HELM_VALUES)
@click.option('--suffix','-s', default= '', help=ui.HelpMessages.SUFFIX)
@click.option('--dryrun','-d', is_flag=True, default=False, help= ui.HelpMessages.DRYRUN)
@click.option('--yes','-y', is_flag=True, default=False, help=ui.HelpMessages.YES)
@click.argument('deployments', nargs=-1,required=True)
def install(helmo_releases_yaml,values,suffix,dryrun,yes,deployments):
    """
    Installs given helm releases according to the information in serial-releases.yaml
    """
    action = 'install'
    ui.serial_releases_file_ui_validate(helmo_releases_yaml,"HELMO_SERIAL_RELEASES_YAML file can not be null or empty. Either give it with -r option or set environment variable 'HELMO_SERIAL_RELEASES_YAML' with the absolute path of the file.")
    ui.file_extensions_ui_validate(helmo_releases_yaml,".yaml",".yml",message=f"HELMO_SERIAL_RELEASES_YAML file {helmo_releases_yaml} is not in expected format. Expected formats: yaml, .yml")
    ui.file_existence_ui_validate(helmo_releases_yaml,f"HELMO_SERIAL_RELEASES_YAML file {helmo_releases_yaml} does not exist.")
    ui.deployment_args_ui_validate(deployments,message=f"Paths or files are not accepted as release names {deployments}.")

    for file in values:
        ui.file_extensions_ui_validate(file,'.yaml',".yml",message=f"Additional values file {file} is not in expected format. Expected formats: yaml, .yml")
        ui.file_existence_ui_validate(file,f"Additional values file {file} does not exist.")

    if not yes:
        if click.confirm(f"{ui.Icons.WARNING}  Serial helm action requires pre-configuration per deployment. Have you done it already? For more info 'helmo init --help' "):
            click.secho(f"  {ui.Icons.ROCKET} Serial helm action '{action}' begins for {[*deployments]}.",color='yellow')
        else:
            click.secho(f"  {ui.Icons.FAILURE} Serial helm action '{action}' cancelled for {[*deployments]}.",color='red')
            raise click.Abort()
  
    helm.serial_deploy_logic(
        action=action,
        releases_file=helmo_releases_yaml,
        values = values,
        deployments=deployments,
        suffix = suffix,
        dryrun = dryrun
    )

@serial.command()
@click.option(
    '--helmo-releases-yaml', '-f',
    default = f"{os.environ.get("HELMO_SERIAL_RELEASES_YAML")}",
    required=True,
    help=ui.HelpMessages.HELMO_SERIAL_RELEASES_YAML
)
@click.option('--values', '-v', multiple=True, help=ui.HelpMessages.HELM_VALUES)
@click.option('--suffix','-s', default= '', help=ui.HelpMessages.SUFFIX)
@click.option('--dryrun','-d', is_flag=True, default=False, help= ui.HelpMessages.DRYRUN)
@click.option('--yes','-y', is_flag=True, default=False, help=ui.HelpMessages.YES)
@click.argument('deployments', nargs=-1,required=True)
def upgrade(helmo_releases_yaml,values,suffix,dryrun,yes,deployments):
    """
    Upgrades given helm releases according to the information in serial-releases.yaml
    """
    action = 'upgrade'
    ui.serial_releases_file_ui_validate(helmo_releases_yaml,"HELMO_SERIAL_RELEASES_YAML file can not be null or empty. Either give it with -r option or set environment variable 'HELMO_SERIAL_RELEASES_YAML' with the absolute path of the file.")
    ui.file_extensions_ui_validate(helmo_releases_yaml,".yaml",".yml",message=f"HELMO_SERIAL_RELEASES_YAML file {helmo_releases_yaml} is not in expected format. Expected formats: yaml, .yml")
    ui.file_existence_ui_validate(helmo_releases_yaml,f"HELMO_SERIAL_RELEASES_YAML file {helmo_releases_yaml} does not exist.")
    ui.deployment_args_ui_validate(deployments,message=f"Paths or files are not accepted as release names {deployments}.")

    for file in values:
        ui.file_extensions_ui_validate(file,'.yaml',".yml",message=f"Additional values file {file} is not in expected format. Expected formats: yaml, .yml")
        ui.file_existence_ui_validate(file,f"Additional values file {file} does not exist.")

    if not yes:
        if click.confirm(f"{ui.Icons.WARNING}  Serial helm action requires pre-configuration per deployment. Have you done it already? For more info 'helmo init --help' "):
            click.secho(f"  {ui.Icons.ROCKET} Serial helm action '{action}' begins for {[*deployments]}.",color='yellow')
        else:
            click.secho(f"  {ui.Icons.FAILURE} Serial helm action '{action}' cancelled for {[*deployments]}.",color='red')
            raise click.Abort()
  
    helm.serial_deploy_logic(
        action=action,
        releases_file=helmo_releases_yaml,
        values=values,
        deployments=deployments,
        suffix = suffix,
        dryrun = dryrun
    )

@serial.command()
@click.option(
    '--helmo-releases-yaml', '-f',
    default = f"{os.environ.get("HELMO_SERIAL_RELEASES_YAML")}",
    required=True,
    help=ui.HelpMessages.HELMO_SERIAL_RELEASES_YAML
)
@click.option('--dryrun','-d', is_flag=True, default=False, help= ui.HelpMessages.DRYRUN)
@click.option('--yes','-y', is_flag=True, default=False, help=ui.HelpMessages.YES)
@click.option('--deletenamespace','-del', is_flag=True, default=False, help=ui.HelpMessages.KUBERNETES_DELETE_NAMESPACE)
@click.argument('deployments', nargs=-1,required=True)
def uninstall(helmo_releases_yaml,dryrun,yes,deletenamespace,deployments):
    """
    Uninstalls given deployment release names.
    """
    action = 'uninstall'
    ui.serial_releases_file_ui_validate(helmo_releases_yaml,"HELMO_SERIAL_RELEASES_YAML file can not be null or empty. Either give it with -r option or set environment variable 'HELMO_SERIAL_RELEASES_YAML' with the absolute path of the file.")
    ui.file_extensions_ui_validate(helmo_releases_yaml,".yaml",".yml",message=f"HELMO_SERIAL_RELEASES_YAML file {helmo_releases_yaml} is not in expected format. Expected formats: yaml, .yml")
    ui.file_existence_ui_validate(helmo_releases_yaml,f"HELMO_SERIAL_RELEASES_YAML file {helmo_releases_yaml} does not exist.")
    ui.deployment_args_ui_validate(deployments,message=f"Paths or files are not accepted as release names {deployments}.")
    if not yes:
        if click.confirm(f"{ui.Icons.WARNING}  Serial helm action requires pre-configuration per deployment. Have you done it already? For more info 'helmo init --help' "):
            click.secho(f"  {ui.Icons.ROCKET} Serial helm action '{action}' begins for {[*deployments]}.",color='yellow')
        else:
            click.secho(f"  {ui.Icons.FAILURE} Serial helm action '{action}' cancelled for {[*deployments]}.",color='red')
            raise click.Abort()

    helm.uninstall_logic(releases_file=helmo_releases_yaml,
                         deployments=deployments,
                         delete_namespace=deletenamespace,
                         dryrun=dryrun)
@cli.command()
@click.option('--initfile','-i', required=True, help=ui.HelpMessages.INIT_FILE)
@click.option(
    '--env', '-e',
    type=click.Choice(['prod', 'staging', 'test'], case_sensitive=True),
    required=True,
    help=ui.HelpMessages.ENVIRONMENT
)
@click.option(
    '--action','-a', 
    type=click.Choice(['install', 'upgrade', 'uninstall'], case_sensitive=True),
    required=True,
    help=ui.HelpMessages.HELM_ACTION
)
@click.option('--wait','-w', default='2m', help=ui.HelpMessages.WAIT)
@click.option('--suffix','-s', default='', help=ui.HelpMessages.SUFFIX)
@click.option('--quiet','-q', is_flag=True, default=False, help=ui.HelpMessages.QUIET)
@click.option('--yes','-y', is_flag=True, default=False, help=ui.HelpMessages.YES)
@click.option('--dryrun','-d', is_flag=True, default=False, help=ui.HelpMessages.DRYRUN)
@click.option('--values', '-v', multiple=True, help=ui.HelpMessages.HELM_VALUES)
def manual(initfile,env,action,wait,suffix,quiet,yes,dryrun,values):
    """
    A cli.deploy command to manage a single manual deployment.
    """
    ui.file_extensions_ui_validate(initfile,".helmo",message=f"Release file {initfile} is not in expected format. Expected: path/to/file-name.helmo")
    ui.file_existence_ui_validate(initfile, message=f"Release file {initfile} does not exist.")
    for file in values:
        ui.file_extensions_ui_validate(file,'.yaml',".yml",message=f"Additional values file {file} is not in expected format. Expected: path/to/file-name.(yaml|yml)")
        ui.file_existence_ui_validate(file, message=f"Additional values file {file} does not exist.")
 
    if env=="prod":
        if not yes:
            if click.confirm(f'{ui.Icons.WARNING}  Do you want to continue deployment to {env.upper()} context?'):
                click.secho(f"  {ui.Icons.ROCKET} Deploying to {env.upper()} context.",color='yellow')
            else:
                click.secho(f"  {ui.Icons.FAILURE} Deployment cancelled.",color='red')
                raise click.Abort()
    helm.manual_deploy_logic(release_file=initfile,
                        environment=env,
                        helm_action=action,
                        additional_values=values,
                        wait=wait,
                        suffix=suffix,
                        quiet=quiet,
                        dryrun = dryrun
                        )
"""
def init(init,env,suffix,quiet) TODO: Make env optional current context, add help
"""
@cli.command()
@click.option('--initfile','-i', required=True, help=ui.HelpMessages.INIT_FILE)
@click.option(
    '--env', '-e',
    type=click.Choice(['prod', 'staging', 'test'], case_sensitive=True),
    required=True,
    help = ui.HelpMessages.ENVIRONMENT
)
@click.option('--suffix','-s', default= '', help=ui.HelpMessages.SUFFIX)
@click.option('--quiet','-q', is_flag= True, help=ui.HelpMessages.QUIET)
def init(initfile,env,suffix,quiet):
    """
    A cli command for initializing release namespace folder with generated values yaml manifests and versions previous manifests.
    """
    ui.file_extensions_ui_validate(initfile,".helmo",message=f"Release file {initfile} is not in expected format. Expected: path/to/file-name.helmo")
    ui.file_existence_ui_validate(initfile, f"Release file {initfile} does not exist.")
    helm.init_logic(initfile,suffix,env,quiet)
    click.secho(f"{ui.Icons.SUCCESS} Namespace folder ready for {initfile} release.")

@cli.command()
@click.option('--namespace','-n', required=False, default='', help=ui.HelpMessages.KUBERNETES_NAMESPACE)
@click.option('--secrettitle','-t', required=True, help=ui.HelpMessages.KUBERNETES_SECRET_TITLE)
@click.option('--secretfile','-f', required=True, help=ui.HelpMessages.KUBERNETES_SECRET_FILE)
@click.option(
    '--context', '-c',
    required=False,
    help=ui.HelpMessages.KUBERNETES_CONTEXT
)
@click.option('--override','-o', is_flag=True, help=ui.HelpMessages.KUBERNETES_SECRET_OVERRIDE)
def create_file_secret(secrettitle,secretfile,context,namespace,override):
    """
    A cli.resource command to create a kubernetes secret from a file.
    """
    ui.file_existence_ui_validate(secretfile,f"Secret file {secretfile} does not exist.")
    k8s.create_file_secret_logic(secrettitle,secretfile,context,namespace,override)

#endregion CLI COMMANDS

#region REGISTRY COMMANDS
@cli.group()
@logger.catch(onerror=lambda _: sys.exit(1))
def registry():
    """
    Registry commands. Expects ~/.netrc file to make registry calls.
    """
    res_load_list = []
    try:
        res_load_list  = load_validated_netrc(ensure_file('~/.netrc'))
    except (FileNotFoundError,ValueError) as e:
        e.add_note(".netrc file must be in ~/ directory with correct format.")
        raise e from e
    os.environ["HELMO_REGISTRY_URL"] = res_load_list[0].machine

@registry.command()
@click.option(
    '--registryurl', '-u',
    required=True,
    envvar='HELMO_REGISTRY_URL',
    help=ui.HelpMessages.REGISTRY_URL
)
def catalog(registryurl):
    """
    Lists remote images in the registry
    """
    catalog =  docker.list_catalog_logic_http(registryurl)
    click.secho(f"  {ui.Icons.SUCCESS} Current catalog for {registryurl}:",color='yellow')
    click.secho(f"{catalog}",color='yellow')

@registry.command()
@click.option(
    '--registryurl', '-u',
    required=True,
    envvar='HELMO_REGISTRY_URL',
    help=ui.HelpMessages.REGISTRY_URL
)
@click.argument('repo', nargs=-1,required=True)
def tags(registryurl,repo):
    """
    Lists remote images in the registry
    """
    tags =  docker.list_tags_logic_http(url=registryurl,repos=repo)
    click.secho(f"  {ui.Icons.SUCCESS} Repository:{registryurl}:",color='yellow')
    click.secho(f"{tags}",color='yellow')

@registry.command()
@click.option(
    '--registryurl', '-u',
    required=True,
    envvar='HELMO_REGISTRY_URL',
    help= ui.HelpMessages.REGISTRY_URL
)
@click.option(
    '--repo', '-r',
    required=True,
    help=ui.HelpMessages.REGISTRY_REPO
)
@click.argument('tags', nargs=-1,required=True)
def get_digest(registryurl,repo,tags):
    """
    Get digest sha of a given tag of a given repo.
    """
    digest = docker.get_digest_logic_http(url=registryurl,repo=repo,tags = tags)
    click.secho(f"  {ui.Icons.SUCCESS} Repository: {registryurl}:",color='yellow')
    click.secho(f"  {ui.Icons.SUCCESS} Image: {repo}:",color='yellow')
    click.secho(f"{digest}",color='yellow')

@registry.command()
@click.option(
    '--registryurl', '-u',
    required=True,
    envvar='HELMO_REGISTRY_URL',
    help=ui.HelpMessages.REGISTRY_URL
)
@click.option(
    '--repo', '-r',
    required=True,
    help= ui.HelpMessages.REGISTRY_REPO
)
@click.option('--yes','-y', is_flag= True, help= ui.HelpMessages.YES)
@click.argument('digests', nargs=-1,required=True)
def delete_digest(registryurl,repo,yes,digests):
    """
    Deletes given sha of a given tag of a given repo.
    """
    if not yes:
        if click.confirm(f"{ui.Icons.WARNING}  Are sure to delete the digests {repo}: {[*digests]}' ? This operation can not be undone!"):
            click.secho(f"  {ui.Icons.ROCKET} Deleting the digests {repo}: {[*digests]}'",color='yellow')
        else:
            click.secho(f"  {ui.Icons.FAILURE} Aborted deleting digests {repo}: {[*digests]}.",color='red')
            raise click.Abort()
    delete_message = docker.delete_digests_logic_http(url=registryurl,repo=repo,digests=digests)
    click.secho(f"  {ui.Icons.SUCCESS} Repository: {registryurl}:",color='yellow')
    click.secho(f"  {ui.Icons.SUCCESS} Image: {repo}:",color='yellow')
    click.secho(f"{delete_message}",color='yellow')

@registry.command()
@click.option(
    '--registryurl', '-u',
    required=True,
    envvar='HELMO_REGISTRY_URL',
    help=ui.HelpMessages.REGISTRY_URL
)
@click.option(
    '--repo', '-r',
    required=True,
    help= ui.HelpMessages.REGISTRY_REPO
)
@click.option('--yes','-y', is_flag= True, help= ui.HelpMessages.YES)
@click.argument('tags', nargs=-1,required=True)
def delete_tags(registryurl,repo,yes,tags):
    """
    Deletes given tag of a given repo.
    """
    if not yes:
        if click.confirm(f"{ui.Icons.WARNING}  Are sure to delete the digests {repo}: {[*tags]}' ? This operation can not be undone!"):
            click.secho(f"  {ui.Icons.ROCKET} Deleting the digests {repo}: {[*tags]}'",color='yellow')
        else:
            click.secho(f"  {ui.Icons.FAILURE} Aborted deleting digests {repo}: {[*tags]}.",color='red')
            raise click.Abort()

    delete_message = docker.delete_tags_logic_http(url=registryurl,repo=repo,tags=tags)
    click.secho(f"  {ui.Icons.SUCCESS} Repository: {registryurl}:",color='yellow')
    click.secho(f"  {ui.Icons.SUCCESS} Image: {repo}:",color='yellow')
    click.secho(f"{delete_message}",color='yellow')

@registry.command()
@click.option(
    '--registryurl', '-u',
    required=True,
    envvar='HELMO_REGISTRY_URL',
    help= ui.HelpMessages.REGISTRY_URL
)
@click.option('--yes','-y', is_flag= True, help= ui.HelpMessages.YES)
@click.argument('repos', nargs=-1,required=True)
def delete_all(registryurl,repos,yes):
    """
    Deletes all tags of a given repo.
    """
    if not yes:
        if click.confirm(f"{ui.Icons.WARNING}  Are sure to delete all tags of image {[*repos]}? This operation can not be undone!"):
            click.secho(f"  {ui.Icons.ROCKET} Deleting all tags of {[*repos]}",color='yellow')
        else:
            click.secho(f"  {ui.Icons.FAILURE} Aborted deleting all tags of {[*repos]}",color='red')
            raise click.Abort()

    delete_message = docker.delete_all_tags_logic_http(url=registryurl,repos=repos)
    click.secho(f"  {ui.Icons.SUCCESS} Repository: {registryurl}:",color='yellow')
    click.secho(f"  {ui.Icons.SUCCESS} Image: {repos}:",color='yellow')
    click.secho(f"{delete_message}",color='yellow')



@registry.command()
@click.option(
    '--context', '-c',
    required = True,
    help=ui.HelpMessages.KUBERNETES_CONTEXT
)
@click.option(
    '--namespace', '-n', required = True,
    help=ui.HelpMessages.KUBERNETES_NAMESPACE
)
@click.option(
    '--podname', '-p',
    required = True,
    help=ui.HelpMessages.KUBERNETES_POD_NAME
)
@click.option(
    '--image', '-i', 
    help=ui.HelpMessages.KUBERNETES_CONTAINER_NAME
)
def gc_collect(context,namespace,podname,image):
    """
    Runs garbage collection for the registry deployment in the cluster.
    """
    res = k8s.gc_collect_logic(context, namespace, podname, image)
    logger.info(res)

#endregion REGISTRY COMMANDS

if __name__ == '__main__':
    cli()