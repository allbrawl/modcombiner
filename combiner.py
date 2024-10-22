import os
import shutil
import csv
from datetime import datetime
import subprocess
import argparse
import json
import glob
import re
import random
import string
from sc_compression import decompress, compress
from sc_compression.signatures import Signatures

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def merge_csv_files(base_file, mod_file, output_file):
    with open(base_file, 'r', newline='', encoding='utf-8') as f:
        base_reader = csv.reader(f)
        base_data = list(base_reader)
    with open(mod_file, 'r', newline='', encoding='utf-8') as f:
        mod_reader = csv.reader(f)
        mod_data = list(mod_reader)

    header = base_data[0] if base_data else mod_data[0]
    base_data = base_data[1:] if base_data else []
    mod_data = mod_data[1:] if mod_data else []

    base_keys = {row[0]: row for row in base_data}
    merged_data = base_data.copy()
    for row in mod_data:
        if row[0] not in base_keys:
            merged_data.append(row)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(merged_data)


def apply_config(data, file):  # Modified to work with list of lists
    mod_config = config.get("values", {})
    col_data_types = {}

    header = data[0]
    dtype_row = data[1]
    data_rows = data[2:]

    for csv_file, entries in mod_config.items():
        if file.endswith(csv_file):
            for identifier, updates in entries.items():
                for col, value in updates.items():
                    if col not in col_data_types:
                        if isinstance(value, bool):
                            col_data_types[col] = 'boolean'
                        elif isinstance(value, str):
                            col_data_types[col] = 'string'
                        elif isinstance(value, int) or isinstance(value, float):
                            col_data_types[col] = 'int'
                        else:
                            col_data_types[col] = 'string'

    for col, dtype in col_data_types.items():
        if col not in header:
            header.append(col)
            dtype_row.append(dtype)
            for row in data_rows:
                row.append(str(value)) 
        else:
            col_index = header.index(col)
            if not dtype_row[col_index]:
                dtype_row[col_index] = dtype

    for csv_file, entries in mod_config.items():
        if file.endswith(csv_file):
            if "*" in entries:
                updates = entries["*"]
                for col, value in updates.items():
                    if col in header:
                        col_index = header.index(col)
                        for row in data_rows:
                            if not row[col_index] or row[col_index] == str(value):
                                row[col_index] = str(value)

            for identifier, updates in entries.items():
                if identifier != "*":
                    for row in data_rows:
                        if row[0] == identifier:
                            for col, value in updates.items():
                                if col in header:
                                    col_index = header.index(col)
                                    row[col_index] = str(value)
    return data


def copy_initial_mod(file_path, target_mod):
    if not os.path.exists(target_mod):
        os.makedirs(target_mod)

    if os.path.isdir(file_path):
        mod_path = file_path
        mod_folder = os.path.basename(file_path)
    else:
        mod_folder = extract_files(file_path)
        mod_path = os.path.join(work_directory, mod_folder)

    if os.path.exists(mod_path):
        for item in os.listdir(mod_path):
            src = os.path.join(mod_path, item)
            dest = os.path.join(target_mod, item)
            if os.path.isdir(src):
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest)


def merge_mods_into_base(base_mod, mods_list, config):
    paths = {
        "csv_logic": ["characters.csv", "cards.csv", "skills.csv", "skins.csv",
                      "skin_confs.csv", "projectiles.csv", "accessories.csv", "items.csv",
                      "locations.csv", "maps.csv"],
        "csv_client": ["sounds.csv", "effects.csv", "animations.csv", "faces.csv"]
    }

    for mod in mods_list:
        mod_path = os.path.join(work_directory, mod)
        for folder, files in paths.items():
            for csv_file in files:
                mod_csv = os.path.join(mod_path, "assets", folder, csv_file)
                base_csv = os.path.join(base_mod, "assets", folder, csv_file)
                if os.path.exists(mod_csv):
                    merge_csv_files(base_csv, mod_csv, base_csv)

    additional_folders = ["sc", "sc3d", "sfx", "music", "shader", "localization", "image", "badge"]
    for mod in mods_list:
        mod_path = os.path.join(work_directory, mod)
        for folder in additional_folders:
            folder_path = os.path.join(mod_path, "assets", folder)
            if os.path.exists(folder_path):
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        src_file = os.path.join(root, file)
                        rel_path = os.path.relpath(root, mod_path)
                        dest_folder = os.path.join(base_mod, rel_path)
                        ensure_directory(dest_folder)
                        shutil.copy2(src_file, os.path.join(dest_folder, file))


