import requests
import json
import streamlit as st
from PIL import Image, UnidentifiedImageError, ImageFile
from io import BytesIO
from db import bytes_to_megabytes
from pillow_heif import register_heif_opener
import os

# module scope
assets = []
base_url = None
api_key = None
timeout = None

def api_init(immich_server_url, immich_api_key, api_timeout):
    global base_url, api_key, timeout
    base_url = immich_server_url.rstrip('/') + '/api'
    api_key = immich_api_key
    timeout = api_timeout

@st.cache_data(show_spinner=True)
def fetchAssets(type):
    global assets

    if 'fetch_message' not in st.session_state:
        st.session_state['fetch_message'] = ""
    message_placeholder = st.empty()
    assets = []

    asset_paths_url = f"{base_url}/view/folder/unique-paths"
    asset_info_url  = f"{base_url}/view/folder"
    # st.write(f"Debug: asset_paths_url = {asset_paths_url}")
    # st.write(f"Debug: asset_info_url = {asset_info_url}")

    try:
        with st.spinner('Fetching assets...'):
            # st.write(f"Debug: Sending GET to {asset_paths_url}")
            response = requests.get(
                asset_paths_url,
                headers={'Accept': 'application/json', 'x-api-key': api_key},
                verify=False,
                timeout=timeout
            )
            # st.write(f"Debug: Received status {response.status_code} from {response.url}")
            # st.write(f"Debug: Response headers: {response.headers}")
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type and response.text:
                paths = response.json()
            else:
                st.session_state['fetch_message'] = (
                    f'Unexpected response: {content_type} / {response.text}'
                )
                paths = []

            for path in paths:
                if not path:
                    continue
                # st.write(f"Debug: Fetching assets for path: {path}")
                # st.write(f"Debug: GET {asset_info_url}?path={path}")
                r2 = requests.get(
                    f"{asset_info_url}?path={path}",
                    headers={'Accept': 'application/json', 'x-api-key': api_key},
                    verify=False,
                    timeout=timeout
                )
                # st.write(f"Debug: Received status {r2.status_code} from {r2.url}")
                r2.raise_for_status()
                if 'application/json' in r2.headers.get('Content-Type', '') and r2.text:
                    assets.extend(r2.json())
                else:
                    st.session_state['fetch_message'] = (
                        f'Unexpected for path {path}: {r2.headers.get("Content-Type")}'
                    )

            # Debug: report before filtering
            print(f"DEBUG fetchAssets: total assets before filtering: {len(assets)}")
            if assets:
                sample_types = [a.get("type") for a in assets][:10]
                print(f"DEBUG fetchAssets: sample asset types: {sample_types}")

            # Debug: filter by requested asset type
            filtered_assets = [a for a in assets if a.get("type") == type]
            print(f"DEBUG fetchAssets: assets after filtering by type '{type}': {len(filtered_assets)}")
            assets = filtered_assets

            # Debug: show sample IDs
            sample_ids = [a.get("id") for a in assets][:10]
            print(f"DEBUG fetchAssets: sample asset IDs after filtering: {sample_ids}")

            st.session_state['fetch_message'] = 'Assets fetched successfully!'

    except requests.exceptions.ConnectTimeout:
        st.session_state['fetch_message'] = 'Connection timed out.'
        assets = []

    except requests.exceptions.HTTPError as e:
        st.session_state['fetch_message'] = f'HTTP error: {e}'
        assets = []

    except requests.exceptions.RequestException as e:
        st.session_state['fetch_message'] = f'Request error: {e}'
        assets = []

    message_placeholder.text(st.session_state['fetch_message'])
    return assets

def getImage(asset_id, photo_choice):
    register_heif_opener()
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    # Debug: log entry
    print(f"DEBUG getImage: fetching asset_id={asset_id}, size choice={photo_choice}")

    # Determine endpoint based on selected size
    # Supported sizes per Immich API: thumbnail, preview, fullsize
    if photo_choice == 'Thumbnail':
        endpoint = 'thumbnail'
    elif photo_choice == 'Preview':
        endpoint = 'preview'
    elif photo_choice == 'Full Size':
        endpoint = 'fullsize'
    else:
        endpoint = 'thumbnail'

    url = f"{base_url}/assets/{asset_id}/thumbnail?size={endpoint}"
    headers = {
        'Accept': 'application/octet-stream',
        'x-api-key': api_key
    }

    # Debug: request URL and headers
    print(f"DEBUG getImage: URL = {url}")
    print(f"DEBUG getImage: Headers = {headers}")

    try:
        response = requests.get(
            url,
            headers=headers,
            verify=False,
            timeout=timeout
        )
        print(f"DEBUG getImage: Response status={response.status_code}, Content-Type={response.headers.get('Content-Type')}")
    except requests.RequestException as e:
        print(f"DEBUG getImage: RequestException for asset_id {asset_id}: {e}")
        return None

    # Wenn wir ein Bild zurückbekommen, öffne es, sonst logge und return None
    if response.status_code == 200 and 'image/' in response.headers.get('Content-Type', ''):
        try:
            image = Image.open(BytesIO(response.content))
            image.load()
            return image
        except UnidentifiedImageError:
            print(
                f"Failed to identify image for asset_id {asset_id}. "
                f"Content-Type: {response.headers.get('Content-Type')}"
            )
            return None
    else:
        print(
            f"Skipping non-image asset_id {asset_id} with "
            f"Content-Type: {response.headers.get('Content-Type')}"
        )
        return None

