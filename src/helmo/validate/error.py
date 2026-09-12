from typing import Any
import json

class HelmoError(Exception):
    def __init__(self, *args):
        self.message = ', '.join(str(arg) for arg in args)
        self.data = {}
        super().__init__(*args)
    def add_data(self, **kwargs):
        self.data.update(**kwargs)
        return self
    def add_note(self, note):
        super().add_note(note)
        return self
    def get_str(self, to_json = False, indent =2):
        msg = f"{type(self).__name__} says {self.message}"
        if self.data:
            msg += f" | Context: {self.data}"
        return json.dumps(self.to_dict(),indent=indent) if to_json else msg
    def __str__(self) -> str:
        msg =  self.message
        if self.data:
            msg += f" | Context: {self.data}"
        return msg
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "data": self._make_serializable(self.data),
        }

    @staticmethod
    def _make_serializable(obj: Any, max_depth: int = 10) -> Any:
        """Recursively convert objects to JSON-serializable form."""
        
        if max_depth <= 0:
            return str(obj)
        
        if isinstance(obj, Exception):
            return {
                "exception": obj.__class__.__name__,
                "message": str(obj),
            }
        
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        
        if isinstance(obj, dict):
            return {
                k: HelmoError._make_serializable(v, max_depth - 1)
                for k, v in obj.items()
            }
        
        if isinstance(obj, (list, tuple)):
            return [
                HelmoError._make_serializable(item, max_depth - 1)
                for item in obj
            ]
        
        # Custom objects
        try:
            obj_dict = {
                k: HelmoError._make_serializable(v, max_depth - 1)
                for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
            return {
                "__class__": obj.__class__.__name__,
                **obj_dict,
            } if obj_dict else str(obj)
        except Exception:
            return str(obj)

class HelmoValidationError(HelmoError, ValueError):
    """Also a ValueError so pydantic folds it into ValidationError."""

class HelmoPathError(HelmoError):
    pass

class HelmoRuntimeError(HelmoError):
    pass

class HelmoApiError(HelmoError):
    pass
