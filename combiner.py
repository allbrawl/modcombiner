import os
import shutil
import pandas as pd
from datetime import datetime
import subprocess
import argparse
import json
import shlex

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def merge_csv_files(file1, file2, output_file):
    df1 = pd.read_csv(file1) if os.path.exists(file1) else pd.DataFrame()
    df2 = pd.read_csv(file2) if os.path.exists(file2) else pd.DataFrame()

    if df2.empty:
        return

    if df1.empty:
        return

    merged_df = pd.concat([df1, df2[~df2[df2.columns[0]].isin(df1[df1.columns[0]])]])
    merged_df.to_csv(output_file, index=False)

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

def merge_mods_into_base(base_mod, mods_list):
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

    if file_path.endswith(".apk") or file_path.endswith(".zip"):
        shutil.copy(file_path, new_file_path + ".apk")
        zip_path = new_file_path + ".zip"
        os.rename(new_file_path + ".apk", zip_path)
        shutil.unpack_archive(zip_path, new_file_path)
        os.remove(zip_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    return mod_name


def create_apk(mod_name):
    try:
        os.makedirs(release_directory, exist_ok=True)
        
        zip_file_path = os.path.join(apk_directory, f"{mod_name}.apk").replace('./', os.getcwd() + "/")

        zip_archive_path = shutil.make_archive(zip_file_path, 'zip', release_directory)
        
        apk_file_path = zip_file_path
        os.rename(zip_archive_path, apk_file_path)
        
    except Exception as e:
        print(f"Error creating APK: {e}")

    return apk_file_path

def sign(apk_path, uber_path):
    print("Signing...")
    try:
        uber_path_expanded = os.path.expanduser(uber_path)
                
        subprocess.run(['java', '-jar', uber_path_expanded, '-a', apk_path], check=True)
    except Exception as e:
        print(e)


def load_configuration(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=False, default="configuration.json")
    args = parser.parse_args()

    config = load_configuration(args.config)
    
    mod_name = config.get("mod_name", "All Brawl")
    mods = config["mods"]
    uber_path = config["uber_path"]
    work_directory = config["work_directory"]
    apk_directory = f"{config['release_directory']}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    print(apk_directory)
    release_directory = f"{apk_directory}/{mod_name}"

    ensure_directory(work_directory)
    ensure_directory(release_directory)

    if mods:
        first_mod = mods[0]
        ensure_directory(release_directory)
        copy_initial_mod(first_mod, release_directory)

        for mod in mods[1:]:
            try:
                mod_folder = extract_files(mod)
            except Exception as e:
                print(f"Error extracting {mod}: {e}")
            merge_mods_into_base(release_directory, [mod_folder])

        print(f"All mods merged into {release_directory}")
        print("Creating apk...")
        sign(f"{create_apk(mod_name)}", uber_path)
    else:
        print("No mods found")
