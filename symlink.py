from pathlib import Path
import os

# Windows only and run as admin
files  = [
    Path( "batch_export.inx" ), 
    Path( "batch_export.py" )
    ]

dest = Path(os.getenv('APPDATA'))/r"inkscape\extensions"
for file in files:
    path = dest/file
    path.symlink_to(file.absolute())
