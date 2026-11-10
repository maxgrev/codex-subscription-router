#!/usr/bin/env python3
"""Create an independently signed ChatGPT.app copy with Codex multiplexing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
DEFAULT_SOURCE = Path("/Applications/ChatGPT.app")
DESKTOP_DISPLAY_NAME = "Codex++"
DEFAULT_DESTINATION = Path.home() / "Applications" / f"{DESKTOP_DISPLAY_NAME}.app"
LEGACY_DESKTOP_APP_NAME = "Codex Subscription Router.app"
DEFAULT_STATE_ROOT = Path.home() / ".codex-mux"
CONTROL_PORT = 48123
DESKTOP_PROFILE_NAME = DESKTOP_DISPLAY_NAME
LEGACY_DESKTOP_PROFILE_NAME = "Codex Subscription Router"
DESKTOP_BUNDLE_IDENTIFIER = "app.cdxmux.multi"
OPENAI_DESKTOP_CODE_IDENTIFIER = "com.openai.codex"
OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER = "com.openai.sky.CUAService"
COMPUTER_USE_BUNDLE_IDENTIFIER = "com.cdxmux.sky.CUAService"
COMPUTER_USE_DISPLAY_NAME = f"{DESKTOP_DISPLAY_NAME} Computer Use"
COMPUTER_USE_APP_NAME = f"{COMPUTER_USE_DISPLAY_NAME}.app"
LEGACY_COMPUTER_USE_APP_NAME = "Codex Subscription Router Computer Use.app"
LAUNCH_SERVICES_REGISTER = Path(
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
    "LaunchServices.framework/Support/lsregister"
)
ASAR_UNPACK_DIRECTORIES = (
    "node_modules/{@worklouder,better-sqlite3,node-mac-permissions,node-pty,objc-js}"
)
PREFERRED_SIGNING_IDENTITY_PREFIXES = (
    "Developer ID Application:",
    "Apple Development:",
)
PROVISION_PROFILE_DIRECTORIES = (
    Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles",
    Path.home() / "Library/MobileDevice/Provisioning Profiles",
)
PROFILE_TEAM_ENTITLEMENTS = (
    "com.apple.application-identifier",
    "com.apple.developer.team-identifier",
    "keychain-access-groups",
)
OPENAI_INTERNAL_TEAM_IDENTIFIER = "HX7739G8FX"
OPENAI_DISTRIBUTION_TEAM_IDENTIFIER = "2DC432GLL2"
TESTED_SOURCE_BUILDS = {
    (
        "26.803.61601",
        "6396",
    ): "d5a44ed9e2f1db5f81dbbe85408aed256f3203c5b16f00817bb9d7cd941343cf",
    (
        "26.814.41407",
        "6720",
    ): "8fba32f8baa6d984b0f0f4149d3da46221e3adb3b52836f85fe65e31e655a8c0",
    (
        "26.818.22352",
        "6872",
    ): "530f670f3859f2f82c3dd7e188537b369820b2ff1fe6a2207eec16abdb7d1d42",
    (
        "26.818.41509",
        "6962",
    ): "8eb91bd9efbf9a4dd04b9b0afdbfcb4e0bab5da18c1919ad74ca327c00c7e791",
    (
        "26.818.61809",
        "7019",
    ): "76bbcdc2a4a2d77cfe03904a6537d0a655f9892f27a8925e3a6c7b613801d4cf",
    (
        "26.820.60940",
        "7119",
    ): "c964aebbf9a6a0f70799d01215c611d8ef6ee63f816b3d57beccddd47a811fd9",
    (
        "26.825.32147",
        "7303",
    ): "0462b03e878f0e78b223b849ee14cbba0de043f2c16acebee163cb95daa622ef",
    (
        "26.825.51511",
        "7377",
    ): "f56ac8d5254a10fc4a04e7417fa787d135c3bbca49bad7d668d4ae65833d40c7",
    (
        "26.831.21537",
        "7579",
    ): "4df5376dd69ec8fd1d99c7e590982d8a10b762116ceb1961c0e2addcc08b07fa",
    (
        "26.901.20858",
        "7658",
    ): "3dee62fa9bfabc58d1c96d9de1b04ab2a09597e78b9f39f14403e26d627f8b73",
    (
        "26.901.22334",
        "7746",
    ): "405f0e1600fc63851abe4c763ec0546f56c32da312c2c2745e2b997c579ce0d0",
    (
        "26.901.41123",
        "7942",
    ): "959726c107e11691044b60445e34e1a5c732d89320b0bee22cf1a3b13da00cd1",
    (
        "26.901.51231",
        "8109",
    ): "64fc2f27d2dddfa968acfacbe5e4e0328071bdc406351ff4a7d18f0b4692c83d",
    (
        "26.908.40834",
        "8881",
    ): "bb40cd8811887363104a19291346af9595632e0e956316a1086b274fb8e3eafc",
    (
        "26.908.70816",
        "9275",
    ): "100b3a06768326eec58ae32e54fa7b85368fef8d4ead5a5866ecb0e8751bdeaa",
    (
        "26.911.61220",
        "9647",
    ): "f3ea5ab82e0503d283c98ea21b0ecfde4d8fe4c740fb1d81dfc57b6f5c22ce1f",
    (
        "26.915.31029",
        "9771",
    ): "3c471b5f7573c5cc1cdf7d7e732cb41e16cccd50dcec377071cb29f3e2d04cbb",
    (
        "26.915.31945",
        "9922",
    ): "1f7939c1c781887c167043c4d1d307af3400d324685cfc315dfe2f80e634f483",
    (
        "26.930.31730",
        "12947",
    ): "87a934de9a00a04d2e534693db87756321ca4f3413f6caa55d3a0d32a5543836",
    (
        "26.1103.60933",
        "25894",
    ): "a77588b2dcfa9b394d722dd8c2c8b13d3a09bacd49c839cc715245742dba6048",
}
EXPECTED_CUA_IDENTIFIER_REPLACEMENTS = 49
EXPECTED_ASAR_CUA_IDENTIFIER_REPLACEMENTS = 8
EXPECTED_ASAR_CUA_GROUP_REPLACEMENTS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {PROJECT_VERSION}")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing destination after moving it to a timestamped backup.",
    )
    parser.add_argument(
        "--allow-adhoc-signing",
        action="store_true",
        help="Allow an ad-hoc signature (Appshots and Computer Use may stop working).",
    )
    parser.add_argument(
        "--allow-untested-source",
        action="store_true",
        help="Continue after an explicit version, build, or ASAR hash mismatch.",
    )
    parser.add_argument(
        "--allow-signing-team-change",
        action="store_true",
        help="Replace an existing build signed by a different Apple team.",
    )
    return parser.parse_args()


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"required tool not found: {name}")


def resolve_signing_identity(allow_adhoc: bool) -> str:
    configured = os.environ.get("CODEX_MUX_SIGNING_IDENTITY", "").strip()
    if configured:
        return configured
    identities = output(["security", "find-identity", "-v", "-p", "codesigning"])
    available = re.findall(
        r'^\s*\d+\)\s+[0-9A-F]+\s+"([^"]+)"',
        identities,
        re.MULTILINE,
    )
    development_identities = [
        identity
        for identity in available
        if identity.startswith("Apple Development:")
    ]
    for prefix in PREFERRED_SIGNING_IDENTITY_PREFIXES:
        if prefix == "Apple Development:":
            for identity in development_identities:
                team = signing_team_identifier(identity)
                if team is not None and find_mac_wildcard_profile(team) is not None:
                    return identity
        for identity in available:
            if identity.startswith(prefix):
                return identity
    if allow_adhoc:
        print(
            "Warning: using an ad-hoc signature; Appshots and Computer Use may be unavailable.",
            file=sys.stderr,
        )
        return "-"
    raise RuntimeError(
        "no team-backed code-signing identity found; set CODEX_MUX_SIGNING_IDENTITY "
        "or explicitly pass --allow-adhoc-signing"
    )


def signing_team_identifier(identity: str) -> str | None:
    if identity == "-":
        return None
    certificate = subprocess.run(
        ["security", "find-certificate", "-c", identity, "-p"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subject = subprocess.run(
        ["openssl", "x509", "-noout", "-subject"],
        check=True,
        input=certificate.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.decode("utf-8", "replace")
    match = re.search(r"\bOU=([A-Z0-9]{10})\b", subject)
    if match is not None:
        return match.group(1)
    match = re.search(r"\(([A-Z0-9]{10})\)$", identity)
    if match is None:
        raise RuntimeError(
            "could not read the 10-character Apple team ID from the signing certificate"
        )
    return match.group(1)


def provision_profile_info(path: Path) -> dict[str, object] | None:
    result = subprocess.run(
        ["security", "cms", "-D", "-i", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        info = plistlib.loads(result.stdout)
    except plistlib.InvalidFileException:
        return None
    return info if isinstance(info, dict) else None


def find_mac_wildcard_profile(team_identifier: str) -> Path | None:
    """Find a local Mac development profile that can sign arbitrary team app IDs."""
    for directory in PROVISION_PROFILE_DIRECTORIES:
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix not in {".mobileprovision", ".provisionprofile"}:
                continue
            info = provision_profile_info(path)
            if info is None:
                continue
            entitlements = info.get("Entitlements")
            if not isinstance(entitlements, dict):
                continue
            team = entitlements.get("com.apple.developer.team-identifier")
            teams = info.get("TeamIdentifier")
            if team != team_identifier and teams != [team_identifier]:
                continue
            platforms = info.get("Platform") or []
            name = str(info.get("Name") or "")
            if "OSX" not in platforms and "MacOS" not in platforms and "Mac " not in name:
                continue
            if entitlements.get("com.apple.application-identifier") != f"{team_identifier}.*":
                continue
            return path
    return None


def embed_provision_profile(bundle: Path, profile: Path) -> None:
    destination = bundle / "Contents" / "embedded.provisionprofile"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile, destination)


def signed_code_metadata(path: Path) -> tuple[str | None, str | None]:
    result = subprocess.run(
        ["codesign", "--display", "--verbose=4", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    details = result.stdout + result.stderr
    identifier_match = re.search(r"^Identifier=(.+)$", details, re.MULTILINE)
    team_match = re.search(r"^TeamIdentifier=(.+)$", details, re.MULTILINE)
    identifier = identifier_match.group(1).strip() if identifier_match else None
    team = team_match.group(1).strip() if team_match else None
    if team == "not set":
        team = None
    return identifier, team


def verify_signed_code(
    path: Path,
    expected_identifier: str,
    expected_team: str | None,
) -> None:
    run(["codesign", "--verify", "--deep", "--strict", str(path)])
    identifier, team = signed_code_metadata(path)
    if identifier != expected_identifier:
        raise RuntimeError(
            f"unexpected signing identifier on {path}: {identifier!r}"
        )
    if team != expected_team:
        raise RuntimeError(f"unexpected signing team on {path}: {team!r}")


def existing_signing_team(path: Path) -> str | None:
    if not path.exists():
        return None
    plist_path = path / "Contents" / "Info.plist"
    if plist_path.is_file():
        try:
            with plist_path.open("rb") as handle:
                recorded = plistlib.load(handle).get("CodexMuxSigningTeamIdentifier")
            if isinstance(recorded, str) and recorded != "":
                return None if recorded == "adhoc" else recorded
        except (OSError, plistlib.InvalidFileException):
            pass
    _, team = signed_code_metadata(path)
    return team


def ensure_components_are_stopped(paths: tuple[Path, ...]) -> None:
    # Match paths as text; pgrep would read the "++" in Codex++ as a regex.
    commands = output(["ps", "-ax", "-o", "command="]).splitlines()
    for path in paths:
        if not path.exists():
            continue
        if any(str(path) in command for command in commands):
            raise RuntimeError(
                f"quit the running component before replacing it: {path}"
            )


MACH_O_MAGICS = {
    b"\xfe\xed\xfa\xce",  # 32-bit, big endian
    b"\xfe\xed\xfa\xcf",  # 64-bit, big endian
    b"\xce\xfa\xed\xfe",  # 32-bit, little endian
    b"\xcf\xfa\xed\xfe",  # 64-bit, little endian
    b"\xca\xfe\xba\xbe",  # universal binary
    b"\xbe\xba\xfe\xca",  # universal binary, little endian
}


def is_mach_o(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACH_O_MAGICS
    except OSError:
        return False


def arm64_swift_small_string(value: str) -> bytes:
    """Encode the instructions used to materialize a 10-byte Swift string."""
    encoded = value.encode("ascii")
    if len(encoded) != 10:
        raise ValueError("a signing team identifier must contain 10 ASCII bytes")

    def instruction(base: int, immediate: int, register: int, shift: int = 0) -> bytes:
        word = base | ((shift // 16) << 21) | (immediate << 5) | register
        return word.to_bytes(4, "little")

    chunks = [
        int.from_bytes(encoded[index : index + 2], "little")
        for index in range(0, len(encoded), 2)
    ]
    return b"".join(
        (
            instruction(0xD2800000, chunks[0], 0),
            instruction(0xF2800000, chunks[1], 0, 16),
            instruction(0xF2800000, chunks[2], 0, 32),
            instruction(0xF2800000, chunks[3], 0, 48),
            instruction(0xD2800000, chunks[4], 1),
            instruction(0xF2800000, 0xEA00, 1, 48),
        )
    )


def swift_small_string_constant(value: str) -> bytes:
    """Encode a 10-byte Swift small string as stored in a Mach-O constant pool."""
    encoded = value.encode("ascii")
    if len(encoded) != 10:
        raise ValueError("a signing team identifier must contain 10 ASCII bytes")
    return encoded + bytes(5) + bytes([0xEA])


def asar_header_sha256(path: Path) -> str:
    """Return the SHA-256 Electron stores in ElectronAsarIntegrity.

    Electron hashes the ASAR header JSON, not the whole archive. 26.901
    started enforcing that check and rejects a full-file digest.
    """
    with path.open("rb") as handle:
        size_prefix = handle.read(8)
        if len(size_prefix) != 8:
            raise RuntimeError(f"asar archive is truncated: {path}")
        header_pickle_size = struct.unpack_from("<I", size_prefix, 4)[0]
        header_pickle = handle.read(header_pickle_size)
    if len(header_pickle) != header_pickle_size:
        raise RuntimeError(f"asar header is truncated: {path}")
    header_string_size = struct.unpack_from("<I", header_pickle, 4)[0]
    header_json = header_pickle[8 : 8 + header_string_size]
    if len(header_json) != header_string_size:
        raise RuntimeError(f"asar header JSON is truncated: {path}")
    return hashlib.sha256(header_json).hexdigest()


ASAR_INTEGRITY_SENTINEL = b"AGbevlPCksUGKNL8TSn7wGmJEuJsXb2A"


def electron_asar_integrity_digest(asar_path: Path) -> bytes:
    """Match Electron's embedded digest of the Info.plist integrity dictionary."""
    header_hash = asar_header_sha256(asar_path).encode("ascii")
    return hashlib.sha256(b"Resources/app.asar" + b"SHA256" + header_hash).digest()


