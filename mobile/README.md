# App mobile — Doce Cesta Brasília

    pip install pillow
    python mobile/build_app.py --android --apk      # APK em mobile/dist/
    python mobile/build_app.py --android --release  # AAB/APK assinado (KEYSTORE_*)
    python mobile/build_app.py --ios                # macOS + Xcode

Deploy do servidor: publicar `assets/app_bridge.js` e `utils/ui.py` junto com o app Streamlit.
GitHub Actions: `.github/workflows/build_android.yml`.
