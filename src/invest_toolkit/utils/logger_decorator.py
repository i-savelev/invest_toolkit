from .logger import Logger as log
import functools
import pandas as pd

def log_dataframe(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, pd.DataFrame):
            log.raw_dataframe(result,
                caption=f"Результат выполнения '{func.__name__}'")
        return result
    return wrapper