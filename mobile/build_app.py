#!/usr/bin/env python3
"""
Gera o aplicativo mobile (Android/iOS) da Doce Cesta Brasília.

Uso:
    python mobile/build_app.py --android            # prepara o projeto Android
    python mobile/build_app.py --android --apk      # + gera APK de teste (debug)
    python mobile/build_app.py --android --release  # + gera AAB/APK assinado (usa variáveis KEYSTORE_*)
    python mobile/build_app.py --ios                # prepara o projeto iOS (requer macOS + Xcode)

Requisitos: Python 3.9+, Pillow, Node 20+, JDK 21 e Android SDK (para --apk/--release).
Variáveis de assinatura: KEYSTORE_FILE, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
LOGO = RAIZ / "assets" / "logo.png"
FUNDO = (59, 36, 23, 255)  # #3B2417
NPM = "npm.cmd" if os.name == "nt" else "npm"
NPX = "npx.cmd" if os.name == "nt" else "npx"
GRADLEW = "gradlew.bat" if os.name == "nt" else "./gradlew"


def run(cmd, cwd=AQUI, env=None):
    print("→", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def config():
    return json.loads((AQUI / "capacitor.config.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ ícones
def _logo_quadrada(tamanho, margem=0.0):
    img = Image.open(LOGO).convert("RGBA")
    lado = max(img.size)
    base = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    base.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2), img)
    alvo = int(tamanho * (1 - margem * 2))
    base = base.resize((alvo, alvo), Image.LANCZOS)
    saida = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    saida.paste(base, ((tamanho - alvo) // 2, (tamanho - alvo) // 2), base)
    return saida


def _mascara(tamanho, redondo):
    m = Image.new("L", (tamanho, tamanho), 0)
    d = ImageDraw.Draw(m)
    if redondo:
        d.ellipse((0, 0, tamanho - 1, tamanho - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, tamanho - 1, tamanho - 1), radius=int(tamanho * 0.22), fill=255)
    return m


def gerar_icones_android(res):
    densidades = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for dens, px in densidades.items():
        pasta = res / f"mipmap-{dens}"
        pasta.mkdir(parents=True, exist_ok=True)
        for nome, redondo in (("ic_launcher.png", False), ("ic_launcher_round.png", True)):
            fundo = Image.new("RGBA", (px, px), FUNDO)
            fundo.alpha_composite(_logo_quadrada(px, 0.12))
            out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            out.paste(fundo, (0, 0), _mascara(px, redondo))
            out.save(pasta / nome)
        fg = _logo_quadrada(int(px * 108 / 48), 0.22)
        fg.save(pasta / "ic_launcher_foreground.png")
    # adaptive icon
    anydpi = res / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
           '    <background android:drawable="@color/ic_launcher_background"/>\n'
           '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
           '</adaptive-icon>\n')
    (anydpi / "ic_launcher.xml").write_text(xml)
    (anydpi / "ic_launcher_round.xml").write_text(xml)
    valores = res / "values"
    valores.mkdir(parents=True, exist_ok=True)
    (valores / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="ic_launcher_background">#3B2417</color>\n</resources>\n')


def gerar_splash_android(res):
    for pasta in res.glob("drawable*"):
        if pasta.is_dir() and (pasta / "splash.png").exists():
            larg, alt = Image.open(pasta / "splash.png").size
            tela = Image.new("RGBA", (larg, alt), FUNDO)
            logo = _logo_quadrada(int(min(larg, alt) * 0.42))
            tela.alpha_composite(logo, ((larg - logo.width) // 2, (alt - logo.height) // 2))
            tela.convert("RGB").save(pasta / "splash.png")


def gerar_icones_ios(projeto):
    destino = projeto / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset"
    if not destino.exists():
        return
    icone = Image.new("RGBA", (1024, 1024), FUNDO)
    icone.alpha_composite(_logo_quadrada(1024, 0.12))
    for arq in destino.glob("*.png"):
        arq.unlink()
    icone.convert("RGB").save(destino / "AppIcon-512@2x.png")
    (destino / "Contents.json").write_text(json.dumps({
        "images": [{"filename": "AppIcon-512@2x.png", "idiom": "universal",
                    "platform": "ios", "size": "1024x1024"}],
        "info": {"author": "xcode", "version": 1}}, indent=2))


# ------------------------------------------------------------------ Android
def preparar_android():
    android = AQUI / "android"
    if not android.exists():
        run([NPX, "cap", "add", "android"])

    manifest = android / "app" / "src" / "main" / "AndroidManifest.xml"
    txt = manifest.read_text(encoding="utf-8")
    for perm in ("android.permission.INTERNET", "android.permission.USE_BIOMETRIC",
                 "android.permission.USE_FINGERPRINT", "android.permission.ACCESS_NETWORK_STATE"):
        if perm not in txt:
            txt = txt.replace("</manifest>", f'    <uses-permission android:name="{perm}" />\n</manifest>')
    if "windowSoftInputMode" not in txt:
        txt = txt.replace("<activity", '<activity\n            android:windowSoftInputMode="adjustResize"', 1)
    txt = txt.replace('android:allowBackup="true"', 'android:allowBackup="false"')
    manifest.write_text(txt, encoding="utf-8")

    res = android / "app" / "src" / "main" / "res"
    gerar_icones_android(res)
    gerar_splash_android(res)

    # nome do app
    strings = res / "values" / "strings.xml"
    if strings.exists():
        s = strings.read_text(encoding="utf-8")
        s = re.sub(r'(<string name="app_name">).*?(</string>)', r"\1Doce Cesta Brasília\2", s)
        s = re.sub(r'(<string name="title_activity_main">).*?(</string>)', r"\1Doce Cesta Brasília\2", s)
        strings.write_text(s, encoding="utf-8")

    # assinatura (opcional, via variáveis de ambiente)
    (android / "app" / "signing.gradle").write_text(
        "def ks = System.getenv('KEYSTORE_FILE')\n"
        "if (ks) {\n"
        "    android {\n"
        "        signingConfigs {\n"
        "            release {\n"
        "                storeFile file(ks)\n"
        "                storePassword System.getenv('KEYSTORE_PASSWORD')\n"
        "                keyAlias System.getenv('KEY_ALIAS')\n"
        "                keyPassword System.getenv('KEY_PASSWORD')\n"
        "            }\n"
        "        }\n"
        "        buildTypes { release { signingConfig signingConfigs.release } }\n"
        "    }\n"
        "}\n")
    bg = android / "app" / "build.gradle"
    g = bg.read_text(encoding="utf-8")
    if "signing.gradle" not in g:
        bg.write_text(g + "\napply from: 'signing.gradle'\n", encoding="utf-8")


def compilar_android(release):
    android = AQUI / "android"
    if os.name != "nt":
        os.chmod(android / "gradlew", 0o755)
    if release:
        run([GRADLEW, "assembleRelease", "bundleRelease"], cwd=android)
        destino = [android / "app/build/outputs/apk/release", android / "app/build/outputs/bundle/release"]
    else:
        run([GRADLEW, "assembleDebug"], cwd=android)
        destino = [android / "app/build/outputs/apk/debug"]
    saida = AQUI / "dist"
    saida.mkdir(exist_ok=True)
    for pasta in destino:
        for arq in list(pasta.glob("*.apk")) + list(pasta.glob("*.aab")):
            shutil.copy2(arq, saida / arq.name)
            print("✔", saida / arq.name)


# ---------------------------------------------------------------------- iOS
def preparar_ios():
    if sys.platform != "darwin":
        sys.exit("O projeto iOS só pode ser preparado em macOS (Xcode).")
    ios = AQUI / "ios"
    if not ios.exists():
        run([NPX, "cap", "add", "ios"])
    plist = ios / "App" / "App" / "Info.plist"
    p = plist.read_text(encoding="utf-8")
    if "NSFaceIDUsageDescription" not in p:
        p = p.replace("</dict>\n</plist>",
                      "\t<key>NSFaceIDUsageDescription</key>\n"
                      "\t<string>Use o Face ID para acessar a área administrativa.</string>\n</dict>\n</plist>")
        plist.write_text(p, encoding="utf-8")
    gerar_icones_ios(ios)


def main():
    ap = argparse.ArgumentParser(description="Gera o app mobile Doce Cesta Brasília")
    ap.add_argument("--android", action="store_true")
    ap.add_argument("--ios", action="store_true")
    ap.add_argument("--apk", action="store_true", help="compila APK debug")
    ap.add_argument("--release", action="store_true", help="compila APK/AAB de release")
    a = ap.parse_args()
    if not (a.android or a.ios):
        ap.error("informe --android e/ou --ios")
    if not LOGO.exists():
        sys.exit(f"Logo não encontrada: {LOGO}")

    run([NPM, "install", "--no-audit", "--no-fund", "--legacy-peer-deps"])
    if a.android:
        preparar_android()
    if a.ios:
        preparar_ios()
    run([NPX, "cap", "sync"])
    if a.android and (a.apk or a.release):
        compilar_android(a.release)
    print("Concluído.")


if __name__ == "__main__":
    main()
