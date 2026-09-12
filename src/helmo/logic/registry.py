
import json,sys
from loguru import logger
from helmo.api import RegistryClient

@logger.catch(onerror=lambda _: sys.exit(1))
def list_catalog_logic_http(url):
    with RegistryClient(f"https://{url}") as client:
        catalog = client.list_catalog()
        return json.dumps(catalog,indent=2)
@logger.catch(onerror=lambda _: sys.exit(1))
def get_digest_logic_http(url,repo,tags):
    res_dict = {}
    with RegistryClient(f"https://{url}") as client:
        for tg in tags:
            digest = client.get_digest(repo,tg)
            res_dict[tg]=digest
        return json.dumps(res_dict,indent=2)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def list_tags_logic_http(url,repos):
    res_dict = {}

    with RegistryClient(f"https://{url}") as client:
        for rep in repos:
            tags =  client.list_tags(rep)
            res_dict[rep] = tags

        return json.dumps(res_dict,indent=2)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def delete_digests_logic_http(url, repo, digests):
    res_dict = {}
    with RegistryClient(f"https://{url}") as client:
        for dig in digests:
            is_deleted =  client.delete_manifest(repo,dig)
            res_dict[dig] = is_deleted
        return json.dumps(res_dict,indent=2)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def delete_tags_logic_http(url, repo, tags):
    res_dict = {}
    with RegistryClient(f"https://{url}") as client:
        for tag in tags:
            is_deleted =  client.delete_tag(repo,tag)
            res_dict[tag] = is_deleted
        return json.dumps(res_dict,indent=2)
    
@logger.catch(onerror=lambda _: sys.exit(1))
def delete_all_tags_logic_http(url, repos):
    res_dict = {}
    with RegistryClient(f"https://{url}") as client:
        for rep in repos:
            del_mess =  client.delete_all_tags(rep)
            res_dict[rep] = del_mess

        return json.dumps(res_dict,indent=2)


