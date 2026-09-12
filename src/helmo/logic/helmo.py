import shutil
import sys
import helmo.validate as validate
from helmo.validate import HelmoReleasesYamlItemModel
import helmo.runtime as runtime
from helmo.validate.error import HelmoError
from loguru import logger
from datetime import datetime

@logger.catch(onerror=lambda _: sys.exit(1))
def uninstall_serial_deployment_release(deployment_release,delete_namespace=False, dryrun=False):
    init_file = deployment_release.initFile
    init_file = validate.ensure_file(init_file,'.helmo')
    HELMO_INIT_FILE = validate.ensure_helmo_init_file_format(init_file)
    context = getattr(HELMO_INIT_FILE,f"{str(deployment_release.environment).upper()}_CONTEXT")
    release_name = init_file.stem
    #
    helm_command_arr=[
        'helm',
        'uninstall',
        release_name,
        '-n',
        HELMO_INIT_FILE.NAMESPACE,
        '--wait',
        '--timeout',
        '5m'
    ]
    logger.warning(f"HELM COMMAND in context {context}: \n" +
                f"{helm_command_arr} \n" +
            "Wait till all resources uninstalled")
    if dryrun:
        logger.warning(f"Dry run completed for {release_name}.")
    else:
        try:
            stdout = runtime.execute_subprocess(*helm_command_arr)
            logger.info(stdout)
        except HelmoError as he:
            logger.warning(he.data['stderr'])

        if delete_namespace:
            runtime.delete_namespace(namespace=HELMO_INIT_FILE.NAMESPACE,context=context)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def uninstall_logic(releases_file,deployments,delete_namespace=False,dryrun=False):
    releases_file = validate.ensure_file(releases_file,'.yaml','.yml')
    releases_ctx = validate.safe_load_helmo_releases_yaml_file(releases_file)
    root_dir = releases_file.parent
    #purging_releases = [rel for rel in releases_ctx.releases if validate.path_resolver(rel.initFile).stem in deployments]
    purging_releases_dict = {validate.path_resolver(rel.initFile).stem:rel for rel in releases_ctx.releases if validate.path_resolver(rel.initFile).stem in deployments}
    for _,dep_rel in purging_releases_dict.items():
        dep_rel.initFile = root_dir / dep_rel.initFile
    #for dep_rel in purging_releases:
    #    dep_rel.initFile = root_dir / dep_rel.initFile
    wrong_releases_given = list(set(deployments) - set(dr.initFile.stem for dr in purging_releases_dict.values()))
    if wrong_releases_given:
        logger.error(f"Given release names {wrong_releases_given} is not defined in {releases_file} file")
        sys.exit(1)
        
    logger.info(f"Serial uninstall started for {[*deployments]} via {releases_file}")
    for depl_rel_key in deployments:
        uninstall_serial_deployment_release(deployment_release=purging_releases_dict[depl_rel_key],
                                            delete_namespace=delete_namespace,
                                            dryrun=dryrun)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def manual_deploy_logic(release_file,
                        environment,
                        helm_action,
                        additional_values,
                        wait,
                        suffix='',
                        quiet=False,
                        dryrun=False):
    """
    Logical function for manual helm deployment of a release.

    :param chart: .helm file of the chart.
    :param env: Environment prod|staging|test.
    :param action: Helm action install|upgrade|uninstall.
    :param wait: Wait timeout after helm command.
    :param quiet: Skips promopting to user.
    :param values: Additional partial or complete values.yaml files to override original values.yaml manifest of release.
    """
    release_file = validate.ensure_file(release_file,'.helmo')
    additional_values = [validate.ensure_file(val,'.yaml','.yml') for val in additional_values]
    release_name = release_file.stem
    deployment_root = release_file.parent
    INIT_FILE_VARS = validate.ensure_helmo_init_file_format(init_file=release_file) 
    REPOSITORY_NAME=INIT_FILE_VARS.REPOSITORY_NAME
    CHART_NAME=INIT_FILE_VARS.CHART_NAME
    CHART_VERSION=INIT_FILE_VARS.CHART_VERSION
    NAMESPACE=INIT_FILE_VARS.NAMESPACE
    chart_values_file= f"{deployment_root}/{release_name}_{environment}_{CHART_VERSION}.yaml"
    if not validate.file_exists(chart_values_file):
        logger.error(f"Values manifest file {chart_values_file} does not exist. Consider running 'helmo init -i {release_file}' first to generate manifest files to required directories")
        sys.exit(1) 
    
    additional_values_files_cmd=[
        item 
        for af in additional_values 
        for item in ("--values", str(validate.path_resolver(af)))
    ]

    helm_command_arr = [
        "helm",
        f"{helm_action}",
        f"{release_name}",
        f"{REPOSITORY_NAME}/{CHART_NAME}",
        "--namespace",
        f"{NAMESPACE}",
        "--create-namespace",
        "--version",
        f"{CHART_VERSION}",
        "--values",
        f"{chart_values_file}"
    ]

    helm_command_arr.extend(additional_values_files_cmd)
    helm_command_arr.extend(["--wait","--timeout",f"{wait}"])
    context = getattr(INIT_FILE_VARS,f"{str(environment).upper()}_CONTEXT")
    runtime.switch_context(context)
    #k8s_switch_context(context)
    init_logic(init_file=release_file,suffix=suffix,env=environment,quiet=quiet,dryrun=dryrun)
    logger.warning(f"HELM COMMAND in context {context}: \n" +
                f"{helm_command_arr} \n" +
            f"Wait till all resources deployed for {wait}")
    if dryrun:
        logger.warning(f"Dry run completed for {release_name}.")
    else:
        runtime.execute_subprocess(*helm_command_arr)
        #k8s_execute_helm_command(*helm_command_arr)

