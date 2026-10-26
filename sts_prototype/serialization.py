"""Convert NumPy scalar values to native JSON types without stringifying booleans."""
def json_scalar(value):
    import numpy as np
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f'Unsupported JSON type: {type(value).__name__}')
