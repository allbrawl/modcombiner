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
    # Read CSV files with header=None
    df_base = pd.read_csv(base_file, header=None, dtype=str, keep_default_na=False) if os.path.exists(base_file) else pd.DataFrame()
    df_mod = pd.read_csv(mod_file, header=None, dtype=str, keep_default_na=False) if os.path.exists(mod_file) else pd.DataFrame()

    if not df_base.empty:
        df_base.columns = df_base.iloc[0]  # Set headers
        df_base = df_base.drop(df_base.index[0])  # Remove header row

    if not df_mod.empty:
        df_mod.columns = df_mod.iloc[0]
        df_mod = df_mod.drop(df_mod.index[0])

    # Apply configuration to df_base
    df_base = apply_config(df_base, base_file)

    # Now, get header and data type rows from df_base
    header_row = pd.DataFrame([df_base.columns.tolist()], columns=df_base.columns)
    dtype_row = df_base.iloc[0:1]  # Data type row

    # Exclude data type row from df_base
    df_base_data = df_base.iloc[1:]

    # Similarly for df_mod, get data type row and data
    dtype_row_mod = df_mod.iloc[0:1]
    df_mod_data = df_mod.iloc[1:]

    # Merge data, excluding data type row
    merged_data = pd.concat([df_base_data, df_mod_data[~df_mod_data[df_mod_data.columns[0]].isin(df_base_data[df_base_data.columns[0]])]], sort=False)

    # Reconstruct the merged dataframe
    merged_df = pd.concat([header_row, dtype_row, merged_data], ignore_index=True)

    # Fill NaN with empty strings
    merged_df = merged_df.fillna('')

    # Save to CSV without index and header
    merged_df.to_csv(output_file, index=False, header=False)

    
def get_default_value(dtype):
    if dtype == 'boolean':
        return 'False'
    elif dtype == 'string':
        return ''
    elif dtype == 'int':
        return '0'
    elif dtype == 'float':
        return '0.0'
    else:
        return ''

def value_to_string(value, dtype):
    if dtype == 'boolean':
        return 'True' if value else 'False'
    else:
        return str(value)

def apply_config(df, file):
    mod_config = config.get("values", {})
    col_data_types = {}

    # Assume the data type row is at index 0 after setting columns and dropping header row
    dtype_row_index = df.index[0]  # The index of data type row
    data_start_indices = df.index[1:]  # Indices where data starts

    # Step 1: Collect all columns from the config and determine their data types
    for csv_file, entries in mod_config.items():
        if file.endswith(csv_file):
            for identifier, updates in entries.items():
                for col, value in updates.items():
                    if col not in col_data_types:
                        if isinstance(value, bool):
                            col_data_types[col] = 'boolean'
                        elif isinstance(value, str):
                            col_data_types[col] = 'string'
                        elif isinstance(value, int):
                            col_data_types[col] = 'int'
                        elif isinstance(value, float):
                            col_data_types[col] = 'float'
                        else:
                            col_data_types[col] = 'string'  # Default to string

    # Step 2: Add any new columns to df
    for col, dtype in col_data_types.items():
        if col not in df.columns:
            df[col] = ''
            # Assign data type in the data type row
            df.loc[dtype_row_index, col] = dtype
            # Assign default values in data rows
            default_value = get_default_value(dtype)
            df.loc[data_start_indices, col] = default_value
        else:
            # Ensure data type is set for existing columns
            if pd.isna(df.loc[dtype_row_index, col]) or df.loc[dtype_row_index, col] == '':
                df.loc[dtype_row_index, col] = dtype

    # Step 3: Apply default values under '*'
    for csv_file, entries in mod_config.items():
        if file.endswith(csv_file):
            if "*" in entries:
                updates = entries["*"]
                for col, value in updates.items():
                    if col in df.columns:
                        dtype = df.loc[dtype_row_index, col]
                        default_value = get_default_value(dtype)
                        value_str = value_to_string(value, dtype)
                        for index in data_start_indices:
                            current_value = df.at[index, col]
                            # Only overwrite if current value is empty or default
                            if pd.isna(current_value) or current_value == default_value or current_value == '':
                                df.at[index, col] = value_str

            # Step 4: Apply specific updates for identifiers
            for identifier, updates in entries.items():
                if identifier != "*":
                    for index in data_start_indices:
                        if df.at[index, df.columns[0]] == identifier:
                            for col, value in updates.items():
                                if col in df.columns:
                                    dtype = df.loc[dtype_row_index, col]
                                    value_str = value_to_string(value, dtype)
                                    df.at[index, col] = value_str
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