@st.cache_data
def fetch_asset_info(asset_id):
    url = f"{base_url}/assets/{asset_id}"
    response = requests.get(
        url,
        headers={'Accept': 'application/json', 'x-api-key': api_key},
        verify=False,
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()

def getAssetInfo(asset_id):
    """Return detailed info tuple or None for a given asset_id."""
    # Try to find the asset in the in-memory list
    asset = next((a for a in assets if a.get('id') == asset_id), None)
    if asset is None:
        asset = fetch_asset_info(asset_id)
    if asset is None:
        return None

    # Safely extract EXIF info
    exif = asset.get('exifInfo') or {}

    # File size in MB
    try:
        file_size = bytes_to_megabytes(exif.get('fileSizeInByte', 0))
    except Exception:
        file_size = "Unknown"

    # Original file name
    file_name = asset.get('originalFileName', 'Unknown')

    # Resolution
    height = exif.get('exifImageHeight', 'Unknown')
    width = exif.get('exifImageWidth', 'Unknown')
    resolution = f"{height} x {width}"

    # Lens model
    lens = exif.get('lensModel', 'Unknown')

    # Original creation date
    date_original = exif.get('dateTimeOriginal') or asset.get('fileCreatedAt', 'Unknown')

    # Original path and flags
    path = asset.get('originalPath', 'Unknown')
    is_offline = asset.get('isOffline', False)
    is_trashed = asset.get('isTrashed', False)
    is_favorite = asset.get('isFavorite', False)

    return (
        file_size,
        file_name,
        resolution,
        lens,
        date_original,
        path,
        is_offline,
        is_trashed,
        is_favorite
    )

def deleteAsset(asset_id):
    st.session_state['show_faiss_duplicate'] = False
    url = f"{base_url}/assets"
    payload = json.dumps({"force": True, "ids": [asset_id]})
    headers = {'Content-Type': 'application/json', 'x-api-key': api_key}

    try:
        response = requests.delete(url, headers=headers, data=payload)
        if response.status_code == 204:
            st.write(f"Successfully deleted asset with ID: {asset_id}")
            return True
        else:
            try:
                error_message = response.json().get('message', 'No additional error message provided.')
            except ValueError:
                error_message = 'Response content is not valid JSON.'
            st.error(f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}")
            return False
    except requests.RequestException as e:
        st.error(f"Request failed: {str(e)}")
        return False

def updateAsset(asset_id, dateTimeOriginal, description, isFavorite, latitude, longitude, isArchived):
    url = f"{base_url}/assets/{asset_id}"
    payload = json.dumps({
        "dateTimeOriginal": dateTimeOriginal,
        "description": description,
        "isArchived": isArchived,
        "isFavorite": isFavorite,
        "latitude": latitude,
        "longitude": longitude
    })
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'x-api-key': api_key}

    try:
        response = requests.put(url, headers=headers, data=payload)
        if response.status_code == 200:
            st.success(f"Successfully updated asset with ID: {asset_id}")
            return True
        else:
            error_message = response.json().get('message', 'No additional error message provided.')
            st.error(f"Failed to update asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}")
            return False
    except requests.RequestException as e:
        st.error(f"Request failed: {str(e)}")
        return False

def getVideoAndSave(asset_id, save_directory):
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    # st.write(f"Debug: Downloading video for asset_id {asset_id} from URL: {url}")
    url = f"{base_url}/download-asset/{asset_id}"
    response = requests.get(
        url,
        headers={'Accept': 'application/octet-stream', 'x-api-key': api_key},
        stream=True,
        timeout=timeout
    )
    # st.write(f"Debug: Video response status {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
    file_path = os.path.join(save_directory, f"{asset_id}.mp4")
    if response.status_code == 200 and 'video/' in response.headers.get('Content-Type', ''):
        with open(file_path, 'wb') as f:
            f.write(response.content)
        return file_path
    else:
        print(f"Failed to retrieve video for asset_id {asset_id}. Status Code: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
        return None