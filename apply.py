#!/usr/bin/env python3
"""Brand an untouched RustDesk source checkout as CHANTCH Remote (plan: docs/rustdesk-plan.md, Phase 4).

    python3 apply.py --src <rustdesk checkout at a release tag, hbb_common submodule checked out>
                     [--brand brand.env] [--logo assets/logo.png] [--tray-mac assets/tray-mac.png]

Every source edit is anchored: the text it replaces must be found the stated number of times, or the run stops
with the file and the edit named and nothing is half-branded (all edits are checked before any file is written).
When an upstream release moves one of these lines, fix that one edit here; never edit the upstream tree by hand.
Icons are regenerated from the logo at the size each upstream file already has. Needs Pillow.
"""
import argparse
import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image


def die(msg: str) -> None:
    print(f"[apply] ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def read_brand(path: Path) -> dict:
    brand = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            die(f"{path}:{n}: expected KEY=VALUE")
        k, v = line.split("=", 1)
        brand[k.strip()] = v.strip()
    rules = {
        "APP_NAME": r"[A-Za-z][A-Za-z0-9]{2,31}",
        "DISPLAY_NAME": r"[A-Za-z0-9][A-Za-z0-9 .&()-]{1,63}",
        "COMPANY": r"[A-Za-z0-9][A-Za-z0-9 .&()-]{1,63}",
        "ORG": r"[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+",
        "BUNDLE_ID": r"[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+",
        "ID_SERVER": r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+",
        "RS_PUB_KEY": r"[A-Za-z0-9+/]{43}=",
    }
    for k, rx in rules.items():
        v = brand.get(k, "")
        if not re.fullmatch(rx, v):
            hint = " (copy /opt/chantch/rustdesk/data/id_ed25519.pub from the server)" if k == "RS_PUB_KEY" else ""
            die(f"{k} in {path} is missing or not valid: {v!r}{hint}")
    if len(base64.b64decode(brand["RS_PUB_KEY"])) != 32:
        die("RS_PUB_KEY must be 32 bytes (an Ed25519 public key)")
    if brand["APP_NAME"] == "RustDesk":
        die("APP_NAME must differ from RustDesk (a custom client is detected by that)")
    return brand


class Edit:
    """Replace `old` (literal, or a regex when regex=True) with `new` in `path`; `count` = exact expected matches,
    or None for 'at least one'."""

    def __init__(self, path, old, new, count=1, regex=False, why=""):
        self.path, self.old, self.new, self.count, self.regex, self.why = path, old, new, count, regex, why

    def apply_to(self, text: str) -> str:
        if self.regex:
            found = len(re.findall(self.old, text, flags=re.M))
        else:
            found = text.count(self.old)
        if (self.count is None and found == 0) or (self.count is not None and found != self.count):
            want = "at least 1" if self.count is None else str(self.count)
            die(f"{self.path}: expected {want} match(es) of {self.old!r}, found {found} "
                f"({self.why}). Upstream changed this spot: update the edit in apply.py.")
        if self.regex:
            return re.sub(self.old, lambda _m: self.new, text, flags=re.M)
        return text.replace(self.old, self.new)


def edits(b: dict) -> list:
    app, disp, comp = b["APP_NAME"], b["DISPLAY_NAME"], b["COMPANY"]
    cfg = "libs/hbb_common/src/config.rs"
    return [
        Edit(cfg, r'^(\s*pub static ref ORG: RwLock<String> = RwLock::new\(")[^"]*(".to_owned\(\)\);)$',
             f'    pub static ref ORG: RwLock<String> = RwLock::new("{b["ORG"]}".to_owned());', regex=True,
             why="launchd labels and the macOS config folder"),
        Edit(cfg, '    pub static ref APP_NAME: RwLock<String> = RwLock::new("RustDesk".to_owned());',
             f'    pub static ref APP_NAME: RwLock<String> = RwLock::new("{app}".to_owned());',
             why="app name; also makes is_custom_client() true"),
        Edit(cfg, r'^pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];$',
             f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{b["ID_SERVER"]}"];', regex=True,
             why="built-in ID server"),
        Edit(cfg, r'^pub const RS_PUB_KEY: &str = "[^"]*";$',
             f'pub const RS_PUB_KEY: &str = "{b["RS_PUB_KEY"]}";', regex=True,
             why="built-in server key"),
        Edit("src/updater.rs", "fn check_update(manually: bool) -> ResultType<()> {\n",
             "fn check_update(manually: bool) -> ResultType<()> {\n"
             "    // CHANTCH Remote: never download stock RustDesk from github.com/rustdesk over the branded client,\n"
             "    // even if someone ticks 'Auto update'. Updates come from the CHANTCH Remote releases.\n"
             "    if crate::is_custom_client() {\n"
             "        return Ok(());\n"
             "    }\n",
             why="Windows auto-update would install stock RustDesk"),
        Edit("Cargo.toml", 'ProductName = "RustDesk"\n', f'ProductName = "{disp}"\n', why="Windows file properties"),
        Edit("Cargo.toml", 'FileDescription = "RustDesk Remote Desktop"\n', f'FileDescription = "{disp}"\n',
             why="Windows file properties"),
        Edit("flutter/windows/runner/Runner.rc", r'^(\s*VALUE "CompanyName", )"[^"]*"( "\\0")$',
             f'            VALUE "CompanyName", "{comp}" "\\0"', regex=True, why="Windows file properties"),
        Edit("flutter/windows/runner/Runner.rc", 'VALUE "FileDescription", "RustDesk Remote Desktop" "\\0"',
             f'VALUE "FileDescription", "{disp}" "\\0"', why="Windows file properties"),
        Edit("flutter/windows/runner/Runner.rc", 'VALUE "ProductName", "RustDesk" "\\0"',
             f'VALUE "ProductName", "{disp}" "\\0"', why="Windows file properties"),
        Edit("flutter/macos/Runner/Configs/AppInfo.xcconfig", "PRODUCT_NAME = RustDesk\n",
             f"PRODUCT_NAME = {app}\n", why="macOS bundle /Applications/<APP_NAME>.app, which the Rust code expects"),
        Edit("flutter/macos/Runner/Configs/AppInfo.xcconfig", r"^PRODUCT_BUNDLE_IDENTIFIER = .*$",
             f"PRODUCT_BUNDLE_IDENTIFIER = {b['BUNDLE_ID']}", regex=True, why="macOS bundle id"),
        Edit("flutter/macos/Runner/Configs/AppInfo.xcconfig", r"^PRODUCT_COPYRIGHT = .*$",
             f"PRODUCT_COPYRIGHT = {comp}. Based on RustDesk, Copyright Purslane Tech Pte. Ltd., AGPL-3.0.",
             regex=True, why="macOS About box"),
        Edit("flutter/macos/Runner.xcodeproj/project.pbxproj", "RustDesk.app", f"{app}.app", count=None,
             why="product reference (cosmetic; the real name comes from PRODUCT_NAME)"),
        Edit("build.py", "RustDesk.app", f"{app}.app", count=None,
             why="macOS build copies the service binary into the bundle"),
        Edit("res/osx-dist.sh", "RustDesk.app", f"{app}.app", count=None, why="macOS packaging script"),
    ]


def solid(img: Image.Image, size) -> Image.Image:
    """The logo fitted into `size` on a transparent canvas (aspect kept, centred)."""
    w, h = size
    im = img.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
    return canvas


def silhouette(img: Image.Image, size) -> Image.Image:
    """Black shape with the logo's alpha: a macOS 'template' tray icon (macOS recolours it)."""
    im = solid(img, size)
    alpha = im.getchannel("A")
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.putalpha(alpha)
    return out


def icons(src: Path, logo: Image.Image, tray_mac: Image.Image | None) -> list:
    written = []

    def png(rel, maker=solid, base=logo):
        p = src / rel
        if not p.exists():
            die(f"{rel}: icon file missing upstream (update the icon list in apply.py)")
        size = Image.open(p).size
        maker(base, size).save(p, format="PNG")
        written.append(rel)

    def ico(rel, sizes=None):
        p = src / rel
        if not p.exists():
            die(f"{rel}: icon file missing upstream (update the icon list in apply.py)")
        sizes = sizes or sorted(Image.open(p).info.get("sizes") or {(256, 256)})
        big = max(max(s) for s in sizes)
        solid(logo, (big, big)).save(p, format="ICO", sizes=sizes)
        written.append(rel)

    for rel in ("res/icon.png", "res/mac-icon.png", "res/128x128.png", "res/128x128@2x.png", "res/32x32.png",
                "res/64x64.png"):
        png(rel)
    for rel in ("res/mac-tray-dark-x2.png", "res/mac-tray-light-x2.png"):
        png(rel, maker=(solid if tray_mac else silhouette), base=(tray_mac or logo))
    # App icons get the full Windows set (upstream's app_icon.ico holds only 48 px: blurry on a desktop);
    # the tray icon keeps upstream's sizes.
    app_sizes = [(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]
    ico("res/icon.ico", app_sizes)
    ico("flutter/windows/runner/resources/app_icon.ico", app_sizes)
    ico("res/tray-icon.ico")
    icns = src / "flutter/macos/Runner/AppIcon.icns"
    if not icns.exists():
        die("flutter/macos/Runner/AppIcon.icns missing upstream")
    solid(logo, (1024, 1024)).save(icns, format="ICNS")
    written.append("flutter/macos/Runner/AppIcon.icns")

    # In-app logo (Flutter renders assets/icon.svg): an SVG wrapping the PNG, so no vector redraw is needed.
    buf = io.BytesIO()
    solid(logo, (256, 256)).save(buf, format="PNG")
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'width="256" height="256" viewBox="0 0 256 256"><image width="256" height="256" '
           f'xlink:href="data:image/png;base64,{data}"/></svg>\n')
    for rel in ("flutter/assets/icon.svg", "res/logo.svg"):
        if not (src / rel).exists():
            die(f"{rel}: logo file missing upstream (update the icon list in apply.py)")
        (src / rel).write_text(svg, encoding="ascii")
        written.append(rel)
    return written


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--brand", type=Path, default=here / "brand.env")
    ap.add_argument("--logo", type=Path, default=here / "assets" / "logo.png")
    ap.add_argument("--tray-mac", type=Path, default=here / "assets" / "tray-mac.png")
    a = ap.parse_args()

    src = a.src.resolve()
    if not (src / "libs/hbb_common/src/config.rs").exists():
        die(f"{src} is not a RustDesk checkout with the hbb_common submodule (git submodule update --init)")
    brand = read_brand(a.brand)
    if not a.logo.exists():
        die(f"logo not found: {a.logo} (assets/README.md)")
    logo = Image.open(a.logo).convert("RGBA")
    if min(logo.size) < 512:
        die(f"logo is {logo.size[0]}x{logo.size[1]}; give at least 1024x1024 (512 is the absolute minimum)")
    tray_mac = Image.open(a.tray_mac).convert("RGBA") if a.tray_mac.exists() else None

    # 1. Check every edit against the current text first; write only if all of them match.
    staged = {}
    for e in edits(brand):
        p = src / e.path
        if not p.exists():
            die(f"{e.path}: file missing upstream ({e.why})")
        if e.path not in staged:
            with open(p, encoding="utf-8", newline="") as f:     # newline="": keep the file's line endings
                staged[e.path] = f.read()
        staged[e.path] = e.apply_to(staged[e.path])
    for rel, text in staged.items():
        with open(src / rel, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    print(f"[apply] {len(edits(brand))} source edits in {len(staged)} files")

    # 2. Icons.
    written = icons(src, logo, tray_mac)
    print(f"[apply] {len(written)} icon files from {a.logo.name}")
    print(f"[apply] branded as {brand['APP_NAME']} ({brand['DISPLAY_NAME']}), server {brand['ID_SERVER']}")


if __name__ == "__main__":
    main()
