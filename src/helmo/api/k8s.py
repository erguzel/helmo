
from typing import Optional
from loguru import logger
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from helmo.validate import HelmoApiError
class K8sClient:
    """Minimal Kubernetes API client for the registry garbage-collection path.

    Everything helmo does with helm and kubectl goes through ``helmo.runtime``
    as a subprocess, so that both share one kubeconfig, one current context and
    one auth path.  This client covers only the step that subprocess handles
    badly: finding the registry pod and streaming a command inside it.
    """

    def __init__(
        self,
        context: Optional[str] = None,
        namespace: str = "default",
        in_cluster: bool = False,
    ):
        """
        Initialize Kubernetes client.

        Args:
            context: kubeconfig context name (uses current context if None)
            namespace: Default namespace for operations
            in_cluster: Use in-cluster authentication (for pods running in K8s)
        """
       

        # Load kubeconfig with auto-authentication
        if in_cluster:
            config.load_incluster_config()
        else:
            config.load_kube_config(context=context)

        current_context = None
        if not in_cluster:
            _, current_context = config.list_kube_config_contexts()

        if not namespace:
            namespace = (current_context or {}).get("context", {}).get("namespace", "default")

        self.namespace = namespace
        self.context = None if in_cluster else (context or (current_context or {}).get("name"))
        self.api_client = client.ApiClient()
        self.v1 = client.CoreV1Api(self.api_client)

    def list_pods(self, namespace: Optional[str] = None) -> list[dict]:
        """List all pods in namespace."""
        ns = namespace or self.namespace
        try:
            pods = self.v1.list_namespaced_pod(ns)
            return [pod.to_dict() for pod in pods.items]
        except ApiException as e:
            raise HelmoApiError("Failed to list pods").add_data(status = e.status, reason = e.reason)

    def exec_pod_command(
        self, pod_name: str, command: list[str], namespace: Optional[str] = None
    ) -> str:
        """Execute command in pod and return output."""
        from kubernetes.stream import stream

        ns = namespace or self.namespace
        try:
            output = stream(
                self.v1.connect_get_namespaced_pod_exec,
                pod_name,
                ns,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
            return output
        except ApiException as e:
            raise HelmoApiError("Failed to exec command").add_data(status = e.status, reason = e.reason)

    def run_registry_gc(
        self,
        pod_name: Optional[str] = None,
        container_name: str = "docker-registry"
    ) -> str:
        """
        Run Docker registry garbage collection on a pod.

        Finds the registry pod (by label or name) and executes garbage collection.
        This reclaims disk space after deleting manifests.

        Args:
            pod_name: Specific pod name (if None, finds the pod by label or image)
            container_name: Label value and image substring to match the pod by

        Returns:
            Garbage collection output

        Example:
            output = k8s.run_registry_gc()  # Auto-finds registry pod
            output = k8s.run_registry_gc(pod_name="my-registry-0")  # Specific pod
        """
        ns = self.namespace

        # If no pod name provided, try to find registry pod
        if not pod_name:
            try:
                pods = self.list_pods(ns)
                # Look for pod with app=registry label
                for pod in pods:
                    labels = pod.get("metadata", {}).get("labels", {})
                    if labels.get("app") == container_name:
                        pod_name = pod["metadata"]["name"]
                        break

                # If still not found, search by image
                if not pod_name:
                    for pod in pods:
                        containers = pod.get("spec", {}).get("containers", [])
                        for cont in containers:
                            if container_name in cont.get("image", ""):
                                pod_name = pod["metadata"]["name"]
                                break
                        if pod_name:
                            break

                if not pod_name:
                    raise HelmoApiError(
                        f"No registry pod found in namespace {ns}. "
                        "Specify pod_name explicitly."
                    )
            except Exception as e:
                raise HelmoApiError(f"Failed to find registry pod: {e}")

        try:
            # Execute garbage collection
            output = self.exec_pod_command(
                pod_name,
                [
                    "bin/registry",
                    "garbage-collect",
                    "/etc/distribution/config.yml",
                    "--delete-untagged"
                ],
                ns,
            )
            logger.info(f"✓ Garbage collection completed on {pod_name}")
            return output

        except Exception as e:
            raise HelmoApiError(f"Failed to run garbage collection: {e}")   
    
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.api_client.close()