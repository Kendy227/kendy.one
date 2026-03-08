def parse_object(message):
    """Parse a message string returned by upstream into a dictionary.

    The real project has a richer parser; here we implement a defensive
    best-effort parser that looks for simple key/value pairs or returns
    sensible defaults.
    """
    if not message:
        return {}

    # If message is already a dict-like object, just return it
    if isinstance(message, dict):
        return message

    text = str(message)
    out = {}

    # Common patterns: "Nickname: X", "ID: 123", "Country: YY"
    for part in text.split('\n'):
        if ':' in part:
            key, val = part.split(':', 1)
            key = key.strip().lower().replace(' ', '-').replace('_', '-')
            val = val.strip()
            out[key] = val

    # Best-effort mappings used by the app
    if 'in-game-nickname' in out:
        out['in-game-nickname'] = out.get('in-game-nickname')
    if 'nickname' in out and 'in-game-nickname' not in out:
        out['in-game-nickname'] = out.get('nickname')

    # country codes or region
    if 'country' in out and len(out.get('country', '')) == 2:
        out['country'] = out.get('country')

    return out
