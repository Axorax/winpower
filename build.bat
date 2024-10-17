@echo off

pyinstaller --name="Winpower" --onefile --paths=env/Lib/site-packages --add-data="env/Lib/site-packages/sv_ttk;sv_ttk" --add-data="icon.ico;." --noconsole --icon=icon.png main.py