@logger.catch(onerror=lambda _: sys.exit(1))
def init_logic(init_file,suffix,env, quiet = False, dryrun=False):
    """
    Generates a set of values.yaml file for release_name_environmment-chart-version.yaml. If files already exists, archives them with a versioning suffix.
    
    :param helmo_file: release-name.helmo file of the release.
    :param suffix: Suffix for renaming previous yaml files for versioning. Default is '%Y%m%d%H%M%S"'.
    """

    init_file = validate.path_resolver(init_file)
    validate.ensure_file(init_file,'.helmo')
    namespace_path = init_file.parent
    release_name = init_file.stem
    RELEASE_FILE_VARS = validate.ensure_helmo_init_file_format(init_file=init_file)
    REPOSITORY_NAME=RELEASE_FILE_VARS.REPOSITORY_NAME
    CHART_NAME=RELEASE_FILE_VARS.CHART_NAME
    CHART_VERSION=RELEASE_FILE_VARS.CHART_VERSION
    NAMESPACE=RELEASE_FILE_VARS.NAMESPACE
    context = getattr(RELEASE_FILE_VARS,f"{str(env).upper()}_CONTEXT")
    helm_command_return = runtime.execute_subprocess(
        "helm",
        "show",
        "values",
        f"{REPOSITORY_NAME}/{CHART_NAME}",
        "--version", 
        f"{CHART_VERSION}"
    )

    if not namespace_path.name == NAMESPACE:
        namespace_path = init_file.parent / NAMESPACE
    release_file_permanent = namespace_path / init_file.name
    config_path = namespace_path / "config" / release_name
    config_path.mkdir(parents=True, exist_ok=True)

    #if not validate.file_exists(release_file_permanent):
    #        namespace_path.mkdir(parents=True, exist_ok=True)
    #if not validate.directory_exists(namespace_path):
    namespace_path.mkdir(parents=True, exist_ok=True)
    if release_file_permanent != init_file:
        shutil.move(init_file,release_file_permanent)
        logger.warning(f"Release file {init_file} permanently overwrote {release_file_permanent}.")
    if not runtime.resource_exists("namespace",NAMESPACE,context):
        runtime.execute_subprocess(
            "kubectl","create", "namespace", NAMESPACE
        )
        if not quiet:
            logger.info(f"Namespace {NAMESPACE} created in {context} context")
    time_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    if dryrun:
        suffix = f"dryrun.{time_stamp}.{suffix}" if suffix else f"dryrun.{time_stamp}" 
    else:
        suffix = f"{time_stamp}.{suffix}" if suffix else f"{time_stamp}"
    file_types=['prod','test','default']
    for ft in file_types:
        latest_file=validate.path_resolver(namespace_path / f"{release_name}_{ft}_{CHART_VERSION}.yaml")
        archived_file_name=validate.path_resolver(namespace_path / f"{release_name}_{ft}_{CHART_VERSION}_{suffix}.yaml")
        if validate.file_exists(latest_file):
            if ft == "default":
                latest_file.write_text(helm_command_return.stdout)
            else:
                shutil.copy2(latest_file,archived_file_name)
        else:
            latest_file.write_text(helm_command_return.stdout)
    logger.info(f"Latest manifests of {release_name} versioned to {suffix} suffix.")
    if not quiet:
        logger.info(f"Init {release_name} completed: {namespace_path}")


