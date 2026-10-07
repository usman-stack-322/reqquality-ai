"""Keep response data separate from HTTP serialization."""

def response_payload(*args, **kwargs):
    if args:
        return args[0] if len(args) == 1 else list(args)
    return kwargs
