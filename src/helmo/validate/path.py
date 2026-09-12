import os
from pathlib import Path
from helmo.validate.error import HelmoPathError

def path_resolver(path: str|Path)->Path:
    path = Path(os.path.expanduser(path)).resolve() if str(path).startswith('~') else Path(path).resolve()
    return path

# region FILE-DIRECTORY
def file_exists(file : str | Path,ensure = False):
    """
    Returns true if file exists
    
    :param file: Path File path.
    :type file: str | 
    :param ensure: Throws FileNotFound exception if file does not exists.
    """
    file_path = path_resolver(file)
    file_present = file_path.is_file()
    if not file_present:
        if ensure:
            raise HelmoPathError(f"File {file} does not exists.")
        return False
    return True


def ensure_file(file : str | Path, *allowed_suffixes)->Path:
    """
    Returns ensured file. 
    Throws Value error if sufix is bad/
    Throws FileNotFound error if file does not exists.
    
    :param file: Path File path.
    :type file: str | 
    """
    file_path = path_resolver(file)
    file_present = file_path.is_file()
    if allowed_suffixes:
        suffix_exists(file_path,*allowed_suffixes,ensure=True)
    if not file_present:
        raise HelmoPathError(f"File {file} does not exists.")
    return file_path
#

def ensure_directory(directory:str|Path)->Path:
    directory_exists(directory,ensure=True)
    return path_resolver(directory)

def directory_exists(path: str|Path, ensure = False):
    """
    Returns true if directory exists.
    
    :param path: Directory path.
    :type path: str | Path
    :param ensure: Throws NotADirectoryError exception if Directory does not exists.
    """
    path = path_resolver(path)
    directory_present = path.is_dir()
    if not directory_present:
        if ensure:
            raise HelmoPathError(f"Directory {path} does not exists.")
        return False
    return True
    

def suffix_exists(file: str|Path, *allowed_suffixes, ensure = False):
    """
    Docstring for suffix_exists
    
    :param file: Description
    :type file: str | Path
    :param extension: Description
    :param multi_suffix: Description
    :param ensure: Description
    """
    file_path = path_resolver(file)
    suffix = file_path.suffix
    suffixes = file_path.suffixes
    if file_path.name.startswith('.'):
        suffixes = [f'.{st}' for st in file_path.name.split('.') if st]
        suffix = suffixes[len(suffixes)-1]
    suffix_accepted = suffix in allowed_suffixes and len(suffixes) == 1
    if not suffix_accepted:
        if ensure:
            raise HelmoPathError(f"File {file_path} does not have expected suffix.",allowed_suffixes)
        return False
    return True


def is_path(value):
    value = Path(value)
    ispath = len(value.parts) > 1
    if ispath:
        return True
    return False

def is_file(value):
    value = Path(value)
    ispath = len(value.suffixes) >= 1
    if ispath:
        return True
    return False

def is_path_or_file(value):
    value = Path(value)
    ispathorstring = is_path(value) or is_file(value)
    if ispathorstring:
        return True
    return False