def patch_embedded_asar_integrity(app: Path, asar_path: Path) -> None:
    """Update the framework digest that binds ElectronAsarIntegrity to the app.

    Electron 154 rejects the Info.plist hash unless this slot matches. The
    header hash in Info.plist still checks the archive itself.
    """
    digest = electron_asar_integrity_digest(asar_path)
    framework_root = (
        app / "Contents" / "Frameworks" / "Codex Framework.framework"
    )
    binaries = [
        candidate
        for candidate in framework_root.rglob("Codex Framework")
        if candidate.is_file() and not candidate.is_symlink()
    ]
    if len(binaries) != 1:
        raise RuntimeError(
            f"expected one Codex framework binary, found {len(binaries)}"
        )
    binary = binaries[0]
    data = bytearray(binary.read_bytes())
    offset = data.find(ASAR_INTEGRITY_SENTINEL)
    if offset < 0:
        return
    if data.find(ASAR_INTEGRITY_SENTINEL, offset + 1) != -1:
        raise RuntimeError("found more than one embedded ASAR integrity digest")
    used = data[offset + 32]
    version = data[offset + 33]
    if used != 1 or version != 1:
        raise RuntimeError(
            "embedded ASAR integrity digest has an unexpected slot "
            f"(used={used}, version={version})"
        )
    start = offset + 34
    data[start : start + 32] = digest
    binary.write_bytes(data)


def replace_same_length_identifier(
    path: Path, original: str, replacement: str
) -> int:
    """Replace an embedded identifier without changing binary or bundle offsets."""
    original_bytes = original.encode("ascii")
    replacement_bytes = replacement.encode("ascii")
    if len(original_bytes) != len(replacement_bytes):
        raise RuntimeError("replacement identifiers must have the same byte length")
    data = path.read_bytes()
    count = data.count(original_bytes)
    if count:
        path.write_bytes(data.replace(original_bytes, replacement_bytes))
    return count


def computer_use_package(app: Path) -> Path:
    return (
        app
        / "Contents"
        / "Resources"
        / "cua_node"
        / "lib"
        / "node_modules"
        / "@oai"
        / "sky"
    )


def bundled_codex_app(app: Path) -> Path:
    return app / "Contents" / "Resources" / "codex-cli" / "CodexCLI.app"


def bundled_codex_executable(app: Path) -> Path:
    return bundled_codex_app(app) / "Contents" / "MacOS" / "codex"


def resign_codex_framework(
    app: Path, identity: str, team_identifier: str | None
) -> None:
    """Re-sign Codex Framework after the embedded asar digest changes.

    Helper processes load that framework. They abort when its team no longer
    matches theirs, so the helpers have to move to the same identity. Team
    application groups from the official profile are dropped; this development
    identity has no profile that grants them.
    """
    framework = app / "Contents" / "Frameworks" / "Codex Framework.framework"
    if not framework.is_dir():
        return
    bundle_suffixes = {".app", ".appex", ".bundle", ".framework", ".xpc"}

    def inside_nested_bundle(path: Path) -> bool:
        current = path.parent
        while current != framework and current != current.parent:
            if current.suffix in bundle_suffixes:
                return True
            current = current.parent
        return False

    mach_os = [
        candidate
        for candidate in framework.rglob("*")
        if candidate.is_file()
        and not candidate.is_symlink()
        and is_mach_o(candidate)
        and not inside_nested_bundle(candidate)
    ]
    for executable in sorted(mach_os, key=lambda candidate: len(candidate.parts), reverse=True):
        sign_runtime_executable(
            executable,
            identity,
            None,
            entitlements_for_independent_app(
                executable,
                identity,
                team_identifier,
                DESKTOP_BUNDLE_IDENTIFIER,
            ),
            runtime=True,
        )

    bundles = [
        candidate
        for candidate in framework.rglob("*")
        if candidate.is_dir() and candidate.suffix in bundle_suffixes
    ]
    bundles.append(framework)
    for bundle in sorted(set(bundles), key=lambda candidate: len(candidate.parts), reverse=True):
        executable = bundle_main_executable(bundle)
        entitlements = (
            entitlements_for_independent_app(
                executable,
                identity,
                team_identifier,
                DESKTOP_BUNDLE_IDENTIFIER,
            )
            if executable is not None
            else None
        )
        identifier = (
            "com.openai.codex.framework" if bundle == framework else None
        )
        sign_runtime_bundle(
            bundle,
            identity,
            identifier,
            entitlements,
            runtime=True,
        )


