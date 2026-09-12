
from typing import List, Literal,Dict
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel,HttpUrl,SecretStr, Field, field_validator
from helmo.validate.path import suffix_exists
from helmo.validate.error import HelmoValidationError

class RegistryAuthCredentialsModel(BaseModel):
    username: str
    password: SecretStr
    auth: SecretStr
    model_config = SettingsConfigDict(extra="forbid")

class RegistryAuthConfigModel(BaseModel):
    auths: Dict[str, RegistryAuthCredentialsModel]
    model_config = SettingsConfigDict(extra="forbid")

class HelmoInitFileModel(BaseSettings):
    TEST_CONTEXT: str
    PROD_CONTEXT: str
    CHART_VERSION: str
    APP_VERSION: str
    REPO_URL: HttpUrl
    REPOSITORY_NAME: str
    CHART_NAME: str
    NAMESPACE: str
    model_config = SettingsConfigDict(env_file=".helmo", env_file_encoding="utf-8")


# region YAML FILE 
class HelmoReleasesYamlItemModel(BaseModel):
    # name: REQUIRED (Lowercase alphanumeric and dashes only for K8s)
    #name: str = Field(..., pattern=r"^[a-z0-9-]+$")
    initFile: str = Field(...)
    # context: REQUIRED (only prod|staging|test)
    environment: Literal["prod", "staging", "test"]
    # secretNames: OPTIONAL (Defaults to empty list)
    secretFileNames: List[str] = []
    # resourceManifests: OPTIONAL but needs to be yaml/yml if provided
    resourceManifestNames: List[str] = []
    additionalValuesNames: List[str] = []
    
    @field_validator('initFile')
    @classmethod
    def validate_init_file_extensions(cls, release_file: str) -> None:
        if not suffix_exists(release_file,'.helmo'):
            raise HelmoValidationError(f"Helmo release file {release_file} must have a single .helmo suffix.")\
                .add_data(validator_model = cls.__name__)
        return release_file
    
    @field_validator('resourceManifestNames')
    @classmethod
    def validate_resource_manifest_extensions(cls, resource_manifests: List[str]) -> List[str]:
        for file_path in resource_manifests:
            if not suffix_exists(file_path,'.yml','.yaml'):
                raise HelmoValidationError(f"Kubernetes resource manifest file {file_path} should be a yaml.")\
                    .add_data(validator_model=cls.__name__)
        return resource_manifests
    
    @field_validator('additionalValuesNames')
    @classmethod
    def validate_additional_values_names_extensions(cls, additional_values_names: List[str]) -> List[str]:
        for file_path in additional_values_names:
            if not suffix_exists(file_path,'.yml','.yaml'):
                raise HelmoValidationError(f"Kubernetes resource manifest file {file_path} should be a yaml.")\
                    .add_data(validator_model=cls.__name__)
        return additional_values_names

class HelmoReleasesYamlFileModel(BaseModel):
    releases: List[HelmoReleasesYamlItemModel]


class NetrcEntryModel(BaseModel):
    machine: str
    login: str
    password: SecretStr  
    account: str | None = None
