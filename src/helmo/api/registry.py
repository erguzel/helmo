
from typing import Optional
import httpx
from helmo.validate import HelmoApiError
class RegistryClient:
    """ Docker Registry v2 client for OCI/Docker manifests."""

    ACCEPT_HEADERS = [
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
    ]

    def __init__(
        self,
        registry_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = True,
    ):
        """
        Initialize registry client.

        Args:
            registry_url: Base registry URL (e.g., https://registry.example.com:5000)
            username: Registry username (uses .netrc if None)
            password: Registry password (uses .netrc if None)
            verify_ssl: Whether to verify SSL certificates
        """
        self.registry_url = registry_url.rstrip("/")
    
        # Use provided credentials or fall back to .netrc
        auth = self._get_auth(username, password) if (username and password) else httpx.NetRCAuth()

        self.client = httpx.Client(
            verify=verify_ssl, follow_redirects=False, auth=auth
        )

    @staticmethod
    def _get_auth(username: Optional[str], password: Optional[str]) -> Optional[tuple]:
        """
        Get authentication from arguments or .netrc file.

        Args:
            username: Explicit username
            password: Explicit password

        Returns:
            Tuple of (username, password) or None
        """
        if username and password:
            return (username, password)

        # .netrc is automatically used by httpx if no auth is provided
        # and the host matches an entry in ~/.netrc
        return None

    def get_digest(self, image: str, tag: str) -> str:
        """
        Get the manifest digest for an image tag.

        Args:
            image: Image name (e.g., 'myapp', 'namespace/myapp')
            tag: Tag name (e.g., 'v1.0.0', 'latest')

        Returns:
            The manifest digest (sha256:...)

        Raises:
            httpx.HTTPStatusError: If request fails
            ValueError: If digest header is missing
        """
        url = f"{self.registry_url}/v2/{image}/manifests/{tag}"
        headers = {"Accept": ",".join(self.ACCEPT_HEADERS)}

        response = self.client.head(url, headers=headers)
        response.raise_for_status()

        digest = response.headers.get("docker-content-digest")
        if not digest:
            raise HelmoApiError("No digest found").add_data(image=image,tag = tag)

        return digest

    def delete_manifest(self, image: str, digest: str) -> bool:
        """
        Delete a manifest by digest.

        Args:
            image: Image name
            digest: Manifest digest (from get_digest)

        Returns:
            True if deletion was successful (202 or 404)
        """
        url = f"{self.registry_url}/v2/{image}/manifests/{digest}"
        headers = {"Accept": ",".join(self.ACCEPT_HEADERS)}

        response = self.client.delete(url, headers=headers)

        # 202 = successful deletion, 404 = already deleted/doesn't exist
        return response.status_code in (202, 404)

    def list_catalog(self) -> list[str]:
        """
        List all images in the registry.

        Returns:
            List of image names
        """
        url = f"{self.registry_url}/v2/_catalog"
        response = self.client.get(url)
        response.raise_for_status()

        return response.json().get("repositories", [])

    def list_tags(self, image: str) -> list[str]:
        """
        List all tags for an image.

        Args:
            image: Image name

        Returns:
            List of tag names
        """
        url = f"{self.registry_url}/v2/{image}/tags/list"
        response = self.client.get(url)
        response.raise_for_status()

        return response.json().get("tags", [])

    def delete_tag(self, image: str, tag: str) -> bool:
        """
        Convenience method: delete an image by tag (get digest then delete).

        Args:
            image: Image name
            tag: Tag name

        Returns:
            True if successful
        """
        digest = self.get_digest(image, tag)
        return self.delete_manifest(image, digest)


    def delete_all_tags(self,image:str):
        tags = self.list_tags(image)
        res_dict = {}
        for tag in tags:
            try:
                del_message = self.delete_tag(image, tag)
                res_dict[tag] = del_message
            except httpx.HTTPStatusError as e:
                fail_data = {
                    'status_code': e.response.status_code,
                    'response': e.response.json()
                    }
                res_dict[tag] = fail_data
        return res_dict
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()