def retire_stale_cached_computer_use_app() -> None:
    """Move aside only a prior custom helper copied into the shared Codex home."""
    cached_app = (
        Path.home() / ".codex" / "computer-use" / "Codex Computer Use.app"
    )
    plist_path = cached_app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return
    try:
        with plist_path.open("rb") as handle:
            bundle_identifier = plistlib.load(handle).get("CFBundleIdentifier")
    except (OSError, plistlib.InvalidFileException):
        return
    if bundle_identifier != COMPUTER_USE_BUNDLE_IDENTIFIER:
        return
    if LAUNCH_SERVICES_REGISTER.is_file():
        run([str(LAUNCH_SERVICES_REGISTER), "-u", str(cached_app)])
    backup = cached_app.with_name(
        f"Codex Computer Use backup-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    cached_app.rename(backup)
    print(f"Stale cached Computer Use helper moved to {backup}")


def migrate_legacy_profile() -> None:
    """Carry sign-ins and caches over from the profile name used before Codex++."""
    library = Path.home() / "Library"
    for parent in (library / "Application Support", library / "Caches"):
        legacy = parent / LEGACY_DESKTOP_PROFILE_NAME
        profile = parent / DESKTOP_PROFILE_NAME
        if not legacy.is_dir():
            continue
        if profile.exists():
            print(f"Kept {profile}; the older copy remains at {legacy}")
            continue
        legacy.rename(profile)
        print(f"Moved {legacy} to {profile}")


def patch_computer_use_identity(app: Path, team_identifier: str | None) -> None:
    """Give the copied CUA service an independent identity and trusted callers."""
    package = computer_use_package(app)
    service = package / "Codex Computer Use.app"
    executable = service / "Contents" / "MacOS" / "SkyComputerUseService"
    if not executable.is_file():
        raise RuntimeError("bundled Codex Computer Use service was not found")

    for profile in package.rglob("embedded.provisionprofile"):
        profile.unlink()

    identifier_replacements = 0
    for candidate in package.rglob("*"):
        if candidate.is_file() and not candidate.is_symlink():
            identifier_replacements += replace_same_length_identifier(
                candidate,
                OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            )
    if identifier_replacements != EXPECTED_CUA_IDENTIFIER_REPLACEMENTS:
        raise RuntimeError(
            "expected "
            f"{EXPECTED_CUA_IDENTIFIER_REPLACEMENTS} Computer Use identity "
            f"references, found {identifier_replacements}"
        )

    plist_path = service / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    info["CFBundleIdentifier"] = COMPUTER_USE_BUNDLE_IDENTIFIER
    info["CFBundleDisplayName"] = COMPUTER_USE_DISPLAY_NAME
    info["CFBundleName"] = COMPUTER_USE_DISPLAY_NAME
    # Launch Services does not pass the desktop process environment into the
    # helper. Without this, Computer Use still opens the official app-group
    # socket that Apple Development signing cannot create.
    installed_helper = DEFAULT_DESTINATION.parent / COMPUTER_USE_APP_NAME
    info["LSEnvironment"] = {
        "SKY_CUA_SERVICE_NATIVE_PIPE_PATH": str(DEFAULT_STATE_ROOT / "computer-use.sock"),
        "SKY_CUA_SERVICE_PATH": str(installed_helper),
    }
    for key in list(info):
        if key.startswith("SU"):
            del info[key]
    with plist_path.open("wb") as handle:
        plistlib.dump(info, handle, fmt=plistlib.FMT_BINARY, sort_keys=False)

    if team_identifier is None:
        return
    binary = executable.read_bytes()
    instruction_replacement = arm64_swift_small_string(team_identifier)
    constant_replacement = swift_small_string_constant(team_identifier)
    for original_team, description in (
        (OPENAI_INTERNAL_TEAM_IDENTIFIER, "internal"),
        (OPENAI_DISTRIBUTION_TEAM_IDENTIFIER, "distribution"),
    ):
        instruction = arm64_swift_small_string(original_team)
        constant = swift_small_string_constant(original_team)
        instruction_matches = binary.count(instruction)
        constant_matches = binary.count(constant)
        expected_constant = 1 if description == "internal" else 3
        if instruction_matches == 2:
            binary = binary.replace(instruction, instruction_replacement)
            expected_raw_matches = 1 if description == "internal" else 17
        elif constant_matches == expected_constant:
            binary = binary.replace(constant, constant_replacement)
            expected_raw_matches = 0 if description == "internal" else 14
        else:
            raise RuntimeError(
                f"expected two Computer Use {description}-team instruction "
                f"checks or {expected_constant} constant-pool strings, found "
                f"{instruction_matches} instructions and "
                f"{constant_matches} constants; the official app layout may "
                "have changed"
            )

        raw_original = original_team.encode("ascii")
        raw_replacement = team_identifier.encode("ascii")
        raw_match_count = binary.count(raw_original)
        if raw_match_count != expected_raw_matches:
            raise RuntimeError(
                f"expected {expected_raw_matches} Computer Use {description}-team "
                f"constants, found {raw_match_count}; the official app layout may have changed"
            )
        if raw_match_count:
            binary = binary.replace(raw_original, raw_replacement)

    # Keep the official production desktop ID. The inner Electron stub is still
    # signed `com.openai.codex`; overwriting that slot makes the helper reject
    # node_repl with "Sender process is not authenticated". The wrapper ID goes
    # in the unused Atlas slot (same length).
    production_bundle_id = b"com.openai.codex\0"
    wrapper_slot = b"com.openai.atlas\0"
    wrapper_bundle_id = DESKTOP_BUNDLE_IDENTIFIER.encode("ascii") + b"\0"
    if len(wrapper_bundle_id) != len(wrapper_slot):
        raise RuntimeError(
            "the independent bundle identifier must match the CUA identifier length"
        )
    if binary.count(production_bundle_id) != 1:
        raise RuntimeError("Computer Use production bundle ID must remain present")
    if binary.count(wrapper_slot) != 1:
        raise RuntimeError("could not find the Computer Use Atlas bundle ID slot")
    executable.write_bytes(binary.replace(wrapper_slot, wrapper_bundle_id))


def patch_asar_computer_use_identity(
    extracted: Path, team_identifier: str | None
) -> None:
    """Keep desktop launch, temp-file, and service references on the new CUA ID."""
    replacements = 0
    for candidate in extracted.rglob("*"):
        if candidate.is_file() and not candidate.is_symlink():
            replacements += replace_same_length_identifier(
                candidate,
                OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            )
    if replacements != EXPECTED_ASAR_CUA_IDENTIFIER_REPLACEMENTS:
        raise RuntimeError(
            "expected "
            f"{EXPECTED_ASAR_CUA_IDENTIFIER_REPLACEMENTS} Computer Use references "
            f"in app.asar, found {replacements}"
        )
    if not team_identifier:
        return
    official_group = (
        f"{OPENAI_DISTRIBUTION_TEAM_IDENTIFIER}.{COMPUTER_USE_BUNDLE_IDENTIFIER}"
    )
    router_group = f"{team_identifier}.{COMPUTER_USE_BUNDLE_IDENTIFIER}"
    group_replacements = 0
    for candidate in extracted.rglob("*"):
        if candidate.is_file() and not candidate.is_symlink():
            group_replacements += replace_same_length_identifier(
                candidate,
                official_group,
                router_group,
            )
    if group_replacements != EXPECTED_ASAR_CUA_GROUP_REPLACEMENTS:
        raise RuntimeError(
            "expected "
            f"{EXPECTED_ASAR_CUA_GROUP_REPLACEMENTS} Computer Use app-group "
            f"references in app.asar, found {group_replacements}"
        )


GROUP_CONTAINER_PIPE_PATTERN = re.compile(
    r"([A-Za-z_$][\w$]*)\.join\(([A-Za-z_$][\w$]*)\(\),"
    r'"Library","Group Containers",'
    r'"[A-Z0-9]{10}\.com\.(?:openai|cdxmux)\.sky\.CUAService",'
    r'"IPC","computeruse\.sock"\)'
)
COMPUTER_USE_LAUNCHER_CLIENT = (
    'client="${codex_home}/computer-use/Codex Computer Use.app/Contents/'
    'SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient"'
)
COMPUTER_USE_LAUNCHER_CLIENT_REPLACEMENT = """if [ -n "${SKY_CUA_SERVICE_PATH:-}" ]; then
  client="${SKY_CUA_SERVICE_PATH}/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient"
else
  client="${codex_home}/computer-use/Codex Computer Use.app/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient"
fi"""


def patch_computer_use_ipc(app: Path) -> None:
    """Keep Computer Use on the mux pipe instead of OpenAI app groups."""
    resources = app / "Contents" / "Resources"
    pipe_replacements = 0
    for candidate in (resources / "cua_node").rglob("native-pipe.js"):
        original = candidate.read_text(encoding="utf-8")
        updated, count = GROUP_CONTAINER_PIPE_PATTERN.subn(
            r'\1.join(\2(),".codex-mux","computer-use.sock")',
            original,
        )
        if count:
            candidate.write_text(updated, encoding="utf-8")
            pipe_replacements += count
    if pipe_replacements < 1:
        raise RuntimeError(
            "could not retarget Computer Use away from the official app-group socket"
        )

    identity_replacements = 0
    for candidate in (resources / "cua_node").rglob("native-pipe.js"):
        original = candidate.read_text(encoding="utf-8")
        if OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER not in original:
            continue
        candidate.write_text(
            original.replace(
                OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            ),
            encoding="utf-8",
        )
        identity_replacements += 1
    for executable_name in ("node", "node_repl"):
        identity_replacements += replace_same_length_identifier(
            resources / "cua_node" / "bin" / executable_name,
            OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER,
            COMPUTER_USE_BUNDLE_IDENTIFIER,
        )
    if identity_replacements < 1:
        raise RuntimeError(
            "could not retarget leftover Computer Use bundle IDs outside @oai/sky"
        )

    launcher_replacements = 0
    for launcher in (resources / "plugins").rglob("computer-use-client-launcher"):
        original = launcher.read_text(encoding="utf-8")
        if COMPUTER_USE_LAUNCHER_CLIENT not in original:
            continue
        launcher.write_text(
            original.replace(
                COMPUTER_USE_LAUNCHER_CLIENT,
                COMPUTER_USE_LAUNCHER_CLIENT_REPLACEMENT,
                1,
            ),
            encoding="utf-8",
        )
        launcher_replacements += 1
    if launcher_replacements < 1:
        raise RuntimeError("could not retarget Computer Use client launchers")


def sign_native_code_tree(root: Path, identity: str) -> None:
    """Sign native modules before ASAR records their final sizes."""
    if not root.is_dir():
        return
    for candidate in root.rglob("*"):
        if not is_mach_o(candidate):
            continue
        run(
            [
                "codesign",
                "--force",
                "--sign",
                identity,
                "--timestamp=none",
                "--options",
                "runtime",
                str(candidate),
            ]
        )


TEAM_SCOPED_ENTITLEMENTS = (
    "com.apple.application-identifier",
    "com.apple.developer.team-identifier",
    "com.apple.security.application-groups",
    "keychain-access-groups",
)
# Restricted keys copied from official ChatGPT. Apple Development signing
# without a matching provision profile makes Launch Services refuse to open
# the app ("can't be opened") and SIGKILL the stub (exit 137).
RESTRICTED_RUNTIME_ENTITLEMENTS = (
    "com.apple.developer.aps-environment",
    "com.apple.security.personal-information.calendars",
    "com.apple.security.personal-information.addressbook",
    "com.apple.security.personal-information.location",
)


def read_runtime_entitlements(executable: Path) -> dict[str, object] | None:
    result = subprocess.run(
        ["codesign", "--display", "--entitlements", ":-", str(executable)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not result.stdout.strip():
        return None
    try:
        entitlements = plistlib.loads(result.stdout)
    except plistlib.InvalidFileException as error:
        raise RuntimeError(
            f"could not read signing entitlements from {executable}"
        ) from error
    if not isinstance(entitlements, dict):
        raise RuntimeError(f"invalid signing entitlements on {executable}")
    return entitlements


def strip_restricted_runtime_entitlements(
    entitlements: dict[str, object],
) -> dict[str, object]:
    sanitized = dict(entitlements)
    for key in TEAM_SCOPED_ENTITLEMENTS:
        sanitized.pop(key, None)
    for key in RESTRICTED_RUNTIME_ENTITLEMENTS:
        sanitized.pop(key, None)
    for key in list(sanitized):
        if key.startswith("com.apple.developer."):
            sanitized.pop(key, None)
    return sanitized


def sanitized_runtime_entitlements(executable: Path) -> dict[str, object] | None:
    """Keep runtime capabilities while removing the official app's team grants."""
    entitlements = read_runtime_entitlements(executable)
    if entitlements is None:
        return None
    return strip_restricted_runtime_entitlements(entitlements) or None


def remap_team_entitlements(
    entitlements: dict[str, object],
    team_identifier: str,
    bundle_identifier: str,
    profile: Path | None = None,
    group_identifier: str | None = None,
) -> dict[str, object]:
    """Keep local runtime rights and retarget team grants to a matching profile."""
    remapped = strip_restricted_runtime_entitlements(entitlements)
    remapped["com.apple.application-identifier"] = (
        f"{team_identifier}.{bundle_identifier}"
    )
    remapped["com.apple.developer.team-identifier"] = team_identifier
    remapped["keychain-access-groups"] = [f"{team_identifier}.*"]
    # Sequoia+ prompts "access data from other apps" on every launch when a
    # non-App-Store helper calls containerURL() without a Team-ID-prefixed
    # application group in its entitlements.
    if entitlements.get("com.apple.security.application-groups"):
        remapped["com.apple.security.application-groups"] = [
            f"{team_identifier}.{group_identifier or bundle_identifier}"
        ]
    return entitlements_allowed_by_profile(remapped, profile)


def bundle_identifier_for_executable(executable: Path, service: Path) -> str:
    """Read the patched bundle ID for a Computer Use executable."""
    current = executable.parent
    while True:
        plist_path = current / "Contents" / "Info.plist"
        if plist_path.is_file():
            with plist_path.open("rb") as handle:
                identifier = plistlib.load(handle).get("CFBundleIdentifier")
            if isinstance(identifier, str) and identifier:
                return identifier
        if current == service or current.parent == current:
            break
        current = current.parent
    return COMPUTER_USE_BUNDLE_IDENTIFIER


def profile_allows_get_task_allow(profile: Path | None) -> bool:
    if profile is None:
        return False
    info = provision_profile_info(profile)
    if info is None:
        return False
    entitlements = info.get("Entitlements")
    return isinstance(entitlements, dict) and bool(
        entitlements.get("com.apple.security.get-task-allow")
    )


def entitlements_allowed_by_profile(
    entitlements: dict[str, object],
    profile: Path | None,
) -> dict[str, object]:
    """Drop restricted keys the embedded profile does not authorize.

    Embedding a Mac development profile puts AMFI in profile-matching mode.
    `get-task-allow` is restricted; signing it when the wildcard profile
    omits it SIGKILLs the process at launch (exit 137).
    """
    allowed = dict(entitlements)
    if not profile_allows_get_task_allow(profile):
        allowed.pop("com.apple.security.get-task-allow", None)
    return allowed


def entitlements_for_independent_app(
    executable: Path,
    identity: str,
    team_identifier: str | None,
    bundle_identifier: str,
) -> dict[str, object]:
    """Allow the copied stub to load OpenAI-signed Electron frameworks.

    Do not embed a provision profile or team-scoped entitlements on the
    Electron desktop app. The stub keeps identifier `com.openai.codex` while
    the wrapper is `app.cdxmux.multi`; putting `application-identifier` on
    that pair makes AMFI SIGKILL the process. Computer Use gets the profile.
    """
    del team_identifier, bundle_identifier
    entitlements = strip_restricted_runtime_entitlements(
        read_runtime_entitlements(executable) or {}
    )
    entitlements["com.apple.security.cs.disable-library-validation"] = True
    if identity.startswith("Apple Development:"):
        entitlements["com.apple.security.get-task-allow"] = True
    return entitlements


AUTO_ENTITLEMENTS = object()


def sign_runtime_executable(
    executable: Path,
    identity: str,
    identifier: str | None = None,
    entitlements: dict[str, object] | None | object = AUTO_ENTITLEMENTS,
    runtime: bool = True,
) -> None:
    """Re-sign an embedded runtime without breaking JIT-backed processes."""
    if entitlements is AUTO_ENTITLEMENTS:
        entitlements = sanitized_runtime_entitlements(executable)
    command = [
        "codesign",
        "--force",
        "--sign",
        identity,
        "--timestamp=none",
    ]
    if runtime:
        command.extend(("--options", "runtime"))
    if identifier is None:
        command.append("--preserve-metadata=identifier")
    else:
        command.extend(("--identifier", identifier))
    if entitlements is None:
        run([*command, str(executable)])
        return
    with tempfile.TemporaryDirectory(prefix=".codesign-entitlements-") as temporary:
        entitlements_path = Path(temporary) / "entitlements.plist"
        with entitlements_path.open("wb") as handle:
            plistlib.dump(
                entitlements,
                handle,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            )
        run([*command, "--entitlements", str(entitlements_path), str(executable)])


def bundle_main_executable(bundle: Path) -> Path | None:
    plist_path = bundle / "Contents" / "Info.plist"
    executable_root = bundle / "Contents" / "MacOS"
    if bundle.suffix == ".framework":
        plist_path = bundle / "Versions" / "Current" / "Resources" / "Info.plist"
        executable_root = bundle / "Versions" / "Current"
    if not plist_path.is_file():
        return None
    with plist_path.open("rb") as handle:
        executable_name = plistlib.load(handle).get("CFBundleExecutable")
    if not isinstance(executable_name, str) or executable_name == "":
        return None
    executable = executable_root / executable_name
    return executable if executable.is_file() else None


def sign_runtime_bundle(
    bundle: Path,
    identity: str,
    identifier: str | None = None,
    entitlements: dict[str, object] | None | object = AUTO_ENTITLEMENTS,
    runtime: bool = True,
) -> None:
    if entitlements is AUTO_ENTITLEMENTS:
        executable = bundle_main_executable(bundle)
        entitlements = (
            sanitized_runtime_entitlements(executable)
            if executable is not None
            else None
        )
    command = [
        "codesign",
        "--force",
        "--sign",
        identity,
        "--timestamp=none",
    ]
    if runtime:
        command.extend(("--options", "runtime"))
    if identifier is not None:
        command.extend(("--identifier", identifier))
    if entitlements is None:
        run([*command, str(bundle)])
        return
    with tempfile.TemporaryDirectory(prefix=".codesign-entitlements-") as temporary:
        entitlements_path = Path(temporary) / "entitlements.plist"
        with entitlements_path.open("wb") as handle:
            plistlib.dump(
                entitlements,
                handle,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            )
        run([*command, "--entitlements", str(entitlements_path), str(bundle)])


def capture_computer_use_entitlements(
    app: Path,
) -> dict[Path, dict[str, object] | None]:
    service = computer_use_package(app) / "Codex Computer Use.app"
    if not service.is_dir():
        raise RuntimeError("bundled Codex Computer Use service was not found")
    return {
        executable.relative_to(service): read_runtime_entitlements(executable)
        for executable in service.rglob("*")
        if is_mach_o(executable)
    }


def sign_computer_use_code(
    app: Path,
    identity: str,
    preserved_entitlements: dict[Path, dict[str, object] | None],
    team_identifier: str | None,
) -> None:
    """Keep the Computer Use service and its callers on one signing team."""
    resources = app / "Contents" / "Resources"
    service = computer_use_package(app) / "Codex Computer Use.app"
    if not service.is_dir():
        raise RuntimeError("bundled Codex Computer Use service was not found")
    service_executable = service / "Contents" / "MacOS" / "SkyComputerUseService"
    profile = (
        find_mac_wildcard_profile(team_identifier)
        if team_identifier is not None
        else None
    )
    if profile is not None:
        embed_provision_profile(service, profile)
        print(f"Embedded Computer Use profile {profile.name}")

    for executable in sorted(
        (candidate for candidate in service.rglob("*") if is_mach_o(candidate)),
        key=lambda candidate: len(candidate.parts),
        reverse=True,
    ):
        relative = executable.relative_to(service)
        official = preserved_entitlements.get(relative) or {}
        if (
            profile is not None
            and team_identifier is not None
            and (
                executable == service_executable
                or official.get("com.apple.application-identifier")
                or official.get("com.apple.security.application-groups")
            )
        ):
            entitlements = remap_team_entitlements(
                official,
                team_identifier,
                bundle_identifier_for_executable(executable, service),
                profile,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            )
        else:
            entitlements = (
                strip_restricted_runtime_entitlements(official)
                if official
                else None
            )
        sign_runtime_executable(
            executable,
            identity,
            entitlements=entitlements,
        )

    bundle_suffixes = {".app", ".appex", ".bundle", ".framework", ".xpc"}
    bundles = [
        candidate
        for candidate in service.rglob("*")
        if candidate.is_dir() and candidate.suffix in bundle_suffixes
    ]
    bundles.append(service)
    for bundle in sorted(
        set(bundles),
        key=lambda candidate: len(candidate.parts),
        reverse=True,
    ):
        identifier = (
            COMPUTER_USE_BUNDLE_IDENTIFIER if bundle == service else None
        )
        executable = bundle_main_executable(bundle)
        official = (
            preserved_entitlements.get(executable.relative_to(service))
            if executable is not None
            else None
        ) or {}
        if (
            profile is not None
            and team_identifier is not None
            and (
                bundle == service
                or official.get("com.apple.application-identifier")
                or official.get("com.apple.security.application-groups")
            )
        ):
            bundle_id = (
                COMPUTER_USE_BUNDLE_IDENTIFIER
                if bundle == service or executable is None
                else bundle_identifier_for_executable(executable, service)
            )
            entitlements = remap_team_entitlements(
                official,
                team_identifier,
                bundle_id,
                profile,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            )
        else:
            entitlements = (
                strip_restricted_runtime_entitlements(official)
                if official
                else None
            )
        sign_runtime_bundle(bundle, identity, identifier, entitlements)
        run(["codesign", "--verify", "--deep", "--strict", str(bundle)])

    for executable_name in ("node", "node_repl"):
        executable = resources / "cua_node" / "bin" / executable_name
        sign_runtime_executable(executable, identity)
    sign_runtime_executable(
        app / "Contents" / "MacOS" / "ChatGPT",
        identity,
        OPENAI_DESKTOP_CODE_IDENTIFIER,
        entitlements_for_independent_app(
            app / "Contents" / "MacOS" / "ChatGPT",
            identity,
            team_identifier,
            DESKTOP_BUNDLE_IDENTIFIER,
        ),
        runtime=True,
    )


def sign_independent_app(
    app: Path, identity: str, team_identifier: str | None
) -> None:
    """Apply one stable identity throughout the modified Electron bundle."""
    # Official ChatGPT ships an OpenAI Developer ID profile. Leaving it in place
    # after re-signing with Apple Development makes macOS kill the process at
    # launch (exit 137) on current desktop builds.
    official_profile = app / "Contents" / "embedded.provisionprofile"
    if official_profile.is_file():
        official_profile.unlink()
    # 26.930 ships read-only plugin files with com.apple.provenance. xattr
    # cannot clear that attribute unless the file is writable.
    run(["chmod", "-R", "u+w", str(app)])
    run(["xattr", "-cr", str(app)])
    computer_use_entitlements = capture_computer_use_entitlements(app)
    patch_computer_use_identity(app, team_identifier)
    patch_computer_use_ipc(app)
    sign_computer_use_code(
        app, identity, computer_use_entitlements, team_identifier
    )
    # Never embed a development profile on the Electron desktop app. The
    # inner stub keeps `com.openai.codex` while the wrapper is independently
    # identified; AMFI treats that as a profile mismatch and SIGKILLs launch.
    # 26.901+ node_repl asks this host to ensureService(computer-use). The
    # helper then authenticates the sender team; leaving the official
    # Developer ID on codex.real makes that handshake fail.
    # 26.930 nests the CLI in CodexCLI.app. The mux is that bundle's main
    # executable and must stay flags=0x0. Sign the real CLI first so the
    # bundle seal records it, then sign the bundle without the hardened runtime.
    real_codex = bundled_codex_executable(app).with_name("codex.real")
    sign_runtime_executable(
        real_codex,
        identity,
        None,
        entitlements_for_independent_app(
            real_codex,
            identity,
            team_identifier,
            DESKTOP_BUNDLE_IDENTIFIER,
        ),
        runtime=True,
    )
    sign_runtime_bundle(
        bundled_codex_app(app),
        identity,
        "codex",
        None,
        runtime=False,
    )
    resign_codex_framework(app, identity, team_identifier)
    sign_runtime_bundle(
        app,
        identity,
        OPENAI_DESKTOP_CODE_IDENTIFIER,
        entitlements_for_independent_app(
            app / "Contents" / "MacOS" / "ChatGPT",
            identity,
            team_identifier,
            DESKTOP_BUNDLE_IDENTIFIER,
        ),
    )


def load_or_create_token() -> str:
    DEFAULT_STATE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    DEFAULT_STATE_ROOT.chmod(0o700)
    token_path = DEFAULT_STATE_ROOT / "control-token"
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{64}", token) is None:
            raise RuntimeError(f"invalid control token at {token_path}")
        token_path.chmod(0o600)
        return token
    token = secrets.token_hex(32)
    descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token)
    return token


def build_proxy(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "go",
            "build",
            "-trimpath",
            "-ldflags=-s -w",
            "-o",
            str(destination),
            "./cmd/codex-mux",
        ],
        cwd=PROJECT_ROOT,
    )
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_main_stub(app: Path) -> None:
    """Replace the Electron stub with one that passes the isolated profile.

    Chromium's process singleton picks its profile before any app code runs,
    so without `--user-data-dir` the copy hands off to official ChatGPT. A
    launcher that execs the stub is not an option: macOS never places menu bar
    items for a process exec'd from the bundle's main executable.
    """
    stub = app / "Contents" / "MacOS" / "ChatGPT"
    framework_version = (
        app / "Contents" / "Frameworks" / "Codex Framework.framework" / "Versions" / "Current"
    ).resolve().name
    framework_path = (
        f"../Frameworks/Codex Framework.framework/Versions/{framework_version}/Codex Framework"
    )
    if not (stub.parent / framework_path).is_file():
        raise RuntimeError(f"could not find the Codex framework at {framework_path}")
    with (app / "Contents" / "Info.plist").open("rb") as handle:
        minimum_system_version = plistlib.load(handle)["LSMinimumSystemVersion"]
    architectures = subprocess.run(
        ["lipo", "-archs", str(stub)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.split()
    entitlements = read_runtime_entitlements(stub) or {}
    with tempfile.TemporaryDirectory(prefix=".codex-main-stub-") as temporary:
        built = Path(temporary) / stub.name
        run(
            [
                "xcrun",
                "clang",
                "-Os",
                "-Wall",
                "-Wextra",
                *(flag for architecture in architectures for flag in ("-arch", architecture)),
                f"-mmacosx-version-min={minimum_system_version}",
                f'-DFRAMEWORK_RELATIVE_PATH="{framework_path}"',
                f'-DPROFILE_NAME="{DESKTOP_PROFILE_NAME}"',
                "-o",
                str(built),
                str(PROJECT_ROOT / "native" / "main_stub.c"),
            ]
        )
        # Signing reads the stub's entitlements (JIT, unsigned executable
        # memory) back from the binary, so carry the official ones over. Sign
        # outside the bundle so codesign treats it as a plain executable.
        sign_runtime_executable(
            built, "-", OPENAI_DESKTOP_CODE_IDENTIFIER, entitlements, runtime=False
        )
        shutil.copy2(built, stub)


def ensure_asar_tool() -> Path:
    asar = PROJECT_ROOT / "node_modules" / ".bin" / "asar"
    package_manifest = PROJECT_ROOT / "node_modules" / "@electron" / "asar" / "package.json"
    expected = json.loads(
        (PROJECT_ROOT / "package.json").read_text(encoding="utf-8")
    )["devDependencies"]["@electron/asar"]
    if not asar.exists() or not package_manifest.is_file():
        raise RuntimeError("run `npm ci --ignore-scripts` before patching")
    actual = json.loads(package_manifest.read_text(encoding="utf-8")).get("version")
    if actual != expected:
        raise RuntimeError(
            f"installed @electron/asar is {actual!r}, expected {expected!r}; "
            "run `npm ci --ignore-scripts`"
        )
    return asar


_JAVASCRIPT_CACHE: dict[Path, dict[Path, str]] = {}


def javascript_texts(extracted: Path) -> dict[Path, str]:
    cached = _JAVASCRIPT_CACHE.get(extracted)
    if cached is not None:
        return cached
    texts: dict[Path, str] = {}
    for root in (extracted / "webview", extracted / ".vite"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.js"):
            if "node_modules" in path.parts or path.stat().st_size > 20_000_000:
                continue
            try:
                texts[path] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
    _JAVASCRIPT_CACHE[extracted] = texts
    return texts


def write_javascript(extracted: Path, path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    cached = _JAVASCRIPT_CACHE.get(extracted)
    if cached is not None:
        cached[path] = text


def files_containing(extracted: Path, needle: str) -> list[Path]:
    return [
        path
        for path, text in javascript_texts(extracted).items()
        if needle in text
    ]


def require_text(extracted: Path, needle: str, description: str) -> tuple[Path, str]:
    found = files_containing(extracted, needle)
    if len(found) != 1:
        raise RuntimeError(f"expected one {description}, found {len(found)}")
    path = found[0]
    return path, javascript_texts(extracted)[path]


def module_containing(source: str, marker: str) -> str:
    index = source.find(marker)
    if index < 0:
        raise RuntimeError(f"could not find {marker}")
    starts = [
        match.start()
        for match in re.finditer(
            r"(?:^|[,{])[A-Za-z0-9_$]{1,12}\(e,t,[A-Za-z]\)\{",
            source,
        )
    ]
    if not starts:
        return source
    start = max(position for position in starts if position <= index)
    later = [position for position in starts if position > index]
    end = later[0] if later else len(source)
    return source[start:end]


def imported_binding(source: str, module_id: str) -> str:
    matches = set(
        re.findall(
            rf"([A-Za-z_$][\w$]*)=(?:n|a|r)\(\"{re.escape(module_id)}\"\)",
            source,
        )
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one import of {module_id}, found {sorted(matches)}"
        )
    return next(iter(matches))


def bind_mux_ui(source: str, bindings: dict[str, str]) -> str:
    for placeholder, value in bindings.items():
        if source.count(placeholder) < 1:
            continue
        source = source.replace(placeholder, value)
    missing = [
        placeholder
        for placeholder in (
            "__MUX_JSX__",
            "__MUX_REACT__",
            "__MUX_MENU_ITEM__",
            "__MUX_SEPARATOR__",
            "__MUX_OPEN_MODAL__",
            "__MUX_USAGE_MODAL__",
            "__MUX_MODAL_SCOPE__",
        )
        if placeholder in source
    ]
    if missing:
        raise RuntimeError(
            "the account menu still names a host binding: " + ", ".join(missing)
        )
    return source


def patch_dot_menu_bar(extracted: Path) -> None:
    """Add a menu bar icon that opens Your dot in a popover."""
    main_path, main = require_text(
        extracted,
        "setMacMenuBarEnabled:async ",
        "desktop main bundle",
    )
    hook_at = main.find("setMacMenuBarEnabled:async ")
    window_manager = None
    for match in re.finditer(
        r"([A-Za-z_$][\w$]*)\.windowManager\.getOrCreateNavigationWindow",
        main[:hook_at],
    ):
        window_manager = match
    if window_manager is None:
        raise RuntimeError("could not find the desktop window manager")
    manager = window_manager.group(1)
    menu_hook = re.compile(
        r"navigateToRoute:(?P<fn>[A-Za-z_$][\w$]*\.navigateToRoute),"
        r"setRemoteHostedPIPActiveThreadID:"
    )
    if len(menu_hook.findall(main)) != 1:
        raise RuntimeError("could not find the menu bar startup hook")
    main = menu_hook.sub(
        lambda match: (
            "navigateToRoute:(global.codexMuxWindowManager="
            f"{manager}.windowManager,{match.group('fn')}),"
            "setRemoteHostedPIPActiveThreadID:"
        ),
        main,
        count=1,
    )
    startup = (
        "isRendererAvailable(){return!this.isDisposed&&!this.origin.isDestroyed()"
        "&&this.windowManager.hasPrimaryWebContents(this.origin)}"
    )
    if main.count(startup) != 1:
        raise RuntimeError("could not find the startup renderer check")
    main = main.replace(
        startup,
        "isRendererAvailable(){return!this.isDisposed&&!this.origin.isDestroyed()"
        "&&(this.windowManager.hasPrimaryWebContents(this.origin)"
        "||global.codexMuxDotWebContentsId===this.origin.id)}",
        1,
    )
    script = (PROJECT_ROOT / "ui" / "dot-menu-bar.js").read_text(encoding="utf-8")
    marker = "//# sourceMappingURL="
    if main.count(marker) != 1:
        raise RuntimeError("desktop main bundle is missing its source map line")
    main = main.replace(marker, "\n" + script + marker, 1)
    write_javascript(extracted, main_path, main)
    patch_dot_window_layout(extracted)
    align_dot_call_button(extracted)


def patch_dot_window_layout(extracted: Path) -> None:
    """Drop the app chrome when the window route asks for `window=dot`.

    A space page already renders without the navigation rail. The same flag
    covers the dot popover.
    """
    anchor = (
        'let i=r.U?.startsWith("/space/")?new URL(r.U,"app://-"):null,'
        'a=null!=i&&/^\\/space\\/[^/]+\\/?$/.test(i.pathname)'
        '&&"page"===i.searchParams.get("window")'
    )
    path, bundle = require_text(extracted, anchor, "page-window layout check")
    if bundle.count(anchor) != 1:
        raise RuntimeError("could not find the page window layout check")
    bundle = bundle.replace(
        anchor,
        'let i=null!=r.U?new URL(r.U,"app://-"):null,'
        'a=null!=i&&(/^\\/space\\/[^/]+\\/?$/.test(i.pathname)'
        '&&"page"===i.searchParams.get("window")'
        '||"dot"===i.searchParams.get("window"))',
        1,
    )
    write_javascript(extracted, path, bundle)


def align_dot_call_button(extracted: Path) -> None:
    """Center the dot's call button on its avatar in windows without a toolbar.

    The avatar moves to the top of a window with a custom title bar, but the
    call button stays below the space the toolbar would take.
    """
    call_box = (
        "pointer-events-none absolute top-[anchor(bottom)] left-[anchor(left)] z-30 "
        "flex w-[anchor-size(width)] justify-end p-2"
    )
    header_path, header = require_text(extracted, call_box, "dot header bundle")
    if "codex-mux-dot-call" in header:
        raise RuntimeError("source app already aligns the dot call button")
    if header.count(call_box) != 1:
        raise RuntimeError("could not find the dot call button container")
    write_javascript(
        extracted,
        header_path,
        header.replace(call_box, call_box + " codex-mux-dot-call", 1),
    )
    index_path = extracted / "webview" / "index.html"
    index = index_path.read_text(encoding="utf-8")
    if "codex-mux-dot-call" in index or "</head>" not in index:
        raise RuntimeError("could not add the dot call-button style")
    # The avatar starts 2px below the header and is 56px tall; the call button
    # is 36px tall inside 8px of padding, so 2 + 28 - 8 - 18 = 4px.
    index_path.write_text(
        index.replace(
            "</head>",
            "<style>[data-app-shell-custom-titlebar=true] .codex-mux-dot-call"
            "{top:calc(var(--app-shell-application-menu-height,0px) + 4px)}"
            "</style></head>",
            1,
        ),
        encoding="utf-8",
    )


def load_account_menu(token: str) -> str:
    source = (PROJECT_ROOT / "ui" / "account-menu.js").read_text(encoding="utf-8")
    source = source.replace("__CODEX_MUX_CONTROL_PORT__", str(CONTROL_PORT))
    return source.replace("__CODEX_MUX_CONTROL_TOKEN__", token)


def patch_renderer(extracted: Path, token: str) -> None:
    account_menu = load_account_menu(token)
    markers = {
        "usage": "function CodexMuxUsageModal(",
        "reset": "function CodexMuxUseResetAccountState(",
        "menu": "function CodexMuxAccountMenu(",
        "avatar": "function CodexMuxAccountAvatar(",
    }
    positions = {}
    for name, marker in markers.items():
        if account_menu.count(marker) != 1:
            raise RuntimeError(f"could not split the Codex multiplexer UI at {marker}")
        positions[name] = account_menu.find(marker)
    runtime = account_menu[: positions["usage"]]
    modal_source = account_menu[positions["reset"] : positions["menu"]]
    menu_source = (
        account_menu[positions["usage"] : positions["reset"]]
        + account_menu[positions["menu"] : positions["avatar"]]
    )
    avatar_source = account_menu[positions["avatar"] :]

    patch_renderer_csp(extracted)
    patch_account_routing(extracted, runtime)
    patch_depletion_alerts(extracted)
    patch_account_menu(extracted, menu_source, avatar_source)
    patch_usage_modal(extracted, modal_source)
    patch_profile_menu_guard(extracted)
    patch_profile_avatar(extracted)


def patch_renderer_csp(extracted: Path) -> None:
    for name in ("index.html", "detached-window.html"):
        path = extracted / "webview" / name
        if not path.is_file():
            continue
        html = path.read_text(encoding="utf-8")
        anchor = "connect-src 'self'"
        if html.count(anchor) != 1:
            raise RuntimeError(f"could not find the CSP connect-src in {name}")
        path.write_text(
            html.replace(
                anchor,
                f"{anchor} http://127.0.0.1:{CONTROL_PORT}",
                1,
            ),
            encoding="utf-8",
        )


def patch_account_routing(extracted: Path, runtime: str) -> None:
    profile_pattern = re.compile(
        r"let [A-Za-z_$][\w$]*=await [A-Za-z_$][\w$]*\.CodexRequest"
        r"\.safeGet\(\"/wham/profiles/me\"\)"
    )
    path, bundle = require_text(
        extracted,
        'CodexRequest.safeGet("/wham/profiles/me"',
        "profile stats bundle",
    )
    if "function codexMuxRequest(" in bundle:
        raise RuntimeError("source app already contains the Codex multiplexer helpers")
    bundle = runtime + bundle
    bundle, profile_replacements = profile_pattern.subn(
        "let e=await globalThis.codexMuxProfileData("
        "globalThis.__codexMuxSelectedProfileAccountId??null)",
        bundle,
        count=1,
    )
    if profile_replacements != 1:
        raise RuntimeError("could not find the native profile stats request")

    reset_query = re.compile(
        r"function (?P<name>[A-Za-z_$][\w$]*)\(\)\{let e,t=\(0,"
        r"(?P<cache>[A-Za-z_$][\w$]*)\.c\)\(1\);return\(0,"
        r"(?P<mark>[A-Za-z_$][\w$]*)\.As\)\(\),\(0,"
        r"(?P<clear>[A-Za-z_$][\w$]*)\.Ul\)\(null\),"
        r"t\[0\]===Symbol\.for\(\"react\.memo_cache_sentinel\"\)\?\(e=\{"
        r"queryKey:\[\"rate-limit-reset-credits\"\],queryFn:"
        r"(?P<fetch>[A-Za-z_$][\w$]*),select:(?P<select>[A-Za-z_$][\w$]*),"
        r"refetchInterval:(?P<time>[A-Za-z_$][\w$]*)\.D\.ONE_MINUTE,"
        r"staleTime:(?P=time)\.D\.FIVE_SECONDS\},t\[0\]=e\):e=t\[0\],"
        r"\(0,(?P<use>[A-Za-z_$][\w$]*)\.I\)\(e\)\}"
    )
    if len(reset_query.findall(bundle)) != 1:
        raise RuntimeError("could not find the native reset-credit query")

    def reset_query_replacement(match: re.Match[str]) -> str:
        return (
            f"function {match.group('name')}(){{"
            "let e=window.__codexMuxResetAccountId;"
            f"(0,{match.group('mark')}.As)();"
            f"(0,{match.group('clear')}.Ul)(null);"
            f"return (0,{match.group('use')}.I)({{"
            'queryKey:["rate-limit-reset-credits",e??"primary"],'
            f"queryFn:e?()=>globalThis.codexMuxRateLimitResets(e):{match.group('fetch')},"
            f"select:{match.group('select')},"
            f"refetchInterval:{match.group('time')}.D.ONE_MINUTE,"
            f"staleTime:{match.group('time')}.D.FIVE_SECONDS}})}}"
        )

    bundle = reset_query.sub(reset_query_replacement, bundle, count=1)
    bundle = retarget_reset_mutation(bundle)
    request_anchor = (
        "async sendRequest(e,t,n){this.assertActive();"
        "let r=await this.requestClient.sendRequest(e,t,n)"
    )
    if bundle.count(request_anchor) != 1:
        raise RuntimeError("could not find the native app-server request bridge")
    bundle = bundle.replace(
        request_anchor,
        "async sendRequest(e,t,n){this.assertActive();"
        "let codexMuxParams=globalThis.codexMuxScopePluginRequest?"
        "globalThis.codexMuxScopePluginRequest(e,t):t;"
        "let r=await this.requestClient.sendRequest(e,codexMuxParams,n)",
        1,
    )
    write_javascript(extracted, path, bundle)


def retarget_reset_mutation(bundle: str) -> str:
    marker = 'setQueryData(["rate-limit-reset-credits"]'
    if bundle.count(marker) != 1:
        raise RuntimeError("could not find the native reset-credit mutation")
    start = bundle.rfind("function ", 0, bundle.find(marker))
    end = bundle.find("}function ", start)
    if start < 0 or end < 0:
        raise RuntimeError("could not find the native reset-credit mutation")
    function = bundle[start : end + 1]
    header = re.match(
        r"function [A-Za-z_$][\w$]*\(\)\{let e,t=\(0,[A-Za-z_$][\w$]*\.c\)\(3\),",
        function,
    )
    mutate = re.search(r"mutationFn:([A-Za-z_$][\w$]*)", function)
    if header is None or mutate is None or function.count(marker) != 1:
        raise RuntimeError("could not read the native reset-credit mutation")
    updated = function.replace(
        f"mutationFn:{mutate.group(1)}",
        "mutationFn:window.__codexMuxResetAccountId?"
        "codexMuxCredit=>globalThis.codexMuxConsumeRateLimitReset("
        "window.__codexMuxResetAccountId,codexMuxCredit):"
        f"{mutate.group(1)}",
        1,
    )
    key = '["rate-limit-reset-credits",window.__codexMuxResetAccountId??"primary"]'
    updated = updated.replace('["rate-limit-reset-credits"]', key)
    return bundle[:start] + updated + bundle[end + 1 :]


def patch_depletion_alerts(extracted: Path) -> None:
    alerts = (
        'defaultMessage:"You\'ve hit your usage limit. Add credits to continue, or try again at {resetDate}."',
        'defaultMessage:"You\'ve hit your usage limit. Add credits to continue, or try again later."',
        'defaultMessage:"You\'ve hit your usage limit. Contact your workspace owner for more access."',
        'defaultMessage:"You\'ve hit your usage limit. Review your workspace\'s usage settings to continue."',
        'defaultMessage:"You\'ve hit your usage limit. Try again at {resetDate}."',
        'defaultMessage:"You\'ve hit your usage limit. Try again later."',
        'defaultMessage:"You\'ve hit your usage limit. Upgrade your plan or add credits to continue, or try again at {resetDate}."',
        'defaultMessage:"You\'ve hit your usage limit. Upgrade your plan or add credits to continue, or try again later."',
        'defaultMessage:"You\'ve hit your usage limit. Upgrade your plan to continue, or try again at {resetDate}."',
        'defaultMessage:"You\'ve hit your usage limit. Upgrade your plan to continue, or try again later."',
    )
    replacement = 'defaultMessage:"All connected subscriptions are depleted"'
    patched = 0
    for path, text in list(javascript_texts(extracted).items()):
        if "You've hit your usage limit" not in text:
            continue
        for alert in alerts:
            if text.count(alert) != 1:
                raise RuntimeError("could not find a native subscription depletion alert")
            text = text.replace(alert, replacement, 1)
        write_javascript(extracted, path, text)
        patched += 1
    if patched < 1:
        raise RuntimeError("could not find a native subscription depletion alert")


def patch_account_menu(extracted: Path, menu_source: str, avatar_source: str) -> None:
    path, bundle = require_text(
        extracted,
        "ProfileDropdownItems:",
        "profile menu bundle",
    )
    module = module_containing(bundle, "ProfileDropdownItems:")
    export = re.search(
        r"ProfileDropdownItems:\(\)=>([A-Za-z_$][\w$]*)",
        module,
    )
    if export is None or module.count(f"function {export.group(1)}(") != 1:
        raise RuntimeError("could not find the native profile menu component")
    jsx = imported_binding(module, "ABep")
    react = imported_binding(module, "zd8w")
    menu_item = imported_binding(module, "bqtn")
    opener = re.findall(r"\(0,([A-Za-z_$][\w$]*)\.qf\)\(", module)
    usage_modal = re.findall(
        rf"{re.escape(imported_binding(module, 'jn9r'))}\.w\b",
        module,
    )
    scopes = re.findall(
        r"\(0,[A-Za-z_$][\w$]*\.gh\)\([A-Za-z_$][\w$]*\.u\)",
        module,
    )
    if len(set(opener)) != 1 or len(usage_modal) != 1 or not scopes:
        raise RuntimeError("could not find the profile menu host components")
    scope = max(set(scopes), key=scopes.count)
    bound = bind_mux_ui(
        menu_source + avatar_source,
        {
            "__MUX_JSX__": jsx,
            "__MUX_REACT__": react,
            "__MUX_MENU_ITEM__": f"{menu_item}.tJ",
            "__MUX_SEPARATOR__": f"{menu_item}.ms.Separator",
            "__MUX_OPEN_MODAL__": f"{opener[0]}.qf",
            "__MUX_USAGE_MODAL__": usage_modal[0],
            "__MUX_MODAL_SCOPE__": scope,
        },
    )
    usage_slot = re.search(
        r"let (?P<items>[A-Za-z_$][\w$]*)=(?P<hide>[A-Za-z_$][\w$]*)\?null:(?P<native>[A-Za-z_$][\w$]*);return",
        bundle,
    )
    if usage_slot is None:
        raise RuntimeError("could not find the native usage menu slot")
    bundle = bundle.replace(
        usage_slot.group(0),
        f"let {usage_slot.group('items')}={usage_slot.group('hide')}?null:"
        f"(0,{jsx}.jsx)(CodexMuxAccountMenu,{{}});return",
        1,
    )
    function_anchor = f"function {export.group(1)}("
    bundle = bundle.replace(function_anchor, bound + "\n" + function_anchor, 1)
    write_javascript(extracted, path, bundle)


def patch_usage_modal(extracted: Path, modal_source: str) -> None:
    path, bundle = require_text(
        extracted,
        "RateLimitResetModal:",
        "usage modal bundle",
    )
    module = module_containing(bundle, "RateLimitResetModal:")
    export = re.search(r"RateLimitResetModal:\(\)=>([A-Za-z_$][\w$]*)", module)
    if export is None:
        raise RuntimeError("could not find the native Usage modal component")
    function_name = export.group(1)
    function_anchor = f"function {function_name}("
    if bundle.count(function_anchor) != 1:
        raise RuntimeError("could not find the native Usage modal component")
    windows = re.search(
        r"\(0,(?P<format>[A-Za-z_$][\w$]*)\.Ss\)\((?P<source>[A-Za-z_$][\w$]*)\),"
        r"(?P<cache>[A-Za-z_$][\w$]*)\[5\]=(?P=source),(?P=cache)\[6\]=(?P<windows>[A-Za-z_$][\w$]*)\):"
        r"(?P=windows)=(?P=cache)\[6\];let (?P<selected>[A-Za-z_$][\w$]*)=(?P=windows);",
        bundle,
    )
    if windows is None:
        raise RuntimeError("could not find the native usage-window selection")
    bundle = bundle.replace(
        windows.group(0),
        windows.group(0)[: -len(f"let {windows.group('selected')}={windows.group('windows')};")]
        + f"let {windows.group('selected')}=window.__codexMuxSelectedUsageWindows??"
        + f"{windows.group('windows')};",
        1,
    )
    header = (
        'children:[b,j,R,B]}),S[77]=C,S[78]=j,S[79]=R,S[80]=B,S[81]=U):U=S[81]'
    )
    if bundle.count(header) != 1:
        raise RuntimeError("could not find the native Usage sheet header")
    bundle = bundle.replace(
        "S[77]!==C||S[78]!==j||S[79]!==R||S[80]!==B?(U=(0,i.jsxs)(O.R4,"
        '{className:"overflow-y-auto text-default",style:C,children:[b,j,R,B]}),'
        "S[77]=C,S[78]=j,S[79]=R,S[80]=B,S[81]=U):U=S[81]",
        "S[77]!==C||S[78]!==j||S[79]!==R||S[80]!==B||!0?(U=(0,i.jsxs)(O.R4,"
        '{className:"overflow-y-auto text-default",style:C,children:[b,'
        "window.__codexMuxResetAccountSelector??null,j,R,B]}),"
        "S[77]=C,S[78]=j,S[79]=R,S[80]=B,S[81]=U):U=S[81]",
        1,
    )
    bound = bind_mux_ui(
        modal_source,
        {
            "__MUX_JSX__": imported_binding(module, "ABep"),
            "__MUX_REACT__": imported_binding(module, "zd8w"),
        },
    )
    call = f"function {function_name}(e){{"
    if bundle.count(call) != 1:
        raise RuntimeError("could not find the native Usage modal component")
    bundle = bundle.replace(
        call,
        bound + "\n" + call + "CodexMuxUseResetAccountState();",
        1,
    )
    write_javascript(extracted, path, bundle)


def patch_profile_menu_guard(extracted: Path) -> None:
    found = [
        candidate
        for candidate in files_containing(extracted, "CodexProfileMenuOpened")
        if javascript_texts(extracted)[candidate].count("CodexProfileMenuOpened") == 1
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one profile menu open handler, found {len(found)}"
        )
    path = found[0]
    bundle = javascript_texts(extracted)[path]
    start = bundle.rfind("function ", 0, bundle.find("CodexProfileMenuOpened"))
    end = bundle.find("\nfunction ", start + 1)
    if end < 0:
        end = bundle.find("function ", start + 10)
    function = bundle[start:end]
    close_match = re.search(
        r"onClose:([A-Za-z_$][\w$]*)\}\)",
        function,
    )
    open_names = set(re.findall(r"onOpenChange:([A-Za-z_$][\w$]*)", function))
    if close_match is None or len(open_names) != 1 or function.count("onOpenChange:") != 2:
        raise RuntimeError("could not find a native profile menu open-state hook")
    close_name = close_match.group(1)
    open_name = next(iter(open_names))
    function = function.replace(
        f"onClose:{close_name}",
        f"onClose:globalThis.CodexMuxProfileMenuOpenChange({close_name})",
        1,
    )
    function = function.replace(
        f"onOpenChange:{open_name}",
        f"onOpenChange:globalThis.CodexMuxProfileMenuOpenChange({open_name})",
    )
    write_javascript(extracted, path, bundle[:start] + function + bundle[end:])


def patch_profile_avatar(extracted: Path) -> None:
    path, bundle = require_text(
        extracted,
        "data-profile-sticker-photo",
        "Profile settings bundle",
    )
    avatar = re.search(
        r"children:\[\(0,(?P<jsx>[A-Za-z_$][\w$]*)\.jsxs\)\(\"div\",\{"
        r"\"aria-disabled\":[A-Za-z_$][\w$]*,\"data-profile-sticker-photo\":!0",
        bundle,
    )
    native_class = '"group relative flex rounded-full outline-none"'
    if avatar is None or bundle.count(native_class) != 1:
        raise RuntimeError("could not find the native Profile avatar")
    bundle = bundle.replace(
        avatar.group(0),
        "children:[globalThis.CodexMuxProfileAvatarStack?.({onSelect:()=>{}})??null,"
        + avatar.group(0)[len("children:[") :],
        1,
    )
    bundle = bundle.replace(
        native_class,
        '(globalThis.CodexMuxProfileAvatarStack?"hidden":'
        '"group relative flex rounded-full outline-none")',
        1,
    )
    write_javascript(extracted, path, bundle)


def patch_desktop_profile(
    extracted: Path, installed_computer_use_app: Path
) -> None:
    """Give the copied Electron app its own user-data and single-instance scope."""
    profile_pattern = re.compile(
        r"(?P<electron>[A-Za-z_$][\w$]*)\.app\.setPath\(\"userData\",function\(\{"
        r"appDataPath:[A-Za-z_$][\w$]*,buildFlavor:[A-Za-z_$][\w$]*,"
        r"env:[A-Za-z_$][\w$]*\}\)\{.*?\}\(\{appDataPath:(?P=electron)\.app\.getPath\("
        r"\"appData\"\),buildFlavor:[A-Za-z_$][\w$]*,env:process\.env\}\)\)",
        re.DOTALL,
    )

    def profile_replacement(match: re.Match[str]) -> str:
        electron = match.group("electron")
        computer_use_pipe = json.dumps(str(DEFAULT_STATE_ROOT / "computer-use.sock"))
        computer_use_app = json.dumps(str(installed_computer_use_app))
        return (
            f"process.env.SKY_CUA_SERVICE_NATIVE_PIPE_PATH={computer_use_pipe};"
            f"process.env.SKY_CUA_SERVICE_PATH={computer_use_app};"
            f"process.env.CODEX_ELECTRON_COMPUTER_USE_APP_PATH={computer_use_app};"
            'process.env.CODEX_ELECTRON_SKIP_COMPUTER_USE_CANONICAL_REFRESH="1";'
            f'{electron}.app.setPath("userData",'
            f'{electron}.app.getPath("appData")+"/{DESKTOP_PROFILE_NAME}")'
        )

    updater_pattern = re.compile(
        r"(?P<sparkle>[A-Za-z_$][\w$]*)=(?P<flags>[A-Za-z_$][\w$]*)\.x"
        r"\.shouldIncludeSparkle\((?P<flavor>[A-Za-z_$][\w$]*),process\.platform,process\.env\),"
        r"(?P<updater>[A-Za-z_$][\w$]*)=(?P=flags)\.x\.shouldIncludeUpdater\("
        r"(?P=flavor),process\.platform,process\.env\)"
    )
    service_pattern = re.compile(
        r"(?P<prefix>[A-Za-z_$][\w$]*=new [A-Za-z_$][\w$]*\()"
        r"[A-Za-z_$][\w$]*\([A-Za-z_$][\w$]*\.codexHome\)"
        r"(?P<suffix>,\{onServiceAvailable:)"
    )

    def service_replacement(match: re.Match[str]) -> str:
        return (
            match.group("prefix")
            + json.dumps(str(installed_computer_use_app))
            + match.group("suffix")
        )

    instruction = "Control desktop apps on macOS through Computer Use."
    strict_instruction = (
        "Control desktop apps on macOS through Computer Use via node_repl and "
        "@oai/sky only. Never use shell commands, open, AppleScript, osascript, "
        "JXA, System Events, or CGEvent synthesis for computer interactions or "
        "as a fallback. If Computer Use is unavailable, report the failure "
        "instead of using another automation method."
    )
    counts = {"profile": 0, "updater": 0, "service": 0, "instruction": 0}
    instruction_path: Path | None = None
    for path in (extracted / ".vite" / "build").glob("*.js"):
        text = path.read_text(encoding="utf-8")
        updated = text
        updated, count = profile_pattern.subn(profile_replacement, updated, count=1)
        counts["profile"] += count
        updated, count = updater_pattern.subn(
            r"\g<sparkle>=!1,\g<updater>=!1",
            updated,
            count=1,
        )
        counts["updater"] += count
        updated, count = service_pattern.subn(service_replacement, updated, count=1)
        counts["service"] += count
        if instruction in updated:
            if updated.count(instruction) != 1:
                raise RuntimeError("could not find the Computer Use tool instruction")
            updated = updated.replace(instruction, strict_instruction, 1)
            counts["instruction"] += 1
            instruction_path = path
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    for name, count in counts.items():
        if count != 1:
            raise RuntimeError(f"could not patch the desktop {name} hook ({count})")
    if instruction_path is None:
        raise RuntimeError("could not find the Computer Use tool instruction")
    ui_test_bridge = extracted / ".vite" / "build" / "ui-test-bridge.cjs"
    shutil.copy2(PROJECT_ROOT / "ui" / "ui-test-bridge.cjs", ui_test_bridge)
    main = instruction_path.read_text(encoding="utf-8")
    instruction_path.write_text(
        main
        + "\n;if(process.env.CODEX_MUX_UI_TESTS===`1`)"
        "require(require(`node:path`).join(__dirname,`ui-test-bridge.cjs`)).start();",
        encoding="utf-8",
    )


def patch_info_plist(
    app: Path,
    asar_path: Path,
    team_identifier: str | None,
) -> None:
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    info["CFBundleDisplayName"] = DESKTOP_DISPLAY_NAME
    info["CFBundleName"] = DESKTOP_DISPLAY_NAME
    # A distinct identifier keeps Launch Services and external Computer Use from
    # confusing this independently signed copy with the official ChatGPT app.
    info["CFBundleIdentifier"] = DESKTOP_BUNDLE_IDENTIFIER
    info["BundleSigningBaseName"] = "CodexSubscriptionRouter"
    info["CodexMuxSigningTeamIdentifier"] = team_identifier or "adhoc"
    info["CrProductDirName"] = DESKTOP_PROFILE_NAME
    for key in list(info):
        if key.startswith("SU"):
            del info[key]
    info["SUEnableAutomaticChecks"] = False
    info["SUAllowsAutomaticUpdates"] = False
    for url_type in info.get("CFBundleURLTypes", []):
        schemes = url_type.get("CFBundleURLSchemes", [])
        url_type["CFBundleURLSchemes"] = [
            "codex-subscription-router" if value == "codex" else value for value in schemes
        ]
    digest = asar_header_sha256(asar_path)
    info["ElectronAsarIntegrity"] = {
        "Resources/app.asar": {"algorithm": "SHA256", "hash": digest}
    }
    with plist_path.open("wb") as handle:
        plistlib.dump(info, handle, fmt=plistlib.FMT_BINARY, sort_keys=False)


def patch_app(
    source: Path,
    destination: Path,
    force: bool,
    allow_adhoc_signing: bool,
    allow_untested_source: bool,
    allow_signing_team_change: bool,
) -> None:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_dir() or not (source / "Contents" / "Resources" / "app.asar").is_file():
        raise RuntimeError(f"not a ChatGPT app bundle: {source}")
    if source == destination:
        raise RuntimeError(
            "source and destination must be different; "
            "the original app is never patched in place"
        )
    if destination.exists() and not force:
        raise RuntimeError(
            f"destination exists: {destination} "
            "(pass --force to create a recoverable backup)"
        )

    source_plist = source / "Contents" / "Info.plist"
    with source_plist.open("rb") as handle:
        source_info = plistlib.load(handle)
    source_version = str(source_info.get("CFBundleShortVersionString", "unknown"))
    source_build = str(source_info.get("CFBundleVersion", "unknown"))
    source_asar = source / "Contents" / "Resources" / "app.asar"
    source_asar_hash = hashlib.sha256(source_asar.read_bytes()).hexdigest()
    expected_asar_hash = TESTED_SOURCE_BUILDS.get((source_version, source_build))
    print(
        f"Source ChatGPT version: {source_version} ({source_build}), "
        f"app.asar {source_asar_hash}"
    )
    if expected_asar_hash != source_asar_hash and not allow_untested_source:
        raise RuntimeError(
            "the source version, build, or app.asar hash is not approved; "
            "review the upstream change or pass --allow-untested-source"
        )
    if expected_asar_hash != source_asar_hash:
        print(
            "Warning: continuing with an untested official ChatGPT build; "
            "the patch will continue only while every expected anchor matches.",
            file=sys.stderr,
        )

    for tool in ("codesign", "ditto", "go", "npm", "security", "xcrun"):
        require_tool(tool)
    asar = ensure_asar_tool()
    token = load_or_create_token()
    signing_identity = resolve_signing_identity(allow_adhoc_signing)
    team_identifier = signing_team_identifier(signing_identity)
    if destination.exists():
        installed_team = existing_signing_team(destination)
        if installed_team != team_identifier and not allow_signing_team_change:
            raise RuntimeError(
                "the selected signing team differs from the installed build; "
                "reuse the prior identity or pass --allow-signing-team-change"
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    installed_computer_use_app = destination.parent / COMPUTER_USE_APP_NAME
    legacy_app = destination.parent / LEGACY_DESKTOP_APP_NAME
    legacy_computer_use_app = destination.parent / LEGACY_COMPUTER_USE_APP_NAME
    ensure_components_are_stopped(
        (destination, legacy_app, installed_computer_use_app, legacy_computer_use_app)
    )

    with tempfile.TemporaryDirectory(prefix=".codex-subscription-router-", dir=destination.parent) as temporary:
        temporary_path = Path(temporary)
        staged_app = temporary_path / destination.name
        staged_computer_use_app = temporary_path / COMPUTER_USE_APP_NAME
        extracted = temporary_path / "asar"
        proxy = temporary_path / "codex-mux"

        print("Building multiplexer…")
        build_proxy(proxy)
        print("Copying ChatGPT.app…")
        run(["ditto", str(source), str(staged_app)])
        install_main_stub(staged_app)

        resources = staged_app / "Contents" / "Resources"
        original_asar = resources / "app.asar"
        print("Patching desktop profile and renderer…")
        run([str(asar), "extract", str(original_asar), str(extracted)])
        patch_asar_computer_use_identity(extracted, team_identifier)
        patch_desktop_profile(extracted, installed_computer_use_app)
        patch_renderer(extracted, token)
        patch_dot_menu_bar(extracted)
        sign_native_code_tree(extracted, signing_identity)
        repacked_asar = temporary_path / "app.asar"
        run(
            [
                str(asar),
                "pack",
                "--unpack-dir",
                ASAR_UNPACK_DIRECTORIES,
                str(extracted),
                str(repacked_asar),
            ]
        )
        asar_listing = output([str(asar), "list", "--is-pack", str(repacked_asar)])
        required_unpacked_module = (
            "unpack : /node_modules/better-sqlite3/build/Release/"
            "better_sqlite3.node"
        )
        if required_unpacked_module not in asar_listing:
            raise RuntimeError("native ASAR modules were not kept unpacked")
        shutil.copy2(repacked_asar, original_asar)
        repacked_unpacked = temporary_path / "app.asar.unpacked"
        if not repacked_unpacked.is_dir():
            raise RuntimeError("ASAR pack did not produce its unpacked native tree")
        shutil.copytree(
            repacked_unpacked,
            resources / "app.asar.unpacked",
            dirs_exist_ok=True,
        )

        bundled_codex = bundled_codex_executable(staged_app)
        real_codex = bundled_codex.with_name("codex.real")
        if not bundled_codex.is_file():
            raise RuntimeError("bundled Codex CLI executable was not found")
        if real_codex.exists():
            raise RuntimeError("source app already contains codex.real")
        nested_profile = (
            bundled_codex_app(staged_app) / "Contents" / "embedded.provisionprofile"
        )
        if nested_profile.is_file():
            nested_profile.unlink()
        bundled_codex.rename(real_codex)
        shutil.copy2(proxy, bundled_codex)
        bundled_codex.chmod(0o755)

        patch_info_plist(staged_app, original_asar, team_identifier)
        patch_embedded_asar_integrity(staged_app, original_asar)
        print(f"Signing independent app copy with {signing_identity}…")
        sign_independent_app(staged_app, signing_identity, team_identifier)
        verify_signed_code(
            staged_app,
            OPENAI_DESKTOP_CODE_IDENTIFIER,
            team_identifier,
        )
        verify_signed_code(
            staged_app / "Contents" / "MacOS" / "ChatGPT",
            OPENAI_DESKTOP_CODE_IDENTIFIER,
            team_identifier,
        )
        bundled_computer_use_app = (
            computer_use_package(staged_app) / "Codex Computer Use.app"
        )
        run(
            [
                "ditto",
                str(bundled_computer_use_app),
                str(staged_computer_use_app),
            ]
        )
        verify_signed_code(
            staged_computer_use_app,
            COMPUTER_USE_BUNDLE_IDENTIFIER,
            team_identifier,
        )

        backup_suffix = time.strftime("%Y%m%d-%H%M%S")
        backup_directory = DEFAULT_STATE_ROOT / "backups" / backup_suffix
        app_backup = backup_directory / destination.name
        helper_backup = backup_directory / installed_computer_use_app.name
        legacy_backup = backup_directory / legacy_app.name
        legacy_helper_backup = backup_directory / legacy_computer_use_app.name
        had_app = destination.exists()
        had_helper = installed_computer_use_app.exists()
        had_legacy_app = legacy_app != destination and legacy_app.exists()
        had_legacy_helper = (
            legacy_computer_use_app != installed_computer_use_app
            and legacy_computer_use_app.exists()
        )
        if LAUNCH_SERVICES_REGISTER.is_file():
            for legacy, present in (
                (legacy_app, had_legacy_app),
                (legacy_computer_use_app, had_legacy_helper),
            ):
                if present:
                    run([str(LAUNCH_SERVICES_REGISTER), "-u", str(legacy)])
        if had_app or had_helper or had_legacy_app or had_legacy_helper:
            backup_directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            backup_directory.parent.chmod(0o700)
            backup_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        try:
            if had_app:
                destination.rename(app_backup)
                print(f"Existing copy moved to {app_backup}")
            if had_legacy_app:
                legacy_app.rename(legacy_backup)
                print(f"Previously named copy moved to {legacy_backup}")
            if had_helper:
                installed_computer_use_app.rename(helper_backup)
                print(f"Existing Computer Use helper moved to {helper_backup}")
            if had_legacy_helper:
                legacy_computer_use_app.rename(legacy_helper_backup)
                print(
                    "Previously named Computer Use helper moved to "
                    f"{legacy_helper_backup}"
                )
            staged_app.rename(destination)
            staged_computer_use_app.rename(installed_computer_use_app)
            run(["xattr", "-cr", str(destination), str(installed_computer_use_app)])
        except OSError:
            failed_directory = backup_directory / "failed-install"
            failed_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if destination.exists():
                destination.rename(failed_directory / destination.name)
            if installed_computer_use_app.exists():
                installed_computer_use_app.rename(
                    failed_directory / installed_computer_use_app.name
                )
            if app_backup.exists():
                app_backup.rename(destination)
            if legacy_backup.exists():
                legacy_backup.rename(legacy_app)
            if helper_backup.exists():
                helper_backup.rename(installed_computer_use_app)
            if legacy_helper_backup.exists():
                legacy_helper_backup.rename(legacy_computer_use_app)
            raise

    migrate_legacy_profile()
    if LAUNCH_SERVICES_REGISTER.is_file():
        run(
            [
                str(LAUNCH_SERVICES_REGISTER),
                "-f",
                str(destination),
                str(installed_computer_use_app),
            ]
        )
    retire_stale_cached_computer_use_app()

    print(destination)
    print(installed_computer_use_app)


def main() -> int:
    args = parse_args()
    try:
        patch_app(
            args.source,
            args.destination,
            args.force,
            args.allow_adhoc_signing,
            args.allow_untested_source,
            args.allow_signing_team_change,
        )
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"patch failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
