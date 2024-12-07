import os
import json
import argparse
import piexif
from PIL import Image
from datetime import datetime
import logging
from pathlib import Path
import shutil
import unicodedata
from pillow_heif import register_heif_opener

# google-photos-takeout-metadata-exif-json-to-synology
# https://github.com/alexmonnerie/google-photos-takeout-metadata-exif-json-to-synology/

# HEIC support recording
register_heif_opener()

# Supported formats
IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.heic', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
VIDEO_FORMATS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v'}

ALL_FORMATS = {ext.lower() for ext in list(IMAGE_FORMATS) + list(VIDEO_FORMATS)}

class MediaProcessor:
    def __init__(self, work_dir, debug=False, dry_run=False):
        self.work_dir = Path(work_dir)
        self.dry_run = dry_run
        self.stats = {
            'success': 0,
            'warnings': 0,
            'json_not_found': 0,
            'ignored_with_exif': 0,
            'json_found_in_other_dir': 0
        }
        self.files_without_json = []
        self.files_with_warnings = []
        
        # Logging settings
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Logging for PIL (EXIF editing)
        logging.getLogger('PIL').setLevel(logging.WARNING)

    def find_json_file(self, media_path):
        """Find associated JSON file using multiple strategies"""
        
        def get_potential_json_names(base_path):
            """Generate various possible names for locating JSON file"""
            potential_names = [
                # Standard cases
                f"{base_path}.json", # image.jpg.json
                f"{str(base_path).replace(base_path.suffix, '')}.json", # image.json
            ]
            
            # Case: LivePhotos iOS
            if base_path.suffix.upper() == '.MP4':
                potential_names.extend([
                    f"{str(base_path).replace(base_path.suffix, '.HEIC')}.json",
                    f"{str(base_path).replace(base_path.suffix, '.JPG')}.json",
                    # LivePhotos case and duplicate file
                    f"{str(base_path.parent / base_path.stem).split('(')[0]}.HEIC.json",
                    f"{str(base_path.parent / base_path.stem).split('(')[0]}.JPG.json",
                ])

            potential_names.extend([
                # Case: duplicated files (x)
                f"{str(base_path.parent / base_path.stem).split('(')[0]}{base_path.suffix}.json",
                # Case: JSON without “-modified” suffix
                f"{str(base_path).replace('-modifié', '')}.json",
                f"{str(base_path).replace('-modified', '')}.json",
            ])

            # Case: truncated filename 
            full_name = str(base_path)
            for i in range(8):  # Limit 8 attempts
                truncated = full_name[:-(i+1)]  # Remove a character by one
                potential_names.append(f"{truncated}.json")

            return potential_names

        # Step 1: search JSON file in the same directory as the media
        for json_path in get_potential_json_names(media_path):
            logging.debug(f"Check if JSON exist {json_path}")
            if Path(json_path).exists():
                logging.debug(f"JSON file found {json_path}")
                return Path(json_path)

        # Step 2: search for JSON in subdirectories
        media_name = media_path.name
        for json_candidate in self.work_dir.rglob('*.json'):
            if json_candidate.name in [Path(p).name for p in get_potential_json_names(media_path)]:
                logging.warning(f"JSON file found in another directory {json_candidate}")
                self.stats['json_found_in_other_dir'] += 1
                return json_candidate

        return None

    def update_file_dates(self, file_path, timestamp):
        """Update system dates in media"""

        if self.dry_run:
            newdate_modified = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            logging.debug(f"[DRY RUN] Simulated updating system dates for {file_path} : {newdate_modified}")
            return

        # Update access (atime) and modification (mtime) dates
        os.utime(file_path, (timestamp, timestamp))
        
        # Update last modification date
        Path(file_path).touch(exist_ok=True)
        os.utime(file_path, (timestamp, timestamp))
        
        logging.debug(f"Updated system dates for {file_path}")

    def update_image_exif(self, image_path, json_data):
        """Update an picture's EXIF metadata"""
        if image_path.suffix.lower() not in IMAGE_FORMATS:
            return

        try:
            timestamp = int(json_data['photoTakenTime']['timestamp'])
            date_time = datetime.fromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
            
            if self.dry_run:
                logging.debug(f"[DRY RUN] Simulated updating EXIF metadata for {image_path}")
                return

            exif_dict = {
                "0th": {},
                "Exif": {
                    piexif.ExifIFD.DateTimeOriginal: date_time.encode(),
                    piexif.ExifIFD.DateTimeDigitized: date_time.encode(),
                    piexif.ExifIFD.SubSecTime: "00".encode(),
                    piexif.ExifIFD.SubSecTimeOriginal: "00".encode(),
                    piexif.ExifIFD.SubSecTimeDigitized: "00".encode(),
                    piexif.ExifIFD.OffsetTime: "+00:00".encode(),
                    piexif.ExifIFD.OffsetTimeOriginal: "+00:00".encode(),
                    piexif.ExifIFD.OffsetTimeDigitized: "+00:00".encode()
                },
                "GPS": {}
            }

            # GPS data preparation 
            gps_data = json_data.get('geoDataExif', {})
            lat = gps_data.get('latitude', 0)
            lon = gps_data.get('longitude', 0)
            
            if lat != 0 and lon != 0:
                exif_dict["GPS"] = self.create_gps_dict(lat, lon)

            exif_bytes = piexif.dump(exif_dict)
            
            # Saving EXIF metadata
            with Image.open(image_path) as img:
                img.save(image_path, exif=exif_bytes)

        except Exception as e:
            logging.warning(f"An error occurred during EXIF update of {image_path}: {str(e)}")
            self.stats['warnings'] += 1
            self.files_with_warnings.append((str(image_path), str(e)))

    def create_gps_dict(self, lat, lon):
        """Create GPS dictionary for EXIF data"""
        lat_deg = self.convert_to_degrees(abs(lat))
        lon_deg = self.convert_to_degrees(abs(lon))
        
        return {
            piexif.GPSIFD.GPSLatitudeRef: "N".encode() if lat >= 0 else "S".encode(),
            piexif.GPSIFD.GPSLatitude: lat_deg,
            piexif.GPSIFD.GPSLongitudeRef: "E".encode() if lon >= 0 else "W".encode(),
            piexif.GPSIFD.GPSLongitude: lon_deg
        }

    @staticmethod
    def convert_to_degrees(value):
        """Converts decimal value into degrees for EXIF format"""
        d = int(value)
        m = int((value - d) * 60)
        s = int(((value - d) * 60 - m) * 60)
        return ((d, 1), (m, 1), (s, 1))

    def process_media_file(self, media_path):
        """Processes a media file, main processing function"""
        json_path = self.find_json_file(media_path)

        if not json_path:
            # # Check if EXIF are already included in image
            # if media_path.suffix.lower() in IMAGE_FORMATS:
            #     try:
            #         with Image.open(media_path) as img:
            #             exif = img._getexif()
            #             if exif and piexif.ExifIFD.DateTimeOriginal in exif:
            #                 logging.info(f"EXIF already included in {media_path}, ignored")
            #                 self.stats['ignored_with_exif'] += 1
            #                 return
            #     except Exception:
            #         pass

            logging.warning(f"JSON file not found for {media_path}")
            self.stats['json_not_found'] += 1
            self.files_without_json.append(str(media_path))
            return
        
        try:
            logging.info(f"JSON file used {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # EXIF update except for HEIC images
            if media_path.suffix.lower() in IMAGE_FORMATS and media_path.suffix.lower() != '.heic':
                self.update_image_exif(media_path, json_data)

            # Update system dates
            timestamp = int(json_data['photoTakenTime']['timestamp'])
            self.update_file_dates(media_path, timestamp)
            
            newdate = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            self.stats['success'] += 1
            logging.info(f"New date time {newdate} for {media_path}")
            logging.info(f"Successful processing for {media_path}")

        except Exception as e:
            logging.error(f"An error occurred when processing {media_path}: {str(e)}")
            self.stats['warnings'] += 1
            self.files_with_warnings.append((str(media_path), str(e)))

    def process_directory(self):
        """Processes all media files stored in directory"""
        for file_path in self.work_dir.rglob('*'):
            if file_path.suffix.lower() in ALL_FORMATS:
                logging.info(f"File processing {file_path}")
                self.process_media_file(file_path)


    def print_stats(self):
        """Shows processing statistics"""
        print("\n===== Final results =====")
        print(f"Files processed successfully: {self.stats['success']}")
        print(f"Files processed with warnings: {self.stats['warnings']}")
        print(f"JSON files found in another directory: {self.stats['json_found_in_other_dir']}")
        print(f"JSON files not found: {self.stats['json_not_found']}") 
        # print(f"JSON files not found (but EXIF metadata existing): {self.stats['ignored_with_exif']}") 
        # This option is disabled. You can enable this option by unchecking lines 189-199. 
        # This may cause some files to be missed during processing. I prefer to manually set dates for concerned files.
        
        if self.files_with_warnings:
            print("\nWarning files:")
            for file, error in self.files_with_warnings:
                print(f"- {file}")
                print(f"  Error details: {error}")

        if self.files_without_json:
            print("\nJSON files not found:")
            for file in self.files_without_json:
                print(f"- {file}")
            
            # In rare cases, if JSON can't be found and error processing occurs, it's possible to manually set date and time for media by referring to the file name or album name in which it's located.
            reponse = input("\nDo you want manually set date and time for files without JSON? (y/n) ")
            if reponse.lower() == 'y':
                for file in self.files_without_json:
                    date_str = input(f"\nEnter date and time for {file} \nFormat YYYY-MM-DD HH:MM (or press Enter to skip) : ")
                    if date_str.strip():   # If user has input date time
                        try:
                            timestamp = int(datetime.strptime(date_str, "%Y-%m-%d %H:%M").timestamp())
                            self.update_file_dates(Path(file), timestamp)
                            logging.info(f"Successfully set date and time")
                        except ValueError:
                            logging.error(f"Invalid date time format, ignored")

            # ask_delete_json = input("\nDo you want purge all JSON files? (y/n) ")
            # if ask_delete_json.lower() == 'y':
            #     logging.info("Deleting JSON files...")
            #     for json_file in self.work_dir.rglob('*.json'):
            #         if not self.dry_run:
            #             try:
            #                 json_file.unlink()
            #                 logging.debug(f"JSON file deleted : {json_file}")
            #             except Exception as e:
            #                 logging.error(f"An error occurred during deleting {json_file}: {str(e)}")
            #         else:
            #             logging.debug(f"[DRY RUN] Simulated deletion of JSON file : {json_file}")

            # ask_delete_emptydir = input("\nDo you want delete all empty directories? (y/n) ")
            # if ask_delete_emptydir.lower() == 'y':
            #     logging.info("Deleting empty directories...")
            #     for dirpath, dirnames, filenames in os.walk(self.work_dir, topdown=False):
            #         if not dirnames and not filenames:
            #             if not self.dry_run:
            #                 try:
            #                     os.rmdir(dirpath)
            #                     logging.debug(f"Empty directory deleted : {dirpath}")
            #                 except Exception as e:
            #                     logging.error(f"An error occurred during deleting empty directory {dirpath}: {str(e)}")  
            #             else:
            #                 logging.debug(f"[DRY RUN] Simulated deletion of empty directory : {dirpath}")


def main():
    parser = argparse.ArgumentParser(description="Update media file metadata")
    parser.add_argument("work_dir", help="Work directory with folders and media files")
    parser.add_argument("--debug", action="store_true", help="Activate verbose debug mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate proccessing without modifying files")
    
    args = parser.parse_args()
    
    processor = MediaProcessor(args.work_dir, args.debug, args.dry_run)
    processor.process_directory()
    processor.print_stats()

if __name__ == "__main__":
    main() 

