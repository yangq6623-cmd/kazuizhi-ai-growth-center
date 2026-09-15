# V1.9.5 Build Resource Check

Required frontend resources:

- web/index.html
- web/style.css
- web/dashboard.js
- web/charts.js
- web/WEB_VERSION.txt

Build pipeline:

Source web -> Build -> EXE -> Installer

Before packaging:
- Clear old build cache
- Copy latest web resources
- Verify version file
