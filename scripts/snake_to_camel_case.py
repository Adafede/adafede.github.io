def snake_to_camel_case(snake_str):
    if not snake_str:
        return snake_str

    components = snake_str.split("_")
    return components[0] + "".join(word.capitalize() for word in components[1:])
