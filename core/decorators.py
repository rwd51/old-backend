from error_handling.error_list import CUSTOM_ERROR_LIST


def check_prerequisites(conditions):
    def decorator(function):
        def wrapper(*args, **kwargs):
            for condition in conditions:
                view = args[0]
                request = args[1]
                if not condition(request.user):
                    raise CUSTOM_ERROR_LIST.CUSTOM_VALIDATION_ERROR_4008(
                        message={condition.__name__: "Prerequisite not met"}
                    )
            result = function(*args, **kwargs)
            return result
        return wrapper
    return decorator