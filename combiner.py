import os
import shutil
import pandas as pd
from datetime import datetime
import subprocess
import argparse
import json
import glob

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def merge_csv_files(base_file, mod_file, output_file):
    df_base = pd.read_csv(base_file, header=None, dtype=str, keep_default_na=False) if os.path.exists(base_file) else pd.DataFrame()
    df_mod = pd.read_csv(mod_file, header=None, dtype=str, keep_default_na=False) if os.path.exists(mod_file) else pd.DataFrame()

    if not df_base.empty:
        df_base.columns = df_base.iloc[0]
        df_base = df_base.drop(df_base.index[0])

    if not df_mod.empty:
        df_mod.columns = df_mod.iloc[0]
        df_mod = df_mod.drop(df_mod.index[0])

    df_base = apply_config(df_base, base_file)

    header_row = pd.DataFrame([df_base.columns.tolist()], columns=df_base.columns)
    dtype_row = df_base.iloc[0:1]

    df_base_data = df_base.iloc[1:]
    dtype_row_mod = df_mod.iloc[0:1]
    df_mod_data = df_mod.iloc[1:]

    merged_data = pd.concat([df_base_data, df_mod_data[~df_mod_data[df_mod_data.columns[0]].isin(df_base_data[df_base_data.columns[0]])]], sort=False)
    merged_df = pd.concat([header_row, dtype_row, merged_data], ignore_index=True)
    merged_df = merged_df.fillna('')

    merged_df.to_csv(output_file, index=False, header=False)

def apply_config(df, file):
    mod_config = config.get("values", {})
    col_data_types = {}

    dtype_row_index = df.index[0]
    data_start_indices = df.index[1:]

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
        if col not in df.columns:
            df[col] = ''
            df.loc[dtype_row_index, col] = dtype
            df.loc[data_start_indices, col] = str(value)
        else:
            if pd.isna(df.loc[dtype_row_index, col]) or df.loc[dtype_row_index, col] == '':
                df.loc[dtype_row_index, col] = dtype

    for csv_file, entries in mod_config.items():
        if file.endswith(csv_file):
            if "*" in entries:
                updates = entries["*"]
                for col, value in updates.items():
                    if col in df.columns:
                        dtype = df.loc[dtype_row_index, col]
                        for index in data_start_indices:
                            current_value = df.at[index, col]
                            if pd.isna(current_value) or current_value == str(value) or current_value == '':
                                df.at[index, col] = str(value)

            for identifier, updates in entries.items():
                if identifier != "*":
                    for index in data_start_indices:
                        if df.at[index, df.columns[0]] == identifier:
                            for col, value in updates.items():
                                if col in df.columns:
                                    dtype = df.loc[dtype_row_index, col]
                                    df.at[index, col] = str(value)
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
        subprocess.run(['java', '-jar', apktool_path, 'd', file_path, '-o', new_file_path, '-f'], check=True)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    return mod_name

def create_apk(mod_path):
    try:
        os.makedirs(release_directory, exist_ok=True)
        subprocess.run(['java', '-jar', apktool_path, 'b', mod_path, '-o', os.path.join(release_directory, f"{mod_name}.apk"), '-f'], check=True)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=False, default="configuration.json")
    args = parser.parse_args()

    config = load_configuration(args.config)
    
    mods = config.get("mods", [])
    mod_name = config.get("mod_name", "All Brawl")
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

        print(f"All mods merged into {release_directory}")
        print("Creating apk...")
        create_apk(release_directory)
    else:
        print("No mods found")
