"""Keep authored and imported documentation pages within explicit MkDocs navigation."""


def navigation_paths(nav):
    if isinstance(nav, str):
        return {nav}
    if isinstance(nav, list):
        return set().union(*(navigation_paths(item) for item in nav))
    if isinstance(nav, dict):
        return set().union(*(navigation_paths(item) for item in nav.values()))
    raise ValueError("explicit navigation must contain lists, mappings and page paths")


def validate_navigation(files, nav):
    selected = navigation_paths(nav)
    unexpected = sorted(
        file.src_uri for file in files.documentation_pages() if file.src_uri not in selected
    )
    if unexpected:
        raise ValueError(
            "documentation pages missing from explicit navigation: " + ", ".join(unexpected)
        )
    return files
