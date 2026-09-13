
import subprocess
from helmo.validate import HelmoRuntimeError

def execute_subprocess(*args):
    """
    Raises RuntimeError if subprocess return nonzero returncode.
    
    :param args: Command arguments.
    """
    cmd = [arg for arg in args if arg]
    cmd_result = subprocess.run(cmd,capture_output=True, text=True)
    if cmd_result.returncode !=0:
        raise HelmoRuntimeError("Subprocess returned nonzero status")\
        .add_data(command = cmd, stderr = cmd_result.stderr)
    return cmd_result
