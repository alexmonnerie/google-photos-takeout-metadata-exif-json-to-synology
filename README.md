# google-photos-takeout-metadata-exif-json-to-synology

## Context

This project contains Python scripts for processing and organizing photos/videos, specifically for managing date metadata. When exporting from Google Photos using Google Takeout, metadata is frequently missing from photos and videos. These scripts allow you to reintegrate media metadata from `.json` files into media archives retrieved from Google Takeout. The script works on photos and videos, including iOS Live Photos and various known types.

It was initially designed for importing media to a Synology NAS, but can be used for importing to any other type of private or public photo library.

## User guide

### Download datas from Google Photos

1. **Access Google Takeout:**
   - Go to [Google Takeout](https://takeout.google.com/)
   - Log in to your Google account.

2. **Select data for export:**
   - By default, all Google services are selected
   - Click on “Deselect all”.
   - Check “Google Photos” only

3. **Configure export:**
   - Choose export frequency (single export recommended in our case)
   - Select file format (zip recommended)
   - Choose maximum archive size (recommended: 4 GB)
   - Click on “Create export”.

4. **Download archive:**
   - Google will prepare your data (may take several hours depending on size)
   - You will receive an email when the export is ready.
   - Download the archive via the links provided or from https://takeout.google.com/manage

> Note: Google Takeout archives can be very large. Make sure you have enough free disk space before you start downloading.


### Environment preparation

1. **Download Python :**
   - Go to [python.org](https://www.python.org)
   - Download the latest stable version of Python 3.x

2. **Check installation:**
   ```bash
   python --version # Show Python version
   python3 --version 
   ```

3. **Create a Python virtual environment:**
   ```bash
   python3 -m venv venvmedia
   source venvmedia/bin/activate # On Windows, use venv\Scripts\activate
   ```
   To exit virtual environment : `deactivate`

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt --verbose 
   ```

### Running scripts

- **Extracting and moving files:**
  ```bash
  python 01_extract_takeout_files.py <source_dir> <work_dir>  
  ```

  - `<source_dir>`: Source folder containing Takeout archives.
  - `<work_dir>`: Destination folder for extracted folders and files, then used as work_dir.


- **Updating media metadata:**
  ```bash
  python 02_update_media_metadata.py <work_dir> [--debug] [--dry-run]  
  ```

  - `<work_dir>`: Working folder containing media files.
  - `--debug`: Activates verbose debug mode.
  - `--dry-run`: Simulation without file modification.


## Technical explanations

- **01_extract_takeout_files.py**: This script extracts data from various Takeout archives and moves them into a single folder. The source folder must contain the zip archives downloaded from Google Takeout.


- **02_update_media_metadata.py**: This script matches metadata contained in JSON files with medias (photos and videos) stored in `<work_dir>`. It contains various special cases and rules for searching JSON files associated with various media (LivePhotos, modified photos, duplicate media, troncated filename). It updates the creation and modification dates of files, as well as the EXIF metadata of images. It also updates GPS coordinates in EXIF metadata.    


## Results

At the end of execution of the `02_update_media_metadata.py` script, the following statistics are displayed:

- Number of files successfully processed
- Number of files processed with warning 
  - File corrupted or error during EXIF modification, but system date modification was usually successful
- Number of JSON files found in another directory
- Number of JSON files not found (with list of affected files displayed)

> Note: This information can be used to check the effectiveness of processing and identify files requiring particular attention.

## Dry Run mode

The `--dry-run` mode allows to :
- Simulate all operations without modifying files
- Check actions that would otherwise be performed
- Test detection of JSON files
- Validate processes before modifying files

## Additional features

At the end of execution of the `02_update_media_metadata.py` script,  different options are available:

1. **Manual date assignment**
   - For files without associated and located JSON, manual date assignment possible
   - Expected format: YYYY-MM-DD HH:MM
   - You can skip a file by pressing Enter

2. **Clean JSON files** (currently disabled)
   - Option to delete all JSON files after processing.
   - Useful for freeing up space after metadata processing.
   - Use `cd <work_dir>; find . -type f -name "*.json" -delete` for deleting JSON files.

3. **Clean empty directories** (currently disabled)
   - Option to delete all empty directories after processing.
