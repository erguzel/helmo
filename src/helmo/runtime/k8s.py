
from helmo.runtime import execute_subprocess
from loguru import logger
from pathlib import Path
# region k8

#def k8s_execute_helm_command(*args):
#    execute_subprocess(*args)
#
def resource_apply(file,context=''):
    """
    Applies a given resource yaml file to given environment
    
    :param file: Resource manifest yaml.
    :param environment: Deploy environment prod|test
    """
    #file = Path(file).resolve()
    #file_exists(file,ensure=True)
    if context:
        switch_context(context)
    #apply resource
    execute_subprocess('kubectl',"apply","-f",file)


def switch_context(context):
    """
    Switches context according to given environment.
    
    :param environment: Environment prod|test
    """
    cmd_res = execute_subprocess(
        "kubectl","config","current-context"
    )
    if cmd_res.stdout.strip() != context:
        execute_subprocess(
            "kubectl","config","use-context",f"{context}"
        )

def resource_exists(resource_type, resource_name,context='',namespace=''):
    """
    Checks whether a given resource name exists in the given type in kubernetes context of given environment and namespace.

    Absence and failure are different answers. --ignore-not-found turns a
    missing resource into a zero exit with empty output, which leaves a nonzero
    exit to mean a real failure -- an unreachable cluster, a rejected
    credential, an unknown resource type. Those are raised rather than reported
    as "not there", because reporting them as absence would send the caller on
    to create namespaces and secrets against a cluster it never reached.

    :param resource_type: Type of resource. Any kubernetes resource type i.e. ingress, clusterissuer etc.
    :param resource_name: Name of the resource.
    :param context: Kubernetes context to switch to before looking.
    :param namespace: Kubernetes namespace.
    """
    if context:
        switch_context(context)

    cmd_res = execute_subprocess(
        "kubectl",
        "get",
        resource_type,
        resource_name,
        "-n" if namespace else '',
        namespace if namespace else '',
        "--ignore-not-found",
        "-o",
        "name"
    )

    return bool(cmd_res.stdout.strip())

def create_file_secret(title,secret_file,context='',namespace='',override=False):
    #ensure_file(file)
    secret_file = Path(secret_file).resolve()
    secret_file_name=secret_file.name
    is_env_file = str(secret_file).endswith('.env')
    is_dockerconfigjson = str(secret_file).endswith('.dockerconfigjson')
    helm_cmd =  [       
                "kubectl","create","secret","generic",
                title,
                f"--from-env-file={secret_file}" if is_env_file else f"--from-file={secret_file_name}={secret_file}",
                f"--type={'kubernetes.io/dockerconfigjson'}" if is_dockerconfigjson else f"--type={'Opaque'}",
                f"{'-n' if namespace else ''}",
                f"{namespace if namespace else ''}"
            ]
    if namespace:
        if not resource_exists(resource_type="namespace",resource_name=namespace,context=context,namespace=namespace):
            execute_subprocess(
                "kubectl", "create", "namespace", namespace
            )

    if resource_exists(resource_type="secret",resource_name=title,context=context,namespace=namespace):
        logger.warning(f"Secret {title} already exists in context: {context if context else "current"}, namespace: {namespace if namespace else "current"}")
        if override:
            logger.warning(f"Overriding secret {title} in context: {context if context else "current"}, namespace: {namespace if namespace else "current"} with secret file {secret_file}")
            execute_subprocess(
                "kubectl", "delete", "secret", title,f"{'-n' if namespace else ''}",namespace if namespace else ''
            )

            execute_subprocess(*helm_cmd)
    else:
        execute_subprocess(*helm_cmd)
        
        logger.info(f"Secret {title} in context: {context if context else "current"}, namespace: {namespace if namespace else "current"} with secret file {secret_file} created successfully")


def delete_namespace(namespace, context):
    
    if namespace:
        if resource_exists(resource_type="namespace",resource_name=namespace,context=context,namespace=namespace):
            logger.warning(f"Deleting namespace {namespace} in context: {context if context else "current"}")
            execute_subprocess(
                "kubectl", "delete", "namespace", namespace
            )
        else:
            logger.warning(f"Namespace {namespace} in context: {context if context else "current"} does not exist")
  

# endregion k8s
