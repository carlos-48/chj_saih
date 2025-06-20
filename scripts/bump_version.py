import re
import sys
import os

def bump_version(release_type):
    setup_py_path = "setup.py"
    try:
        with open(setup_py_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: {setup_py_path} not found.")
        sys.exit(1)

    version_regex = r"version\s*=\s*["'](\d+)\.(\d+)\.(\d+)["']"
    match = re.search(version_regex, content)

    if not match:
        print(f"Error: Could not find version string in {setup_py_path}")
        sys.exit(1)

    major, minor, patch = map(int, match.groups())

    if release_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif release_type == "minor":
        minor += 1
        patch = 0
    elif release_type == "patch":
        patch += 1
    else:
        print(f"Error: Invalid release type '{release_type}'. Must be one of 'major', 'minor', 'patch'.")
        sys.exit(1)

    new_version = f"{major}.{minor}.{patch}"
    # Preserve the original quote type used in setup.py for the version string
    quote_char = match.group(0)[match.group(0).find("version=")+len("version=")+1]
    if quote_char not in ["'", '"']: # Should not happen with the current regex but good for robustness
        quote_char = '"' # Default to double quotes
    new_version_line = f'version={quote_char}{new_version}{quote_char}'

    # Ensure we are replacing the correct part, could be made more robust
    # This regex finds the version assignment line, capturing the part before the version string
    # and the part after it, to reconstruct the line with the new version.
    # It specifically looks for version="X.Y.Z" or version='X.Y.Z'
    old_version_line_pattern = re.compile(r"(version\s*=\s*["'])"+r"\d+\.\d+\.\d+"+r"(["'])")

    # Replace the version number part of the matched line
    # The replacement function uses the captured groups (quote characters) to reconstruct the line
    def replace_version_in_line(m):
        return f"{m.group(1)}{new_version}{m.group(2)}"

    new_content = old_version_line_pattern.sub(replace_version_in_line, content, 1)

    try:
        with open(setup_py_path, "w") as f:
            f.write(new_content)
    except Exception as e:
        print(f"Error writing updated content to {setup_py_path}: {e}")
        sys.exit(1)

    print(new_version) # Output new version for GitHub Actions

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <major|minor|patch>")
        sys.exit(1)

    release_type_arg = sys.argv[1]
    bump_version(release_type_arg)
