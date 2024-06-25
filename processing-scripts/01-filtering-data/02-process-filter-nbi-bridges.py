import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def calculate_lat_dd(lat_016):
    """
    Function to calculate latitude in decimal degrees from the given format
    """
    lat_016 = str(lat_016).zfill(8)  # Ensure the string is at least 8 characters long
    degrees = int(lat_016[:2])  # Extract degrees
    minutes = int(lat_016[2:4]) / 60  # Extract minutes and convert to degrees
    seconds = (
        float(lat_016[4:6] + "." + lat_016[6:8]) / 3600
    )  # Extract seconds and convert to degrees
    return degrees + minutes + seconds


# Function to calculate longitude in decimal degrees from the given format
def calculate_long_dd(long_017):
    """
    Function to calculate longitude in decimal degrees from the given format
    """
    long_017 = str(long_017).zfill(9)  # Ensure the string is at least 9 characters long
    degrees = int(long_017[:3])
    minutes = int(long_017[3:5]) / 60
    seconds = float(long_017[5:7] + "." + long_017[7:9]) / 3600
    return -(degrees + minutes + seconds)


# List to keep track of bridges to be excluded
exclude_bridges = []


def determine_final_values(row):
    """
    Function to determine the final latitude and longitude values based on duplicate status
    """
    if row["is_duplicate_new"]:
        if row["is_duplicate_old"]:
            exclude_bridges.append(row["STRUCTURE_NUMBER_008"])
            return pd.Series([None, None])  # Placeholder values
        return pd.Series(
            [row["LATDD"], row["LONGDD"]]
        )  # Return old coordinates if not duplicates
    else:
        return pd.Series(
            [row["LAT_DD_new"], row["LONG_DD_new"]]
        )  # Return new coordinates if not duplicates


def exclude_duplicate_bridges(df, output_duplicate_exclude_csv):
    """
    Function to exclude duplicate bridges, remove non-posted culverts and save the result to a CSV
    """

    # Check for duplicates in new and old coordinates
    df["is_duplicate_new"] = df.duplicated(
        subset=["LAT_DD_new", "LONG_DD_new"], keep=False
    )
    df["is_duplicate_old"] = df.duplicated(subset=["LATDD", "LONGDD"], keep=False)

    df[["LAT_Final", "LONG_Final"]] = df.apply(determine_final_values, axis=1)

    # Exclude bridges that are marked for exclusion
    df = df[~df["STRUCTURE_NUMBER_008"].isin(exclude_bridges)]

    # Drop the duplicate check columns
    df.drop(columns=["is_duplicate_new", "is_duplicate_old"], inplace=True)

    # Remove culverts which are not posted
    df = df[
        ~((df["STRUCTURE_TYPE_043B"] == 19) & (df["OPEN_CLOSED_POSTED_041"] != "P"))
    ]

    df.to_csv(output_duplicate_exclude_csv, index=False)

    return df


def convert_to_gpkg(df, output_gpkg_file):
    """
    Function to convert the DataFrame to a GeoPackage
    """

    # Create geometry from latitude and longitude
    geometry = [Point(xy) for xy in zip(df["LONG_Final"], df["LAT_Final"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry)

    gdf.to_file(output_gpkg_file, driver="GPKG")

    print(f"GeoPackage saved successfully to {output_gpkg_file}")


def process_coordinates(
    input_csv, output_convert_csv, output_duplicate_exclude_csv, output_gpkg_file
):
    """
    Funtion to perform processing of coordinates and filtering of bridges
    """
    # Read the input CSV
    df = pd.read_csv(
        input_csv, dtype={"LAT_016": str, "LONG_017": str}, low_memory=False
    )

    # Handle missing values by filling with zeros
    df["LAT_016"] = df["LAT_016"].fillna("00000000")
    df["LONG_017"] = df["LONG_017"].fillna("000000000")

    # Calculate LAT_DD and LONG_DD
    df["LAT_DD_new"] = df["LAT_016"].apply(calculate_lat_dd)
    df["LONG_DD_new"] = df["LONG_017"].apply(calculate_long_dd)

    # Write to a new CSV
    df.to_csv(output_convert_csv, index=False)

    # Exclude duplicate bridges and save the result to a CSV
    df = exclude_duplicate_bridges(df, output_duplicate_exclude_csv)

    # Convert the final DataFrame to a GeoPackage file
    convert_to_gpkg(df, output_gpkg_file)


input_csv = "input-data/Kentucky-NBI-bridge-data.csv"
output_convert_csv = "output-data/csv-files/Kentucky-bridge-converted-coordinates.csv"
output_duplicate_exclude_csv = (
    "output-data/csv-files/Kentucky-bridge-chosen-coordinates.csv"
)
output_gpkg_file = "output-data/gpkg-files/NBI-Kentucky-Bridge-Data.gpkg"
process_coordinates(
    input_csv, output_convert_csv, output_duplicate_exclude_csv, output_gpkg_file
)
