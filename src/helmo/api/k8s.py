
import os
from typing import Optional
from loguru import logger
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from helmo.validate import HelmoApiError
class K8sClient:
    """Kubernetes client with auto-authentication."""

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
        self.apps_v1 = client.AppsV1Api(self.api_client)
        self.batch_v1 = client.BatchV1Api(self.api_client)

    def get_pod(self, name: str, namespace: Optional[str] = None) -> dict:
        """Get pod details."""
        ns = namespace or self.namespace
        try:
            pod = self.v1.read_namespaced_pod(name, ns)
            return pod.to_dict()
        except ApiException as e:
            raise HelmoApiError("Failed to get pod").add_data(pod_name = name, status = e.status, reason = e.reason)

    def list_pods(self, namespace: Optional[str] = None) -> list[dict]:
        """List all pods in namespace."""
        ns = namespace or self.namespace
        try:
            pods = self.v1.list_namespaced_pod(ns)
            return [pod.to_dict() for pod in pods.items]
        except ApiException as e:
            raise HelmoApiError("Failed to list pods").add_data(status = e.status, reason = e.reason)

    def list_all_pods(self, label_selector: Optional[str] = None) -> list[dict]:
        """List pods across all namespaces."""
        try:
            pods = self.v1.list_pod_for_all_namespaces(label_selector=label_selector)
            return [pod.to_dict() for pod in pods.items]
        except ApiException as e:
            raise HelmoApiError("Failed to list all pods").add_data(status = e.status, reason = e.reason)

    def get_deployment(self, name: str, namespace: Optional[str] = None) -> dict:
        """Get deployment details."""
        ns = namespace or self.namespace
        try:
            deploy = self.apps_v1.read_namespaced_deployment(name, ns)
            return deploy.to_dict()
        except ApiException as e:
            raise HelmoApiError("Failed to get deployment").add_data(status = e.status, reason = e.reason)

    def list_deployments(self, namespace: Optional[str] = None) -> list[dict]:
        """List all deployments in namespace."""
        ns = namespace or self.namespace
        try:
            deploys = self.apps_v1.list_namespaced_deployment(ns)
            return [d.to_dict() for d in deploys.items]
        except ApiException as e:
            raise HelmoApiError("Failed to list deployments").add_data(status = e.status, reason = e.reason)

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

    def port_forward_pod(
        self, pod_name: str, local_port: int, remote_port: int, namespace: Optional[str] = None
    ) -> None:
        """
        Port-forward to a pod.

        Note: This is a blocking operation. Use in a separate thread or process.
        """
        from kubernetes.stream import portforward

        ns = namespace or self.namespace
        pf = portforward(
            self.v1.connect_get_namespaced_pod_portforward,
            pod_name,
            ns,
            ports=str(remote_port),
            local_port=local_port,
        )
        pf.start()
        return pf

    def get_pod_logs(
        self,
        pod_name: str,
        tail_lines: Optional[int] = None,
        namespace: Optional[str] = None,
    ) -> str:
        """Get pod logs."""
        ns = namespace or self.namespace
        try:
            logs = self.v1.read_namespaced_pod_log(
                pod_name, ns, tail_lines=tail_lines
            )
            return logs
        except ApiException as e:
            raise HelmoApiError("Failed to get logs").add_data(status = e.status, reason = e.reason)

    def get_configmap(self, name: str, namespace: Optional[str] = None) -> dict:
        """Get ConfigMap."""
        ns = namespace or self.namespace
        try:
            cm = self.v1.read_namespaced_config_map(name, ns)
            return cm.to_dict()
        except ApiException as e:
            raise HelmoApiError("Failed to get ConfigMap").add_data(status = e.status, reason = e.reason)

    def get_secret(self, name: str, namespace: Optional[str] = None) -> dict:
        """Get Secret (returns decoded data)."""
        ns = namespace or self.namespace
        try:
            secret = self.v1.read_namespaced_secret(name, ns)
            return secret.to_dict()
        except ApiException as e:
            raise HelmoApiError("Failed to get Secret").add_data(status = e.status, reason = e.reason)

    def delete_pod(
        self, pod_name: str, grace_period: int = 30, namespace: Optional[str] = None
    ) -> None:
        """Delete a pod."""
        ns = namespace or self.namespace
        try:
            self.v1.delete_namespaced_pod(
                pod_name, ns, grace_period_seconds=grace_period
            )
            logger.info(f"Pod {pod_name} deleted")
        except ApiException as e:
            raise HelmoApiError("Failed to delete pod").add_data(status = e.status, reason = e.reason)

    def delete_deployment(
        self, deployment_name: str, namespace: Optional[str] = None
    ) -> None:
        """Delete a deployment."""
        ns = namespace or self.namespace
        try:
            self.apps_v1.delete_namespaced_deployment(deployment_name, ns)
            logger.info(f"Deployment {deployment_name} deleted")
        except ApiException as e:
            raise HelmoApiError("Failed to delete deployment").add_data(status = e.status, reason = e.reason)

    def scale_deployment(
        self, deployment_name: str, replicas: int, namespace: Optional[str] = None
    ) -> None:
        """Scale deployment to desired replica count."""
        ns = namespace or self.namespace
        try:
            body = {"spec": {"replicas": replicas}}
            self.apps_v1.patch_namespaced_deployment(deployment_name, ns, body)
            logger.info(f"Deployment {deployment_name} scaled to {replicas} replicas")
        except ApiException as e:
            raise HelmoApiError("Failed to scale deployment").add_data(status = e.status, reason = e.reason)

    def get_nodes(self) -> list[dict]:
        """List all nodes in cluster."""
        try:
            nodes = self.v1.list_node()
            return [node.to_dict() for node in nodes.items]
        except ApiException as e:
            raise HelmoApiError("Failed to list nodes").add_data(status = e.status, reason = e.reason)

    def watch_pod(self, pod_name: str, namespace: Optional[str] = None) -> None:
        """Watch pod events in real-time."""
        ns = namespace or self.namespace
        w = watch.Watch()
        try:
            for event in w.stream(
                self.v1.list_namespaced_pod,
                ns,
                field_selector=f"metadata.name={pod_name}",
                timeout_seconds=10,
            ):
                logger.info(
                    f"{event['type']}: {event['object'].metadata.name} - "
                    f"Phase: {event['object'].status.phase}"
                )
        except ApiException as e:
            logger.error(f"Watch error: {e}")

    def create_file_secret(
        self,
        secret_name: str,
        file_path: str,
        override: bool = False,
        namespace: Optional[str] = None,
    ) -> None:
        """
        Create a Kubernetes secret from a file.

        Args:
            secret_name: Name of the secret
            file_path: Path to file to encode as secret data
            override: If True, delete and recreate existing secret
            namespace: Target namespace
        """
        ns = namespace or self.namespace

        # Check if secret exists
        if self.resource_exists("secret", secret_name, ns):
            if override:
                self.v1.delete_namespaced_secret(secret_name, ns)
                logger.info(f"Secret {secret_name} deleted (override=True)")
            else:
                raise HelmoApiError(
                    f"Secret {secret_name} already exists. Set override=True to replace."
                )

        # Read file and create secret
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            secret = client.V1Secret(
                api_version="v1",
                kind="Secret",
                metadata=client.V1ObjectMeta(name=secret_name, namespace=ns),
                type="Opaque",
                data={os.path.basename(file_path): file_data},
            )

            self.v1.create_namespaced_secret(ns, secret)
            logger.info(f"Secret {secret_name} created from {file_path}")
        except FileNotFoundError as e:
            raise HelmoApiError(f"File not found: {file_path}").add_data(inner=e)
        except ApiException as e:
            raise HelmoApiError("Failed to create secret").add_data(status = e.status, reason = e.reason)

    def switch_context(self, context: str) -> None:
        """
        Switch to a different kubeconfig context.

        Args:
            context: Context name to switch to
        """
        try:
            config.load_kube_config(context=context)
            self.api_client = client.ApiClient()
            self.v1 = client.CoreV1Api(self.api_client)
            self.apps_v1 = client.AppsV1Api(self.api_client)
            self.batch_v1 = client.BatchV1Api(self.api_client)
            logger.info(f"Switched to context: {context}")
        except config.config_exception.ConfigException as e:
            raise HelmoApiError(f"Failed to switch context: {e}")

    def resource_exists(
        self, resource_type: str, name: str, namespace: Optional[str] = None
    ) -> bool:
        """
        Check if a Kubernetes resource exists.

        Args:
            resource_type: Type of resource (pod, secret, configmap, deployment, etc.)
            name: Resource name
            namespace: Namespace (not needed for cluster-scoped resources like nodes)

        Returns:
            True if resource exists, False otherwise
        """
        ns = namespace or self.namespace

        try:
            if resource_type.lower() == "pod":
                self.v1.read_namespaced_pod(name, ns)
            elif resource_type.lower() == "secret":
                self.v1.read_namespaced_secret(name, ns)
            elif resource_type.lower() == "configmap":
                self.v1.read_namespaced_config_map(name, ns)
            elif resource_type.lower() == "deployment":
                self.apps_v1.read_namespaced_deployment(name, ns)
            elif resource_type.lower() == "statefulset":
                self.apps_v1.read_namespaced_stateful_set(name, ns)
            elif resource_type.lower() == "daemonset":
                self.apps_v1.read_namespaced_daemon_set(name, ns)
            elif resource_type.lower() == "service":
                self.v1.read_namespaced_service(name, ns)
            elif resource_type.lower() == "node":
                self.v1.read_node(name)
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")

            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise HelmoApiError(f"Error checking resource: {e.status} {e.reason}") from e

    def resource_apply(
        self, manifest: dict, namespace: Optional[str] = None, override: bool = False
    ) -> None:
        """
        Apply a Kubernetes resource manifest (create or update).

        Args:
            manifest: Dictionary containing K8s resource definition
            namespace: Override namespace in manifest
            override: If True, replace existing resource; if False, merge updates
        """
        ns = namespace or manifest.get("metadata", {}).get("namespace") or self.namespace
        manifest["metadata"]["namespace"] = ns

        resource_type = manifest.get("kind", "").lower()
        resource_name = manifest.get("metadata", {}).get("name")

        try:
            # Check if resource exists
            exists = self.resource_exists(resource_type, resource_name, ns)

            if resource_type == "secret":
                secret = client.V1Secret(**manifest)
                if exists and override:
                    self.v1.delete_namespaced_secret(resource_name, ns)
                    self.v1.create_namespaced_secret(ns, secret)
                    logger.info(f"Secret {resource_name} replaced")
                elif exists:
                    self.v1.patch_namespaced_secret(resource_name, ns, secret)
                    logger.info(f"Secret {resource_name} patched")
                else:
                    self.v1.create_namespaced_secret(ns, secret)
                    logger.info(f"Secret {resource_name} created")

            elif resource_type == "configmap":
                cm = client.V1ConfigMap(**manifest)
                if exists and override:
                    self.v1.delete_namespaced_config_map(resource_name, ns)
                    self.v1.create_namespaced_config_map(ns, cm)
                    logger.info(f"ConfigMap {resource_name} replaced")
                elif exists:
                    self.v1.patch_namespaced_config_map(resource_name, ns, cm)
                    logger.info(f"ConfigMap {resource_name} patched")
                else:
                    self.v1.create_namespaced_config_map(ns, cm)
                    logger.info(f"ConfigMap {resource_name} created")

            elif resource_type == "deployment":
                deploy = client.V1Deployment(**manifest)
                if exists and override:
                    self.apps_v1.delete_namespaced_deployment(resource_name, ns)
                    self.apps_v1.create_namespaced_deployment(ns, deploy)
                    logger.info(f"Deployment {resource_name} replaced")
                elif exists:
                    self.apps_v1.patch_namespaced_deployment(resource_name, ns, deploy)
                    logger.info(f"Deployment {resource_name} patched")
                else:
                    self.apps_v1.create_namespaced_deployment(ns, deploy)
                    logger.info(f"Deployment {resource_name} created")

            else:
                raise ValueError(f"Unsupported resource type for apply: {resource_type}")

        except ApiException as e:
            raise HelmoApiError("Failed to apply resource").add_data(status = e.status, reason = e.reason)

    def get_job(self, name: str, namespace: Optional[str] = None) -> dict:
        """
        Get a Kubernetes Job by name.

        Args:
            name: Job name
            namespace: Namespace (uses default if not specified)

        Returns:
            Job manifest as dictionary
        """
        ns = namespace or self.namespace
        try:
            job = self.batch_v1.read_namespaced_job(name, ns)
            return job.to_dict()
        except ApiException as e:
            raise HelmoApiError(f"Failed to get job {name}").add_data(status = e.status, reason = e.reason)

    def restart_job(
        self, job_name: str, new_job_name: str, namespace: Optional[str] = None
    ) -> None:
        """
        Get an existing job and restart it with a new name.

        This creates a new Job with the same spec as the original, but with a new name.
        The original job is left unchanged.

        Args:
            job_name: Name of the existing job to copy
            new_job_name: Name for the new job instance
            namespace: Namespace (uses default if not specified)
        """
        ns = namespace or self.namespace

        try:
            # Get the original job
            original_job = self.batch_v1.read_namespaced_job(job_name, ns)
            
            # Create a new job manifest based on the original
            new_job = client.V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=client.V1ObjectMeta(
                    name=new_job_name,
                    namespace=ns,
                    labels=original_job.metadata.labels,
                    annotations=original_job.metadata.annotations,
                ),
                spec=original_job.spec,
            )

            # Create the new job
            self.batch_v1.create_namespaced_job(ns, new_job)
            logger.info(f"Job {new_job_name} started (copied from {job_name})")

        except ApiException as e:
            raise HelmoApiError(f"Failed to restart job {job_name}").add_data(status = e.status, reason = e.reason)
        
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
            pod_name: Specific pod name (if None, finds by label app=registry or image name)
            image_name: Container image name to match (default: registry)
            namespace: Namespace (uses default if not specified)

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