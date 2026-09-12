import sys
from loguru import logger
from helmo.runtime import create_file_secret
from helmo.api import K8sClient

@logger.catch(onerror=lambda _: sys.exit(1))
def create_file_secret_logic(title,file,context='', namespace='',override=False):
    """
    Logical function for creating a kubernetes secret from file. If given file is .env file, uses --from-env-file option.

    :param title: Secret name.
    :param file: Secret file.
    :param environment: Environment prod|test|staging
    :param namespace: Kubernetes namespace.
    :param override: Overrides existing secret.
    """
    create_file_secret(title,file,context,namespace,override)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def gc_collect_logic(context, namespace, pod_name, container_name, ):
    res = None
    with K8sClient(context,namespace) as cl:
      res =  cl.run_registry_gc(pod_name,container_name)
    return res