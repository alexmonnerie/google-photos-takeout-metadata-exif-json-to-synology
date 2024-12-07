import os
import zipfile
import sys

# google-photos-takeout-metadata-exif-json-to-synology
# https://github.com/alexmonnerie/google-photos-takeout-metadata-exif-json-to-synology/

def unzip_files(source_dir, dest_dir):
     # Checks if the source folder exists
    if not os.path.exists(source_dir):
        print(f"Error: Source directory {source_dir} doesn't exist.")
        return

    # Create destination directory if not already created
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    # Browse all files in source folder
    for item in os.listdir(source_dir):
        # Construct full path of file
        file_path = os.path.join(source_dir, item)
        
        # Check if it's zip file
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Extract content to target directory
                zip_ref.extractall(dest_dir)
                print(f"Extract: {item} into {dest_dir}")

if __name__ == "__main__":
     # Checks if arguments are given
    if len(sys.argv) != 3:
        print("usage: python 01_extract_takeout_files.py source_dir work_dir")
    else:
        source_directory = sys.argv[1]
        destination_directory = sys.argv[2]
        print(f"Starting data extracting to {destination_directory} ")
        unzip_files(source_directory, destination_directory)

