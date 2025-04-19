import zipfile

with zipfile.ZipFile('stocknews_monitor.zip', 'r') as zipf:
    print("Contents of the zip file:")
    for file in zipf.namelist():
        print(f"  {file}")