def validate_node_id(node_id):
    """
    Validate that a node identifier is a reasonable string input.

    The function currently perform lightweight validation only:
    it checks the type and rejects excessively long values before
    the value is used in form handling or database logic.

    :param node_id: str, raw node identifier input
    :return: str, the validated node identifier
    :raise: ValueError, if the input is not a string or is too long
    """
    if not isinstance(node_id, str):
        raise ValueError("Node must be a string!")
    if len(node_id) > 50:
        raise ValueError("Node ID too long!")
    return node_id

def validate_positive_int(value, field_name="id"):
    """
    Validate and convert a value to a positive integer.

    This helper is used for form and route input validation,
    especially whereIDs are expected. It raises a descriptive
    error for missing, invalid, or non-positive values.

    :param value: raw input value to convert
    :param field_name: str, field name used in error messages
    :return: int, converted positive integer
    :raise: ValueError, if conversion fails or the number is not positive
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer.")
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number