@logger.catch(onerror=lambda _: sys.exit(1))
def serial_deploy_logic(action,
                        releases_file,
                        deployments,
                        values=[],
                        suffix='',
                        dryrun=False):
    """
    Serial deployment for pre-configured deployments. Deployment names are arguments after defined options.
    """
    releases_file = validate.ensure_file(releases_file,'.yaml','.yml')
    releases_ctx = validate.safe_load_helmo_releases_yaml_file(releases_file)
    root_dir = releases_file.parent
    deploying_releases = {validate.path_resolver(rel.initFile).stem:rel for rel in releases_ctx.releases if validate.path_resolver(rel.initFile).stem in deployments}
    for _,dep_rel in deploying_releases.items():
        dep_rel.initFile = root_dir / dep_rel.initFile
        dep_rel.additionalValuesNames.extend(validate.path_resolver(val) for val in values)

    wrong_deployments_given = list(set(deployments) - set(dr.initFile.stem for dr in deploying_releases.values()))
  
    if wrong_deployments_given:
        logger.error(f"Given release names {wrong_deployments_given} is not defined in {releases_file} file")
        sys.exit(1)
    
    for d_rel_key in deployments:
        validate_serial_deployment_release(deploying_releases[d_rel_key])

    logger.info(f"Serial deployment started for {[*deployments]} via {releases_file}")
    for d_rel_key in deployments:
        deploy_serial_deployment_release(deployment_release=deploying_releases[d_rel_key],
                                         action=action,
                                         suffix=suffix,
                                         dryrun=dryrun)

@logger.catch(onerror=lambda _: sys.exit(1))
def validate_serial_deployment_release(deployment_release: HelmoReleasesYamlItemModel):
    release_file = deployment_release.initFile
    secret_names = deployment_release.secretFileNames
    resource_manifest_names = deployment_release.resourceManifestNames
    additional_values = deployment_release.additionalValuesNames
    ####
    release_file = validate.ensure_file(release_file,'.helmo')
    release_name = release_file.stem
    config_dir = release_file.parent / 'config' /release_name
    #### Resources
    
    for secret_name in secret_names:
        validate.ensure_file(config_dir / secret_name)
    for res_man_file_name in resource_manifest_names:
        validate.ensure_file(config_dir / res_man_file_name,'.yaml', '.yml')
    for additional_val_file_name in additional_values:
        validate.ensure_file(config_dir / additional_val_file_name,'.yaml', '.yml')

@logger.catch(onerror=lambda _: sys.exit(1))
def deploy_serial_deployment_release(deployment_release,action,suffix='',additional_values=[], dryrun=False):
    init_file = deployment_release.initFile
    environment = deployment_release.environment
    secret_file_names = deployment_release.secretFileNames
    resource_manifest_names = deployment_release.resourceManifestNames
    additional_values_names = deployment_release.additionalValuesNames
    init_file = validate.path_resolver(init_file)
    HELMO_INIT_FILE = validate.ensure_helmo_init_file_format(init_file)
    context = getattr(HELMO_INIT_FILE,f"{str(environment).upper()}_CONTEXT")
    release_name = init_file.stem
    config_dir = init_file.parent / 'config' / release_name
    secret_files= [validate.ensure_file(config_dir / sec_name) for sec_name in secret_file_names]
    validate.ensure_file(init_file,'.helmo')
    #secrets =  [(sec_name,validate.ensure_file(config_dir / sec_name)) for sec_name in secret_files]
    resource_manifests = [validate.ensure_file(config_dir / resman_name,'.yaml','.yml') for resman_name in resource_manifest_names]
    additional_values = [validate.ensure_file(config_dir / add_val_name,'.yaml','.yml') for add_val_name in additional_values_names]
    ####
    NAMESPACE = HELMO_INIT_FILE.NAMESPACE
    #if secret_files:
    for sec_file in secret_files:
        logger.warning(f"Will override secret {sec_file.stem} with secret {sec_file} in {NAMESPACE} namespace")
        if not dryrun:
                runtime.create_file_secret(
                sec_file.stem,
                sec_file,
                context,
                NAMESPACE,
                True
            )
    #if resource_manifests:
    for res_man in resource_manifests:
        logger.warning(f"Will override resource {res_man}")
        if not dryrun:
            runtime.resource_apply(
                res_man,
                context
            )
    manual_deploy_logic(release_file=init_file,
                        environment=environment,
                        helm_action=action,
                        additional_values=additional_values,
                        wait="5m",
                        suffix=suffix,
                        quiet=False,
                        dryrun=dryrun)