def extract_files(file_path):
    mod_name = os.path.basename(file_path).replace(".apk", "").replace(".zip", "")
    new_file_path = os.path.join(work_directory, mod_name)

    if os.path.exists(new_file_path) == False:
        if file_path.endswith(".apk") or file_path.endswith(".zip"):
            subprocess.run(['java', '-jar', apktool_path, 'd', file_path, '-o', new_file_path], check=True)
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
    else:
        print(f"{new_file_path} already exists, skipping...")

    return mod_name


def create_apk(mod_path):
    try:
        os.makedirs(release_directory, exist_ok=True)
        output_path = os.path.join(release_directory, f"{mod_name}.apk")
        subprocess.run(['java', '-jar', apktool_path, 'b', mod_path, '-o', output_path], check=True)
    except Exception as e:
        print(f"Error creating APK: {e}")


def load_configuration(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config


def expand_wildcards(paths):
    expanded_paths = []
    for path in paths:
        expanded_paths.extend(glob.glob(path))
    return expanded_paths


def generate_random_string(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def change_manifest_package(manifest_path, new_package_name, apktool_path):
    manifest_path = manifest_path.replace("./", f"{os.getcwd()}/")
    manifest_file = os.path.join(manifest_path, "AndroidManifest.xml")
    file = os.path.join(manifest_path, "AndroidManifest.xml")
    
    with open(manifest_file, 'r') as file:
        manifest_content = file.read()
    
    match = re.search(r'package="([^"]+)"', manifest_content)
    if match:
        current_package_name = match.group(1)
        
        updated_content = manifest_content.replace(current_package_name, new_package_name)
        
        with open(manifest_file, 'w') as file:
            file.write(updated_content)
        
        subprocess.run(['java', '-jar', apktool_path, 'b', manifest_path], check=True)
    else:
        raise ValueError("Package name not found in the manifest.")

# https://github.com/xcoder-tool/XCoder/blob/master/system/lib/features/csv/decompress.py
# https://pypi.org/project/sc-compression/
def decompress_csv(input, output):
    for file in os.listdir(input):
        if file.endswith(".csv"):
            try:
                with open(f"{input}/{file}", "rb") as f:
                    file_data = f.read()

                with open(f"{output}/{file}", "wb") as f:
                    f.write(decompress(file_data)[0])
            except Exception as e:
                print(f"Failed to decompress: {e}")

# https://github.com/xcoder-tool/XCoder/blob/master/system/lib/features/csv/compress.py
# https://pypi.org/project/sc-compression/
def compress_csv(input, output):
    for file in os.listdir(input):
        if file.endswith(".csv"):
            try:
                with open(f"{input}/{file}", "rb") as f:
                    file_data = f.read()

                with open(f"{output}/{file}", "wb") as f:
                    f.write(compress(file_data, Signatures.LZMA))
            except Exception as e:
                print(f"Failed to compress: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=False, default="configuration.json")
    args = parser.parse_args()

    config = load_configuration(args.config)
    
    mods = config.get("mods", [])
    mod_name = config.get("mod_name", "All Brawl")
    package_name = config.get("package_name", "com.natesworks.allbrawl")
    app_icon_path = config.get("app_icon_path")
    apktool_path = config["apktool_path"]
    work_directory = config["work_directory"]
    apk_directory = f"{config['release_directory']}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    release_directory = os.path.join(apk_directory, mod_name)

    ensure_directory(work_directory)
    ensure_directory(release_directory)

    mods = expand_wildcards(mods)

    if mods:
        copy_initial_mod(mods[0], release_directory)
        for mod in mods:
            try:
                mod_folder = extract_files(mod)
            except Exception as e:
                print(f"Error extracting {mod}: {e}")
            merge_mods_into_base(release_directory, [mod_folder], config)

        change_manifest_package(release_directory, package_name, config["apktool_path"])

        print(f"All mods merged into {release_directory}")
        print("Creating apk...")
        create_apk(release_directory)
    else:
        print("No mods found")
