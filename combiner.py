import os
import shutil
import pandas as pd
from datetime import datetime
import subprocess
import argparse
import json

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def merge_csv_files(base_file, mod_file, output_file):
    df_base = pd.read_csv(base_file) if os.path.exists(base_file) else pd.DataFrame()
    df_mod = pd.read_csv(mod_file) if os.path.exists(mod_file) else pd.DataFrame()

    df_base = apply_config(df_base, mod_file)

    merged_df = pd.concat([df_base, df_mod[~df_mod[df_mod.columns[0]].isin(df_base[df_base.columns[0]])]])

    merged_df.to_csv(output_file, index=False)

def apply_config(df, file):
    mod_config = config.get("values", {})
    general_values = {}

    for csv_file, values in mod_config.items():
        if file.endswith(csv_file):
            for col, value in values.items():
                if col != "*":
                    if isinstance(value, bool):
                        general_values[col] = False
                    elif isinstance(value, str):
                        general_values[col] = ""
                    elif isinstance(value, (int, float)):
                        general_values[col] = 0

    for col, value in general_values.items():
        if col not in df.columns:
            df[col] = value
        df.at[0, col] = value

    for csv_file, values in mod_config.items():
        if file.endswith(csv_file):
            if "*" in values:
                updates = values["*"]
                for col, value in updates.items():
                    if col in df.columns:
                        for index, row in df.iterrows():
                            if col in df.columns:
                                if isinstance(value, (bool, str, int, float)):
                                    df.at[index, col] = value
                                else:
                                    df.at[index, col] = list(value.values())[0]

            for identifier, updates in values.items():
                if identifier != "*":
                    for index, row in df.iterrows():
                        if row[0] == identifier:
                            for col, value in updates.items():
                                df.at[index, col] = value
    return df

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
                values = config["values"].get(csv_file, {})
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

    if file_path.endswith(".apk") or file_path.endswith(".zip"):
        shutil.copy(file_path, new_file_path + ".apk")
        zip_path = new_file_path + ".zip"
        os.rename(new_file_path + ".apk", zip_path)
        shutil.unpack_archive(zip_path, new_file_path)
        os.remove(zip_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    return mod_name


def create_apk(mod_path):
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
    
    mods = config.get("mods", [])
    mod_name = config.get("mod_name", "All Brawl")
    uber_path = config["uber_path"]
    work_directory = config["work_directory"]
    apk_directory = f"{config['release_directory']}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    release_directory = os.path.join(apk_directory, mod_name)

    ensure_directory(work_directory)
    ensure_directory(release_directory)


    if mods:
        copy_initial_mod(mods[0], release_directory)
        for mod in mods:
            try:
                mod_folder = extract_files(mod)
            except Exception as e:
                print(f"Error extracting {mod}: {e}")
            merge_mods_into_base(release_directory, [mod_folder], config)

        print(f"All mods merged into {release_directory}")
        print("Creating apk...")
        sign(f"{create_apk(mods)}", uber_path)
    else:
        print("No mods found")
