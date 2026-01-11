## General Rules 

- Helmo cli works based on a release-name.release file which is in below structure.

    CHART_VERSION="v1.19.2"<br>
    APP_VERSION="v1.19.2"<br>
    REPO_URL=https://charts.jetstack.io<br>
    REPOSITORY_NAME=jetstack<br>
    CHART_NAME=cert-manager<br>
    NAMESPACE=cert-manager<br>

- Helmo deployment file structure is created by<br>
``` helmo values --chart /path/to/release-name.release```
```
NAMESPACE/
├── config/
|── release-name_CHART_VERSION_default.yaml
|── release-name_CHART_VERSION_prod.yaml
|── release-name_CHART_VERSION_test.yaml
|── release-name.release.helm
```